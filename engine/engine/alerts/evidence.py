"""Similar-post evidence for live calls, by Gate 0 v1's method (engine/backtest): PR 4's
similar() and match rule v1 over earlier text posts, keeping those whose window had closed
by the alert and that have a judged move in signal_moves, best first, at most 50; then
the backtest's verdict (direction, rules 3 and 4) on their moves against the stored
random-time medians.

The pool of past posts' vectors lives in memory: loaded once when the worker starts, and
each new post is added as the alert stage passes it.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.alerts.model import EXCERPT_CHARS, Evidence, Example, FyiReason
from engine.alerts.send_rule import Picker, SendRule
from engine.backtest import gate
from engine.backtest.data import instrument_infos
from engine.backtest.evaluate import Pick, pair_targets, verdict
from engine.backtest.gate import Pair
from engine.backtest.randomtimes import NEW_YORK
from engine.extract.batch import TEXT_POSTS
from engine.extract.similarity import MatchRule, Similarity, Vector
from engine.market.instruments import Instrument
from engine.tables import (
    backtest_runs,
    backtest_summary,
    random_baselines,
    signal_embeddings,
    signal_moves,
    signals,
)
from engine.text import excerpt, has_words

ENTRY = "main"
"""The entry rule past posts' moves are read at: the alert, post + 2 minutes."""
EXAMPLES = 3


class LivePool:
    """Every text post's vector (posts with words only, as the backtest's sample), in one
    matrix that grows as posts are scored."""

    def __init__(self, similarity: Similarity) -> None:
        self.similarity = similarity
        self.index = {str(key): i for i, key in enumerate(similarity.keys)}

    @classmethod
    async def load(cls, conn: AsyncConnection, model_version: str) -> "LivePool":
        rows = (
            await conn.execute(
                select(
                    signal_embeddings.c.signal_key,
                    signals.c.posted_at,
                    signals.c.text,
                    signal_embeddings.c.vector,
                )
                .join(signals, signals.c.key == signal_embeddings.c.signal_key)
                .where(signal_embeddings.c.model_version == model_version, TEXT_POSTS)
                .order_by(signals.c.posted_at, signal_embeddings.c.signal_key)
            )
        ).all()
        kept = [row for row in rows if has_words(row.text)]
        vectors = [np.frombuffer(row.vector, dtype="<f4") for row in kept]
        matrix = np.stack(vectors) if vectors else np.zeros((0, 1), dtype=np.float32)
        return cls(Similarity([r.signal_key for r in kept], [r.posted_at for r in kept], matrix))

    def __len__(self) -> int:
        return len(self.index)

    def add(self, key: str, posted_at: datetime, vector: Vector) -> None:
        """Add a post once; a retried stage adds nothing more."""
        if key not in self.index:
            self.similarity.add(key, posted_at, vector)
            self.index[key] = len(self.index)

    def scored(
        self, key: str, vector: Vector, before: datetime, threshold: float
    ) -> list[tuple[str, datetime]]:
        """Every post scoring at the threshold or more and made before `before`, best
        first, with its time (the pool is cut to 50 per pair later, as in the backtest)."""
        found = self.similarity.similar(key, vector, before, threshold, k=len(self))
        times = self.similarity.times
        return [(m.key, datetime.fromtimestamp(times[self.index[m.key]], NEW_YORK)) for m in found]


@dataclass(frozen=True)
class Target:
    """One call to make: a pair and the instrument it lands on."""

    pair: Pair
    instrument: Instrument


@dataclass(frozen=True)
class Drafted:
    """A call with its evidence, before the send rule's decision."""

    target: Target
    direction: int
    """+1 up, -1 down, 0 none."""
    blocked: FyiReason | None
    """few_matches (rule 3) or not_better_than_random (rule 4), or None if both hold."""
    evidence: Evidence


@dataclass(frozen=True)
class Post:
    key: str
    posted_at: datetime
    vector: Vector | None
    """None for a post without words: it matches nothing."""


def targets(rule: SendRule, pick: Pick, listed: Mapping[int, Instrument]) -> list[Target]:
    """The calls one pick makes, in the send rule's order (rule 1)."""
    slugs = {i.slug: i.id for i in listed.values()}
    return [
        Target(pair, listed[instrument_id])
        for pair in rule.calls
        for instrument_id in pair_targets(pair, pick, slugs)
    ]


