"""Gate 0 v1 over a universe of posts, picks and prices: each pair's calls through the send
rule's filters, their statistics, the pass rule, Benjamini-Hochberg, the head-to-head and
the volumes. Pure: everything comes in as arrays and callables, so planted-effect tests
run it on synthetic prices and the real run on the cache and the database alike."""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from functools import cached_property
from typing import Any

import numpy as np
import numpy.typing as npt

from engine.backtest import gate
from engine.backtest.gate import Pair
from engine.backtest.moves import (
    MAIN,
    MIRRORS,
    NONE,
    PREMARKET,
    EntryRule,
    Moves,
    PriceData,
    Sessions,
    Status,
    adjusted,
    compute_moves,
    rolling_beta,
)
from engine.backtest.randomtimes import RandomTimes
from engine.backtest.stats import Days, benjamini_hochberg, days_needed, resampled_p, wilson
from engine.extract.similarity import Similarity

Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]
Statuses = npt.NDArray[np.int8]


@dataclass(frozen=True)
class InstrumentInfo:
    id: int
    slug: str
    asset_class: str
    benchmark_id: int | None

    @property
    def kind(self) -> str:
        return "coin" if self.asset_class == "coin" else "stock"

    @property
    def judged_net(self) -> bool:
        """A company (and ETH) is judged net of beta times its benchmark; SPY, QQQ, BTC
        and the sector fund on their raw move."""
        return self.benchmark_id is not None and self.asset_class in ("stock", "coin")


@dataclass(frozen=True)
class Posts:
    """The sample's text posts, oldest first."""

    keys: Sequence[str]
    seconds: Floats
    """Each post's time, seconds since the epoch."""
    days: Ints
    """Each post's New York date, as an ordinal."""
    buckets: Ints
    """Each post's New York weekday * 24 + hour."""

    def __len__(self) -> int:
        return len(self.keys)

    def alert(self, rule: EntryRule) -> Floats:
        result: Floats = self.seconds + rule.delay_seconds
        return result


@dataclass(frozen=True)
class Pick:
    """What one picker said about one post."""

    market_link: bool
    companies: frozenset[int] = frozenset()
    """Counted instruments of asset class stock."""
    topic: str | None = None


@dataclass(frozen=True)
class Picker:
    name: str
    picks: Mapping[int, Pick]
    """By post index: only the posts this picker answered."""
    since: date
    """The first New York date of its sample (the AI picker's window start)."""


@dataclass(frozen=True)
class Judged:
    """One instrument, entry rule and window, for every post: the judged move (NaN when
    there is none), when it matured (NONE when unknown) and its status."""

    move: Floats
    matured: Ints
    status: Statuses


Baseline = Callable[[int, str, str, int], float | None]
"""(instrument id, entry rule, window, bucket) -> the judged random-time median."""


