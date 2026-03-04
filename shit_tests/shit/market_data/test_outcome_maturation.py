"""Tests for outcome maturation pipeline (OutcomeCalculator.mature_outcomes)."""

import os

# Ensure DATABASE_URL is set before any market_data imports trigger sync_session
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, call
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


def _make_incomplete_outcome(**overrides):
    """Helper to create a mock PredictionOutcome with is_complete=False."""
    outcome = MagicMock(spec=PredictionOutcome)
    outcome.prediction_id = overrides.get("prediction_id", 1)
    outcome.symbol = overrides.get("symbol", "AAPL")
    outcome.is_complete = overrides.get("is_complete", False)
    outcome.price_at_prediction = overrides.get("price_at_prediction", 100.0)
    outcome.price_t1 = overrides.get("price_t1", 101.0)
    outcome.price_t3 = overrides.get("price_t3", 102.0)
    outcome.price_t7 = overrides.get("price_t7", None)  # Not yet matured
    outcome.price_t30 = overrides.get("price_t30", None)  # Not yet matured
    outcome.prediction_date = overrides.get("prediction_date", date(2025, 6, 15))
    return outcome


# ─── mature_outcomes ────────────────────────────────────────────────


class TestMatureOutcomes:
    def test_returns_stats_dict_with_all_keys(self, calculator, mock_session):
        """mature_outcomes() returns a dict with the expected stat keys."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = calculator.mature_outcomes()
        assert "total_incomplete" in result
        assert "matured" in result
        assert "newly_complete" in result
        assert "still_incomplete" in result
        assert "errors" in result
        assert "skipped" in result

    def test_no_incomplete_outcomes(self, calculator, mock_session):
        """When no incomplete outcomes exist, stats show zero work."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = calculator.mature_outcomes()
        assert result["total_incomplete"] == 0
        assert result["matured"] == 0
        assert result["newly_complete"] == 0

    def test_processes_unique_prediction_ids(self, calculator, mock_session):
        """Multiple outcomes for same prediction_id are processed once."""
        o1 = _make_incomplete_outcome(prediction_id=1, symbol="AAPL")
        o2 = _make_incomplete_outcome(prediction_id=1, symbol="TSLA")
        o3 = _make_incomplete_outcome(prediction_id=2, symbol="GOOG")
        mock_session.query.return_value.filter.return_value.all.return_value = [o1, o2, o3]

        # Mock calculate_outcome_for_prediction to return outcomes
        mock_outcome_complete = MagicMock(is_complete=True)
        mock_outcome_incomplete = MagicMock(is_complete=False)
        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=[
                [mock_outcome_complete, mock_outcome_incomplete],  # pred 1: 2 outcomes
                [mock_outcome_complete],  # pred 2: 1 outcome
            ]
        )

        result = calculator.mature_outcomes()
        assert calculator.calculate_outcome_for_prediction.call_count == 2
        assert result["matured"] == 3
        assert result["newly_complete"] == 2
        assert result["still_incomplete"] == 1

    def test_applies_limit(self, calculator, mock_session):
        """The limit parameter is passed to the query."""
        mock_query = mock_session.query.return_value.filter.return_value
        mock_query.limit.return_value.all.return_value = []

        calculator.mature_outcomes(limit=50)
        mock_query.limit.assert_called_once_with(50)

    def test_no_limit_skips_limit_call(self, calculator, mock_session):
        """When limit is None, .limit() is not called on the query."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        calculator.mature_outcomes(limit=None)
        mock_session.query.return_value.filter.return_value.limit.assert_not_called()

    def test_handles_errors_gracefully(self, calculator, mock_session):
        """Errors for one prediction don't prevent processing others."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        o2 = _make_incomplete_outcome(prediction_id=2)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1, o2]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=[RuntimeError("db error"), [mock_outcome]]
        )

        result = calculator.mature_outcomes()
        assert result["errors"] == 1
        assert result["matured"] == 1
        assert result["newly_complete"] == 1

    def test_calls_force_refresh_false(self, calculator, mock_session):
        """mature_outcomes passes force_refresh=False to leverage the fixed early-return."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        calculator.calculate_outcome_for_prediction = MagicMock(return_value=[])

        calculator.mature_outcomes()
        calculator.calculate_outcome_for_prediction.assert_called_once_with(
            prediction_id=1, force_refresh=False
        )

    def test_emits_event_when_flag_true(self, calculator, mock_session):
        """When emit_event=True and outcomes matured, the code path doesn't crash."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            return_value=[mock_outcome]
        )

        # The event emission uses a deferred import inside try/except,
        # so it gracefully handles missing event infrastructure
        result = calculator.mature_outcomes(emit_event=True)
        assert result["matured"] == 1

    def test_no_event_when_flag_false(self, calculator, mock_session):
        """When emit_event=False (default), no event is emitted."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            return_value=[mock_outcome]
        )

        # Should not raise even without event infrastructure
        result = calculator.mature_outcomes(emit_event=False)
        assert result["matured"] == 1


# ─── Fixed early-return logic ──────────────────────────────────────


class TestFixedEarlyReturn:
    """Tests for the fixed early-return in _calculate_single_outcome."""

    def test_returns_existing_when_complete_and_no_force(self, calculator, mock_session):
        """Complete outcomes are still returned immediately without re-evaluation."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = True
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
        )
        assert result is existing
        # Should NOT have tried to get prices
        calculator.market_client.get_price_on_date.assert_not_called()

    def test_re_evaluates_when_incomplete_and_no_force(self, calculator, mock_session):
        """Incomplete outcomes fall through to re-evaluation."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = False
        existing.price_at_prediction = 100.0
        existing.price_t1 = 101.0  # Already filled
        existing.price_t3 = None   # Not yet filled
        existing.price_t7 = None
        existing.price_t30 = None
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        # Provide price data for the re-evaluation
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=False,
        )
        # Should have attempted to get prices (fell through the early-return)
        calculator.market_client.get_price_on_date.assert_called()

    def test_force_refresh_still_recalculates_complete(self, calculator, mock_session):
        """force_refresh=True always recalculates, even when complete."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = True
        existing.price_at_prediction = 100.0
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=True,
        )
        calculator.market_client.get_price_on_date.assert_called()


