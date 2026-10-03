"""The live `alert` stage on planted history: similar-post evidence by the backtest's
method, send rule v1 through the stage, the challenger, the wake hook and the pause
switch, the moves filler and the worker's start checks."""

import asyncio
import dataclasses
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

import engine.alerts.stage as stage
from engine.alerts.evidence import Evidencer, LivePool, Post, Target
from engine.alerts.fill import fill_worker, unfilled
from engine.alerts.public import check_public
from engine.alerts.send_rule import BadSendRule, Picker, SendRule, current_send_rule
from engine.alerts.stage import market_open
from engine.alerts.store import read_changes
from engine.alerts.wake import Wake, sends_paused
from engine.backtest.gate import Pair
from engine.extract.ai import AiPicker
from engine.extract.similarity import load_match_rule
from engine.feeds.posts import Post as FeedPost
from engine.feeds.store import store_posts, trump_source_id
from engine.market.instruments import Instrument, all_instruments
from engine.pipeline import signals_worker
from engine.registry import EngineContext, WorkerFunc
from engine.settings import Settings
from engine.tables import alert_revisions, alerts, challenger_calls, signals
from tests.alert_helpers import (
    DryRun,
    LiveRun,
    ReasonStub,
    a_post,
    plant_backtest,
    plant_baselines,
    plant_move,
    plant_past,
    similar_history,
    slug_id,
    stub_ai_clients,
    stub_vector,
)
from tests.conftest import operator_notices
from tests.extract_helpers import StubClient, StubEmbedder, answer, ready_config, sync_names
from tests.market_helpers import market_settings

WORDS = "Apple and $NVDA are building big plants in America"
MOVES = [-0.004, -0.004, -0.004, 0.002]
"""Cycled over 12 past posts: 9 fell and 3 rose, median -0.4%."""
PASSING_SPY_1H = {"rules": frozenset({Pair("spy", "1h")}), "ai": frozenset()}


@dataclasses.dataclass
class History:
    now: datetime
    spy: int
    past: list[str]


@pytest.fixture
async def history(db: AsyncEngine) -> History:
    """12 past posts like WORDS on 12 days, with SPY's 1h moves, and SPY's random-time
    median of 0.0% at every hour."""
    await sync_names(db)
    now = datetime.now(UTC)
    past = []
    async with db.begin() as conn:
        spy = await slug_id(conn, "spy")
        rng = np.random.default_rng(5)
        for when, words, vector, move in similar_history(WORDS, 12, MOVES, now, rng):
            key = await plant_past(conn, when, words, vector)
            await plant_move(conn, spy, key, "1h", move, when + timedelta(minutes=62))
            past.append(key)
        await plant_baselines(conn, spy, "1h", 0.0)
    return History(now, spy, past)


def rule(**changes: Any) -> SendRule:
    return dataclasses.replace(current_send_rule(), **changes)


def live(minutes_ago: float = 1, words: str = WORDS, low: int = 1) -> FeedPost:
    return a_post(datetime.now(UTC) - timedelta(minutes=minutes_ago), words, low)


def live_ai() -> AiPicker:
    return AiPicker(ready_config(), stub_ai_clients(market_link=True))


async def count(db: AsyncEngine, table: Any) -> int:
    async with db.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(table))).scalar_one())


async def column(db: AsyncEngine, query: Any) -> list[Any]:
    async with db.connect() as conn:
        return list((await conn.execute(query)).scalars())


# --- evidence ----------------------------------------------------------------------------------