class MoveBook:
    """Every post's moves, and random-time moves for the posts that may call, computed on
    demand from each instrument's prices and kept."""

    def __init__(
        self,
        sessions: Sessions,
        instruments: Mapping[int, InstrumentInfo],
        prices: Callable[[int], PriceData],
        posts: Posts,
        randoms: RandomTimes,
        cutoff: int,
    ) -> None:
        self.sessions = sessions
        self.instruments = instruments
        self._prices = prices
        self.posts = posts
        self.randoms = randoms
        self.cutoff = cutoff
        self._beta: dict[int, Floats] = {}
        self._moves: dict[tuple[int, str], Moves] = {}
        self._judged: dict[tuple[int, str], tuple[dict[str, Floats], dict[str, Statuses]]] = {}
        self._random_rows: dict[int, Floats] = {}
        self._random: dict[tuple[int, str, str], dict[int, Floats]] = {}

    def prices(self, instrument_id: int) -> PriceData:
        return self._prices(instrument_id)

    def beta(self, instrument_id: int) -> Floats:
        if instrument_id not in self._beta:
            info = self.instruments[instrument_id]
            assert info.benchmark_id is not None
            own, other = self.prices(instrument_id), self.prices(info.benchmark_id)
            self._beta[instrument_id] = rolling_beta(*_aligned(own, other))
        return self._beta[instrument_id]

    def forget(self, instrument_id: int) -> None:
        """Drop what is kept for an instrument (its prices are the caller's)."""
        self._beta.pop(instrument_id, None)
        for key in [k for k in self._moves if k[0] == instrument_id]:
            del self._moves[key], self._judged[key]
        for each in [k for k in self._random if k[0] == instrument_id]:
            del self._random[each]

    def moves_at(self, instrument_id: int, times: Floats, rule: EntryRule) -> Moves:
        return compute_moves(self.prices(instrument_id), self.sessions, times, rule, self.cutoff)

    def judged_at(
        self, instrument_id: int, times: Floats, rule: EntryRule
    ) -> tuple[Moves, dict[str, Floats], dict[str, Statuses]]:
        """Moves at `times`, and the judged move and status per window."""
        info = self.instruments[instrument_id]
        moves = self.moves_at(instrument_id, times, rule)
        if not info.judged_net or info.benchmark_id is None:
            return moves, moves.move, moves.status
        benchmark = self.moves_at(info.benchmark_id, times, rule)
        net, status = adjusted(moves, benchmark, self.beta(instrument_id))
        return moves, net, status

    def post_moves(self, instrument_id: int, rule: EntryRule) -> Moves:
        self._post(instrument_id, rule)
        return self._moves[(instrument_id, rule.name)]

    def _post(self, instrument_id: int, rule: EntryRule) -> None:
        key = (instrument_id, rule.name)
        if key not in self._moves:
            moves, net, status = self.judged_at(instrument_id, self.posts.seconds, rule)
            self._moves[key] = moves
            self._judged[key] = (net, status)

    def judged(self, instrument_id: int, rule: EntryRule, window: str) -> Judged:
        self._post(instrument_id, rule)
        moves = self._moves[(instrument_id, rule.name)]
        net, status = self._judged[(instrument_id, rule.name)]
        return Judged(net[window], moves.matured[window], status[window])

    def random_rows(self, posts: Iterable[int]) -> None:
        """Draw the random times of these posts (each post's draw is its own)."""
        for p in posts:
            if p not in self._random_rows:
                key, b = self.posts.keys[p], int(self.posts.buckets[p])
                self._random_rows[p] = self.randoms.draw(key, b)

    def random_judged(
        self, instrument_id: int, rule: EntryRule, window: str, posts: Sequence[int]
    ) -> Floats:
        """One row of judged random-time moves per post (NaN where none)."""
        cache = self._random.setdefault((instrument_id, rule.name, window), {})
        missing = [p for p in dict.fromkeys(posts) if p not in cache]
        if missing:
            self.random_rows(missing)
            rows = np.stack([self._random_rows[p] for p in missing])
            _, net, _ = self.judged_at(instrument_id, rows.ravel(), rule)
            for p, row in zip(missing, net[window].reshape(rows.shape), strict=True):
                cache[p] = row
        if not posts:
            return np.zeros((0, self.randoms.per_post))
        return np.stack([cache[p] for p in posts])


def _aligned(own: PriceData, other: PriceData) -> tuple[Floats, Floats]:
    """Two instruments' daily closes on one axis (sessions for stocks, UTC days for
    coins: a coin's benchmark is a coin)."""
    if own.kind == "stock":
        return own.daily, other.daily
    start = min(own.day_base, other.day_base)
    end = max(own.day_base + len(own.daily), other.day_base + len(other.daily))

    def place(prices: PriceData) -> Floats:
        result = np.full(end - start, np.nan)
        result[prices.day_base - start : prices.day_base - start + len(prices.daily)] = prices.daily
        return result

    shift = own.day_base - start
    return place(own)[shift:], place(other)[shift:]


# --- the calls -------------------------------------------------------------------------


