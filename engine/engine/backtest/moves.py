"""Entries, windows and moves (Gate 0 v1), for many times at once.

Times are seconds since the epoch for posts and their random times, and whole minutes
since the epoch for bars, sessions and exits. A move is exit over entry minus 1; nothing
here returns a price.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Literal

import numpy as np
import numpy.typing as npt

from engine.backtest import gate
from engine.market.bars import MinuteSeries
from engine.market.calendar import schedule

Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]
Kind = Literal["stock", "coin"]

STOCK_WINDOWS: dict[str, int] = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "close": 0,
    "1d": 1,
    "3d": 3,
    "5d": 5,
}
"""Minutes for the minute windows; sessions after the close's session for the day windows."""
COIN_WINDOWS: dict[str, int] = {
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "24h": 1440,
    "3d": 3 * 1440,
    "7d": 7 * 1440,
}
DAY_MINUTES = 1440
NONE = -1
"""An entry or exit time that doesn't exist."""


class Status(IntEnum):
    """Why a window has no move (OK when it has one)."""

    OK = 0
    NOT_YET = 1
    """It ends after the data does."""
    NO_ENTRY = 2
    LATE_ENTRY = 3
    """A coin's first bar starts more than 5 minutes after the alert time."""
    PAST_CLOSE = 4
    NO_EXIT = 5
    NO_CLOSE = 6
    """No official close for the exit's session."""
    NO_BETA = 7
    NO_BENCHMARK = 8
    NOT_PREMARKET = 9
    """The pre-market rule doesn't apply: the alert isn't 04:00 to 09:30 on a trading day."""


@dataclass(frozen=True)
class EntryRule:
    name: Literal["main", "premarket", "mirrors"]
    delay_seconds: int
    premarket: bool = False


MAIN = EntryRule("main", gate.ALERT_DELAY_SECONDS)
PREMARKET = EntryRule("premarket", gate.ALERT_DELAY_SECONDS, premarket=True)
MIRRORS = EntryRule("mirrors", gate.MIRRORS_DELAY_SECONDS)
RULES = {rule.name: rule for rule in (MAIN, PREMARKET, MIRRORS)}


