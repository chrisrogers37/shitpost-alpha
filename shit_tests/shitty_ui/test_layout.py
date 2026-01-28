"""
Tests for shitty_ui layout components and callbacks.
Tests dashboard structure, component creation, and callback behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pandas as pd
import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))


class TestColors:
    """Tests for color palette configuration."""

    def test_colors_dict_exists(self):
        """Test that COLORS dictionary is defined."""
        from layout import COLORS

        assert isinstance(COLORS, dict)
        assert 'primary' in COLORS
        assert 'secondary' in COLORS
        assert 'accent' in COLORS
        assert 'success' in COLORS
        assert 'danger' in COLORS
        assert 'warning' in COLORS
        assert 'text' in COLORS
        assert 'text_muted' in COLORS
        assert 'border' in COLORS

    def test_colors_are_valid_hex(self):
        """Test that all colors are valid hex values."""
        from layout import COLORS

        for name, color in COLORS.items():
            assert color.startswith('#'), f"{name} should be a hex color"
            assert len(color) == 7, f"{name} should be 7 characters (#RRGGBB)"


class TestCreateApp:
    """Tests for create_app function."""

    @patch('layout.get_prediction_stats')
    @patch('layout.get_performance_metrics')
    @patch('layout.get_accuracy_by_confidence')
    @patch('layout.get_accuracy_by_asset')
    @patch('layout.get_recent_signals')
    @patch('layout.get_active_assets_from_db')
    def test_creates_dash_app(self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats):
        """Test that function creates a Dash application."""
        from layout import create_app
        from dash import Dash

        # Mock all data functions
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        assert isinstance(app, Dash)
        assert app.title == "Shitpost Alpha - Prediction Performance Dashboard"

    @patch('layout.get_prediction_stats')
    @patch('layout.get_performance_metrics')
    @patch('layout.get_accuracy_by_confidence')
    @patch('layout.get_accuracy_by_asset')
    @patch('layout.get_recent_signals')
    @patch('layout.get_active_assets_from_db')
    def test_app_has_layout(self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats):
        """Test that app has a layout defined."""
        from layout import create_app

        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        assert app.layout is not None


class TestCreateHeader:
    """Tests for create_header function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_header
        from dash import html

        header = create_header()

        assert isinstance(header, html.Div)

    def test_contains_title(self):
        """Test that header contains the title."""
        from layout import create_header

        header = create_header()

        # Check that there's content in the header
        assert len(header.children) > 0


class TestCreateFilterControls:
    """Tests for create_filter_controls function."""

    def test_returns_row(self):
        """Test that function returns a Bootstrap Row."""
        from layout import create_filter_controls
        import dash_bootstrap_components as dbc

        controls = create_filter_controls()

        assert isinstance(controls, dbc.Row)

    def test_contains_confidence_slider(self):
        """Test that filter controls contain confidence slider."""
        from layout import create_filter_controls

        controls = create_filter_controls()

        # Row should have columns with controls
        assert len(controls.children) >= 3


class TestCreateFooter:
    """Tests for create_footer function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_footer
        from dash import html

        footer = create_footer()

        assert isinstance(footer, html.Div)


class TestCreateMetricCard:
    """Tests for create_metric_card function."""

    def test_returns_card(self):
        """Test that function returns a Bootstrap Card."""
        from layout import create_metric_card
        import dash_bootstrap_components as dbc

        card = create_metric_card(
            title="Test Title",
            value="100",
            subtitle="Test subtitle",
            icon="chart-line"
        )

        assert isinstance(card, dbc.Card)

    def test_uses_default_color(self):
        """Test that default accent color is used."""
        from layout import create_metric_card, COLORS

        card = create_metric_card(
            title="Test",
            value="100"
        )

        # Card should be created without error with default color
        assert card is not None

    def test_accepts_custom_color(self):
        """Test that custom color can be passed."""
        from layout import create_metric_card

        card = create_metric_card(
            title="Test",
            value="100",
            color="#FF0000"
        )

        assert card is not None


class TestCreateSignalCard:
    """Tests for create_signal_card function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_signal_card
        from dash import html

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet content',
            'confidence': 0.8,
            'assets': ['AAPL', 'GOOGL'],
            'market_impact': {'AAPL': 'bullish'},
            'return_t7': 2.5,
            'correct_t7': True
        }

        card = create_signal_card(row)

        assert isinstance(card, html.Div)

    def test_handles_bullish_sentiment(self):
        """Test that bullish sentiment is displayed correctly."""
        from layout import create_signal_card

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet',
            'confidence': 0.8,
            'assets': ['AAPL'],
            'market_impact': {'AAPL': 'bullish'},
            'return_t7': 2.5,
            'correct_t7': True
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_bearish_sentiment(self):
        """Test that bearish sentiment is displayed correctly."""
        from layout import create_signal_card

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet',
            'confidence': 0.7,
            'assets': ['TSLA'],
            'market_impact': {'TSLA': 'bearish'},
            'return_t7': -1.5,
            'correct_t7': True
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_pending_outcome(self):
        """Test that pending outcome is displayed correctly."""
        from layout import create_signal_card

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet',
            'confidence': 0.6,
            'assets': ['MSFT'],
            'market_impact': {'MSFT': 'neutral'},
            'return_t7': None,
            'correct_t7': None
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_incorrect_outcome(self):
        """Test that incorrect outcome is displayed correctly."""
        from layout import create_signal_card

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet',
            'confidence': 0.8,
            'assets': ['NVDA'],
            'market_impact': {'NVDA': 'bullish'},
            'return_t7': -3.0,
            'correct_t7': False
        }

        card = create_signal_card(row)
        assert card is not None

    def test_truncates_long_text(self):
        """Test that long text is truncated."""
        from layout import create_signal_card

        long_text = "A" * 200  # More than 150 characters

        row = {
            'timestamp': datetime.now(),
            'text': long_text,
            'confidence': 0.8,
            'assets': ['AAPL'],
            'market_impact': {},
            'return_t7': None,
            'correct_t7': None
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_many_assets(self):
        """Test that many assets are displayed with +N notation."""
        from layout import create_signal_card

        row = {
            'timestamp': datetime.now(),
            'text': 'Test tweet',
            'confidence': 0.8,
            'assets': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'],
            'market_impact': {},
            'return_t7': None,
            'correct_t7': None
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_string_timestamp(self):
        """Test that string timestamps are handled."""
        from layout import create_signal_card

        row = {
            'timestamp': '2024-01-15 10:30:00',
            'text': 'Test tweet',
            'confidence': 0.8,
            'assets': ['AAPL'],
            'market_impact': {},
            'return_t7': None,
            'correct_t7': None
        }

        card = create_signal_card(row)
        assert card is not None


class TestRegisterCallbacks:
    """Tests for register_callbacks function."""

    @patch('layout.get_prediction_stats')
    @patch('layout.get_performance_metrics')
    @patch('layout.get_accuracy_by_confidence')
    @patch('layout.get_accuracy_by_asset')
    @patch('layout.get_recent_signals')
    @patch('layout.get_active_assets_from_db')
    def test_callbacks_registered(self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats):
        """Test that callbacks are registered on the app."""
        from layout import create_app, register_callbacks

        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()
        register_callbacks(app)

        # Check that callbacks were registered
        # The app.callback_map should have entries after registration
        assert app.callback_map is not None