async def test_the_evidence_is_the_backtests_method_on_similar_past_posts(
    db: AsyncEngine, history: History
) -> None:
    async with db.begin() as conn:
        await plant_backtest(conn, {("rules", "spy:1h"): (0.5812, 40)})
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    (alerted,) = await run.post(live())
    alert = alerted.alert
    assert alert is not None and alert.disposition == "sent" and alert.lead == "spy:1h"
    assert check_public(alert.model_dump(mode="json")) == []
    call = next(c for c in alert.calls if c.instrument == "spy" and c.window == "1h")
    assert call.sent and call.direction == "down" and call.gate_passed
    evidence = call.evidence
    assert (evidence.matches, evidence.match_days, evidence.low_sample) == (12, 12, False)
    assert (evidence.share_in_direction, evidence.median_move, evidence.random_median) == (
        75.0,
        -0.4,
        0.0,
    )
    assert (evidence.backtest_hit_rate, evidence.backtest_days) == (58.12, 40)
    assert evidence.benchmark is None and evidence.median_vs_benchmark is None
    assert evidence.text == (
        "Like 12 past posts: SPY fell after 75% of them within 1 hour (median -0.4% vs random 0.0%)"
    )
    assert len(evidence.examples) == 3
    async with db.connect() as conn:
        keys = dict((await conn.execute(select(signals.c.public_id, signals.c.key))).all())
    assert all(keys[e.public_id] in history.past for e in evidence.examples)
    assert all(e.move in (-0.4, 0.2) for e in evidence.examples)
    others = [c for c in alert.calls if c is not call]
    assert {c.fyi_reason for c in others} == {"no_passing_pair"}
    assert not any(c.gate_passed for c in others)  # only spy:1h is listed as passing


async def draft_spy_1h(
    db: AsyncEngine, history: History, posted: datetime, *at: datetime
) -> list[Any]:
    """The spy:1h evidence of a post like WORDS made at `posted`, drafted at each `at`."""
    async with db.connect() as conn:
        evidencer = Evidencer(await LivePool.load(conn, StubEmbedder.version), load_match_rule())
        listed = {i.id: i for i in await all_instruments(conn)}
        calls: dict[Picker, list[Target]] = {
            "rules": [Target(Pair("spy", "1h"), listed[history.spy])]
        }
        post = Post("ts:live", posted, stub_vector(WORDS))
        return [
            (await evidencer.draft(conn, post, calls, listed, when))["rules"][0].evidence
            for when in at
        ]


async def test_the_pool_leaves_out_windows_that_had_not_closed_by_the_alert(
    db: AsyncEngine, history: History
) -> None:
    vector = stub_vector(WORDS)
    async with db.begin() as conn:
        recent = await plant_past(conn, history.now - timedelta(minutes=30), WORDS, vector)
        await plant_move(conn, history.spy, recent, "1h", 0.01, history.now + timedelta(minutes=32))
        skipped = await plant_past(conn, history.now - timedelta(days=20), WORDS + "!", vector)
        await plant_move(conn, history.spy, skipped, "1h", None, history.now)
    later = history.now + timedelta(hours=1)  # a post made an hour on: the window has closed
    (now,) = await draft_spy_1h(db, history, history.now, history.now)
    (after,) = await draft_spy_1h(db, history, later, later + timedelta(minutes=2))
    assert (now.matches, after.matches) == (12, 13)


async def test_the_evidence_is_as_of_the_posts_alert_time_however_late_it_is_drafted(
    db: AsyncEngine, history: History
) -> None:
    """Gate 0 v1 takes a post's matches as of its alert time, the post plus 2 minutes. A
    post drafted later (seen late through a mirror, or after an outage) gets the same: not
    an earlier post whose window closed inside its own, nor a post made after it."""
    posted = history.now - timedelta(hours=3)
    vector = stub_vector(WORDS)
    async with db.begin() as conn:
        edge = await plant_past(conn, posted - timedelta(minutes=60), f"{WORDS} (e)", vector)
        await plant_move(conn, history.spy, edge, "1h", -0.009, posted + timedelta(seconds=90))
        overlap = await plant_past(conn, posted - timedelta(minutes=59), f"{WORDS} (a)", vector)
        await plant_move(conn, history.spy, overlap, "1h", -0.009, posted + timedelta(minutes=3))
        after = await plant_past(conn, posted + timedelta(minutes=4), f"{WORDS} (b)", vector)
        await plant_move(conn, history.spy, after, "1h", -0.012, posted + timedelta(minutes=66))
    drafted = await draft_spy_1h(
        db, history, posted, *(posted + timedelta(minutes=m) for m in (1, 2, 5, 70))
    )
    # As of a minute after the post the edge window hadn't closed; from the alert time on,
    # it is the 13th match, and nothing that closed (or was posted) later joins it.
    assert [e.matches for e in drafted] == [12, 13, 13, 13]
    assert all(x.posted_at < posted for e in drafted for x in e.examples)


