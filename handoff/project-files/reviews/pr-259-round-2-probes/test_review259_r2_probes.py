"""Round-2 review probes for PR #259 at 0974fe2. A passing probe means the suspected bug is
real. Not finished tests: prints, minimal cleanup. Do not commit."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.cnn import CnnFeed, cnn_post
from engine.feeds.live import Live
from engine.feeds.store import insert_signals, trump_source_id
from engine.registry import EngineContext
from engine.settings import Settings
from engine.tables import feed_status, signals
from tests.conftest import operator_notices
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    TRUMPSTRUTH_HOST,
    FakeWeb,
    feed_settings,
    json_response,
    status,
    status_id_at,
)

MakeLive = Callable[..., Live]
ONLY_CNN = frozenset({"direct", "trumpstruth", "scrapecreators"})
MIRRORS = frozenset({"direct", "scrapecreators"})


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
async def make_live(migrated: Settings, db: AsyncEngine, web: FakeWeb) -> AsyncIterator[MakeLive]:
    clients: list[httpx.AsyncClient] = []

    def make(**overrides: object) -> Live:
        settings = feed_settings(migrated, **overrides)
        client = web.client(settings)
        clients.append(client)
        return Live(EngineContext(settings, db), client)

    yield make
    for client in clients:
        await client.aclose()


def day(d: int) -> str:
    return status_id_at(datetime(2026, 9, d, 12, tzinfo=UTC))


def cnn_item(status_id: str) -> dict[str, Any]:
    return {"id": status_id, "content": f"post {status_id}", "media": []}


def cnn_head(status_ids: list[str]) -> bytes:
    items = ",".join(f'{{"id": "{i}", "content": "post {i}"}}' for i in status_ids)
    return f'[{items}, {{"id": "1", "conte'.encode()


def status_json(status_id: str) -> dict[str, Any]:
    return {"id": status_id, "content": f"<p>post {status_id}</p>", "account": {"id": "107780257626128497"}}


def rss(status_ids: list[str]) -> Callable[[httpx.Request], httpx.Response]:
    items = "".join(
        f"<item><guid>{i}</guid><description>post {i}</description>"
        f"<truth:originalId>{i}</truth:originalId></item>"
        for i in status_ids
    )
    body = f'<rss xmlns:truth="https://truthsocial.com/ns"><channel>{items}</channel></rss>'
    return lambda request: httpx.Response(
        200, content=body.encode(), headers={"content-type": "application/rss+xml"}
    )


async def store_imported(db: AsyncEngine, *status_ids: str) -> None:
    async with db.begin() as conn:
        posts = [cnn_post(cnn_item(i)) for i in status_ids]
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)


async def stored_ids(db: AsyncEngine) -> set[str]:
    async with db.connect() as conn:
        return {k.split(":")[1] for k in (await conn.execute(select(signals.c.key))).scalars()}


GAP_START = day(1)
GAP = [day(5), day(8), day(10)]
HEAD = [day(d) for d in (28, 27, 26)]


# --- R1: a block during catch-up drops the read's posts and is retried at once forever ----


async def test_r1_cnn_download_blocked_head_never_stored(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []

    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return httpx.Response(
                206, content=cnn_head(HEAD), headers={"content-type": "application/json"}
            )
        downloads.append(request)
        return httpx.Response(429)  # the full file is rate-limited; the range read is fine

    web.routes[CNN_HOST] = route
    live = make_live(sources_off=ONLY_CNN)
    await live.start()
    cnn = live.pollers["cnn"]
    for _ in range(4):
        cnn.last_poll = None  # each back-off over
        await cnn.poll()
    stored = await stored_ids(db)
    print(
        "state", cnn.state, "downloads", len(downloads), "catch_up_after", cnn.catch_up_after,
        "head stored", [h in stored for h in HEAD],
    )
    assert cnn.state == "blocked"
    assert len(downloads) == 4  # no catch-up back-off: every try downloads again
    assert not any(h in stored for h in HEAD)  # the head posts CNN read are never stored


async def test_r1_control_download_503_keeps_head(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)

    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return httpx.Response(
                206, content=cnn_head(HEAD), headers={"content-type": "application/json"}
            )
        return httpx.Response(503)

    web.routes[CNN_HOST] = route
    live = make_live(sources_off=ONLY_CNN)
    await live.start()
    await live.pollers["cnn"].poll()
    assert set(HEAD) <= await stored_ids(db)
    assert live.pollers["cnn"].state == "up"


async def test_r1b_direct_page_back_429_keeps_direct_blocked_and_scrapecreators_paid(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """After a long direct outage, its catch-up pages back; Truth Social answers a page with
    429. direct's own new posts are dropped, it stays blocked for good (each retry pages back
    again), and ScrapeCreators polls every 2 minutes all that time."""
    await store_imported(db, GAP_START)
    page_one = [status_json(i) for i in HEAD]
    requests = {"page1": 0, "back": 0}

    def direct(request: httpx.Request) -> httpx.Response:
        if "max_id" in request.url.params:
            requests["back"] += 1
            return httpx.Response(429)
        requests["page1"] += 1
        return json_response(page_one)

    web.routes[DIRECT_HOST] = direct
    live = make_live(
        sources_off=frozenset({"trumpstruth", "cnn"}),
        scrapecreators_key=SecretStr("k"),
        scrapecreators_fallback_seconds=120.0,
    )
    await live.start()
    d = live.pollers["direct"]
    for _ in range(4):
        d.last_poll = None
        await d.poll()
    stored = await stored_ids(db)
    print(
        "direct state", d.state, "requests", requests, "sc interval", live.interval("scrapecreators"),
        "head stored", [h in stored for h in HEAD],
        "blocked notices", len(operator_notices(caplog, "feed_blocked")),
    )
    assert d.state == "blocked"
    assert requests == {"page1": 4, "back": 4}
    assert not any(h in stored for h in HEAD)
    assert live.interval("scrapecreators") == 120


# --- R2: while a catch-up waits, each poll wipes its "catch-up failed" error -------------


async def test_r2_waiting_poll_clears_catch_up_error(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)

    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return httpx.Response(
                206, content=cnn_head(HEAD), headers={"content-type": "application/json"}
            )
        return httpx.Response(503)

    web.routes[CNN_HOST] = route
    live = make_live(sources_off=ONLY_CNN)
    await live.start()
    cnn = live.pollers["cnn"]
    await cnn.poll()

    async def last_error() -> Any:
        async with db.connect() as conn:
            return (
                await conn.execute(
                    select(feed_status.c.last_error).where(feed_status.c.feed == "cnn")
                )
            ).scalar_one()

    first = await last_error()
    await cnn.poll()  # within the catch-up's wait
    second = await last_error()
    print("after failed catch-up:", first, "| next poll while waiting:", second)
    assert first.startswith("catch-up failed")
    assert second is None


# --- R3: a feed switched back on starts at the newest post, so a gap nobody filled stays --


async def test_r3_feed_switched_on_after_gap_skips_it(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    window = [day(d) for d in (28, 27, 26, 25, 24)]
    web.routes[TRUMPSTRUTH_HOST] = rss(window)

    def cnn(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return httpx.Response(
                206, content=cnn_head(HEAD), headers={"content-type": "application/json"}
            )
        downloads.append(request)
        return json_response([cnn_item(i) for i in [*window, *GAP, GAP_START]])

    web.routes[CNN_HOST] = cnn
    first = make_live(sources_off=frozenset({"direct", "scrapecreators", "cnn"}))
    await first.start()
    await first.pollers["trumpstruth"].poll()  # can't read back: "other feeds may fill it"
    second = make_live(sources_off=MIRRORS)  # CNN switched back on
    await second.start()
    await second.pollers["cnn"].poll()
    stored = await stored_ids(db)
    print("downloads", len(downloads), "gap stored", [g in stored for g in GAP])
    assert downloads == [] and not any(g in stored for g in GAP)


# --- R4: map_items logs the same skipped item again whenever the item count changes -------


async def test_r4_skip_warning_repeats_when_head_grows(
    web: FakeWeb, migrated: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    bodies = [
        '[{"id": "x"}, {"id": "%s", "content": "a"}, {"id": "1", "co' % day(20),
        '[{"id": "%s", "content": "b"}, {"id": "x"}, {"id": "%s", "content": "a"}, {"id": "1", "co'
        % (day(21), day(20)),
        '[{"id": "%s", "content": "c"}, {"id": "%s", "content": "b"}, {"id": "x"}, {"id": "%s", "content": "a"}, {"id": "1", "co'
        % (day(22), day(21), day(20)),
    ]
    caplog.set_level(logging.WARNING)
    async with web.client(migrated) as client:
        feed = CnnFeed(client, migrated)
        for body in bodies:
            web.routes[CNN_HOST] = lambda request, body=body: httpx.Response(
                206, content=body.encode(), headers={"content-type": "application/json"}
            )
            await feed.read()
    warnings = [r.getMessage() for r in caplog.records if "items that don't map" in r.getMessage()]
    print(len(warnings), warnings)
    assert len(warnings) == 3  # the same odd item, logged on every new post


# --- R5: reading exactly 32 KB stops before the end of the 206, so the connection is not reused


async def test_r5_range_read_does_not_reuse_connection(migrated: Settings) -> None:
    body = cnn_head(HEAD).ljust(32 * 1024, b" ")[: 32 * 1024]
    connections = 0

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                if not head:
                    break
                writer.write(
                    b"HTTP/1.1 206 Partial Content\r\ncontent-type: application/json\r\n"
                    + f"content-length: {len(body)}\r\ncontent-range: bytes 0-{len(body) - 1}/20000000\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    from engine.feeds import cnn as cnn_module

    url = f"http://127.0.0.1:{port}/data/truth-social/truth_archive.json"
    old = cnn_module.URL
    cnn_module.URL = url
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            feed = CnnFeed(client, migrated)
            for _ in range(5):
                read = await feed.read()
                assert len(read.posts) == 3
    finally:
        cnn_module.URL = old
        server.close()
        await server.wait_closed()
    print("TCP connections for 5 range reads:", connections)
    assert connections == 5


async def test_r5_control_reading_to_the_end_reuses_it(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.feeds import base as base_module

    async def read_body(response: httpx.Response, limit: int | None) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body += chunk
            if limit is not None and len(body) > limit:  # stop only past the range
                break
        return bytes(body[:limit] if limit else body)

    monkeypatch.setattr(base_module, "_read_body", read_body)
    body = cnn_head(HEAD).ljust(32 * 1024, b" ")[: 32 * 1024]
    connections = 0

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        try:
            while True:
                await reader.readuntil(b"\r\n\r\n")
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

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    from engine.feeds import cnn as cnn_module

    monkeypatch.setattr(cnn_module, "URL", f"http://127.0.0.1:{port}/a.json")
    async with httpx.AsyncClient(trust_env=False) as client:
        feed = CnnFeed(client, migrated)
        for _ in range(5):
            assert len((await feed.read()).posts) == 3
    server.close()
    await server.wait_closed()
    print("control: TCP connections for 5 range reads:", connections)
    assert connections == 1


async def test_control_restored_block_still_blocked_one_notice(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    web.routes[DIRECT_HOST] = status(403)
    only = frozenset({"trumpstruth", "cnn", "scrapecreators"})
    first = make_live(sources_off=only)
    await first.start()
    for _ in range(3):
        await first.pollers["direct"].poll()
    since = first.pollers["direct"].blocked_since
    second = make_live(sources_off=only)
    await second.start()
    d = second.pollers["direct"]
    d.last_poll = None
    await d.poll()  # still blocked after the handover
    async with db.connect() as conn:
        row = (await conn.execute(select(feed_status).where(feed_status.c.feed == "direct"))).one()
    print("notices", len(operator_notices(caplog, "feed_blocked")), "backoff", d.backoff, row.backoff_seconds, row.blocked_since == since)
    assert len(operator_notices(caplog, "feed_blocked")) == 1
    assert d.backoff == 480 and row.blocked_since == since
