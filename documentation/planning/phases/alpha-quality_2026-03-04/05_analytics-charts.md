# Phase 05: Wire Existing Analytics Charts

**PR Title:** feat: add analytics charts section to dashboard with equity curve, rolling accuracy, calibration, and backtest simulator

**Risk Level:** Medium
**Estimated Effort:** Medium (3-4 days)

**Files Created:** 3
- `shitty_ui/pages/dashboard_callbacks/analytics.py`
- `shitty_ui/data/backtest_queries.py`
- `shit_tests/shitty_ui/test_analytics_charts.py`

**Files Modified:** 7
- `shitty_ui/components/charts.py`
- `shitty_ui/pages/dashboard.py`
- `shitty_ui/pages/dashboard_callbacks/__init__.py`
- `shitty_ui/data/performance_queries.py`
- `shitty_ui/data/__init__.py`
- `shitty_ui/brand_copy.py`
- `shitty_ui/constants.py`

---

## Context

Four advanced analytics query functions exist in `shitty_ui/data/performance_queries.py` -- `get_cumulative_pnl()`, `get_rolling_accuracy()`, `get_confidence_calibration()`, and `get_backtest_simulation()` -- but none of them are connected to any UI component. The dashboard currently shows KPIs, an asset screener, a post feed, and a collapsible data table, but has no visual charts on the main page.

This phase adds an "Analytics" collapsible section to the dashboard (between the screener and the post feed, matching the Secondary visual tier) with four charts:
1. **Cumulative P&L Equity Curve** -- line chart from `get_cumulative_pnl()`
2. **Rolling Accuracy** -- line chart from `get_rolling_accuracy()`
3. **Confidence Calibration** -- grouped bar chart from `get_confidence_calibration()`
4. **Backtest Simulator** -- interactive equity curve with configurable inputs, requiring a new time-series query function

The existing `get_backtest_simulation()` only returns a summary dict (final_value, win_rate, etc.), not a date-ordered time series. For a proper backtest chart, we need a new query that returns the cumulative equity curve filtered by confidence threshold.

---

## Dependencies

- **Depends on:** None. All four query functions already exist and are exported. This phase only adds UI components.
- **Unlocks:** None directly, but enables future enhancements like additional chart types or a dedicated `/analytics` page.

---

## Detailed Implementation Plan

### Step 1: Add new brand copy entries

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/brand_copy.py`

Add entries to the `COPY` dict after the existing `"analytics_header"` key (line 32). The existing entries on lines 32-35 are already there for `analytics_header`, `tab_accuracy`, `tab_confidence`, `tab_asset`. Add these new entries immediately after line 35:

```python
    # ===== Dashboard: Analytics Charts Section =====
    "analytics_section_subtitle": "equity curves, accuracy trends, and backtesting (the real stuff)",
    "analytics_pnl_tab": "Equity Curve",
    "analytics_rolling_tab": "Rolling Accuracy",
    "analytics_calibration_tab": "Calibration",
    "analytics_backtest_tab": "Backtest Simulator",
    "analytics_empty_pnl": "No P&L data yet. Predictions need 7+ trading days to mature.",
    "analytics_empty_rolling": "Not enough data points for rolling accuracy.",
    "analytics_empty_calibration": "No calibration data. Need evaluated predictions first.",
    "analytics_empty_backtest": "No backtest data for these settings.",
    "analytics_backtest_capital_label": "Starting Capital ($)",
    "analytics_backtest_confidence_label": "Min Confidence",
```

### Step 2: Add analytics chart color constants

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/constants.py`

Add a new section after the existing `CHART_COLORS` dict (after line 200):

```python
# Analytics chart-specific colors
ANALYTICS_COLORS = {
    "equity_line": "#85BB65",       # Dollar bill green -- main equity curve
    "equity_fill": "rgba(133, 187, 101, 0.12)",  # Subtle green fill
    "zero_line": "rgba(139, 154, 126, 0.4)",     # Sage muted -- $0 reference
    "rolling_line": "#FFD700",      # Gold -- rolling accuracy
    "rolling_fill": "rgba(255, 215, 0, 0.08)",   # Subtle gold fill
    "calibration_predicted": "#85BB65",  # Dollar green -- predicted confidence bar
    "calibration_actual": "#FFD700",     # Gold -- actual accuracy bar
    "calibration_perfect": "rgba(139, 154, 126, 0.3)",  # Sage -- diagonal reference
    "backtest_line": "#85BB65",     # Dollar green -- equity curve
    "backtest_fill": "rgba(133, 187, 101, 0.10)",
    "backtest_start": "#FFD700",    # Gold -- starting capital marker
}
```