class Evidencer:
    """Builds the calls' evidence for one post: one similarity pass, and one read each of
    the moves, the baselines and the backtest summary for all its calls."""

    def __init__(self, pool: LivePool, match: MatchRule) -> None:
        self.pool = pool
        self.match = match

    async def draft(
        self,
        conn: AsyncConnection,
        post: Post,
        calls: Mapping[Picker, Sequence[Target]],
        listed: Mapping[int, Instrument],
        at: datetime,
    ) -> dict[Picker, list[Drafted]]:
        """Each picker's calls (by picker name) with their evidence, as of `at`."""
        scored = (
            self.pool.scored(post.key, post.vector, at, self.match.threshold)
            if post.vector is not None
            else []
        )
        every = [t for picker_targets in calls.values() for t in picker_targets]
        ids = {t.instrument.id for t in every}
        moves = await _moves(conn, ids, [key for key, _ in scored])
        baselines = await _baselines(conn, ids, post.posted_at)
        backtest = await _backtest(conn)
        pools = {
            (picker, i): self._pool(t, scored, moves, at)
            for picker, picker_targets in calls.items()
            for i, t in enumerate(picker_targets)
        }
        shown = {key for found in pools.values() for key, _, _ in found[:EXAMPLES]}
        posts = await _posts(conn, shown)
        return {
            picker: [
                self._drafted(
                    t, pools[(picker, i)], baselines, backtest.get((picker, t.pair.name)),
                    posts, listed,
                )
                for i, t in enumerate(picker_targets)
            ]
            for picker, picker_targets in calls.items()
        }  # fmt: skip

    def _pool(
        self,
        target: Target,
        scored: Sequence[tuple[str, datetime]],
        moves: Mapping[tuple[int, str], Any],
        at: datetime,
    ) -> list[tuple[str, datetime, Any]]:
        """The pair's matches: scored posts with a judged move whose window closed by
        `at`, best first, at most the match rule's 50."""
        window, instrument = target.pair.window, target.instrument
        net = judged_net(instrument)
        found = []
        for key, posted_at in scored:
            row = moves.get((instrument.id, key))
            if row is None:
                continue
            judged = row[f"adjusted_{window}" if net else f"move_{window}"]
            matured = row[f"matured_{window}"]
            if judged is None or matured is None or matured > at:
                continue
            found.append((key, posted_at, row))
            if len(found) == self.match.max_matches:
                break
        return found

    def _drafted(
        self,
        target: Target,
        found: Sequence[tuple[str, datetime, Any]],
        baselines: Mapping[tuple[int, str], tuple[float | None, float | None]],
        backtest: tuple[float | None, int] | None,
        posts: Mapping[str, Any],
        listed: Mapping[int, Instrument],
    ) -> Drafted:
        window, instrument = target.pair.window, target.instrument
        net = judged_net(instrument)
        raw = np.array([row[f"move_{window}"] for _, _, row in found], dtype=np.float64)
        adjusted = [row[f"adjusted_{window}"] for _, _, row in found]
        judged = np.array(adjusted, dtype=np.float64) if net else raw
        days = np.array([t.date().toordinal() for _, t, _ in found], dtype=np.int64)
        base = baselines.get((instrument.id, window), (None, None))
        baseline = base[1] if net else base[0]
        said = verdict(judged, days, baseline, filters=True)
        match_days = len(set(days.tolist()))
        direction = said.direction
        benchmark = listed[instrument.benchmark_id] if instrument.benchmark_id else None
        known_adjusted = [a for a in adjusted if a is not None]
        evidence = Evidence(
            matches=len(found),
            match_days=match_days,
            share_in_direction=(
                _percent(float((judged * direction > 0).mean())) if direction else None
            ),
            median_move=_percent(float(np.median(raw))) if len(raw) else None,
            median_vs_benchmark=(
                _percent(float(np.median(known_adjusted))) if benchmark and known_adjusted else None
            ),
            benchmark=benchmark.slug if benchmark else None,
            random_median=_percent(baseline) if baseline is not None else None,
            backtest_hit_rate=(
                _percent(backtest[0]) if backtest and backtest[0] is not None else None
            ),
            backtest_days=backtest[1] if backtest else None,
            low_sample=match_days < gate.MIN_MATCH_DAYS,
            text=line(instrument, window, direction, judged, raw, baseline, net, benchmark),
            examples=[
                Example(
                    public_id=posts[key].public_id,
                    posted_at=posted_at,
                    excerpt=excerpt(posts[key].text, EXCERPT_CHARS),
                    move=_percent(row[f"move_{window}"]),
                    vs_benchmark=(
                        _percent(row[f"adjusted_{window}"])
                        if row[f"adjusted_{window}"] is not None
                        else None
                    ),
                )
                for key, posted_at, row in found[:EXAMPLES]
            ],
        )
        return Drafted(target, direction, _blocked(said.reason, match_days), evidence)


def _blocked(reason: str | None, match_days: int) -> FyiReason | None:
    """The verdict's reason as the send rule's: rule 3 (enough match days) comes before
    rule 4 (one way and better than random), so a tie counts against rule 4 only once
    rule 3 holds."""
    if reason is None:
        return None
    if reason in ("no_matches", "few_match_days"):
        return "few_matches"
    if reason == "tie" and match_days < gate.MIN_MATCH_DAYS:
        return "few_matches"
    return "not_better_than_random"


def _percent(fraction: float) -> float:
    return round(fraction * 100, 2)


def judged_net(instrument: Instrument) -> bool:
    """Rule 4 judges a company (and ETH) net of its benchmark, the rest raw."""
    return instrument_infos([instrument])[instrument.id].judged_net


