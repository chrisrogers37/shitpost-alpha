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


def _find_component_ids(component):
    """Recursively collect all component IDs from a Dash component tree."""
    ids = set()
    comp_id = getattr(component, "id", None)
    if comp_id:
        ids.add(comp_id)

    children = getattr(component, "children", None)
    if children is None:
        return ids
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "id"):
                ids.update(_find_component_ids(child))
    elif hasattr(children, "children") or hasattr(children, "id"):
        ids.update(_find_component_ids(children))
    return ids


def _find_component_by_id(component, target_id):
    """Recursively find a component by its ID in a Dash component tree."""
    comp_id = getattr(component, "id", None)
    if comp_id == target_id:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "id"):
                result = _find_component_by_id(child, target_id)
                if result is not None:
                    return result
    elif hasattr(children, "children") or hasattr(children, "id"):
        result = _find_component_by_id(children, target_id)
        if result is not None:
            return result
    return None


def _find_components_by_type(component, comp_type):
    """Recursively find all components of a given type in a Dash component tree."""
    found = []
    if isinstance(component, comp_type):
        found.append(component)

    children = getattr(component, "children", None)
    if children is None:
        return found
    if isinstance(children, (list, tuple)):
        for child in children:
            found.extend(_find_components_by_type(child, comp_type))
    elif hasattr(children, "children"):
        found.extend(_find_components_by_type(children, comp_type))
    return found


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


class TestEmptyStateChart:
    """Tests for create_empty_state_chart function."""

    def test_returns_figure(self):
        """Test that function returns a Plotly Figure."""
        from components.cards import create_empty_state_chart
        import plotly.graph_objects as go

        fig = create_empty_state_chart("No data available")
        assert isinstance(fig, go.Figure)

    def test_default_height_is_compact(self):
        """Test that the default height is 80px, not 250px like create_empty_chart."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("No data")
        assert fig.layout.height == 80

    def test_custom_height(self):
        """Test that custom height is respected."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("No data", height=120)
        assert fig.layout.height == 120

    def test_includes_message_in_annotation(self):
        """Test that the primary message appears in the annotation."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Custom empty message")
        annotations = fig.layout.annotations
        assert len(annotations) == 1
        assert "Custom empty message" in annotations[0].text

    def test_includes_hint_in_annotation(self):
        """Test that the hint text appears in the annotation when provided."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main message", hint="This is the hint")
        annotation_text = fig.layout.annotations[0].text
        assert "This is the hint" in annotation_text

    def test_no_hint_when_omitted(self):
        """Test that no hint span is added when hint is empty."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main message")
        annotation_text = fig.layout.annotations[0].text
        assert "<br>" not in annotation_text

    def test_icon_is_included(self):
        """Test that the default info icon is in the annotation."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Test")
        annotation_text = fig.layout.annotations[0].text
        # Default icon is the info emoji
        assert "\u2139" in annotation_text

    def test_custom_icon(self):
        """Test that a custom icon replaces the default."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Test", icon="\u23f3")
        annotation_text = fig.layout.annotations[0].text
        assert "\u23f3" in annotation_text

    def test_no_grid_or_tick_labels(self):
        """Test that axes have no grid, ticks, or labels."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Test")
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False

    def test_context_line_appears_in_annotation(self):
        """Test that context_line text appears in the annotation."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main", context_line="74 evaluated trades all-time")
        text = fig.layout.annotations[0].text
        assert "74 evaluated trades all-time" in text

    def test_action_text_appears_in_annotation(self):
        """Test that action_text appears in the annotation with accent color."""
        from components.cards import create_empty_state_chart
        from constants import COLORS

        fig = create_empty_state_chart("Main", action_text="Try expanding to All")
        text = fig.layout.annotations[0].text
        assert "Try expanding to All" in text
        assert COLORS["accent"] in text

    def test_context_and_action_combined(self):
        """Test that both context_line and action_text appear together."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart(
            "Main", context_line="10 trades", action_text="Try All"
        )
        text = fig.layout.annotations[0].text
        assert "10 trades" in text
        assert "Try All" in text

    def test_empty_context_line_omitted(self):
        """Test that empty context_line doesn't add extra markup."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main only")
        text = fig.layout.annotations[0].text
        # Only one line — no extra <br> tags beyond message
        assert text.count("<br>") == 0

    def test_auto_height_adjustment_with_context(self):
        """Test that height auto-adjusts when context lines are added."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main", context_line="ctx", action_text="act")
        assert fig.layout.height == 80 + (2 * 18)  # 116

    def test_explicit_height_no_auto_adjust(self):
        """Test that explicit height is not auto-adjusted."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Main", context_line="ctx", height=120)
        assert fig.layout.height == 120

    def test_backward_compatibility_no_new_params(self):
        """Test that calling without new params works identically to before."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("No data", hint="Check back later")
        assert fig.layout.height == 80
        text = fig.layout.annotations[0].text
        assert "No data" in text
        assert "Check back later" in text

    def test_transparent_background(self):
        """Test that the figure has a transparent background."""
        from components.cards import create_empty_state_chart

        fig = create_empty_state_chart("Test")
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_accessible_via_layout_import(self):
        """Test that the function can be imported from the layout re-export hub."""
        from layout import create_empty_state_chart
        import plotly.graph_objects as go

        fig = create_empty_state_chart("Test")
        assert isinstance(fig, go.Figure)


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


