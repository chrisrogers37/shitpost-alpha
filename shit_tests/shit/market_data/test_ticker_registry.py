"""
Tests for shit/market_data/ticker_registry.py - TickerRegistryService.

All tests use mocked get_session to avoid database dependencies.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock, PropertyMock

from shit.market_data.ticker_registry import TickerRegistryService
from shit.market_data.models import TickerRegistry, MarketPrice

SESSION_PATCH = "shit.market_data.ticker_registry.get_session"


def _mock_session():
    """Create a mock session with context manager support."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, session


class TestRegisterTickers:
    """Tests for TickerRegistryService.register_tickers."""

    def test_registers_new_ticker_successfully(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["AAPL"])

        assert newly == ["AAPL"]
        assert known == []
        session.add.assert_called_once()

    def test_skips_already_registered_ticker(self):
        ctx, session = _mock_session()
        existing = MagicMock(status="active")
        session.query.return_value.filter.return_value.first.return_value = existing

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["AAPL"])

        assert newly == []
        assert known == ["AAPL"]
        session.add.assert_not_called()

    def test_returns_newly_registered_and_already_known_lists(self):
        ctx, session = _mock_session()
        existing = MagicMock(status="active")
        # First call returns None (new), second returns existing
        session.query.return_value.filter.return_value.first.side_effect = [None, existing]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["NVDA", "AAPL"])

        assert newly == ["NVDA"]
        assert known == ["AAPL"]

    def test_handles_empty_symbol_list(self):
        service = TickerRegistryService()
        newly, known = service.register_tickers([])
        assert newly == []
        assert known == []

    def test_skips_invalid_symbol_format_space(self):
        ctx, session = _mock_session()

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["THE ECONOMY"])

        assert newly == []
        assert known == []
        session.add.assert_not_called()

    def test_skips_invalid_symbol_format_too_long(self):
        ctx, session = _mock_session()

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["A" * 21])

        assert newly == []
        assert known == []

    def test_skips_empty_string_symbol(self):
        ctx, session = _mock_session()

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers([""])

        assert newly == []
        assert known == []

    def test_uppercases_symbols(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["aapl"])

        assert newly == ["AAPL"]

    def test_sets_source_prediction_id(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.register_tickers(["TSLA"], source_prediction_id=42)

        added_obj = session.add.call_args[0][0]
        assert added_obj.source_prediction_id == 42

    def test_sets_first_seen_date_to_today(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.register_tickers(["MSFT"])

        added_obj = session.add.call_args[0][0]
        assert added_obj.first_seen_date == date.today()

    def test_default_status_is_active(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.register_tickers(["GOOG"])

        added_obj = session.add.call_args[0][0]
        assert added_obj.status == "active"

    def test_handles_integrity_error(self):
        from sqlalchemy.exc import IntegrityError

        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None
        session.commit.side_effect = IntegrityError("dup", {}, None)

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            newly, known = service.register_tickers(["AAPL"])

        # Should not raise, should rollback
        session.rollback.assert_called_once()


class TestGetNewTickers:
    """Tests for TickerRegistryService.get_new_tickers."""

    def test_returns_unknown_tickers(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.all.return_value = [("AAPL",)]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_new_tickers(["AAPL", "NVDA"])

        assert result == ["NVDA"]

    def test_returns_empty_when_all_known(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.all.return_value = [
            ("AAPL",),
            ("TSLA",),
        ]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_new_tickers(["AAPL", "TSLA"])

        assert result == []

    def test_handles_empty_input(self):
        service = TickerRegistryService()
        result = service.get_new_tickers([])
        assert result == []

    def test_uppercases_before_comparison(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.all.return_value = [("AAPL",)]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_new_tickers(["aapl", "nvda"])

        # aapl is known (uppercased match), nvda is new
        assert result == ["nvda"]


class TestGetActiveTickers:
    """Tests for TickerRegistryService.get_active_tickers."""

    def test_returns_only_active_tickers(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.all.return_value = [
            ("AAPL",),
            ("TSLA",),
        ]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_active_tickers()

        assert result == ["AAPL", "TSLA"]

    def test_returns_empty_when_no_active(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.all.return_value = []

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_active_tickers()

        assert result == []


class TestMarkTickerInvalid:
    """Tests for TickerRegistryService.mark_ticker_invalid."""

    def test_marks_existing_ticker_invalid(self):
        ctx, session = _mock_session()
        entry = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = entry

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.mark_ticker_invalid("FAKE", "no data")

        assert entry.status == "invalid"
        assert entry.status_reason == "no data"

    def test_sets_status_reason(self):
        ctx, session = _mock_session()
        entry = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = entry

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.mark_ticker_invalid("FAKE", "yfinance returned no price data")

        assert entry.status_reason == "yfinance returned no price data"

    def test_handles_nonexistent_ticker_gracefully(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            # Should not raise
            service.mark_ticker_invalid("NOPE", "reason")

        session.commit.assert_not_called()

    def test_truncates_long_reason(self):
        ctx, session = _mock_session()
        entry = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = entry

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.mark_ticker_invalid("FAKE", "x" * 300)

        assert len(entry.status_reason) == 255


class TestUpdatePriceMetadata:
    """Tests for TickerRegistryService.update_price_metadata."""

    def test_updates_metadata_from_market_prices(self):
        ctx, session = _mock_session()
        entry = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = entry

        stats_result = MagicMock()
        stats_result.earliest = date(2024, 1, 1)
        stats_result.latest = date(2024, 12, 31)
        stats_result.count = 250

        # First query returns entry, second returns stats
        query_mock = MagicMock()
        session.query.side_effect = [
            # First query chain: TickerRegistry lookup
            MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=entry)))),
            # Second query chain: stats lookup
            MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=stats_result)))),
        ]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.update_price_metadata("AAPL")

        assert entry.price_data_start == date(2024, 1, 1)
        assert entry.price_data_end == date(2024, 12, 31)
        assert entry.total_price_records == 250

    def test_handles_nonexistent_ticker(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            # Should not raise
            service.update_price_metadata("NOPE")

    def test_handles_zero_price_records(self):
        ctx, session = _mock_session()
        entry = MagicMock()
        stats_result = MagicMock()
        stats_result.count = 0

        session.query.side_effect = [
            MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=entry)))),
            MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=stats_result)))),
        ]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            service.update_price_metadata("AAPL")

        # Should not update since count is 0
        session.commit.assert_not_called()


class TestGetRegistryStats:
    """Tests for TickerRegistryService.get_registry_stats."""

    def test_returns_correct_counts(self):
        ctx, session = _mock_session()
        # Each scalar call returns a different count
        session.query.return_value.scalar.return_value = 10
        session.query.return_value.filter.return_value.scalar.side_effect = [5, 3, 2]

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_registry_stats()

        assert result["total"] == 10
        assert result["active"] == 5
        assert result["invalid"] == 3
        assert result["inactive"] == 2

    def test_returns_zeros_when_empty(self):
        ctx, session = _mock_session()
        session.query.return_value.scalar.return_value = 0
        session.query.return_value.filter.return_value.scalar.return_value = 0

        with patch(SESSION_PATCH, return_value=ctx):
            service = TickerRegistryService()
            result = service.get_registry_stats()

        assert result["total"] == 0
        assert result["active"] == 0
        assert result["invalid"] == 0
        assert result["inactive"] == 0
