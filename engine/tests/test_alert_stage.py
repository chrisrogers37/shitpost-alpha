"""The live `alert` stage on planted history: similar-post evidence by the backtest's
method, send rule v1 through the stage, the challenger, the wake hook and the worker's
start checks."""

import asyncio
import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.alerts.evidence import Evidencer, LivePool, Post, Target
from engine.alerts.fill import unfilled
from engine.alerts.send_rule import BadSendRule, SendRule, current_send_rule
from engine.alerts.store import read_changes
from engine.alerts.wake import Wake, sends_paused
from engine.backtest.gate import Pair
from engine.extract.ai import AiPicker, Reply
from engine.extract.similarity import load_match_rule
from engine.market.instruments import all_instruments
from engine.pipeline import signals_worker
from engine.registry import EngineContext
from engine.settings import Settings
from engine.tables import alert_revisions, alerts, challenger_calls, signals
from tests.alert_helpers import (
    DryRun,
    LiveRun,
    a_post,
    plant_backtest,
    plant_baselines,
    plant_move,
    plant_past,
    similar_history,
    slug_id,
    stub_vector,
)
from tests.extract_helpers import StubClient, StubEmbedder, answer, ready_config, sync_names

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


def live(minutes_ago: float = 1, words: str = WORDS, low: int = 1) -> Any:
    return a_post(datetime.now(UTC) - timedelta(minutes=minutes_ago), words, low)


async def count(db: AsyncEngine, table: Any) -> int:
    async with db.connect() as conn:
        return int((await conn.execute(select(func.count()).select_from(table))).scalar_one())


# --- evidence ----------------------------------------------------------------------------------


async def test_the_evidence_is_the_backtests_method_on_similar_past_posts(
    db: AsyncEngine, history: History
) -> None:
    async with db.begin() as conn:
        await plant_backtest(conn, "rules", "spy:1h", 0.5812, 40)
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    (alerted,) = await run.post(live())
    alert = alerted.alert
    assert alert is not None and alert.disposition == "sent" and alert.lead == "spy:1h"
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
        "Like 12 past posts: SPY fell after 75% of them within 1 hour (median -0.4% vs random "
        "0.0%)"
    )
    assert len(evidence.examples) == 3
    async with db.connect() as conn:
        public_ids = dict(
            (await conn.execute(select(signals.c.public_id, signals.c.key))).all()
        )
    assert all(public_ids[e.public_id] in history.past for e in evidence.examples)
    assert all(e.move in (-0.4, 0.2) for e in evidence.examples)
    others = [c for c in alert.calls if c is not call]
    assert {c.fyi_reason for c in others} == {"no_passing_pair"}


async def test_the_pool_leaves_out_windows_that_had_not_closed_by_the_alert(
    db: AsyncEngine, history: History
) -> None:
    vector = stub_vector(WORDS)
    async with db.begin() as conn:
        recent = await plant_past(conn, history.now - timedelta(minutes=30), WORDS, vector)
        await plant_move(conn, history.spy, recent, "1h", 0.01, history.now + timedelta(minutes=32))
        unknown = await plant_past(conn, history.now - timedelta(days=20), WORDS + "!", vector)
        await plant_move(conn, history.spy, unknown, "1h", 0.01, history.now)
        await conn.execute(
            update(type(signals).c if False else __import__("engine.tables").tables.signal_moves)
            .where(__import__("engine.tables").tables.signal_moves.c.signal_key == unknown)
            .values(move_1h=None)
        )
    async with db.connect() as conn:
        pool = LivePool(
            (await LivePool.load(conn, StubEmbedder.version)).similarity
        )
        listed = {i.id: i for i in await all_instruments(conn)}
        evidencer = Evidencer(pool, load_match_rule())
        target = Target(Pair("spy", "1h"), listed[history.spy])
        post = Post("ts:live", history.now, vector)
        now = await evidencer.draft(conn, post, {"rules": [target]}, listed, history.now)
        later = await evidencer.draft(
            conn, post, {"rules": [target]}, listed, history.now + timedelta(hours=1)
        )
    assert now["rules"][0].evidence.matches == 12
    assert later["rules"][0].evidence.matches == 13  # its window has closed by then


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
        _, missing = await unfilled(conn)
        symbols = {i.id: i.slug for i in await all_instruments(conn)}
    assert {"aapl", "nvda"} <= {symbols[i] for i in missing}
    assert "spy" not in {symbols[i] for i in missing}


