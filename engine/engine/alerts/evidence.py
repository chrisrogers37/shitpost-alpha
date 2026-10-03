"""Similar-post evidence for live calls, by Gate 0 v1's method (engine/backtest): PR 4's
similar() and match rule v1 over earlier text posts, keeping those whose window had
matured by the post's alert time and that have a judged move in signal_moves, best first,
at most 50; then the backtest's verdict (direction, rules 3 and 4) on their moves against
the stored random-time medians.

The evidence is as of the post's alert time in Gate 0 v1, the post plus 2 minutes, however
late the stage runs (a post first seen late, a backlog): no match is a post made after it,
and no match's window closed inside the post's own. If the stage runs before then, it is
as of the stage's time. Rules 5 and 6 of the send rule still use the alert's own time.

A stored number the public format can't carry (outside -100% to +300%: a real +357% day
would read as a price) never refuses an alert. Its match still counts, but it is no
example; a median past the range is null, and so is such a random-time median, which rule
4 then counts as missing.

The pool of past posts' vectors lives in memory: the backtest sample's posts (through its
own loader, so they are the same posts), loaded once when the worker starts, and each new
post added as the alert stage passes it.
"""

import dataclasses
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.alerts.model import Evidence, Example, FyiReason
from engine.alerts.public import is_percent, quote
from engine.alerts.send_rule import Picker, SendRule
from engine.backtest import gate
from engine.backtest.data import load_posts, sample_span
from engine.backtest.evaluate import InstrumentInfo, Pick, pair_targets, verdict
from engine.backtest.gate import Pair
from engine.backtest.moves import MAIN
from engine.backtest.randomtimes import NEW_YORK
from engine.extract.similarity import MatchRule, Similarity, Vector
from engine.market.instruments import Instrument
from engine.tables import backtest_runs, backtest_summary, random_baselines, signal_moves, signals

log = logging.getLogger(__name__)

ENTRY = MAIN.name
"""The entry rule past posts' moves are read at: Gate 0 v1's main entry, at the alert time
(the post plus 2 minutes)."""
EXAMPLES = 3
SECTOR_FUNDS = frozenset(gate.SECTOR_TOPICS.values())


def as_of(posted_at: datetime, now: datetime) -> datetime:
    """The time a post's evidence is taken as of: its alert time in Gate 0 v1 (the main
    entry's, the post plus 2 minutes), or `now` if that is earlier."""
    return min(now, posted_at + timedelta(seconds=MAIN.delay_seconds))


class LivePool:
    """The text posts' vectors (posts with words only, as the backtest's sample), in one
    matrix that grows as posts are scored."""

    def __init__(self, similarity: Similarity) -> None:
        self.similarity = similarity
        self.index = {str(key): i for i, key in enumerate(similarity.keys)}

    @classmethod
    async def load(cls, conn: AsyncConnection, model_version: str) -> "LivePool":
        """The backtest sample's posts from its first day through today (and a day more,
        for a post stamped ahead of this host's clock), by the sample's own loader."""
        today = datetime.now(NEW_YORK).date()
        span = sample_span(today + timedelta(days=1))
        _, similarity = await load_posts(conn, span, model_version)
        return cls(similarity)

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
        first, with its time in New York (the pool is cut to 50 per pair later, as in the
        backtest)."""
        found = self.similarity.similar(key, vector, before, threshold, k=len(self))
        times = self.similarity.times
        return [(m.key, datetime.fromtimestamp(times[self.index[m.key]], NEW_YORK)) for m in found]


@dataclass(frozen=True)
class Target:
    """One call to make: a pair and the instrument it lands on."""

    pair: Pair
    instrument: Instrument

    @property
    def named_by_post(self) -> bool:
        """The post brought the instrument in itself (a company it names, or the sector
        fund of its topic), unlike the calls on SPY, QQQ and BTC that any market link
        makes."""
        return self.pair.instrument == "company" or self.pair.instrument in SECTOR_FUNDS


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


@dataclass(frozen=True)
class Matched:
    """A match and its stored move over the call's window, as fractions (0.004 is 0.4%)."""

    key: str
    posted_at: datetime
    """In New York time: its date is the match day."""
    move: float
    adjusted: float | None
    """Net of beta times the benchmark; None without one."""


