"""Tests for get_asset_screener_data and get_screener_sparkline_prices in data.py."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from data import get_asset_screener_data, get_screener_sparkline_prices


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear TTL caches before each test."""
    get_asset_screener_data.clear_cache()
    get_screener_sparkline_prices.clear_cache()
    yield
    get_asset_screener_data.clear_cache()
    get_screener_sparkline_prices.clear_cache()


class TestGetAssetScreenerData:
    """Tests for get_asset_screener_data."""

    @patch("data.execute_query")
    def test_returns_expected_columns(self, mock_query):
        mock_query.return_value = (
            [("XLE", 29, 14, 15, 2.48, 719.0, 0.72, "bullish")],
            [
                "symbol",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
                "latest_sentiment",
            ],
        )
        df = get_asset_screener_data()
        expected_cols = {
            "symbol",
            "total_predictions",
            "correct",
            "incorrect",
            "avg_return",
            "total_pnl",
            "avg_confidence",
            "latest_sentiment",
            "accuracy",
        }
        assert set(df.columns) == expected_cols

    @patch("data.execute_query")
    def test_calculates_accuracy(self, mock_query):
        mock_query.return_value = (
            [("XLE", 10, 6, 4, 1.5, 300.0, 0.70, "bullish")],
            [
                "symbol",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
                "latest_sentiment",
            ],
        )
        df = get_asset_screener_data()
        assert df.iloc[0]["accuracy"] == 60.0

    @patch("data.execute_query")
    def test_with_days_filter(self, mock_query):
        mock_query.return_value = ([], [])
        get_asset_screener_data(days=30)
        call_args = mock_query.call_args
        query_text = str(call_args[0][0])
        assert "start_date" in str(call_args[0][1]) or "start_date" in str(
            call_args[1].get("params", call_args[0][1] if len(call_args[0]) > 1 else {})
        )

    @patch("data.execute_query")
    def test_empty_result(self, mock_query):
        mock_query.return_value = ([], [])
        df = get_asset_screener_data()
        assert df.empty

    @patch("data.execute_query")
    def test_error_returns_empty(self, mock_query):
        mock_query.side_effect = Exception("DB error")
        df = get_asset_screener_data()
        assert df.empty

    @patch("data.execute_query")
    def test_multiple_assets(self, mock_query):
        mock_query.return_value = (
            [
                ("XLE", 29, 14, 15, 2.48, 719.0, 0.72, "bullish"),
                ("DIS", 17, 8, 9, -2.58, -438.0, 0.65, "bearish"),
            ],
            [
                "symbol",
                "total_predictions",
                "correct",
                "incorrect",
                "avg_return",
                "total_pnl",
                "avg_confidence",
                "latest_sentiment",
            ],
        )
        df = get_asset_screener_data()
        assert len(df) == 2
        assert df.iloc[0]["symbol"] == "XLE"
        assert df.iloc[1]["symbol"] == "DIS"


class TestGetScreenerSparklinePrices:
    """Tests for get_screener_sparkline_prices."""

    def test_empty_symbols_returns_empty(self):
        result = get_screener_sparkline_prices(symbols=())
        assert result == {}

    @patch("data.execute_query")
    def test_returns_dict_keyed_by_symbol(self, mock_query):
        mock_query.return_value = (
            [
                ("XLE", "2025-06-01", 80.0),
                ("XLE", "2025-06-02", 81.5),
                ("DIS", "2025-06-01", 100.0),
                ("DIS", "2025-06-02", 99.0),
            ],
            ["symbol", "date", "close"],
        )
        result = get_screener_sparkline_prices(symbols=("XLE", "DIS"))
        assert "XLE" in result
        assert "DIS" in result
        assert isinstance(result["XLE"], pd.DataFrame)

    @patch("data.execute_query")
    def test_filters_symbols_with_less_than_2_points(self, mock_query):
        mock_query.return_value = (
            [
                ("XLE", "2025-06-01", 80.0),
                ("XLE", "2025-06-02", 81.5),
                ("DIS", "2025-06-01", 100.0),  # Only 1 point
            ],
            ["symbol", "date", "close"],
        )
        result = get_screener_sparkline_prices(symbols=("XLE", "DIS"))
        assert "XLE" in result
        assert "DIS" not in result

    @patch("data.execute_query")
    def test_no_rows_returns_empty(self, mock_query):
        mock_query.return_value = ([], [])
        result = get_screener_sparkline_prices(symbols=("XLE",))
        assert result == {}

    @patch("data.execute_query")
    def test_error_returns_empty(self, mock_query):
        mock_query.side_effect = Exception("DB error")
        result = get_screener_sparkline_prices(symbols=("XLE",))
        assert result == {}

    @patch("data.execute_query")
    def test_dataframe_has_date_and_close_columns(self, mock_query):
        mock_query.return_value = (
            [
                ("XLE", "2025-06-01", 80.0),
                ("XLE", "2025-06-02", 81.5),
                ("XLE", "2025-06-03", 82.0),
            ],
            ["symbol", "date", "close"],
        )
        result = get_screener_sparkline_prices(symbols=("XLE",))
        df = result["XLE"]
        assert list(df.columns) == ["date", "close"]
        assert len(df) == 3
