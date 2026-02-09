"""
Tests for shit/market_data/cli.py - Market data CLI commands.

Tests the auto-pipeline command and its integration with
auto_backfill_recent and OutcomeCalculator.
"""

import os

# Ensure DATABASE_URL is set before any market_data imports trigger sync_session
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from shit.market_data.cli import cli

# auto_backfill_recent and get_service_logger are imported inside the
# auto_pipeline function body (deferred imports), so patch at their source module.
BACKFILL_PATCH = "shit.market_data.auto_backfill_service.auto_backfill_recent"
LOGGER_PATCH = "shit.logging.get_service_logger"
# OutcomeCalculator is imported at the top of cli.py, so patch on the cli module.
CALC_PATCH = "shit.market_data.cli.OutcomeCalculator"


def _mock_calculator(outcome_stats):
    """Create a mock OutcomeCalculator with context manager support."""
    calc = MagicMock()
    calc.calculate_outcomes_for_all_predictions.return_value = outcome_stats
    calc.__enter__ = MagicMock(return_value=calc)
    calc.__exit__ = MagicMock(return_value=False)
    return calc


class TestAutoPipelineCommand:
    """Test cases for the auto-pipeline CLI command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_auto_pipeline_command_exists(self, runner):
        """Test that auto-pipeline command is registered and callable."""
        result = runner.invoke(cli, ["auto-pipeline", "--help"])
        assert result.exit_code == 0
        assert "Run the full market data pipeline" in result.output

    def test_auto_pipeline_help_shows_options(self, runner):
        """Test that help shows --days-back and --limit options."""
        result = runner.invoke(cli, ["auto-pipeline", "--help"])
        assert result.exit_code == 0
        assert "--days-back" in result.output
        assert "--limit" in result.output

    def test_auto_pipeline_default_args(self, runner):
        """Test auto-pipeline with default arguments (days_back=7, limit=None)."""
        bf_stats = {"predictions_processed": 10, "assets_backfilled": 5, "errors": 0}
        oc_stats = {
            "total_predictions": 10,
            "processed": 10,
            "outcomes_created": 8,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats) as mock_bf,
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 0
            mock_bf.assert_called_once_with(days=7)
            calc.calculate_outcomes_for_all_predictions.assert_called_once_with(
                limit=None, days_back=7
            )

    def test_auto_pipeline_custom_days_back(self, runner):
        """Test auto-pipeline with custom --days-back value."""
        bf_stats = {"predictions_processed": 20, "assets_backfilled": 10, "errors": 0}
        oc_stats = {
            "total_predictions": 20,
            "processed": 20,
            "outcomes_created": 15,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats) as mock_bf,
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline", "--days-back", "30"])

            assert result.exit_code == 0
            mock_bf.assert_called_once_with(days=30)
            calc.calculate_outcomes_for_all_predictions.assert_called_once_with(
                limit=None, days_back=30
            )

    def test_auto_pipeline_with_limit(self, runner):
        """Test auto-pipeline with --limit option."""
        bf_stats = {"predictions_processed": 5, "assets_backfilled": 3, "errors": 0}
        oc_stats = {
            "total_predictions": 5,
            "processed": 5,
            "outcomes_created": 4,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline", "--limit", "50"])

            assert result.exit_code == 0
            calc.calculate_outcomes_for_all_predictions.assert_called_once_with(
                limit=50, days_back=7
            )

    def test_auto_pipeline_with_all_options(self, runner):
        """Test auto-pipeline with both --days-back and --limit."""
        bf_stats = {"predictions_processed": 3, "assets_backfilled": 2, "errors": 0}
        oc_stats = {
            "total_predictions": 3,
            "processed": 3,
            "outcomes_created": 3,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats) as mock_bf,
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(
                cli, ["auto-pipeline", "--days-back", "14", "--limit", "100"]
            )

            assert result.exit_code == 0
            mock_bf.assert_called_once_with(days=14)
            calc.calculate_outcomes_for_all_predictions.assert_called_once_with(
                limit=100, days_back=14
            )

    def test_auto_pipeline_backfill_failure_exits_1(self, runner):
        """Test that auto-pipeline exits with code 1 when backfill raises."""
        with (
            patch(BACKFILL_PATCH, side_effect=Exception("Database connection failed")),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 1

    def test_auto_pipeline_outcome_failure_exits_1(self, runner):
        """Test that auto-pipeline exits with code 1 when outcome calc raises."""
        bf_stats = {"predictions_processed": 5, "assets_backfilled": 3, "errors": 0}

        calc = MagicMock()
        calc.calculate_outcomes_for_all_predictions.side_effect = Exception(
            "Calc failed"
        )
        calc.__enter__ = MagicMock(return_value=calc)
        calc.__exit__ = MagicMock(return_value=False)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 1

    def test_auto_pipeline_displays_results(self, runner):
        """Test that auto-pipeline displays backfill and outcome results."""
        bf_stats = {"predictions_processed": 10, "assets_backfilled": 5, "errors": 0}
        oc_stats = {
            "total_predictions": 10,
            "processed": 10,
            "outcomes_created": 8,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 0
            assert "Predictions processed: 10" in result.output
            assert "Assets backfilled: 5" in result.output
            assert "Total predictions: 10" in result.output
            assert "Outcomes created: 8" in result.output

    def test_auto_pipeline_reports_errors_in_output(self, runner):
        """Test that auto-pipeline reports error counts when they occur."""
        bf_stats = {"predictions_processed": 10, "assets_backfilled": 5, "errors": 2}
        oc_stats = {
            "total_predictions": 10,
            "processed": 8,
            "outcomes_created": 6,
            "errors": 1,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 0
            assert "3 errors" in result.output

    def test_auto_pipeline_calls_steps_in_order(self, runner):
        """Test that backfill runs before outcome calculation."""
        call_order = []

        def mock_backfill(days):
            call_order.append("backfill")
            return {"predictions_processed": 1, "assets_backfilled": 1, "errors": 0}

        oc_stats = {
            "total_predictions": 1,
            "processed": 1,
            "outcomes_created": 1,
            "errors": 0,
        }

        calc = MagicMock()

        def mock_calculate(**kwargs):
            call_order.append("outcomes")
            return oc_stats

        calc.calculate_outcomes_for_all_predictions.side_effect = mock_calculate
        calc.__enter__ = MagicMock(return_value=calc)
        calc.__exit__ = MagicMock(return_value=False)

        with (
            patch(BACKFILL_PATCH, side_effect=mock_backfill),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline"])

            assert result.exit_code == 0
            assert call_order == ["backfill", "outcomes"]


class TestAutoPipelineArgParsing:
    """Test argument parsing for auto-pipeline command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_days_back_short_flag(self, runner):
        """Test -d short flag for --days-back."""
        bf_stats = {"predictions_processed": 0, "assets_backfilled": 0, "errors": 0}
        oc_stats = {
            "total_predictions": 0,
            "processed": 0,
            "outcomes_created": 0,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats) as mock_bf,
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline", "-d", "21"])

            assert result.exit_code == 0
            mock_bf.assert_called_once_with(days=21)

    def test_limit_short_flag(self, runner):
        """Test -l short flag for --limit."""
        bf_stats = {"predictions_processed": 0, "assets_backfilled": 0, "errors": 0}
        oc_stats = {
            "total_predictions": 0,
            "processed": 0,
            "outcomes_created": 0,
            "errors": 0,
        }
        calc = _mock_calculator(oc_stats)

        with (
            patch(BACKFILL_PATCH, return_value=bf_stats),
            patch(CALC_PATCH, return_value=calc),
            patch(LOGGER_PATCH, return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["auto-pipeline", "-l", "25"])

            assert result.exit_code == 0
            calc.calculate_outcomes_for_all_predictions.assert_called_once_with(
                limit=25, days_back=7
            )

    def test_invalid_days_back_type(self, runner):
        """Test that non-integer --days-back is rejected."""
        result = runner.invoke(cli, ["auto-pipeline", "--days-back", "abc"])
        assert result.exit_code != 0

    def test_invalid_limit_type(self, runner):
        """Test that non-integer --limit is rejected."""
        result = runner.invoke(cli, ["auto-pipeline", "--limit", "xyz"])
        assert result.exit_code != 0


class TestCliGroupRegistration:
    """Test that auto-pipeline is properly registered in the CLI group."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_auto_pipeline_in_help(self, runner):
        """Test that auto-pipeline appears in the main CLI help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "auto-pipeline" in result.output

    def test_all_expected_commands_present(self, runner):
        """Test that all expected commands are registered."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        expected_commands = [
            "auto-pipeline",
            "fetch-prices",
            "update-all-prices",
            "calculate-outcomes",
            "auto-backfill",
            "backfill-all-missing",
            "accuracy-report",
            "price-stats",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in CLI help"
