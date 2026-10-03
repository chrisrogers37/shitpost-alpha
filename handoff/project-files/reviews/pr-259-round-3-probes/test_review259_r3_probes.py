"""Round-3 review probes for PR #259 at 7d96886. Tests named `test_r3bug_...` pass when the
suspected bug is real; `test_r3check_...` pass when the fix works. Not finished tests:
prints, minimal cleanup. Do not commit."""

import asyncio
import logging
import time
from typing import Any, NoReturn

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import DataError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds import live as live_module
from engine.feeds.posts import status_time
from engine.feeds.status import status_lines
from engine.feeds.store import store_posts
from engine.tables import feed_status, signal_sightings, signals, source_stats
from tests import helpers
from tests.conftest import operator_notices
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    json_response,
    status,
)
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
    refused,
    started,
    status_json,
    store_imported,
    stored_ids,
    web,
)
from tests.feeds_helpers import FakeWeb

ONLY_DIRECT_AND_SC = frozenset({"trumpstruth", "cnn"})


async def stats(db: AsyncEngine, feed: str) -> tuple[int, int, int]:
    async with db.connect() as conn:
        row = (
            await conn.execute(
                select(
                    func.sum(source_stats.c.polls),
                    func.sum(source_stats.c.errors),
                    func.sum(source_stats.c.blocks),
                ).where(source_stats.c.feed == feed)
            )
        ).one()
    return (int(row[0] or 0), int(row[1] or 0), int(row[2] or 0))


async def status_row(db: AsyncEngine, feed: str) -> Any:
    return await one(db, select(feed_status).where(feed_status.c.feed == feed))


# --- S1: the whole life of a block during catch-up -----------------------------------------


async def test_r3check_s1_cnn_blocked_catch_up_lifecycle(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    await store_imported(db, GAP_START)
    mark = status_time(GAP_START)
    downloads: list[httpx.Request] = []
    answer = {"download": refused}
    web.routes[CNN_HOST] = cnn_after_outage(downloads, lambda r: answer["download"](r))
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]

    await cnn.poll()  # head 206 (etag v1), download 429
    row = await status_row(db, "cnn")
    print("1:", cnn.state, await stats(db, "cnn"), row.state, row.caught_up_to, row.last_error)
    assert cnn.state == "up" and set(HEAD) <= await stored_ids(db)
    assert await stats(db, "cnn") == (1, 0, 1)
    assert row.state == "up" and row.caught_up_to == mark and row.last_error.endswith("HTTP 429")
    assert cnn.feed.etag is None and cnn.catch_up_wait == 60

    await cnn.poll()  # waiting: no download, no If-None-Match, error kept
    last = [r for r in web.requests if r.url.host == CNN_HOST][-1]
    row2 = await status_row(db, "cnn")
    assert len(downloads) == 1 and "if-none-match" not in last.headers
    assert await stats(db, "cnn") == (2, 0, 1) and row2.last_error == row.last_error

    cnn.catch_up_after = 0  # the wait is over; still refused
    await cnn.poll()
    assert len(downloads) == 2 and cnn.catch_up_wait == 120 and await stats(db, "cnn") == (3, 0, 2)
    assert operator_notices(caplog, "feed_blocked") == []

    answer["download"] = lambda r: json_response([cnn_item(i) for i in [*WINDOW, *GAP, GAP_START]])
    cnn.catch_up_after = 0
    await cnn.poll()
    row4 = await status_row(db, "cnn")
    stored = await stored_ids(db)
    print("4:", row4.state, row4.caught_up_to, row4.last_error, cnn.feed.etag, cnn.catch_up_wait)
    assert set(GAP) <= stored and set(WINDOW) <= stored
    assert row4.caught_up_to == status_time(HEAD[0]) and row4.last_error is None
    assert cnn.feed.etag == '"v1"' and cnn.catch_up_wait == 0 and cnn.catch_up_error is None

    await cnn.poll()  # now conditional: 304
    last = [r for r in web.requests if r.url.host == CNN_HOST][-1]
    assert last.headers.get("if-none-match") == '"v1"' and len(downloads) == 3
    async with db.connect() as conn:
        sightings = (
            await conn.execute(
                select(signal_sightings.c.signal_key, func.count())
                .where(signal_sightings.c.feed == "cnn")
                .group_by(signal_sightings.c.signal_key)
            )
        ).all()
        n_signals = (await conn.execute(select(func.count()).select_from(signals))).scalar_one()
    print("sightings", len(sightings), "signals", n_signals)
    assert all(n == 1 for _, n in sightings)
    assert len(sightings) == len(set(WINDOW) | set(GAP)) and n_signals == len(sightings) + 1
    assert await stats(db, "cnn") == (5, 0, 2)


