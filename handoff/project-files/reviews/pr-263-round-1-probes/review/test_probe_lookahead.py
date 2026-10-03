"""Probes (PR 263 review, round 1): look-ahead in the match pool and the baselines.

Synthetic prices only. Each test passes while the look-ahead it names is real."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import numpy as np

from engine.backtest import gate
from engine.backtest.evaluate import Pick, call_for
from engine.backtest.moves import MAIN, PriceData
from engine.market.bars import MinuteSeries
from tests.backtest_helpers import (
    BTC,
    ETH,
    SPY,
    World,
    at,
    coin_series,
    minutes_of,
    planted_world,
    sessions_for,
    stock_series,
    theme,
)


def _without(prices: PriceData, minutes: range) -> PriceData:
    keep = ~np.isin(prices.bars.minutes, np.array(list(minutes), dtype=np.int64))
    return replace(prices, bars=prices.bars.where(keep))


def _scaled_after(prices: PriceData, after: int, factor: float) -> PriceData:
    """The same bars, with every price from minute `after` on scaled (a different future)."""
    later = prices.bars.minutes >= after
    bars = MinuteSeries(
        prices.bars.minutes,
        np.where(later, prices.bars.opens * factor, prices.bars.opens),
        np.where(later, prices.bars.closes * factor, prices.bars.closes),
    )
    return replace(prices, bars=bars)


def test_probe_a_match_whose_benchmark_exit_is_after_the_alert_is_in_the_pool() -> None:
    """B1: Matcher.matches (evaluate.py:285-286) takes a match's maturity from the
    instrument alone (MoveBook.judged, evaluate.py:186), but its judged move also uses the
    benchmark's exit, which can come later (BTC entering a few minutes after ETH: a gap
    under 5 minutes is allowed). A post whose alert falls between the two exits gets that
    match, and its call changes with BTC prices after its own alert."""
    rng = np.random.default_rng(4)
    t0 = datetime(2024, 3, 4, 12, 0, tzinfo=UTC)
    m0 = minutes_of(t0)
    world = World()
    match = world.add(t0, theme(rng, 0), Pick(True))
    post = world.add(t0 + timedelta(minutes=61), theme(rng, 0), Pick(True))  # alert t0+63
    full = coin_series(rng, 0.0004)
    btc = _without(full, range(m0 + 2, m0 + 6))  # BTC enters at t0+6
    eth = PriceData(  # ETH moves with BTC (beta 1), with no gap: it enters at t0+2
        "coin",
        MinuteSeries(full.bars.minutes, full.bars.opens * 0.03, full.bars.closes * 0.03),
        full.daily * 0.03,
        day_base=full.day_base,
    )
    world.prices = {BTC: btc, ETH: eth}
    universe = world.universe()
    judged = universe.book.judged(ETH, MAIN, "1h")
    btc_moves = universe.book.post_moves(BTC, MAIN)
    alert_minute = minutes_of(t0) + 63
    assert judged.matured[match] == m0 + 62 <= alert_minute  # ETH's exit: before the alert
    assert btc_moves.matured["1h"][match] == m0 + 66 > alert_minute  # BTC's: after it
    assert match in universe.matcher.matches(post, MAIN, judged)
    seen = judged.move[match]

    # Change only BTC prices from after the post's alert: the match's judged move moves.
    world.prices = {BTC: _scaled_after(btc, alert_minute + 1, 1.05), ETH: eth}
    future = world.universe().book.judged(ETH, MAIN, "1h")
    assert match in world.universe().matcher.matches(post, MAIN, future)
    assert abs(future.move[match] - seen) > 0.01  # ~5% times beta: read from the future


def test_probe_rule_4s_baseline_reads_prices_after_the_post() -> None:
    """Q1 (the frozen spec's own definition): the random-time median a post is compared
    with (rule 4) is taken over random times on dates drawn from the whole sample, so a
    July 2023 post's send decision depends on SPY prices from 2024. Changing only prices
    from 2023-10-01 on flips whether a 2023-07-03 post is sent."""
    base = planted_world(seed=5, effect=0.0)
    early = 0  # the first market-link post: 2023-07-03 10:30, a Monday
    assert base.times[early].date() == date(2023, 7, 3)
    bucket = 0 * 24 + 10
    u1 = base.universe()
    b1 = u1.baseline(SPY, "main", "1h", bucket)
    assert b1 is not None

    # The same world, with SPY moving +1% at 11:00 New York on every session from October.
    sessions = sessions_for()
    jumps = {
        minutes_of(at(date.fromordinal(int(d)), 11)): 0.01
        for d in sessions.days
        if d >= date(2023, 10, 1).toordinal()
    }
    later = planted_world(seed=5, effect=0.0)
    rng = np.random.default_rng(99)
    later.prices[SPY] = stock_series(sessions, rng, 0.0004, jumps)
    first = base.prices[SPY].bars
    cut = minutes_of(at(date(2023, 10, 1), 0))
    # Prices up to October 2023 kept exactly as in the base world: only the future differs.
    keep = first.minutes < cut
    joined = MinuteSeries(
        np.concatenate([first.minutes[keep], later.prices[SPY].bars.minutes[later.prices[SPY].bars.minutes >= cut]]),
        np.concatenate([first.opens[keep], later.prices[SPY].bars.opens[later.prices[SPY].bars.minutes >= cut]]),
        np.concatenate([first.closes[keep], later.prices[SPY].bars.closes[later.prices[SPY].bars.minutes >= cut]]),
    )
    later.prices[SPY] = PriceData("stock", joined, base.prices[SPY].daily, extended=joined)
    b2 = later.universe().baseline(SPY, "main", "1h", bucket)
    assert b2 is not None and b2 - b1 > 0.001  # the 2023 post's baseline moved

    # Matches whose median beats b1 by 25 bp: sent with today's past, not with that future.
    from tests.test_backtest_gate import judged as judged_moves, posts_on

    moves = judged_moves([b1 + 0.0025] * 7 + [-0.01] * 3)
    days, matches = posts_on(list(range(10))), np.arange(10)
    assert call_for(matches, moves, days, b1, filters=True).reason is None
    assert call_for(matches, moves, days, b2, filters=True).reason == "not_better_than_random"
    assert gate.BEAT_RANDOM == 0.0020


def test_probe_the_pool_takes_stock_windows_the_live_feed_cannot_see_yet() -> None:
    """Q2: the pool takes a stock match as soon as its window ends (evaluate.py:284-286),
    but live, Alpaca's free SIP data is 15 minutes behind (PR 3's SIP_DELAY, 16 min):
    at a 16:05 alert the 16:00 close of an earlier post isn't readable yet. The gate says
    both "matured by this post's alert time" and "exactly as it would be live"."""
    from engine.market.alpaca import SIP_DELAY

    rng = np.random.default_rng(8)
    world = World()
    day = date(2024, 3, 5)
    earlier = world.add(at(day, 10, 30), theme(rng, 0), Pick(True))
    post = world.add(at(day, 16, 3), theme(rng, 0), Pick(True))  # alert 16:05
    world.prices = {SPY: stock_series(sessions_for(), rng, 0.0004)}
    universe = world.universe()
    judged = universe.book.judged(SPY, MAIN, "close")
    assert judged.matured[earlier] == minutes_of(at(day, 16))
    assert earlier in universe.matcher.matches(post, MAIN, judged)
    readable_live = minutes_of(at(day, 16, 5)) - SIP_DELAY.total_seconds() / 60
    assert judged.matured[earlier] > readable_live  # not yet readable live at the alert
