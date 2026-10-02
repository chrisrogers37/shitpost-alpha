"""The live loop against a fake web: blocks, back-off, ScrapeCreators' schedule, catch-up,
all dark, the off switch, carrying on across copies, and the lease."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import event, func, insert, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.feeds import live as live_module
from engine.feeds import store as store_module
from engine.feeds.cnn import cnn_post, leading_items
from engine.feeds.live import Live, feeds_worker
from engine.feeds.mastodon import DirectFeed
from engine.feeds.posts import ACCOUNT_ID, mirror_post
from engine.feeds.status import status_lines
from engine.feeds.store import insert_signals, store_posts, trump_source_id
from engine.lease import LEASE_NAME
from engine.registry import EngineContext, Registry
from engine.runtime import run_engine
from engine.settings import FEED_NAMES, Settings
from engine.tables import (
    engine_lease,
    engine_meta,
    feed_status,
    signal_sightings,
    signals,
    source_stats,
)
from tests.conftest import operator_notices
from tests.feeds_helpers import (
    CNN_HOST,
    DIRECT_HOST,
    SCRAPECREATORS_HOST,
    TRUMPSTRUTH_HOST,
    FakeWeb,
    Route,
    cf_mitigated,
    challenge,
    cnn_ok,
    direct_ok,
    feed_settings,
    fixture_bytes,
    fixture_json,
    html_page,
    json_response,
    status,
    status_id_at,
)

MakeLive = Callable[..., Live]
ONLY_DIRECT = frozenset({"trumpstruth", "cnn", "scrapecreators"})
ONLY_CNN = frozenset({"direct", "trumpstruth", "scrapecreators"})
MIRRORS = frozenset({"direct", "scrapecreators"})


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


async def started(live: Live) -> Live:
    await live.start()
    return live


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


async def feed_columns(db: AsyncEngine, column: Any) -> dict[str, Any]:
    async with db.connect() as conn:
        return dict((await conn.execute(select(feed_status.c.feed, column))).all())


async def stored_ids(db: AsyncEngine) -> set[str]:
    return {key.split(":")[1] for key in await scalars(db, select(signals.c.key))}


def day(d: int) -> str:
    """A status id for a post at noon on that day of September 2026."""
    return status_id_at(datetime(2026, 9, d, 12, tzinfo=UTC))


def cnn_item(status_id: str) -> dict[str, Any]:
    return {"id": status_id, "content": f"post {status_id}", "media": []}


def cnn_head(status_ids: list[str]) -> bytes:
    """A range read's body: complete items, then one cut off."""
    items = ",".join(f'{{"id": "{i}", "content": "post {i}"}}' for i in status_ids)
    return f'[{items}, {{"id": "1", "conte'.encode()


def rss(status_ids: list[str]) -> Route:
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


@pytest.mark.parametrize(
    ("route", "polls"),
    [
        (status(403), 1),
        (status(429), 1),
        (challenge, 1),
        (html_page, 1),
        (cf_mitigated, 1),
        (status(500), 5),
    ],
)
async def test_each_block_signal_marks_direct_blocked(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, route: Route, polls: int
) -> None:
    live = await started(make_live(sources_off=ONLY_DIRECT))
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
    live = await started(make_live(sources_off=ONLY_DIRECT))
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