def targets(rule: SendRule, pick: Pick, listed: Mapping[int, Instrument]) -> list[Target]:
    """The calls one pick makes, in the send rule's order (rule 1)."""
    slugs = {i.slug: i.id for i in listed.values()}
    return [
        Target(pair, listed[instrument_id])
        for pair in rule.calls
        for instrument_id in pair_targets(pair, pick, slugs)
    ]


class Evidencer:
    """Builds the calls' evidence for one post: one similarity pass; one read each of the
    moves, the baselines, the example posts and the backtest summary; and each target's
    numbers once, whichever pickers call it."""

    def __init__(self, pool: LivePool, match: MatchRule) -> None:
        self.pool = pool
        self.match = match
        self._noted: set[str] = set()

    async def draft(
        self,
        conn: AsyncConnection,
        post: Post,
        calls: Mapping[Picker, Sequence[Target]],
        listed: Mapping[int, Instrument],
        now: datetime,
    ) -> dict[Picker, list[Drafted]]:
        """Each picker's calls (by picker name) with their evidence, as of the post's alert
        time (as_of) when the stage runs at `now`."""
        cut = as_of(post.posted_at, now)
        scored = (
            self.pool.scored(post.key, post.vector, cut, self.match.threshold)
            if post.vector is not None
            else []
        )
        wanted = list(dict.fromkeys(t for picker_targets in calls.values() for t in picker_targets))
        ids = {t.instrument.id for t in wanted}
        moves = await _moves(conn, ids, [key for key, _ in scored])
        baselines = await _baselines(conn, ids, post.posted_at)
        nets = {t: judged_net(t.instrument) for t in wanted}
        pools = {t: self._pool(t, nets[t], scored, moves, cut) for t in wanted}
        shown = {t: self._examples(t, pools[t]) for t in wanted}
        posts = await _posts(conn, {m.key for chosen in shown.values() for m in chosen})
        measured = {
            t: self._measure(t, nets[t], pools[t], shown[t], baselines, posts, listed)
            for t in wanted
        }
        backtest = await _backtest(conn)
        return {
            picker: [_with_backtest(measured[t], backtest.get((picker, t.pair.name))) for t in ts]
            for picker, ts in calls.items()
        }

    def _pool(
        self,
        target: Target,
        net: bool,
        scored: Sequence[tuple[str, datetime]],
        moves: Mapping[tuple[int, str], Any],
        cut: datetime,
    ) -> list[Matched]:
        """The pair's matches: scored posts with a judged move whose window had matured by
        `cut`, best first, at most the match rule's 50."""
        window = target.pair.window
        found: list[Matched] = []
        for key, posted_at in scored:
            row = moves.get((target.instrument.id, key))
            if row is None:
                continue
            move, adjusted = row[f"move_{window}"], row[f"adjusted_{window}"]
            matured = row[f"matured_{window}"]
            judged = adjusted if net else move
            if move is None or judged is None or matured is None or matured > cut:
                continue
            found.append(Matched(key, posted_at, move, adjusted))
            if len(found) == self.match.max_matches:
                break
        return found

    def _examples(self, target: Target, found: Sequence[Matched]) -> list[Matched]:
        """The best matches whose moves the public format can carry, at most EXAMPLES; one
        past its range (a real +357% day) is passed over, and noted once."""
        what = f"{target.instrument.symbol} {target.pair.window} after"
        chosen: list[Matched] = []
        for m in found:
            if len(chosen) == EXAMPLES:
                break
            move = self._shown(f"{what} {m.key}", m.move)
            net = self._shown(f"{what} {m.key}, net of its benchmark", m.adjusted)
            if move is not None and (m.adjusted is None or net is not None):
                chosen.append(m)
        return chosen

    def _measure(
        self,
        target: Target,
        net: bool,
        found: Sequence[Matched],
        examples: Sequence[Matched],
        baselines: Mapping[tuple[int, str], tuple[float | None, float | None]],
        posts: Mapping[str, Any],
        listed: Mapping[int, Instrument],
    ) -> Drafted:
        """The call's verdict and evidence, but for the picker's backtest numbers."""
        instrument, what = target.instrument, f"{target.instrument.symbol} {target.pair.window}"
        raw = np.array([m.move for m in found], dtype=np.float64)
        judged = np.array([m.adjusted for m in found], dtype=np.float64) if net else raw
        days = np.array([m.posted_at.date().toordinal() for m in found], dtype=np.int64)
        raw_base, net_base = baselines.get((instrument.id, target.pair.window), (None, None))
        stored = net_base if net else raw_base
        baseline = stored if self._shown(f"{what} random-time median", stored) is not None else None
        said = verdict(judged, days, baseline, filters=True)
        match_days, direction = len(set(days.tolist())), said.direction
        share = float((judged * direction > 0).mean()) if direction else None
        median = float(np.median(judged)) if len(found) else None
        benchmark = listed[instrument.benchmark_id] if instrument.benchmark_id else None
        adjusted = [m.adjusted for m in found if m.adjusted is not None]
        evidence = Evidence(
            matches=len(found),
            match_days=match_days,
            share_in_direction=_public(share),
            median_move=self._shown(f"{what} median", float(np.median(raw))) if len(raw) else None,
            median_vs_benchmark=(
                self._shown(f"{what} median net of its benchmark", float(np.median(adjusted)))
                if benchmark and adjusted
                else None
            ),
            benchmark=benchmark.slug if benchmark else None,
            random_median=_public(baseline),
            backtest_hit_rate=None,
            backtest_days=None,
            low_sample=match_days < gate.MIN_MATCH_DAYS,
            text=line(
                target, len(found), direction, share, median, baseline, benchmark if net else None
            ),
            examples=[_example(m, posts[m.key]) for m in examples],
        )
        return Drafted(target, direction, _blocked(said.reason, match_days), evidence)

    def _shown(self, what: str, fraction: float | None) -> float | None:
        """`fraction` as a public percent; None when it is None or past the percent unit's
        range, which is logged once."""
        shown = _public(fraction)
        if fraction is not None and shown is None:
            message = f"evidence: {what}: {fraction * 100:+.1f}% is past the public range, left out"
            if message not in self._noted:
                self._noted.add(message)
                log.warning(message)
        return shown