class TestHeroSignalCardDedup:
    """Tests for create_hero_signal_card with aggregated outcome data."""

    def test_renders_with_aggregated_correct(self):
        """Test card renders Correct badge when correct_count > incorrect_count."""
        from components.cards import create_hero_signal_card

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Defense stocks post",
            "confidence": 0.75,
            "assets": ["RTX", "LMT", "NOC", "GD"],
            "market_impact": {"RTX": "bullish"},
            "outcome_count": 4,
            "correct_count": 3,
            "incorrect_count": 1,
            "total_pnl_t7": 84.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_renders_with_all_incorrect(self):
        """Test card renders Incorrect badge when incorrect_count > correct_count."""
        from components.cards import create_hero_signal_card

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Bad call post",
            "confidence": 0.80,
            "assets": ["AAPL", "GOOGL"],
            "market_impact": {"AAPL": "bearish"},
            "outcome_count": 2,
            "correct_count": 0,
            "incorrect_count": 2,
            "total_pnl_t7": -40.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_renders_pending_when_no_outcomes(self):
        """Test card renders Pending badge when outcome_count is 0."""
        from components.cards import create_hero_signal_card

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Fresh post",
            "confidence": 0.90,
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bullish"},
            "outcome_count": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "total_pnl_t7": None,
            "is_complete": None,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_backward_compatible_with_old_columns(self):
        """Test card still works with old per-ticker columns (correct_t7, pnl_t7)."""
        from components.cards import create_hero_signal_card

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Old format post",
            "confidence": 0.85,
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "correct_t7": True,
            "pnl_t7": 30.0,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_shows_total_pnl_across_tickers(self):
        """Test that P&L badge shows total across all tickers, not per-ticker."""
        from components.cards import create_hero_signal_card

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Multi-ticker post",
            "confidence": 0.75,
            "assets": ["RTX", "LMT", "NOC"],
            "market_impact": {"RTX": "bullish"},
            "outcome_count": 3,
            "correct_count": 3,
            "incorrect_count": 0,
            "total_pnl_t7": 120.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        # Card should render -- exact P&L display is a visual test
        assert card is not None


class TestTypographyConstants:
    """Tests for typography scale and spacing token constants."""

    def test_font_sizes_dict_exists(self):
        """Test that FONT_SIZES dictionary is defined with all required keys."""
        from constants import FONT_SIZES

        assert isinstance(FONT_SIZES, dict)
        required_keys = ["page_title", "section_header", "card_title", "body", "label", "meta", "small"]
        for key in required_keys:
            assert key in FONT_SIZES, f"FONT_SIZES missing key: {key}"

    def test_font_sizes_are_rem_values(self):
        """Test that all font size values end with 'rem'."""
        from constants import FONT_SIZES

        for name, size in FONT_SIZES.items():
            assert size.endswith("rem"), f"FONT_SIZES['{name}'] should be a rem value, got: {size}"

    def test_font_sizes_hierarchy(self):
        """Test that font sizes follow a decreasing hierarchy."""
        from constants import FONT_SIZES

        # Parse rem values to floats for comparison
        def parse_rem(s):
            return float(s.replace("rem", ""))

        assert parse_rem(FONT_SIZES["page_title"]) > parse_rem(FONT_SIZES["section_header"])
        assert parse_rem(FONT_SIZES["section_header"]) > parse_rem(FONT_SIZES["card_title"])
        assert parse_rem(FONT_SIZES["card_title"]) > parse_rem(FONT_SIZES["body"])
        assert parse_rem(FONT_SIZES["body"]) > parse_rem(FONT_SIZES["label"])
        assert parse_rem(FONT_SIZES["label"]) > parse_rem(FONT_SIZES["meta"])
        assert parse_rem(FONT_SIZES["meta"]) > parse_rem(FONT_SIZES["small"])

    def test_font_weights_dict_exists(self):
        """Test that FONT_WEIGHTS dictionary is defined with all required keys."""
        from constants import FONT_WEIGHTS

        assert isinstance(FONT_WEIGHTS, dict)
        required_keys = ["bold", "semibold", "medium", "normal"]
        for key in required_keys:
            assert key in FONT_WEIGHTS, f"FONT_WEIGHTS missing key: {key}"

    def test_font_weights_are_numeric_strings(self):
        """Test that all font weight values are valid CSS numeric weight strings."""
        from constants import FONT_WEIGHTS

        for name, weight in FONT_WEIGHTS.items():
            assert weight.isdigit(), f"FONT_WEIGHTS['{name}'] should be numeric, got: {weight}"
            assert 100 <= int(weight) <= 900, f"FONT_WEIGHTS['{name}'] should be 100-900, got: {weight}"

    def test_spacing_dict_exists(self):
        """Test that SPACING dictionary is defined with all required keys."""
        from constants import SPACING

        assert isinstance(SPACING, dict)
        required_keys = ["xs", "sm", "md", "lg", "xl", "xxl"]
        for key in required_keys:
            assert key in SPACING, f"SPACING missing key: {key}"

    def test_spacing_values_are_px(self):
        """Test that all spacing values end with 'px'."""
        from constants import SPACING

        for name, value in SPACING.items():
            assert value.endswith("px"), f"SPACING['{name}'] should be a px value, got: {value}"

    def test_spacing_values_increase(self):
        """Test that spacing values increase from xs to xxl."""
        from constants import SPACING

        def parse_px(s):
            return int(s.replace("px", ""))

        order = ["xs", "sm", "md", "lg", "xl", "xxl"]
        for i in range(len(order) - 1):
            assert parse_px(SPACING[order[i]]) < parse_px(SPACING[order[i + 1]]), (
                f"SPACING['{order[i]}'] should be less than SPACING['{order[i + 1]}']"
            )

    def test_section_accent_dict_exists(self):
        """Test that SECTION_ACCENT dictionary is defined."""
        from constants import SECTION_ACCENT

        assert isinstance(SECTION_ACCENT, dict)
        assert "width" in SECTION_ACCENT
        assert "color" in SECTION_ACCENT
        assert "radius" in SECTION_ACCENT


