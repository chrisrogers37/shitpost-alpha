"""Tests for shitty_ui/components/sparkline.py - Sparkline chart components."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
from datetime import date, datetime
import plotly.graph_objects as go
from dash import dcc, html

from components.sparkline import (
    build_sparkline_figure,
    create_sparkline_component,
    create_sparkline_placeholder,
)
from constants import SPARKLINE_CONFIG, COLORS


def _make_price_df(closes: list, start_date: str = "2025-06-10") -> pd.DataFrame:
    """Create a minimal price DataFrame for testing."""
    dates = pd.bdate_range(start=start_date, periods=len(closes))
    return pd.DataFrame({"date": dates, "close": closes})


class TestBuildSparklineFigure:
    """Tests for the build_sparkline_figure function."""

    def test_returns_go_figure(self):
        """Function returns a Plotly Figure."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df)
        assert isinstance(fig, go.Figure)

    def test_has_one_trace_without_prediction_date(self):
        """Without prediction_date, only the price line trace exists."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df)
        assert len(fig.data) == 1

    def test_has_two_traces_with_prediction_date(self):
        """With prediction_date, a marker trace is added."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df, prediction_date=date(2025, 6, 12))
        assert len(fig.data) == 2

    def test_line_color_green_when_price_up(self):
        """Line should be green (success) when price increased > 0.5%."""
        df = _make_price_df([100, 102, 104, 106, 108])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_up"]

    def test_line_color_red_when_price_down(self):
        """Line should be red (danger) when price decreased > 0.5%."""
        df = _make_price_df([108, 106, 104, 102, 100])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_down"]

    def test_line_color_muted_when_flat(self):
        """Line should be muted when price change < 0.5%."""
        df = _make_price_df([100.0, 100.1, 100.0, 99.9, 100.2])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_flat"]

    def test_layout_has_no_axes(self):
        """Sparkline should hide all axis chrome."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False

    def test_layout_dimensions_match_config(self):
        """Figure dimensions should match SPARKLINE_CONFIG."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.height == SPARKLINE_CONFIG["height"]
        assert fig.layout.width == SPARKLINE_CONFIG["width"]

    def test_transparent_background(self):
        """Background should be fully transparent."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_zero_margins(self):
        """All margins should be zero for tight embedding."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.margin.l == 0
        assert fig.layout.margin.r == 0
        assert fig.layout.margin.t == 0
        assert fig.layout.margin.b == 0

    def test_marker_placed_near_prediction_date(self):
        """Marker trace should be placed at the prediction date."""
        df = _make_price_df([100, 101, 102, 103, 104], start_date="2025-06-10")
        fig = build_sparkline_figure(df, prediction_date=date(2025, 6, 12))
        marker_trace = fig.data[1]
        assert marker_trace.marker.color == SPARKLINE_CONFIG["marker_color"]
        assert marker_trace.marker.size == SPARKLINE_CONFIG["marker_size"]

    def test_fill_under_line(self):
        """Price trace should have fill='tozeroy'."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.data[0].fill == "tozeroy"

    def test_no_legend(self):
        """Sparkline should not show any legend."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.showlegend is False


class TestCreateSparklineComponent:
    """Tests for the create_sparkline_component wrapper."""

    def test_returns_dcc_graph(self):
        """Should return a dcc.Graph component."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert isinstance(component, dcc.Graph)

    def test_display_mode_bar_disabled(self):
        """The Plotly modebar should be hidden."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert component.config["displayModeBar"] is False

    def test_dimensions_in_style(self):
        """Component style should set width and height from config."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert f"{SPARKLINE_CONFIG['width']}px" in component.style["width"]
        assert f"{SPARKLINE_CONFIG['height']}px" in component.style["height"]

    def test_custom_component_id(self):
        """Custom component_id should be used as the Graph id."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df, component_id="my-sparkline")
        assert component.id == "my-sparkline"


class TestCreateSparklinePlaceholder:
    """Tests for the create_sparkline_placeholder function."""

    def test_returns_html_div(self):
        """Should return an html.Div component."""
        placeholder = create_sparkline_placeholder()
        assert isinstance(placeholder, html.Div)

    def test_has_matching_dimensions(self):
        """Placeholder should match sparkline dimensions for layout consistency."""
        placeholder = create_sparkline_placeholder()
        assert f"{SPARKLINE_CONFIG['width']}px" in placeholder.style["width"]
        assert f"{SPARKLINE_CONFIG['height']}px" in placeholder.style["height"]

    def test_shows_no_data_text(self):
        """Placeholder should show 'No price data' text."""
        placeholder = create_sparkline_placeholder()
        span = placeholder.children
        assert hasattr(span, "children")
        assert "No price data" in span.children

    def test_has_dashed_border(self):
        """Placeholder should have a dashed border for visual distinction."""
        placeholder = create_sparkline_placeholder()
        assert "dashed" in placeholder.style["border"]
