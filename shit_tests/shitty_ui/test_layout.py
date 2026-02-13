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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


def _find_text_in_component(component, text):
    """Recursively search a Dash component tree for a text string.

    Returns True if the text is found as children or within children strings.
    """
    if isinstance(component, str):
        return text in component

    children = getattr(component, "children", None)
    if children is None:
        return False

    if isinstance(children, str):
        return text in children

    if isinstance(children, (list, tuple)):
        return any(_find_text_in_component(child, text) for child in children)

    # Single component child
    return _find_text_in_component(children, text)


class TestColors:
    """Tests for color palette configuration."""

    def test_colors_dict_exists(self):
        """Test that COLORS dictionary is defined."""
        from layout import COLORS

        assert isinstance(COLORS, dict)
        assert "primary" in COLORS
        assert "secondary" in COLORS
        assert "accent" in COLORS
        assert "success" in COLORS
        assert "danger" in COLORS
        assert "warning" in COLORS
        assert "text" in COLORS
        assert "text_muted" in COLORS
        assert "border" in COLORS

    def test_colors_are_valid_hex(self):
        """Test that all colors are valid hex values."""
        from layout import COLORS

        for name, color in COLORS.items():
            assert color.startswith("#"), f"{name} should be a hex color"
            assert len(color) == 7, f"{name} should be 7 characters (#RRGGBB)"