def pair_targets(pair: Pair, pick: Pick, slugs: Mapping[str, int]) -> list[int]:
    """The instruments one pick is called on for `pair` (send rule v1's rule 1): each
    company it counted; the sector fund when its topic maps there; else the pair's
    instrument, when it makes a market link. Shared with live alerts."""
    sector = {slug: topic for topic, slug in gate.SECTOR_TOPICS.items()}
    if pair.instrument == "company":
        return sorted(pick.companies)
    if pair.instrument in sector:
        return [slugs[pair.instrument]] if pick.topic == sector[pair.instrument] else []
    return [slugs[pair.instrument]] if pick.market_link else []


@dataclass(frozen=True)
class Call:
    post: int
    instrument_id: int
    direction: int
    """+1 up, -1 down."""


STATUS_COUNTS = {
    Status.NOT_YET: "not_yet",
    Status.NO_ENTRY: "no_entry",
    Status.LATE_ENTRY: "coin_no_entry_bar",
    Status.PAST_CLOSE: "past_close",
    Status.NO_EXIT: "no_exit_bar",
    Status.NO_CLOSE: "no_close",
    Status.NO_BETA: "no_beta",
    Status.NO_BENCHMARK: "no_benchmark_move",
    Status.NOT_PREMARKET: "not_premarket",
}


class Matcher:
    """Each post's matches, through PR 4's similar() and match rule v1. The pool for a
    pair is every earlier post whose window had matured by this post's alert time and has
    a judged move."""

    def __init__(self, similarity: Similarity, posts: Posts, threshold: float, most: int) -> None:
        self.similarity = similarity
        self.posts = posts
        self.threshold = threshold
        self.most = most
        if list(similarity.keys) != list(posts.keys):
            raise ValueError("the similarity matrix must hold the sample's posts, in order")
        self.index = {key: i for i, key in enumerate(posts.keys)}
        self._found: dict[tuple[int, int], Ints] = {}

    def scored(self, post: int, rule: EntryRule) -> Ints:
        """Every post scoring at the threshold or more and made before this post's alert
        time, best first (post indices)."""
        found_key = (post, rule.delay_seconds)
        if found_key not in self._found:
            key = self.posts.keys[post]
            before = datetime.fromtimestamp(self.posts.seconds[post] + rule.delay_seconds, UTC)
            vector = self.similarity.vectors[self.index[key]]
            everyone = len(self.similarity.keys)
            matches = self.similarity.similar(key, vector, before, self.threshold, k=everyone)
            self._found[found_key] = np.array([self.index[m.key] for m in matches], dtype=np.int64)
        return self._found[found_key]

    def matches(self, post: int, rule: EntryRule, judged: Judged) -> Ints:
        """The match rule's matches from the pair's pool, best first."""
        scored = self.scored(post, rule)
        alert_minute = (self.posts.seconds[post] + rule.delay_seconds) / 60
        matured = judged.matured[scored]
        pool = np.isfinite(judged.move[scored]) & (matured != NONE) & (matured <= alert_minute)
        result: Ints = scored[pool][: self.most]
        return result


@dataclass(frozen=True)
class Verdict:
    direction: int
    reason: str | None
    """Why there is no call, or why the filters dropped it."""


def call_for(
    matches: Ints, judged: Judged, posts: Posts, baseline: float | None, filters: bool
) -> Verdict:
    """The direction most matches moved and, with `filters`, send rule v1's rules 3 and 4."""
    return verdict(judged.move[matches], posts.days[matches], baseline, filters)


def verdict(moves: Floats, days: Ints, baseline: float | None, filters: bool) -> Verdict:
    """call_for's rule on the matches' judged moves and their New York dates: the one
    method the backtest and live alerts (engine/alerts/evidence.py) share."""
    if not len(moves):
        return Verdict(0, "no_matches")
    up, down = int((moves > 0).sum()), int((moves < 0).sum())
    if up == down:
        return Verdict(0, "tie")
    direction = 1 if up > down else -1
    if not filters:
        return Verdict(direction, None)
    if len(np.unique(days)) < gate.MIN_MATCH_DAYS:
        return Verdict(direction, "few_match_days")
    if max(up, down) / len(moves) < gate.ONE_WAY:
        return Verdict(direction, "not_one_way")
    if baseline is None:
        return Verdict(direction, "no_baseline")
    if not direction * (float(np.median(moves)) - baseline) > gate.BEAT_RANDOM:
        return Verdict(direction, "not_better_than_random")
    return Verdict(direction, None)


