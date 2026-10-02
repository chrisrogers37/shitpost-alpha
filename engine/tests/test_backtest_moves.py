"""Gate 0 v1's entries, windows and moves, on stand-in prices."""

from collections.abc import Collection
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from engine.backtest.moves import (
    MAIN,
    MIRRORS,
    NONE,
    PREMARKET,
    EntryRule,
    Moves,
    PriceData,
    Status,
    adjusted,
    compute_moves,
    price_at,
    rolling_beta,
)
from engine.market.bars import MinuteSeries
from tests.backtest_helpers import at, cutoff, minutes_of, sessions_for

SESSIONS = sessions_for()
END = cutoff()


def series(
    minutes: list[int], opens: list[float], closes: list[float] | None = None
) -> MinuteSeries:
    return MinuteSeries(
        np.array(minutes, dtype=np.int64),
        np.array(opens, dtype=np.float64),
        np.array(closes if closes is not None else opens, dtype=np.float64),
    )


def stock(bars: MinuteSeries, closes: dict[date, float] | None = None) -> PriceData:
    daily = np.full(len(SESSIONS), np.nan)
    for day, close in (closes or {}).items():
        daily[int(np.searchsorted(SESSIONS.days, day.toordinal()))] = close
    return PriceData("stock", bars, daily, extended=bars)


def session_minutes(day: date) -> list[int]:
    i = int(np.searchsorted(SESSIONS.days, day.toordinal()))
    return list(range(int(SESSIONS.opens[i]), int(SESSIONS.closes[i])))


def one(prices: PriceData, posted: datetime, rule: EntryRule = MAIN) -> Moves:
    return compute_moves(prices, SESSIONS, np.array([posted.timestamp()]), rule, END)


def test_a_post_while_the_market_is_shut_enters_at_the_next_open() -> None:
    monday = date(2024, 6, 10)
    minutes = session_minutes(monday)
    moves = one(stock(series(minutes, [100.0] * len(minutes))), at(date(2024, 6, 8), 12))
    assert moves.entered[0] == minutes_of(at(monday, 9, 30))
    assert moves.status["1h"][0] == Status.OK and moves.move["1h"][0] == 0.0


def test_entry_is_two_minutes_after_the_post_and_twenty_for_mirrors() -> None:
    day = date(2024, 6, 10)
    minutes = session_minutes(day)
    prices = stock(series(minutes, [100.0 + 0.01 * i for i in range(len(minutes))]))
    posted = at(day, 11, 0)
    assert one(prices, posted).entered[0] == minutes_of(at(day, 11, 2))
    assert one(prices, posted, MIRRORS).entered[0] == minutes_of(at(day, 11, 20))
    # A post at 11:00:30 has its alert at 11:02:30: the first bar at or after is 11:03.
    assert one(prices, posted + timedelta(seconds=30)).entered[0] == minutes_of(at(day, 11, 3))


def test_the_close_is_at_least_30_minutes_after_entry_including_a_half_day() -> None:
    half, next_day, after = date(2023, 11, 24), date(2023, 11, 27), date(2023, 11, 28)
    minutes = session_minutes(half)
    assert minutes[-1] == minutes_of(at(half, 12, 59))  # closes at 13:00
    prices = stock(
        series(minutes, [100.0] * len(minutes)), {half: 101.0, next_day: 102.0, after: 103.0}
    )
    early = one(prices, at(half, 12, 20))  # entry 12:22, the close 38 minutes on
    assert early.matured["close"][0] == minutes_of(at(half, 13))
    assert early.move["close"][0] == pytest.approx(0.01)
    assert early.move["1d"][0] == pytest.approx(0.02)

    late = one(prices, at(half, 12, 40))  # entry 12:42, 18 minutes before the close
    assert late.matured["close"][0] == minutes_of(at(next_day, 16))
    assert late.move["close"][0] == pytest.approx(0.02)
    assert late.move["1d"][0] == pytest.approx(0.03)