async def test_r3check_s1_direct_page_back_429_then_fills(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    await store_imported(db, GAP_START)
    page_one = [status_json(i) for i in HEAD]
    page_two = [status_json(i) for i in [*GAP, GAP_START]]
    requests = {"page1": 0, "back": 0}
    refuse = {"on": True}

    def direct(request: httpx.Request) -> httpx.Response:
        if "max_id" in request.url.params:
            requests["back"] += 1
            return httpx.Response(429) if refuse["on"] else json_response(page_two)
        requests["page1"] += 1
        return json_response(page_one)

    web.routes[DIRECT_HOST] = direct
    live = await started(
        make_live(sources_off=ONLY_DIRECT_AND_SC, scrapecreators_key=SecretStr("k"))
    )
    d = live.pollers["direct"]
    for _ in range(3):
        d.last_poll = None
        await d.poll()
    print("requests", requests, "stats", await stats(db, "direct"), "sc", live.interval("scrapecreators"))
    assert requests == {"page1": 3, "back": 1} and d.state == "up"
    assert await stats(db, "direct") == (3, 0, 1)
    assert live.interval("scrapecreators") == 3600
    assert operator_notices(caplog, "feed_blocked") == []
    refuse["on"] = False
    d.catch_up_after = 0
    await d.poll()
    assert set(GAP) <= await stored_ids(db) and d.caught_up_to == status_time(HEAD[0])
    assert web.count(SCRAPECREATORS_HOST) == 0


async def test_r3check_n3_waiting_poll_keeps_the_error(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)
    web.routes[CNN_HOST] = cnn_after_outage([], status(503))
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    await cnn.poll()
    first = (await status_row(db, "cnn")).last_error
    await cnn.poll()
    second = (await status_row(db, "cnn")).last_error
    async with db.connect() as conn:
        line = [ln for ln in await status_lines(conn) if ln.startswith("feed cnn")][0]
    print(first, "|", second, "|", line)
    assert first and second == first and "catch-up to" in line


# --- N2: page-backs share the head read's memo --------------------------------------------


async def test_r3bug_n2_direct_page_back_resets_the_heads_skip_memo(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """direct's newest page has one odd item; a catch-up page has none. The page-back goes
    through map_items(part="read"), so the next head read logs the same odd item again."""
    caplog.set_level(logging.WARNING)
    await store_imported(db, GAP_START)
    page_one = [None, *[status_json(i) for i in HEAD]]
    page_two = [status_json(i) for i in [*GAP, GAP_START]]
    web.routes[DIRECT_HOST] = lambda request: json_response(
        page_two if "max_id" in request.url.params else page_one
    )
    live = await started(make_live(sources_off=frozenset({"trumpstruth", "cnn", "scrapecreators"})))
    d = live.pollers["direct"]
    for _ in range(3):
        d.last_poll = None
        await d.poll()
    warnings = [r.getMessage() for r in caplog.records if "items that don't map" in r.getMessage()]
    print(len(warnings), warnings)
    assert set(GAP) <= await stored_ids(db)
    assert len(warnings) == 2  # once for the first read, again after the page-back


# --- stale catch-up wait --------------------------------------------------------------------


async def test_r3bug_catch_up_wait_is_not_reset_when_the_gap_closes_without_a_catch_up(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    """ScrapeCreators stands in for direct and its catch-up fails three times; direct
    recovers (ScrapeCreators only checks, no catch-up); later direct is blocked again and
    ScrapeCreators' next catch-up failure backs off from the old value, not from 1 min."""
    await store_imported(db, GAP_START)
    sc_page = {"posts": [status_json(i) for i in HEAD], "success": True}
    web.routes[SCRAPECREATORS_HOST] = lambda request: (
        httpx.Response(503) if "next_max_id" in request.url.params else json_response(sc_page)
    )
    direct_answer = {"route": status(403)}
    web.routes[DIRECT_HOST] = lambda r: direct_answer["route"](r)
    live = await started(make_live(sources_off=ONLY_DIRECT_AND_SC, scrapecreators_key=SecretStr("k")))
    d, sc = live.pollers["direct"], live.pollers["scrapecreators"]
    await d.poll()
    assert d.state == "blocked"
    for _ in range(3):
        sc.catch_up_after = 0
        await sc.poll()
    after_three = sc.catch_up_wait
    direct_answer["route"] = lambda r: json_response([status_json(i) for i in HEAD])
    d.last_poll = None
    await d.poll()
    assert d.state == "up"
    await sc.poll()  # only checking now: returns before any catch-up bookkeeping
    direct_answer["route"] = status(403)
    d.last_poll = None
    await d.poll()
    assert d.state == "blocked"
    # a new gap for ScrapeCreators: its mark moved to HEAD[0] on the checking poll
    newer = [day(d_) for d_ in (30, 29)]
    sc_page["posts"] = [status_json(i) for i in newer]
    sc.catch_up_after = 0
    await sc.poll()
    print("after three failures", after_three, "first failure of the next incident", sc.catch_up_wait)
    assert after_three == 240
    assert sc.catch_up_wait == 480  # 60 expected for a new incident


# --- a store failure after a good catch-up repeats the whole download at the poll rate -----


async def test_r3bug_failed_store_after_catch_up_downloads_again_every_poll(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_after_outage(downloads)
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]

    async def failing(*args: Any, **kwargs: Any) -> NoReturn:
        raise OperationalError("INSERT", {}, Exception("server closed the connection"))

    monkeypatch.setattr(live_module, "store_posts", failing)
    for _ in range(3):
        cnn.last_poll = None
        with pytest.raises(OperationalError):
            await cnn.poll()
    print("downloads after 3 polls whose store failed:", len(downloads), "catch_up_wait", cnn.catch_up_wait)
    assert len(downloads) == 3


async def test_r3control_failed_download_is_backed_off(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_after_outage(downloads, status(503))
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    for _ in range(3):
        cnn.last_poll = None
        await cnn.poll()
    assert len(downloads) == 1


# --- a non-transient database error in the per-feed loop -----------------------------------


async def test_r3bug_poison_post_wedges_cnn_silently_but_no_hot_loop(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """A post whose text holds a NUL fails the store with DataError every poll: the loop
    stays at the poll interval (no hot spin), but the feed reads "up" with no error and
    source_stats counts nothing."""
    body = b'[{"id": "%s", "content": "bad \\u0000 text"}, {"id": "%s", "content": "ok"}, {"id": "1", "co' % (
        HEAD[0].encode(),
        HEAD[1].encode(),
    )
    web.routes[CNN_HOST] = lambda r: httpx.Response(
        206, content=body, headers={"content-type": "application/json"}
    )
    live = await started(make_live(sources_off=ONLY_CNN, cnn_interval_seconds=0.2))
    task = asyncio.create_task(live.run())
    await asyncio.sleep(1.5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    polls = web.count(CNN_HOST)
    errors = [r for r in caplog.records if "poll failed; trying again" in r.getMessage()]
    exc_types = {type(r.exc_info[1]).__name__ for r in errors if r.exc_info}
    async with db.connect() as conn:
        row = (await conn.execute(select(feed_status).where(feed_status.c.feed == "cnn"))).one_or_none()
        n = (await conn.execute(select(func.count()).select_from(signals))).scalar_one()
    print("requests in 1.5 s:", polls, "logged:", len(errors), exc_types, "status row:", row, "signals:", n)
    assert 4 <= polls <= 10  # the 0.2 s interval, not a hot loop
    assert exc_types == {"DataError"}
    assert row is None and n == 0  # nothing says the feed is failing
    assert await stats(db, "cnn") == (0, 0, 0)


# --- S2: other places a converted cancellation could be swallowed --------------------------


async def stall(*args: object, **kwargs: object) -> NoReturn:
    await helpers.stall_then_fail_on_cancel()


@pytest.mark.parametrize("where", ["failed-write", "answered-dark-clear", "status-write"])
async def test_r3check_s2_other_db_writes_stop_on_cancel(
    where: str, make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    live = await started(make_live(sources_off=ONLY_CNN))
    if where == "failed-write":
        web.routes[CNN_HOST] = status(503)
        monkeypatch.setattr(live_module, "count", stall)
    elif where == "status-write":
        monkeypatch.setattr(live_module, "set_feed_status", stall)
    else:
        live.dark_since = live_module.datetime.now(live_module.UTC)

        async def answered() -> NoReturn:
            await helpers.stall_then_fail_on_cancel()

        monkeypatch.setattr(live, "answered", answered)

    async def already_started() -> None:
        return None

    monkeypatch.setattr(live, "start", already_started)  # started above, before the patches
    task = asyncio.create_task(live.run())
    await asyncio.sleep(0.3)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and task.cancelled()


async def test_r3check_s2_programming_error_cancel_in_dark_watch(
    make_live: MakeLive, db: AsyncEngine
) -> None:
    """The ProgrammingError flavour (a cancel during a pool's first connect) in _go_dark."""
    from sqlalchemy.exc import ProgrammingError

    live = await started(make_live(sources_off=frozenset({"direct", "trumpstruth", "cnn", "scrapecreators"}), feeds_dark_after_seconds=1.0))

    class Db:
        def begin(self) -> Any:
            class Ctx:
                async def __aenter__(self) -> None:
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        raise ProgrammingError("connect", {}, Exception("cancel during connect")) from None

                async def __aexit__(self, *a: object) -> None:
                    return None

            return Ctx()

    live.db = Db()  # type: ignore[assignment]
    live.last_answer = time.monotonic() - 5
    task = asyncio.create_task(live._watch_dark())
    await asyncio.sleep(0.3)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and task.cancelled()


async def test_r3check_s2_cancel_during_live_start_stops_the_supervised_worker(
    make_live: MakeLive, web: FakeWeb, migrated: Any, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live.start() has no handler; under PR 1's _supervise a converted cancellation there
    still stops the worker."""
    from engine.registry import EngineContext
    from engine.runtime import _supervise
    from tests.feeds_helpers import feed_settings

    settings = feed_settings(migrated, sources_off=ONLY_CNN)
    monkeypatch.setattr(live_module, "set_feed_status", stall)
    worker = live_module.feeds_worker(web.transport())
    task = asyncio.create_task(_supervise("feeds", worker, EngineContext(settings, db)))
    await asyncio.sleep(0.3)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=2.0)
    if not done:
        await helpers.cancel_wedged()
    assert done and task.cancelled()


async def test_r3bug_preexisting_a_20_digit_id_fails_every_cnn_poll_instead_of_being_skipped(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    """parse_status_id accepts 20 digits, but status_time overflows past year 9999. The
    OverflowError comes from _catch_up's max(posted_at), outside map_items, so the whole
    read fails (and the feed blocks after 5) instead of skipping the one item."""
    odd = "99999999999999999999"
    body = b'[{"id": "%s", "content": "odd"}, {"id": "%s", "content": "ok"}, {"id": "1", "co' % (
        odd.encode(),
        HEAD[0].encode(),
    )
    web.routes[CNN_HOST] = lambda r: httpx.Response(
        206, content=body, headers={"content-type": "application/json"}
    )
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    for _ in range(5):
        await cnn.poll()
    row = await status_row(db, "cnn")
    print("state", cnn.state, "| last_error", row.last_error, "| stored", await stored_ids(db))
    assert cnn.state == "blocked" and "OverflowError" in row.last_error
    assert HEAD[0] not in await stored_ids(db)