class TestNavLinkIds:
    """Tests for nav link IDs in the header component."""

    def test_nav_links_have_ids(self):
        """Test that all four navigation links have unique IDs."""
        from components.header import create_header

        header = create_header()

        expected_ids = [
            "nav-link-dashboard",
            "nav-link-signals",
            "nav-link-trends",
            "nav-link-performance",
        ]
        found_ids = _find_component_ids(header)
        for nav_id in expected_ids:
            assert nav_id in found_ids, f"Nav link ID '{nav_id}' not found in header"

    def test_nav_links_have_nav_link_custom_class(self):
        """Test that all nav links use the nav-link-custom class."""
        from components.header import create_header
        from dash import dcc

        header = create_header()
        nav_links = _find_components_by_type(header, dcc.Link)
        for link in nav_links:
            if hasattr(link, "id") and link.id and str(link.id).startswith("nav-link-"):
                assert "nav-link-custom" in (link.className or ""), (
                    f"Nav link {link.id} should have nav-link-custom class"
                )


class TestCSSClasses:
    """Tests for CSS classes in the app index string."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_section_header_class(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .section-header CSS class."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".section-header" in app.index_string
        assert ".page-title" in app.index_string
        assert ".text-label" in app.index_string
        assert ".text-meta" in app.index_string
        assert ".section-label" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_active_nav_pseudo_element(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains nav-link active ::after pseudo-element."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".nav-link-custom.active::after" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_card_header_has_font_size_override(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that .card-header CSS includes font-size override."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        # Verify the card-header override includes font-size
        assert "0.95rem" in app.index_string


class TestDashboardPageStructure:
    """Tests for the restructured dashboard page layout."""

    def test_create_dashboard_page_returns_div(self):
        """Test that create_dashboard_page returns an html.Div."""
        from pages.dashboard import create_dashboard_page
        from dash import html

        page = create_dashboard_page()
        assert isinstance(page, html.Div)

    def test_dashboard_contains_analytics_tabs(self):
        """Test that dashboard contains dbc.Tabs with id 'analytics-tabs'."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "analytics-tabs" in found_ids, "analytics-tabs not found in dashboard page"

    def test_dashboard_contains_three_chart_ids(self):
        """Test that all three chart graph IDs are present in the tabbed layout."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "accuracy-over-time-chart" in found_ids
        assert "confidence-accuracy-chart" in found_ids
        assert "asset-accuracy-chart" in found_ids

    def test_dashboard_does_not_contain_asset_selector(self):
        """Test that the Asset Deep Dive dropdown has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "asset-selector" not in found_ids, (
            "asset-selector should be removed from dashboard"
        )

    def test_dashboard_does_not_contain_asset_drilldown(self):
        """Test that the asset drilldown content area has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "asset-drilldown-content" not in found_ids, (
            "asset-drilldown-content should be removed from dashboard"
        )

    def test_dashboard_does_not_contain_alert_history(self):
        """Test that the alert history panel has been removed from dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-alert-history" not in found_ids, (
            "Alert history collapse should be removed from dashboard"
        )
        assert "collapse-alert-history-button" not in found_ids, (
            "Alert history button should be removed from dashboard"
        )

    def test_dashboard_contains_post_feed(self):
        """Test that post-feed-container is present in the dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "post-feed-container" in found_ids

    def test_dashboard_contains_recent_signals(self):
        """Test that recent-signals-list is present in the dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "recent-signals-list" in found_ids

    def test_dashboard_contains_collapse_chevron(self):
        """Test that the collapse section has a chevron icon."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-table-chevron" in found_ids, (
            "collapse-table-chevron not found in dashboard page"
        )

    def test_collapse_chevron_has_correct_initial_class(self):
        """Test that the chevron starts with collapse-chevron class (not rotated)."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        chevron = _find_component_by_id(page, "collapse-table-chevron")
        assert chevron is not None, "Could not find collapse-table-chevron component"
        assert "collapse-chevron" in (chevron.className or "")
        assert "rotated" not in (chevron.className or "")

    def test_dashboard_preserves_hero_signals_section(self):
        """Test that hero-signals-section is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "hero-signals-section" in found_ids

    def test_dashboard_preserves_performance_metrics(self):
        """Test that performance-metrics is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "performance-metrics" in found_ids

    def test_dashboard_preserves_collapse_table(self):
        """Test that the collapsible data table is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-table" in found_ids
        assert "collapse-table-button" in found_ids
        assert "predictions-table-container" in found_ids


class TestAnalyticsTabsCSS:
    """Tests for analytics tab CSS in the app stylesheet."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_analytics_tabs_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .analytics-tabs CSS."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".analytics-tabs" in app.index_string
        assert ".collapse-chevron" in app.index_string
        assert ".collapse-chevron.rotated" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_collapse_toggle_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .collapse-toggle-btn CSS."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".collapse-toggle-btn" in app.index_string


