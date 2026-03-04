"""Tests for intraday_provider.py."""

from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

from shit.market_data.intraday_provider import (
    IntradayPriceSnapshot,
    fetch_intraday_snapshot,
)


class TestIntradayPriceSnapshot:
    def test_defaults_to_none(self):
        snap = IntradayPriceSnapshot()
        assert snap.price_at_post is None
        assert snap.price_1h_after is None
        assert snap.price_at_next_close is None

    def test_accepts_values(self):
        snap = IntradayPriceSnapshot(
            price_at_post=150.0,
            price_1h_after=151.0,
            price_at_next_close=149.5,
        )
        assert snap.price_at_post == 150.0
        assert snap.price_1h_after == 151.0
        assert snap.price_at_next_close == 149.5


class TestFetchIntradaySnapshot:
    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_returns_empty_snapshot_when_no_bars(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = []

        result = fetch_intraday_snapshot(
            "AAPL", datetime(2025, 6, 16, 14, 0, tzinfo=timezone.utc)
        )
        assert result.price_at_post is None
        assert result.price_1h_after is None
        assert result.price_at_next_close is None

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_finds_price_at_post(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)

        # Create mock bars with bar_datetime as formal field
        bar1 = MagicMock()
        bar1.close = 150.0
        bar1.open = 149.5
        bar1.bar_datetime = datetime(2025, 6, 16, 13, 30, tzinfo=timezone.utc)

        bar2 = MagicMock()
        bar2.close = 151.0
        bar2.open = 150.0
        bar2.bar_datetime = datetime(2025, 6, 16, 14, 30, tzinfo=timezone.utc)

        bar3 = MagicMock()
        bar3.close = 152.0
        bar3.open = 151.0
        bar3.bar_datetime = datetime(2025, 6, 16, 15, 30, tzinfo=timezone.utc)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = [bar1, bar2, bar3]

        # Post at 2:15 PM UTC
        result = fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 14, 15, tzinfo=timezone.utc),
        )
        # Closest bar at or before 2:15 PM is bar1 (1:30 PM)
        assert result.price_at_post == 150.0
        # 1h after 2:15 PM is 3:15 PM, closest bar at/before that is bar2 (2:30 PM)
        assert result.price_1h_after == 151.0
        # price_at_next_close is last bar's close
        assert result.price_at_next_close == 152.0

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_premarket_post_uses_first_bar_open(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)

        bar1 = MagicMock()
        bar1.close = 150.0
        bar1.open = 149.0
        bar1.bar_datetime = datetime(2025, 6, 16, 13, 30, tzinfo=timezone.utc)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = [bar1]

        # Post at 10:00 AM UTC (before 1:30 PM bar)
        result = fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc),
        )
        # Pre-market: use first bar's open
        assert result.price_at_post == 149.0

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_non_trading_day_uses_next_session(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = False
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)  # Monday

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = []

        # Post on Saturday
        fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 14, 12, 0, tzinfo=timezone.utc),
        )
        # Should have called fetch_intraday_prices with Monday's date
        mock_provider.fetch_intraday_prices.assert_called_once_with(
            "AAPL", date(2025, 6, 16), interval="1h"
        )

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_after_close_uses_next_session(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )
        mock_cal.next_trading_day.return_value = date(2025, 6, 17)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = []

        # Post at 9 PM UTC (after close)
        fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 21, 0, tzinfo=timezone.utc),
        )
        # Should have called fetch_intraday_prices with next trading day
        mock_provider.fetch_intraday_prices.assert_called_once_with(
            "AAPL", date(2025, 6, 17), interval="1h"
        )

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_handles_fetch_exception_gracefully(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.side_effect = RuntimeError("network error")

        result = fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 14, 0, tzinfo=timezone.utc),
        )
        assert result.price_at_post is None
        assert result.price_1h_after is None

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_naive_datetime_assumed_utc(self, mock_cal_cls, mock_yf_cls):
        """Naive datetimes should be treated as UTC."""
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(
            2025, 6, 16, 20, 0, tzinfo=timezone.utc
        )

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = []

        # Should not raise -- naive datetime gets UTC timezone
        result = fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 14, 0),  # naive
        )
        assert result.price_at_post is None