def no_bursts(calls: Sequence[Call], alerts: Floats) -> tuple[list[Call], int]:
    """Send rule v1's rule 6: at most one call per instrument per 30 minutes. Returns the
    calls kept and how many were dropped."""
    kept: list[Call] = []
    last: dict[int, float] = {}
    for call in sorted(calls, key=lambda c: (alerts[c.post], c.instrument_id)):
        at = float(alerts[call.post])
        previous = last.get(call.instrument_id)
        if previous is not None and at - previous < gate.BURST_SECONDS:
            continue
        last[call.instrument_id] = at
        kept.append(call)
    return kept, len(calls) - len(kept)


# --- the tests -------------------------------------------------------------------------


@dataclass(frozen=True)
class View:
    name: str
    rule: EntryRule
    filters: bool = True
    judged: bool = False
    """One of the 22 gate tests (BH and the pass rule apply)."""
    posts: frozenset[int] | None = None
    """Only calls on these posts (None: all the picker answered)."""
    drop_days: frozenset[int] = frozenset()
    """UTC day numbers: a call whose entry or exit falls on one is left out."""


@dataclass
class PairResult:
    picker: str
    view: str
    pair: Pair
    calls: int = 0
    days: int = 0
    mean_5bp: float | None = None
    mean_20bp: float | None = None
    total_20bp: float = 0.0
    hit_rate: float | None = None
    hit_low: float | None = None
    hit_high: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    last12_mean: float | None = None
    last12_days: int = 0
    enough_days: bool = False
    entry_2min: bool = False
    above_costs: bool = False
    beats_random: bool = False
    last12_holds: bool = False
    passes: bool = False
    counts: Counter[str] = field(default_factory=Counter)
    sent_posts: set[int] = field(default_factory=set)
    """Posts with a call that passed the filters (sent), measurable or not."""

    def finish(self, judged: bool) -> None:
        """The pass rule's five conditions (judged tests only for q and passes)."""
        self.enough_days = self.days >= gate.MIN_DAYS
        self.above_costs = self.mean_20bp is not None and self.mean_20bp > 0
        self.last12_holds = (
            self.last12_days >= gate.LAST_MIN_DAYS
            and self.last12_mean is not None
            and self.last12_mean > 0
        )
        self.beats_random = judged and self.q_value is not None and self.q_value < gate.MAX_Q
        self.passes = judged and all(
            (self.enough_days, self.entry_2min, self.above_costs, self.beats_random,
             self.last12_holds)
        )  # fmt: skip