def test_a_window_past_the_regular_close_is_skipped() -> None:
    day = date(2024, 6, 10)
    minutes = session_minutes(day)
    moves = one(stock(series(minutes, [100.0] * len(minutes))), at(day, 15, 20))
    assert moves.status["15m"][0] == Status.OK
    assert moves.status["1h"][0] == Status.PAST_CLOSE
    assert np.isnan(moves.move["1h"][0])
    assert moves.matured["1h"][0] == minutes_of(at(day, 16, 22))  # counted, not "not yet"


def test_the_price_at_a_time_falls_back_to_a_close_within_five_minutes() -> None:
    bars = series([100, 110], [10.0, 20.0], [11.0, 21.0])
    found = price_at(bars, np.array([100, 103, 105, 106, 110, 99]))
    assert found[0] == 10.0 and found[1] == 11.0 and found[2] == 11.0
    assert np.isnan(found[3])  # the last bar started 6 minutes before
    assert found[4] == 20.0 and np.isnan(found[5])


def coin(first: datetime, count: int, gaps: Collection[int] = ()) -> PriceData:
    start = minutes_of(first)
    minutes = [start + i for i in range(count) if i not in gaps]
    prices = [1000.0 * (1 + 0.0001 * (m - start)) for m in minutes]
    return PriceData("coin", series(minutes, prices), np.zeros(0), day_base=start // 1440)


def test_coin_windows_run_across_midnight_utc() -> None:
    posted = datetime(2024, 3, 4, 23, 50, tzinfo=UTC)
    prices = coin(posted, 3 * 1440 - 10)
    moves = one(prices, posted)
    entry = minutes_of(posted) + 2
    assert moves.entered[0] == entry
    for window, minutes in (("1h", 60), ("4h", 240), ("24h", 1440)):
        expected = (1 + 0.0001 * (2 + minutes)) / (1 + 0.0001 * 2) - 1
        assert moves.move[window][0] == pytest.approx(expected)
        assert moves.matured[window][0] == entry + minutes
    assert moves.status["3d"][0] == Status.NO_EXIT  # the bars stop before 3 days


def test_a_coin_call_without_a_bar_near_entry_or_exit_is_skipped() -> None:
    posted = datetime(2024, 3, 4, 12, 0, tzinfo=UTC)
    late = one(coin(posted, 600, gaps=set(range(0, 8))), posted)  # first bar 6 min late
    assert late.status["1h"][0] == Status.LATE_ENTRY and late.entered[0] == NONE
    # An exit at entry + 15 with no bar there or in the 5 minutes before is skipped...
    entry = 2
    gone = one(coin(posted, 600, gaps=set(range(entry + 9, entry + 16))), posted)
    assert gone.status["15m"][0] == Status.NO_EXIT
    # ...and with a bar 3 minutes before, that bar's close is the exit price.
    near = one(coin(posted, 600, gaps=set(range(entry + 13, entry + 16))), posted)
    assert near.status["15m"][0] == Status.OK


def test_a_window_ending_after_the_data_is_not_yet_known() -> None:
    last = date(2024, 6, 28)
    minutes = session_minutes(last)
    prices = stock(series(minutes, [100.0] * len(minutes)), {last: 100.0})
    moves = one(prices, at(last, 15, 0))
    assert moves.status["15m"][0] == Status.OK
    assert moves.status["1d"][0] == Status.NOT_YET and moves.matured["1d"][0] == NONE
    after = one(prices, at(last, 17, 0))  # enters next session: after the data
    assert after.status["close"][0] == Status.NOT_YET and after.entered[0] == NONE
    coins = one(coin(datetime(2024, 6, 28, 0, tzinfo=UTC), 2 * 1440), at(last, 23, 59))
    assert coins.status["5m"][0] == Status.NOT_YET  # its alert is after the data


def test_premarket_entry_uses_extended_bars_between_four_and_the_open() -> None:
    day = date(2024, 6, 10)
    minutes = list(range(minutes_of(at(day, 4)), minutes_of(at(day, 16))))
    prices = stock(series(minutes, [100.0 + 0.01 * i for i in range(len(minutes))]))
    early = one(prices, at(day, 8, 0), PREMARKET)
    assert early.entered[0] == minutes_of(at(day, 8, 2))
    assert early.status["1h"][0] == Status.OK
    regular = one(prices, at(day, 8, 0))
    assert regular.entered[0] == minutes_of(at(day, 9, 30))
    assert one(prices, at(day, 11, 0), PREMARKET).status["1h"][0] == Status.NOT_PREMARKET
    assert one(prices, at(date(2024, 6, 8), 8, 0), PREMARKET).status["1h"][0] == (
        Status.NOT_PREMARKET  # a Saturday: no session that day
    )


def test_beta_is_the_slope_on_the_120_sessions_before() -> None:
    rng = np.random.default_rng(3)
    market = 100 * np.cumprod(1 + rng.normal(0, 0.01, 200))
    returns = np.diff(market) / market[:-1]
    company = 50 * np.cumprod(np.concatenate([[1.0], 1 + 1.5 * returns]))
    beta = rolling_beta(company, market)
    assert np.isnan(beta[60]) and beta[61] == pytest.approx(1.5)  # 60 returns before 61
    assert beta[199] == pytest.approx(1.5)
    shifted = company.copy()
    shifted[:78] *= np.cumprod(1 + rng.normal(0, 0.05, 78))  # returns before the window only
    assert rolling_beta(shifted, market)[199] == pytest.approx(1.5)


def test_a_company_is_judged_net_of_beta_times_spy() -> None:
    day = date(2024, 6, 10)
    minutes = session_minutes(day)
    i = int(np.searchsorted(SESSIONS.days, day.toordinal()))
    entry = minutes.index(minutes_of(at(day, 11, 2)))
    spy_opens = [100.0] * len(minutes)
    spy_opens[entry + 60] = 101.0  # SPY +1% over the hour
    acme_opens = [50.0] * len(minutes)
    acme_opens[entry + 60] = 51.0  # the company +2%
    spy, acme = stock(series(minutes, spy_opens)), stock(series(minutes, acme_opens))
    times = np.array([at(day, 11).timestamp()])
    beta = np.full(len(SESSIONS), np.nan)
    beta[i] = 1.5
    net, status = adjusted(
        compute_moves(acme, SESSIONS, times, MAIN, END),
        compute_moves(spy, SESSIONS, times, MAIN, END),
        beta,
    )
    assert net["1h"][0] == pytest.approx(0.02 - 1.5 * 0.01)
    assert status["1h"][0] == Status.OK
    beta[i] = np.nan
    net, status = adjusted(
        compute_moves(acme, SESSIONS, times, MAIN, END),
        compute_moves(spy, SESSIONS, times, MAIN, END),
        beta,
    )
    assert status["1h"][0] == Status.NO_BETA and np.isnan(net["1h"][0])


def test_eth_is_judged_against_btc_on_utc_days() -> None:
    posted = datetime(2024, 3, 4, 12, 0, tzinfo=UTC)
    btc = coin(posted, 600)
    eth_minutes = btc.bars.minutes
    eth = PriceData(
        "coin",
        series(list(eth_minutes), list(1 + 2 * (btc.bars.opens / 1000 - 1))),
        np.zeros(0),
        day_base=btc.day_base,
    )
    times = np.array([posted.timestamp()])
    eth_moves, btc_moves = (compute_moves(p, SESSIONS, times, MAIN, END) for p in (eth, btc))
    beta = np.full(5, np.nan)
    beta[eth_moves.position[0]] = 2.0
    assert eth_moves.position[0] == 0  # the entry's UTC day, from day_base
    net, _ = adjusted(eth_moves, btc_moves, beta)
    assert net["1h"][0] == pytest.approx(eth_moves.move["1h"][0] - 2 * btc_moves.move["1h"][0])
