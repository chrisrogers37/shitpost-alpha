"""Tests for shitty_ui/components/charts.py - Reusable chart builders."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from components.charts import build_signal_over_trend_chart, build_empty_signal_chart, apply_chart_layout
from constants import CHART_LAYOUT, CHART_COLORS, CHART_CONFIG, COLORS


def _make_prices_df():
    """Create a sample prices DataFrame for testing."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04"]),
        "open": [100.0, 101.0, 102.0, 103.0],
        "high": [105.0, 106.0, 107.0, 108.0],
        "low": [99.0, 100.0, 101.0, 102.0],
        "close": [103.0, 104.0, 105.0, 106.0],
        "volume": [1000, 1100, 1200, 1300],
    })


def _make_signals_df(**overrides):
    """Create a sample signals DataFrame for testing."""
    data = {
        "prediction_date": pd.to_datetime(["2025-06-02"]),
        "prediction_sentiment": ["bullish"],
        "prediction_confidence": [0.85],
        "thesis": ["Strong earnings expected"],
        "correct_t7": [True],
        "return_t7": [2.5],
        "pnl_t7": [250.0],
        "post_text": ["Tariffs are great for business"],
        "price_at_prediction": [104.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


class TestBuildSignalOverTrendChart:
    """Tests for build_signal_over_trend_chart."""

    def test_returns_figure_with_valid_data(self):
        """Test that a go.Figure is returned with valid price and signal data."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(),
            symbol="TEST",
        )
        assert isinstance(fig, go.Figure)
        # Should have candlestick + signal marker + 3 legend traces
        assert len(fig.data) >= 2

    def test_returns_figure_with_empty_signals(self):
        """Test that chart renders with prices only when signals are empty."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        assert isinstance(fig, go.Figure)
        # Candlestick + 3 legend traces (no signal markers)
        assert len(fig.data) >= 1

    def test_returns_figure_with_empty_prices(self):
        """Test that chart renders gracefully with no price data."""
        fig = build_signal_over_trend_chart(
            prices_df=pd.DataFrame(),
            signals_df=_make_signals_df(),
            symbol="TEST",
        )
        assert isinstance(fig, go.Figure)

    def test_marker_color_matches_sentiment(self):
        """Test that bullish signals get green markers."""
        from constants import SENTIMENT_COLORS

        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(prediction_sentiment=["bullish"]),
            symbol="TEST",
        )
        # Find the scatter trace (not candlestick, not legend traces)
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        assert len(scatter_traces) >= 1
        assert scatter_traces[0].marker.color == SENTIMENT_COLORS["bullish"]

    def test_bearish_marker_color(self):
        """Test that bearish signals get red markers."""
        from constants import SENTIMENT_COLORS

        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(prediction_sentiment=["bearish"]),
            symbol="TEST",
        )
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        assert len(scatter_traces) >= 1
        assert scatter_traces[0].marker.color == SENTIMENT_COLORS["bearish"]

    def test_marker_size_scales_with_confidence(self):
        """Test that higher confidence = larger marker."""
        from constants import MARKER_CONFIG

        # High confidence
        fig_high = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(prediction_confidence=[0.95]),
            symbol="TEST",
        )
        # Low confidence
        fig_low = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(prediction_confidence=[0.1]),
            symbol="TEST",
        )

        high_traces = [t for t in fig_high.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        low_traces = [t for t in fig_low.data if isinstance(t, go.Scatter) and t.x[0] is not None]

        assert high_traces[0].marker.size > low_traces[0].marker.size

    def test_timeframe_windows_added_when_enabled(self):
        """Test that vrects are added when show_timeframe_windows=True."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(),
            symbol="TEST",
            show_timeframe_windows=True,
        )
        # Should have at least one shape (vrect)
        shapes = fig.layout.shapes
        assert shapes is not None
        assert len(shapes) >= 1

    def test_timeframe_windows_not_added_when_disabled(self):
        """Test that no vrects when show_timeframe_windows=False."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(),
            symbol="TEST",
            show_timeframe_windows=False,
        )
        shapes = fig.layout.shapes
        assert shapes is None or len(shapes) == 0

    def test_hover_template_contains_confidence(self):
        """Test that hover text includes the confidence value."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(prediction_confidence=[0.85]),
            symbol="TEST",
        )
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        assert "85%" in scatter_traces[0].hovertemplate

    def test_hover_template_contains_thesis(self):
        """Test that hover text includes thesis text."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(thesis=["My investment thesis"]),
            symbol="TEST",
        )
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        assert "My investment thesis" in scatter_traces[0].hovertemplate

    def test_sentiment_legend_traces_added(self):
        """Test that legend traces are present for all sentiments."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=_make_signals_df(),
            symbol="TEST",
        )
        legend_names = [t.name for t in fig.data if t.showlegend]
        assert "Bullish" in legend_names
        assert "Bearish" in legend_names
        assert "Neutral" in legend_names

    def test_signal_on_weekend_skipped(self):
        """Test that a signal on a date with no price data is gracefully skipped."""
        # Signal date doesn't match any price date
        signals = _make_signals_df(
            prediction_date=pd.to_datetime(["2025-06-07"])  # Saturday
        )
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=signals,
            symbol="TEST",
        )
        # Should only have candlestick + 3 legend traces (no marker since no match)
        scatter_with_data = [t for t in fig.data if isinstance(t, go.Scatter) and t.x[0] is not None]
        assert len(scatter_with_data) == 0


class TestBuildEmptySignalChart:
    """Tests for build_empty_signal_chart."""

    def test_returns_figure(self):
        """Test that an empty chart returns a go.Figure."""
        fig = build_empty_signal_chart()
        assert isinstance(fig, go.Figure)

    def test_contains_annotation_message(self):
        """Test that the annotation contains the provided message."""
        fig = build_empty_signal_chart("Custom message here")
        annotations = fig.layout.annotations
        assert len(annotations) == 1
        assert annotations[0].text == "Custom message here"

    def test_default_message(self):
        """Test that the default message is 'No data available'."""
        fig = build_empty_signal_chart()
        assert fig.layout.annotations[0].text == "No data available"


class TestApplyChartLayout:
    """Tests for the shared apply_chart_layout() helper."""

    def test_sets_transparent_backgrounds(self):
        """Base layout must set transparent plot and paper backgrounds."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_sets_height(self):
        """Height parameter is applied to the figure layout."""
        fig = go.Figure()
        apply_chart_layout(fig, height=450)
        assert fig.layout.height == 450

    def test_default_height_is_300(self):
        """Default height should be 300 if not specified."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.height == 300

    def test_show_legend_false_by_default(self):
        """Legend should be hidden by default."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.showlegend is False

    def test_show_legend_override(self):
        """show_legend=True enables the legend."""
        fig = go.Figure()
        apply_chart_layout(fig, show_legend=True)
        assert fig.layout.showlegend is True

    def test_yaxis_override_preserves_gridcolor(self):
        """Overriding yaxis title should not lose gridcolor from base."""
        fig = go.Figure()
        apply_chart_layout(fig, yaxis={"title": "Accuracy %"})
        assert fig.layout.yaxis.title.text == "Accuracy %"
        assert fig.layout.yaxis.gridcolor is not None
        assert "51, 65, 85" in fig.layout.yaxis.gridcolor

    def test_xaxis_override_preserves_gridcolor(self):
        """Overriding xaxis should not lose gridcolor from base."""
        fig = go.Figure()
        apply_chart_layout(fig, xaxis={"rangeslider": {"visible": False}})
        assert fig.layout.xaxis.gridcolor is not None

    def test_hoverlabel_styling(self):
        """Base layout must set dark hoverlabel with matching font."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"
        assert fig.layout.hoverlabel.bordercolor == "#334155"
        assert fig.layout.hoverlabel.font.color == "#f1f5f9"

    def test_font_family_set(self):
        """Base layout must set system font stack."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert "apple-system" in fig.layout.font.family

    def test_arbitrary_overrides(self):
        """Extra kwargs are passed through to update_layout."""
        fig = go.Figure()
        apply_chart_layout(fig, hovermode="closest", bargap=0.3)
        assert fig.layout.hovermode == "closest"
        assert fig.layout.bargap == 0.3

    def test_returns_same_figure(self):
        """Function returns the same figure object for chaining."""
        fig = go.Figure()
        result = apply_chart_layout(fig)
        assert result is fig