async def test_the_stage_drafts_the_evidence_as_of_the_alert_time_or_now_if_earlier(
    db: AsyncEngine, history: History
) -> None:
    """Through the stage. A post seen 70 minutes late counts neither a window that closed
    after its alert time nor a post made after it. A post 10 seconds old is drafted as of
    the database clock: a window closing 90 seconds from now isn't counted, though it
    closes before the post's alert time; the two that closed an hour ago are."""
    late, fresh = live(minutes_ago=70, low=1), live(minutes_ago=10 / 60, low=2)
    vector = stub_vector(WORDS)
    async with db.begin() as conn:
        overlap = await plant_past(conn, late.posted_at - timedelta(minutes=59), WORDS, vector)
        closed = late.posted_at + timedelta(minutes=3)
        await plant_move(conn, history.spy, overlap, "1h", 0.01, closed)
        after = await plant_past(conn, late.posted_at + timedelta(minutes=4), f"{WORDS}!", vector)
        closed = late.posted_at + timedelta(minutes=66)
        await plant_move(conn, history.spy, after, "1h", 0.01, closed)
        closing = await plant_past(conn, history.now - timedelta(minutes=59), f"{WORDS}?", vector)
        closes = history.now + timedelta(seconds=90)
        await plant_move(conn, history.spy, closing, "1h", 0.01, closes)
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    matches = []
    for post in (late, fresh):
        (alerted,) = await run.post(post)
        assert alerted.alert is not None
        call = next(c for c in alerted.alert.calls if (c.instrument, c.window) == ("spy", "1h"))
        matches.append(call.evidence.matches)
        assert all(e.posted_at < post.posted_at for e in call.evidence.examples)
    assert matches == [12, 14]


async def test_a_post_scored_live_becomes_a_match_for_the_next_one(
    db: AsyncEngine, history: History
) -> None:
    """Each post's vector joins the in-memory pool as it passes the stage: once its move is
    stored, the next look-alike counts it (12 + 1 matches) without a restart."""
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    first = live(minutes_ago=3, low=1)
    await run.post(first)
    async with db.begin() as conn:
        matured = datetime.now(UTC) - timedelta(seconds=1)
        await plant_move(conn, history.spy, first.key, "1h", -0.004, matured)
    (second,) = await run.post(live(minutes_ago=1, low=2))
    assert second.alert is not None
    call = next(c for c in second.alert.calls if (c.instrument, c.window) == ("spy", "1h"))
    assert call.evidence.matches == 13


async def test_a_move_past_the_percent_range_is_no_example_and_refuses_nothing(
    db: AsyncEngine, history: History, caplog: pytest.LogCaptureFixture
) -> None:
    """A real +357% close in the closest past post (as DWAC's on 2021-10-21) still counts
    as a match, but it isn't shown: the alerts are written, and nothing lands in
    signals.error."""
    async with db.begin() as conn:
        nvda = await slug_id(conn, "nvda")
        when = history.now - timedelta(days=40)
        best = await plant_past(conn, when, WORDS, stub_vector(WORDS))
        await plant_move(conn, nvda, best, "close", 3.57, when + timedelta(hours=5), 3.565)
        for key in history.past:
            closed = history.now - timedelta(hours=1)
            await plant_move(conn, nvda, key, "close", 0.01, closed, 0.01)
        await plant_baselines(conn, nvda, "close", 0.0, adjusted=0.0)
    run = LiveRun(db)
    first, second = live(minutes_ago=1, low=1), live(minutes_ago=0.5, low=2)
    alerted = await run.post(first, second)
    assert [a.alert is not None for a in alerted] == [True, True]
    for one in alerted:
        assert one.alert is not None and check_public(one.alert.model_dump(mode="json")) == []
        call = next(c for c in one.alert.calls if (c.instrument, c.window) == ("nvda", "close"))
        assert call.evidence.matches == 13 and len(call.evidence.examples) == 3
        assert all(e.move == 1.0 for e in call.evidence.examples)
    errors = await column(
        db, select(signals.c.error).where(signals.c.key.in_([first.key, second.key]))
    )
    assert errors == [None, None]
    assert sum("past the public range" in r.getMessage() for r in caplog.records) == 2  # once each