@dataclass
class Universe:
    posts: Posts
    instruments: Mapping[int, InstrumentInfo]
    book: MoveBook
    matcher: Matcher
    baseline: Baseline
    pickers: Mapping[str, Picker]
    data_from: date
    data_to: date

    @cached_property
    def slugs(self) -> dict[str, int]:
        return {info.slug: info.id for info in self.instruments.values()}

    def candidates(self, picker: Picker, pair: Pair, view: View) -> list[tuple[int, int]]:
        """(post, instrument) the picker's rule 1 lets through for this pair."""
        found: list[tuple[int, int]] = []
        for post, pick in sorted(picker.picks.items()):
            if view.posts is None or post in view.posts:
                found += [(post, target) for target in pair_targets(pair, pick, self.slugs)]
        return found

    def test(self, picker: Picker, view: View, pair: Pair, seed_name: str) -> PairResult:
        result = PairResult(picker.name, view.name, pair)
        result.entry_2min = view.rule == MAIN
        rule, alerts = view.rule, self.posts.alert(view.rule)
        sent: list[Call] = []
        for post, instrument in self.candidates(picker, pair, view):
            judged = self.book.judged(instrument, rule, pair.window)
            if rule.premarket and judged.status[post] == Status.NOT_PREMARKET:
                continue
            matches = self.matcher.matches(post, rule, judged)
            baseline = self.baseline(
                instrument, rule.name, pair.window, int(self.posts.buckets[post])
            )
            verdict = call_for(matches, judged, self.posts, baseline, view.filters)
            if verdict.reason is not None:
                result.counts[verdict.reason] += 1
            else:
                sent.append(Call(post, instrument, verdict.direction))
        if view.filters:
            sent, dropped = no_bursts(sent, alerts)
            result.counts["burst"] += dropped
        result.sent_posts = {call.post for call in sent}

        measured: list[Call] = []
        for call in sent:
            judged = self.book.judged(call.instrument_id, rule, pair.window)
            if np.isnan(judged.move[call.post]):
                result.counts[STATUS_COUNTS[Status(judged.status[call.post])]] += 1
            elif view.drop_days and self._on_dropped_day(call, rule, pair.window, view):
                result.counts["divergent_day"] += 1
            else:
                measured.append(call)
        randoms = self._random_rows(measured, rule, pair.window)
        usable = [i for i, row in enumerate(randoms) if np.isfinite(row).any()]
        result.counts["no_random_moves"] += len(measured) - len(usable)
        measured = [measured[i] for i in usable]
        self._statistics(result, measured, randoms[usable], rule, pair.window, seed_name)
        result.finish(view.judged)
        return result

    def _on_dropped_day(self, call: Call, rule: EntryRule, window: str, view: View) -> bool:
        moves = self.book.post_moves(call.instrument_id, rule)
        entry = int(moves.entered[call.post]) // 1440
        exit_ = int(moves.matured[window][call.post]) // 1440
        return entry in view.drop_days or exit_ in view.drop_days

    def _random_rows(self, calls: Sequence[Call], rule: EntryRule, window: str) -> Floats:
        rows = np.zeros((len(calls), self.book.randoms.per_post))
        by_instrument: dict[int, list[int]] = {}
        for i, call in enumerate(calls):
            by_instrument.setdefault(call.instrument_id, []).append(i)
        for instrument, where in by_instrument.items():
            posts = [calls[i].post for i in where]
            rows[where] = self.book.random_judged(instrument, rule, window, posts)
        return rows

    def _statistics(
        self,
        result: PairResult,
        calls: Sequence[Call],
        randoms: Floats,
        rule: EntryRule,
        window: str,
        seed_name: str,
    ) -> None:
        result.calls = len(calls)
        if not calls:
            result.p_value = 1.0
            return
        posts = np.array([c.post for c in calls], dtype=np.int64)
        directions = np.array([c.direction for c in calls], dtype=np.float64)
        gross = np.array(
            [
                self.book.judged(c.instrument_id, rule, window).move[c.post] * c.direction
                for c in calls
            ]
        )
        days = Days.of(self.posts.days[posts])
        result.days = len(days)
        by_day = days.values(gross)
        result.mean_5bp = float(by_day.mean() - gate.LOW_COST)
        result.mean_20bp = float(by_day.mean() - gate.GATE_COST)
        result.total_20bp = float((by_day - gate.GATE_COST).sum())
        hits = int((by_day > 0).sum())
        result.hit_rate = hits / len(days)
        interval = wilson(hits, len(days))
        if interval is not None:
            result.hit_low, result.hit_high = interval
        recent = days.days > (self.data_to - timedelta(days=gate.LAST_DAYS)).toordinal()
        result.last12_days = int(recent.sum())
        if result.last12_days:
            result.last12_mean = float(by_day[recent].mean() - gate.GATE_COST)
        result.p_value = resampled_p(
            days,
            directions,
            randoms,
            float((by_day - gate.GATE_COST).mean()),
            gate.GATE_COST,
            gate.seed("p-value", seed_name),
        )


# --- the whole backtest ------------------------------------------------------------------


