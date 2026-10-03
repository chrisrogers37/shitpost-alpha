"""Round-4 review probes for PR #259 at 558d50c. `test_r4bug_...` pass when the suspected
problem is real; `test_r4check_...` record behaviour (pass = as described in the probe).
Not finished tests: prints, minimal cleanup. Do not commit."""

import asyncio
import json
import traceback
from datetime import UTC, datetime
from typing import Any, NoReturn

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import DataError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine import cli
from engine.feeds import history
from engine.feeds import live as live_module
from engine.feeds import mastodon
from engine.feeds.base import FeedFailed
from engine.feeds.cnn import CnnFeed
from engine.feeds.history import run_import
from engine.feeds.mastodon import ScrapeCreatorsFeed
from engine.feeds.posts import status_time
from engine.feeds.status import status_lines
from engine.feeds.store import store_posts as real_store_posts
from engine.http_client import make_client
from engine.settings import Settings
from engine.tables import feed_status, signals, source_stats
from tests.feeds_helpers import CNN_HOST, TRUMPSTRUTH_HOST, FakeWeb, feed_settings, fixture_json
from tests.test_live import (  # noqa: F401  (fixtures)
    GAP,
    GAP_START,
    HEAD,
    ONLY_CNN,
    WINDOW,
    MakeLive,
    cnn_after_outage,
    cnn_head,
    cnn_item,
    day,
    make_live,
    one,
    run_for,
    started,
    store_imported,
    stored_ids,
    web,
)

ONLY_TRUMPSTRUTH = frozenset({"direct", "cnn", "scrapecreators"})


async def cnn_status_line(db: AsyncEngine) -> str:
    async with db.connect() as conn:
        (line,) = [line for line in await status_lines(conn) if line.startswith("feed cnn")]
    return line


# --- S1 follow-up: a lone surrogate is as unstorable as a NUL ---------------------------------


