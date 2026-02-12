"""Tests for shitty_ui/pages/trends.py - Trends page layout and callbacks."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from dash import html
import dash_bootstrap_components as dbc

from pages.trends import create_trends_page, register_trends_callbacks, _build_signal_summary


class TestCreateTrendsPage:
    """Tests for create_trends_page layout."""

    def test_returns_html_div(self):
        """Test that the page returns an html.Div."""
        page = create_trends_page()
        assert isinstance(page, html.Div)

    def test_contains_asset_dropdown(self):
        """Test that the page contains the asset selector dropdown."""
        page = create_trends_page()
        html_str = str(page)
        assert "trends-asset-selector" in html_str

    def test_contains_range_buttons(self):
        """Test that the page contains the time range buttons."""
        page = create_trends_page()
        html_str = str(page)
        assert "trends-range-30d" in html_str
        assert "trends-range-90d" in html_str
        assert "trends-range-180d" in html_str
        assert "trends-range-1y" in html_str

    def test_contains_chart_graph(self):
        """Test that the page contains the chart graph component."""
        page = create_trends_page()
        html_str = str(page)
        assert "trends-signal-chart" in html_str

    def test_contains_options_checklist(self):
        """Test that the page contains the options checklist."""
        page = create_trends_page()
        html_str = str(page)
        assert "trends-options-checklist" in html_str

    def test_contains_summary_section(self):
        """Test that the page contains the signal summary section."""
        page = create_trends_page()
        html_str = str(page)
        assert "trends-signal-summary" in html_str


class TestRegisterTrendsCallbacks:
    """Tests for register_trends_callbacks."""

    def test_callbacks_registered_without_error(self):
        """Test that callbacks register without raising exceptions."""
        mock_app = MagicMock()
        mock_app.callback = MagicMock(return_value=lambda f: f)
        register_trends_callbacks(mock_app)
        # Should have registered 3 callbacks
        assert mock_app.callback.call_count == 3


class TestBuildSignalSummary:
    """Tests for _build_signal_summary helper."""

    def test_empty_signals_shows_message(self):
        """Test that empty signals show a 'no signals' message."""
        result = _build_signal_summary("TEST", pd.DataFrame())
        assert isinstance(result, html.Div)
        html_str = str(result)
        assert "No prediction signals found" in html_str

    def test_valid_signals_returns_row(self):
        """Test that valid signals produce a summary row."""
        signals_df = pd.DataFrame({
            "prediction_sentiment": ["bullish", "bearish", "bullish"],
            "prediction_confidence": [0.8, 0.6, 0.9],
            "correct_t7": [True, False, None],
        })
        result = _build_signal_summary("TEST", signals_df)
        assert isinstance(result, dbc.Row)

    def test_accuracy_calculation(self):
        """Test that accuracy is calculated correctly."""
        signals_df = pd.DataFrame({
            "prediction_sentiment": ["bullish", "bearish", "bullish", "bearish"],
            "prediction_confidence": [0.8, 0.6, 0.9, 0.7],
            "correct_t7": [True, True, False, None],
        })
        result = _build_signal_summary("TEST", signals_df)
        # 2 correct out of 3 evaluated = 67%
        html_str = str(result)
        assert "67%" in html_str

    def test_all_pending_shows_zero_accuracy(self):
        """Test that all-pending signals show 0% accuracy."""
        signals_df = pd.DataFrame({
            "prediction_sentiment": ["bullish", "bearish"],
            "prediction_confidence": [0.8, 0.6],
            "correct_t7": [None, None],
        })
        result = _build_signal_summary("TEST", signals_df)
        html_str = str(result)
        assert "0%" in html_str
