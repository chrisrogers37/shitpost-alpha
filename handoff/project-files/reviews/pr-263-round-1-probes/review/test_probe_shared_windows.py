"""Probe (PR 263 review, round 1): the p-value treats New York days as independent, but
posts on different days often share one market window (everything posted from Friday's
close to Monday's open enters at Monday's open; 1-day and 24-hour windows of consecutive
days overlap). The random-time draws are independent per call, so the null is too narrow
and p-values come out too small. Synthetic prices only, no effect planted."""

from datetime import date, timedelta

import numpy as np

from engine.backtest.evaluate import Pick, View
from engine.backtest.gate import Pair
from engine.backtest.moves import MAIN
from engine.backtest.stats import Days, resampled_p
from tests.backtest_helpers import FIRST, LAST, SPY, World, at, sessions_for, stock_series, theme


def test_probe_resampled_p_on_calls_sharing_one_move_rejects_far_too_often() -> None:
    """Pure statistics, modelled as the gate draws: 52 weekends, each with one Monday move
    (everything posted from Friday's close to Monday's open enters at Monday's open). Calls
    fall on 13 weekends, 4 calls each on 4 New York dates (Friday night, Saturday, Sunday,
    Monday before the open), so 52 "days" carry 13 moves. Each call's 100 random times are
    random Fridays/Saturdays/Sundays/Mondays of the sample, i.e. random weekends' Monday
    moves. No effect: a valid one-sided test rejects at p < 0.05 about 5% of the time."""
    rejected, trials = 0, 400
    for seed in range(trials):
        rng = np.random.default_rng(seed)
        population = rng.normal(0.0, 0.01, 52)  # the sample's Monday moves
        chosen = rng.choice(52, 13, replace=False)  # the weekends with calls
        moves = np.repeat(population[chosen], 4)
        days = Days.of(np.arange(52, dtype=np.int64))  # 52 New York dates
        randoms = population[rng.integers(0, 52, (52, 100))]
        up = np.ones(52)
        observed = float((days.values(moves) - 0.002).mean())
        p = resampled_p(days, up, randoms, observed, 0.002, seed=seed, draws=2000)
        rejected += p < 0.05
    rate = rejected / trials
    print(f"pure: p<0.05 in {rate:.1%} of {trials} no-effect trials")
    assert rate > 0.12, rate  # well over twice the nominal 5%


def _weekend_world(seed: int, clustered: bool) -> World:
    """One theme, market-link posts only, on a quarter of the weeks (chosen by the seed).
    clustered: Friday 20:00, Saturday and Sunday noon and Monday 08:00 of each chosen
    weekend (all enter at Monday's open). Otherwise: 10:30 on Friday, Monday, Tuesday and
    Wednesday of each chosen week (four separate sessions)."""
    rng = np.random.default_rng(seed)
    sessions = sessions_for()
    world = World()
    fridays = [FIRST + timedelta(days=n) for n in range((LAST - FIRST).days - 7)]
    fridays = [d for d in fridays if d.weekday() == 4]
    chosen = set(rng.choice(len(fridays), len(fridays) // 4, replace=False).tolist())
    for n, day in enumerate(fridays):
        if n not in chosen:
            continue
        if clustered:
            for offset, hour in ((0, 20), (1, 12), (2, 12), (3, 8)):
                world.add(at(day + timedelta(days=offset), hour), theme(rng, 0), Pick(True))
        else:
            for offset in (0, 3, 4, 5):
                world.add(at(day + timedelta(days=offset), 10, 30), theme(rng, 0), Pick(True))
    world.prices = {SPY: stock_series(sessions, rng, 0.0008)}
    return world


def _false_positives(clustered: bool, seeds: range) -> float:
    hits = 0
    for seed in seeds:
        world = _weekend_world(seed, clustered)
        universe = world.universe()
        result = universe.test(
            universe.pickers["rules"],
            View("all_posts", MAIN, filters=False),
            Pair("spy", "close"),
            f"probe/{seed}",
        )
        assert result.days >= 12
        hits += (result.p_value or 1.0) < 0.05
    return hits / len(seeds)


def test_probe_end_to_end_no_effect_rejects_more_when_dates_share_a_window() -> None:
    """The pipeline itself, SPY at the close, no effect: posts on four dates that share
    Monday's window give p < 0.05 several times as often as posts on four separate
    sessions."""
    seeds = range(120)
    clustered = _false_positives(True, seeds)
    separate = _false_positives(False, seeds)
    print(f"p<0.05 rate: clustered {clustered:.0%}, separate {separate:.0%}")
    assert clustered >= 0.12 and clustered >= 2 * max(separate, 0.05)
    assert date(2023, 7, 3) == FIRST