### Step 3: Add new backtest time-series query function

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/backtest_queries.py` (NEW FILE)

This file provides the date-ordered time-series version of the backtest simulation that the chart needs. The existing `get_backtest_simulation()` in `performance_queries.py` returns only a summary dict -- it does not include `prediction_date`, so it cannot power a line chart showing equity growth over time.

```python
"""Backtest simulation queries returning time-series data for charts.

Supplements the summary-only get_backtest_simulation() in performance_queries
with a date-ordered DataFrame suitable for plotting equity curves.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import text

import data.base as _base
from data.base import ttl_cache, logger


@ttl_cache(ttl_seconds=300)
def get_backtest_equity_curve(
    initial_capital: float = 10000,
    min_confidence: float = 0.75,
    days: int = None,
) -> pd.DataFrame:
    """Get date-ordered equity curve for backtest simulation chart.

    Returns the same trade-by-trade P&L data as get_backtest_simulation()
    but includes prediction_date so it can be plotted as a time series.

    Args:
        initial_capital: Starting capital in dollars.
        min_confidence: Minimum prediction confidence threshold to include.
        days: Number of days to look back (None = all time).

    Returns:
        DataFrame with columns:
            prediction_date, pnl_t7, cumulative_pnl, equity
        Where equity = initial_capital + cumulative_pnl.
        Empty DataFrame if no data.
    """
    date_filter = ""
    params: Dict[str, Any] = {"min_confidence": min_confidence}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_date,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as daily_pnl,
            COUNT(*) as trade_count
        FROM prediction_outcomes
        WHERE prediction_confidence >= :min_confidence
            AND correct_t7 IS NOT NULL
            AND return_t7 IS NOT NULL
            {date_filter}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["cumulative_pnl"] = df["daily_pnl"].cumsum()
            df["equity"] = initial_capital + df["cumulative_pnl"]
        return df
    except Exception as e:
        logger.error(f"Error loading backtest equity curve: {e}")
        return pd.DataFrame()
```

### Step 4: Export the new query function

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/__init__.py`

Add the import and export for the new backtest query module. After line 82 (the insight_queries import block), add:

```python
# --- Backtest queries ---
from data.backtest_queries import (  # noqa: F401
    get_backtest_equity_curve,
)
```

In the `clear_all_caches()` function (around line 85), add after the insight queries cache clear block (line 113):

```python
    # Backtest queries (1 cached function)
    get_backtest_equity_curve.clear_cache()  # type: ignore
```

In the `__all__` list (around line 116), add before the closing bracket:

```python
    # Backtest queries
    "get_backtest_equity_curve",
```

### Step 5: Build four new chart builder functions

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/charts.py`

Add the following four functions at the end of the file (after the existing `_add_annotation_legend` function ending at line 455). All four follow the same pattern as existing chart builders: accept a DataFrame, return a `go.Figure`, and use `apply_chart_layout()` for consistent styling.

Add the new import at the top of the file (after line 5):

```python
# Existing imports on lines 1-15 stay unchanged. Add this after line 15:
from constants import (
    COLORS,
    SENTIMENT_COLORS,
    MARKER_CONFIG,
    TIMEFRAME_COLORS,
    CHART_LAYOUT,
    CHART_COLORS,
    ANALYTICS_COLORS,  # NEW
)
```

This replaces the existing import on lines 8-15. The only change is adding `ANALYTICS_COLORS` to the import list.

Now add the four chart functions after line 455:

```python
# ──────────────────────────────────────────────────────────────────────
# Analytics chart builders (Phase 05)
# ──────────────────────────────────────────────────────────────────────


def build_cumulative_pnl_chart(
    df: pd.DataFrame,
    chart_height: int = 350,
) -> go.Figure:
    """Build a cumulative P&L equity curve line chart.

    Shows running total P&L over time with a horizontal $0 reference line.
    Green fill above zero, red below.

    Args:
        df: DataFrame from get_cumulative_pnl() with columns:
            prediction_date, daily_pnl, predictions_count, cumulative_pnl.
        chart_height: Height in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    if df.empty:
        return build_empty_signal_chart("No P&L data available")

    fig = go.Figure()

    # --- $0 reference line ---
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color=ANALYTICS_COLORS["zero_line"],
        line_width=1,
    )

    # --- Main equity curve ---
    fig.add_trace(
        go.Scatter(
            x=df["prediction_date"],
            y=df["cumulative_pnl"],
            mode="lines",
            line=dict(
                color=ANALYTICS_COLORS["equity_line"],
                width=2,
            ),
            fill="tozeroy",
            fillcolor=ANALYTICS_COLORS["equity_fill"],
            name="Cumulative P&L",
            showlegend=False,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Cumulative P&L: <b>$%{y:+,.0f}</b>"
                "<extra></extra>"
            ),
        )
    )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="x unified",
        margin={"l": 55, "r": 20, "t": 10, "b": 40},
        yaxis={"title": "Cumulative P&L ($)", "tickprefix": "$"},
    )

    return fig


