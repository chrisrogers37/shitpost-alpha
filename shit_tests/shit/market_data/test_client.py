"""Tests for MarketDataClient (shit/market_data/client.py)."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session

from shit.market_data.client import MarketDataClient
from shit.market_data.models import MarketPrice


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def client(mock_session):
    c = MarketDataClient(session=mock_session)
    return c


class TestMarketDataClientInit:
    def test_init_with_session(self, mock_session):
        c = MarketDataClient(session=mock_session)
        assert c.session is mock_session
        assert c._own_session is False

    def test_init_without_session(self):
        c = MarketDataClient()
        assert c.session is None
        assert c._own_session is True

    def test_context_manager_with_external_session(self, mock_session):
        c = MarketDataClient(session=mock_session)
        with c as ctx:
            assert ctx.session is mock_session

    @patch("shit.market_data.client.get_session")
    def test_context_manager_creates_session_when_none(self, mock_get_session):
        mock_sess = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        c = MarketDataClient()
        with c as ctx:
            assert ctx.session is mock_sess


class TestGetExistingPrices:
    def test_returns_matching_prices(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice), MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client._get_existing_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 2

    def test_returns_empty_list_when_none(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = client._get_existing_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []


class TestFetchPriceHistory:
    def test_returns_cached_prices_when_available(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert result == existing

    @patch("shit.market_data.client.yf")
    def test_fetches_from_yfinance_when_no_cache(self, mock_yf, client, mock_session):
        # No cached data
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        # No existing individual prices
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Mock yfinance ticker
        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        # Mock empty history
        mock_hist = MagicMock()
        mock_hist.empty = True
        mock_ticker.history.return_value = mock_hist

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert result == []
        mock_yf.Ticker.assert_called_once_with("AAPL")

    @patch("shit.market_data.client.yf")
    def test_force_refresh_skips_cache(self, mock_yf, client, mock_session):
        # Even with existing data, force_refresh should call yfinance
        mock_session.query.return_value.filter.return_value.first.return_value = None

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_hist = MagicMock()
        mock_hist.empty = True
        mock_ticker.history.return_value = mock_hist

        client.fetch_price_history("AAPL", date(2026, 1, 1), force_refresh=True)
        # yfinance should have been called (cache was bypassed)
        mock_yf.Ticker.assert_called_once_with("AAPL")

    def test_end_date_defaults_to_today(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        # Should succeed without passing end_date
        assert len(result) == 1

    @patch("shit.market_data.client.yf")
    def test_rolls_back_on_error(self, mock_yf, client, mock_session):
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_yf.Ticker.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="API down"):
            client.fetch_price_history("AAPL", date(2026, 1, 1))

        mock_session.rollback.assert_called_once()


class TestGetPriceOnDate:
    def test_returns_exact_date_match(self, client, mock_session):
        mock_price = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_price

        result = client.get_price_on_date("AAPL", date(2026, 1, 15))
        assert result is mock_price

    def test_returns_none_when_not_found(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = client.get_price_on_date("AAPL", date(2026, 1, 15))
        assert result is None

    def test_looks_back_when_market_closed(self, client, mock_session):
        # First call (exact date) returns None, second call (day before) returns price
        mock_price = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            None,  # exact date
            mock_price,  # 1 day back
        ]

        result = client.get_price_on_date("AAPL", date(2026, 1, 15))
        assert result is mock_price

    def test_respects_lookback_limit(self, client, mock_session):
        # All lookback days return None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = client.get_price_on_date("AAPL", date(2026, 1, 15), lookback_days=3)
        assert result is None
        # exact date + 3 lookback = 4 calls
        assert mock_session.query.return_value.filter.return_value.first.call_count == 4


class TestGetLatestPrice:
    def test_returns_most_recent(self, client, mock_session):
        mock_price = MagicMock(spec=MarketPrice, close=150.0)
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_price

        result = client.get_latest_price("AAPL")
        assert result is mock_price

    def test_returns_none_when_no_data(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = client.get_latest_price("AAPL")
        assert result is None


class TestUpdatePricesForSymbols:
    def test_updates_multiple_symbols(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.update_prices_for_symbols(["AAPL", "TSLA"])
        assert result == {"AAPL": 1, "TSLA": 1}

    @patch("shit.market_data.client.yf")
    def test_continues_on_error(self, mock_yf, client, mock_session):
        # First symbol fails, second succeeds
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_yf.Ticker.side_effect = RuntimeError("API down")

        result = client.update_prices_for_symbols(["BAD", "ALSO_BAD"])
        assert result["BAD"] == 0
        assert result["ALSO_BAD"] == 0

    def test_defaults_to_30_day_range(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.update_prices_for_symbols(["AAPL"])
        # Should succeed with default date range
        assert "AAPL" in result


class TestGetPriceStats:
    def test_returns_stats_dict(self, client, mock_session):
        mock_stats = MagicMock()
        mock_stats.count = 100
        mock_stats.earliest_date = date(2025, 1, 1)
        mock_stats.latest_date = date(2026, 1, 31)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_stats

        # Mock get_latest_price via the order_by path
        mock_latest = MagicMock(close=155.0)
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_latest

        result = client.get_price_stats("AAPL")
        assert result["symbol"] == "AAPL"
        assert result["count"] == 100
        assert result["latest_price"] == 155.0

    def test_returns_empty_stats_when_no_data(self, client, mock_session):
        mock_stats = MagicMock()
        mock_stats.count = 0
        mock_session.query.return_value.filter.return_value.first.return_value = mock_stats

        result = client.get_price_stats("NOPE")
        assert result["count"] == 0
        assert result["earliest_date"] is None
        assert result["latest_price"] is None
