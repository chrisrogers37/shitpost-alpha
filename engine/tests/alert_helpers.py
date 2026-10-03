"""Test-only helpers for the alert stage: a full sample alert, planted history (past
posts, their moves, the random-time medians, a backtest summary), a live run of the
`score` and `alert` stages, and a dry-run delivery worker that follows the cursor and
sends nothing."""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from engine.alerts.evidence import Evidencer, LivePool
from engine.alerts.model import AlertV1, Call, Evidence, Example, Instrument
from engine.alerts.send_rule import SendRule, current_send_rule
from engine.alerts.stage import ALERT, Alerted, Alerter
from engine.alerts.store import Revision, read_changes
from engine.alerts.wake import Wake
from engine.extract.ai import AiPicker
from engine.extract.rules import current_rules
from engine.extract.score import Scorer, store_embedding
from engine.extract.similarity import Embedded, Vector, load_match_rule
from engine.feeds.posts import Post
from engine.feeds.store import SCORE, insert_signals, store_posts, trump_source_id
from engine.registry import EngineContext, WorkerFunc
from engine.stages import Stage, StageRunner
from engine.tables import (
    backtest_runs,
    backtest_summary,
    instruments,
    random_baselines,
    signal_moves,
    signals,
)
from engine.text import normalize
from tests.extract_helpers import CountsAll, StubEmbedder
from tests.feeds_helpers import status_id_at

AT = datetime(2026, 3, 2, 15, 0, tzinfo=UTC)
"""A Monday, 10:00 New York."""


def sample_alert(**changes: Any) -> AlertV1:
    """An alert with every field filled, as the stage writes them."""
    evidence = Evidence(
        matches=14,
        match_days=12,
        share_in_direction=64.29,
        median_move=-0.42,
        median_vs_benchmark=None,
        benchmark=None,
        random_median=0.01,
        backtest_hit_rate=55.5,
        backtest_days=48,
        low_sample=False,
        text="Like 14 past posts: SPY fell after 64% of them within 1 hour (median -0.4% vs "
        "random 0.0%)",
        examples=[
            Example(
                public_id="Ab3_x-9Z",
                posted_at=AT - timedelta(days=30),
                excerpt="Tariffs on China start Monday",
                move=-0.61,
                vs_benchmark=None,
            )
        ],
    )
    company = evidence.model_copy(
        update={"benchmark": "spy", "median_vs_benchmark": -0.3, "examples": []}
    )
    values: dict[str, Any] = {
        "public_id": "Zz9_a-1B",
        "signal_key": "ts:1",
        "posted_at": AT,
        "alerted_at": AT + timedelta(minutes=2),
        "send_until": AT + timedelta(minutes=15),
        "excerpt": "Apple will build 4 plants, $500 Billion!",
        "topic": "trade",
        "picker": "rules v1",
        "send_rule": "v1",
        "reason": "The post names Apple's plant plans",
        "market_open": True,
        "disposition": "sent",
        "fyi_reason": None,
        "lead": "spy:1h",
        "instruments": [
            Instrument(slug="spy", symbol="SPY", asset_class="etf", market_open=True),
            Instrument(slug="aapl", symbol="AAPL", asset_class="stock", market_open=True),
        ],
        "calls": [
            Call(
                instrument="spy",
                window="1h",
                direction="down",
                gate_passed=True,
                sent=True,
                fyi_reason=None,
                evidence=evidence,
            ),
            Call(
                instrument="aapl",
                window="close",
                direction=None,
                gate_passed=False,
                sent=False,
                fyi_reason="no_passing_pair",
                evidence=company,
            ),
        ],
    }
    return AlertV1(**(values | changes))


def a_post(when: datetime, words: str, low: int = 1) -> Post:
    status_id = status_id_at(when, low)
    return Post(status_id, "post", None, words, False, {"id": status_id})


def stub_vector(text: str) -> Vector:
    """What StubEmbedder makes of a post's words: a planted post with it matches fully."""
    return StubEmbedder().embed([normalize(text)])[0].vector


async def slug_id(conn: AsyncConnection, slug: str) -> int:
    found: int = (
        await conn.execute(select(instruments.c.id).where(instruments.c.slug == slug))
    ).scalar_one()
    return found


async def plant_past(conn: AsyncConnection, when: datetime, words: str, vector: Vector) -> str:
    """A past post (imported, so not live) with its vector. Returns its key."""
    post = a_post(when, words, low=7)
    await insert_signals(conn, await trump_source_id(conn), "cnn", [post], imported=True)
    await store_embedding(conn, post.key, StubEmbedder.version, words, Embedded(vector, False))
    return post.key


async def plant_move(
    conn: AsyncConnection,
    instrument_id: int,
    key: str,
    window: str,
    move: float,
    matured: datetime,
    adjusted: float | None = None,
) -> None:
    await conn.execute(
        insert(signal_moves).values(
            instrument_id=instrument_id,
            entry="main",
            signal_key=key,
            adjustment="none",
            **{
                f"move_{window}": move,
                f"adjusted_{window}": adjusted,
                f"matured_{window}": matured,
            },
        )
    )