def build_rolling_accuracy_chart(
    df: pd.DataFrame,
    chart_height: int = 350,
) -> go.Figure:
    """Build a rolling accuracy percentage line chart.

    Shows rolling-window accuracy over time so the user can see if
    the system is improving or degrading.

    Args:
        df: DataFrame from get_rolling_accuracy() with columns:
            prediction_date, correct, total, rolling_accuracy.
        chart_height: Height in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    if df.empty or "rolling_accuracy" not in df.columns:
        return build_empty_signal_chart("Not enough data for rolling accuracy")

    fig = go.Figure()

    # --- 50% reference line (coin flip baseline) ---
    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color=ANALYTICS_COLORS["zero_line"],
        line_width=1,
        annotation_text="50% (coin flip)",
        annotation_position="bottom right",
        annotation_font_color=COLORS["text_muted"],
        annotation_font_size=10,
    )

    # --- Rolling accuracy line ---
    fig.add_trace(
        go.Scatter(
            x=df["prediction_date"],
            y=df["rolling_accuracy"],
            mode="lines",
            line=dict(
                color=ANALYTICS_COLORS["rolling_line"],
                width=2,
            ),
            fill="tozeroy",
            fillcolor=ANALYTICS_COLORS["rolling_fill"],
            name="Rolling Accuracy",
            showlegend=False,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Rolling Accuracy: <b>%{y:.1f}%</b>"
                "<extra></extra>"
            ),
        )
    )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="x unified",
        margin={"l": 50, "r": 20, "t": 10, "b": 40},
        yaxis={"title": "Accuracy (%)", "range": [0, 105], "ticksuffix": "%"},
    )

    return fig


def build_confidence_calibration_chart(
    df: pd.DataFrame,
    chart_height: int = 350,
) -> go.Figure:
    """Build a confidence calibration grouped bar chart.

    Compares predicted confidence levels vs actual accuracy per bucket.
    A well-calibrated model has bars at roughly equal heights.
    Includes a diagonal "perfect calibration" reference line.

    Args:
        df: DataFrame from get_confidence_calibration() with columns:
            bucket_start, total, correct, avg_confidence,
            actual_accuracy, predicted_confidence, bucket_label.
        chart_height: Height in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    if df.empty:
        return build_empty_signal_chart("No calibration data available")

    fig = go.Figure()

    # --- Predicted confidence bars ---
    fig.add_trace(
        go.Bar(
            x=df["bucket_label"],
            y=df["predicted_confidence"],
            name="Predicted Confidence",
            marker_color=ANALYTICS_COLORS["calibration_predicted"],
            opacity=0.7,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Predicted: <b>%{y:.1f}%</b>"
                "<extra></extra>"
            ),
        )
    )

    # --- Actual accuracy bars ---
    fig.add_trace(
        go.Bar(
            x=df["bucket_label"],
            y=df["actual_accuracy"],
            name="Actual Accuracy",
            marker_color=ANALYTICS_COLORS["calibration_actual"],
            opacity=0.7,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Actual: <b>%{y:.1f}%</b><br>"
                "Predictions: <b>%{customdata}</b>"
                "<extra></extra>"
            ),
            customdata=df["total"],
        )
    )

    # --- Perfect calibration reference line ---
    # Draw a diagonal from bottom-left to top-right using bucket midpoints
    if len(df) >= 2:
        fig.add_trace(
            go.Scatter(
                x=df["bucket_label"],
                y=df["predicted_confidence"],
                mode="lines",
                line=dict(
                    color=ANALYTICS_COLORS["calibration_perfect"],
                    width=1.5,
                    dash="dot",
                ),
                name="Perfect Calibration",
                showlegend=True,
                hoverinfo="skip",
            )
        )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=True,
        barmode="group",
        margin={"l": 50, "r": 20, "t": 10, "b": 40},
        yaxis={"title": "Percentage (%)", "range": [0, 105], "ticksuffix": "%"},
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )

    return fig