async def test_a_company_without_stored_moves_is_fyi_few_matches(
    db: AsyncEngine, history: History
) -> None:
    company = {"rules": frozenset({Pair("company", "close")}), "ai": frozenset()}
    run = LiveRun(db, rule(passing=company))
    (alerted,) = await run.post(live())
    assert alerted.alert is not None
    companies = [c for c in alerted.alert.calls if c.instrument in ("aapl", "nvda")]
    assert {c.instrument for c in companies} == {"aapl", "nvda"}
    closes = [c for c in companies if c.window == "close"]
    assert all(c.fyi_reason == "few_matches" and c.evidence.matches == 0 for c in closes)
    assert all(c.evidence.benchmark == "spy" for c in companies)
    assert alerted.alert.fyi_reason == "few_matches"
    async with db.connect() as conn:  # the moves filler builds them
        sample = await unfilled(conn)
        symbols = {i.id: i.slug for i in await all_instruments(conn)}
    assert sample is not None
    assert {"aapl", "nvda"} <= {symbols[i] for i in sample.missing}
    assert "spy" not in {symbols[i] for i in sample.missing}


# --- send rule v1 through the stage ----------------------------------------------------------


async def test_version_1_makes_every_alert_fyi_no_passing_pair(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db)
    (alerted,) = await run.post(live())
    assert alerted.alert is not None
    assert (alerted.alert.disposition, alerted.alert.fyi_reason) == ("fyi", "no_passing_pair")
    assert alerted.alert.send_rule == "v1" and alerted.alert.picker == "rules v1"
    assert not any(c.gate_passed for c in alerted.alert.calls)
    async with db.connect() as conn:
        row = (await conn.execute(select(alerts))).one()
        created = (await conn.execute(select(alert_revisions.c.created_at))).scalar_one()
    assert row.disposition == "fyi" and row.sent_instrument_ids == []
    assert row.doc == alerted.alert.model_dump(mode="json")
    assert row.alerted_at == created == alerted.alert.alerted_at  # revision 1's: the seq lock's