# --- the line ----------------------------------------------------------------------------------

STOCK_WINDOWS = {
    "5m": "within 5 minutes",
    "15m": "within 15 minutes",
    "1h": "within 1 hour",
    "close": "by the close",
    "1d": "by the next day's close",
    "3d": "within 3 trading days",
    "5d": "within 5 trading days",
}
COIN_WINDOWS = {
    "5m": "within 5 minutes",
    "15m": "within 15 minutes",
    "1h": "within 1 hour",
    "4h": "within 4 hours",
    "24h": "within 24 hours",
    "3d": "within 3 days",
    "7d": "within 7 days",
}


def window_words(instrument: Instrument, window: str) -> str:
    return (COIN_WINDOWS if instrument.is_coin else STOCK_WINDOWS)[window]


def signed(percent: float) -> str:
    """-0.4%, +1.2%, 0.0%."""
    rounded = round(percent, 1)
    return "0.0%" if rounded == 0 else f"{rounded:+.1f}%"


def line(
    instrument: Instrument,
    window: str,
    direction: int,
    judged: Any,
    raw: Any,
    baseline: float | None,
    net: bool,
    benchmark: Instrument | None,
) -> str:
    """The evidence in one short line, e.g. "Like 14 past posts: SPY fell after 64% of
    them within 1 hour (median -0.4% vs random 0.0%)"."""
    when = window_words(instrument, window)
    if not len(judged):
        return f"No similar past posts with a known move {when} yet"
    posts = f"Like {len(judged)} past post{'s' if len(judged) != 1 else ''}"
    if not direction:
        return f"{posts}: {instrument.symbol} rose after as many as fell {when}"
    share = float((judged * direction > 0).mean()) * 100
    moved = "rose" if direction > 0 else "fell"
    median = signed(float(np.median(judged)) * 100)
    against = f" net of {benchmark.symbol}" if net and benchmark else ""
    random = f" vs random {signed(baseline * 100)}" if baseline is not None else ""
    return (
        f"{posts}: {instrument.symbol} {moved} after {share:.0f}% of them {when} "
        f"(median {median}{against}{random})"
    )


# --- reads -------------------------------------------------------------------------------------


async def _moves(
    conn: AsyncConnection, instrument_ids: Collection[int], keys: Collection[str]
) -> dict[tuple[int, str], Any]:
    """The past posts' stored moves (main entry) on these instruments."""
    if not instrument_ids or not keys:
        return {}
    rows = await conn.execute(
        select(signal_moves).where(
            signal_moves.c.entry == ENTRY,
            signal_moves.c.instrument_id.in_(sorted(instrument_ids)),
            signal_moves.c.signal_key.in_(sorted(keys)),
        )
    )
    return {(row.instrument_id, row.signal_key): row._mapping for row in rows}


async def _baselines(
    conn: AsyncConnection, instrument_ids: Collection[int], posted_at: datetime
) -> dict[tuple[int, str], tuple[float | None, float | None]]:
    """Each instrument's random-time medians (raw, adjusted) per window for the post's New
    York weekday and hour, from the latest sample built for that instrument."""
    if not instrument_ids:
        return {}
    local = posted_at.astimezone(NEW_YORK)
    rb = random_baselines
    latest = (
        select(rb.c.instrument_id, func.max(rb.c.data_to).label("data_to"))
        .where(rb.c.instrument_id.in_(sorted(instrument_ids)), rb.c.entry == ENTRY)
        .group_by(rb.c.instrument_id)
        .subquery()
    )
    rows = await conn.execute(
        select(rb.c.instrument_id, rb.c.window, rb.c.median_move, rb.c.median_adjusted)
        .join(
            latest,
            (latest.c.instrument_id == rb.c.instrument_id) & (latest.c.data_to == rb.c.data_to),
        )
        .where(rb.c.entry == ENTRY, rb.c.weekday == local.weekday(), rb.c.hour == local.hour)
    )
    return {(r.instrument_id, r.window): (r.median_move, r.median_adjusted) for r in rows}


async def _backtest(conn: AsyncConnection) -> dict[tuple[str, str], tuple[float | None, int]]:
    """The latest backtest run's Gate 0 numbers: (picker, pair) -> (hit rate, days)."""
    run = select(func.max(backtest_runs.c.id)).scalar_subquery()
    rows = await conn.execute(
        select(
            backtest_summary.c.picker,
            backtest_summary.c.pair,
            backtest_summary.c.hit_rate,
            backtest_summary.c.days,
        ).where(backtest_summary.c.run_id == run, backtest_summary.c.view == "gate")
    )
    return {(r.picker, r.pair): (r.hit_rate, r.days) for r in rows}


async def _posts(conn: AsyncConnection, keys: Collection[str]) -> dict[str, Any]:
    if not keys:
        return {}
    rows = await conn.execute(
        select(signals.c.key, signals.c.text, signals.c.public_id).where(
            signals.c.key.in_(sorted(keys))
        )
    )
    return {row.key: row for row in rows}
