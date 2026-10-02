"""The live loop against a fake web: blocks, back-off, ScrapeCreators' schedule, catch-up,
all dark, the off switch and the lease."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds.cnn import cnn_post, leading_items
from engine.feeds.live import Live, feeds_worker
from engine.feeds.posts import ACCOUNT_ID
from engine.feeds.status import status_lines
from engine.feeds.store import insert_signals, trump_source_id
from engine.lease import LEASE_NAME
from engine.registry import EngineContext, Registry
from engine.runtime import run_engine
from engine.settings import Settings
from engine.tables import engine_lease, engine_meta, feed_status, signal_sightings, signals
from tests.conftest import operator_notices
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    TRUMPSTRUTH_HOST,
    FakeWeb,
    Route,
    challenge,
    cnn_ok,
    direct_ok,
    feed_settings,
    fixture_bytes,
    fixture_json,
    json_response,
    status,
    status_id_at,
)

MakeLive = Callable[..., Live]
ONLY_DIRECT = frozenset({"trumpstruth", "cnn", "scrapecreators"})


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
async def make_live(migrated: Settings, db: AsyncEngine, web: FakeWeb) -> AsyncIterator[MakeLive]:
    """Live loops on the test database with fast timings; `overrides` adjust settings."""
    clients: list[httpx.AsyncClient] = []

    def make(**overrides: object) -> Live:
        settings = feed_settings(migrated, **overrides)
        client = web.client(settings)
        clients.append(client)
        return Live(EngineContext(settings, db), client)

    yield make
    for client in clients:
        await client.aclose()


async def run_for(live: Live, seconds: float) -> None:
    task = asyncio.create_task(live.run())
    await asyncio.sleep(seconds)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def one(db: AsyncEngine, query: Any) -> Any:
    async with db.connect() as conn:
        return (await conn.execute(query)).one()


async def scalar(db: AsyncEngine, query: Any) -> Any:
    async with db.connect() as conn:
        return (await conn.execute(query)).scalar_one()


async def scalars(db: AsyncEngine, query: Any) -> list[Any]:
    async with db.connect() as conn:
        return list((await conn.execute(query)).scalars())


@pytest.mark.parametrize(
    ("route", "polls"),
    [
        (status(403), 1),
        (status(429), 1),
        (challenge, 1),
        (
            lambda request: httpx.Response(
                200, text="<html>Just a moment...</html>", headers={"content-type": "text/html"}
            ),
            1,
        ),
        (lambda request: json_response([], headers={"cf-mitigated": "challenge"}), 1),
        (status(500), 5),
    ],
)
async def test_each_block_signal_marks_direct_blocked(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, route: Route, polls: int
) -> None:
    live = make_live(sources_off=ONLY_DIRECT)
    await live.start()
    direct = live.pollers["direct"]
    web.routes[DIRECT_HOST] = route
    for _ in range(polls - 1):
        await direct.poll()
        assert direct.state == "up"
    await direct.poll()
    assert direct.state == "blocked"
    row = await one(db, select(feed_status).where(feed_status.c.feed == "direct"))
    assert row.state == "blocked" and row.blocked_since is not None


async def test_back_off_grows_from_1_to_30_minutes_with_one_message_each_way(
    make_live: MakeLive, web: FakeWeb, caplog: pytest.LogCaptureFixture
) -> None:
    live = make_live(sources_off=ONLY_DIRECT)
    await live.start()
    direct = live.pollers["direct"]
    web.routes[DIRECT_HOST] = status(403)
    backoffs = []
    for _ in range(8):
        await direct.poll()
        backoffs.append(direct.backoff)
    assert backoffs == [60, 120, 240, 480, 960, 1800, 1800, 1800]
    assert direct.last_poll is not None
    assert direct.due_in(direct.last_poll + 1799) > 0 >= direct.due_in(direct.last_poll + 1800)
    assert len(operator_notices(caplog, "feed_blocked")) == 1

    web.routes[DIRECT_HOST] = direct_ok
    await direct.poll()
    await direct.poll()
    assert (direct.state, direct.backoff, direct.failures) == ("up", 0, 0)
    assert len(operator_notices(caplog, "feed_recovered")) == 1

    web.routes[DIRECT_HOST] = status(429)  # a new incident, a new message
    await direct.poll()
    assert len(operator_notices(caplog, "feed_blocked")) == 2


async def test_other_feeds_keep_going_while_direct_is_blocked(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    web.routes[DIRECT_HOST] = status(403)
    live = make_live()
    await run_for(live, 0.5)
    assert web.count(DIRECT_HOST) == 1  # then backing off for a minute
    assert web.count(CNN_HOST) >= 3 and web.count(TRUMPSTRUTH_HOST) >= 3
    assert web.count(SCRAPECREATORS_HOST) == 0  # no key: off
    assert await scalar(db, select(func.count()).select_from(signals)) > 0


async def test_scrapecreators_hourly_while_direct_is_healthy_else_every_2_minutes(
    make_live: MakeLive, web: FakeWeb
) -> None:
    timings: dict[str, object] = {
        "scrapecreators_key": SecretStr("key"),
        "scrapecreators_check_seconds": 3600.0,
        "scrapecreators_fallback_seconds": 120.0,
    }
    live = make_live(**timings)
    await live.start()
    assert live.interval("scrapecreators") == 3600
    sc = live.pollers["scrapecreators"]
    await sc.poll()
    assert sc.last_poll is not None
    assert sc.due_in(sc.last_poll + 3599) > 0 >= sc.due_in(sc.last_poll + 3600)

    web.routes[DIRECT_HOST] = status(403)
    await live.pollers["direct"].poll()
    assert live.interval("scrapecreators") == 120
    assert sc.due_in(sc.last_poll + 120) <= 0

    web.routes[DIRECT_HOST] = direct_ok
    await live.pollers["direct"].poll()
    assert live.interval("scrapecreators") == 3600

    direct_off = make_live(sources_off=frozenset({"direct"}), **timings)
    assert "direct" not in direct_off.pollers
    assert direct_off.interval("scrapecreators") == 120


async def test_scrapecreators_is_off_without_a_key(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    live = make_live()
    assert live.off == {"scrapecreators": "no ENGINE_SCRAPECREATORS_KEY"}
    await run_for(live, 0.2)
    assert web.count(SCRAPECREATORS_HOST) == 0
    row = await one(db, select(feed_status).where(feed_status.c.feed == "scrapecreators"))
    assert (row.state, row.last_error) == ("off", "no ENGINE_SCRAPECREATORS_KEY")


async def test_off_switch_skips_listed_feeds_only(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    live = make_live(sources_off=frozenset({"direct", "scrapecreators"}))
    await run_for(live, 0.3)
    assert web.count(DIRECT_HOST) == 0 and web.count(SCRAPECREATORS_HOST) == 0
    assert web.count(CNN_HOST) >= 2 and web.count(TRUMPSTRUTH_HOST) >= 2
    async with db.connect() as conn:
        lines = await status_lines(conn)
    assert "feed direct: off (listed in ENGINE_SOURCES_OFF); last good read: never" in lines
    assert any(line.startswith("feed cnn: up; last good read: 20") for line in lines)
    assert any(line.startswith("signals by stage: done ") for line in lines)


async def store_imported(db: AsyncEngine, *items: dict[str, Any]) -> None:
    async with db.begin() as conn:
        posts = [cnn_post(item) for item in items]
        await insert_signals(conn, await trump_source_id(conn), "test", posts, imported=True)


def status_json(status_id: str) -> dict[str, Any]:
    return {"id": status_id, "content": f"<p>post {status_id}</p>", "account": {"id": ACCOUNT_ID}}


async def test_catch_up_pages_back_without_duplicates(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    newest_stored = status_id_at(datetime(2026, 9, 1, tzinfo=UTC))
    await store_imported(db, {"id": newest_stored, "content": "stored before the gap"})
    page_one = fixture_json("direct_statuses.unverified.json")  # back to 21 Sep
    page_one_oldest = min(page_one, key=lambda s: int(s["id"]))["id"]
    gap = [status_id_at(datetime(2026, 9, day, tzinfo=UTC)) for day in (15, 10)]
    older = status_id_at(datetime(2026, 8, 30, tzinfo=UTC))

    def pages(request: httpx.Request) -> httpx.Response:
        max_id = request.url.params.get("max_id")
        if max_id is None:
            return json_response(page_one)
        assert max_id == page_one_oldest
        return json_response([status_json(i) for i in [*gap, newest_stored, older]])

    web.routes[DIRECT_HOST] = pages
    live = make_live(sources_off=ONLY_DIRECT)
    await live.start()
    await live.pollers["direct"].poll()
    assert web.count(DIRECT_HOST) == 2  # the newest page, then one page back

    keys = list(await scalars(db, select(signals.c.key)))
    assert len(keys) == len(set(keys)) == 1 + len(page_one) + len(gap) + 1
    for status_id in gap:
        assert f"truth_social:{status_id}" in keys
    for status_id in gap:  # catch-up posts are new live posts: they wait for scoring
        stage = await scalar(db, select(signals.c.stage).where(signals.c.key.endswith(status_id)))
        assert stage == "score"

    await live.pollers["direct"].poll()  # no gap now: one request
    assert web.count(DIRECT_HOST) == 3


async def test_cnn_catch_up_reads_the_whole_file(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    newest_stored = status_id_at(datetime(2026, 9, 1, tzinfo=UTC))
    await store_imported(db, {"id": newest_stored, "content": "stored before the gap"})
    head = leading_items(fixture_bytes("cnn_head.json"))  # what the range read shows
    gap = [
        {"id": status_id_at(datetime(2026, 9, d, tzinfo=UTC)), "content": "gap"} for d in (20, 5)
    ]
    stored_again = {"id": newest_stored, "content": "stored before the gap"}
    older = {"id": status_id_at(datetime(2026, 8, 1, tzinfo=UTC)), "content": "old"}
    downloads = []

    def archive(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return cnn_ok(request)
        downloads.append(request)
        return json_response([*head, *gap, stored_again, older])

    web.routes[CNN_HOST] = archive
    live = make_live(sources_off=frozenset({"direct", "trumpstruth", "scrapecreators"}))
    await live.start()
    await live.pollers["cnn"].poll()
    assert len(downloads) == 1

    keys = await scalars(db, select(signals.c.key))
    # The head, the gap and the stored post; nothing older than the stored post.
    assert len(keys) == len(set(keys)) == len(head) + len(gap) + 1
    sighted = await scalars(db, select(signal_sightings.c.signal_key))
    assert len(sighted) == len(head) + len(gap)

    await live.pollers["cnn"].poll()
    assert len(downloads) == 1


async def test_all_dark_sends_one_message_and_clears_when_a_feed_answers(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    for host in (DIRECT_HOST, TRUMPSTRUTH_HOST, CNN_HOST):
        web.routes[host] = status(503)
    live = make_live(
        feeds_dark_after_seconds=0.2,
        feed_backoff_min_seconds=0.02,
        feed_backoff_max_seconds=0.05,
    )
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.6)
    assert len(operator_notices(caplog, "feeds_dark")) == 1
    dark_since = await scalar(db, select(engine_meta.c.feeds_dark_since))
    assert dark_since is not None
    async with db.connect() as conn:
        assert f"feeds: dark since {dark_since}" in await status_lines(conn)

    web.routes[CNN_HOST] = cnn_ok
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(operator_notices(caplog, "feeds_dark")) == 1
    assert len(operator_notices(caplog, "feeds_back")) == 1
    assert await scalar(db, select(engine_meta.c.feeds_dark_since)) is None


async def test_a_copy_without_the_lease_polls_nothing(
    migrated: Settings, db: AsyncEngine, web: FakeWeb
) -> None:
    settings = feed_settings(migrated)
    async with db.begin() as conn:
        await conn.execute(
            insert(engine_lease).values(
                name=LEASE_NAME,
                holder="another-copy",
                acquired_at=func.now(),
                expires_at=func.now() + timedelta(hours=1),
            )
        )
    registry = Registry()
    registry.register_worker("feeds", feeds_worker(web.transport()))
    stop = asyncio.Event()
    task = asyncio.create_task(run_engine(settings, registry, stop))
    await asyncio.sleep(1.0)
    assert web.requests == []

    async with db.begin() as conn:  # the other copy goes away: this one takes over
        await conn.execute(engine_lease.delete())
    await asyncio.sleep(1.0)
    stop.set()
    await task
    assert web.count(CNN_HOST) > 0
