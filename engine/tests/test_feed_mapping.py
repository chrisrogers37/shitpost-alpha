"""Each feed maps its fixtures; what counts as blocked. No database, no network."""

from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest

from engine.feeds.base import Feed, FeedBlocked, FeedFailed
from engine.feeds.cnn import CnnFeed, download_archive, leading_items
from engine.feeds.mastodon import DirectFeed, ScrapeCreatorsFeed
from engine.feeds.posts import Post
from engine.feeds.trumpstruth import TrumpstruthFeed, parse_feed
from engine.settings import Settings
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    FakeWeb,
    Route,
    challenge,
    fixture_bytes,
    fixture_json,
    json_response,
    status,
)

KEY_STATUS = "107780257626128497"


@pytest.fixture
def offline_settings() -> Settings:
    return Settings(database_url="postgresql://unused/unused", scrapecreators_key="test-key")


@pytest.fixture
async def web() -> AsyncIterator[FakeWeb]:
    yield FakeWeb()


def by_id(posts: list[Post]) -> dict[str, Post]:
    return {post.status_id: post for post in posts}


async def test_direct_maps_post_reply_quote_repost_and_media_only(
    web: FakeWeb, offline_settings: Settings
) -> None:
    async with web.client(offline_settings) as client:
        read = await DirectFeed(client, offline_settings).read()
    posts = by_id(read.posts)
    expected = {  # status id: (kind, points_to, has_media, not_scored)
        "117371353802794328": ("post", None, False, None),
        "117369900687288624": ("repost", "117367780569149238", False, "repost"),
        "117369458827039533": ("reply", "117369363664701946", False, None),
        "117368266436035432": ("post", None, True, "no_text"),
        "117307289681145880": ("quote", "117304284426928910", False, None),
    }
    assert {
        i: (p.kind, p.points_to, p.has_media, p.not_scored) for i, p in posts.items()
    } == expected

    reply = posts["117369458827039533"]
    assert reply.key == "truth_social:117369458827039533"
    assert reply.url == "https://truthsocial.com/@realDonaldTrump/117369458827039533"
    assert reply.text == (
        "America does not belong to those who hate it.\n\n"
        "America belongs to those who love it! President DONALD J. TRUMP"
    )
    assert posts["117307289681145880"].text == "Read this!"
    for post in read.posts:  # the id's time matches the status's created_at
        assert post.posted_at.isoformat().startswith(post.raw["created_at"][:19])

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


@pytest.mark.parametrize(
    ("route", "reason"),
    [
        (status(403), "HTTP 403"),
        (status(429), "HTTP 429"),
        (challenge, "HTTP 403"),
        (
            lambda request: httpx.Response(
                200, text="<html>Just a moment...</html>", headers={"content-type": "text/html"}
            ),
            "challenge page",
        ),
        (
            lambda request: json_response([], headers={"cf-mitigated": "challenge"}),
            "cf-mitigated",
        ),
    ],
)
async def test_direct_block_signals(
    web: FakeWeb, offline_settings: Settings, route: Route, reason: str
) -> None:
    web.routes[DIRECT_HOST] = route
    async with web.client(offline_settings) as client:
        with pytest.raises(FeedBlocked, match=reason):
            await DirectFeed(client, offline_settings).read()


async def test_other_errors_are_failures_not_blocks(
    web: FakeWeb, offline_settings: Settings
) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    routes = [status(500), broken, lambda request: json_response({"error": "x"})]
    for route in routes:
        web.routes[DIRECT_HOST] = route
        async with web.client(offline_settings) as client:
            with pytest.raises(FeedFailed):
                await DirectFeed(client, offline_settings).read()


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
        assert len((await feed.read()).posts) == 5
        second = await feed.read()
    assert second.not_modified and second.posts == []


async def test_scrapecreators_maps_its_wrapper_and_treats_a_bad_key_as_blocked(
    web: FakeWeb, offline_settings: Settings
) -> None:
    async with web.client(offline_settings) as client:
        feed = ScrapeCreatorsFeed(client, offline_settings)
        read = await feed.read()
        assert [p.kind for p in read.posts] == ["post", "repost", "reply"]
        (request,) = web.requests
        assert request.headers["x-api-key"] == "test-key"
        assert request.url.params["user_id"] == KEY_STATUS

        web.routes[SCRAPECREATORS_HOST] = status(401)
        with pytest.raises(FeedBlocked, match="HTTP 401"):
            await feed.read()
        web.routes[SCRAPECREATORS_HOST] = lambda request: json_response({"success": False})
        with pytest.raises(FeedFailed, match="success=False"):
            await feed.read()


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


async def test_cnn_304_and_full_download_retry(web: FakeWeb, offline_settings: Settings) -> None:
    attempts = []

    def flaky(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return httpx.Response(304)
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("peer closed connection: incomplete chunked read")
        return json_response(fixture_json("archive_cnn_slice.json"))

    web.routes[CNN_HOST] = flaky
    async with web.client(offline_settings) as client:
        feed = CnnFeed(client, offline_settings)
        assert (await feed.read()).not_modified
        items = await download_archive(client, offline_settings)
    assert len(items) == 6 and len(attempts) == 2
    assert attempts[-1].headers["accept-encoding"] == "gzip"


def test_trumpstruth_maps_items_and_takes_the_id_from_original_id() -> None:
    posts = by_id(parse_feed(fixture_bytes("trumpstruth_feed.xml")))
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


async def test_trumpstruth_busts_cloudflare_cache(web: FakeWeb, offline_settings: Settings) -> None:
    async with web.client(offline_settings) as client:
        await TrumpstruthFeed(client, offline_settings).read()
    (request,) = web.requests
    assert request.url.path == "/feed" and request.url.params["t"].isdigit()


def test_trumpstruth_item_without_original_id_fails() -> None:
    body = b"<rss><channel><item><guid>x</guid><description>y</description></item></channel></rss>"
    with pytest.raises(FeedFailed, match="originalId"):
        parse_feed(body)


def test_every_feed_names_itself() -> None:
    feeds: list[type[Feed]] = [DirectFeed, TrumpstruthFeed, CnnFeed, ScrapeCreatorsFeed]
    assert [f.name for f in feeds] == ["direct", "trumpstruth", "cnn", "scrapecreators"]


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
