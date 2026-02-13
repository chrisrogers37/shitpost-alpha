"""
Tests for shitty_ui data layer functions.
Tests all database query functions for the prediction performance dashboard.
"""

import pytest
from unittest.mock import patch
from datetime import datetime
import pandas as pd
import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


@pytest.fixture(autouse=True)
def clear_data_caches():
    """Clear all data layer caches before and after each test."""
    from data import clear_all_caches

    clear_all_caches()
    yield
    clear_all_caches()


class TestGetPredictionStats:
    """Tests for get_prediction_stats function."""

    @patch("data.execute_query")
    def test_returns_stats_dict(self, mock_execute):
        """Test that function returns a dictionary with expected keys."""
        from data import get_prediction_stats

        mock_execute.return_value = (
            [(100, 80, 60, 20, 0.75, 45)],
            [
                "total_posts",
                "analyzed_posts",
                "completed_analyses",
                "bypassed_posts",
                "avg_confidence",
                "high_confidence_predictions",
            ],
        )

        result = get_prediction_stats()

        assert isinstance(result, dict)
        assert "total_posts" in result
        assert "analyzed_posts" in result
        assert "completed_analyses" in result
        assert "bypassed_posts" in result
        assert "avg_confidence" in result
        assert "high_confidence_predictions" in result

    @patch("data.execute_query")
    def test_handles_null_values(self, mock_execute):
        """Test that function handles NULL values from database."""
        from data import get_prediction_stats

        mock_execute.return_value = (
            [(None, None, None, None, None, None)],
            [
                "total_posts",
                "analyzed_posts",
                "completed_analyses",
                "bypassed_posts",
                "avg_confidence",
                "high_confidence_predictions",
            ],
        )

        result = get_prediction_stats()

        assert result["total_posts"] == 0
        assert result["analyzed_posts"] == 0
        assert result["avg_confidence"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_empty_result(self, mock_execute):
        """Test that function returns defaults when no rows returned."""
        from data import get_prediction_stats

        mock_execute.return_value = ([], [])

        result = get_prediction_stats()

        assert result["total_posts"] == 0
        assert result["avg_confidence"] == 0.0


class TestGetRecentSignals:
    """Tests for get_recent_signals function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_recent_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test text",
                    "post123",
                    1,
                    ["AAPL"],
                    {"AAPL": "bullish"},
                    0.8,
                    "thesis",
                    "completed",
                    "AAPL",
                    "bullish",
                    1.5,
                    2.0,
                    3.0,
                    True,
                    True,
                    True,
                    30.0,
                    True,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "analysis_status",
                "symbol",
                "prediction_sentiment",
                "return_t1",
                "return_t3",
                "return_t7",
                "correct_t1",
                "correct_t3",
                "correct_t7",
                "pnl_t7",
                "is_complete",
            ],
        )

        result = get_recent_signals(limit=10)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_recent_signals

        mock_execute.return_value = ([], [])

        get_recent_signals(limit=25, min_confidence=0.7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 25
        assert call_args[1]["min_confidence"] == 0.7

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_recent_signals

        mock_execute.side_effect = Exception("Database error")

        result = get_recent_signals()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetPerformanceMetrics:
    """Tests for get_performance_metrics function."""

    @patch("data.execute_query")
    def test_returns_metrics_dict(self, mock_execute):
        """Test that function returns a dictionary with performance metrics."""
        from data import get_performance_metrics

        mock_execute.return_value = (
            [(100, 60, 40, 100, 2.5, 2500.0, 0.72)],
            [
                "total_outcomes",
                "correct_t7",
                "incorrect_t7",
                "evaluated_t7",
                "avg_return_t7",
                "total_pnl_t7",
                "avg_confidence",
            ],
        )

        result = get_performance_metrics()

        assert isinstance(result, dict)
        assert result["total_outcomes"] == 100
        assert result["correct_predictions"] == 60
        assert result["accuracy_t7"] == 60.0
        assert result["avg_return_t7"] == 2.5
        assert result["total_pnl_t7"] == 2500.0

    @patch("data.execute_query")
    def test_calculates_accuracy_correctly(self, mock_execute):
        """Test that accuracy is calculated correctly."""
        from data import get_performance_metrics

        mock_execute.return_value = (
            [(50, 35, 15, 50, 1.5, 1500.0, 0.65)],
            [
                "total_outcomes",
                "correct_t7",
                "incorrect_t7",
                "evaluated_t7",
                "avg_return_t7",
                "total_pnl_t7",
                "avg_confidence",
            ],
        )

        result = get_performance_metrics()

        assert result["accuracy_t7"] == 70.0  # 35/50 = 70%

    @patch("data.execute_query")
    def test_handles_zero_evaluated(self, mock_execute):
        """Test that function handles zero evaluated predictions."""
        from data import get_performance_metrics

        mock_execute.return_value = (
            [(0, 0, 0, 0, None, 0.0, None)],
            [
                "total_outcomes",
                "correct_t7",
                "incorrect_t7",
                "evaluated_t7",
                "avg_return_t7",
                "total_pnl_t7",
                "avg_confidence",
            ],
        )

        result = get_performance_metrics()

        assert result["accuracy_t7"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_performance_metrics

        mock_execute.side_effect = Exception("Database error")

        result = get_performance_metrics()

        assert result["total_outcomes"] == 0
        assert result["accuracy_t7"] == 0.0


class TestGetDashboardKpis:
    """Tests for get_dashboard_kpis function."""

    @patch("data.execute_query")
    def test_returns_kpis_dict(self, mock_execute):
        """Test that function returns a dict with all four KPI values."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(80, 48, 2.15, 1720.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert isinstance(result, dict)
        assert result["total_signals"] == 80
        assert result["accuracy_pct"] == 60.0  # 48/80 = 60%
        assert result["avg_return_t7"] == 2.15
        assert result["total_pnl"] == 1720.0

    @patch("data.execute_query")
    def test_accuracy_calculated_correctly(self, mock_execute):
        """Test that accuracy percentage is correct."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(200, 130, 1.8, 3200.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["accuracy_pct"] == 65.0  # 130/200 = 65%

    @patch("data.execute_query")
    def test_handles_zero_signals(self, mock_execute):
        """Test that function handles zero evaluated predictions gracefully."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(0, 0, None, 0.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_signals"] == 0
        assert result["accuracy_pct"] == 0.0
        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns default zeros on database error."""
        from data import get_dashboard_kpis

        mock_execute.side_effect = Exception("Database error")

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_signals"] == 0
        assert result["accuracy_pct"] == 0.0
        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0

    @patch("data.execute_query")
    def test_passes_date_filter_when_days_specified(self, mock_execute):
        """Test that the days parameter creates a date filter in the query."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(10, 6, 1.5, 600.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        get_dashboard_kpis(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" in params

    @patch("data.execute_query")
    def test_no_date_filter_when_days_is_none(self, mock_execute):
        """Test that no date filter is applied when days is None (all time)."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(500, 300, 2.0, 15000.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        get_dashboard_kpis(days=None)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" not in params

    @patch("data.execute_query")
    def test_negative_pnl_returned_correctly(self, mock_execute):
        """Test that negative P&L values are returned without modification."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(50, 20, -1.5, -750.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_pnl"] == -750.0
        assert result["avg_return_t7"] == -1.5
        assert result["accuracy_pct"] == 40.0  # 20/50 = 40%

    @patch("data.execute_query")
    def test_handles_null_avg_return(self, mock_execute):
        """Test that NULL avg_return from database is returned as 0.0."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(0, 0, None, None)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0


class TestGetAccuracyByConfidence:
    """Tests for get_accuracy_by_confidence function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_accuracy_by_confidence

        mock_execute.return_value = (
            [
                ("Low (<60%)", 30, 12, 18, 0.5, 500.0),
                ("Medium (60-75%)", 50, 30, 20, 1.5, 1500.0),
                ("High (>75%)", 20, 16, 4, 3.0, 600.0),
            ],
            [
                "confidence_level",
                "total",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        result = get_accuracy_by_confidence()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "accuracy" in result.columns

    @patch("data.execute_query")
    def test_calculates_accuracy_column(self, mock_execute):
        """Test that accuracy column is calculated correctly."""
        from data import get_accuracy_by_confidence

        mock_execute.return_value = (
            [("High (>75%)", 20, 16, 4, 3.0, 600.0)],
            [
                "confidence_level",
                "total",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        result = get_accuracy_by_confidence()

        assert result["accuracy"].iloc[0] == 80.0  # 16/20 = 80%

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_accuracy_by_confidence

        mock_execute.side_effect = Exception("Database error")

        result = get_accuracy_by_confidence()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetAccuracyByAsset:
    """Tests for get_accuracy_by_asset function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_accuracy_by_asset

        mock_execute.return_value = (
            [
                ("AAPL", 10, 7, 3, 2.5, 250.0),
                ("TSLA", 8, 5, 3, 1.5, 120.0),
            ],
            [
                "symbol",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        result = get_accuracy_by_asset(limit=10)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "accuracy" in result.columns

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_accuracy_by_asset

        mock_execute.return_value = ([], [])

        get_accuracy_by_asset(limit=5)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 5


class TestGetSimilarPredictions:
    """Tests for get_similar_predictions function."""

    @patch("data.execute_query")
    def test_returns_dataframe_for_asset(self, mock_execute):
        """Test that function returns a DataFrame for a specific asset."""
        from data import get_similar_predictions

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test text",
                    "post123",
                    0.8,
                    {"AAPL": "bullish"},
                    "thesis",
                    "bullish",
                    1.0,
                    2.0,
                    3.0,
                    True,
                    30.0,
                    150.0,
                    154.5,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "confidence",
                "market_impact",
                "thesis",
                "prediction_sentiment",
                "return_t1",
                "return_t3",
                "return_t7",
                "correct_t7",
                "pnl_t7",
                "price_at_prediction",
                "price_t7",
            ],
        )

        result = get_similar_predictions(asset="AAPL", limit=10)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_returns_empty_dataframe_for_no_asset(self):
        """Test that function returns empty DataFrame when no asset provided."""
        from data import get_similar_predictions

        result = get_similar_predictions(asset=None)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_similar_predictions

        mock_execute.side_effect = Exception("Database error")

        result = get_similar_predictions(asset="AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetPredictionsWithOutcomes:
    """Tests for get_predictions_with_outcomes function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_predictions_with_outcomes

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test text",
                    "post123",
                    1,
                    ["AAPL"],
                    {"AAPL": "bullish"},
                    0.8,
                    "thesis",
                    "completed",
                    None,
                    "AAPL",
                    "bullish",
                    1.0,
                    2.0,
                    3.0,
                    True,
                    True,
                    True,
                    30.0,
                    True,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "analysis_status",
                "analysis_comment",
                "outcome_symbol",
                "prediction_sentiment",
                "return_t1",
                "return_t3",
                "return_t7",
                "correct_t1",
                "correct_t3",
                "correct_t7",
                "pnl_t7",
                "is_complete",
            ],
        )

        result = get_predictions_with_outcomes(limit=50)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_predictions_with_outcomes

        mock_execute.return_value = ([], [])

        get_predictions_with_outcomes(limit=25)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 25


class TestGetSentimentDistribution:
    """Tests for get_sentiment_distribution function."""

    @patch("data.execute_query")
    def test_returns_distribution_dict(self, mock_execute):
        """Test that function returns a dictionary with sentiment counts."""
        from data import get_sentiment_distribution

        mock_execute.return_value = (
            [("bullish", 50), ("bearish", 30), ("neutral", 20)],
            ["prediction_sentiment", "count"],
        )

        result = get_sentiment_distribution()

        assert isinstance(result, dict)
        assert result["bullish"] == 50
        assert result["bearish"] == 30
        assert result["neutral"] == 20

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_sentiment_distribution

        mock_execute.side_effect = Exception("Database error")

        result = get_sentiment_distribution()

        assert result == {"bullish": 0, "bearish": 0, "neutral": 0}


class TestGetActiveAssetsFromDb:
    """Tests for get_active_assets_from_db function."""

    @patch("data.execute_query")
    def test_returns_list_of_assets(self, mock_execute):
        """Test that function returns a list of asset symbols."""
        from data import get_active_assets_from_db

        mock_execute.return_value = (
            [("AAPL",), ("GOOGL",), ("MSFT",), ("TSLA",)],
            ["symbol"],
        )

        result = get_active_assets_from_db()

        assert isinstance(result, list)
        assert len(result) == 4
        assert "AAPL" in result
        assert "TSLA" in result

    @patch("data.execute_query")
    def test_filters_out_none_values(self, mock_execute):
        """Test that function filters out None values."""
        from data import get_active_assets_from_db

        mock_execute.return_value = ([("AAPL",), (None,), ("GOOGL",)], ["symbol"])

        result = get_active_assets_from_db()

        assert len(result) == 2
        assert None not in result

    @patch("data.execute_query")
    def test_returns_empty_list_on_error(self, mock_execute):
        """Test that function returns empty list on error."""
        from data import get_active_assets_from_db

        mock_execute.side_effect = Exception("Database error")

        result = get_active_assets_from_db()

        assert result == []


class TestLoadFilteredPosts:
    """Tests for load_filtered_posts function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import load_filtered_posts

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test text",
                    "post123",
                    10,
                    5,
                    20,
                    ["AAPL"],
                    {"AAPL": "bullish"},
                    "thesis",
                    0.8,
                    "completed",
                    None,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "replies_count",
                "reblogs_count",
                "favourites_count",
                "assets",
                "market_impact",
                "thesis",
                "confidence",
                "analysis_status",
                "analysis_comment",
            ],
        )

        result = load_filtered_posts(limit=100)

        assert isinstance(result, pd.DataFrame)

    @patch("data.execute_query")
    def test_returns_empty_on_no_results(self, mock_execute):
        """Test that function returns empty DataFrame when no results."""
        from data import load_filtered_posts

        mock_execute.return_value = ([], [])

        result = load_filtered_posts(limit=100)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_passes_limit_to_query(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import load_filtered_posts

        mock_execute.return_value = ([], [])

        load_filtered_posts(limit=50)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 50


class TestTimePeriodFiltering:
    """Tests for time period filtering (days parameter) in data functions."""

    @patch("data.execute_query")
    def test_performance_metrics_with_days(self, mock_execute):
        """Test that days parameter adds date filter to query."""
        from data import get_performance_metrics

        mock_execute.return_value = (
            [(50, 30, 20, 50, 2.5, 2500.0, 0.72)],
            [
                "total_outcomes",
                "correct_t7",
                "incorrect_t7",
                "evaluated_t7",
                "avg_return_t7",
                "total_pnl_t7",
                "avg_confidence",
            ],
        )

        get_performance_metrics(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_performance_metrics_without_days(self, mock_execute):
        """Test that without days parameter, no date filter is added."""
        from data import get_performance_metrics

        mock_execute.return_value = (
            [(100, 60, 40, 100, 2.5, 2500.0, 0.72)],
            [
                "total_outcomes",
                "correct_t7",
                "incorrect_t7",
                "evaluated_t7",
                "avg_return_t7",
                "total_pnl_t7",
                "avg_confidence",
            ],
        )

        get_performance_metrics(days=None)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" not in call_args[1]

    @patch("data.execute_query")
    def test_accuracy_by_confidence_with_days(self, mock_execute):
        """Test that days parameter adds date filter to confidence query."""
        from data import get_accuracy_by_confidence

        mock_execute.return_value = (
            [("High (>75%)", 20, 16, 4, 3.0, 600.0)],
            [
                "confidence_level",
                "total",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        get_accuracy_by_confidence(days=7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_accuracy_by_asset_with_days(self, mock_execute):
        """Test that days parameter adds date filter to asset query."""
        from data import get_accuracy_by_asset

        mock_execute.return_value = (
            [("AAPL", 10, 7, 3, 2.5, 250.0)],
            [
                "symbol",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        get_accuracy_by_asset(limit=10, days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]
        assert call_args[1]["limit"] == 10

    @patch("data.execute_query")
    def test_recent_signals_with_days(self, mock_execute):
        """Test that days parameter adds date filter to signals query."""
        from data import get_recent_signals

        mock_execute.return_value = ([], [])

        get_recent_signals(limit=10, days=7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]
        assert call_args[1]["limit"] == 10

    @patch("data.execute_query")
    def test_recent_signals_without_days(self, mock_execute):
        """Test that without days parameter, no date filter is added to signals."""
        from data import get_recent_signals

        mock_execute.return_value = ([], [])

        get_recent_signals(limit=10, days=None)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" not in call_args[1]

    @patch("data.execute_query")
    def test_sentiment_distribution_with_days(self, mock_execute):
        """Test that days parameter adds date filter to sentiment query."""
        from data import get_sentiment_distribution

        mock_execute.return_value = (
            [("bullish", 30), ("bearish", 20)],
            ["prediction_sentiment", "count"],
        )

        # Clear cache before test to ensure fresh call
        get_sentiment_distribution.clear_cache()
        get_sentiment_distribution(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_similar_predictions_with_days(self, mock_execute):
        """Test that days parameter adds date filter to similar predictions query."""
        from data import get_similar_predictions

        mock_execute.return_value = ([], [])

        get_similar_predictions(asset="AAPL", limit=10, days=7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_predictions_with_outcomes_with_days(self, mock_execute):
        """Test that days parameter adds date filter to predictions with outcomes."""
        from data import get_predictions_with_outcomes

        mock_execute.return_value = ([], [])

        get_predictions_with_outcomes(limit=50, days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]


class TestTTLCache:
    """Tests for the TTL cache decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        from data import ttl_cache

        call_count = 0

        @ttl_cache(ttl_seconds=60)
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = expensive_function()
        result2 = expensive_function()

        assert result1 == result2
        assert call_count == 1  # Only called once

    def test_cache_expires(self):
        """Test that cache expires after TTL."""
        import time
        from data import ttl_cache

        call_count = 0

        @ttl_cache(ttl_seconds=0)  # Expire immediately
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        expensive_function()
        time.sleep(0.1)
        expensive_function()

        assert call_count == 2  # Called twice

    def test_clear_cache(self):
        """Test that cache can be manually cleared."""
        from data import ttl_cache

        call_count = 0

        @ttl_cache(ttl_seconds=300)
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        expensive_function()
        expensive_function.clear_cache()
        expensive_function()

        assert call_count == 2

    def test_different_args_different_cache(self):
        """Test that different arguments have separate cache entries."""
        from data import ttl_cache

        @ttl_cache(ttl_seconds=60)
        def get_data(limit):
            return f"data_{limit}"

        assert get_data(10) == "data_10"
        assert get_data(20) == "data_20"


class TestCumulativePnl:
    """Tests for get_cumulative_pnl function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_cumulative(self, mock_execute):
        """Test that function returns DataFrame with cumulative P&L."""
        from data import get_cumulative_pnl
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 100.0, 3),
                (date(2024, 1, 2), -50.0, 2),
                (date(2024, 1, 3), 200.0, 5),
            ],
            ["prediction_date", "daily_pnl", "predictions_count"],
        )

        result = get_cumulative_pnl()

        assert isinstance(result, pd.DataFrame)
        assert "cumulative_pnl" in result.columns
        assert result["cumulative_pnl"].iloc[-1] == 250.0  # 100 - 50 + 200

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_cumulative_pnl

        mock_execute.return_value = ([], [])

        get_cumulative_pnl(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_cumulative_pnl

        mock_execute.side_effect = Exception("Database error")

        result = get_cumulative_pnl()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestRollingAccuracy:
    """Tests for get_rolling_accuracy function."""

    @patch("data.execute_query")
    def test_returns_rolling_accuracy(self, mock_execute):
        """Test that function returns DataFrame with rolling accuracy."""
        from data import get_rolling_accuracy
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 3, 5),
                (date(2024, 1, 2), 4, 5),
            ],
            ["prediction_date", "correct", "total"],
        )

        result = get_rolling_accuracy(window=2)

        assert isinstance(result, pd.DataFrame)
        assert "rolling_accuracy" in result.columns

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_rolling_accuracy

        mock_execute.return_value = ([], [])

        get_rolling_accuracy(window=30, days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_rolling_accuracy

        mock_execute.side_effect = Exception("Database error")

        result = get_rolling_accuracy()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestWinLossStreaks:
    """Tests for get_win_loss_streaks function."""

    @patch("data.execute_query")
    def test_calculates_streaks(self, mock_execute):
        """Test that function calculates streaks correctly."""
        from data import get_win_loss_streaks
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), True),
                (date(2024, 1, 2), True),
                (date(2024, 1, 3), True),
                (date(2024, 1, 4), False),
                (date(2024, 1, 5), False),
            ],
            ["prediction_date", "correct_t7"],
        )

        result = get_win_loss_streaks()

        assert result["max_win_streak"] == 3
        assert result["max_loss_streak"] == 2
        assert result["current_streak"] == -2

    @patch("data.execute_query")
    def test_returns_zeros_on_empty_data(self, mock_execute):
        """Test that function returns zeros when no data."""
        from data import get_win_loss_streaks

        mock_execute.return_value = ([], [])

        result = get_win_loss_streaks()

        assert result == {
            "current_streak": 0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
        }

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_win_loss_streaks

        mock_execute.side_effect = Exception("Database error")

        result = get_win_loss_streaks()

        assert result == {
            "current_streak": 0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
        }


class TestConfidenceCalibration:
    """Tests for get_confidence_calibration function."""

    @patch("data.execute_query")
    def test_returns_calibration_data(self, mock_execute):
        """Test that function returns calibration DataFrame."""
        from data import get_confidence_calibration

        mock_execute.return_value = (
            [
                (0.5, 20, 12, 0.55),
                (0.7, 15, 11, 0.73),
            ],
            ["bucket_start", "total", "correct", "avg_confidence"],
        )

        result = get_confidence_calibration()

        assert isinstance(result, pd.DataFrame)
        assert "actual_accuracy" in result.columns
        assert "predicted_confidence" in result.columns
        assert "bucket_label" in result.columns

    @patch("data.execute_query")
    def test_with_custom_buckets(self, mock_execute):
        """Test that custom bucket count is used."""
        from data import get_confidence_calibration

        mock_execute.return_value = ([], [])

        get_confidence_calibration(buckets=5)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["bucket_size"] == 0.2  # 1.0 / 5

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_confidence_calibration

        mock_execute.side_effect = Exception("Database error")

        result = get_confidence_calibration()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestMonthlyPerformance:
    """Tests for get_monthly_performance function."""

    @patch("data.execute_query")
    def test_returns_monthly_data(self, mock_execute):
        """Test that function returns monthly performance DataFrame."""
        from data import get_monthly_performance
        from datetime import datetime

        mock_execute.return_value = (
            [
                (datetime(2024, 1, 1), 50, 30, 20, 1.5, 1500.0),
            ],
            [
                "month",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
            ],
        )

        result = get_monthly_performance()

        assert isinstance(result, pd.DataFrame)
        assert "accuracy" in result.columns
        assert result["accuracy"].iloc[0] == 60.0  # 30/50 = 60%

    @patch("data.execute_query")
    def test_with_custom_months(self, mock_execute):
        """Test that months parameter is passed to query."""
        from data import get_monthly_performance

        mock_execute.return_value = ([], [])

        get_monthly_performance(months=6)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["months"] == 6

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_monthly_performance

        mock_execute.side_effect = Exception("Database error")

        result = get_monthly_performance()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestClearAllCaches:
    """Tests for clear_all_caches function."""

    def test_clear_all_caches_exists(self):
        """Test that clear_all_caches function exists and can be called."""
        from data import clear_all_caches

        # Should not raise an exception
        clear_all_caches()


# =============================================================================
# Asset Deep Dive Function Tests
# =============================================================================


class TestGetAssetPriceHistory:
    """Tests for get_asset_price_history function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_price_data(self, mock_execute):
        """Test that function returns a DataFrame with price columns."""
        from data import get_asset_price_history
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 150.0, 155.0, 149.0, 152.0, 1000000, 152.0),
                (date(2024, 1, 2), 152.0, 158.0, 151.0, 157.0, 1200000, 157.0),
            ],
            ["date", "open", "high", "low", "close", "volume", "adjusted_close"],
        )

        result = get_asset_price_history("AAPL", days=30)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "date" in result.columns
        assert "open" in result.columns
        assert "close" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns

    @patch("data.execute_query")
    def test_passes_symbol_and_date_to_query(self, mock_execute):
        """Test that symbol and start_date are passed to the query."""
        from data import get_asset_price_history

        mock_execute.return_value = ([], [])

        get_asset_price_history("TSLA", days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "TSLA"
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_uppercases_symbol(self, mock_execute):
        """Test that symbol is uppercased."""
        from data import get_asset_price_history

        mock_execute.return_value = ([], [])

        get_asset_price_history("aapl", days=30)

        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "AAPL"

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_asset_price_history

        mock_execute.side_effect = Exception("Database error")

        result = get_asset_price_history("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetAssetPredictions:
    """Tests for get_asset_predictions function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_predictions(self, mock_execute):
        """Test that function returns a DataFrame with prediction data."""
        from data import get_asset_predictions
        from datetime import date

        mock_execute.return_value = (
            [
                (
                    date(2024, 1, 5),
                    datetime(2024, 1, 5, 10, 30),
                    "Trump says tariffs on China!",
                    "post123",
                    1,
                    "bullish",
                    0.85,
                    150.0,
                    155.0,
                    1.0,
                    2.5,
                    3.5,
                    5.0,
                    True,
                    True,
                    True,
                    False,
                    35.0,
                    True,
                    0.85,
                    "Tariff policy bullish for domestic manufacturing",
                )
            ],
            [
                "prediction_date",
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "prediction_sentiment",
                "prediction_confidence",
                "price_at_prediction",
                "price_t7",
                "return_t1",
                "return_t3",
                "return_t7",
                "return_t30",
                "correct_t1",
                "correct_t3",
                "correct_t7",
                "correct_t30",
                "pnl_t7",
                "is_complete",
                "confidence",
                "thesis",
            ],
        )

        result = get_asset_predictions("AAPL", limit=10)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert "prediction_date" in result.columns
        assert "text" in result.columns
        assert "prediction_sentiment" in result.columns

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_asset_predictions

        mock_execute.return_value = ([], [])

        get_asset_predictions("AAPL", limit=25)

        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 25

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_asset_predictions

        mock_execute.side_effect = Exception("Database error")

        result = get_asset_predictions("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetAssetStats:
    """Tests for get_asset_stats function."""

    @patch("data.execute_query")
    def test_returns_stats_dict(self, mock_execute):
        """Test that function returns a dictionary with expected keys."""
        from data import get_asset_stats

        mock_execute.return_value = (
            [
                (
                    20,  # total_predictions
                    14,  # correct
                    6,  # incorrect
                    20,  # evaluated
                    2.5,  # avg_return
                    500.0,  # total_pnl
                    0.78,  # avg_confidence
                    12,  # bullish_count
                    6,  # bearish_count
                    2,  # neutral_count
                    8.5,  # best_return
                    -3.2,  # worst_return
                    1000,  # overall_evaluated
                    600,  # overall_correct
                    1.8,  # overall_avg_return
                )
            ],
            [
                "total_predictions",
                "correct",
                "incorrect",
                "evaluated",
                "avg_return",
                "total_pnl",
                "avg_confidence",
                "bullish_count",
                "bearish_count",
                "neutral_count",
                "best_return",
                "worst_return",
                "overall_evaluated",
                "overall_correct",
                "overall_avg_return",
            ],
        )

        # Clear cache before test
        get_asset_stats.clear_cache()
        result = get_asset_stats("AAPL")

        assert isinstance(result, dict)
        assert result["total_predictions"] == 20
        assert result["correct_predictions"] == 14
        assert result["accuracy_t7"] == 70.0  # 14/20 = 70%
        assert result["bullish_count"] == 12
        assert result["bearish_count"] == 6
        assert result["best_return_t7"] == 8.5
        assert result["worst_return_t7"] == -3.2
        assert result["overall_accuracy_t7"] == 60.0  # 600/1000 = 60%

    @patch("data.execute_query")
    def test_handles_zero_evaluated(self, mock_execute):
        """Test that function handles zero evaluated predictions."""
        from data import get_asset_stats

        mock_execute.return_value = (
            [
                (
                    0,  # total_predictions
                    0,  # correct
                    0,  # incorrect
                    0,  # evaluated
                    None,  # avg_return
                    0.0,  # total_pnl
                    None,  # avg_confidence
                    0,  # bullish_count
                    0,  # bearish_count
                    0,  # neutral_count
                    None,  # best_return
                    None,  # worst_return
                    100,  # overall_evaluated
                    60,  # overall_correct
                    1.5,  # overall_avg_return
                )
            ],
            [
                "total_predictions",
                "correct",
                "incorrect",
                "evaluated",
                "avg_return",
                "total_pnl",
                "avg_confidence",
                "bullish_count",
                "bearish_count",
                "neutral_count",
                "best_return",
                "worst_return",
                "overall_evaluated",
                "overall_correct",
                "overall_avg_return",
            ],
        )

        get_asset_stats.clear_cache()
        result = get_asset_stats("UNKNOWN")

        assert result["accuracy_t7"] == 0.0
        assert result["best_return_t7"] is None

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_asset_stats

        mock_execute.side_effect = Exception("Database error")

        get_asset_stats.clear_cache()
        result = get_asset_stats("AAPL")

        assert result["total_predictions"] == 0
        assert result["accuracy_t7"] == 0.0
        assert result["overall_accuracy_t7"] == 0.0


class TestGetRelatedAssets:
    """Tests for get_related_assets function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_related_assets(self, mock_execute):
        """Test that function returns DataFrame with related assets."""
        from data import get_related_assets

        mock_execute.return_value = (
            [
                ("GOOGL", 15, 2.3),
                ("MSFT", 12, 1.8),
                ("AMZN", 8, -0.5),
            ],
            ["related_symbol", "co_occurrence_count", "avg_return_t7"],
        )

        result = get_related_assets("AAPL", limit=10)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "related_symbol" in result.columns
        assert "co_occurrence_count" in result.columns
        assert result.iloc[0]["related_symbol"] == "GOOGL"

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_related_assets

        mock_execute.return_value = ([], [])

        get_related_assets("AAPL", limit=5)

        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 5

    @patch("data.execute_query")
    def test_uppercases_symbol(self, mock_execute):
        """Test that symbol is uppercased."""
        from data import get_related_assets

        mock_execute.return_value = ([], [])

        get_related_assets("aapl", limit=8)

        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "AAPL"

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_related_assets

        mock_execute.side_effect = Exception("Database error")

        result = get_related_assets("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# =============================================================================
# Phase 0.2 New Data Function Tests
# =============================================================================


class TestGetActiveSignals:
    """Tests for get_active_signals function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame with aggregated columns."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test post text",
                    "post123",
                    1,
                    ["AAPL", "GOOGL"],
                    {"AAPL": "bullish", "GOOGL": "bullish"},
                    0.85,
                    "thesis text",
                    2,       # outcome_count
                    2,       # correct_count
                    0,       # incorrect_count
                    3.5,     # avg_return_t7
                    70.0,    # total_pnl_t7
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=48)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["confidence"] == 0.85
        assert result.iloc[0]["outcome_count"] == 2
        assert result.iloc[0]["correct_count"] == 2

    @patch("data.execute_query")
    def test_returns_one_row_per_post_not_per_ticker(self, mock_execute):
        """Test that multi-ticker posts produce one row, not one per ticker."""
        from data import get_active_signals

        # Simulate a post with 4 tickers -- should be ONE row after GROUP BY
        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Pentagon spending post about defense stocks",
                    "post_defense_456",
                    42,
                    ["RTX", "LMT", "NOC", "GD"],
                    {"RTX": "bullish", "LMT": "bullish", "NOC": "bullish", "GD": "bullish"},
                    0.75,
                    "Defense spending thesis",
                    4,       # outcome_count (4 tickers)
                    3,       # correct_count
                    1,       # incorrect_count
                    2.1,     # avg_return_t7
                    84.0,    # total_pnl_t7 (sum across 4 tickers)
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1  # One row, not 4
        assert result.iloc[0]["outcome_count"] == 4
        assert result.iloc[0]["total_pnl_t7"] == 84.0

    @patch("data.execute_query")
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_active_signals

        mock_execute.side_effect = Exception("Database error")

        result = get_active_signals()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_passes_params_to_query(self, mock_execute):
        """Test that min_confidence and hours are used in query params."""
        from data import get_active_signals

        mock_execute.return_value = ([], [])

        get_active_signals(min_confidence=0.8, hours=24)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["min_confidence"] == 0.8

    @patch("data.execute_query")
    def test_no_outcomes_shows_pending(self, mock_execute):
        """Test that a post with zero outcomes shows zero counts."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Fresh post with no outcomes yet",
                    "post_new_789",
                    99,
                    ["TSLA"],
                    {"TSLA": "bearish"},
                    0.90,
                    "Bearish thesis",
                    0,       # outcome_count (no outcomes yet)
                    0,       # correct_count
                    0,       # incorrect_count
                    None,    # avg_return_t7 (NULL from AVG of nothing)
                    None,    # total_pnl_t7 (NULL from SUM of nothing)
                    None,    # is_complete (NULL from BOOL_AND of nothing)
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1
        assert result.iloc[0]["outcome_count"] == 0
        assert result.iloc[0]["total_pnl_t7"] is None

    @patch("data.execute_query")
    def test_single_ticker_post(self, mock_execute):
        """Test that a single-ticker post works correctly."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Just talking about Tesla",
                    "post_single_111",
                    50,
                    ["TSLA"],
                    {"TSLA": "bullish"},
                    0.80,
                    "Bull thesis on TSLA",
                    1,       # outcome_count
                    1,       # correct_count
                    0,       # incorrect_count
                    5.2,     # avg_return_t7
                    52.0,    # total_pnl_t7
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1
        assert result.iloc[0]["outcome_count"] == 1
        assert result.iloc[0]["total_pnl_t7"] == 52.0


class TestGetWeeklySignalCount:
    """Tests for get_weekly_signal_count function."""

    @patch("data.execute_query")
    def test_returns_integer_count(self, mock_execute):
        """Test that function returns an integer count."""
        from data import get_weekly_signal_count

        mock_execute.return_value = ([(15,)], ["count"])

        result = get_weekly_signal_count()

        assert isinstance(result, int)
        assert result == 15

    @patch("data.execute_query")
    def test_returns_zero_on_empty(self, mock_execute):
        """Test that function returns 0 when no results."""
        from data import get_weekly_signal_count

        mock_execute.return_value = ([], [])

        result = get_weekly_signal_count()

        assert result == 0

    @patch("data.execute_query")
    def test_returns_zero_on_error(self, mock_execute):
        """Test that function returns 0 on error."""
        from data import get_weekly_signal_count

        mock_execute.side_effect = Exception("Database error")

        result = get_weekly_signal_count()

        assert result == 0


class TestGetHighConfidenceMetrics:
    """Tests for get_high_confidence_metrics function."""

    @patch("data.execute_query")
    def test_returns_metrics_dict(self, mock_execute):
        """Test that function returns a dict with expected keys."""
        from data import get_high_confidence_metrics

        mock_execute.return_value = ([(20, 14, 6)], ["total", "correct", "incorrect"])

        get_high_confidence_metrics.clear_cache()
        result = get_high_confidence_metrics()

        assert isinstance(result, dict)
        assert result["total"] == 20
        assert result["correct"] == 14
        assert result["incorrect"] == 6
        assert result["win_rate"] == 70.0

    @patch("data.execute_query")
    def test_handles_zero_total(self, mock_execute):
        """Test that function handles zero total predictions."""
        from data import get_high_confidence_metrics

        mock_execute.return_value = ([(0, 0, 0)], ["total", "correct", "incorrect"])

        get_high_confidence_metrics.clear_cache()
        result = get_high_confidence_metrics()

        assert result["win_rate"] == 0.0
        assert result["total"] == 0

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_high_confidence_metrics

        mock_execute.return_value = ([(10, 7, 3)], ["total", "correct", "incorrect"])

        get_high_confidence_metrics.clear_cache()
        get_high_confidence_metrics(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_high_confidence_metrics

        mock_execute.side_effect = Exception("Database error")

        get_high_confidence_metrics.clear_cache()
        result = get_high_confidence_metrics()

        assert result == {"win_rate": 0.0, "total": 0, "correct": 0, "incorrect": 0}


class TestGetBestPerformingAsset:
    """Tests for get_best_performing_asset function."""

    @patch("data.execute_query")
    def test_returns_asset_dict(self, mock_execute):
        """Test that function returns a dict with asset info."""
        from data import get_best_performing_asset

        mock_execute.return_value = (
            [("AAPL", 500.0, 10, 7)],
            ["symbol", "total_pnl", "prediction_count", "correct"],
        )

        get_best_performing_asset.clear_cache()
        result = get_best_performing_asset()

        assert result["symbol"] == "AAPL"
        assert result["total_pnl"] == 500.0
        assert result["prediction_count"] == 10
        assert result["accuracy"] == 70.0

    @patch("data.execute_query")
    def test_returns_defaults_on_empty(self, mock_execute):
        """Test that function returns defaults when no data."""
        from data import get_best_performing_asset

        mock_execute.return_value = ([], [])

        get_best_performing_asset.clear_cache()
        result = get_best_performing_asset()

        assert result["symbol"] == "N/A"
        assert result["total_pnl"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_best_performing_asset

        mock_execute.side_effect = Exception("Database error")

        get_best_performing_asset.clear_cache()
        result = get_best_performing_asset()

        assert result["symbol"] == "N/A"


class TestGetAccuracyOverTime:
    """Tests for get_accuracy_over_time function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_accuracy(self, mock_execute):
        """Test that function returns DataFrame with accuracy column."""
        from data import get_accuracy_over_time

        mock_execute.return_value = (
            [
                (datetime(2024, 1, 1), 10, 7),
                (datetime(2024, 1, 8), 12, 9),
            ],
            ["week", "total", "correct"],
        )

        result = get_accuracy_over_time()

        assert isinstance(result, pd.DataFrame)
        assert "accuracy" in result.columns
        assert result["accuracy"].iloc[0] == 70.0  # 7/10

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_accuracy_over_time

        mock_execute.return_value = ([], [])

        get_accuracy_over_time(days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_accuracy_over_time

        mock_execute.side_effect = Exception("Database error")

        result = get_accuracy_over_time()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetBacktestSimulation:
    """Tests for get_backtest_simulation function."""

    @patch("data.execute_query")
    def test_returns_simulation_dict(self, mock_execute):
        """Test that function returns a dict with simulation results."""
        from data import get_backtest_simulation

        mock_execute.return_value = (
            [
                (2.5, True, 25.0),
                (-1.5, False, -15.0),
                (3.0, True, 30.0),
            ],
            ["return_t7", "correct_t7", "pnl_t7"],
        )

        get_backtest_simulation.clear_cache()
        result = get_backtest_simulation(initial_capital=10000, min_confidence=0.75)

        assert result["initial_capital"] == 10000
        assert result["trade_count"] == 3
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["final_value"] == 10040.0  # 10000 + 25 - 15 + 30

    @patch("data.execute_query")
    def test_returns_defaults_on_no_data(self, mock_execute):
        """Test that function returns defaults when no data."""
        from data import get_backtest_simulation

        mock_execute.return_value = ([], [])

        get_backtest_simulation.clear_cache()
        result = get_backtest_simulation(initial_capital=10000)

        assert result["final_value"] == 10000
        assert result["trade_count"] == 0
        assert result["win_rate"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_backtest_simulation

        mock_execute.side_effect = Exception("Database error")

        get_backtest_simulation.clear_cache()
        result = get_backtest_simulation()

        assert result["trade_count"] == 0
        assert result["win_rate"] == 0.0

    @patch("data.execute_query")
    def test_win_rate_calculation(self, mock_execute):
        """Test that win rate is calculated correctly."""
        from data import get_backtest_simulation

        mock_execute.return_value = (
            [
                (1.0, True, 10.0),
                (2.0, True, 20.0),
                (-1.0, False, -10.0),
                (3.0, True, 30.0),
            ],
            ["return_t7", "correct_t7", "pnl_t7"],
        )

        get_backtest_simulation.clear_cache()
        result = get_backtest_simulation()

        assert result["wins"] == 3
        assert result["losses"] == 1
        assert result["win_rate"] == 75.0


class TestGetSentimentAccuracy:
    """Tests for get_sentiment_accuracy function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_sentiment_accuracy

        mock_execute.return_value = (
            [
                ("bullish", 50, 35),
                ("bearish", 30, 15),
                ("neutral", 20, 10),
            ],
            ["sentiment", "total", "correct"],
        )

        result = get_sentiment_accuracy()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "accuracy" in result.columns
        assert result.iloc[0]["accuracy"] == 70.0  # 35/50

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_sentiment_accuracy

        mock_execute.return_value = ([], [])

        get_sentiment_accuracy(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_sentiment_accuracy

        mock_execute.side_effect = Exception("Database error")

        result = get_sentiment_accuracy()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


# =============================================================================
# Signal Feed Tests
# =============================================================================


class TestGetSignalFeed:
    """Tests for get_signal_feed function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_signal_feed

        mock_execute.return_value = (
            [
                (
                    datetime(2025, 1, 15, 10, 30),
                    "Test post text",
                    "post123",
                    1,
                    ["AAPL"],
                    {"AAPL": "bullish"},
                    0.85,
                    "Test thesis",
                    "completed",
                    "AAPL",
                    "bullish",
                    0.85,
                    1.5,
                    2.0,
                    3.5,
                    True,
                    True,
                    True,
                    35.0,
                    True,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "analysis_status",
                "symbol",
                "prediction_sentiment",
                "prediction_confidence",
                "return_t1",
                "return_t3",
                "return_t7",
                "correct_t1",
                "correct_t3",
                "correct_t7",
                "pnl_t7",
                "is_complete",
            ],
        )

        result = get_signal_feed(limit=20, offset=0)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result["confidence"].iloc[0] == 0.85

    @patch("data.execute_query")
    def test_passes_pagination_params(self, mock_execute):
        """Test that limit and offset are passed to the query."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(limit=10, offset=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["limit"] == 10
        assert params["offset"] == 30

    @patch("data.execute_query")
    def test_applies_sentiment_filter(self, mock_execute):
        """Test that sentiment filter is included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(sentiment_filter="bullish")

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["sentiment_filter"] == "bullish"

    @patch("data.execute_query")
    def test_applies_confidence_range(self, mock_execute):
        """Test that confidence min and max are included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(confidence_min=0.6, confidence_max=0.9)

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["confidence_min"] == 0.6
        assert params["confidence_max"] == 0.9

    @patch("data.execute_query")
    def test_applies_asset_filter(self, mock_execute):
        """Test that asset filter is uppercased and included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(asset_filter="aapl")

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["asset_filter"] == "AAPL"

    @patch("data.execute_query")
    def test_applies_outcome_filter_correct(self, mock_execute):
        """Test that outcome filter for 'correct' adds the right WHERE clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter="correct")

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert "correct_t7 = true" in query_str

    @patch("data.execute_query")
    def test_applies_outcome_filter_incorrect(self, mock_execute):
        """Test that outcome filter for 'incorrect' adds the right WHERE clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter="incorrect")

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert "correct_t7 = false" in query_str

    @patch("data.execute_query")
    def test_applies_outcome_filter_pending(self, mock_execute):
        """Test that outcome filter for 'pending' adds IS NULL clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter="pending")

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert "correct_t7 IS NULL" in query_str

    @patch("data.execute_query")
    def test_no_filter_when_none(self, mock_execute):
        """Test that no extra filters are added when all params are None."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed()

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "sentiment_filter" not in params
        assert "asset_filter" not in params
        assert "confidence_min" not in params
        assert "confidence_max" not in params

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on database error."""
        from data import get_signal_feed

        mock_execute.side_effect = Exception("Connection timeout")

        result = get_signal_feed()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetSignalFeedCount:
    """Tests for get_signal_feed_count function."""

    @patch("data.execute_query")
    def test_returns_integer_count(self, mock_execute):
        """Test that function returns an integer."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(142,)], ["total"])

        result = get_signal_feed_count()

        assert isinstance(result, int)
        assert result == 142

    @patch("data.execute_query")
    def test_returns_zero_on_no_results(self, mock_execute):
        """Test that function returns 0 when query returns no rows."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([], [])

        result = get_signal_feed_count()

        assert result == 0

    @patch("data.execute_query")
    def test_returns_zero_on_error(self, mock_execute):
        """Test that function returns 0 on database error."""
        from data import get_signal_feed_count

        mock_execute.side_effect = Exception("Database error")

        result = get_signal_feed_count()

        assert result == 0

    @patch("data.execute_query")
    def test_applies_sentiment_filter(self, mock_execute):
        """Test that sentiment filter is passed to query."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(50,)], ["total"])

        get_signal_feed_count(sentiment_filter="bearish")

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["sentiment_filter"] == "bearish"

    @patch("data.execute_query")
    def test_returns_zero_on_null_count(self, mock_execute):
        """Test that function returns 0 when database returns NULL count."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(None,)], ["total"])

        result = get_signal_feed_count()

        assert result == 0


class TestGetNewSignalsSince:
    """Tests for get_new_signals_since function."""

    @patch("data.execute_query")
    def test_returns_count_of_new_signals(self, mock_execute):
        """Test that function returns the count of new signals."""
        from data import get_new_signals_since

        mock_execute.return_value = ([(5,)], ["new_count"])

        result = get_new_signals_since("2025-01-15T10:00:00")

        assert result == 5

    def test_returns_zero_for_none_timestamp(self):
        """Test that function returns 0 when timestamp is None."""
        from data import get_new_signals_since

        result = get_new_signals_since(None)

        assert result == 0

    def test_returns_zero_for_empty_timestamp(self):
        """Test that function returns 0 when timestamp is empty string."""
        from data import get_new_signals_since

        result = get_new_signals_since("")

        assert result == 0

    @patch("data.execute_query")
    def test_passes_timestamp_to_query(self, mock_execute):
        """Test that timestamp is passed as query parameter."""
        from data import get_new_signals_since

        mock_execute.return_value = ([(0,)], ["new_count"])

        get_new_signals_since("2025-01-15T10:00:00")

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["since_timestamp"] == "2025-01-15T10:00:00"

    @patch("data.execute_query")
    def test_returns_zero_on_error(self, mock_execute):
        """Test that function returns 0 on database error."""
        from data import get_new_signals_since

        mock_execute.side_effect = Exception("Database error")

        result = get_new_signals_since("2025-01-15T10:00:00")

        assert result == 0


class TestGetSignalFeedCsv:
    """Tests for get_signal_feed_csv function."""

    @patch("data.get_signal_feed")
    def test_returns_dataframe_with_export_columns(self, mock_feed):
        """Test that function returns a DataFrame with human-readable columns."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2025, 1, 15, 10, 30),
                    "text": "Test post",
                    "shitpost_id": "post123",
                    "prediction_id": 1,
                    "assets": ["AAPL"],
                    "market_impact": {"AAPL": "bullish"},
                    "confidence": 0.85,
                    "thesis": "Bull thesis",
                    "analysis_status": "completed",
                    "symbol": "AAPL",
                    "prediction_sentiment": "bullish",
                    "prediction_confidence": 0.85,
                    "return_t1": 1.0,
                    "return_t3": 2.0,
                    "return_t7": 3.5,
                    "correct_t1": True,
                    "correct_t3": True,
                    "correct_t7": True,
                    "pnl_t7": 35.0,
                    "is_complete": True,
                }
            ]
        )

        result = get_signal_feed_csv()

        assert isinstance(result, pd.DataFrame)
        assert "Timestamp" in result.columns
        assert "Post Text" in result.columns
        assert "Asset" in result.columns
        assert "Sentiment" in result.columns
        assert "Confidence" in result.columns
        assert "Outcome" in result.columns

    @patch("data.get_signal_feed")
    def test_returns_empty_dataframe_when_no_data(self, mock_feed):
        """Test that function returns empty DataFrame when feed is empty."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame()

        result = get_signal_feed_csv()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.get_signal_feed")
    def test_formats_confidence_as_percentage(self, mock_feed):
        """Test that confidence is formatted as a percentage string."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2025, 1, 15, 10, 30),
                    "text": "Test",
                    "shitpost_id": "p1",
                    "prediction_id": 1,
                    "assets": ["AAPL"],
                    "market_impact": {},
                    "confidence": 0.85,
                    "thesis": "",
                    "analysis_status": "completed",
                    "symbol": "AAPL",
                    "prediction_sentiment": "bullish",
                    "prediction_confidence": 0.85,
                    "return_t1": None,
                    "return_t3": None,
                    "return_t7": None,
                    "correct_t1": None,
                    "correct_t3": None,
                    "correct_t7": None,
                    "pnl_t7": None,
                    "is_complete": False,
                }
            ]
        )

        result = get_signal_feed_csv()

        assert result["Confidence"].iloc[0] == "85%"

    @patch("data.get_signal_feed")
    def test_formats_outcome_labels(self, mock_feed):
        """Test that outcome column uses Correct/Incorrect/Pending labels."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2025, 1, 15),
                    "text": "T1",
                    "shitpost_id": "p1",
                    "prediction_id": 1,
                    "assets": [],
                    "market_impact": {},
                    "confidence": 0.7,
                    "thesis": "",
                    "analysis_status": "completed",
                    "symbol": "AAPL",
                    "prediction_sentiment": "bullish",
                    "prediction_confidence": 0.7,
                    "return_t1": None,
                    "return_t3": None,
                    "return_t7": 2.0,
                    "correct_t1": None,
                    "correct_t3": None,
                    "correct_t7": True,
                    "pnl_t7": 20.0,
                    "is_complete": True,
                },
                {
                    "timestamp": datetime(2025, 1, 14),
                    "text": "T2",
                    "shitpost_id": "p2",
                    "prediction_id": 2,
                    "assets": [],
                    "market_impact": {},
                    "confidence": 0.6,
                    "thesis": "",
                    "analysis_status": "completed",
                    "symbol": "TSLA",
                    "prediction_sentiment": "bearish",
                    "prediction_confidence": 0.6,
                    "return_t1": None,
                    "return_t3": None,
                    "return_t7": -1.0,
                    "correct_t1": None,
                    "correct_t3": None,
                    "correct_t7": False,
                    "pnl_t7": -10.0,
                    "is_complete": True,
                },
                {
                    "timestamp": datetime(2025, 1, 13),
                    "text": "T3",
                    "shitpost_id": "p3",
                    "prediction_id": 3,
                    "assets": [],
                    "market_impact": {},
                    "confidence": 0.5,
                    "thesis": "",
                    "analysis_status": "completed",
                    "symbol": "MSFT",
                    "prediction_sentiment": "neutral",
                    "prediction_confidence": 0.5,
                    "return_t1": None,
                    "return_t3": None,
                    "return_t7": None,
                    "correct_t1": None,
                    "correct_t3": None,
                    "correct_t7": None,
                    "pnl_t7": None,
                    "is_complete": False,
                },
            ]
        )

        result = get_signal_feed_csv()

        assert result["Outcome"].iloc[0] == "Correct"
        assert result["Outcome"].iloc[1] == "Incorrect"
        assert result["Outcome"].iloc[2] == "Pending"

    @patch("data.get_signal_feed")
    def test_passes_filters_to_feed(self, mock_feed):
        """Test that filter params are forwarded to get_signal_feed."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame()

        get_signal_feed_csv(
            sentiment_filter="bullish",
            confidence_min=0.7,
            confidence_max=0.9,
            asset_filter="AAPL",
            outcome_filter="correct",
        )

        mock_feed.assert_called_once_with(
            limit=10000,
            offset=0,
            sentiment_filter="bullish",
            confidence_min=0.7,
            confidence_max=0.9,
            asset_filter="AAPL",
            outcome_filter="correct",
        )


class TestGetTopPredictedAsset:
    """Tests for get_top_predicted_asset function."""

    @patch("data.execute_query")
    def test_returns_top_asset(self, mock_execute):
        """Test that function returns the symbol with most predictions."""
        from data import get_top_predicted_asset

        get_top_predicted_asset.clear_cache()
        mock_execute.return_value = (
            [("TSLA", 42)],
            ["symbol", "prediction_count"],
        )

        result = get_top_predicted_asset()
        assert result == "TSLA"

    @patch("data.execute_query")
    def test_returns_none_when_empty(self, mock_execute):
        """Test that function returns None when no assets exist."""
        from data import get_top_predicted_asset

        get_top_predicted_asset.clear_cache()
        mock_execute.return_value = ([], ["symbol", "prediction_count"])

        result = get_top_predicted_asset()
        assert result is None

    @patch("data.execute_query")
    def test_returns_none_on_error(self, mock_execute):
        """Test that function returns None on database error."""
        from data import get_top_predicted_asset

        get_top_predicted_asset.clear_cache()
        mock_execute.side_effect = Exception("DB connection failed")

        result = get_top_predicted_asset()
        assert result is None
