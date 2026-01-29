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