def _example(match: Matched, post: Any) -> Example:
    return Example(
        public_id=post.public_id,
        posted_at=match.posted_at,
        excerpt=quote(post.text),
        move=_percent(match.move),
        vs_benchmark=None if match.adjusted is None else _percent(match.adjusted),
    )


def _with_backtest(drafted: Drafted, numbers: tuple[float | None, int] | None) -> Drafted:
    """The call with its picker's Gate 0 numbers for the pair (labelled backtest)."""
    if numbers is None:
        return drafted
    hit_rate, days = numbers
    update = {"backtest_hit_rate": _public(hit_rate), "backtest_days": days}
    return dataclasses.replace(drafted, evidence=drafted.evidence.model_copy(update=update))


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
    """A fraction as a percent with 2 decimals (never -0.0)."""
    return round(fraction * 100, 2) + 0.0


def _public(fraction: float | None) -> float | None:
    """A fraction as a percent the public format carries, or None (None, or past its
    range)."""
    if fraction is None:
        return None
    percent = _percent(fraction)
    return percent if is_percent(percent) else None


def judged_net(instrument: Instrument) -> bool:
    """Rule 4 judges a company (and ETH) net of its benchmark, the rest raw."""
    info = InstrumentInfo(
        instrument.id, instrument.slug, instrument.asset_class, instrument.benchmark_id
    )
    return info.judged_net


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
    target: Target,
    matches: int,
    direction: int,
    share: float | None,
    median: float | None,
    baseline: float | None,
    net_of: Instrument | None,
) -> str:
    """The evidence in one short line, e.g. "Like 14 past posts: SPY fell after 64% of
    them within 1 hour (median -0.4% vs random 0.0%)". The share, the median and the
    random-time median are the judged ones (`net_of` a company's benchmark), as fractions."""
    symbol = target.instrument.symbol
    when = window_words(target.instrument, target.pair.window)
    if not matches:
        return f"No similar past posts with a known move {when} yet"
    posts = f"Like {matches} past post{'s' if matches != 1 else ''}"
    if share is None or median is None:
        return f"{posts}: as many saw {symbol} rise as fall {when}"
    moved = "rose" if direction > 0 else "fell"
    against = f" net of {net_of.symbol}" if net_of else ""
    random = f" vs random {signed(baseline * 100)}" if baseline is not None else ""
    return (
        f"{posts}: {symbol} {moved} after {share * 100:.0f}% of them {when} "
        f"(median {signed(median * 100)}{against}{random})"
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
