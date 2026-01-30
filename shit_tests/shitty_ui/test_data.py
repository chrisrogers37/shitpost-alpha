"""
Tests for shitty_ui data layer functions.
Tests all database query functions for the prediction performance dashboard.
"""

import pytest
from unittest.mock import patch, MagicMock
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

        result = get_performance_metrics(days=30)

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

        result = get_performance_metrics(days=None)

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

        result = get_accuracy_by_confidence(days=7)

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

        result = get_accuracy_by_asset(limit=10, days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]
        assert call_args[1]["limit"] == 10

    @patch("data.execute_query")
    def test_recent_signals_with_days(self, mock_execute):
        """Test that days parameter adds date filter to signals query."""
        from data import get_recent_signals

        mock_execute.return_value = ([], [])

        result = get_recent_signals(limit=10, days=7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]
        assert call_args[1]["limit"] == 10

    @patch("data.execute_query")
    def test_recent_signals_without_days(self, mock_execute):
        """Test that without days parameter, no date filter is added to signals."""
        from data import get_recent_signals

        mock_execute.return_value = ([], [])

        result = get_recent_signals(limit=10, days=None)

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
        result = get_sentiment_distribution(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_similar_predictions_with_days(self, mock_execute):
        """Test that days parameter adds date filter to similar predictions query."""
        from data import get_similar_predictions

        mock_execute.return_value = ([], [])

        result = get_similar_predictions(asset="AAPL", limit=10, days=7)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_predictions_with_outcomes_with_days(self, mock_execute):
        """Test that days parameter adds date filter to predictions with outcomes."""
        from data import get_predictions_with_outcomes

        mock_execute.return_value = ([], [])

        result = get_predictions_with_outcomes(limit=50, days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]


class TestTTLCache:
    """Tests for the TTL cache decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        import time
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

        result = get_cumulative_pnl(days=30)

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

        result = get_rolling_accuracy(window=30, days=90)

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

        result = get_confidence_calibration(buckets=5)

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

        result = get_monthly_performance(months=6)

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


class TestGetEquityCurveData:
    """Tests for get_equity_curve_data function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_cumulative(self, mock_execute):
        """Test that function returns DataFrame with cumulative P&L column."""
        from data import get_equity_curve_data
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), "AAPL", "bullish", 50.0, 0.8, True, 50.0),
                (date(2024, 1, 2), "TSLA", "bearish", -30.0, 0.6, False, 20.0),
            ],
            [
                "prediction_date",
                "symbol",
                "prediction_sentiment",
                "pnl_t7",
                "prediction_confidence",
                "correct_t7",
                "cumulative_pnl",
            ],
        )

        result = get_equity_curve_data()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "cumulative_pnl" in result.columns

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_equity_curve_data

        mock_execute.return_value = ([], [])

        result = get_equity_curve_data(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_equity_curve_data

        mock_execute.side_effect = Exception("Database error")

        result = get_equity_curve_data()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetDrawdownData:
    """Tests for get_drawdown_data function."""

    @patch("data.get_equity_curve_data")
    def test_calculates_drawdown(self, mock_equity):
        """Test that function calculates drawdown correctly."""
        from data import get_drawdown_data
        from datetime import date

        mock_equity.return_value = pd.DataFrame(
            {
                "prediction_date": [
                    date(2024, 1, 1),
                    date(2024, 1, 2),
                    date(2024, 1, 3),
                ],
                "cumulative_pnl": [100.0, 150.0, 80.0],
                "pnl_t7": [100.0, 50.0, -70.0],
                "symbol": ["AAPL", "TSLA", "GOOGL"],
                "correct_t7": [True, True, False],
            }
        )

        result = get_drawdown_data()

        assert isinstance(result, pd.DataFrame)
        assert "drawdown" in result.columns
        assert "peak_pnl" in result.columns
        # Peak should be 150, drawdown at end should be 80 - 150 = -70
        assert result.iloc[-1]["drawdown"] == -70.0

    @patch("data.get_equity_curve_data")
    def test_returns_empty_on_no_data(self, mock_equity):
        """Test that function returns empty DataFrame when equity data is empty."""
        from data import get_drawdown_data

        mock_equity.return_value = pd.DataFrame()

        result = get_drawdown_data()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetSentimentPerformance:
    """Tests for get_sentiment_performance function."""

    @patch("data.execute_query")
    def test_returns_sentiment_breakdown(self, mock_execute):
        """Test that function returns performance by sentiment."""
        from data import get_sentiment_performance

        mock_execute.return_value = (
            [
                ("bullish", 50, 30, 20, 1.5, 1500.0, 0.72),
                ("bearish", 30, 15, 15, -0.5, -500.0, 0.68),
            ],
            [
                "prediction_sentiment",
                "total",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
            ],
        )

        result = get_sentiment_performance()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "accuracy" in result.columns
        assert result[result["prediction_sentiment"] == "bullish"]["accuracy"].iloc[
            0
        ] == 60.0  # 30/50

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_sentiment_performance

        mock_execute.return_value = ([], [])

        result = get_sentiment_performance(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_sentiment_performance

        mock_execute.side_effect = Exception("Database error")

        result = get_sentiment_performance()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetPerformanceSummary:
    """Tests for get_performance_summary function."""

    @patch("data.get_drawdown_data")
    @patch("data.execute_query")
    def test_returns_summary_dict(self, mock_execute, mock_drawdown):
        """Test that function returns dictionary with summary metrics."""
        from data import get_performance_summary

        mock_execute.return_value = (
            [(100, 60, 40, 5000.0, 50.0, 7000.0, 2000.0, 200.0, -100.0, 0.72)],
            [
                "total_trades",
                "wins",
                "losses",
                "total_pnl",
                "avg_pnl",
                "gross_profit",
                "gross_loss",
                "best_trade",
                "worst_trade",
                "avg_confidence",
            ],
        )
        mock_drawdown.return_value = pd.DataFrame({"drawdown": [-500.0, -300.0, -100.0]})

        result = get_performance_summary()

        assert isinstance(result, dict)
        assert result["total_trades"] == 100
        assert result["win_rate"] == 60.0  # 60/100
        assert result["total_pnl"] == 5000.0
        assert result["profit_factor"] == 3.5  # 7000/2000
        assert result["max_drawdown"] == -500.0

    @patch("data.get_drawdown_data")
    @patch("data.execute_query")
    def test_handles_zero_gross_loss(self, mock_execute, mock_drawdown):
        """Test that function handles zero gross loss (infinite profit factor)."""
        from data import get_performance_summary

        mock_execute.return_value = (
            [(10, 10, 0, 1000.0, 100.0, 1000.0, 0.0, 200.0, 50.0, 0.8)],
            [
                "total_trades",
                "wins",
                "losses",
                "total_pnl",
                "avg_pnl",
                "gross_profit",
                "gross_loss",
                "best_trade",
                "worst_trade",
                "avg_confidence",
            ],
        )
        mock_drawdown.return_value = pd.DataFrame({"drawdown": [0.0]})

        result = get_performance_summary()

        assert result["profit_factor"] == "Inf"

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_performance_summary

        mock_execute.side_effect = Exception("Database error")

        result = get_performance_summary()

        assert result["total_trades"] == 0
        assert result["win_rate"] == 0.0


class TestGetPeriodicPerformance:
    """Tests for get_periodic_performance function."""

    @patch("data.execute_query")
    def test_returns_monthly_performance(self, mock_execute):
        """Test that function returns monthly performance data."""
        from data import get_periodic_performance

        mock_execute.return_value = (
            [
                ("2024-01", 50, 30, 20, 1.5, 1500.0, 0.72),
                ("2024-02", 40, 25, 15, 2.0, 2000.0, 0.75),
            ],
            [
                "period_label",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
            ],
        )

        result = get_periodic_performance(period="month")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "accuracy" in result.columns

    @patch("data.execute_query")
    def test_returns_weekly_performance(self, mock_execute):
        """Test that function returns weekly performance data."""
        from data import get_periodic_performance

        mock_execute.return_value = (
            [
                ("2024-W01", 10, 6, 4, 1.0, 100.0, 0.70),
            ],
            [
                "period_label",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
            ],
        )

        result = get_periodic_performance(period="week")

        assert isinstance(result, pd.DataFrame)
        assert result["period_label"].iloc[0] == "2024-W01"

    @patch("data.execute_query")
    def test_with_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter."""
        from data import get_periodic_performance

        mock_execute.return_value = ([], [])

        result = get_periodic_performance(period="month", days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert "start_date" in call_args[1]

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_periodic_performance

        mock_execute.side_effect = Exception("Database error")

        result = get_periodic_performance()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestClearAllCaches:
    """Tests for clear_all_caches function."""

    def test_clear_all_caches_exists(self):
        """Test that clear_all_caches function exists and can be called."""
        from data import clear_all_caches

        # Should not raise an exception
        clear_all_caches()