def build_backtest_equity_chart(
    df: pd.DataFrame,
    initial_capital: float = 10000,
    chart_height: int = 350,
) -> go.Figure:
    """Build a backtest simulation equity curve chart.

    Shows the hypothetical equity growth over time if following the
    system's high-confidence recommendations.

    Args:
        df: DataFrame from get_backtest_equity_curve() with columns:
            prediction_date, daily_pnl, trade_count, cumulative_pnl, equity.
        initial_capital: Starting capital for the horizontal reference line.
        chart_height: Height in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    if df.empty:
        return build_empty_signal_chart("No backtest data for these settings")

    fig = go.Figure()

    # --- Starting capital reference line ---
    fig.add_hline(
        y=initial_capital,
        line_dash="dash",
        line_color=ANALYTICS_COLORS["backtest_start"],
        line_width=1,
        annotation_text=f"Start: ${initial_capital:,.0f}",
        annotation_position="top left",
        annotation_font_color=ANALYTICS_COLORS["backtest_start"],
        annotation_font_size=10,
    )

    # --- Equity curve ---
    fig.add_trace(
        go.Scatter(
            x=df["prediction_date"],
            y=df["equity"],
            mode="lines",
            line=dict(
                color=ANALYTICS_COLORS["backtest_line"],
                width=2,
            ),
            fill="tozeroy",
            fillcolor=ANALYTICS_COLORS["backtest_fill"],
            name="Portfolio Value",
            showlegend=False,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Portfolio: <b>$%{y:,.0f}</b>"
                "<extra></extra>"
            ),
        )
    )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="x unified",
        margin={"l": 60, "r": 20, "t": 10, "b": 40},
        yaxis={"title": "Portfolio Value ($)", "tickprefix": "$"},
    )

    return fig
```

### Step 6: Add the Analytics section to the dashboard layout

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

Add new imports at the top of the file. The existing imports are on lines 1-9. Replace the import block with:

```python
"""Dashboard page layout and callbacks."""

from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS, HIERARCHY, CHART_CONFIG
from components.controls import create_filter_controls
from components.header import create_header, create_footer
from brand_copy import COPY
```

The only change is adding `CHART_CONFIG` to the constants import (line 6).

Now insert the Analytics section into the `create_dashboard_page()` function. The insertion point is between the Asset Screener Card (ending at line 140 with `),`) and the Latest Posts Card (starting at line 141 with `# ========== Latest Posts`).

Insert the following block between line 140 and line 141 (after the screener card's closing `,` and before the `# ========== Latest Posts` comment):

```python
                    # ========== Analytics Charts (Secondary tier, collapsible) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    dbc.Button(
                                        [
                                            html.I(
                                                className="fas fa-chevron-right me-2 collapse-chevron",
                                                id="collapse-analytics-chevron",
                                            ),
                                            html.I(className="fas fa-chart-area me-2"),
                                            COPY["analytics_header"],
                                            html.Small(
                                                f" - {COPY['analytics_section_subtitle']}",
                                                style={
                                                    "color": COLORS["text_muted"],
                                                    "fontWeight": "normal",
                                                },
                                            ),
                                        ],
                                        id="collapse-analytics-button",
                                        color="link",
                                        className="text-white fw-bold p-0 collapse-toggle-btn",
                                    ),
                                ],
                                className="fw-bold",
                                style={
                                    "backgroundColor": HIERARCHY["secondary"][
                                        "background"
                                    ]
                                },
                            ),
                            dbc.Collapse(
                                dbc.CardBody(
                                    [
                                        # Tab navigation for chart types
                                        dbc.Tabs(
                                            [
                                                dbc.Tab(
                                                    label=COPY["analytics_pnl_tab"],
                                                    tab_id="tab-pnl",
                                                ),
                                                dbc.Tab(
                                                    label=COPY["analytics_rolling_tab"],
                                                    tab_id="tab-rolling",
                                                ),
                                                dbc.Tab(
                                                    label=COPY["analytics_calibration_tab"],
                                                    tab_id="tab-calibration",
                                                ),
                                                dbc.Tab(
                                                    label=COPY["analytics_backtest_tab"],
                                                    tab_id="tab-backtest",
                                                ),
                                            ],
                                            id="analytics-tabs",
                                            active_tab="tab-pnl",
                                            className="mb-3",
                                        ),
                                        # Backtest controls (visible only on backtest tab)
                                        html.Div(
                                            [
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    COPY["analytics_backtest_capital_label"],
                                                                    style={
                                                                        "color": COLORS["text_muted"],
                                                                        "fontSize": "0.8rem",
                                                                        "marginBottom": "4px",
                                                                    },
                                                                ),
                                                                dbc.Input(
                                                                    id="backtest-capital-input",
                                                                    type="number",
                                                                    value=10000,
                                                                    min=1000,
                                                                    max=1000000,
                                                                    step=1000,
                                                                    style={
                                                                        "backgroundColor": COLORS["bg"],
                                                                        "color": COLORS["text"],
                                                                        "border": f"1px solid {COLORS['border']}",
                                                                    },
                                                                ),
                                                            ],
                                                            md=4,
                                                            xs=6,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    COPY["analytics_backtest_confidence_label"],
                                                                    style={
                                                                        "color": COLORS["text_muted"],
                                                                        "fontSize": "0.8rem",
                                                                        "marginBottom": "4px",
                                                                    },
                                                                ),
                                                                dcc.Slider(
                                                                    id="backtest-confidence-slider",
                                                                    min=0.5,
                                                                    max=0.95,
                                                                    step=0.05,
                                                                    value=0.75,
                                                                    marks={
                                                                        0.5: "50%",
                                                                        0.6: "60%",
                                                                        0.7: "70%",
                                                                        0.75: "75%",
                                                                        0.8: "80%",
                                                                        0.9: "90%",
                                                                        0.95: "95%",
                                                                    },
                                                                    tooltip={
                                                                        "placement": "bottom",
                                                                        "always_visible": False,
                                                                    },
                                                                ),
                                                            ],
                                                            md=6,
                                                            xs=12,
                                                        ),
                                                    ],
                                                    className="g-3 align-items-end",
                                                ),
                                            ],
                                            id="backtest-controls-container",
                                            style={"display": "none", "marginBottom": "16px"},
                                        ),
                                        # Chart container
                                        dcc.Loading(
                                            type="circle",
                                            color=COLORS["accent"],
                                            children=dcc.Graph(
                                                id="analytics-chart",
                                                config=CHART_CONFIG,
                                            ),
                                        ),
                                        # Backtest summary stats (below chart, only on backtest tab)
                                        html.Div(
                                            id="backtest-summary-container",
                                            style={"display": "none"},
                                        ),
                                    ],
                                    style={
                                        "backgroundColor": HIERARCHY["secondary"][
                                            "background"
                                        ],
                                        "padding": "12px",
                                    },
                                ),
                                id="collapse-analytics",
                                is_open=False,
                            ),
                        ],
                        className="mb-4",
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                        },
                    ),
```

Update the `register_dashboard_callbacks` function (line 237-251) to include the new analytics callback module:

```python
def register_dashboard_callbacks(app: Dash):
    """Register all dashboard-specific callbacks.

    Delegates to focused sub-modules. This function is the single
    entry point called by layout.register_callbacks().
    """
    from pages.dashboard_callbacks import (
        register_period_callbacks,
        register_content_callbacks,
        register_table_callbacks,
        register_analytics_callbacks,  # NEW
    )

    register_period_callbacks(app)
    register_content_callbacks(app)
    register_table_callbacks(app)
    register_analytics_callbacks(app)  # NEW
```

### Step 7: Update the dashboard callbacks `__init__.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/__init__.py`

Replace the entire file with:

```python
"""Dashboard callback sub-modules.