async def plant_baselines(
    conn: AsyncConnection,
    instrument_id: int,
    window: str,
    median: float,
    adjusted: float | None = None,
    data_to: Any = None,
) -> None:
    """The same random-time median for every weekday and hour."""
    data_to = data_to or (AT - timedelta(days=1)).date()
    await conn.execute(
        insert(random_baselines),
        [
            {
                "data_to": data_to,
                "instrument_id": instrument_id,
                "entry": "main",
                "window": window,
                "weekday": weekday,
                "hour": hour,
                "moves": 100,
                "median_move": median,
                "adjusted": 100 if adjusted is not None else 0,
                "median_adjusted": adjusted,
            }
            for weekday in range(7)
            for hour in range(24)
        ],
    )


async def plant_backtest(
    conn: AsyncConnection, picker: str, pair: str, hit: float, days: int
) -> None:
    run_id = (
        await conn.execute(
            insert(backtest_runs)
            .values(
                code_commit="test", gate_sha256="g", rules_sha256="r", ai_picker_sha256="a",
                match_rule_sha256="m", model_version=StubEmbedder.version,
                data_from=AT.date(), data_to=AT.date(), report_sha256="x",
            )
            .returning(backtest_runs.c.id)
        )
    ).scalar_one()  # fmt: skip
    flags = dict.fromkeys(
        ("enough_days", "entry_2min", "above_costs", "beats_random", "last12_holds", "passes"),
        True,
    )
    await conn.execute(
        insert(backtest_summary).values(
            run_id=run_id, picker=picker, view="gate", pair=pair, calls=days, days=days,
            hit_rate=hit, last12_days=days, counts={}, **flags,
        )
    )  # fmt: skip


@dataclass
class LiveRun:
    """The live stages as the signals worker runs them, with what each post produced."""

    db: AsyncEngine
    send_rule: SendRule = field(default_factory=current_send_rule)
    ai: AiPicker | None = None
    wake: Wake = field(default_factory=Wake)
    alerted: dict[str, Alerted] = field(default_factory=dict)
    runner: StageRunner | None = None
    alerter: Alerter | None = None

    async def start(self) -> None:
        """Load the pool as the worker does when it starts (after planting)."""
        embedder = StubEmbedder()
        async with self.db.connect() as conn:
            pool = await LivePool.load(conn, embedder.version)
        rules = current_rules()
        scorer = Scorer(rules, embedder, self.ai, CountsAll())
        self.alerter = Alerter(
            self.send_rule, rules.version, Evidencer(pool, load_match_rule()), embedder.version,
            self.ai, self.wake, self.observe,
        )  # fmt: skip
        stages = [
            Stage(SCORE, scorer.handle),
            Stage(ALERT, self.alerter.handle, self.alerter.after_commit),
        ]
        self.runner = StageRunner(self.db, signals, stages, max_attempts=3)

    def observe(self, alerted: Alerted) -> None:
        self.alerted[alerted.key] = alerted

    async def post(self, *posts: Post) -> list[Alerted]:
        """Store live posts and run the stages until they are done."""
        if self.runner is None:
            await self.start()
        assert self.runner is not None
        async with self.db.begin() as conn:
            await store_posts(conn, await trump_source_id(conn), "trumpstruth", posts)
        while await self.runner.run_once():
            pass
        return [self.alerted[p.key] for p in posts if p.key in self.alerted]


@dataclass
class DryRun:
    """Test-only dry-run delivery: follows the change cursor as an outlet does, waking on
    the wake hook or every `poll` seconds, and records what it read (and when). It sends
    nothing."""

    read: list[Revision] = field(default_factory=list)
    read_at: dict[int, float] = field(default_factory=dict)
    """seq -> perf_counter() when it was read."""
    poll: float | None = None

    def worker(self) -> WorkerFunc:
        async def run(ctx: EngineContext) -> None:
            poll = self.poll or ctx.settings.delivery_poll_seconds
            bookmark, seen = 0, ctx.wake.rung
            while True:
                async with ctx.db.connect() as conn:
                    changes = await read_changes(conn, bookmark)
                for revision in changes.revisions:
                    self.read.append(revision)
                    self.read_at[revision.seq] = time.perf_counter()
                    bookmark = revision.seq
                if not changes.has_more:
                    seen = await ctx.wake.wait(seen, poll)

        return run


def similar_history(
    words: str, days: int, moves: Sequence[float], end: datetime, rng: np.random.Generator
) -> list[tuple[datetime, str, Vector, float]]:
    """Past posts like `words`, one a day for `days` days before `end` at 10:00 New York
    (each its own match day), with the given moves in turn."""
    vector = stub_vector(words)
    found = []
    for day in range(days):
        when = end - timedelta(days=day + 1)
        noisy = vector + rng.normal(0, 0.001, len(vector)).astype(np.float32)
        noisy /= np.linalg.norm(noisy)
        found.append((when, f"{words} ({day})", noisy, moves[day % len(moves)]))
    return found