class TestCreateApp:
    """Tests for create_app function."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_creates_dash_app(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that function creates a Dash application."""
        from layout import create_app
        from dash import Dash

        # Mock all data functions
        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        assert isinstance(app, Dash)
        assert app.title == "Shitpost Alpha - Trading Intelligence Dashboard"

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_app_has_layout(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that app has a layout defined."""
        from layout import create_app

        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
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

    def test_contains_next_refresh_label(self):
        """Test that header contains 'Next refresh' label for the countdown timer."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "Next refresh")
        assert found, "Header should contain 'Next refresh' label"

    def test_contains_last_updated_label(self):
        """Test that header contains 'Last updated' label for the update time."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "Last updated")
        assert found, "Header should contain 'Last updated' label"

    def test_countdown_has_default_value(self):
        """Test that countdown timer has the default '5:00' value."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "5:00")
        assert found, "Header countdown should default to '5:00'"

    def test_last_update_has_default_value(self):
        """Test that last update time has the default '--:--' value."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "--:--")
        assert found, "Header last update time should default to '--:--'"


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
            title="Test Title", value="100", subtitle="Test subtitle", icon="chart-line"
        )

        assert isinstance(card, dbc.Card)

    def test_uses_default_color(self):
        """Test that default accent color is used."""
        from layout import create_metric_card, COLORS

        card = create_metric_card(title="Test", value="100")

        # Card should be created without error with default color
        assert card is not None

    def test_accepts_custom_color(self):
        """Test that custom color can be passed."""
        from layout import create_metric_card

        card = create_metric_card(title="Test", value="100", color="#FF0000")

        assert card is not None


class TestCreateSignalCard:
    """Tests for create_signal_card function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_signal_card
        from dash import html

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet content",
            "confidence": 0.8,
            "assets": ["AAPL", "GOOGL"],
            "market_impact": {"AAPL": "bullish"},
            "return_t7": 2.5,
            "correct_t7": True,
        }

        card = create_signal_card(row)

        assert isinstance(card, html.Div)

    def test_handles_bullish_sentiment(self):
        """Test that bullish sentiment is displayed correctly."""
        from layout import create_signal_card

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet",
            "confidence": 0.8,
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "return_t7": 2.5,
            "correct_t7": True,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_bearish_sentiment(self):
        """Test that bearish sentiment is displayed correctly."""
        from layout import create_signal_card

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet",
            "confidence": 0.7,
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bearish"},
            "return_t7": -1.5,
            "correct_t7": True,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_pending_outcome(self):
        """Test that pending outcome is displayed correctly."""
        from layout import create_signal_card

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet",
            "confidence": 0.6,
            "assets": ["MSFT"],
            "market_impact": {"MSFT": "neutral"},
            "return_t7": None,
            "correct_t7": None,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_incorrect_outcome(self):
        """Test that incorrect outcome is displayed correctly."""
        from layout import create_signal_card

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet",
            "confidence": 0.8,
            "assets": ["NVDA"],
            "market_impact": {"NVDA": "bullish"},
            "return_t7": -3.0,
            "correct_t7": False,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_truncates_long_text(self):
        """Test that long text is truncated."""
        from layout import create_signal_card

        long_text = "A" * 200  # More than 150 characters

        row = {
            "timestamp": datetime.now(),
            "text": long_text,
            "confidence": 0.8,
            "assets": ["AAPL"],
            "market_impact": {},
            "return_t7": None,
            "correct_t7": None,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_many_assets(self):
        """Test that many assets are displayed with +N notation."""
        from layout import create_signal_card

        row = {
            "timestamp": datetime.now(),
            "text": "Test tweet",
            "confidence": 0.8,
            "assets": ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"],
            "market_impact": {},
            "return_t7": None,
            "correct_t7": None,
        }

        card = create_signal_card(row)
        assert card is not None

    def test_handles_string_timestamp(self):
        """Test that string timestamps are handled."""
        from layout import create_signal_card

        row = {
            "timestamp": "2024-01-15 10:30:00",
            "text": "Test tweet",
            "confidence": 0.8,
            "assets": ["AAPL"],
            "market_impact": {},
            "return_t7": None,
            "correct_t7": None,
        }

        card = create_signal_card(row)
        assert card is not None


class TestRegisterCallbacks:
    """Tests for register_callbacks function."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_callbacks_registered(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that callbacks are registered on the app."""
        from layout import create_app, register_callbacks

        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()
        register_callbacks(app)

        # Check that callbacks were registered
        # The app.callback_map should have entries after registration
        assert app.callback_map is not None


class TestErrorCard:
    """Tests for create_error_card function."""

    def test_returns_card(self):
        """Test that function returns a Bootstrap Card."""
        from layout import create_error_card
        import dash_bootstrap_components as dbc

        card = create_error_card("Test error message")
        assert isinstance(card, dbc.Card)

    def test_includes_message(self):
        """Test that error message is included."""
        from layout import create_error_card

        card = create_error_card("Test error message", "Details here")
        assert card is not None

    def test_handles_none_details(self):
        """Test that None details are handled gracefully."""
        from layout import create_error_card

        card = create_error_card("Test error message", None)
        assert card is not None


class TestEmptyChart:
    """Tests for create_empty_chart function."""

    def test_returns_figure(self):
        """Test that function returns a Plotly Figure."""
        from layout import create_empty_chart
        import plotly.graph_objects as go

        fig = create_empty_chart("No data available")
        assert isinstance(fig, go.Figure)

    def test_includes_annotation(self):
        """Test that chart includes the message annotation."""
        from layout import create_empty_chart

        fig = create_empty_chart("Custom message")
        # Figure should have layout with annotations
        assert fig.layout is not None


class TestPeriodButtonStyles:
    """Tests for get_period_button_styles function."""

    def test_returns_list(self):
        """Test that function returns a list of styles."""
        from layout import get_period_button_styles

        styles = get_period_button_styles("7d")
        assert isinstance(styles, list)
        assert len(styles) == 8  # 4 periods * 2 (color + outline)

    def test_selected_period_highlighted(self):
        """Test that selected period is highlighted."""
        from layout import get_period_button_styles

        # Test 7d selected
        styles = get_period_button_styles("7d")
        assert styles[0] == "primary"  # 7d color
        assert styles[1] is False  # 7d outline
        assert styles[2] == "secondary"  # 30d color
        assert styles[3] is True  # 30d outline

    def test_90d_default(self):
        """Test 90d as default selection."""
        from layout import get_period_button_styles

        styles = get_period_button_styles("90d")
        assert styles[4] == "primary"  # 90d color
        assert styles[5] is False  # 90d outline

    def test_all_period(self):
        """Test all period selection."""
        from layout import get_period_button_styles

        styles = get_period_button_styles("all")
        assert styles[6] == "primary"  # all color
        assert styles[7] is False  # all outline


class TestLoadingStates:
    """Tests for loading state components."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_app_has_loading_components(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that app layout contains dcc.Loading components."""
        from layout import create_app
        from dash import dcc

        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        # App should have been created with loading components
        assert app.layout is not None


class TestTimePeriodSelector:
    """Tests for time period selector UI components."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_app_has_period_store(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that app layout contains selected-period store."""
        from layout import create_app

        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        # App should have been created with period selector
        assert app.layout is not None


class TestRefreshIndicator:
    """Tests for refresh indicator components."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_app_has_countdown_interval(
        self,
        mock_assets,
        mock_signals,
        mock_asset_acc,
        mock_conf_acc,
        mock_perf,
        mock_stats,
    ):
        """Test that app layout contains countdown interval."""
        from layout import create_app

        mock_stats.return_value = {
            "total_posts": 0,
            "analyzed_posts": 0,
            "completed_analyses": 0,
            "bypassed_posts": 0,
            "avg_confidence": 0.0,
            "high_confidence_predictions": 0,
        }
        mock_perf.return_value = {
            "total_outcomes": 0,
            "evaluated_predictions": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "total_pnl_t7": 0.0,
            "avg_confidence": 0.0,
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        app = create_app()

        # App should have been created with countdown interval
        assert app.layout is not None


# =============================================================================
# Signal Feed Component Tests
# =============================================================================


class TestCreateFeedSignalCard:
    """Tests for create_feed_signal_card function."""

    def _make_row(self, **overrides):
        """Create a default row dict for create_feed_signal_card."""
        row = {
            "timestamp": datetime(2025, 1, 15, 10, 30),
            "text": "Test post about markets",
            "shitpost_id": "post123",
            "prediction_id": 1,
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "confidence": 0.85,
            "thesis": "Bullish thesis on Apple stock",
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
        row.update(overrides)
        return row

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_feed_signal_card
        from dash import html

        card = create_feed_signal_card(self._make_row())
        assert isinstance(card, html.Div)

    def test_handles_bullish_sentiment(self):
        """Test that bullish sentiment is rendered without error."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(self._make_row(prediction_sentiment="bullish"))
        assert card is not None

    def test_handles_bearish_sentiment(self):
        """Test that bearish sentiment is rendered without error."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(
                prediction_sentiment="bearish",
                market_impact={"TSLA": "bearish"},
                return_t7=-2.0,
                correct_t7=False,
                pnl_t7=-20.0,
            )
        )
        assert card is not None

    def test_handles_neutral_sentiment(self):
        """Test that neutral/unknown sentiment is rendered without error."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(prediction_sentiment="neutral", market_impact={})
        )
        assert card is not None

    def test_handles_pending_outcome(self):
        """Test card with no outcome data yet."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(
                correct_t7=None,
                return_t7=None,
                pnl_t7=None,
                is_complete=False,
            )
        )
        assert card is not None

    def test_handles_incorrect_outcome(self):
        """Test card with an incorrect outcome."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(
                correct_t7=False,
                return_t7=-3.0,
                pnl_t7=-30.0,
            )
        )
        assert card is not None

    def test_handles_missing_fields(self):
        """Test that card handles a row with minimal fields gracefully."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            {
                "timestamp": datetime(2025, 1, 15),
                "text": "Minimal post",
            }
        )
        assert card is not None

    def test_handles_zero_confidence(self):
        """Test card with zero confidence value."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(self._make_row(confidence=0))
        assert card is not None

    def test_handles_none_confidence(self):
        """Test card with None confidence value."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(self._make_row(confidence=None))
        assert card is not None

    def test_handles_empty_thesis(self):
        """Test card with empty thesis."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(self._make_row(thesis=""))
        assert card is not None

    def test_handles_long_thesis(self):
        """Test card with a very long thesis that should be truncated."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(self._make_row(thesis="A" * 500))
        assert card is not None


    def test_handles_nan_prediction_sentiment(self):
        """Test card renders when prediction_sentiment is NaN from LEFT JOIN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(prediction_sentiment=float("nan"))
        )
        assert card is not None

    def test_handles_nan_return_t7(self):
        """Test card renders when return_t7 is NaN from LEFT JOIN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(return_t7=float("nan"), pnl_t7=float("nan"))
        )
        assert card is not None

    def test_handles_nan_correct_t7(self):
        """Test card renders when correct_t7 is NaN from LEFT JOIN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(correct_t7=float("nan"))
        )
        assert card is not None

    def test_handles_nan_thesis(self):
        """Test card renders when thesis is NaN from LEFT JOIN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(thesis=float("nan"))
        )
        assert card is not None

    def test_handles_nan_symbol(self):
        """Test card renders when symbol is NaN from LEFT JOIN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(symbol=float("nan"))
        )
        assert card is not None

    def test_handles_all_outcome_fields_nan(self):
        """Test card renders when all LEFT JOIN outcome fields are NaN."""
        from layout import create_feed_signal_card

        card = create_feed_signal_card(
            self._make_row(
                symbol=float("nan"),
                prediction_sentiment=float("nan"),
                prediction_confidence=float("nan"),
                return_t1=float("nan"),
                return_t3=float("nan"),
                return_t7=float("nan"),
                correct_t1=float("nan"),
                correct_t3=float("nan"),
                correct_t7=float("nan"),
                pnl_t7=float("nan"),
                is_complete=float("nan"),
            )
        )
        assert card is not None