# ─── Skip filled timeframes ────────────────────────────────────────


class TestSkipFilledTimeframes:
    """Tests for the optimization that skips already-filled timeframes."""

    @patch("shit.market_data.outcome_calculator.date")
    def test_skips_filled_timeframe(self, mock_date, calculator, mock_session):
        """Timeframes with existing prices are not re-fetched."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # Existing incomplete outcome with T+1 already filled
        existing = PredictionOutcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            prediction_sentiment="bullish",
            prediction_confidence=0.8,
            price_at_prediction=100.0,
            price_t1=101.0,
            return_t1=1.0,
            correct_t1=True,
            pnl_t1=10.0,
            is_complete=False,
        )
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        # Price data for unfilled timeframes
        mock_price_t0 = MagicMock(close=100.0)
        mock_price_tn = MagicMock(close=110.0)

        # get_price_on_date: first call is for price_t0, then for unfilled timeframes
        calculator.market_client.get_price_on_date.side_effect = [
            mock_price_t0,  # price at prediction (t0)
            mock_price_tn,  # T+3 (was NULL)
            mock_price_tn,  # T+7 (was NULL)
            mock_price_tn,  # T+30 (was NULL)
        ]

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=False,
        )

        # T+1 was already filled, so only 4 calls: t0 + t3 + t7 + t30
        # (not 5 calls which would include t1)
        assert calculator.market_client.get_price_on_date.call_count == 4


# ─── CLI command ────────────────────────────────────────────────────


class TestMatureOutcomesCLI:
    """Tests for the mature-outcomes CLI command."""

    @pytest.fixture
    def runner(self):
        from click.testing import CliRunner
        return CliRunner()

    def test_command_exists(self, runner):
        from shit.market_data.cli import cli
        result = runner.invoke(cli, ["mature-outcomes", "--help"])
        assert result.exit_code == 0
        assert "Re-evaluate incomplete prediction outcomes" in result.output

    def test_command_in_cli_help(self, runner):
        from shit.market_data.cli import cli
        result = runner.invoke(cli, ["--help"])
        assert "mature-outcomes" in result.output

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_default_run(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 5,
            "matured": 3,
            "newly_complete": 2,
            "still_incomplete": 1,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes"])
        assert result.exit_code == 0
        assert "Incomplete outcomes found: 5" in result.output
        assert "Newly complete: 2" in result.output
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=None, emit_event=False
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_with_limit(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 2,
            "matured": 2,
            "newly_complete": 2,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes", "--limit", "10"])
        assert result.exit_code == 0
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=10, emit_event=False
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_with_emit_event_flag(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 0,
            "matured": 0,
            "newly_complete": 0,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes", "--emit-event"])
        assert result.exit_code == 0
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=None, emit_event=True
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_error_handling(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.side_effect = Exception("DB connection failed")
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes"])
        assert result.exit_code != 0