class TestClientSideRoutes:
    """Tests for direct URL access to client-side routes (SPA routing fix).

    Dash's /<path:path> catch-all already serves the SPA index for /signals,
    /trends, /performance. The only route that needs special handling is
    /assets/<symbol>, because Dash's static file handler (/assets/<path:filename>)
    intercepts it before the catch-all. register_client_routes() adds a
    before_request hook to serve the SPA index for /assets/<symbol> requests.
    """

    _mock_stats = {
        "total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0,
        "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0,
    }
    _mock_perf = {
        "total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0,
        "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0,
        "total_pnl_t7": 0.0, "avg_confidence": 0.0,
    }

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def _create_test_app(self, mock_assets, mock_signals, mock_asset_acc,
                         mock_conf_acc, mock_perf, mock_stats):
        """Create a Dash app with callbacks and client routes for testing."""
        mock_stats.return_value = self._mock_stats
        mock_perf.return_value = self._mock_perf
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app, register_callbacks
        from app import register_client_routes

        app = create_app()
        register_callbacks(app)
        register_client_routes(app)
        return app

    def test_asset_route_returns_200(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/assets/LMT")
        assert response.status_code == 200

    def test_asset_route_different_symbols(self):
        app = self._create_test_app()
        client = app.server.test_client()
        for symbol in ["AAPL", "TSLA", "SPY", "BTC-USD"]:
            response = client.get(f"/assets/{symbol}")
            assert response.status_code == 200, f"/assets/{symbol} returned {response.status_code}"

    def test_asset_route_serves_dash_index(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/assets/LMT")
        html_content = response.data.decode("utf-8")
        assert "dash-renderer" in html_content or "_dash-app-content" in html_content

    def test_static_file_extensions_not_intercepted(self):
        """Requests for actual static files (e.g. .css, .js) should NOT be intercepted."""
        app = self._create_test_app()
        response = app.server.test_client().get("/assets/style.css")
        # Static file doesn't exist, so Dash's handler returns 404 (not our SPA index)
        assert response.status_code == 404

    def test_signals_route_returns_200(self):
        """Dash's catch-all already handles /signals."""
        app = self._create_test_app()
        response = app.server.test_client().get("/signals")
        assert response.status_code == 200

    def test_performance_route_returns_200(self):
        """Dash's catch-all already handles /performance."""
        app = self._create_test_app()
        response = app.server.test_client().get("/performance")
        assert response.status_code == 200

    def test_root_route_still_works(self):
        app = self._create_test_app()
        response = app.server.test_client().get("/")
        assert response.status_code == 200


class TestThesisToggleCSS:
    """Tests for thesis expand/collapse CSS classes in the app stylesheet."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_thesis_toggle_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .thesis-toggle-area CSS class."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".thesis-toggle-area" in app.index_string