async def test_a_post_without_a_market_link_gets_no_alert(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    post = live(words="Happy birthday to my wonderful wife")
    assert await run.post(post) == [run.alerted[post.key]]
    assert run.alerted[post.key].alert is None
    assert await count(db, alerts) == 0
    assert await column(db, select(signals.c.stage).where(signals.c.key == post.key)) == ["done"]


async def test_a_post_after_send_until_is_late(db: AsyncEngine, history: History) -> None:
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    (alerted,) = await run.post(live(minutes_ago=15.5))
    assert alerted.alert is not None and alerted.alert.fyi_reason == "late"


async def test_a_second_send_on_spy_within_30_minutes_is_a_burst(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    (first,) = await run.post(live(minutes_ago=3, low=1))
    (second,) = await run.post(live(minutes_ago=2, low=2))
    assert first.alert is not None and first.alert.disposition == "sent"
    assert second.alert is not None and second.alert.fyi_reason == "burst"
    sent = await column(db, select(alerts.c.sent_instrument_ids).order_by(alerts.c.id))
    assert sent == [[history.spy], []]


async def test_the_database_refuses_a_second_alert_when_the_stage_runs_again(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db)
    post = live()
    await run.post(post)
    async with db.begin() as conn:
        await conn.execute(update(signals).where(signals.c.key == post.key).values(stage="alert"))
    assert run.runner is not None
    await run.runner.run_once()
    (error,) = await column(db, select(signals.c.error).where(signals.c.key == post.key))
    assert error is not None and "alerts_signal_key_key" in error
    assert (await count(db, alerts), await count(db, alert_revisions)) == (1, 1)


# --- the challenger and the reason line --------------------------------------------------------


async def test_the_challenger_is_stored_apart_and_never_on_the_cursor(
    db: AsyncEngine, history: History
) -> None:
    passing = {"rules": frozenset(), "ai": frozenset({Pair("spy", "1h")})}
    run = LiveRun(db, rule(passing=passing), ai=live_ai())
    (alerted,) = await run.post(live())
    assert alerted.alert is not None and alerted.alert.fyi_reason == "no_passing_pair"
    assert alerted.alert.reason == "The post names Apple and Nvidia plant plans"
    assert alerted.challenger is not None
    async with db.connect() as conn:
        (row,) = (await conn.execute(select(challenger_calls))).all()
        changes = await read_changes(conn, 0)
    assert (row.picker, row.disposition, row.sent_instrument_ids) == ("ai", "sent", [history.spy])
    spy = next(c for c in row.calls if c["instrument"] == "spy" and c["window"] == "1h")
    assert spy["sent"] and spy["evidence"]["matches"] == 12
    assert [r.kind for r in changes.revisions] == ["created"]
    assert changes.revisions[0].doc["picker"] == "rules v1"


async def test_with_the_ai_picker_in_use_the_rules_are_the_challenger(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db, rule(picker="ai", passing=PASSING_SPY_1H), ai=live_ai())
    (alerted,) = await run.post(live())
    assert alerted.alert is not None and alerted.alert.picker.startswith("ai v")
    assert await column(db, select(challenger_calls.c.picker)) == ["rules"]


async def test_the_ai_calls_only_the_companies_its_vote_counted(
    db: AsyncEngine, history: History
) -> None:
    """The AI vote counts a company only when both models name it. OpenAI names Apple and
    Anthropic doesn't, so the challenger (the AI) has no Apple call; the rules counted
    Apple and Nvidia, so the alert has both."""
    clients = {
        "openai": StubClient(
            "openai", default=answer(True, ("Apple", "AAPL", "stock", "explicit"))
        ),
        "anthropic": ReasonStub("anthropic", default=answer(True)),
    }
    run = LiveRun(db, ai=AiPicker(ready_config(), clients))
    (alerted,) = await run.post(live())
    assert alerted.alert is not None and alerted.challenger is not None
    assert {"aapl", "nvda"} <= {c.instrument for c in alerted.alert.calls}
    assert "aapl" not in {c.instrument for c in alerted.challenger}


async def test_a_challenger_record_the_public_check_refuses_holds_up_nothing(
    db: AsyncEngine,
    history: History,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def refuse_calls(doc: Any) -> list[str]:
        return (
            ["calls[].evidence.median_move: refused"]
            if "calls" in doc and "format" not in doc
            else check_public(doc)
        )

    monkeypatch.setattr(stage, "check_public", refuse_calls)
    run = LiveRun(db, ai=live_ai())
    (alerted,) = await run.post(live())
    assert alerted.alert is not None and alerted.challenger is None
    assert await count(db, alerts) == 1 and await count(db, challenger_calls) == 0
    (notice,) = operator_notices(caplog, "challenger_not_public")
    assert "median_move: refused" in notice


async def test_the_reason_line_gets_only_the_instruments_the_post_names(
    db: AsyncEngine, history: History
) -> None:
    """Not SPY's, QQQ's or BTC's names, which every market link calls: "500" (from "SPDR
    S&P 500 ETF Trust") is then a number the line may not state."""
    clients = stub_ai_clients()
    reason = clients["anthropic"]
    assert isinstance(reason, ReasonStub)
    reason.line = "Tariff post puts SPY near 500"
    run = LiveRun(db, ai=AiPicker(ready_config(), clients))
    (named, plain) = await run.post(
        live(minutes_ago=2, low=1),
        live(minutes_ago=1, words="Tariffs on China start Monday!", low=2),
    )
    assert named.alert is not None and plain.alert is not None
    assert named.alert.reason is None and plain.alert.reason is None  # refused: 500
    lines = [user for user in reason.asked if "\n\nTopic: " in user]  # not the picker's asks
    asked = [user.split("\nInstruments:")[1].strip() for user in lines]
    assert asked == ["Apple Inc., NVIDIA Corp.", ""], asked


async def test_a_reason_line_the_public_check_refuses_is_dropped(
    db: AsyncEngine, history: History
) -> None:
    clients = stub_ai_clients()
    reason = clients["anthropic"]
    assert isinstance(reason, ReasonStub)
    reason.line = (
        "Apple and Nvidia plan ¥5 plant deals"  # passes check_reason, not the public check
    )
    run = LiveRun(db, ai=AiPicker(ready_config(), clients))
    (alerted,) = await run.post(live(words=f"{WORDS}, 5 of them"))
    assert alerted.alert is not None and alerted.alert.reason is None


# --- the worker, the wake hook and the pause switch --------------------------------------------


def worker(**changes: Any) -> WorkerFunc:
    return signals_worker(
        embedder_loader=lambda s: StubEmbedder(), ai_loader=lambda s: None, **changes
    )


async def run_until(
    tasks: Sequence["asyncio.Future[None]"],
    done: Callable[[], Awaitable[bool]],
    seconds: float = 10,
) -> None:
    """Wait for `done()` while `tasks` run; fail at once if one of them stops."""
    async with asyncio.timeout(seconds):
        while not await done():
            assert not any(t.done() for t in tasks), [t.exception() for t in tasks if t.done()]
            await asyncio.sleep(0.02)


async def stop(tasks: Sequence["asyncio.Future[None]"]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def store(db: AsyncEngine, *posts: FeedPost) -> None:
    async with db.begin() as conn:
        await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)


async def test_the_wake_hook_reaches_a_delivery_worker_at_once(
    migrated: Settings, db: AsyncEngine, history: History
) -> None:
    ctx = EngineContext(migrated, db)
    dry = DryRun()  # polls every 30 s: only the wake gets it there sooner
    tasks = [asyncio.ensure_future(worker()(ctx)), asyncio.ensure_future(dry.worker()(ctx))]
    try:
        await asyncio.sleep(0.5)
        await store(db, live())

        async def read() -> bool:
            return bool(dry.read)

        await run_until(tasks, read)
    finally:
        await stop(tasks)
    assert [r.revision for r in dry.read] == [1] and ctx.wake.rung >= 1


async def test_paused_sends_hold_the_outlets_while_alerts_carry_on(
    migrated: Settings, db: AsyncEngine, history: History
) -> None:
    ctx = EngineContext(migrated.model_copy(update={"sends_paused": True}), db)
    dry = DryRun()
    tasks = [asyncio.ensure_future(worker()(ctx)), asyncio.ensure_future(dry.worker()(ctx))]
    try:
        await store(db, live())

        async def alerted() -> bool:
            return bool(ctx.wake.rung)

        await run_until(tasks, alerted)
        await asyncio.sleep(0.2)  # the outlet's turn after the ring
    finally:
        await stop(tasks)
    assert await count(db, alerts) == 1 and dry.read == []


async def test_a_missed_wake_is_covered_by_the_poll() -> None:
    wake = Wake()
    seen = wake.rung
    started = asyncio.get_running_loop().time()
    assert await wake.wait(seen, 0.2) == seen
    assert asyncio.get_running_loop().time() - started >= 0.2
    waiting = asyncio.ensure_future(wake.wait(seen, 30))
    await asyncio.sleep(0)
    wake.ring()
    assert await asyncio.wait_for(waiting, 1) == seen + 1
    async with asyncio.timeout(1):  # already rung (while the worker read): no wait
        assert await wake.wait(seen, 30) == seen + 1


MONDAY_10AM_NEW_YORK = datetime(2026, 3, 2, 15, 0, tzinfo=UTC)
MONDAY_10PM_NEW_YORK = datetime(2026, 3, 3, 3, 0, tzinfo=UTC)
SATURDAY_NOON_NEW_YORK = datetime(2026, 3, 7, 17, 0, tzinfo=UTC)


def test_stocks_and_etfs_are_open_in_the_regular_session_and_coins_always() -> None:
    spy = Instrument(1, "spy", "SPY", "SPDR S&P 500 ETF Trust", "etf", "XNYS", "SPY", None, None)
    aapl = Instrument(9, "aapl", "AAPL", "Apple Inc.", "stock", "XNYS", "AAPL", 1, None)
    btc = Instrument(3, "btc", "BTC", "Bitcoin", "coin", "24/7", "BTC/USD", None, None)
    for listed in (spy, aapl):
        assert market_open(listed, MONDAY_10AM_NEW_YORK)
        assert not market_open(listed, MONDAY_10PM_NEW_YORK)
        assert not market_open(listed, SATURDAY_NOON_NEW_YORK)
    for at in (MONDAY_10AM_NEW_YORK, MONDAY_10PM_NEW_YORK, SATURDAY_NOON_NEW_YORK):
        assert market_open(btc, at)


def test_sends_paused_is_read_from_engine_sends_paused(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not sends_paused(settings)
    monkeypatch.setenv("ENGINE_SENDS_PAUSED", "true")
    monkeypatch.setenv("ENGINE_DATABASE_URL", settings.db_url)
    assert sends_paused(Settings())


async def test_the_worker_refuses_an_ai_send_rule_without_the_ai(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    with pytest.raises(BadSendRule, match="isn't live"):
        await worker(send_rule=lambda: rule(picker="ai"))(EngineContext(migrated, db))


async def test_the_worker_refuses_calls_on_an_unknown_instrument(
    migrated: Settings, db: AsyncEngine
) -> None:
    await sync_names(db)
    unknown = rule(calls=(Pair("spy", "1h"), Pair("dia", "1h")))
    with pytest.raises(BadSendRule, match="dia"):
        await worker(send_rule=lambda: unknown)(EngineContext(migrated, db))


@pytest.mark.parametrize("call", [Pair("btc", "close"), Pair("company", "4h"), Pair("spy", "24h")])
async def test_the_worker_refuses_a_window_its_instrument_has_no_moves_for(
    migrated: Settings, db: AsyncEngine, call: Pair
) -> None:
    await sync_names(db)
    lacking = rule(calls=(Pair("spy", "1h"), call))
    with pytest.raises(BadSendRule, match=call.name):
        await worker(send_rule=lambda: lacking)(EngineContext(migrated, db))


# --- the moves filler --------------------------------------------------------------------------


async def test_the_moves_filler_builds_what_alerts_need_and_retries_a_failure_once(
    migrated: Settings,
    db: AsyncEngine,
    history: History,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await LiveRun(db).post(live())  # calls on SPY (built), QQQ, BTC, AAPL and NVDA
    async with db.connect() as conn:
        sample = await unfilled(conn)
    assert sample is not None and len(sample.missing) == 4
    data_to, missing = sample.data_to, sample.missing
    builds: list[tuple[date, list[int]]] = []

    async def build(settings: Settings, day: date, ids: Sequence[int]) -> None:
        builds.append((day, list(ids)))
        if len(builds) == 1:
            raise RuntimeError("Alpaca is down")
        async with db.begin() as conn:  # the last has no prices in the sample: none written
            for i in ids[:-1]:
                await plant_baselines(conn, i, "1h", 0.0, data_to=day)

    fast = market_settings(migrated, fill_moves_tick_seconds=0.05, fill_moves_retry_seconds=0.5)
    tasks = [asyncio.ensure_future(fill_worker(build)(EngineContext(fast, db)))]
    try:

        async def built_twice() -> bool:
            return len(builds) == 2

        await run_until(tasks, built_twice)
        await asyncio.sleep(0.7)  # past another retry interval: nothing is due again
    finally:
        await stop(tasks)
    assert builds == [(data_to, missing), (data_to, missing)]
    async with db.connect() as conn:
        left = await unfilled(conn)
    assert left is not None and (left.data_to, left.missing) == (data_to, missing[-1:])
    assert len(operator_notices(caplog, "moves_fill_failed")) == 4  # one each, once


async def test_the_moves_filler_waits_while_a_sample_is_being_built(
    migrated: Settings, db: AsyncEngine, history: History
) -> None:
    """build-moves writes a sample one instrument at a time. While a new day's sample grows
    (here SPY first, then the rest), the filler starts no build beside it, and once the
    sample holds still nothing is left for it."""
    await LiveRun(db).post(live())  # calls on SPY, QQQ, BTC, AAPL and NVDA
    async with db.begin() as conn:
        ids = [await slug_id(conn, slug) for slug in ("spy", "qqq", "btc", "aapl", "nvda")]
        for i in ids:  # the day before: every one built
            await plant_baselines(conn, i, "1h", 0.0, data_to=date(2026, 9, 30))
        await plant_baselines(conn, ids[0], "1h", 0.0, data_to=date(2026, 10, 1))
    builds: list[list[int]] = []

    async def build(settings: Settings, day: date, due: Sequence[int]) -> None:
        builds.append(list(due))

    fast = market_settings(migrated, fill_moves_tick_seconds=0.1)
    tasks = [asyncio.ensure_future(fill_worker(build)(EngineContext(fast, db)))]
    try:
        for i in ids[1:]:  # the other build goes on writing, an instrument per 0.05 s
            await asyncio.sleep(0.05)
            async with db.begin() as conn:
                await plant_baselines(conn, i, "1h", 0.0, data_to=date(2026, 10, 1))
        await asyncio.sleep(0.5)  # several ticks with the sample holding still
    finally:
        await stop(tasks)
    assert builds == []


async def test_the_moves_filler_needs_alpacas_keys(
    migrated: Settings, db: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    async def build(settings: Settings, day: date, ids: Sequence[int]) -> None:
        raise AssertionError("built without keys")

    await asyncio.wait_for(fill_worker(build)(EngineContext(migrated, db)), 5)
    assert "no Alpaca keys" in caplog.text
