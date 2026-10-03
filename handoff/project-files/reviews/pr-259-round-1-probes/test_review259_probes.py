"""Review probes for PR #259 (4cb9f49). A passing probe means the suspected bug is real.

Not finished tests: prints, no cleanup beyond the PR's fixtures. Do not commit.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds import live as live_mod
from engine.feeds.cnn import download_archive
from engine.feeds.base import FeedBlocked
from engine.feeds.live import Live
from engine.feeds.posts import clean_text, html_text
from engine.feeds.store import insert_signals, trump_source_id
from engine.feeds.cnn import cnn_post
from engine.registry import EngineContext
from engine.settings import Settings
from engine.tables import engine_meta, feed_status, signals
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


def day(d: int, month: int = 9) -> str:
    return status_id_at(datetime(2026, month, d, 12, tzinfo=UTC))


def cnn_item(status_id: str, text: str = "words") -> dict[str, Any]:
    return {"id": status_id, "content": f"{text} {status_id}", "media": []}


def rss(status_ids: list[str]) -> bytes:
    items = "".join(
        f"<item><guid>{i}</guid><description><![CDATA[<p>post {i}</p>]]></description>"
        f"<truth:originalId>{i}</truth:originalId></item>"
        for i in status_ids
    )
    return (
        '<?xml version="1.0"?><rss xmlns:truth="https://truthsocial.com/ns"><channel>'
        f"{items}</channel></rss>"
    ).encode()


def rss_route(status_ids: list[str]) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(
        200, content=rss(status_ids), headers={"content-type": "application/xml"}
    )


async def store_old(db: AsyncEngine, status_id: str) -> None:
    async with db.begin() as conn:
        await insert_signals(
            conn, await trump_source_id(conn), "test", [cnn_post(cnn_item(status_id))], imported=True
        )


async def keys(db: AsyncEngine) -> set[str]:
    async with db.connect() as conn:
        return {k.split(":")[1] for k in (await conn.execute(select(signals.c.key))).scalars()}


# --- P1: a shorter-window feed hides the gap from the feed that could fill it -------------


async def test_p1_gap_hidden_when_trumpstruth_stores_first(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    t0 = day(1)  # newest stored before the outage
    await store_old(db, t0)
    gap = [day(5), day(8), day(10)]  # older than trumpstruth's 4-day window
    window = [day(d) for d in (28, 27, 26, 25, 24)]  # trumpstruth's window
    head = [day(d) for d in (28, 27, 26)]  # CNN's 32 KB head
    downloads: list[httpx.Request] = []

    def cnn(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            body = ("[" + ",".join(f'{{"id": "{i}", "content": "c {i}"}}' for i in head)).encode()
            return httpx.Response(206, content=body, headers={"content-type": "application/json"})
        downloads.append(request)
        return json_response([cnn_item(i) for i in [*window, *gap, t0]])

    web.routes[TRUMPSTRUTH_HOST] = rss_route(window)
    web.routes[CNN_HOST] = cnn
    live = make_live(sources_off=frozenset({"direct", "scrapecreators"}))
    await live.start()
    await live.pollers["trumpstruth"].poll()  # answers first (both are due at start)
    await live.pollers["cnn"].poll()
    for _ in range(3):
        live.pollers["cnn"]._last_keys = frozenset()
        await live.pollers["cnn"].poll()
    stored = await keys(db)
    print("downloads:", len(downloads), "gap stored:", [g in stored for g in gap])
    assert downloads == []  # CNN never caught up
    assert not any(g in stored for g in gap)  # and the gap stays forever


async def test_p1_control_cnn_first_fills_gap(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    t0 = day(1)
    await store_old(db, t0)
    gap = [day(5), day(8), day(10)]
    window = [day(d) for d in (28, 27, 26, 25, 24)]
    head = [day(d) for d in (28, 27, 26)]

    def cnn(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            body = ("[" + ",".join(f'{{"id": "{i}", "content": "c {i}"}}' for i in head)).encode()
            return httpx.Response(206, content=body, headers={"content-type": "application/json"})
        return json_response([cnn_item(i) for i in [*window, *gap, t0]])

    web.routes[TRUMPSTRUTH_HOST] = rss_route(window)
    web.routes[CNN_HOST] = cnn
    live = make_live(sources_off=frozenset({"direct", "scrapecreators"}))
    await live.start()
    await live.pollers["cnn"].poll()
    await live.pollers["trumpstruth"].poll()
    stored = await keys(db)
    assert all(g in stored for g in gap)


# --- P2: the ETag is kept although the poll failed, so the next poll is a 304 -------------


def cnn_with_etag(head: list[str], downloads: list[httpx.Request], download: Callable[[], httpx.Response]):
    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            if request.headers.get("if-none-match") == '"v1"':
                return httpx.Response(304)
            body = ("[" + ",".join(f'{{"id": "{i}", "content": "c {i}"}}' for i in head)).encode()
            return httpx.Response(
                206, content=body, headers={"content-type": "application/json", "etag": '"v1"'}
            )
        downloads.append(request)
        return download()

    return route


async def test_p2_failed_catch_up_is_never_retried(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_old(db, day(1))
    head = [day(d) for d in (28, 27, 26)]
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_with_etag(head, downloads, lambda: httpx.Response(503))
    live = make_live(sources_off=frozenset({"direct", "trumpstruth", "scrapecreators"}))
    await live.start()
    cnn = live.pollers["cnn"]
    await cnn.poll()  # head read OK (etag v1), the download fails: poll fails
    assert cnn.failures == 1
    web.routes[CNN_HOST] = cnn_with_etag(head, downloads, lambda: json_response([]))  # CNN fine now
    for _ in range(5):
        await cnn.poll()  # 304 every time: nothing to catch up from
    stored = await keys(db)
    print("state", cnn.state, "downloads", len(downloads), "head stored", [h in stored for h in head])
    assert cnn.state == "up" and cnn.failures == 0
    assert len(downloads) == 1
    assert not any(h in stored for h in head)  # CNN never stores these posts


async def test_p2_failed_store_is_never_retried(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = [day(d) for d in (28, 27, 26)]
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_with_etag(head, downloads, lambda: json_response([]))
    live = make_live(sources_off=frozenset({"direct", "trumpstruth", "scrapecreators"}))
    await live.start()
    real = live_mod.store_posts
    calls = 0

    async def flaky(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError("INSERT", {}, Exception("server closed the connection"))
        return await real(*args, **kwargs)

    monkeypatch.setattr(live_mod, "store_posts", flaky)
    task = asyncio.create_task(live._run_feed(live.pollers["cnn"]))
    await asyncio.sleep(0.5)
    task.cancel()
    stored = await keys(db)
    print("store calls", calls, "head stored", [h in stored for h in head])
    assert calls >= 2  # it did poll again...
    assert not any(h in stored for h in head)  # ...but only got 304s


# --- P3: one odd answer from one feed takes every feed down --------------------------------


async def test_p3_cnn_json_object_kills_all_feeds(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    web.routes[CNN_HOST] = lambda request: json_response({"error": "temporarily unavailable"})
    live = make_live(sources_off=frozenset({"direct", "scrapecreators"}))
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.3)
    assert task.done()
    exc = task.exception()
    print("Live.run ended with:", repr(exc))
    assert isinstance(exc, ExceptionGroup)
    assert any(isinstance(e, AttributeError) for e in exc.exceptions)
    assert web.count(TRUMPSTRUTH_HOST) <= 1  # trumpstruth was cancelled with it


async def test_p3_direct_list_with_null_kills_all_feeds(
    make_live: MakeLive, web: FakeWeb
) -> None:
    web.routes[DIRECT_HOST] = lambda request: json_response([None])
    live = make_live(sources_off=frozenset({"scrapecreators"}))
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.3)
    assert task.done() and isinstance(task.exception(), ExceptionGroup)
    print("Live.run ended with:", repr(task.exception()))


# --- P4: block state is in memory only: a restart or lease handover forgets it ------------


async def test_p4_restart_forgets_block_new_message_and_immediate_poll(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    web.routes[DIRECT_HOST] = status(403)
    only_direct = frozenset({"trumpstruth", "cnn", "scrapecreators"})
    first = make_live(sources_off=only_direct)
    await first.start()
    for _ in range(6):
        await first.pollers["direct"].poll()  # blocked, backing off 30 minutes now
    async with db.connect() as conn:
        since_1 = (
            await conn.execute(select(feed_status.c.blocked_since).where(feed_status.c.feed == "direct"))
        ).scalar_one()
    second = make_live(sources_off=only_direct)  # worker restart or another copy takes over
    await second.start()
    assert second.pollers["direct"].due_in(time.monotonic()) <= 0  # due at once, not in 30 min
    await second.pollers["direct"].poll()
    async with db.connect() as conn:
        since_2 = (
            await conn.execute(select(feed_status.c.blocked_since).where(feed_status.c.feed == "direct"))
        ).scalar_one()
    notices = operator_notices(caplog, "feed_blocked")
    print("requests to direct:", web.count(DIRECT_HOST), "feed_blocked notices:", len(notices))
    print("blocked_since before/after restart:", since_1, since_2)
    assert len(notices) == 2  # same incident, second message
    assert since_2 > since_1  # incident start time lost


# --- P5: a blocked scrapecreators polls more often than a healthy one ---------------------


async def test_p5_blocked_scrapecreators_polls_faster(make_live: MakeLive, web: FakeWeb) -> None:
    web.routes[SCRAPECREATORS_HOST] = status(429)
    live = make_live(
        sources_off=frozenset({"direct"}),
        scrapecreators_key=SecretStr("k"),
        scrapecreators_fallback_seconds=120.0,
    )
    await live.start()
    sc = live.pollers["scrapecreators"]
    await sc.poll()
    assert sc.state == "blocked" and sc.last_poll is not None
    print("healthy interval", live.interval("scrapecreators"), "blocked wait", sc.backoff)
    assert sc.due_in(sc.last_poll + 60) <= 0  # 429 -> retries after 60 s, healthy is 120 s

    healthy = make_live(scrapecreators_key=SecretStr("k"))  # direct healthy: hourly check
    await healthy.start()
    web.routes[SCRAPECREATORS_HOST] = status(401)
    sc2 = healthy.pollers["scrapecreators"]
    await sc2.poll()
    assert sc2.last_poll is not None
    waits = []
    for _ in range(6):
        waits.append(sc2.backoff)
        await sc2.poll()
    print("bad key: waits between calls", waits, "vs healthy", healthy.interval("scrapecreators"))
    assert sum(waits[:5]) < 3600  # 6 paid-API calls in the first hour, vs 1 when healthy


# --- P6: mojibake repair rewrites correct text -----------------------------------------------


def test_p6_mojibake_repair_corrupts_correct_latin1_pairs() -> None:
    print(repr(html_text("<p>CAFÉ&nbsp;OWNERS LOVE TRUMP</p>")))
    assert html_text("<p>CAFÉ&nbsp;OWNERS</p>") == "CAFɠOWNERS"
    print(repr(clean_text("«CAFÉ» says")))
    assert clean_text("«CAFÉ» says") != "«CAFÉ» says"


# --- P7: a 200 (Range ignored) means the whole file each poll, and it can't be stored -------


async def test_p7_cnn_200_full_file(make_live: MakeLive, web: FakeWeb, db: AsyncEngine) -> None:
    n = 36_624
    filler = "Big news for America! " * 20
    items = [cnn_item(status_id_at(datetime(2026, 9, 1, tzinfo=UTC), low=i + 1), filler) for i in range(n)]
    body = httpx.Response(200, json=items).content
    print("body MB", round(len(body) / 1e6, 1))
    served = []

    def cnn(request: httpx.Request) -> httpx.Response:
        served.append(len(body))
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    web.routes[CNN_HOST] = cnn
    live = make_live(sources_off=frozenset({"direct", "trumpstruth", "scrapecreators"}))
    await live.start()
    cnn_poller = live.pollers["cnn"]

    t = time.perf_counter()
    read = await cnn_poller.feed.read()
    print("read+parse+map seconds (event loop blocked):", round(time.perf_counter() - t, 2), len(read.posts))

    task = asyncio.create_task(live._run_feed(cnn_poller))
    await asyncio.sleep(40)
    task.cancel()
    async with db.connect() as conn:
        count = (await conn.execute(select(func.count()).select_from(signals))).scalar_one()
    print("full-file transfers:", len(served), "MB:", round(sum(served) / 1e6), "signals stored:", count)
    assert len(served) >= 2
    assert count == 0


# --- P8: two feeds answering together send two "feeds back" messages ------------------------


async def test_p8_two_feeds_back_messages(
    make_live: MakeLive, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    live = make_live()
    await live.start()
    live.dark_since = datetime(2026, 10, 1, tzinfo=UTC)
    await asyncio.gather(live.answered(), live.answered())
    print("feeds_back notices:", len(operator_notices(caplog, "feeds_back")))
    assert len(operator_notices(caplog, "feeds_back")) == 2


# --- P9: catch-up download ignores block statuses and challenge pages -----------------------


@pytest.mark.parametrize(
    "route",
    [
        status(429),
        lambda request: httpx.Response(
            200, text="<html>Just a moment...</html>", headers={"content-type": "text/html"}
        ),
    ],
)
async def test_p9_download_archive_block_is_a_plain_failure(route: Any) -> None:
    settings = Settings(database_url="postgresql://unused/unused")
    web = FakeWeb()
    web.routes[CNN_HOST] = route
    async with web.client(settings) as client:
        with pytest.raises(Exception) as caught:
            await download_archive(client, settings)
    print(type(caught.value).__name__, caught.value, "requests:", len(web.requests))
    assert not isinstance(caught.value, FeedBlocked)


# --- P10: one bad trumpstruth item blocks the feed and its good items -----------------------


async def test_p10_one_bad_item_blocks_trumpstruth(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    good = day(28)
    body = rss([good]).replace(
        b"</channel>", b"<item><guid>notice</guid><description>site notice</description></item></channel>"
    )
    web.routes[TRUMPSTRUTH_HOST] = lambda request: httpx.Response(
        200, content=body, headers={"content-type": "application/xml"}
    )
    live = make_live(sources_off=frozenset({"direct", "cnn", "scrapecreators"}))
    await live.start()
    for _ in range(5):
        await live.pollers["trumpstruth"].poll()
    print("state:", live.pollers["trumpstruth"].state, operator_notices(caplog, "feed_blocked"))
    assert live.pollers["trumpstruth"].state == "blocked"
    assert good not in await keys(db)


# --- P11: a failed status write on entering a block leaves blocked_since NULL ---------------


async def test_p11_blocked_since_none(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    web.routes[DIRECT_HOST] = status(403)
    live = make_live(sources_off=frozenset({"trumpstruth", "cnn", "scrapecreators"}))
    await live.start()
    real = live_mod.set_feed_status
    calls = 0

    async def flaky(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError("UPDATE", {}, Exception("server closed the connection"))
        return await real(*args, **kwargs)

    monkeypatch.setattr(live_mod, "set_feed_status", flaky)
    direct = live.pollers["direct"]
    with pytest.raises(OperationalError):
        await direct.poll()
    await direct.poll()
    web.routes[DIRECT_HOST] = lambda request: json_response([])
    await direct.poll()
    async with db.connect() as conn:
        row = (await conn.execute(select(feed_status).where(feed_status.c.feed == "direct"))).one()
    print("after 2nd failure blocked_since:", row.blocked_since, operator_notices(caplog, "feed_recovered"))
    assert any("blocked since None" in n for n in operator_notices(caplog, "feed_recovered"))


async def test_engine_meta_dark_since_column_exists(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        assert (await conn.execute(select(engine_meta.c.feeds_dark_since))).scalar_one() is None


# --- P3b: through run_engine: the crash loop also hammers a blocked feed ------------------


async def test_p3b_crash_loop_resets_blocks(
    migrated: Settings, db: AsyncEngine, web: FakeWeb, caplog: pytest.LogCaptureFixture
) -> None:
    from engine.feeds.live import feeds_worker
    from engine.registry import Registry
    from engine.runtime import run_engine

    settings = feed_settings(migrated, sources_off=frozenset({"trumpstruth", "scrapecreators"}))
    web.routes[DIRECT_HOST] = status(403)  # blocked: should wait 1 min before trying again
    calls = {"cnn": 0}

    def cnn(request: httpx.Request) -> httpx.Response:
        calls["cnn"] += 1
        if calls["cnn"] == 1:
            return httpx.Response(200, json={"error": "x"}, headers={"content-type": "application/json"})
        return httpx.Response(304)

    web.routes[CNN_HOST] = cnn
    async def odd_after_first(request: httpx.Request) -> httpx.Response:  # noqa: unused
        raise AssertionError

    registry = Registry()
    registry.register_worker("feeds", feeds_worker(web.transport()))
    stop = asyncio.Event()
    # Every restart: CNN's first answer is odd again (a fresh worker), direct is polled again.
    def cnn_always_odd(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "x"}, headers={"content-type": "application/json"})

    web.routes[CNN_HOST] = cnn_always_odd
    task = asyncio.create_task(run_engine(settings, registry, stop))
    await asyncio.sleep(1.5)
    stop.set()
    await task
    print(
        "worker_failed:", len(operator_notices(caplog, "worker_failed")),
        "feed_blocked:", len(operator_notices(caplog, "feed_blocked")),
        "direct requests:", web.count(DIRECT_HOST),
    )
    assert web.count(DIRECT_HOST) >= 3  # a blocked feed polled on every restart
    assert len(operator_notices(caplog, "feed_blocked")) >= 3


async def test_p7b_store_posts_over_32767_posts_fails(db: AsyncEngine) -> None:
    from engine.feeds.posts import mirror_post
    from engine.feeds.store import store_posts

    base = datetime(2026, 9, 1, tzinfo=UTC)
    posts = [mirror_post(status_id_at(base, low=i + 1), f"t {i}", False, {}) for i in range(33_000)]
    t = time.perf_counter()
    with pytest.raises(Exception) as caught:
        async with db.begin() as conn:
            await store_posts(conn, await trump_source_id(conn), "cnn", posts)
    print("after", round(time.perf_counter() - t, 1), "s:", type(caught.value).__name__, str(caught.value)[:200])
    async with db.connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(signals))).scalar_one() == 0


# --- P12 (expected OK): first copy wins under truly overlapping transactions ---------------


async def test_p12_overlapping_writes_keep_earliest(db: AsyncEngine) -> None:
    from sqlalchemy import text as sql_text

    from engine.feeds.posts import mirror_post
    from engine.feeds.store import store_posts
    from engine.tables import signal_sightings

    async def via(post_id: str) -> tuple[str, str, int]:
        async with db.connect() as conn:
            row = (await conn.execute(select(signals).where(signals.c.key == f"truth_social:{post_id}"))).one()
            n = (await conn.execute(select(func.count()).select_from(signal_sightings).where(signal_sightings.c.signal_key == row.key))).scalar_one()
            return row.raw_via, row.first_seen_via, n

    # 1. A's transaction starts first (earlier now()), B inserts and commits first.
    p1 = mirror_post(day(20), "one", None, {})
    async with db.connect() as a, db.connect() as b:
        await a.begin(); await a.execute(sql_text("select now()"))
        await asyncio.sleep(0.05)
        await b.begin(); await store_posts(b, 1, "cnn", [p1]); await b.commit()
        await store_posts(a, 1, "trumpstruth", [p1]); await a.commit()
    r1 = await via(p1.status_id)

    # 2. A inserts (uncommitted); B's insert waits on A's row; A commits, then B finishes.
    p2 = mirror_post(day(21), "two", None, {})
    async with db.connect() as a, db.connect() as b:
        await a.begin(); await store_posts(a, 1, "trumpstruth", [p2])
        await b.begin()
        t = asyncio.create_task(store_posts(b, 1, "cnn", [p2]))
        await asyncio.sleep(0.2); assert not t.done()  # B is blocked on A's row
        await a.commit(); await t; await b.commit()
    r2 = await via(p2.status_id)

    # 3. B's transaction starts first, A inserts + commits, then B's insert conflicts.
    p3 = mirror_post(day(22), "three", None, {})
    async with db.connect() as a, db.connect() as b:
        await b.begin(); await b.execute(sql_text("select now()"))
        await asyncio.sleep(0.05)
        await a.begin(); await store_posts(a, 1, "trumpstruth", [p3]); await a.commit()
        await store_posts(b, 1, "cnn", [p3]); await b.commit()
    r3 = await via(p3.status_id)
    print("case1", r1, "case2", r2, "case3", r3)
    assert r1 == ("cnn", "trumpstruth", 2)
    assert r2 == ("trumpstruth", "trumpstruth", 2)
    assert r3 == ("trumpstruth", "cnn", 2)


@pytest.mark.parametrize(("cnn_delay", "ts_delay"), [(0.0, 0.0), (0.1, 0.0), (0.0, 0.1)])
async def test_p1b_real_loop_race(
    migrated: Settings, db: AsyncEngine, cnn_delay: float, ts_delay: float
) -> None:
    t0 = day(1)
    await store_old(db, t0)
    gap = [day(5), day(8), day(10)]
    window = [day(d) for d in (28, 27, 26, 25, 24)]
    head = [day(d) for d in (28, 27, 26)]
    downloads = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == TRUMPSTRUTH_HOST:
            await asyncio.sleep(ts_delay)
            return rss_route(window)(request)
        if "range" in request.headers:
            await asyncio.sleep(cnn_delay)  # CNN's range read answers a little later
            body = ("[" + ",".join(f'{{"id": "{i}", "content": "c {i}"}}' for i in head)).encode()
            return httpx.Response(206, content=body, headers={"content-type": "application/json"})
        downloads.append(request)
        return json_response([cnn_item(i) for i in [*window, *gap, t0]])

    settings = feed_settings(migrated, sources_off=frozenset({"direct", "scrapecreators"}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        live = Live(EngineContext(settings, db), client)
        task = asyncio.create_task(live.run())
        await asyncio.sleep(1.0)
        task.cancel()
    stored = await keys(db)
    print(f"cnn delay {cnn_delay}s, trumpstruth delay {ts_delay}s: downloads {len(downloads)}, gap stored {[g in stored for g in gap]}")


async def test_p4b_recovery_after_handover_is_never_announced(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    from tests.feeds_helpers import direct_ok

    web.routes[DIRECT_HOST] = status(403)
    only_direct = frozenset({"trumpstruth", "cnn", "scrapecreators"})
    first = make_live(sources_off=only_direct)
    await first.start()
    await first.pollers["direct"].poll()  # blocked: one message
    web.routes[DIRECT_HOST] = direct_ok  # the block lifts during a deploy
    second = make_live(sources_off=only_direct)
    await second.start()
    await second.pollers["direct"].poll()
    print(
        "feed_blocked:", len(operator_notices(caplog, "feed_blocked")),
        "feed_recovered:", len(operator_notices(caplog, "feed_recovered")),
    )
    assert len(operator_notices(caplog, "feed_blocked")) == 1
    assert len(operator_notices(caplog, "feed_recovered")) == 0
