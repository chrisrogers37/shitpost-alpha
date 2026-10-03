"""Each feed maps its fixtures; what counts as blocked or failed. No database, no network."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
import pytest

from engine.feeds import cnn
from engine.feeds.base import Feed, FeedBlocked, FeedFailed
from engine.feeds.cnn import HEAD_BYTES, CnnFeed, download_archive, leading_items
from engine.feeds.live import FEEDS
from engine.feeds.mastodon import DirectFeed, ScrapeCreatorsFeed
from engine.feeds.posts import ACCOUNT_ID, Post
from engine.feeds.trumpstruth import TrumpstruthFeed, feed_post, parse_items
from engine.http_client import make_client
from engine.registry import build_registry
from engine.settings import FEED_NAMES, Settings
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    TRUMPSTRUTH_HOST,
    FakeWeb,
    Route,
    cf_mitigated,
    challenge,
    fixture_bytes,
    fixture_json,
    html_page,
    json_response,
    status,
)

# status id: (kind, points_to, has_media, not_scored), in both hand-built fixtures
MASTODON_EXPECTED = {
    "117371353802794328": ("post", None, False, None),
    "117369900687288624": ("repost", "117367780569149238", False, "repost"),
    "117369458827039533": ("reply", "117369363664701946", False, None),
    "117368266436035432": ("post", None, True, "no_text"),
    "117307289681145880": ("quote", "117304284426928910", False, None),
}


@pytest.fixture
def offline_settings() -> Settings:
    return Settings(database_url="postgresql://unused/unused", scrapecreators_key="test-key")


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


def by_id(posts: list[Post]) -> dict[str, Post]:
    return {post.status_id: post for post in posts}


def parse_feed(body: bytes, settings: Settings) -> list[Post]:
    return TrumpstruthFeed(httpx.AsyncClient(), settings).map_items(parse_items(body), feed_post)


def assert_mastodon_mapping(posts: list[Post]) -> None:
    mapped = by_id(posts)
    assert {
        i: (p.kind, p.points_to, p.has_media, p.not_scored) for i, p in mapped.items()
    } == MASTODON_EXPECTED
    reply = mapped["117369458827039533"]
    assert reply.key == "truth_social:117369458827039533"
    assert reply.url == "https://truthsocial.com/@realDonaldTrump/117369458827039533"
    assert reply.text == (
        "America does not belong to those who hate it.\n\n"
        "America belongs to those who love it! President DONALD J. TRUMP"
    )
    assert mapped["117307289681145880"].text == "Read this!"
    for post in posts:  # the id's time matches the status's created_at
        assert post.posted_at.isoformat().startswith(post.raw["created_at"][:19])


async def test_direct_maps_post_reply_quote_repost_and_media_only(
    web: FakeWeb, offline_settings: Settings
) -> None:
    async with web.client(offline_settings) as client:
        read = await DirectFeed(client, offline_settings).read()
    assert_mastodon_mapping(read.posts)

    (request,) = web.requests
    assert request.url.params["exclude_replies"] == "true"
    assert request.url.params["limit"] == "20"
    assert request.headers["user-agent"].startswith("shitpost-alpha-engine/")


async def test_direct_skips_statuses_from_other_accounts(
    web: FakeWeb, offline_settings: Settings
) -> None:
    statuses = fixture_json("direct_statuses.unverified.json")
    statuses[0]["account"] = {"id": "1"}
    web.routes[DIRECT_HOST] = lambda request: json_response(statuses)
    async with web.client(offline_settings) as client:
        read = await DirectFeed(client, offline_settings).read()
    assert len(read.posts) == len(statuses) - 1


BLOCKS: list[tuple[Route, str]] = [
    (status(403), "HTTP 403"),
    (status(429), "HTTP 429"),
    (challenge, "HTTP 403"),
    (html_page, "challenge page"),
    (cf_mitigated, "cf-mitigated"),
]


@pytest.mark.parametrize(("route", "reason"), BLOCKS)
async def test_direct_block_signals(
    web: FakeWeb, offline_settings: Settings, route: Route, reason: str
) -> None:
    web.routes[DIRECT_HOST] = route
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedBlocked, match=reason):
            await DirectFeed(client, offline_settings).read()


@pytest.mark.parametrize(
    "route",
    [
        status(500),
        lambda request: json_response({"error": "x"}),
        lambda request: httpx.Response(200, text="not json"),
        lambda request: json_response([None, 3, "x"]),  # nothing in it maps
    ],
)
async def test_other_errors_are_failures_not_blocks(
    web: FakeWeb, offline_settings: Settings, route: Route
) -> None:
    web.routes[DIRECT_HOST] = route
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedFailed):
            await DirectFeed(client, offline_settings).read()


async def test_a_network_error_is_a_failure(web: FakeWeb, offline_settings: Settings) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    web.routes[DIRECT_HOST] = broken
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedFailed, match="ConnectError"):
            await DirectFeed(client, offline_settings).read()


async def test_one_odd_status_is_skipped_and_the_rest_kept(
    web: FakeWeb, offline_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    statuses = [None, *fixture_json("direct_statuses.unverified.json")]
    web.routes[DIRECT_HOST] = lambda request: json_response(statuses)
    async with web.client(offline_settings) as client:
        feed = DirectFeed(client, offline_settings)
        assert len((await feed.read()).posts) == 5
        assert len((await feed.read()).posts) == 5
    skipped = [r for r in caplog.records if "skipped 1 of 6 items" in r.getMessage()]
    assert len(skipped) == 1  # logged once, not every poll


async def test_the_same_odd_item_is_logged_once_as_new_posts_arrive(
    web: FakeWeb, offline_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    statuses = fixture_json("direct_statuses.unverified.json")
    feed_now: list[object] = [None, *statuses[1:]]
    web.routes[DIRECT_HOST] = lambda request: json_response(feed_now)
    async with web.client(offline_settings) as client:
        feed = DirectFeed(client, offline_settings)
        await feed.read()
        feed_now.insert(1, statuses[0])  # a new post arrives; the odd item is still there
        await feed.read()
    assert caplog.text.count("items that don't map") == 1


async def test_direct_sends_if_none_match_and_reads_304_as_not_modified(
    web: FakeWeb, offline_settings: Settings
) -> None:
    web.routes[DIRECT_HOST] = lambda request: (
        httpx.Response(304)
        if request.headers.get("if-none-match") == 'W/"v1"'
        else json_response(
            fixture_json("direct_statuses.unverified.json"), headers={"etag": 'W/"v1"'}
        )
    )
    async with web.client(offline_settings) as client:
        feed = DirectFeed(client, offline_settings)
        first = await feed.read()
        assert len(first.posts) == 5 and first.etag == 'W/"v1"'
        assert (await feed.read()).posts  # the poller hasn't kept the ETag yet
        feed.etag = first.etag  # it keeps it once the posts are stored
        second = await feed.read()
    assert second.not_modified and second.posts == []
    assert "if-none-match" not in web.requests[0].headers


async def test_scrapecreators_maps_post_reply_quote_repost_and_media_only(
    web: FakeWeb, offline_settings: Settings
) -> None:
    async with web.client(offline_settings) as client:
        read = await ScrapeCreatorsFeed(client, offline_settings).read()
    assert_mastodon_mapping(read.posts)
    (request,) = web.requests
    assert request.headers["x-api-key"] == "test-key"
    assert request.url.params["user_id"] == ACCOUNT_ID


@pytest.mark.parametrize(
    ("route", "error"),
    [
        (status(401), FeedBlocked),
        (status(402), FeedBlocked),
        (challenge, FeedBlocked),
        (lambda request: json_response({"success": False}), FeedFailed),
        (lambda request: json_response({"success": True, "posts": None}), FeedFailed),
        (lambda request: json_response(["not", "an", "object"]), FeedFailed),
    ],
)
async def test_scrapecreators_bad_key_is_blocked_and_odd_answers_fail(
    web: FakeWeb, offline_settings: Settings, route: Route, error: type[Exception]
) -> None:
    web.routes[SCRAPECREATORS_HOST] = route
    async with web.client(offline_settings) as client:
        with pytest.raises(error):
            await ScrapeCreatorsFeed(client, offline_settings).read()


async def test_cnn_parses_the_complete_posts_of_a_range_read(
    web: FakeWeb, offline_settings: Settings
) -> None:
    async with web.client(offline_settings) as client:
        read = await CnnFeed(client, offline_settings).read()
    (request,) = web.requests
    assert request.headers["range"] == "bytes=0-32767"
    assert request.headers["accept-encoding"] == "identity"

    assert len(read.posts) == 17  # the 18th is cut off part way
    newest = read.posts[0]
    assert (newest.status_id, newest.kind, newest.points_to, newest.has_media) == (
        "117369900687288624",
        "repost",
        "117367780569149238",
        True,
    )
    texts = by_id(read.posts)
    assert texts["117369458827039533"].text.startswith("America does not belong")
    assert texts["117369458827039533"].not_scored is None
    media_only = [p for p in read.posts if p.has_media and not p.text]
    assert media_only and all(p.not_scored == "no_text" for p in media_only)
    for post in read.posts:  # CNN's created_at agrees with the id's time to within 1 s
        created = datetime.fromisoformat(post.raw["created_at"])
        assert abs((post.posted_at - created).total_seconds()) < 1


def test_cnn_range_cut_inside_a_character() -> None:
    body = '[{"id": "117369900687288624", "content": "a"}, {"id": "1", "content": "café'
    raw = body.encode()[:-1]  # cut between the two bytes of é
    assert leading_items(raw) == [{"id": "117369900687288624", "content": "a"}]


@pytest.mark.parametrize(
    "body",
    [
        b'{"message": "Too many requests", "codes": [429]}',  # an error body answered 206
        b'{"items": [1, 2]}',
        b"[1, 2, 3",  # a list, but of no posts
    ],
)
async def test_cnn_odd_range_answers_fail(
    web: FakeWeb, offline_settings: Settings, body: bytes
) -> None:
    web.routes[CNN_HOST] = lambda request: httpx.Response(
        206, content=body, headers={"content-type": "application/json"}
    )
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedFailed):
            await CnnFeed(client, offline_settings).read()


async def test_cnn_reads_at_most_32_kb_and_fails_when_the_range_is_ignored(
    web: FakeWeb, offline_settings: Settings
) -> None:
    pulled: list[int] = []
    head = fixture_bytes("cnn_head.json")

    async def big_body() -> AsyncIterator[bytes]:
        chunk = head[:4096]
        yield head  # the real head, then far more than the range asked for
        for _ in range(250):
            pulled.append(len(chunk))
            yield chunk

    web.routes[CNN_HOST] = lambda request: httpx.Response(
        206, content=big_body(), headers={"content-type": "application/json"}
    )
    async with web.client(offline_settings) as client:
        read = await CnnFeed(client, offline_settings).read()
        assert len(read.posts) == 17
        assert len(head) + sum(pulled) <= HEAD_BYTES + 4096

        whole_file = []

        async def whole() -> AsyncIterator[bytes]:
            for _ in range(250):
                whole_file.append(1)
                yield head

        web.routes[CNN_HOST] = lambda request: httpx.Response(
            200, content=whole(), headers={"content-type": "application/json"}
        )
        with pytest.raises(FeedFailed, match="HTTP 200 to a range request"):
            await CnnFeed(client, offline_settings).read()
    assert len(whole_file) <= 1


async def test_cnn_range_reads_reuse_one_connection(offline_settings: Settings) -> None:
    """A 206 of exactly 32 KB and a 304 are read to their end, so the connection goes back
    to the pool (a new TLS handshake every 15 s otherwise)."""
    body = fixture_bytes("cnn_head.json").ljust(HEAD_BYTES, b" ")
    connections = 0

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        try:
            while True:
                if b"if-none-match" in (await reader.readuntil(b"\r\n\r\n")).lower():
                    writer.write(b'HTTP/1.1 304 Not Modified\r\netag: "v1"\r\n\r\n')
                else:
                    writer.write(
                        b"HTTP/1.1 206 Partial Content\r\ncontent-type: application/json\r\n"
                        + f"content-length: {len(body)}\r\n\r\n".encode()
                        + body
                    )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        async with make_client(offline_settings, httpx.AsyncHTTPTransport()) as client:
            feed = CnnFeed(client, offline_settings)
            feed_url = f"http://127.0.0.1:{port}/truth_archive.json"
            for unchanged in (False, True, True, False, True):
                feed.etag = '"v1"' if unchanged else None
                answer = await feed.get(feed_url, conditional=True, range_bytes=HEAD_BYTES)
                assert (answer is None) == unchanged
                assert answer is None or len(answer.body) == HEAD_BYTES
    finally:
        server.close()
        await server.wait_closed()
    assert connections == 1


async def test_cnn_304_only_for_the_etag_it_sent(web: FakeWeb, offline_settings: Settings) -> None:
    def archive(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(
            206,
            content=fixture_bytes("cnn_head.json"),
            headers={"content-type": "application/json", "etag": '"v1"'},
        )

    web.routes[CNN_HOST] = archive
    async with web.client(offline_settings) as client:
        feed = CnnFeed(client, offline_settings)
        first = await feed.read()
        feed.etag = first.etag
        assert (await feed.read()).not_modified
    assert web.requests[1].headers["if-none-match"] == '"v1"'


async def test_cnn_full_download_retries_a_cut_off_download(
    web: FakeWeb, offline_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cnn, "RETRY_PAUSE_SECONDS", 0)
    attempts = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("peer closed connection: incomplete chunked read")
        return json_response(fixture_json("archive_cnn_slice.json"))

    web.routes[CNN_HOST] = flaky
    async with web.client(offline_settings) as client:
        items = await download_archive(client, offline_settings)
    assert len(items) == 6 and len(attempts) == 2
    assert attempts[-1].headers["accept-encoding"] == "gzip"


@pytest.mark.parametrize(("route", "reason"), BLOCKS)
async def test_cnn_full_download_block_is_a_block_and_not_retried(
    web: FakeWeb, offline_settings: Settings, route: Route, reason: str
) -> None:
    web.routes[CNN_HOST] = route
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedBlocked, match=reason):
            await download_archive(client, offline_settings)
    assert len(web.requests) == 1


def test_trumpstruth_maps_items_and_takes_the_id_from_original_id(
    offline_settings: Settings,
) -> None:
    posts = by_id(parse_feed(fixture_bytes("trumpstruth_feed.xml"), offline_settings))
    assert len(posts) == 8

    # This item's description links another Trump post; it keeps its own id.
    linking = posts["117307289681145880"]
    assert (linking.kind, linking.points_to, linking.text) == ("quote", "117304284426928910", "")

    repost = posts["117369900687288624"]
    assert (
        repost.text
        == "RT: https://truthsocial.com/users/realDonaldTrump/statuses/117367780569149238"
    )
    assert (repost.kind, repost.points_to) == ("repost", "117367780569149238")

    media_only = posts["117368266436035432"]
    assert (media_only.text, media_only.has_media, media_only.not_scored) == ("", None, "no_text")

    first = posts["117371353802794328"]
    assert first.text.startswith("I am thrilled to announce the Republic of Korea Deal")
    assert "<p>" not in first.text and first.has_media is None
    assert first.raw["originalId"] == "117371353802794328"

    for post in posts.values():  # the id's time and pubDate (whole seconds) agree
        published = parsedate_to_datetime(str(post.raw["pubDate"]))
        assert 0 <= (post.posted_at - published).total_seconds() < 1


def rss_item(fields: str) -> bytes:
    return (
        '<rss xmlns:truth="https://truthsocial.com/ns"><channel>'
        f"<item><guid>g</guid>{fields}</item></channel></rss>"
    ).encode()


def test_trumpstruth_falls_back_to_original_url(offline_settings: Settings) -> None:
    body = rss_item(
        "<description>https://truthsocial.com/@realDonaldTrump/117304284426928910</description>"
        "<truth:originalUrl>https://truthsocial.com/@realDonaldTrump/117307289681145880"
        "</truth:originalUrl>"
    )
    (post,) = parse_feed(body, offline_settings)
    assert (post.status_id, post.points_to) == ("117307289681145880", "117304284426928910")


@pytest.mark.parametrize(
    "fields",
    [
        "<description>y</description>",
        "<truth:originalUrl>https://www.trumpstruth.org/statuses/1</truth:originalUrl>",
    ],
)
def test_trumpstruth_item_without_its_id_fails(offline_settings: Settings, fields: str) -> None:
    with pytest.raises(FeedFailed, match="originalId"):
        parse_feed(rss_item(fields), offline_settings)


def test_trumpstruth_checks_an_id_taken_from_its_link(offline_settings: Settings) -> None:
    link = f"https://truthsocial.com/@realDonaldTrump/{'9' * 20}"  # past a bigint
    with pytest.raises(FeedFailed, match="not a Truth Social status id"):
        parse_feed(rss_item(f"<truth:originalUrl>{link}</truth:originalUrl>"), offline_settings)


def test_trumpstruth_skips_one_odd_item_and_keeps_the_rest(offline_settings: Settings) -> None:
    body = fixture_bytes("trumpstruth_feed.xml").replace(
        b"</channel>",
        b"<item><guid>notice</guid><description>site notice</description></item></channel>",
    )
    assert len(parse_feed(body, offline_settings)) == 8


async def test_trumpstruth_busts_cloudflare_cache(web: FakeWeb, offline_settings: Settings) -> None:
    async with web.client(offline_settings) as client:
        await TrumpstruthFeed(client, offline_settings).read()
    (request,) = web.requests
    assert request.url.host == TRUMPSTRUTH_HOST
    assert request.url.path == "/feed" and request.url.params["t"].isdigit()


def test_every_feed_names_itself() -> None:
    assert tuple(feed.name for feed in FEEDS) == FEED_NAMES
    feeds: list[type[Feed]] = [DirectFeed, TrumpstruthFeed, CnnFeed, ScrapeCreatorsFeed]
    assert set(feeds) == set(FEEDS)


def test_the_engine_runs_the_feeds() -> None:
    assert "feeds" in build_registry().workers


def test_off_switch_and_key_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", "postgresql://unused/unused")
    monkeypatch.setenv("ENGINE_SOURCES_OFF", " direct, scrapecreators ,")
    monkeypatch.setenv("ENGINE_SCRAPECREATORS_KEY", "")
    settings = Settings()
    assert settings.sources_off == {"direct", "scrapecreators"}
    assert settings.scrapecreators_key is None

    monkeypatch.setenv("ENGINE_SOURCES_OFF", "cnn,dirct")
    with pytest.raises(ValueError, match=r"unknown feeds \['dirct'\]"):
        Settings()


async def test_redirects_are_failures(web: FakeWeb, offline_settings: Settings) -> None:
    web.routes[SCRAPECREATORS_HOST] = lambda request: httpx.Response(
        302, headers={"location": "https://elsewhere.example/login"}
    )
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedFailed, match="HTTP 302"):
            await ScrapeCreatorsFeed(client, offline_settings).read()
    assert [r.url.host for r in web.requests] == [SCRAPECREATORS_HOST]
