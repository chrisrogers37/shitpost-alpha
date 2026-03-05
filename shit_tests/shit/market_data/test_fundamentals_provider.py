"""Tests for FundamentalsProvider.

Tests cover fetching, extraction, staleness checking, single-ticker updates,
and batch updates. All tests mock get_session and yf.Ticker to avoid real
API calls and database dependencies.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from shit.market_data.fundamentals_provider import (
    FundamentalsProvider,
    _QUOTE_TYPE_MAP,
    _MAX_DESCRIPTION_LENGTH,
)
from shit.market_data.models import TickerRegistry


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_registry_entry(**overrides) -> MagicMock:
    """Create a mock TickerRegistry row."""
    entry = MagicMock(spec=TickerRegistry)
    entry.symbol = overrides.get("symbol", "AAPL")
    entry.status = overrides.get("status", "active")
    entry.fundamentals_updated_at = overrides.get("fundamentals_updated_at", None)
    entry.company_name = overrides.get("company_name", None)
    entry.sector = overrides.get("sector", None)
    entry.industry = overrides.get("industry", None)
    entry.market_cap = overrides.get("market_cap", None)
    entry.pe_ratio = overrides.get("pe_ratio", None)
    entry.forward_pe = overrides.get("forward_pe", None)
    entry.dividend_yield = overrides.get("dividend_yield", None)
    entry.beta = overrides.get("beta", None)
    entry.exchange = overrides.get("exchange", None)
    entry.asset_type = overrides.get("asset_type", None)
    entry.description = overrides.get("description", None)
    return entry


def _sample_info() -> dict:
    """Return a sample yfinance .info dict for AAPL."""
    return {
        "longName": "Apple Inc.",
        "shortName": "Apple",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3500000000000,
        "trailingPE": 28.5,
        "forwardPE": 25.2,
        "dividendYield": 0.005,
        "beta": 1.25,
        "exchange": "NMS",
        "quoteType": "EQUITY",
        "longBusinessSummary": "Apple designs, manufactures, and markets smartphones.",
        "regularMarketPrice": 175.50,
    }


# ── TestFetchInfo ────────────────────────────────────────────────────


class TestFetchInfo:
    """Tests for FundamentalsProvider.fetch_info()."""

    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_returns_info_dict_for_valid_symbol(self, mock_ticker_cls):
        """Valid symbol returns populated info dict."""
        mock_ticker = MagicMock()
        mock_ticker.info = _sample_info()
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        result = provider.fetch_info("AAPL")

        assert result["longName"] == "Apple Inc."
        assert result["sector"] == "Technology"
        mock_ticker_cls.assert_called_once_with("AAPL")

    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_returns_empty_dict_for_invalid_symbol(self, mock_ticker_cls):
        """Invalid symbol (no shortName/longName) returns empty dict."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingPegRatio": None, "regularMarketPrice": None}
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        result = provider.fetch_info("INVALID123")

        assert result == {}

    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_returns_empty_dict_on_exception(self, mock_ticker_cls):
        """Exception during fetch returns empty dict."""
        mock_ticker_cls.side_effect = Exception("Network error")

        provider = FundamentalsProvider()
        result = provider.fetch_info("AAPL")

        assert result == {}

    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_logs_warning_for_invalid_symbol(self, mock_ticker_cls):
        """Invalid symbol logs a warning."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"regularMarketPrice": None}
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        with patch("shit.market_data.fundamentals_provider.logger") as mock_logger:
            provider.fetch_info("INVALID")
            mock_logger.warning.assert_called_once()


# ── TestExtractFundamentals ──────────────────────────────────────────


class TestExtractFundamentals:
    """Tests for FundamentalsProvider._extract_fundamentals()."""

    def test_extracts_all_fields_from_complete_info(self):
        """Complete info dict populates all fields."""
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(_sample_info())

        assert result["company_name"] == "Apple Inc."
        assert result["sector"] == "Technology"
        assert result["industry"] == "Consumer Electronics"
        assert result["market_cap"] == 3500000000000
        assert result["pe_ratio"] == 28.5
        assert result["forward_pe"] == 25.2
        assert result["dividend_yield"] == 0.005
        assert result["beta"] == 1.25
        assert result["exchange"] == "NMS"
        assert result["asset_type"] == "stock"
        assert result["description"] is not None

    def test_handles_missing_sector_for_etf(self):
        """ETF without sector returns None for sector/industry."""
        info = {
            "shortName": "SPDR S&P 500 ETF Trust",
            "quoteType": "ETF",
            "regularMarketPrice": 450.0,
        }
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert result["company_name"] == "SPDR S&P 500 ETF Trust"
        assert result["sector"] is None
        assert result["industry"] is None
        assert result["asset_type"] == "etf"

    def test_handles_missing_pe_for_commodity(self):
        """Commodity without P/E ratios returns None."""
        info = {
            "shortName": "Gold Futures",
            "quoteType": "FUTURE",
            "regularMarketPrice": 2000.0,
        }
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert result["pe_ratio"] is None
        assert result["forward_pe"] is None
        assert result["asset_type"] == "commodity"

    def test_truncates_long_description(self):
        """Description longer than _MAX_DESCRIPTION_LENGTH is truncated."""
        long_desc = "A" * 1000
        info = {
            "longBusinessSummary": long_desc,
            "shortName": "Test Corp",
            "quoteType": "EQUITY",
        }
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert len(result["description"]) == _MAX_DESCRIPTION_LENGTH
        assert result["description"].endswith("...")

    def test_maps_quote_type_to_asset_type(self):
        """All known quoteType values map correctly."""
        provider = FundamentalsProvider()
        for yf_type, expected in _QUOTE_TYPE_MAP.items():
            info = {"quoteType": yf_type, "shortName": "Test"}
            result = provider._extract_fundamentals(info)
            assert result["asset_type"] == expected

    def test_prefers_longName_over_shortName(self):
        """When both longName and shortName exist, longName is used."""
        info = {
            "longName": "Apple Inc.",
            "shortName": "Apple",
            "quoteType": "EQUITY",
        }
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert result["company_name"] == "Apple Inc."

    def test_handles_none_market_cap(self):
        """None market cap is handled gracefully."""
        info = {"shortName": "Test", "quoteType": "EQUITY"}
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert result["market_cap"] is None

    def test_handles_non_numeric_market_cap(self):
        """Non-numeric market cap is handled gracefully."""
        info = {"shortName": "Test", "quoteType": "EQUITY", "marketCap": "invalid"}
        provider = FundamentalsProvider()
        result = provider._extract_fundamentals(info)

        assert result["market_cap"] is None


# ── TestIsStale ──────────────────────────────────────────────────────


class TestIsStale:
    """Tests for FundamentalsProvider._is_stale()."""

    def test_returns_true_when_never_updated(self):
        """Entry with no fundamentals_updated_at is stale."""
        provider = FundamentalsProvider(staleness_hours=24)
        entry = _make_registry_entry(fundamentals_updated_at=None)

        assert provider._is_stale(entry) is True

    def test_returns_true_when_older_than_threshold(self):
        """Entry older than staleness threshold is stale."""
        provider = FundamentalsProvider(staleness_hours=24)
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=25)
        entry = _make_registry_entry(fundamentals_updated_at=old_time)

        assert provider._is_stale(entry) is True

    def test_returns_false_when_fresh(self):
        """Entry within staleness threshold is not stale."""
        provider = FundamentalsProvider(staleness_hours=24)
        recent_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        entry = _make_registry_entry(fundamentals_updated_at=recent_time)

        assert provider._is_stale(entry) is False


# ── TestUpdateFundamentals ───────────────────────────────────────────


class TestUpdateFundamentals:
    """Tests for FundamentalsProvider.update_fundamentals()."""

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_updates_single_ticker_successfully(
        self, mock_ticker_cls, mock_get_session
    ):
        """Successful update returns True and sets attributes."""
        entry = _make_registry_entry(fundamentals_updated_at=None)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = entry
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_ticker = MagicMock()
        mock_ticker.info = _sample_info()
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        result = provider.update_fundamentals("AAPL", force=True)

        assert result is True
        mock_session.commit.assert_called_once()

    @patch("shit.market_data.fundamentals_provider.get_session")
    def test_skips_fresh_ticker_without_force(self, mock_get_session):
        """Fresh ticker without force=True returns False."""
        recent_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        entry = _make_registry_entry(fundamentals_updated_at=recent_time)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = entry
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        provider = FundamentalsProvider(staleness_hours=24)
        result = provider.update_fundamentals("AAPL", force=False)

        assert result is False
        mock_session.commit.assert_not_called()

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_updates_fresh_ticker_with_force(self, mock_ticker_cls, mock_get_session):
        """Fresh ticker with force=True still updates."""
        recent_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        entry = _make_registry_entry(fundamentals_updated_at=recent_time)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = entry
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_ticker = MagicMock()
        mock_ticker.info = _sample_info()
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        result = provider.update_fundamentals("AAPL", force=True)

        assert result is True
        mock_session.commit.assert_called_once()

    @patch("shit.market_data.fundamentals_provider.get_session")
    def test_returns_false_for_unregistered_ticker(self, mock_get_session):
        """Ticker not in registry returns False."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        provider = FundamentalsProvider()
        result = provider.update_fundamentals("UNKNOWN")

        assert result is False

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_returns_false_when_no_info_returned(
        self, mock_ticker_cls, mock_get_session
    ):
        """Empty info from yfinance returns False."""
        entry = _make_registry_entry(fundamentals_updated_at=None)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = entry
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        result = provider.update_fundamentals("BADTICKER", force=True)

        assert result is False

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch("shit.market_data.fundamentals_provider.yf.Ticker")
    def test_sets_fundamentals_updated_at(self, mock_ticker_cls, mock_get_session):
        """Successful update sets fundamentals_updated_at to now."""
        entry = _make_registry_entry(fundamentals_updated_at=None)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = entry
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_ticker = MagicMock()
        mock_ticker.info = _sample_info()
        mock_ticker_cls.return_value = mock_ticker

        provider = FundamentalsProvider()
        before = datetime.now(tz=timezone.utc)
        provider.update_fundamentals("AAPL", force=True)

        # Check that fundamentals_updated_at was set to roughly now
        assert entry.fundamentals_updated_at is not None
        assert entry.fundamentals_updated_at >= before


