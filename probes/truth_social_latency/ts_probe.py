#!/usr/bin/env python3
"""Read-only latency probe for free Truth Social sources.

Polls three sources on an interval and logs, per source, whether the request
worked and when each Trump post was first seen. Writes nothing anywhere except
JSON lines to stdout (Railway logs) and, optionally, a local file.

Sources:
  direct     truthsocial.com public Mastodon-style statuses endpoint (no auth)
  direct_cf  same URL via curl_cffi Chrome impersonation, if curl_cffi is installed
  cnn        CNN archive JSON (ix.cnn.io)
  trumpstruth  trumpstruth.org RSS feed

Usage:
  python ts_probe.py poll [--interval 20] [--hours 24] [--out probe.jsonl]
  python ts_probe.py summarize probe.jsonl

Default sources are the mirrors only (cnn, trumpstruth). The direct sources stay
off until Chris opts in to polling truthsocial.com; enable them with
--sources direct,direct_cf,cnn,trumpstruth.

Conditional GETs (ETag / If-None-Match) keep frequent polls cheap: an unchanged
feed answers 304 with no body.

Standard library only (curl_cffi optional). No credentials, no database.
"""

from __future__ import annotations

import argparse
import email.utils
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable, Optional

TRUMP_ACCOUNT_ID = "107780257626128497"
DIRECT_URL = (
    f"https://truthsocial.com/api/v1/accounts/{TRUMP_ACCOUNT_ID}/statuses"
    "?exclude_replies=true&limit=20"
)
CNN_URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
TRUMPSTRUTH_URL = "https://trumpstruth.org/feed"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
STATUS_ID_RE = re.compile(r"truthsocial\.com/@realDonaldTrump/(?:posts/)?(\d{15,})")
# Seconds between polls per source, on top of --interval. Keeps load on the
# volunteer-run RSS and on truthsocial.com at one request a minute.
MIN_INTERVAL_S = {"direct": 60, "direct_cf": 60, "trumpstruth": 60}
ETAGS: dict[str, str] = {}
KEEP_HEADERS = (
    "etag",
    "server",
    "cf-ray",
    "cf-mitigated",
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_rfc822(value: str) -> Optional[datetime]:
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Fetchers: return (http_status, headers dict, body bytes) ──────────────


def fetch_urllib(
    url: str, etag: Optional[str] = None, timeout: int = 20
) -> tuple[int, dict, bytes]:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (
                resp.status,
                {k.lower(): v for k, v in resp.headers.items()},
                resp.read(),
            )
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def fetch_curl_cffi(
    url: str, etag: Optional[str] = None, timeout: int = 20
) -> tuple[int, dict, bytes]:
    from curl_cffi import requests as cffi  # optional dependency

    headers = {"If-None-Match": etag} if etag else None
    resp = cffi.get(url, impersonate="chrome", timeout=timeout, headers=headers)
    return (
        resp.status_code,
        {k.lower(): v for k, v in resp.headers.items()},
        resp.content,
    )


# ── Parsers: body -> list of {"id", "created_at"} ─────────────────────────


def parse_mastodon(body: bytes) -> list[dict]:
    data = json.loads(body)
    return [{"id": str(s["id"]), "created_at": s.get("created_at")} for s in data]


def parse_cnn(body: bytes) -> list[dict]:
    data = json.loads(body)
    if isinstance(data, dict):
        data = data.get("posts") or data.get("data") or []
    posts = []
    for p in data:
        pid = str(p.get("id") or "")
        if not pid:
            m = STATUS_ID_RE.search(p.get("url", ""))
            pid = m.group(1) if m else ""
        if pid:
            posts.append({"id": pid, "created_at": p.get("created_at")})
    # Archive is large; newest-first ordering is not guaranteed, so sort.
    posts.sort(key=lambda p: p["created_at"] or "", reverse=True)
    return posts[:50]


def parse_rss(body: bytes) -> list[dict]:
    root = ET.fromstring(body)
    posts = []
    for item in root.iter("item"):
        blob = " ".join(
            filter(
                None,
                (
                    item.findtext("link"),
                    item.findtext("guid"),
                    item.findtext("description"),
                    *(el.text or "" for el in item if el.tag.endswith("originalUrl")),
                ),
            )
        )
        m = STATUS_ID_RE.search(blob)
        pid = (
            m.group(1)
            if m
            else "rss:" + (item.findtext("guid") or item.findtext("link") or "")
        )
        pub = parse_rfc822(item.findtext("pubDate") or "")
        posts.append({"id": pid, "created_at": pub.isoformat() if pub else None})
    return posts


SOURCES: dict[str, tuple[str, Callable, Callable]] = {
    "direct": (DIRECT_URL, fetch_urllib, parse_mastodon),
    "direct_cf": (DIRECT_URL, fetch_curl_cffi, parse_mastodon),
    "cnn": (CNN_URL, fetch_urllib, parse_cnn),
    "trumpstruth": (TRUMPSTRUTH_URL, fetch_urllib, parse_rss),
}


def emit(record: dict, out) -> None:
    line = json.dumps(record, default=str)
    print(line, flush=True)
    if out:
        out.write(line + "\n")
        out.flush()


def poll_once(
    name: str, seen: dict[str, set], first_poll: dict[str, bool], out
) -> None:
    url, fetch, parse = SOURCES[name]
    started = now_utc()
    rec = {"type": "poll", "source": name, "at": started.isoformat()}
    try:
        status, headers, body = fetch(url, ETAGS.get(name))
        rec.update(
            status=status,
            ms=int((now_utc() - started).total_seconds() * 1000),
            bytes=len(body),
            headers={k: headers[k] for k in KEEP_HEADERS if k in headers},
        )
        if status == 304:
            emit(rec, out)
            return
        if status != 200:
            rec["body_head"] = body[:200].decode("utf-8", "replace")
            emit(rec, out)
            return
        posts = parse(body)
        rec["n_posts"] = len(posts)
        if headers.get("etag"):
            ETAGS[name] = headers["etag"]
    except ImportError:
        return  # curl_cffi not installed; skip direct_cf silently
    except Exception as e:  # noqa: BLE001 - probe logs every failure mode
        rec.update(error=f"{type(e).__name__}: {e}")
        emit(rec, out)
        return
    emit(rec, out)

    for p in posts:
        if p["id"] in seen[name]:
            continue
        seen[name].add(p["id"])
        if first_poll[name]:
            continue  # baseline: posts that existed before the probe started
        created = parse_iso(p["created_at"] or "")
        emit(
            {
                "type": "new_post",
                "source": name,
                "id": p["id"],
                "created_at": p["created_at"],
                "first_seen": rec["at"],
                "lag_s": round((started - created).total_seconds())
                if created
                else None,
            },
            out,
        )
    first_poll[name] = False


def cmd_poll(args: argparse.Namespace) -> None:
    out = open(args.out, "a") if args.out else None
    names = args.sources.split(",")
    seen = {n: set() for n in names}
    first_poll = {n: True for n in names}
    deadline = time.monotonic() + args.hours * 3600
    emit(
        {
            "type": "start",
            "at": now_utc().isoformat(),
            "sources": names,
            "interval_s": args.interval,
        },
        out,
    )
    last_poll = {n: float("-inf") for n in names}
    while time.monotonic() < deadline:
        tick = time.monotonic()
        for name in names:
            if tick - last_poll[name] >= MIN_INTERVAL_S.get(name, 0):
                last_poll[name] = tick
                poll_once(name, seen, first_poll, out)
        time.sleep(max(0, args.interval - (time.monotonic() - tick)))


def cmd_summarize(args: argparse.Namespace) -> None:
    polls: dict[str, list] = {}
    lags: dict[str, list] = {}
    for line in open(args.file):
        line = line.strip()
        if not line.startswith("{"):
            continue  # tolerate Railway log prefixes / noise
        r = json.loads(line)
        if r.get("type") == "poll":
            polls.setdefault(r["source"], []).append(r)
        elif r.get("type") == "new_post" and r.get("lag_s") is not None:
            lags.setdefault(r["source"], []).append(r["lag_s"])
    for src, rs in polls.items():
        ok = sum(1 for r in rs if r.get("status") in (200, 304) and "error" not in r)
        codes: dict = {}
        for r in rs:
            key = r.get("status", r.get("error", "?")[:40])
            codes[key] = codes.get(key, 0) + 1
        ls = sorted(lags.get(src, []))
        lag_txt = (
            (
                f"median {statistics.median(ls):.0f}s, p90 {ls[int(0.9 * (len(ls) - 1))]}s, "
                f"max {ls[-1]}s over {len(ls)} posts"
            )
            if ls
            else "no new posts"
        )
        print(
            f"{src:12} ok {ok}/{len(rs)} ({100 * ok / len(rs):.1f}%)  codes {codes}  lag: {lag_txt}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("poll")
    p.add_argument("--interval", type=int, default=20)
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--sources", default="cnn,trumpstruth")
    p.add_argument("--out")
    s = sub.add_parser("summarize")
    s.add_argument("file")
    args = ap.parse_args()
    {"poll": cmd_poll, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