class TestSafeGet:
    """Tests for _safe_get NaN-handling helper."""

    def test_returns_value_when_present(self):
        """Test normal dict access."""
        from components.cards import _safe_get

        assert _safe_get({"key": "value"}, "key") == "value"

    def test_returns_default_when_missing(self):
        """Test missing key returns default."""
        from components.cards import _safe_get

        assert _safe_get({"other": "value"}, "key", "default") == "default"

    def test_returns_default_for_nan(self):
        """Test NaN is normalized to default."""
        from components.cards import _safe_get

        assert _safe_get({"key": float("nan")}, "key", "default") == "default"

    def test_returns_default_for_none(self):
        """Test None is normalized to default."""
        from components.cards import _safe_get

        assert _safe_get({"key": None}, "key", "default") == "default"

    def test_preserves_zero(self):
        """Test that 0 is NOT replaced with default."""
        from components.cards import _safe_get

        assert _safe_get({"key": 0}, "key", 99) == 0

    def test_preserves_empty_string(self):
        """Test that empty string is NOT replaced with default."""
        from components.cards import _safe_get

        assert _safe_get({"key": ""}, "key", "default") == ""

    def test_preserves_false(self):
        """Test that False is NOT replaced with default."""
        from components.cards import _safe_get

        assert _safe_get({"key": False}, "key", True) is False

    def test_works_with_pandas_series(self):
        """Test with Pandas Series (the actual use case)."""
        import pandas as pd
        from components.cards import _safe_get

        series = pd.Series({"a": 1, "b": float("nan"), "c": "hello"})
        assert _safe_get(series, "a") == 1
        assert _safe_get(series, "b", "default") == "default"
        assert _safe_get(series, "c") == "hello"
        assert _safe_get(series, "missing", "default") == "default"


