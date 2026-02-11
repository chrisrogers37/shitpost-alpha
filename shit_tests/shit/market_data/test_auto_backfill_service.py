"""
Tests for shit/market_data/auto_backfill_service.py - AutoBackfillService with registry integration.

Tests the integration between AutoBackfillService and TickerRegistryService,
including registration on process, metadata updates on backfill, and invalid marking.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from datetime import date
from unittest.mock import patch, MagicMock, PropertyMock

from shit.market_data.auto_backfill_service import (
    AutoBackfillService,
    auto_backfill_prediction,
    auto_backfill_recent,
    auto_backfill_all,
)

SESSION_PATCH = "shit.market_data.auto_backfill_service.get_session"
CLIENT_PATCH = "shit.market_data.auto_backfill_service.MarketDataClient"
CALC_PATCH = "shit.market_data.auto_backfill_service.OutcomeCalculator"
REGISTRY_PATCH = "shit.market_data.auto_backfill_service.TickerRegistryService"


def _mock_session():
    """Create a mock session with context manager support."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, session


def _mock_client(prices=None):
    """Create a mock MarketDataClient with context manager support."""
    client = MagicMock()
    client.fetch_price_history.return_value = prices or []
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestBackfillTicker:
    """Tests for AutoBackfillService.backfill_ticker."""

    def test_successful_backfill_returns_true(self):
        client = _mock_client(prices=[MagicMock()] * 100)
        with patch(CLIENT_PATCH, return_value=client), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            result = service.backfill_ticker("AAPL")
        assert result is True

    def test_returns_false_for_no_data(self):
        client = _mock_client(prices=[])
        with patch(CLIENT_PATCH, return_value=client), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            result = service.backfill_ticker("FAKE")
        assert result is False

    def test_skips_invalid_symbols(self):
        with patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            assert service.backfill_ticker("") is False
            assert service.backfill_ticker("A" * 11) is False
            assert service.backfill_ticker("HAS SPACE") is False

    def test_skips_krx_symbols(self):
        with patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            result = service.backfill_ticker("KRX:005930")
        assert result is False

    def test_handles_yfinance_exception(self):
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.fetch_price_history.side_effect = Exception("yfinance error")

        with patch(CLIENT_PATCH, return_value=client), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            result = service.backfill_ticker("AAPL")
        assert result is False

    def test_updates_registry_on_success(self):
        client = _mock_client(prices=[MagicMock()] * 50)
        mock_registry = MagicMock()

        with patch(CLIENT_PATCH, return_value=client), patch(REGISTRY_PATCH, return_value=mock_registry):
            service = AutoBackfillService()
            service.backfill_ticker("AAPL")

        service.registry.update_price_metadata.assert_called_once_with("AAPL")

    def test_marks_invalid_on_no_data(self):
        client = _mock_client(prices=[])
        mock_registry = MagicMock()

        with patch(CLIENT_PATCH, return_value=client), patch(REGISTRY_PATCH, return_value=mock_registry):
            service = AutoBackfillService()
            service.backfill_ticker("FAKE")

        service.registry.mark_ticker_invalid.assert_called_once_with(
            "FAKE", "yfinance returned no price data"
        )


