"""Offline tests for the temporary Truth Social latency probe (no network)."""

import argparse
import json

import ts_probe as tp

OLD = {"id": "115000000000000001", "created_at": "2026-09-30T01:00:00Z"}
NEW = {"id": "115000000000000002", "created_at": "2026-09-30T01:20:00Z"}


def _rss(items: str) -> bytes:
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode()


def test_parse_mastodon() -> None:
    assert tp.parse_mastodon(json.dumps([NEW, OLD]).encode())[0]["id"] == NEW["id"]


def test_parse_cnn_sorts_newest_first_and_falls_back_to_url() -> None:
    body = json.dumps(
        [
            OLD,
            {
                "url": "https://truthsocial.com/@realDonaldTrump/115000000000000002",
                "created_at": NEW["created_at"],
            },
        ]
    ).encode()
    posts = tp.parse_cnn(body)
    assert [p["id"] for p in posts] == [NEW["id"], OLD["id"]]


def test_parse_rss_extracts_status_id_or_falls_back_to_guid() -> None:
    posts = tp.parse_rss(
        _rss(
            "<item><guid>https://trumpstruth.org/statuses/2</guid>"
            "<pubDate>Tue, 30 Sep 2026 01:20:00 +0000</pubDate></item>"
            "<item><link>https://trumpstruth.org/statuses/1</link>"
            "<description>https://truthsocial.com/@realDonaldTrump/115000000000000001</description>"
            "<pubDate>Tue, 30 Sep 2026 01:00:00 +0000</pubDate></item>"
        )
    )
    assert posts[0]["id"] == "rss:https://trumpstruth.org/statuses/2"
    assert posts[0]["created_at"] == "2026-09-30T01:20:00+00:00"
    assert posts[1]["id"] == OLD["id"]


def test_poll_logs_block_and_only_new_posts_after_baseline(
    tmp_path, monkeypatch, capsys
) -> None:
    feed = [[OLD], [NEW, OLD]]
    monkeypatch.setattr(
        tp,
        "SOURCES",
        {
            "direct": (
                "u",
                lambda url, etag=None: (
                    200,
                    {"server": "cloudflare"},
                    json.dumps(feed[0]).encode(),
                ),
                tp.parse_mastodon,
            ),
            "direct_cf": (
                "u",
                lambda url, etag=None: (
                    403,
                    {"cf-mitigated": "challenge"},
                    b"Just a moment",
                ),
                tp.parse_mastodon,
            ),
        },
    )
    seen = {n: set() for n in tp.SOURCES}
    first = {n: True for n in tp.SOURCES}
    log = tmp_path / "probe.jsonl"
    with open(log, "w") as out:
        for _ in range(2):
            for name in tp.SOURCES:
                tp.poll_once(name, seen, first, out)
            feed.pop(0)
    records = [json.loads(line) for line in log.read_text().splitlines()]
    new_posts = [r for r in records if r["type"] == "new_post"]
    assert [(r["source"], r["id"]) for r in new_posts] == [("direct", NEW["id"])]
    assert {r["status"] for r in records if r.get("source") == "direct_cf"} == {403}

    capsys.readouterr()
    tp.cmd_summarize(argparse.Namespace(file=str(log)))
    summary = capsys.readouterr().out
    assert "direct_cf    ok 0/2" in summary and "direct       ok 2/2" in summary


def test_etag_is_sent_and_304_is_logged_without_parsing(tmp_path, monkeypatch) -> None:
    sent = []

    def fetch(url, etag=None):
        sent.append(etag)
        if etag == '"v1"':
            return 304, {"etag": '"v1"'}, b""
        return 200, {"etag": '"v1"'}, json.dumps([OLD]).encode()

    monkeypatch.setattr(tp, "SOURCES", {"cnn": ("u", fetch, tp.parse_mastodon)})
    monkeypatch.setattr(tp, "ETAGS", {})
    seen, first = {"cnn": set()}, {"cnn": True}
    log = tmp_path / "probe.jsonl"
    with open(log, "w") as out:
        tp.poll_once("cnn", seen, first, out)
        tp.poll_once("cnn", seen, first, out)
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert sent == [None, '"v1"']
    assert [r["status"] for r in records] == [200, 304]


def test_parse_rss_prefers_original_url_over_linked_post() -> None:
    posts = tp.parse_rss(
        _rss(
            '<item xmlns:truth="https://truthsocial.com/ns">'
            "<link>https://www.trumpstruth.org/statuses/41825</link>"
            '<description>&lt;a href="https://truthsocial.com/@realDonaldTrump/'
            '117304284426928910"&gt;earlier post&lt;/a&gt;</description>'
            "<pubDate>Sun, 21 Sep 2026 14:00:00 +0000</pubDate>"
            "<truth:originalUrl>https://truthsocial.com/@realDonaldTrump/"
            "117307289681145880</truth:originalUrl></item>"
        )
    )
    assert posts[0]["id"] == "117307289681145880"


def test_fetch_urllib_decompresses_gzip(monkeypatch) -> None:
    import gzip
    import io
    import urllib.request

    class Resp(io.BytesIO):
        status = 200
        headers = {"Content-Encoding": "gzip", "ETag": '"v1"'}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout: Resp(gzip.compress(b"[1]"))
    )
    status, headers, body = tp.fetch_urllib("https://example.test")
    assert (status, body, headers["etag"]) == (200, b"[1]", '"v1"')