# ── TestUpdateAllFundamentals ────────────────────────────────────────


class TestUpdateAllFundamentals:
    """Tests for FundamentalsProvider.update_all_fundamentals()."""

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch.object(FundamentalsProvider, "update_fundamentals")
    def test_processes_all_active_tickers(self, mock_update, mock_get_session):
        """Batch mode calls update_fundamentals for each active ticker."""
        tickers = [
            _make_registry_entry(symbol="AAPL"),
            _make_registry_entry(symbol="TSLA"),
            _make_registry_entry(symbol="GOOG"),
        ]

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = tickers
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_update.return_value = True

        provider = FundamentalsProvider()
        stats = provider.update_all_fundamentals()

        assert stats["total"] == 3
        assert stats["updated"] == 3
        assert mock_update.call_count == 3

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch.object(FundamentalsProvider, "update_fundamentals")
    def test_respects_status_filter(self, mock_update, mock_get_session):
        """Batch mode filters by status."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        provider = FundamentalsProvider()
        stats = provider.update_all_fundamentals(status="inactive")

        assert stats["total"] == 0
        # Verify filter was called (the query chain was invoked)
        mock_session.query.return_value.filter.assert_called_once()

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch.object(FundamentalsProvider, "update_fundamentals")
    def test_counts_updated_skipped_failed(self, mock_update, mock_get_session):
        """Stats correctly count updated, skipped, and failed tickers."""
        tickers = [
            _make_registry_entry(symbol="AAPL"),
            _make_registry_entry(symbol="TSLA"),
            _make_registry_entry(symbol="BAD"),
        ]

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = tickers
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # AAPL updated, TSLA skipped, BAD fails
        mock_update.side_effect = [True, False, Exception("Network error")]

        provider = FundamentalsProvider()
        stats = provider.update_all_fundamentals()

        assert stats["total"] == 3
        assert stats["updated"] == 1
        assert stats["skipped"] == 1
        assert stats["failed"] == 1

    @patch("shit.market_data.fundamentals_provider.get_session")
    @patch.object(FundamentalsProvider, "update_fundamentals")
    def test_continues_on_individual_failures(self, mock_update, mock_get_session):
        """Batch mode continues processing after individual failures."""
        tickers = [
            _make_registry_entry(symbol="FAIL1"),
            _make_registry_entry(symbol="PASS"),
            _make_registry_entry(symbol="FAIL2"),
        ]

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = tickers
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_update.side_effect = [
            Exception("Error 1"),
            True,
            Exception("Error 2"),
        ]

        provider = FundamentalsProvider()
        stats = provider.update_all_fundamentals()

        # All three were attempted despite failures
        assert mock_update.call_count == 3
        assert stats["updated"] == 1
        assert stats["failed"] == 2
