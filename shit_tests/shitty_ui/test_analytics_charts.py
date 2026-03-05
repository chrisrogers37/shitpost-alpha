"""Tests for analytics chart builders and analytics callbacks."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date

from components.charts import (
    build_cumulative_pnl_chart,
    build_rolling_accuracy_chart,
    build_confidence_calibration_chart,
    build_backtest_equity_chart,
    build_empty_signal_chart,
)
from constants import ANALYTICS_COLORS, COLORS


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


def _make_pnl_df():
    """Sample cumulative P&L data."""
    return pd.DataFrame(
        {
            "prediction_date": pd.to_datetime(
                [
                    "2025-06-01",
                    "2025-06-02",
                    "2025-06-03",
                    "2025-06-04",
                    "2025-06-05",
                ]
            ),
            "daily_pnl": [50.0, -20.0, 80.0, -10.0, 30.0],
            "predictions_count": [2, 1, 3, 1, 2],
            "cumulative_pnl": [50.0, 30.0, 110.0, 100.0, 130.0],
        }
    )


def _make_rolling_accuracy_df():
    """Sample rolling accuracy data."""
    return pd.DataFrame(
        {
            "prediction_date": pd.to_datetime(
                [
                    "2025-06-01",
                    "2025-06-02",
                    "2025-06-03",
                    "2025-06-04",
                ]
            ),
            "correct": [1, 2, 1, 3],
            "total": [2, 3, 2, 4],
            "rolling_accuracy": [50.0, 57.1, 55.0, 63.6],
        }
    )


def _make_calibration_df():
    """Sample confidence calibration data."""
    return pd.DataFrame(
        {
            "bucket_start": [0.5, 0.6, 0.7, 0.8],
            "total": [10, 15, 20, 8],
            "correct": [4, 9, 15, 7],
            "avg_confidence": [0.55, 0.67, 0.74, 0.85],
            "actual_accuracy": [40.0, 60.0, 75.0, 87.5],
            "predicted_confidence": [55.0, 67.0, 74.0, 85.0],
            "bucket_label": ["50-60%", "60-70%", "70-80%", "80-90%"],
        }
    )


def _make_backtest_df(initial_capital=10000):
    """Sample backtest equity curve data."""
    return pd.DataFrame(
        {
            "prediction_date": pd.to_datetime(
                [
                    "2025-06-01",
                    "2025-06-02",
                    "2025-06-03",
                    "2025-06-04",
                ]
            ),
            "daily_pnl": [100.0, -50.0, 200.0, 75.0],
            "trade_count": [1, 1, 2, 1],
            "cumulative_pnl": [100.0, 50.0, 250.0, 325.0],
            "equity": [10100.0, 10050.0, 10250.0, 10325.0],
        }
    )


# ──────────────────────────────────────────────────────────────────────
# Cumulative P&L Chart
# ──────────────────────────────────────────────────────────────────────


class TestBuildCumulativePnlChart:
    """Tests for build_cumulative_pnl_chart."""

    def test_returns_figure_with_data(self):
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_chart(self):
        fig = build_cumulative_pnl_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) == 1

    def test_has_line_trace(self):
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter)]
        assert len(scatter_traces) >= 1
        assert scatter_traces[0].mode == "lines"

    def test_line_uses_equity_color(self):
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        line_trace = [t for t in fig.data if isinstance(t, go.Scatter)][0]
        assert line_trace.line.color == ANALYTICS_COLORS["equity_line"]

    def test_has_fill_to_zero(self):
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        line_trace = [t for t in fig.data if isinstance(t, go.Scatter)][0]
        assert line_trace.fill == "tozeroy"

    def test_yaxis_has_dollar_prefix(self):
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        assert fig.layout.yaxis.tickprefix == "$"

    def test_has_zero_reference_line(self):
        """Chart should have an hline shape at y=0."""
        fig = build_cumulative_pnl_chart(_make_pnl_df())
        shapes = fig.layout.shapes
        assert shapes is not None
        assert len(shapes) >= 1
        # hline at y=0
        assert any(s.y0 == 0 and s.y1 == 0 for s in shapes)


# ──────────────────────────────────────────────────────────────────────
# Rolling Accuracy Chart
# ──────────────────────────────────────────────────────────────────────


class TestBuildRollingAccuracyChart:
    """Tests for build_rolling_accuracy_chart."""

    def test_returns_figure_with_data(self):
        fig = build_rolling_accuracy_chart(_make_rolling_accuracy_df())
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_chart(self):
        fig = build_rolling_accuracy_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) >= 1

    def test_has_accuracy_line(self):
        fig = build_rolling_accuracy_chart(_make_rolling_accuracy_df())
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter)]
        assert len(scatter_traces) >= 1

    def test_line_uses_rolling_color(self):
        fig = build_rolling_accuracy_chart(_make_rolling_accuracy_df())
        line_trace = [t for t in fig.data if isinstance(t, go.Scatter)][0]
        assert line_trace.line.color == ANALYTICS_COLORS["rolling_line"]

    def test_yaxis_range_is_0_to_105(self):
        fig = build_rolling_accuracy_chart(_make_rolling_accuracy_df())
        assert tuple(fig.layout.yaxis.range) == (0, 105)

    def test_has_50_percent_baseline(self):
        """Should have a reference line at 50%."""
        fig = build_rolling_accuracy_chart(_make_rolling_accuracy_df())
        shapes = fig.layout.shapes
        assert shapes is not None
        assert any(s.y0 == 50 and s.y1 == 50 for s in shapes)

    def test_missing_rolling_accuracy_column(self):
        """DataFrame without rolling_accuracy column returns empty chart."""
        df = pd.DataFrame({"prediction_date": ["2025-06-01"], "correct": [1]})
        fig = build_rolling_accuracy_chart(df)
        assert len(fig.layout.annotations) >= 1


# ──────────────────────────────────────────────────────────────────────
# Confidence Calibration Chart
# ──────────────────────────────────────────────────────────────────────


class TestBuildConfidenceCalibrationChart:
    """Tests for build_confidence_calibration_chart."""

    def test_returns_figure_with_data(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_chart(self):
        fig = build_confidence_calibration_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) >= 1

    def test_has_two_bar_traces(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
        assert len(bar_traces) == 2

    def test_predicted_bar_uses_correct_color(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
        assert bar_traces[0].marker.color == ANALYTICS_COLORS["calibration_predicted"]

    def test_actual_bar_uses_correct_color(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
        assert bar_traces[1].marker.color == ANALYTICS_COLORS["calibration_actual"]

    def test_has_grouped_barmode(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        assert fig.layout.barmode == "group"

    def test_legend_shown(self):
        fig = build_confidence_calibration_chart(_make_calibration_df())
        assert fig.layout.showlegend is True

    def test_has_reference_line_trace(self):
        """Should have a dotted reference line for perfect calibration."""
        fig = build_confidence_calibration_chart(_make_calibration_df())
        line_traces = [
            t for t in fig.data if isinstance(t, go.Scatter) and t.line.dash == "dot"
        ]
        assert len(line_traces) == 1


# ──────────────────────────────────────────────────────────────────────
# Backtest Equity Chart
# ──────────────────────────────────────────────────────────────────────


class TestBuildBacktestEquityChart:
    """Tests for build_backtest_equity_chart."""

    def test_returns_figure_with_data(self):
        fig = build_backtest_equity_chart(_make_backtest_df())
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_chart(self):
        fig = build_backtest_equity_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) >= 1

    def test_has_equity_line_trace(self):
        fig = build_backtest_equity_chart(_make_backtest_df())
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter)]
        assert len(scatter_traces) >= 1

    def test_line_uses_backtest_color(self):
        fig = build_backtest_equity_chart(_make_backtest_df())
        line_trace = [t for t in fig.data if isinstance(t, go.Scatter)][0]
        assert line_trace.line.color == ANALYTICS_COLORS["backtest_line"]

    def test_has_starting_capital_reference(self):
        """Should have a reference line at initial capital."""
        fig = build_backtest_equity_chart(_make_backtest_df(), initial_capital=10000)
        shapes = fig.layout.shapes
        assert shapes is not None
        assert any(s.y0 == 10000 for s in shapes)

    def test_custom_initial_capital(self):
        """Reference line adapts to custom initial_capital."""
        fig = build_backtest_equity_chart(
            _make_backtest_df(25000), initial_capital=25000
        )
        shapes = fig.layout.shapes
        assert any(s.y0 == 25000 for s in shapes)

    def test_yaxis_has_dollar_prefix(self):
        fig = build_backtest_equity_chart(_make_backtest_df())
        assert fig.layout.yaxis.tickprefix == "$"