class TestProcessSinglePrediction:
    """Tests for AutoBackfillService.process_single_prediction."""

    def test_backfills_missing_tickers_and_calculates_outcome(self):
        ctx, session = _mock_session()
        prediction = MagicMock()
        prediction.id = 1
        prediction.assets = ["AAPL", "TSLA"]
        session.query.return_value.filter.return_value.first.return_value = prediction

        client = _mock_client(prices=[MagicMock()] * 10)
        calc = MagicMock()
        calc.calculate_outcome_for_prediction.return_value = [MagicMock()]
        calc.__enter__ = MagicMock(return_value=calc)
        calc.__exit__ = MagicMock(return_value=False)

        with (
            patch(SESSION_PATCH, return_value=ctx),
            patch(CLIENT_PATCH, return_value=client),
            patch(CALC_PATCH, return_value=calc),
            patch(REGISTRY_PATCH),
        ):
            service = AutoBackfillService()
            # Mock get_missing_tickers to return one missing ticker
            service.get_missing_tickers = MagicMock(return_value=["TSLA"])
            backfilled, outcomes = service.process_single_prediction(1)

        assert backfilled == 1
        assert outcomes == 1

    def test_registers_tickers_in_registry(self):
        ctx, session = _mock_session()
        prediction = MagicMock()
        prediction.id = 42
        prediction.assets = ["AAPL"]
        session.query.return_value.filter.return_value.first.return_value = prediction

        mock_registry = MagicMock()
        mock_registry.register_tickers.return_value = (["AAPL"], [])

        calc = MagicMock()
        calc.calculate_outcome_for_prediction.return_value = []
        calc.__enter__ = MagicMock(return_value=calc)
        calc.__exit__ = MagicMock(return_value=False)

        with (
            patch(SESSION_PATCH, return_value=ctx),
            patch(CALC_PATCH, return_value=calc),
            patch(REGISTRY_PATCH, return_value=mock_registry),
        ):
            service = AutoBackfillService()
            service.get_missing_tickers = MagicMock(return_value=[])
            service.process_single_prediction(42)

        service.registry.register_tickers.assert_called_once_with(
            ["AAPL"], source_prediction_id=42
        )

    def test_handles_prediction_not_found(self):
        ctx, session = _mock_session()
        session.query.return_value.filter.return_value.first.return_value = None

        with patch(SESSION_PATCH, return_value=ctx), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            backfilled, outcomes = service.process_single_prediction(999)

        assert backfilled == 0
        assert outcomes == 0

    def test_handles_prediction_with_no_assets(self):
        ctx, session = _mock_session()
        prediction = MagicMock()
        prediction.id = 1
        prediction.assets = []
        session.query.return_value.filter.return_value.first.return_value = prediction

        with patch(SESSION_PATCH, return_value=ctx), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            backfilled, outcomes = service.process_single_prediction(1)

        assert backfilled == 0
        assert outcomes == 0

    def test_handles_outcome_calculation_failure(self):
        ctx, session = _mock_session()
        prediction = MagicMock()
        prediction.id = 1
        prediction.assets = ["AAPL"]
        session.query.return_value.filter.return_value.first.return_value = prediction

        calc = MagicMock()
        calc.calculate_outcome_for_prediction.side_effect = Exception("calc error")
        calc.__enter__ = MagicMock(return_value=calc)
        calc.__exit__ = MagicMock(return_value=False)

        with (
            patch(SESSION_PATCH, return_value=ctx),
            patch(CALC_PATCH, return_value=calc),
            patch(REGISTRY_PATCH),
        ):
            service = AutoBackfillService()
            service.get_missing_tickers = MagicMock(return_value=[])
            backfilled, outcomes = service.process_single_prediction(1)

        assert outcomes == 0


class TestProcessNewPredictions:
    """Tests for AutoBackfillService.process_new_predictions."""

    def test_processes_recent_predictions(self):
        ctx, session = _mock_session()
        pred1 = MagicMock(id=1)
        pred2 = MagicMock(id=2)
        query = MagicMock()
        query.all.return_value = [pred1, pred2]
        session.query.return_value.filter.return_value.order_by.return_value = query

        with patch(SESSION_PATCH, return_value=ctx), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            service.process_single_prediction = MagicMock(return_value=(1, 1))
            stats = service.process_new_predictions(days_back=7)

        assert stats["predictions_processed"] == 2

    def test_respects_limit_parameter(self):
        ctx, session = _mock_session()
        pred1 = MagicMock(id=1)
        query = MagicMock()
        limited_query = MagicMock()
        limited_query.all.return_value = [pred1]
        query.limit.return_value = limited_query
        session.query.return_value.filter.return_value.order_by.return_value = query

        with patch(SESSION_PATCH, return_value=ctx), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            service.process_single_prediction = MagicMock(return_value=(0, 0))
            stats = service.process_new_predictions(days_back=7, limit=1)

        assert stats["predictions_processed"] == 1

    def test_handles_errors_gracefully(self):
        ctx, session = _mock_session()
        pred1 = MagicMock(id=1)
        query = MagicMock()
        query.all.return_value = [pred1]
        session.query.return_value.filter.return_value.order_by.return_value = query

        with patch(SESSION_PATCH, return_value=ctx), patch(REGISTRY_PATCH):
            service = AutoBackfillService()
            service.process_single_prediction = MagicMock(
                side_effect=Exception("processing error")
            )
            stats = service.process_new_predictions(days_back=7)

        assert stats["errors"] == 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_auto_backfill_prediction_calls_service(self):
        with patch(REGISTRY_PATCH):
            with patch.object(
                AutoBackfillService,
                "process_single_prediction",
                return_value=(1, 1),
            ):
                result = auto_backfill_prediction(42)
        assert result is True

    def test_auto_backfill_recent_calls_service(self):
        expected = {"predictions_processed": 5, "assets_backfilled": 2}
        with patch(REGISTRY_PATCH):
            with patch.object(
                AutoBackfillService,
                "process_new_predictions",
                return_value=expected,
            ):
                result = auto_backfill_recent(days=7)
        assert result == expected

    def test_auto_backfill_all_calls_service(self):
        expected = {"total_assets": 10, "missing_assets": 3, "backfilled": 3, "failed": 0}
        with patch(REGISTRY_PATCH):
            with patch.object(
                AutoBackfillService,
                "process_all_missing_assets",
                return_value=expected,
            ):
                result = auto_backfill_all()
        assert result == expected