async def test_each_poll_is_counted(make_live: MakeLive, web: FakeWeb, db: AsyncEngine) -> None:
    def archive(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(
            206,
            content=fixture_bytes("cnn_head.json"),
            headers={"content-type": "application/json", "etag": '"v1"'},
        )

    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    for route in (archive, archive, status(500), status(403), status(403)):
        web.routes[CNN_HOST] = route
        await cnn.poll()
    row = await one(db, select(source_stats).where(source_stats.c.feed == "cnn"))
    assert (row.polls, row.not_modified, row.errors, row.blocks) == (5, 1, 1, 2)
    assert row.posts_seen == row.posts_first == 17


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


async def test_an_odd_answer_or_a_bug_in_one_feed_leaves_the_others_polling(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    web.routes[CNN_HOST] = lambda request: httpx.Response(
        206, content=b'{"message": "busy", "codes": [429]}', headers={"content-type": "json"}
    )

    async def broken_read(self: Any) -> Any:
        raise RuntimeError("a bug")

    monkeypatch.setattr(DirectFeed, "read", broken_read)
    await run_for(make_live(sources_off=frozenset({"scrapecreators"})), 0.5)
    assert web.count(TRUMPSTRUTH_HOST) >= 3 and web.count(CNN_HOST) >= 3
    errors = await feed_columns(db, feed_status.c.last_error)
    assert errors["direct"] == "unexpected error: RuntimeError('a bug')"
    assert errors["cnn"].startswith("the archive does not start with a JSON list")


async def test_scrapecreators_hourly_while_direct_is_healthy_else_every_2_minutes(
    make_live: MakeLive, web: FakeWeb
) -> None:
    timings: dict[str, object] = {
        "scrapecreators_key": SecretStr("key"),
        "scrapecreators_fallback_seconds": 120.0,
    }
    live = await started(make_live(**timings))
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


async def test_a_blocked_feed_never_polls_sooner_than_a_healthy_one(
    make_live: MakeLive, web: FakeWeb
) -> None:
    web.routes[SCRAPECREATORS_HOST] = status(401)
    key: dict[str, object] = {
        "scrapecreators_key": SecretStr("key"),
        "scrapecreators_fallback_seconds": 120.0,
    }
    checking = await started(make_live(**key))  # direct healthy: an hourly check
    sc = checking.pollers["scrapecreators"]
    await sc.poll()
    assert sc.state == "blocked" and sc.backoff == 60 and sc.last_poll is not None
    assert sc.due_in(sc.last_poll + 3599) > 0 >= sc.due_in(sc.last_poll + 3600)

    fallback = await started(make_live(sources_off=frozenset({"direct"}), **key))
    sc = fallback.pollers["scrapecreators"]
    sc.last_poll = time.monotonic()
    assert sc.due_in(sc.last_poll + 119) > 0 >= sc.due_in(sc.last_poll + 120)


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


def status_json(status_id: str) -> dict[str, Any]:
    return {"id": status_id, "content": f"<p>post {status_id}</p>", "account": {"id": ACCOUNT_ID}}


@pytest.mark.parametrize(
    ("feed", "host", "page_param"),
    [("direct", DIRECT_HOST, "max_id"), ("scrapecreators", SCRAPECREATORS_HOST, "next_max_id")],
)
async def test_catch_up_pages_back_without_duplicates(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, feed: str, host: str, page_param: str
) -> None:
    newest_stored = status_id_at(datetime(2026, 9, 1, tzinfo=UTC))
    await store_imported(db, newest_stored)
    page_one = fixture_json("direct_statuses.unverified.json")  # back to 21 Sep
    page_one_oldest = min(page_one, key=lambda s: int(s["id"]))["id"]
    gap = [status_id_at(datetime(2026, 9, day, tzinfo=UTC)) for day in (15, 10)]
    older = status_id_at(datetime(2026, 8, 30, tzinfo=UTC))
    page_two = [status_json(i) for i in [*gap, newest_stored, older]]

    def pages(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert ({"max_id", "next_max_id"} - {page_param}).isdisjoint(params)
        if page_param not in params:
            body: object = page_one
        else:
            assert params[page_param] == page_one_oldest
            body = page_two
        return json_response({"success": True, "posts": body} if feed != "direct" else body)

    web.routes[host] = pages
    others = frozenset(FEED_NAMES) - {feed}  # direct off: ScrapeCreators is the fallback
    live = await started(make_live(sources_off=others, scrapecreators_key=SecretStr("key")))
    await live.pollers[feed].poll()
    assert web.count(host) == 2  # the newest page, then one page back

    keys = await stored_ids(db)
    # The stored post, the newest page and the gap; nothing older than the stored post.
    assert keys == {newest_stored, *(s["id"] for s in page_one), *gap}
    for status_id in gap:  # catch-up posts are new live posts: they wait for scoring
        stage = await scalar(db, select(signals.c.stage).where(signals.c.key.endswith(status_id)))
        assert stage == "score"

    await live.pollers[feed].poll()  # no gap now: one request
    assert web.count(host) == 3


async def test_cnn_catch_up_reads_the_whole_file(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    newest_stored = status_id_at(datetime(2026, 9, 1, tzinfo=UTC))
    await store_imported(db, newest_stored)
    head = leading_items(fixture_bytes("cnn_head.json"))  # what the range read shows
    gap = [cnn_item(status_id_at(datetime(2026, 9, d, tzinfo=UTC))) for d in (20, 5)]
    older = cnn_item(status_id_at(datetime(2026, 8, 1, tzinfo=UTC)))
    downloads = []

    def archive(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            return cnn_ok(request)
        downloads.append(request)
        return json_response([*head, *gap, cnn_item(newest_stored), older])

    web.routes[CNN_HOST] = archive
    live = await started(make_live(sources_off=ONLY_CNN))
    await live.pollers["cnn"].poll()
    assert len(downloads) == 1
    assert "could not read back" not in caplog.text

    keys = await scalars(db, select(signals.c.key))
    # The head, the gap and the stored post; nothing older than the stored post.
    assert len(keys) == len(set(keys)) == len(head) + len(gap) + 1
    sighted = await scalars(db, select(signal_sightings.c.signal_key))
    assert len(sighted) == len(head) + len(gap)

    await live.pollers["cnn"].poll()
    assert len(downloads) == 1


GAP_START = day(1)  # the newest post stored before an outage
GAP = [day(5), day(8), day(10)]  # older than trumpstruth's window
WINDOW = [day(d) for d in (28, 27, 26, 25, 24)]  # trumpstruth's window
HEAD = [day(d) for d in (28, 27, 26)]  # CNN's range read


def cnn_after_outage(downloads: list[httpx.Request], download: Route | None = None) -> Route:
    def route(request: httpx.Request) -> httpx.Response:
        if "range" in request.headers:
            if request.headers.get("if-none-match") == '"v1"':
                return httpx.Response(304)
            return httpx.Response(
                206,
                content=cnn_head(HEAD),
                headers={"content-type": "application/json", "etag": '"v1"'},
            )
        downloads.append(request)
        if download is not None:
            return download(request)
        return json_response([cnn_item(i) for i in [*WINDOW, *GAP, GAP_START]])

    return route


async def test_a_feed_that_cannot_read_back_first_does_not_hide_a_gap(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[TRUMPSTRUTH_HOST] = rss(WINDOW)
    web.routes[CNN_HOST] = cnn_after_outage(downloads)
    live = await started(make_live(sources_off=MIRRORS))
    await live.pollers["trumpstruth"].poll()  # answers first, from day 24 on
    await live.pollers["trumpstruth"].poll()
    assert caplog.text.count("trumpstruth could not read back") == 1  # once per gap
    await live.pollers["cnn"].poll()
    assert len(downloads) == 1
    assert set(GAP) <= await stored_ids(db)
    marks = await feed_columns(db, feed_status.c.caught_up_to)
    assert marks["cnn"] == marks["trumpstruth"] == cnn_post(cnn_item(day(28))).posted_at


async def test_a_failed_catch_up_keeps_the_new_posts_and_is_tried_again_later(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_after_outage(downloads, status(503))
    live = await started(make_live(sources_off=ONLY_CNN))
    cnn = live.pollers["cnn"]
    await cnn.poll()
    assert len(downloads) == 1 and cnn.state == "up"
    assert set(HEAD) <= await stored_ids(db)  # the new posts are in at once
    assert cnn.catch_up_wait == 60

    web.routes[CNN_HOST] = cnn_after_outage(downloads)  # CNN is fine again
    await cnn.poll()
    assert len(downloads) == 1  # waiting a minute before the next try
    assert "if-none-match" not in web.requests[-1].headers  # its ETag wasn't kept

    cnn.catch_up_after = 0  # the minute is up
    await cnn.poll()
    assert len(downloads) == 2 and set(GAP) <= await stored_ids(db)
    await cnn.poll()
    assert web.requests[-1].headers["if-none-match"] == '"v1"'


async def test_a_gap_left_open_is_still_filled_after_a_restart(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, GAP_START)
    downloads: list[httpx.Request] = []
    web.routes[TRUMPSTRUTH_HOST] = rss(WINDOW)
    web.routes[CNN_HOST] = cnn_after_outage(downloads, status(503))
    first = await started(make_live(sources_off=MIRRORS))
    await first.pollers["trumpstruth"].poll()
    await first.pollers["cnn"].poll()  # the catch-up fails
    assert not set(GAP) & await stored_ids(db)

    web.routes[CNN_HOST] = cnn_after_outage(downloads)
    second = await started(make_live(sources_off=MIRRORS))  # a deploy: newest is day 28 now
    await second.pollers["cnn"].poll()
    assert set(GAP) <= await stored_ids(db)


async def test_a_failed_store_is_read_again(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloads: list[httpx.Request] = []
    web.routes[CNN_HOST] = cnn_after_outage(downloads)
    live = await started(make_live(sources_off=ONLY_CNN))
    calls = 0

    async def flaky(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError("INSERT", {}, Exception("server closed the connection"))
        return await store_posts(*args, **kwargs)

    monkeypatch.setattr(live_module, "store_posts", flaky)
    with pytest.raises(OperationalError):
        await live.pollers["cnn"].poll()
    await live.pollers["cnn"].poll()  # no If-None-Match: the posts come again
    assert set(HEAD) <= await stored_ids(db)


async def test_scrapecreators_check_does_not_catch_up_while_direct_is_healthy(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine
) -> None:
    await store_imported(db, status_id_at(datetime(2026, 9, 1, tzinfo=UTC)))
    live = await started(make_live(scrapecreators_key=SecretStr("key")))
    await live.pollers["scrapecreators"].poll()
    assert web.count(SCRAPECREATORS_HOST) == 1


async def test_a_new_copy_keeps_a_block_and_its_back_off(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    web.routes[DIRECT_HOST] = status(403)
    first = await started(make_live(sources_off=ONLY_DIRECT))
    for _ in range(3):
        await first.pollers["direct"].poll()  # blocked, now backing off 4 minutes
    since = first.pollers["direct"].blocked_since

    second = await started(make_live(sources_off=ONLY_DIRECT))  # a deploy or a restart
    direct = second.pollers["direct"]
    assert (direct.state, direct.backoff, direct.blocked_since) == ("blocked", 240, since)
    assert 239 < direct.due_in(time.monotonic()) <= 240
    await run_for(second, 0.2)
    assert web.count(DIRECT_HOST) == 3  # nothing before the back-off is over

    web.routes[DIRECT_HOST] = direct_ok  # the block lifted during the handover
    await direct.poll()
    assert len(operator_notices(caplog, "feed_blocked")) == 1
    (recovered,) = operator_notices(caplog, "feed_recovered")
    assert recovered.endswith(f"direct answers again (blocked since {since})")


async def test_scrapecreators_check_is_not_repeated_by_a_new_copy(
    make_live: MakeLive, web: FakeWeb
) -> None:
    key: dict[str, object] = {"scrapecreators_key": SecretStr("key")}
    await run_for(make_live(sources_off=frozenset({"trumpstruth", "cnn"}), **key), 0.2)
    await run_for(make_live(sources_off=frozenset({"trumpstruth", "cnn"}), **key), 0.2)
    assert web.count(SCRAPECREATORS_HOST) == 1  # one paid call an hour, deploys or not


async def test_all_dark_sends_one_message_and_clears_when_a_feed_answers(
    make_live: MakeLive, web: FakeWeb, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    for host in (DIRECT_HOST, TRUMPSTRUTH_HOST, CNN_HOST):
        web.routes[host] = status(503)
    dark: dict[str, object] = {
        "feeds_dark_after_seconds": 0.2,
        "feed_backoff_min_seconds": 0.02,
        "feed_backoff_max_seconds": 0.05,
    }
    await run_for(make_live(**dark), 0.6)
    assert len(operator_notices(caplog, "feeds_dark")) == 1
    dark_since = await scalar(db, select(engine_meta.c.feeds_dark_since))
    assert dark_since is not None
    assert f"{dark_since.astimezone(UTC):%Y-%m-%d %H:%M:%S}" in caplog.text  # one clock
    async with db.connect() as conn:
        assert f"feeds: dark since {dark_since}" in await status_lines(conn)

    second = make_live(**dark)  # a new copy: still dark, no second message
    task = asyncio.create_task(second.run())
    await asyncio.sleep(0.3)
    assert len(operator_notices(caplog, "feeds_dark")) == 1
    web.routes[CNN_HOST] = cnn_ok
    await asyncio.sleep(0.3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(operator_notices(caplog, "feeds_dark")) == 1
    assert len(operator_notices(caplog, "feeds_back")) == 1
    assert await scalar(db, select(engine_meta.c.feeds_dark_since)) is None


async def test_two_feeds_answering_together_send_one_back_message(
    make_live: MakeLive, caplog: pytest.LogCaptureFixture
) -> None:
    live = await started(make_live())
    live.dark_since = datetime(2026, 10, 1, tzinfo=UTC)
    await asyncio.gather(live.answered(), live.answered())
    assert len(operator_notices(caplog, "feeds_back")) == 1


async def test_store_writes_in_batches(db: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    """One statement can carry only 65,535 parameters; a big catch-up stores in batches."""
    monkeypatch.setattr(store_module, "BATCH", 4)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    posts = [mirror_post(status_id_at(base, low=i + 1), f"t {i}", False, {}) for i in range(10)]
    async with db.begin() as conn:
        source_id = await trump_source_id(conn)
        assert (await store_posts(conn, source_id, "trumpstruth", posts)).first == 10
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement.split("(")[0].strip())

    event.listen(db.sync_engine, "before_cursor_execute", record)
    try:
        async with db.begin() as conn:
            stored = await store_posts(conn, source_id, "cnn", posts)
    finally:
        event.remove(db.sync_engine, "before_cursor_execute", record)
    assert (stored.seen, stored.first) == (10, 0)
    assert await scalar(db, select(func.count()).select_from(signal_sightings)) == 20
    assert statements.count("INSERT INTO engine.signal_sightings") == 3  # 4 + 4 + 2
    assert sum(s.startswith("UPDATE engine.signals") for s in statements) == 3


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
