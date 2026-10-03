"""Gate 0 v1's statistics: day values, hit rates with Wilson intervals, the random-time
resampling p-value, Benjamini-Hochberg q-values and the paid gate's sample size."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from engine.backtest import gate

Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]


@dataclass(frozen=True)
class Days:
    """Calls grouped by New York date: each call's position in `order` sorts them by day,
    `starts` is where each day begins, `days` its date (an ordinal)."""

    order: Ints
    starts: Ints
    days: Ints
    counts: Floats

    @classmethod
    def of(cls, call_days: Ints) -> "Days":
        order = np.argsort(call_days, kind="stable").astype(np.int64)
        days, starts, counts = np.unique(call_days[order], return_index=True, return_counts=True)
        return cls(order, starts.astype(np.int64), days.astype(np.int64), counts.astype(np.float64))

    def __len__(self) -> int:
        return len(self.days)

    def values(self, per_call: Floats) -> Floats:
        """Each day's mean over its calls (per_call may have rows: one per draw)."""
        if not len(self):
            return np.zeros((*per_call.shape[:-1], 0))
        sorted_calls = per_call[..., self.order]
        result: Floats = np.add.reduceat(sorted_calls, self.starts, axis=-1) / self.counts
        return result


def wilson(hits: int, n: int, z: float = gate.WILSON_Z) -> tuple[float, float] | None:
    """The Wilson score interval for a rate of hits in n."""
    if n == 0:
        return None
    rate = hits / n
    centre = (rate + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def resampled_p(
    days: Days,
    directions: Floats,
    random_moves: Floats,
    observed: float,
    cost: float,
    seed: int,
    draws: int = gate.DRAWS,
    chunk: int = 500,
) -> float:
    """Each draw replaces every call's move with one of its own post's random-time moves,
    chosen evenly among those it has, taken in the call's direction and less `cost`, and
    takes the day-averaged mean. p = (1 + draws at or above `observed`) / (draws + 1).
    `random_moves` has one row per call, NaN where a random time has no move; every row
    needs at least one move."""
    rows = np.sort(random_moves, axis=1)  # NaN last: a row's moves come first
    have = np.isfinite(rows).sum(axis=1)
    if (have == 0).any():
        raise ValueError("a call without random-time moves")
    rng = np.random.default_rng(seed)
    at_or_above = 0
    calls = np.arange(len(rows))
    for start in range(0, draws, chunk):
        size = min(chunk, draws - start)
        picks = np.floor(rng.random((size, len(rows))) * have).astype(np.int64)
        values = directions * rows[calls, picks] - cost
        means = days.values(values).mean(axis=-1)
        at_or_above += int((means >= observed).sum())
    return (1 + at_or_above) / (draws + 1)


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """q-values: each p times m over its rank, made monotone from the largest down, at
    most 1."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        q[i] = running
    return q


def days_needed(hit_rate: float) -> int | None:
    """Days of calls that confirm a hit rate against 50% (one-sided, 5% error, 80%
    power); None when the rate isn't above 50%."""
    if not hit_rate > 0.5:
        return None
    root = gate.ALPHA_Z * 0.5 + gate.POWER_Z * math.sqrt(hit_rate * (1 - hit_rate))
    return math.ceil((root / (hit_rate - 0.5)) ** 2)
