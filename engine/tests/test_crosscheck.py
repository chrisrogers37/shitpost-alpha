from datetime import UTC, date, datetime

from engine.market.alpaca import Bar
from scripts.crosscheck_yfinance import bar_day, compare
from tests.market_helpers import daily_bar


def test_compare_lists_days_more_than_half_a_percent_apart() -> None:
    alpaca = {date(2024, 1, 2): 100.0, date(2024, 1, 3): 101.0, date(2024, 1, 4): 102.0}
    yahoo = {date(2024, 1, 3): 101.4, date(2024, 1, 4): 103.0, date(2024, 1, 5): 104.0}
    result = compare("SPY", alpaca, yahoo)
    assert (result.days, result.only_alpaca, result.only_yahoo) == (2, 1, 1)
    assert result.apart == [(date(2024, 1, 4), 102.0, 103.0)]
    assert result.lines()[0].startswith("SPY: 2 days in both; 1 over 0.5% apart (worst 0.97%)")


def test_bar_days() -> None:
    stock = Bar.parse(daily_bar(date(2024, 1, 2), 1.0))
    assert stock.start == datetime(2024, 1, 2, 5, tzinfo=UTC)
    assert bar_day(stock, coin=False) == date(2024, 1, 2)
    coin = Bar.parse(daily_bar(date(2024, 1, 2), 1.0, coin=True))
    assert bar_day(coin, coin=True) == date(2024, 1, 2)