# --- send rule v1 through the stage ----------------------------------------------------------


async def test_version_1_makes_every_alert_fyi_no_passing_pair(
    db: AsyncEngine, history: History
) -> None:
    run = LiveRun(db)
    (alerted,) = await run.post(live())
    assert alerted.alert is not None
    assert (alerted.alert.disposition, alerted.alert.fyi_reason) == ("fyi", "no_passing_pair")
    assert alerted.alert.send_rule == "v1" and alerted.alert.picker == "rules v1"
    async with db.connect() as conn:
        row = (await conn.execute(select(alerts))).one()
    assert row.disposition == "fyi" and row.sent_instrument_ids == []
    assert row.doc == alerted.alert.model_dump(mode="json")


async def test_a_post_without_a_market_link_gets_no_alert(db: AsyncEngine, history: History) -> None:
    run = LiveRun(db, rule(passing=PASSING_SPY_1H))
    post = live(words="Happy birthday to my wonderful wife")
    assert await run.post(post) == [run.alerted[post.key]]
    assert run.alerted[post.key].alert is None
    assert await count(db, alerts) == 0
    async with db.connect() as conn:
        stage = (await conn.execute(select(signals.c.stage).where(signals.c.key == post.key))).scalar()
    assert stage == "done"


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
    async with db.connect() as conn:
        sent = (await conn.execute(select(alerts.c.sent_instrument_ids).order_by(alerts.c.id))).all()
    assert [tuple(r[0]) for r in sent] == [(history.spy,), ()]


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
    async with db.connect() as conn:
        error = (await conn.execute(select(signals.c.error).where(signals.c.key == post.key))).scalar()
    assert error is not None and "alerts_signal_key_key" in error
    assert (await count(db, alerts), await count(db, alert_revisions)) == (1, 1)


# --- the challenger and the reason line --------------------------------------------------------


@dataclasses.dataclass
class ReasonStub(StubClient):
    line: str = "The post names Apple and Nvidia plant plans"

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply:
        if "\n\nTopic: " in user:
            self.asked.append(user)
            return Reply({"id": "stub"}, self.line, 100, cached_input_tokens=0, output_tokens=10)
        return await super().ask(instructions, user, schema, max_tokens)


def live_ai() -> AiPicker:
    linked = answer(True)
    clients = {"openai": StubClient("openai", default=linked), "anthropic": ReasonStub("anthropic", default=linked)}
    return AiPicker(ready_config(), clients)  # type: ignore[arg-type]


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
    assert row.picker == "ai" and row.disposition == "sent" and row.sent_instrument_ids == [history.spy]
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
    async with db.connect() as conn:
        assert (await conn.execute(select(challenger_calls.c.picker))).scalar() == "rules"


# --- the worker, the wake hook and the pause switch --------------------------------------------


def worker(**changes: Any) -> Any:
    return signals_worker(
        embedder_loader=lambda s: StubEmbedder(), ai_loader=lambda s: None, **changes
    )


async def test_the_wake_hook_reaches_a_delivery_worker_at_once(
    migrated: Settings, db: AsyncEngine, history: History
) -> None:
    ctx = EngineContext(migrated, db)
    dry = DryRun()  # polls every 30 s: only the wake gets it there sooner
    tasks = [asyncio.ensure_future(worker()(ctx)), asyncio.ensure_future(dry.worker()(ctx))]
    try:
        await asyncio.sleep(0.5)
        async with db.begin() as conn:
            from engine.feeds.store import store_posts, trump_source_id

            await store_posts(conn, await trump_source_id(conn), "trumpstruth", [live()])
        async with asyncio.timeout(10):
            while not dry.read:
                assert not any(t.done() for t in tasks), [t.exception() for t in tasks if t.done()]
                await asyncio.sleep(0.02)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert [r.revision for r in dry.read] == [1] and ctx.wake.rung >= 1


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
    assert await wake.wait(seen, 30) == seen + 1  # already rung: no wait


def test_sends_paused_is_read_from_engine_sends_paused(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not sends_paused(settings)
    monkeypatch.setenv("ENGINE_SENDS_PAUSED", "true")
    monkeypatch.setenv("ENGINE_DATABASE_URL", settings.db_url)
    assert sends_paused(Settings())  # type: ignore[call-arg]


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
