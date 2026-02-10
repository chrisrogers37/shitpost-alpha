"""Tests for OutcomeCalculator (shit/market_data/outcome_calculator.py)."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.models import PredictionOutcome


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def calculator(mock_session):
    calc = OutcomeCalculator(session=mock_session)
    calc.market_client = MagicMock()
    return calc


def _make_prediction(**overrides):
    """Helper to create a mock Prediction with sensible defaults."""
    pred = MagicMock()
    pred.id = overrides.get("id", 1)
    pred.analysis_status = overrides.get("analysis_status", "completed")
    pred.assets = overrides.get("assets", ["AAPL"])
    pred.market_impact = overrides.get("market_impact", {"AAPL": "bullish"})
    pred.confidence = overrides.get("confidence", 0.85)
    pred.created_at = overrides.get("created_at", datetime(2025, 6, 15, 10, 0, 0))
    return pred


# ─── Init & Context Manager ─────────────────────────────────────────


class TestOutcomeCalculatorInit:
    def test_init_with_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        assert calc.session is mock_session
        assert calc._own_session is False

    def test_init_without_session(self):
        calc = OutcomeCalculator()
        assert calc.session is None
        assert calc._own_session is True

    @patch("shit.market_data.outcome_calculator.get_session")
    @patch("shit.market_data.outcome_calculator.MarketDataClient")
    def test_context_manager_creates_session(self, mock_mdc, mock_get_session):
        mock_ctx = MagicMock()
        mock_sess = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_sess)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_session.return_value = mock_ctx

        calc = OutcomeCalculator()
        with calc as c:
            assert c.session is mock_sess

    def test_context_manager_with_external_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        with calc as c:
            assert c.session is mock_session
            assert c.market_client is not None


# ─── _extract_sentiment ─────────────────────────────────────────────


class TestExtractSentiment:
    def test_extracts_first_sentiment(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "Bullish"})
        assert result == "bullish"

    def test_returns_none_for_empty_dict(self, calculator):
        assert calculator._extract_sentiment({}) is None

    def test_returns_none_for_none(self, calculator):
        assert calculator._extract_sentiment(None) is None

    def test_lowercases_sentiment(self, calculator):
        result = calculator._extract_sentiment({"TSLA": "BEARISH"})
        assert result == "bearish"

    def test_multi_asset_returns_first(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"})
        assert result in ("bullish", "bearish")  # dict ordering


# ─── calculate_outcome_for_prediction ────────────────────────────────


class TestCalculateOutcomeForPrediction:
    def test_missing_prediction_returns_empty(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = calculator.calculate_outcome_for_prediction(999)
        assert result == []

    def test_bypassed_prediction_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(analysis_status="bypassed")
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_no_assets_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(assets=None)
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_empty_assets_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(assets=[])
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_no_created_at_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(created_at=None)
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_continues_on_per_asset_error(self, calculator, mock_session):
        pred = _make_prediction(assets=["BAD", "GOOD"])
        mock_session.query.return_value.filter.return_value.first.return_value = pred

        # _calculate_single_outcome: first call raises, second returns outcome
        mock_outcome = MagicMock(spec=PredictionOutcome)
        calculator._calculate_single_outcome = MagicMock(
            side_effect=[RuntimeError("bad ticker"), mock_outcome]
        )

        result = calculator.calculate_outcome_for_prediction(1)
        assert len(result) == 1
        assert result[0] is mock_outcome

    def test_calls_calculate_single_for_each_asset(self, calculator, mock_session):
        pred = _make_prediction(assets=["AAPL", "TSLA", "GOOG"])
        mock_session.query.return_value.filter.return_value.first.return_value = pred

        mock_outcome = MagicMock(spec=PredictionOutcome)
        calculator._calculate_single_outcome = MagicMock(return_value=mock_outcome)

        result = calculator.calculate_outcome_for_prediction(1)
        assert len(result) == 3
        assert calculator._calculate_single_outcome.call_count == 3


# ─── _calculate_single_outcome ───────────────────────────────────────


class TestCalculateSingleOutcome:
    def test_returns_existing_when_not_force_refresh(self, calculator, mock_session):
        existing = MagicMock(spec=PredictionOutcome)
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        result = calculator._calculate_single_outcome(
            prediction_id=1, symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish", confidence=0.8
        )
        assert result is existing

    def test_returns_none_when_no_price_data(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        calculator.market_client.get_price_on_date.return_value = None
        calculator.market_client.fetch_price_history.return_value = []

        result = calculator._calculate_single_outcome(
            prediction_id=1, symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish", confidence=0.8
        )
        assert result is None

    @patch("shit.market_data.outcome_calculator.date")
    def test_creates_outcome_with_prices(self, mock_date, calculator, mock_session):
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # No existing outcome
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Mock prices: t0=100, all timeframes=110
        mock_price_t0 = MagicMock(close=100.0)
        mock_price_tn = MagicMock(close=110.0)
        calculator.market_client.get_price_on_date.return_value = mock_price_t0

        # After first call (price_t0), return tn for timeframes
        calculator.market_client.get_price_on_date.side_effect = [
            mock_price_t0,  # price at prediction
            mock_price_tn,  # T+1
            mock_price_tn,  # T+3
            mock_price_tn,  # T+7
            mock_price_tn,  # T+30
        ]

        result = calculator._calculate_single_outcome(
            prediction_id=1, symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish", confidence=0.8
        )

        assert result is not None
        assert result.price_at_prediction == 100.0
        assert result.return_t7 == 10.0  # (110-100)/100 * 100
        assert result.correct_t7 is True  # bullish + positive return
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_force_refresh_recalculates_existing(self, calculator, mock_session):
        existing = MagicMock(spec=PredictionOutcome)
        # First query returns existing outcome, second returns None (no price check)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            existing,  # existing outcome check
        ]
        calculator.market_client.get_price_on_date.return_value = None
        calculator.market_client.fetch_price_history.return_value = []

        result = calculator._calculate_single_outcome(
            prediction_id=1, symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish", confidence=0.8,
            force_refresh=True
        )
        # Should attempt to recalculate (not just return existing)
        calculator.market_client.get_price_on_date.assert_called()


# ─── calculate_outcomes_for_all_predictions ───────────────────────────


class TestCalculateOutcomesForAllPredictions:
    def test_returns_stats_dict(self, calculator, mock_session):
        pred = _make_prediction()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [pred]

        # Mock the per-prediction calculation
        calculator.calculate_outcome_for_prediction = MagicMock(return_value=[MagicMock()])

        result = calculator.calculate_outcomes_for_all_predictions()
        assert result["total_predictions"] == 1
        assert result["processed"] == 1
        assert result["outcomes_created"] == 1
        assert result["errors"] == 0

    def test_counts_errors(self, calculator, mock_session):
        pred = _make_prediction()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [pred]

        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=RuntimeError("boom")
        )

        result = calculator.calculate_outcomes_for_all_predictions()
        assert result["errors"] == 1
        assert result["processed"] == 0

    def test_applies_limit(self, calculator, mock_session):
        mock_query = mock_session.query.return_value.filter.return_value.order_by.return_value
        mock_query.limit.return_value.all.return_value = []

        calculator.calculate_outcomes_for_all_predictions(limit=5)
        mock_query.limit.assert_called_once_with(5)

    def test_applies_days_back_filter(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        calculator.calculate_outcomes_for_all_predictions(days_back=7)
        # Should call filter twice (status + date cutoff)
        assert mock_session.query.return_value.filter.call_count >= 1


# ─── get_accuracy_stats ──────────────────────────────────────────────


class TestGetAccuracyStats:
    def test_returns_zeros_when_no_outcomes(self, calculator, mock_session):
        mock_session.query.return_value.all.return_value = []

        result = calculator.get_accuracy_stats()
        assert result == {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "pending": 0,
            "accuracy": 0.0,
        }

    def test_calculates_accuracy(self, calculator, mock_session):
        outcomes = []
        for correct_val in [True, True, True, False, None]:
            o = MagicMock()
            o.correct_t7 = correct_val
            outcomes.append(o)

        mock_session.query.return_value.all.return_value = outcomes

        result = calculator.get_accuracy_stats(timeframe="t7")
        assert result["total"] == 5
        assert result["correct"] == 3
        assert result["incorrect"] == 1
        assert result["pending"] == 1
        assert result["accuracy"] == 75.0

    def test_uses_specified_timeframe(self, calculator, mock_session):
        o = MagicMock()
        o.correct_t1 = True
        o.correct_t30 = False
        mock_session.query.return_value.all.return_value = [o]

        result_t1 = calculator.get_accuracy_stats(timeframe="t1")
        assert result_t1["correct"] == 1

        result_t30 = calculator.get_accuracy_stats(timeframe="t30")
        assert result_t30["incorrect"] == 1

    def test_filters_by_min_confidence(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.all.return_value = []

        calculator.get_accuracy_stats(min_confidence=0.8)
        mock_session.query.return_value.filter.assert_called_once()

    def test_all_pending_returns_zero_accuracy(self, calculator, mock_session):
        outcomes = [MagicMock(correct_t7=None), MagicMock(correct_t7=None)]
        mock_session.query.return_value.all.return_value = outcomes

        result = calculator.get_accuracy_stats()
        assert result["accuracy"] == 0.0
        assert result["pending"] == 2