async def test_r4bug_lone_surrogate_wedges_cnn_like_a_nul_did(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    """json.loads accepts "\\ud800"; psycopg can't encode it (text) and jsonb refuses it.
    Every store of CNN's head fails while the post is in it; nothing else is stored."""
    items = ",".join(f'{{"id": "{i}", "content": "post {i}"}}' for i in HEAD)
    body = f'[{{"id": "{day(29)}", "content": "cut emoji \\ud83d"}}, {items}, {{"id": "1'.encode()
    web.routes[CNN_HOST] = lambda request: httpx.Response(
        206, content=body, headers={"content-type": "application/json"}
    )
    live = make_live(sources_off=ONLY_CNN)
    await run_for(live, 0.4)
    count = (await one(db, select(func.count()).select_from(signals)))[0]
    row = await one(db, select(source_stats).where(source_stats.c.feed == "cnn"))
    line = await cnn_status_line(db)
    print("signals:", count, "| polls/errors:", row.polls, row.errors, "|", line)
    assert count == 0 and row.errors >= 2 and live.pollers["cnn"].state == "up"
    assert "surrogate" in line or "Unicode" in line


# --- New: after a read back whose store failed, status shows no reason while it waits --------


async def test_r4bug_status_shows_no_reason_while_a_read_back_waits_for_its_store(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_after_outage(downloads)
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    gap_keys = {f"truth_social:{i}" for i in GAP}

    async def refuses_the_gap(conn: Any, source_id: int, feed: str, posts: Any) -> Any:
        if gap_keys & {post.key for post in posts}:  # a post in the gap the database refuses
            raise DataError("INSERT", {}, Exception("a value the database refuses"))
        return await real_store_posts(conn, source_id, feed, posts)

    monkeypatch.setattr(live_module, "store_posts", refuses_the_gap)
    lines = []
    for _ in range(3):
        try:
            await cnn.poll()
        except DataError as exc:
            await live._record_failure(cnn, exc)  # what _run_feed does
        lines.append(await cnn_status_line(db))
    print("downloads:", len(downloads), "| mark:", cnn.caught_up_to, "| error:", cnn.catch_up_error)
    print("\n".join(lines))
    assert len(downloads) == 1 and cnn.caught_up_to is not None
    assert cnn.caught_up_to < status_time(GAP[0])  # the gap is still owed
    assert "DataError" in lines[0]
    assert lines[1].startswith("feed cnn: up; last good read")  # no reason shown while owed
    assert set(GAP).isdisjoint(await stored_ids(db))


# --- E7 follow-ups -----------------------------------------------------------------------------


def rss_items(items: list[str]) -> Any:
    body = f'<rss xmlns:truth="https://truthsocial.com/ns"><channel>{"".join(items)}</channel></rss>'
    return lambda request: httpx.Response(
        200, content=body.encode(), headers={"content-type": "application/rss+xml"}
    )


async def test_r4bug_trumpstruth_original_url_past_a_bigint_fails_every_poll(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    """item_status_id's originalUrl fallback returns the regex match without
    parse_status_id's range check, so status_time overflows outside map_items."""
    good = "".join(
        f"<item><guid>{i}</guid><description>post {i}</description>"
        f"<truth:originalId>{i}</truth:originalId></item>"
        for i in HEAD
    )
    odd = (
        "<item><guid>odd</guid><description>odd</description><truth:originalUrl>"
        f"https://truthsocial.com/@realDonaldTrump/{'9' * 20}</truth:originalUrl></item>"
    )
    web.routes[TRUMPSTRUTH_HOST] = rss_items([odd, good])
    live = await started(make_live(sources_off=ONLY_TRUMPSTRUTH))
    ts = live.pollers["trumpstruth"]
    for _ in range(5):
        await ts.poll()
    row = await one(db, select(feed_status).where(feed_status.c.feed == "trumpstruth"))
    print(ts.state, "|", row.last_error, "| stored:", len(await stored_ids(db)))
    assert ts.state == "blocked" and "OverflowError" in row.last_error
    assert await stored_ids(db) == set()


@pytest.mark.parametrize("odd_id", ["9000000000000000000", "917371353802794328"])
async def test_r4bug_a_far_future_id_moves_the_mark_and_hides_the_next_gap(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, odd_id: str
) -> None:
    """An id under 2**63 passes parse_status_id; its time is centuries ahead, and the
    feed's mark goes there, so no later read is ever behind the mark."""
    first = cnn_head([odd_id, day(5)])
    downloads: list[httpx.Request] = []
    after_outage = cnn_after_outage(downloads)
    serve = {"head": first}

    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers and serve["head"] is not None:
            return httpx.Response(
                206, content=serve["head"], headers={"content-type": "application/json"}
            )
        return after_outage(request)

    web.routes[CNN_HOST] = route
    cnn = (await started(make_live(sources_off=ONLY_CNN))).pollers["cnn"]
    await cnn.poll()
    print("odd id time:", status_time(odd_id), "| mark after poll 1:", cnn.caught_up_to)
    serve["head"] = None  # an outage later: CNN's head is days 28..26, the gap 6..25 unread
    await cnn.poll()
    await cnn.poll()
    print("downloads:", len(downloads), "| gap stored:", set(GAP) <= await stored_ids(db))
    assert cnn.caught_up_to is not None and cnn.caught_up_to.year > 2400
    assert len(downloads) == 0 and {day(8), day(10)}.isdisjoint(await stored_ids(db))


async def test_r4control_without_the_odd_id_the_gap_is_caught_up(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    downloads: list[httpx.Request] = []
    after_outage = cnn_after_outage(downloads)
    serve: dict[str, bytes | None] = {"head": cnn_head([day(5)])}

    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers and serve["head"] is not None:
            return httpx.Response(
                206, content=serve["head"], headers={"content-type": "application/json"}
            )
        return after_outage(request)

    web.routes[CNN_HOST] = route
    cnn = (await started(make_live(sources_off=ONLY_CNN))).pollers["cnn"]
    await cnn.poll()
    serve["head"] = None
    await cnn.poll()
    assert len(downloads) == 1 and {day(8), day(10)} <= await stored_ids(db)


async def test_r4check_import_aborts_on_an_id_past_a_bigint(
    migrated: Settings, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E7's import half: settled() still raises on such an item (now ValueError, not
    OverflowError), so nothing is imported, like any other malformed item."""

    async def fake_download(client: object, settings: Settings) -> list[Any]:
        result: list[Any] = fixture_json("archive_cnn_slice.json")
        return result

    monkeypatch.setattr(
        history,
        "clone_cc0",
        lambda into: ([{"id": "9" * 20, "content": "x"}, *fixture_json("archive_cc0_slice.json")], "abc"),
    )
    monkeypatch.setattr(history, "download_archive", fake_download)
    with pytest.raises(ValueError, match="not a Truth Social status id") as caught:
        await run_import(migrated, print)
    print(repr(caught.value))
    assert await stored_ids(db) == set()


# --- E4 follow-up: an unmigrated database --------------------------------------------------------


async def test_r4check_import_history_on_an_unmigrated_database(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clones: list[Any] = []

    def no_clone(into: Any) -> NoReturn:
        clones.append(into)
        raise AssertionError("cloned")

    monkeypatch.setattr(history, "clone_cc0", no_clone)
    monkeypatch.setenv("ENGINE_DATABASE_URL", settings.db_url)
    with pytest.raises(ProgrammingError) as caught:
        await asyncio.to_thread(cli.main, ["import-history"])
    print("raised:", type(caught.value).__name__, str(caught.value).splitlines()[0])
    assert clones == []  # stops before downloading, but with a traceback, not one line
    monkeypatch.setenv("ENGINE_DATABASE_URL", settings.db_url)
    assert await asyncio.to_thread(cli.main, ["status"]) == 1  # status: one line
    print("status:", capsys.readouterr().out.strip())


# --- B1 follow-ups -----------------------------------------------------------------------------


def test_r4check_validation_error_text_carries_a_refused_key() -> None:
    key = "sc key 0123-probe"
    with pytest.raises(ValidationError) as caught:
        Settings(database_url="postgresql://x", scrapecreators_key=key)
    print("str has key:", key in str(caught.value), "| repr has key:", key in repr(caught.value))
    print(str(caught.value))
    assert key in str(caught.value)  # only cli.py's loc+msg printing keeps it out


def test_r4check_cli_never_prints_a_refused_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENGINE_DATABASE_URL", "postgresql://probe@127.0.0.1:1/probe")
    for key in ("sc key 0123-probe", "sc-kéy-0123-probe", "sc-key-0123-probe\x01"):
        monkeypatch.setenv("ENGINE_SCRAPECREATORS_KEY", key)
        assert cli.main(["status"]) == 2
        err = capsys.readouterr().err
        print(repr(err))
        assert "0123-probe" not in err


async def test_r4check_scrubbed_failure_keeps_the_original_on_context_only(
    offline_settings: Settings,
) -> None:
    """`from None` hides the httpx error from tracebacks, but it stays on __context__,
    with the key in its text and in its request's headers."""
    key = "probe-fake-sc-key-0123456789"
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        async with make_client(offline_settings, httpx.AsyncHTTPTransport()) as client:
            feed = ScrapeCreatorsFeed(client, offline_settings)
            with pytest.raises(FeedFailed) as caught:
                await feed.get(f"http://127.0.0.1:{port}/", headers={"x-api-key": key + "\n"})
    finally:
        server.close()
        await server.wait_closed()
    exc = caught.value
    printed = "".join(traceback.format_exception(exc))
    context = exc.__context__
    print("traceback has key:", key in printed, "| suppress:", exc.__suppress_context__)
    print("context:", type(context).__name__, "| context text has key:", key in str(context))
    assert key not in str(exc) and key not in printed
    assert context is not None and key in str(context)


async def test_r4check_a_non_ascii_key_past_settings_escapes_the_scrub(
    offline_settings: Settings,
) -> None:
    """Settings refuse it, so only a key that bypasses validation gets here: httpx raises
    UnicodeEncodeError (not an httpx error) building the header, and its repr holds it."""
    settings = offline_settings.model_copy(update={"scrapecreators_key": SecretStr("sc-kéy-0123")})
    async with make_client(settings, httpx.AsyncHTTPTransport()) as client:
        feed = ScrapeCreatorsFeed(client, settings)
        with pytest.raises(UnicodeEncodeError) as caught:
            await feed.page(None)
    print(repr(caught.value))
    assert "sc-kéy-0123" in repr(caught.value)


# --- E1 follow-ups: the 75 s keep-alive ---------------------------------------------------------


def test_r4check_keepalive_limits_drop_the_default_connection_caps(
    offline_settings: Settings,
) -> None:
    client = make_client(offline_settings)
    pool = client._transport._pool  # type: ignore[attr-defined]
    default = httpx.AsyncClient()._transport._pool  # type: ignore[attr-defined]
    print("make_client:", pool._max_connections, pool._max_keepalive_connections, pool._keepalive_expiry)
    print("httpx default:", default._max_connections, default._max_keepalive_connections, default._keepalive_expiry)
    assert pool._keepalive_expiry == 75 and pool._max_connections > 10**9  # None -> sys.maxsize
    assert pool._max_keepalive_connections > 10**9 and default._max_connections == 100


async def test_r4check_production_client_reuses_across_a_gap_and_survives_a_server_close(
    offline_settings: Settings,
) -> None:
    """make_client without a transport (as feeds_worker does): a 304 and 206s 6 s apart
    use one connection; a connection the server closed while idle is replaced quietly."""
    body = b"[" + b" " * (32 * 1024 - 1)
    connections = 0
    close_idle_after: list[float] = []

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal connections
        connections += 1
        try:
            while True:
                wait = close_idle_after[0] if close_idle_after else None
                head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), wait)
                if b"if-none-match" in head.lower():
                    writer.write(b'HTTP/1.1 304 Not Modified\r\netag: "v1"\r\n\r\n')
                else:
                    writer.write(
                        b"HTTP/1.1 206 Partial Content\r\ncontent-type: application/json\r\n"
                        + f"content-length: {len(body)}\r\n\r\n".encode()
                        + body
                    )
                await writer.drain()
        except (TimeoutError, asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/truth_archive.json"
    try:
        async with make_client(offline_settings) as client:
            feed = CnnFeed(client, offline_settings)
            for etag in (None, '"v1"', None):
                feed.etag = etag
                await feed.get(url, conditional=True, range_bytes=32 * 1024)
                await asyncio.sleep(6)
            reused = connections
            close_idle_after.append(1.0)  # the server now drops a connection idle for 1 s
            feed.etag = None
            await feed.get(url, conditional=True, range_bytes=32 * 1024)
            await asyncio.sleep(2.5)
            await feed.get(url, conditional=True, range_bytes=32 * 1024)
    finally:
        server.close()
        await server.wait_closed()
    print("connections for 3 polls 6 s apart:", reused, "| after a server-side idle close:", connections)
    assert reused == 1 and connections == 2  # the 4th poll reused it; the 5th opened one


@pytest.fixture
def offline_settings() -> Settings:
    return feed_settings(Settings(database_url="postgresql://probe@127.0.0.1:1/probe"))


_ = (json, mastodon, datetime, UTC, WINDOW, cnn_item)


# --- S1: _record_failure keeps a block, and stops on a converted cancel ------------------------


async def test_r4check_record_failure_keeps_a_block(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.feeds_helpers import status as http_status

    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    web.routes[CNN_HOST] = http_status(429)
    await cnn.poll()
    assert cnn.state == "blocked"
    before = await one(db, select(feed_status).where(feed_status.c.feed == "cnn"))
    web.routes[CNN_HOST] = lambda request: httpx.Response(
        206, content=cnn_head(HEAD), headers={"content-type": "application/json"}
    )

    async def rejected(*args: Any, **kwargs: Any) -> NoReturn:
        raise DataError("INSERT", {}, Exception("a value the database refuses"))

    monkeypatch.setattr(live_module, "store_posts", rejected)
    try:
        await cnn.poll()
    except DataError as exc:
        await live._record_failure(cnn, exc)
    after = await one(db, select(feed_status).where(feed_status.c.feed == "cnn"))
    line = await cnn_status_line(db)
    print("before:", before.state, before.blocked_since, before.backoff_seconds, "| after:", after.state,
          after.blocked_since, after.backoff_seconds, "|", line)
    assert (after.state, after.blocked_since, after.backoff_seconds) == (
        "blocked", before.blocked_since, before.backoff_seconds
    )
    assert line.startswith("feed cnn: blocked since") and "DataError" in line


async def test_r4check_record_failure_stops_on_a_converted_cancel(
    make_live: MakeLive, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import helpers

    async def rejected(*args: Any, **kwargs: Any) -> NoReturn:
        raise DataError("INSERT", {}, Exception("a value the database refuses"))

    async def stall(*args: Any, **kwargs: Any) -> NoReturn:
        await helpers.stall_then_fail_on_cancel()

    live = await started(make_live(sources_off=ONLY_CNN))
    monkeypatch.setattr(live_module, "store_posts", rejected)
    monkeypatch.setattr(live_module, "count", stall)  # _record_failure's first write stalls

    async def already_started() -> None:
        return None

    monkeypatch.setattr(live, "start", already_started)
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.3)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and task.cancelled()


async def test_r4check_record_failure_stops_on_a_converted_cancel_then_good_polls(
    make_live: MakeLive, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stricter: the store fails once, then works. A cancel converted inside
    _record_failure's write must stop the feed even though later polls raise nothing."""
    from engine.feeds.store import count as real_count
    from tests import helpers

    calls = {"store": 0, "count": 0}

    async def once(*args: Any, **kwargs: Any) -> Any:
        calls["store"] += 1
        if calls["store"] == 1:
            raise DataError("INSERT", {}, Exception("a value the database refuses"))
        return await real_store_posts(*args, **kwargs)

    async def stall_first(*args: Any, **kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 1:  # _record_failure's write
            await helpers.stall_then_fail_on_cancel()
        return await real_count(*args, **kwargs)

    live = await started(make_live(sources_off=ONLY_CNN))
    monkeypatch.setattr(live_module, "store_posts", once)
    monkeypatch.setattr(live_module, "count", stall_first)

    async def already_started() -> None:
        return None

    monkeypatch.setattr(live, "start", already_started)
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.3)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    print("store calls:", calls["store"], "| count calls:", calls["count"], "| stopped:", bool(done))
    if not done:
        await helpers.cancel_wedged()
    assert done and task.cancelled() and calls["store"] == 1