@dataclass(frozen=True)
class Sessions:
    """The trading calendar as arrays: each session's date (an ordinal), open and close."""

    days: Ints
    opens: Ints
    closes: Ints

    @classmethod
    def between(cls, first: date, last: date) -> "Sessions":
        rows = schedule(first, last)
        return cls(
            np.array([day.toordinal() for day, _, _ in rows], dtype=np.int64),
            np.array([int(o.timestamp()) // 60 for _, o, _ in rows], dtype=np.int64),
            np.array([int(c.timestamp()) // 60 for _, _, c in rows], dtype=np.int64),
        )

    def __len__(self) -> int:
        return len(self.days)

    def trading_at_or_after(self, minutes: Ints) -> Ints:
        """The session trading at each minute, or the next one: the first to close after
        it (len(self) past the end)."""
        found: Ints = np.searchsorted(self.closes, minutes, side="right").astype(np.int64)
        return found

    def index_of(self, ordinals: Ints) -> Ints:
        """Each date's session index, NONE for a day without one."""
        at = np.searchsorted(self.days, ordinals).astype(np.int64)
        inside = at < len(self.days)
        hit = inside & (self.days[np.minimum(at, len(self.days) - 1)] == ordinals)
        result: Ints = np.where(hit, at, NONE)
        return result


@dataclass(frozen=True)
class PriceData:
    """One instrument's prices for the backtest.

    bars: every bar for a coin; regular-session bars for a stock or ETF. extended: SPY's
    and QQQ's bars with extended hours, for the pre-market entry. daily: official closes,
    one per session for a stock or ETF, one per UTC day from `day_base` for a coin, NaN
    where there is none (or before the instrument's names hold)."""

    kind: Kind
    bars: MinuteSeries
    daily: Floats
    extended: MinuteSeries | None = None
    day_base: int = 0


def price_at(series: MinuteSeries, minutes: Ints) -> Floats:
    """The price at each minute: the open of the bar starting then, else the close of the
    last bar starting in the 5 minutes before, else NaN."""
    n = len(series.minutes)
    if n == 0:
        return np.full(len(minutes), np.nan)
    at = np.searchsorted(series.minutes, minutes)
    here = np.minimum(at, n - 1)
    exact = (at < n) & (series.minutes[here] == minutes)
    before = np.maximum(at - 1, 0)
    recent = (at > 0) & (series.minutes[before] >= minutes - gate.LOOK_BACK_MINUTES)
    result: Floats = np.where(
        exact, series.opens[here], np.where(recent, series.closes[before], np.nan)
    )
    return result


@dataclass
class Moves:
    """Each time's entry and, per window, its move, when it matured and its status."""

    entered: Ints
    position: Ints
    """Where the entry falls on the daily axis (session index, or UTC day from day_base),
    for beta; NONE without an entry."""
    move: dict[str, Floats] = field(default_factory=dict)
    matured: dict[str, Ints] = field(default_factory=dict)
    status: dict[str, npt.NDArray[np.int8]] = field(default_factory=dict)

    def put(self, window: str, move: Floats, matured: Ints, status: npt.NDArray[np.int8]) -> None:
        ok = status == Status.OK
        self.move[window] = np.where(ok, move, np.nan)
        keep = (status != Status.NOT_YET) & (status != Status.NO_ENTRY)
        keep &= status != Status.NOT_PREMARKET
        self.matured[window] = np.where(keep, matured, NONE)
        self.status[window] = status


def _status(*conditions: tuple[npt.NDArray[np.bool_], Status], size: int) -> npt.NDArray[np.int8]:
    """The first condition that holds gives each time's status (OK if none does)."""
    result = np.full(size, Status.OK, dtype=np.int8)
    unset = np.ones(size, dtype=np.bool_)
    for holds, status in conditions:
        mark = holds & unset
        result[mark] = status
        unset &= ~holds
    return result


def ceil_minutes(seconds: Floats) -> Ints:
    result: Ints = np.ceil(seconds / 60).astype(np.int64)
    return result


def stock_moves(
    prices: PriceData, sessions: Sessions, times: Floats, rule: EntryRule, cutoff: int
) -> Moves:
    """Moves for a stock or ETF at each post (or random) time in seconds. `cutoff` is the
    last minute of data: an entry or window after it is NOT_YET."""
    size = len(times)
    alert = times + rule.delay_seconds
    alert_minute = ceil_minutes(alert)
    s = sessions.trading_at_or_after(alert_minute)
    s_safe = np.minimum(s, len(sessions) - 1)
    opens, closes = sessions.opens[s_safe], sessions.closes[s_safe]
    later = (s >= len(sessions)) | (opens > cutoff)  # the entry's session isn't in the data
    if rule.premarket:
        series = prices.extended if prices.extended is not None else MinuteSeries.of([])
        applies = ~later & (alert >= (opens - gate.PREMARKET_MINUTES) * 60) & (alert < opens * 60)
        start = alert_minute
    else:
        series = prices.bars
        applies = ~later
        start = np.maximum(alert_minute, opens)
    n = len(series.minutes)
    at = np.searchsorted(series.minutes, start) if n else np.zeros(size, dtype=np.int64)
    here = np.minimum(at, max(n - 1, 0))
    entered = series.minutes[here] if n else np.zeros(size, dtype=np.int64)
    has_entry = applies & (at < n) & (entered < closes)
    entry_price = series.opens[here] if n else np.full(size, np.nan)
    no_entry = applies & ~has_entry
    moves = Moves(np.where(has_entry, entered, NONE), np.where(has_entry, s_safe, NONE))
    before = (
        (later, Status.NOT_YET),
        (~applies, Status.NOT_PREMARKET),
        (no_entry, Status.NO_ENTRY),
    )

    for window, minutes in STOCK_WINDOWS.items():
        if window in ("5m", "15m", "1h"):
            exit_at = entered + minutes
            price = price_at(series, exit_at)
            status = _status(
                *before,
                (exit_at > closes, Status.PAST_CLOSE),
                (exit_at > cutoff, Status.NOT_YET),
                (np.isnan(price), Status.NO_EXIT),
                size=size,
            )
        else:
            close_session = np.where(
                closes - entered >= gate.CLOSE_AT_LEAST_MINUTES, s_safe, s_safe + 1
            )
            target = close_session + minutes
            target_safe = np.minimum(target, len(sessions) - 1)
            exit_at = sessions.closes[target_safe]
            price = prices.daily[target_safe] if len(prices.daily) else np.full(size, np.nan)
            status = _status(
                *before,
                ((target >= len(sessions)) | (exit_at > cutoff), Status.NOT_YET),
                (np.isnan(price), Status.NO_CLOSE),
                size=size,
            )
        with np.errstate(divide="ignore", invalid="ignore"):
            move = price / entry_price - 1
        moves.put(window, move, exit_at, status)
    return moves


def coin_moves(prices: PriceData, times: Floats, rule: EntryRule, cutoff: int) -> Moves:
    """Moves for a coin at each time in seconds."""
    size = len(times)
    alert = times + rule.delay_seconds
    series = prices.bars
    n = len(series.minutes)
    at = np.searchsorted(series.minutes, ceil_minutes(alert)) if n else np.zeros(size, np.int64)
    here = np.minimum(at, max(n - 1, 0))
    entered = series.minutes[here] if n else np.zeros(size, dtype=np.int64)
    pending = ceil_minutes(alert) > cutoff
    found = at < n
    late = found & (entered * 60 - alert > gate.COIN_ENTRY_SECONDS)
    has_entry = found & ~late
    entry_price = series.opens[here] if n else np.full(size, np.nan)
    moves = Moves(
        np.where(has_entry, entered, NONE),
        np.where(has_entry, entered // DAY_MINUTES - prices.day_base, NONE),
    )
    for window, minutes in COIN_WINDOWS.items():
        exit_at = entered + minutes
        price = price_at(series, exit_at)
        status = _status(
            (pending, Status.NOT_YET),
            (~found, Status.NO_ENTRY),
            (late, Status.LATE_ENTRY),
            (exit_at > cutoff, Status.NOT_YET),
            (np.isnan(price), Status.NO_EXIT),
            size=size,
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            move = price / entry_price - 1
        moves.put(window, move, exit_at, status)
    return moves


def compute_moves(
    prices: PriceData, sessions: Sessions, times: Floats, rule: EntryRule, cutoff: int
) -> Moves:
    if prices.kind == "coin":
        return coin_moves(prices, times, rule, cutoff)
    return stock_moves(prices, sessions, times, rule, cutoff)


def rolling_beta(closes: Floats, benchmark: Floats) -> Floats:
    """At each position on a daily axis, the slope of the instrument's daily returns on
    the benchmark's over the BETA_SESSIONS positions before it (where both have a
    return), or NaN with fewer than BETA_MIN_RETURNS of them."""
    size = len(closes)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.concatenate([[np.nan], closes[1:] / closes[:-1] - 1]) if size else closes
        y = np.concatenate([[np.nan], benchmark[1:] / benchmark[:-1] - 1]) if size else closes
    ok = np.isfinite(x) & np.isfinite(y)

    def sums(values: Floats) -> Floats:
        total = np.concatenate([[0.0], np.cumsum(np.where(ok, values, 0.0))])
        position = np.arange(size)
        start = np.maximum(position - gate.BETA_SESSIONS, 0)
        result: Floats = total[position] - total[start]
        return result

    n = sums(np.ones(size))
    sx, sy, sxy, syy = sums(x), sums(y), sums(x * y), sums(y * y)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta: Floats = (n * sxy - sx * sy) / (n * syy - sy * sy)
    return np.where((n >= gate.BETA_MIN_RETURNS) & np.isfinite(beta), beta, np.nan)


def adjusted(
    moves: Moves, benchmark: Moves, beta: Floats
) -> tuple[dict[str, Floats], dict[str, npt.NDArray[np.int8]]]:
    """Each window's move minus beta (at the entry's position) times the benchmark's move
    for the same times, and each one's status: the move's own, else NO_BETA or
    NO_BENCHMARK."""
    has = (moves.position >= 0) & (moves.position < len(beta))
    b = np.where(has, beta[np.clip(moves.position, 0, max(len(beta) - 1, 0))], np.nan)
    result: dict[str, Floats] = {}
    statuses: dict[str, npt.NDArray[np.int8]] = {}
    for window, move in moves.move.items():
        other = benchmark.move[window]
        own = moves.status[window]
        status = _status(
            (np.isnan(b), Status.NO_BETA), (np.isnan(other), Status.NO_BENCHMARK), size=len(move)
        )
        status = np.where(own != Status.OK, own, status).astype(np.int8)
        statuses[window] = status
        result[window] = np.where(status == Status.OK, move - b * other, np.nan)
    return result, statuses