class TestChartConstants:
    """Tests for the chart constant dicts in constants.py."""

    def test_chart_layout_has_required_keys(self):
        """CHART_LAYOUT must contain all essential layout keys."""
        required = [
            "plot_bgcolor", "paper_bgcolor", "font", "margin",
            "xaxis", "yaxis", "hoverlabel", "showlegend",
        ]
        for key in required:
            assert key in CHART_LAYOUT, f"Missing key: {key}"

    def test_chart_config_disables_modebar(self):
        """CHART_CONFIG must suppress the modebar."""
        assert CHART_CONFIG["displayModeBar"] is False
        assert CHART_CONFIG["displaylogo"] is False

    def test_chart_colors_has_candle_colors(self):
        """CHART_COLORS must have candlestick color keys."""
        for key in ["candle_up", "candle_down", "candle_up_fill", "candle_down_fill"]:
            assert key in CHART_COLORS, f"Missing key: {key}"

    def test_chart_colors_match_app_palette(self):
        """Candle colors must match COLORS success/danger."""
        assert CHART_COLORS["candle_up"] == COLORS["success"]
        assert CHART_COLORS["candle_down"] == COLORS["danger"]

    def test_bar_palette_has_minimum_colors(self):
        """Bar palette must have at least 4 colors for multi-series charts."""
        assert len(CHART_COLORS["bar_palette"]) >= 4


class TestCandlestickChartRestyled:
    """Tests that build_signal_over_trend_chart uses new chart colors."""

    def test_candlestick_uses_chart_colors(self):
        """Candlestick trace must use CHART_COLORS instead of COLORS."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        candle_trace = [t for t in fig.data if isinstance(t, go.Candlestick)]
        assert len(candle_trace) == 1
        assert candle_trace[0].increasing.line.color == CHART_COLORS["candle_up"]
        assert candle_trace[0].decreasing.line.color == CHART_COLORS["candle_down"]

    def test_candlestick_has_explicit_fill_colors(self):
        """Candlestick fill colors must be explicitly set (not Plotly defaults)."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        candle_trace = [t for t in fig.data if isinstance(t, go.Candlestick)][0]
        assert candle_trace.increasing.fillcolor == CHART_COLORS["candle_up_fill"]
        assert candle_trace.decreasing.fillcolor == CHART_COLORS["candle_down_fill"]

    def test_layout_uses_apply_chart_layout(self):
        """Chart layout must have hoverlabel styling from shared base."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"

    def test_rangeslider_hidden(self):
        """Candlestick range slider must be hidden."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        assert fig.layout.xaxis.rangeslider.visible is False


class TestEmptyChartRestyled:
    """Tests that build_empty_signal_chart uses apply_chart_layout."""

    def test_empty_chart_has_hoverlabel(self):
        """Empty chart must have hoverlabel styling from shared base."""
        fig = build_empty_signal_chart("test message")
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"

    def test_empty_chart_hides_gridlines(self):
        """Empty chart must hide all gridlines and tick labels."""
        fig = build_empty_signal_chart()
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False
