"""Tests for MarketDataClient (shit/market_data/client.py)."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session

from shit.market_data.client import MarketDataClient
from shit.market_data.models import MarketPrice
from shit.market_data.price_provider import ProviderChain, ProviderError, RawPriceRecord


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_chain():
    chain = MagicMock(spec=ProviderChain)
    chain.providers = [MagicMock()]
    return chain


@pytest.fixture
def client(mock_session, mock_chain):
    c = MarketDataClient(session=mock_session, provider_chain=mock_chain)
    return c


class TestMarketDataClientInit:
    def test_init_with_session(self, mock_session, mock_chain):
        c = MarketDataClient(session=mock_session, provider_chain=mock_chain)
        assert c.session is mock_session
        assert c._own_session is False

    def test_init_without_session(self):
        c = MarketDataClient()
        assert c.session is None
        assert c._own_session is True

    def test_context_manager_with_external_session(self, mock_session, mock_chain):
        c = MarketDataClient(session=mock_session, provider_chain=mock_chain)
        with c as ctx:
            assert ctx.session is mock_session

    @patch("shit.market_data.client.get_session")
    def test_context_manager_creates_session_when_none(self, mock_get_session, mock_chain):
        mock_sess = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        c = MarketDataClient(provider_chain=mock_chain)
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

    def test_fetches_from_providers_when_no_cache(self, client, mock_session, mock_chain):
        # No cached data
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        # Provider chain returns empty
        mock_chain.fetch_with_fallback.return_value = []

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert result == []
        mock_chain.fetch_with_fallback.assert_called()

    def test_force_refresh_skips_cache(self, client, mock_session, mock_chain):
        mock_chain.fetch_with_fallback.return_value = []

        client.fetch_price_history("AAPL", date(2026, 1, 1), force_refresh=True)
        mock_chain.fetch_with_fallback.assert_called()

    def test_end_date_defaults_to_today(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert len(result) == 1

    def test_stores_raw_records(self, client, mock_session, mock_chain):
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.first.return_value = None

        records = [
            RawPriceRecord(
                symbol="AAPL", date=date(2026, 1, 15),
                open=150.0, high=155.0, low=149.0, close=153.0,
                volume=1000000, adjusted_close=153.0, source="yfinance",
            )
        ]
        mock_chain.fetch_with_fallback.return_value = records

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert len(result) == 1
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_rolls_back_on_db_error(self, client, mock_session, mock_chain):
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.first.return_value = None

        records = [
            RawPriceRecord(
                symbol="AAPL", date=date(2026, 1, 15),
                open=150.0, high=155.0, low=149.0, close=153.0,
                volume=1000000, adjusted_close=153.0, source="yfinance",
            )
        ]
        mock_chain.fetch_with_fallback.return_value = records
        mock_session.commit.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            client.fetch_price_history("AAPL", date(2026, 1, 1))

        mock_session.rollback.assert_called_once()


class TestFetchWithRetry:
    @patch("shit.market_data.client.settings")
    @patch("shit.market_data.client.time")
    def test_retries_on_provider_error(self, mock_time, mock_settings, client, mock_chain):
        mock_settings.MARKET_DATA_MAX_RETRIES = 2
        mock_settings.MARKET_DATA_RETRY_DELAY = 0.01
        mock_settings.MARKET_DATA_RETRY_BACKOFF = 1.0
        mock_settings.MARKET_DATA_FAILURE_ALERT_CHAT_ID = None

        records = [RawPriceRecord(
            symbol="AAPL", date=date(2026, 1, 15),
            open=150.0, high=155.0, low=149.0, close=153.0,
            volume=1000000, adjusted_close=153.0, source="test",
        )]

        mock_chain.fetch_with_fallback.side_effect = [
            ProviderError("all", "down"),
            ProviderError("all", "still down"),
            records,
        ]

        result = client._fetch_with_retry("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1
        assert mock_chain.fetch_with_fallback.call_count == 3

    @patch("shit.market_data.client._send_failure_alert")
    @patch("shit.market_data.client.settings")
    @patch("shit.market_data.client.time")
    def test_sends_alert_after_all_retries_exhausted(self, mock_time, mock_settings, mock_alert, client, mock_chain):
        mock_settings.MARKET_DATA_MAX_RETRIES = 1
        mock_settings.MARKET_DATA_RETRY_DELAY = 0.01
        mock_settings.MARKET_DATA_RETRY_BACKOFF = 1.0
        mock_settings.MARKET_DATA_FAILURE_ALERT_CHAT_ID = None

        mock_chain.fetch_with_fallback.side_effect = ProviderError("all", "permanently down")

        result = client._fetch_with_retry("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []
        mock_alert.assert_called_once()

    @patch("shit.market_data.client.settings")
    def test_no_retry_on_success(self, mock_settings, client, mock_chain):
        mock_settings.MARKET_DATA_MAX_RETRIES = 3
        mock_settings.MARKET_DATA_RETRY_DELAY = 0.01
        mock_settings.MARKET_DATA_RETRY_BACKOFF = 1.0

        records = [MagicMock()]
        mock_chain.fetch_with_fallback.return_value = records

        result = client._fetch_with_retry("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1
        assert mock_chain.fetch_with_fallback.call_count == 1


class TestStoreRawRecords:
    def test_creates_new_price_records(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        records = [
            RawPriceRecord(
                symbol="AAPL", date=date(2026, 1, 15),
                open=150.0, high=155.0, low=149.0, close=153.0,
                volume=1000000, adjusted_close=153.0, source="yfinance",
            ),
        ]

        result = client._store_raw_records(records)
        assert len(result) == 1
        mock_session.add.assert_called_once()

    def test_skips_existing_unless_force(self, client, mock_session):
        existing = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        records = [
            RawPriceRecord(
                symbol="AAPL", date=date(2026, 1, 15),
                open=150.0, high=155.0, low=149.0, close=153.0,
                volume=1000000, adjusted_close=153.0, source="yfinance",
            ),
        ]

        result = client._store_raw_records(records, force_refresh=False)
        assert result[0] is existing
        mock_session.add.assert_not_called()

    def test_updates_existing_on_force(self, client, mock_session):
        existing = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        records = [
            RawPriceRecord(
                symbol="AAPL", date=date(2026, 1, 15),
                open=160.0, high=165.0, low=159.0, close=163.0,
                volume=2000000, adjusted_close=163.0, source="alphavantage",
            ),
        ]

        result = client._store_raw_records(records, force_refresh=True)
        assert result[0] is existing
        assert existing.close == 163.0
        assert existing.source == "alphavantage"
        mock_session.add.assert_not_called()  # Updated in-place, no add


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
        mock_price = MagicMock(spec=MarketPrice)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            None,  # exact date
            mock_price,  # 1 day back
        ]

        result = client.get_price_on_date("AAPL", date(2026, 1, 15))
        assert result is mock_price

    def test_respects_lookback_limit(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = client.get_price_on_date("AAPL", date(2026, 1, 15), lookback_days=3)
        assert result is None
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

    def test_continues_on_error(self, client, mock_session, mock_chain):
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_chain.fetch_with_fallback.side_effect = ProviderError("all", "down")

        result = client.update_prices_for_symbols(["BAD", "ALSO_BAD"])
        assert result["BAD"] == 0
        assert result["ALSO_BAD"] == 0

    def test_defaults_to_30_day_range(self, client, mock_session):
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = existing

        result = client.update_prices_for_symbols(["AAPL"])
        assert "AAPL" in result


class TestGetPriceStats:
    def test_returns_stats_dict(self, client, mock_session):
        mock_stats = MagicMock()
        mock_stats.count = 100
        mock_stats.earliest_date = date(2025, 1, 1)
        mock_stats.latest_date = date(2026, 1, 31)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_stats

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