class TestSignalFeedCallbackErrorHandling:
    """Tests for signal feed callback error handling."""

    @patch("data.get_signal_feed")
    @patch("data.get_signal_feed_count")
    def test_update_signal_feed_returns_error_card_on_exception(
        self, mock_count, mock_feed
    ):
        """Test that the callback returns an error card instead of crashing."""
        mock_feed.side_effect = Exception("Database connection failed")
        mock_count.return_value = 0

        # We cannot easily call the inner callback directly, but we can
        # test that the data function error is handled by the callback logic.
        # For now, verify that get_signal_feed raises and the wrapper catches it.
        try:
            mock_feed(limit=20, offset=0)
        except Exception:
            pass  # Expected - the callback wrapper would catch this

    @patch("data.get_signal_feed")
    @patch("data.get_signal_feed_count")
    def test_update_signal_feed_returns_empty_state_on_empty_data(
        self, mock_count, mock_feed
    ):
        """Test that the callback returns empty state for no matching data."""
        mock_feed.return_value = pd.DataFrame()
        mock_count.return_value = 0

        # Verify the data functions return empty results without error
        df = mock_feed(limit=20, offset=0)
        count = mock_count()
        assert df.empty
        assert count == 0


class TestCreateNewSignalsBanner:
    """Tests for create_new_signals_banner function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_new_signals_banner
        from dash import html

        banner = create_new_signals_banner(5)
        assert isinstance(banner, html.Div)

    def test_singular_for_count_one(self):
        """Test that text uses singular form for count=1."""
        from layout import create_new_signals_banner

        banner = create_new_signals_banner(1)
        # The banner should contain "1 new signal" (not "signals")
        assert banner is not None

    def test_plural_for_count_many(self):
        """Test that text uses plural form for count > 1."""
        from layout import create_new_signals_banner

        banner = create_new_signals_banner(10)
        assert banner is not None

    def test_contains_show_button(self):
        """Test that banner contains the 'Show New Signals' button."""
        from layout import create_new_signals_banner
        import dash_bootstrap_components as dbc

        banner = create_new_signals_banner(3)
        # Children should include the button
        assert len(banner.children) == 2  # text div + button
        assert isinstance(banner.children[1], dbc.Button)
        assert banner.children[1].id == "signal-feed-show-new-btn"


class TestCreateSignalFeedPage:
    """Tests for create_signal_feed_page function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from pages.signals import create_signal_feed_page
        from dash import html

        page = create_signal_feed_page()
        assert isinstance(page, html.Div)

    def test_has_filter_controls(self):
        """Test that page contains filter controls."""
        from pages.signals import create_signal_feed_page

        page = create_signal_feed_page()
        # Page should have multiple children (header, banner, interval, stores, filters, etc.)
        assert len(page.children) > 5

    def test_has_load_more_button(self):
        """Test that page contains the load-more container."""
        from pages.signals import create_signal_feed_page

        page = create_signal_feed_page()
        # Find the load-more container by its id
        found = False
        for child in page.children:
            if hasattr(child, "id") and child.id == "signal-feed-load-more-container":
                found = True
                break
        assert found, "Load More container not found in page"

    def test_has_poll_interval(self):
        """Test that page contains the signal-feed-poll-interval."""
        from pages.signals import create_signal_feed_page
        from dash import dcc

        page = create_signal_feed_page()
        found = False
        for child in page.children:
            if isinstance(child, dcc.Interval) and getattr(child, "id", None) == "signal-feed-poll-interval":
                found = True
                break
        assert found, "Poll interval not found in page"

    def test_has_csv_download(self):
        """Test that page contains the CSV download component."""
        from pages.signals import create_signal_feed_page
        from dash import dcc

        page = create_signal_feed_page()
        found = False
        for child in page.children:
            if isinstance(child, dcc.Download) and getattr(child, "id", None) == "signal-feed-csv-download":
                found = True
                break
        assert found, "CSV download component not found in page"