Each module registers a focused group of callbacks:
- period: Time period selection and countdown
- content: Main dashboard content (KPIs, screener, insights, post feed)
- table: Data table management (collapse, filtering, row clicks, thesis expand)
- analytics: Analytics charts (P&L, accuracy, calibration, backtest)
"""

from pages.dashboard_callbacks.period import register_period_callbacks
from pages.dashboard_callbacks.content import register_content_callbacks
from pages.dashboard_callbacks.table import register_table_callbacks
from pages.dashboard_callbacks.analytics import register_analytics_callbacks

__all__ = [
    "register_period_callbacks",
    "register_content_callbacks",
    "register_table_callbacks",
    "register_analytics_callbacks",
]
```

### Step 8: Create the analytics callbacks module

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/analytics.py` (NEW FILE)

```python
"""Analytics chart callbacks.

Handles the analytics section: tab switching, chart rendering,
backtest controls visibility, and backtest summary display.
"""

import traceback

from dash import Dash, html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc

from constants import COLORS
from brand_copy import COPY
from components.charts import (
    build_cumulative_pnl_chart,
    build_rolling_accuracy_chart,
    build_confidence_calibration_chart,
    build_backtest_equity_chart,
    build_empty_signal_chart,
)
from data import (
    get_cumulative_pnl,
    get_rolling_accuracy,
    get_confidence_calibration,
    get_backtest_simulation,
    get_backtest_equity_curve,
)


def register_analytics_callbacks(app: Dash) -> None:
    """Register analytics chart callbacks.

    Args:
        app: The Dash application instance.
    """

    # ========== Collapse toggle ==========
    @app.callback(
        Output("collapse-analytics", "is_open"),
        [Input("collapse-analytics-button", "n_clicks")],
        [State("collapse-analytics", "is_open")],
    )
    def toggle_analytics_collapse(n_clicks, is_open):
        """Toggle the analytics section collapse."""
        if n_clicks:
            return not is_open
        return is_open

    # Chevron rotation (clientside)
    app.clientside_callback(
        """
        function(isOpen) {
            if (isOpen) {
                return 'fas fa-chevron-right me-2 collapse-chevron rotated';
            }
            return 'fas fa-chevron-right me-2 collapse-chevron';
        }
        """,
        Output("collapse-analytics-chevron", "className"),
        [Input("collapse-analytics", "is_open")],
    )

    # ========== Show/hide backtest controls based on active tab ==========
    @app.callback(
        [
            Output("backtest-controls-container", "style"),
            Output("backtest-summary-container", "style"),
        ],
        [Input("analytics-tabs", "active_tab")],
    )
    def toggle_backtest_controls(active_tab):
        """Show backtest controls only when backtest tab is active."""
        if active_tab == "tab-backtest":
            return (
                {"display": "block", "marginBottom": "16px"},
                {"display": "block"},
            )
        return (
            {"display": "none"},
            {"display": "none"},
        )

    # ========== Main chart rendering callback ==========
    @app.callback(
        [
            Output("analytics-chart", "figure"),
            Output("backtest-summary-container", "children"),
        ],
        [
            Input("analytics-tabs", "active_tab"),
            Input("selected-period", "data"),
            Input("collapse-analytics", "is_open"),
            Input("backtest-capital-input", "value"),
            Input("backtest-confidence-slider", "value"),
        ],
    )
    def update_analytics_chart(
        active_tab, period, is_open, backtest_capital, backtest_confidence
    ):
        """Render the appropriate analytics chart based on active tab.

        Only fetches data when the analytics section is open to avoid
        unnecessary database queries.
        """
        # Don't fetch data if section is collapsed
        if not is_open:
            return build_empty_signal_chart("Expand to view analytics"), html.Div()

        # Convert period to days
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period, 90)

        backtest_summary = html.Div()  # Default empty

        try:
            if active_tab == "tab-pnl":
                df = get_cumulative_pnl(days=days)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_pnl"])
                else:
                    fig = build_cumulative_pnl_chart(df)

            elif active_tab == "tab-rolling":
                df = get_rolling_accuracy(window=30, days=days)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_rolling"])
                else:
                    fig = build_rolling_accuracy_chart(df)

            elif active_tab == "tab-calibration":
                df = get_confidence_calibration(buckets=10)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_calibration"])
                else:
                    fig = build_confidence_calibration_chart(df)

            elif active_tab == "tab-backtest":
                capital = float(backtest_capital or 10000)
                confidence = float(backtest_confidence or 0.75)

                df = get_backtest_equity_curve(
                    initial_capital=capital,
                    min_confidence=confidence,
                    days=days,
                )
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_backtest"])
                else:
                    fig = build_backtest_equity_chart(
                        df, initial_capital=capital
                    )

                # Also fetch the summary stats for the info panel
                summary = get_backtest_simulation(
                    initial_capital=capital,
                    min_confidence=confidence,
                    days=days if days is not None else 90,
                )
                backtest_summary = _build_backtest_summary(summary)

            else:
                fig = build_empty_signal_chart("Select a tab")

        except Exception as e:
            print(f"Error loading analytics chart: {traceback.format_exc()}")
            fig = build_empty_signal_chart(f"Error loading chart: {str(e)[:60]}")

        return fig, backtest_summary


def _build_backtest_summary(summary: dict) -> html.Div:
    """Build the backtest summary stats panel below the chart.

    Args:
        summary: Dict from get_backtest_simulation() with keys:
            initial_capital, final_value, total_return_pct,
            trade_count, wins, losses, win_rate.

    Returns:
        html.Div with a row of summary stats.
    """
    if summary["trade_count"] == 0:
        return html.Div()

    pnl = summary["final_value"] - summary["initial_capital"]
    pnl_color = COLORS["success"] if pnl >= 0 else COLORS["danger"]

    return dbc.Row(
        [
            _backtest_stat(
                f"${summary['final_value']:,.0f}",
                "Final Value",
                pnl_color,
            ),
            _backtest_stat(
                f"{summary['total_return_pct']:+.1f}%",
                "Total Return",
                pnl_color,
            ),
            _backtest_stat(
                f"{summary['trade_count']}",
                "Total Trades",
                COLORS["accent"],
            ),
            _backtest_stat(
                f"{summary['win_rate']:.1f}%",
                f"Win Rate ({summary['wins']}W / {summary['losses']}L)",
                COLORS["success"] if summary["win_rate"] > 50 else COLORS["danger"],
            ),
        ],
        className="g-2 mt-2",
    )


def _backtest_stat(value: str, label: str, color: str) -> dbc.Col:
    """Build a single backtest summary stat card.

    Args:
        value: Prominent display value.
        label: Description below the value.
        color: CSS color for the value.

    Returns:
        dbc.Col containing the stat card.
    """
    return dbc.Col(
        html.Div(
            [
                html.Div(
                    value,
                    style={
                        "fontSize": "1rem",
                        "fontWeight": "bold",
                        "color": color,
                    },
                ),
                html.Div(
                    label,
                    style={
                        "fontSize": "0.7rem",
                        "color": COLORS["text_muted"],
                    },
                ),
            ],
            style={
                "textAlign": "center",
                "padding": "8px",
                "backgroundColor": COLORS["bg"],
                "borderRadius": "8px",
                "border": f"1px solid {COLORS['border']}",
            },
        ),
        xs=6,
        md=3,
    )
```

### Step 9: Add `reference_line` to `CHART_COLORS` (already exists)

Looking at `/Users/chris/Projects/shitpost-alpha/shitty_ui/constants.py` line 199, `CHART_COLORS["reference_line"]` already exists as `"rgba(139, 154, 126, 0.3)"`. No change needed here -- the `ANALYTICS_COLORS` dict defined in Step 2 is a cleaner separation.

---

## Test Plan

### New test file

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_analytics_charts.py` (NEW FILE)

```python
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
    return pd.DataFrame({
        "prediction_date": pd.to_datetime([
            "2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05",
        ]),
        "daily_pnl": [50.0, -20.0, 80.0, -10.0, 30.0],
        "predictions_count": [2, 1, 3, 1, 2],
        "cumulative_pnl": [50.0, 30.0, 110.0, 100.0, 130.0],
    })


def _make_rolling_accuracy_df():
    """Sample rolling accuracy data."""
    return pd.DataFrame({
        "prediction_date": pd.to_datetime([
            "2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04",
        ]),
        "correct": [1, 2, 1, 3],
        "total": [2, 3, 2, 4],
        "rolling_accuracy": [50.0, 57.1, 55.0, 63.6],
    })


def _make_calibration_df():
    """Sample confidence calibration data."""
    return pd.DataFrame({
        "bucket_start": [0.5, 0.6, 0.7, 0.8],
        "total": [10, 15, 20, 8],
        "correct": [4, 9, 15, 7],
        "avg_confidence": [0.55, 0.67, 0.74, 0.85],
        "actual_accuracy": [40.0, 60.0, 75.0, 87.5],
        "predicted_confidence": [55.0, 67.0, 74.0, 85.0],
        "bucket_label": ["50-60%", "60-70%", "70-80%", "80-90%"],
    })


def _make_backtest_df(initial_capital=10000):
    """Sample backtest equity curve data."""
    return pd.DataFrame({
        "prediction_date": pd.to_datetime([
            "2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04",
        ]),
        "daily_pnl": [100.0, -50.0, 200.0, 75.0],
        "trade_count": [1, 1, 2, 1],
        "cumulative_pnl": [100.0, 50.0, 250.0, 325.0],
        "equity": [10100.0, 10050.0, 10250.0, 10325.0],
    })


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
        assert fig.layout.yaxis.range == [0, 105]

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
        line_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.line.dash == "dot"]
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
        fig = build_backtest_equity_chart(_make_backtest_df(25000), initial_capital=25000)
        shapes = fig.layout.shapes
        assert any(s.y0 == 25000 for s in shapes)

    def test_yaxis_has_dollar_prefix(self):
        fig = build_backtest_equity_chart(_make_backtest_df())
        assert fig.layout.yaxis.tickprefix == "$"
```

### Existing tests to verify (no modifications needed)

- Run `shit_tests/shitty_ui/test_charts.py` -- all existing chart tests must still pass unchanged.
- Run `shit_tests/shitty_ui/test_data.py` -- existing data query tests must pass.
- Run `shit_tests/shitty_ui/test_data_init.py` -- verify `get_backtest_equity_curve` appears in exports.

### Manual verification steps

1. Start the dashboard: `cd shitty_ui && python app.py`
2. On the main page, verify the "Show Me The Money" analytics section appears between the Asset Screener and Latest Shitposts.
3. Click to expand the analytics section.
4. Verify the "Equity Curve" tab shows a P&L line chart with $0 reference line.
5. Switch to "Rolling Accuracy" tab -- verify 50% baseline and accuracy line.
6. Switch to "Calibration" tab -- verify grouped bars with legend.
7. Switch to "Backtest Simulator" tab -- verify controls appear, chart updates when slider/input changes.
8. Change the Time Period selector (7D/30D/90D/All) -- verify charts update.
9. Collapse and re-expand the section -- verify no errors.
10. Test on mobile viewport (375px) -- verify controls stack vertically.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Analytics Charts Section** - New collapsible "Show Me The Money" section on the dashboard
  - Cumulative P&L equity curve chart showing running total P&L over time
  - Rolling accuracy chart showing 30-day rolling prediction accuracy trend
  - Confidence calibration chart comparing predicted confidence vs actual accuracy
  - Interactive backtest simulator with configurable starting capital and confidence threshold
  - All charts respect the global Time Period selector
  - Backtest tab shows summary stats (final value, return %, trades, win rate)
```

### brand_copy.py

Already detailed in Step 1. The new copy entries follow the same pattern as existing entries.

---

## Stress Testing & Edge Cases

### Empty data handling

Every chart builder must handle empty DataFrames gracefully. The pattern is consistent: check `df.empty` at the top of each function and return `build_empty_signal_chart(message)` if true. The callback also checks emptiness before calling the chart builder, providing the branded empty message from `COPY`.

### Time period edge cases

- **7D period**: Likely has very few or zero data points. The charts should degrade to an empty state with a helpful message.
- **All time**: May have a large number of data points. The charts use Plotly's built-in rendering which handles thousands of points efficiently.
- **Rolling accuracy with insufficient data**: The `min_periods=1` parameter in `get_rolling_accuracy()` means even a single data point produces a result.

### Backtest slider extremes

- **min_confidence = 0.95**: Likely filters out most trades. Empty equity curve should show gracefully.
- **initial_capital = 1000000**: Large numbers should format correctly with `$` prefix and comma separators in hover tooltips.
- **initial_capital = 1000**: Minimum allowed. Reference line should still render.

### Calibration with few buckets

If only 1-2 confidence buckets have data, the grouped bar chart still renders. The "perfect calibration" reference line requires >= 2 buckets (`if len(df) >= 2` guard in the chart builder).

### Collapse performance

The analytics callback checks `is_open` before fetching data. When the section is collapsed, no database queries execute. This prevents unnecessary load on every 5-minute refresh.

### Concurrent updates

The `selected-period` store triggers both the main dashboard callback and the analytics callback. Both are independent Dash callbacks that run in parallel. Since they read different data, there are no race conditions.

---

## Verification Checklist

1. `source venv/bin/activate && pytest shit_tests/shitty_ui/test_analytics_charts.py -v` -- all new tests pass
2. `source venv/bin/activate && pytest shit_tests/shitty_ui/test_charts.py -v` -- existing chart tests still pass
3. `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all UI tests pass
4. `source venv/bin/activate && python3 -m ruff check shitty_ui/` -- no lint errors
5. `source venv/bin/activate && python3 -m ruff format --check shitty_ui/` -- formatting clean
6. Manual: Dashboard loads without JS console errors
7. Manual: Analytics section collapses/expands smoothly
8. Manual: All four chart tabs render correctly
9. Manual: Backtest controls update chart reactively
10. Manual: Time period selector updates analytics charts

---

## What NOT To Do

1. **Do NOT create a separate `/analytics` route/page.** The 2-view IA (Home + Asset Detail) was an intentional consolidation from a previous session. Adding a third page would undo that work. The collapsible section pattern (matching the existing data table) fits the current IA.

2. **Do NOT modify `get_backtest_simulation()` to return a DataFrame.** It is used elsewhere as a summary dict and has an `@ttl_cache` decorator with a specific return type. Instead, create the new `get_backtest_equity_curve()` query that returns the time-series data.

3. **Do NOT add the analytics callback outputs to the existing `update_dashboard` callback in `content.py`.** That callback already returns 4 outputs and mixing chart figures with HTML components creates coupling. The analytics section has its own separate callback that fires only when the section is open.

4. **Do NOT put the dcc.Graph components inside the main dashboard's `dcc.Loading` wrapper.** Each chart has its own `dcc.Loading` wrapper to show individual loading states.

5. **Do NOT use `prevent_initial_call=True` on the main analytics chart callback.** The chart needs to render when the section is first opened. The `is_open` guard handles the initial collapsed state instead.

6. **Do NOT import from `shitty_ui.data` using the full module path.** Inside `shitty_ui/`, imports are relative to the `shitty_ui` directory (which is the working directory when the Dash app runs). Use `from data import ...` not `from shitty_ui.data import ...`.

7. **Do NOT add new IDs that conflict with existing ones.** The existing dashboard has IDs like `collapse-table`, `collapse-table-button`, `collapse-table-chevron`. The new analytics IDs use the prefix `collapse-analytics-*` and `analytics-*` to avoid conflicts.

8. **Do NOT forget to add the `ANALYTICS_COLORS` import to `charts.py`.** The chart builders reference these colors. Missing the import will cause a `NameError` at runtime.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/charts.py` - Add 4 new chart builder functions
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` - Insert analytics section layout and register new callback module
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/analytics.py` - New file: all analytics callbacks (collapse, tab switching, chart rendering, backtest controls)
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/backtest_queries.py` - New file: time-series backtest equity curve query
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_analytics_charts.py` - New file: comprehensive tests for all 4 chart builders

---

- Wrote: /Users/chris/Projects/shitpost-alpha/documentation/planning/phases/alpha-quality_2026-03-04/05_analytics-charts.md
- PR title: feat: add analytics charts section with equity curve, rolling accuracy, calibration, and backtest
- Effort: Medium (3-4 days)
- Risk: Medium
- Files modified: 7 | Files created: 3
- Dependencies: None
- Unlocks: None