@dataclass
class Outcome:
    results: list[PairResult]
    passes: bool
    picks: str
    """The picker that picks: "rules" or "ai"."""
    totals: dict[str, float]
    """The head-to-head: each picker's total net move across its passing pairs, on the
    posts both were tested on."""
    shared_posts: int
    sends: dict[str, Any]
    samples: list[dict[str, Any]]

    def gate(self) -> list[PairResult]:
        return [r for r in self.results if r.view == "gate" and r.picker in ("rules", "ai")]


def views_for(
    universe: Universe, shared: frozenset[int], drop_days: frozenset[int]
) -> list[tuple[str, View, Sequence[Pair]]]:
    """Every (picker, view, pairs) the report shows, gate tests first."""
    planned: list[tuple[str, View, Sequence[Pair]]] = []
    gate_view = View("gate", MAIN, judged=True)
    for name in ("rules", "ai"):
        if name in universe.pickers:
            planned.append((name, gate_view, gate.GATE_PAIRS))
    if "ai" in universe.pickers:
        planned.append(("rules", View("shared", MAIN, posts=shared), gate.GATE_PAIRS))
    for name in ("rules", "ai"):
        if name not in universe.pickers:
            continue
        planned += [
            (name, View("mirrors", MIRRORS), gate.GATE_PAIRS),
            (name, View("all_posts", MAIN, filters=False), gate.GATE_PAIRS),
            (name, View("premarket", PREMARKET), gate.PREMARKET_PAIRS),
            (name, View("secondary", MAIN), (*gate.ETH_PAIRS, *gate.MINUTE_PAIRS)),
        ]
        if drop_days:
            btc = [p for p in gate.GATE_PAIRS if p.instrument == "btc"]
            planned.append((name, View("btc_no_divergent", MAIN, drop_days=drop_days), btc))
    if "rules" in universe.pickers:
        planned.append(("rules", View("secondary", MAIN), gate.SECTOR_PAIRS))
    for name in universe.pickers:
        if name.startswith("ai:"):
            planned.append((name, View("model", MAIN), gate.GATE_PAIRS))
    return planned


def run_backtest(universe: Universe, drop_days: frozenset[int] = frozenset()) -> Outcome:
    """Every test, the pass rule, the head-to-head and the volumes."""
    ai = universe.pickers.get("ai")
    shared = frozenset(ai.picks) & frozenset(universe.pickers["rules"].picks) if ai else frozenset()
    results: list[PairResult] = []
    for picker_name, view, pairs in views_for(universe, shared, drop_days):
        picker = universe.pickers[picker_name]
        for pair in pairs:
            seed_name = f"{picker_name}/{view.name}/{pair.name}"
            results.append(universe.test(picker, view, pair, seed_name))
    judged = [r for r in results if r.view == "gate"]
    for result, q in zip(
        judged, benjamini_hochberg([r.p_value or 1.0 for r in judged]), strict=True
    ):
        result.q_value = q
        result.finish(judged=True)

    def passing(name: str) -> list[PairResult]:
        return [r for r in judged if r.picker == name and r.passes]

    totals = {"ai": sum(r.total_20bp for r in passing("ai"))}
    rules_passing = {r.pair for r in passing("rules")}
    totals["rules"] = sum(
        r.total_20bp for r in results if r.view == "shared" and r.pair in rules_passing
    )
    picks = "ai" if passing("ai") and totals["ai"] > totals["rules"] else "rules"
    sent = set().union(*(r.sent_posts for r in passing(picks)))
    years = ((universe.data_to - universe.pickers[picks].since).days + 1) / 365.25
    sends = {
        "picker": picks,
        "posts": len(sent),
        "per_year": len(sent) / years if years > 0 else 0.0,
    }
    samples = [
        {
            "picker": r.picker,
            "pair": r.pair.name,
            "hit_rate": r.hit_rate,
            "days": days_needed(r.hit_rate or 0.0),
        }
        for r in judged
        if r.passes
    ]
    return Outcome(
        results,
        passes=any(r.passes for r in judged),
        picks=picks,
        totals=totals,
        shared_posts=len(shared),
        sends=sends,
        samples=samples,
    )
