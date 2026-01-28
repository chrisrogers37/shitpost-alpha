# Performance Page - Engineering Specification

## Overview

This document is a complete engineering specification for adding a dedicated `/performance` page to the Shitpost Alpha dashboard. The performance page provides deep analytical views into how the system's predictions have performed over time, including equity curves, drawdown analysis, streak tracking, rolling accuracy, confidence calibration, sentiment breakdowns, and periodic summary tables.

**Estimated Effort**: 3-4 days
**Priority**: P1 (Should Have)
**Prerequisites**: Core dashboard working (Phase 0.2 complete)

---

## Table of Contents

1. [Architecture Changes](#1-architecture-changes)
2. [Multi-Page Setup](#2-multi-page-setup)
3. [Data Layer - New Queries](#3-data-layer---new-queries)
4. [Layout - Performance Page Components](#4-layout---performance-page-components)
5. [Callbacks](#5-callbacks)
6. [Test Specifications](#6-test-specifications)
7. [Implementation Checklist](#7-implementation-checklist)
8. [Definition of Done](#8-definition-of-done)

---

## 1. Architecture Changes

### Current Structure

```
shitty_ui/
├── app.py          # Entry point
├── layout.py       # Single-page layout + callbacks
├── data.py         # Database queries
└── README.md
```

### New Structure

```
shitty_ui/
├── app.py              # Entry point (MODIFIED - multi-page setup)
├── data.py             # Database queries (MODIFIED - new query functions)
├── layout.py           # Existing home page layout + callbacks (MODIFIED - navigation)
├── pages/              # NEW directory
│   ├── __init__.py     # Empty init file
│   ├── home.py         # NEW - Home page (extracted from layout.py)
│   └── performance.py  # NEW - Performance page layout + callbacks
├── components/         # NEW directory (shared components)
│   ├── __init__.py     # Empty init file
│   ├── nav.py          # NEW - Navigation bar shared across pages
│   └── common.py       # NEW - Shared component functions (metric cards, etc.)
└── README.md
```

### Why This Structure?

- **Separation of concerns**: Each page is its own module with its own layout and callbacks
- **Shared components**: Navigation and reusable components live in `components/`
- **Dash Pages pattern**: Uses Dash's built-in multi-page support via `dash.page_container`
- **Minimal disruption**: Existing `data.py` stays in place; we add functions to it

---

## 2. Multi-Page Setup

### Step 1: Update `app.py`

The entry point needs to switch from a single-page layout to Dash's multi-page architecture using `pages_folder`.

**File**: `shitty_ui/app.py`

```python
"""
Main entry point for Shitty UI Dashboard.
Multi-page Dash application for Shitpost Alpha.
"""

import os
import sys
import dash
from dash import html, dcc, page_container
import dash_bootstrap_components as dbc

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import shared navigation
from components.nav import create_navbar

# Color palette - must match layout.py
COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}


def create_app() -> dash.Dash:
    """Create and configure the multi-page Dash app."""

    app = dash.Dash(
        __name__,
        use_pages=True,
        pages_folder="pages",
        external_stylesheets=[
            dbc.themes.DARKLY,
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Prediction Performance Dashboard"

    # Root layout wraps all pages
    app.layout = html.Div([
        # Auto-refresh interval (shared across pages)
        dcc.Interval(
            id="refresh-interval",
            interval=5 * 60 * 1000,  # 5 minutes
            n_intervals=0,
        ),

        # Navigation bar
        create_navbar(),

        # Page content - Dash renders the active page here
        page_container,

        # Footer
        html.Div([
            html.Hr(style={"borderColor": COLORS["border"], "margin": "40px 0 20px 0"}),
            html.P(
                "Disclaimer: This is NOT financial advice. For entertainment and research purposes only.",
                style={
                    "textAlign": "center",
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "fontStyle": "italic",
                },
            ),
        ], style={"padding": "0 20px", "maxWidth": "1400px", "margin": "0 auto"}),

    ], style={
        "backgroundColor": COLORS["primary"],
        "minHeight": "100vh",
        "color": COLORS["text"],
        "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    })

    return app


def serve_app():
    """Serve the Dash application."""
    app = create_app()

    # Get port from environment (Railway provides this)
    port = int(os.environ.get("PORT", 8050))

    print(f"Starting Shitpost Alpha Dashboard on port {port}...")
    print("Multi-page mode: / (home), /performance")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )


if __name__ == "__main__":
    serve_app()
```

### Step 2: Create Navigation Component

**File**: `shitty_ui/components/__init__.py`

```python
# Empty init file for components package
```

**File**: `shitty_ui/components/nav.py`

```python
"""
Shared navigation bar for the multi-page dashboard.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}


def create_navbar() -> dbc.Navbar:
    """Create the shared navigation bar."""
    return dbc.Navbar(
        dbc.Container([
            # Brand / logo
            dbc.NavbarBrand(
                html.Span([
                    html.Span("Shitpost Alpha", style={"color": COLORS["accent"], "fontWeight": "bold"}),
                ]),
                href="/",
                className="me-auto",
            ),

            # Navigation links
            dbc.Nav([
                dbc.NavItem(dbc.NavLink(
                    [html.I(className="fas fa-home me-1"), "Dashboard"],
                    href="/",
                    active="exact",
                    style={"color": COLORS["text"]},
                )),
                dbc.NavItem(dbc.NavLink(
                    [html.I(className="fas fa-chart-line me-1"), "Performance"],
                    href="/performance",
                    active="exact",
                    style={"color": COLORS["text"]},
                )),
            ], navbar=True),

            # Auto-refresh indicator
            html.Div([
                html.Span(
                    "Auto-refresh: 5 min",
                    style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                ),
            ]),
        ], fluid=True),
        color=COLORS["secondary"],
        dark=True,
        style={"borderBottom": f"1px solid {COLORS['border']}"},
    )
```

### Step 3: Create Shared Components

**File**: `shitty_ui/components/common.py`

```python
"""
Shared UI components used across multiple pages.
Extracted from layout.py for reuse.
"""

from dash import html
import dash_bootstrap_components as dbc

COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}


def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
) -> dbc.Card:
    """Create a metric card component.

    Args:
        title: Label below the value (e.g., "Prediction Accuracy").
        value: The main displayed value (e.g., "65.2%").
        subtitle: Optional smaller text below the title.
        icon: Font Awesome icon name without 'fa-' prefix.
        color: Hex color for the icon and value. Defaults to accent blue.

    Returns:
        A dbc.Card component.
    """
    color = color or COLORS["accent"]
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(
                    className=f"fas fa-{icon}",
                    style={"fontSize": "1.5rem", "color": color},
                ),
            ], className="mb-2"),
            html.H3(
                value,
                style={"margin": 0, "color": color, "fontWeight": "bold"},
            ),
            html.P(
                title,
                style={"margin": 0, "color": COLORS["text_muted"], "fontSize": "0.85rem"},
            ),
            html.Small(subtitle, style={"color": COLORS["text_muted"]}) if subtitle else None,
        ], style={"textAlign": "center", "padding": "15px"}),
    ], style={
        "backgroundColor": COLORS["secondary"],
        "border": f"1px solid {COLORS['border']}",
    })


def create_empty_chart_figure(message: str = "No data available") -> dict:
    """Create a placeholder figure with a centered message.

    Use this when a chart has no data to display.

    Args:
        message: Text to display in the empty chart area.

    Returns:
        A Plotly figure dict (compatible with go.Figure).
    """
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=300,
    )
    return fig


def create_section_card(
    title: str,
    icon: str,
    children,
    card_id: str = None,
) -> dbc.Card:
    """Create a card with a header, used to wrap chart sections.

    Args:
        title: Card header text.
        icon: Font Awesome icon name.
        children: Content to place inside the card body.
        card_id: Optional HTML id for the card.

    Returns:
        A dbc.Card component.
    """
    card_props = {
        "className": "mb-3",
        "style": {"backgroundColor": COLORS["secondary"]},
    }
    if card_id:
        card_props["id"] = card_id

    return dbc.Card([
        dbc.CardHeader([
            html.I(className=f"fas fa-{icon} me-2"),
            title,
        ], className="fw-bold"),
        dbc.CardBody(children),
    ], **card_props)
```

### Step 4: Register the Home Page

**File**: `shitty_ui/pages/__init__.py`

```python
# Empty init file for pages package
```

**File**: `shitty_ui/pages/home.py`

This file registers the existing dashboard as the home page. The existing `layout.py` callback logic stays in `layout.py` for now. This page module simply declares the route and renders the existing layout.

```python
"""
Home page - main dashboard.
Registered as the default '/' route in the multi-page app.
"""

import dash
from dash import html

# Register this module as a page
dash.register_page(
    __name__,
    path="/",
    name="Dashboard",
    title="Shitpost Alpha - Dashboard",
)

# Import the existing layout builder
# NOTE: The existing layout.py create_app() builds the full app.
# For multi-page, we only need the *content* portion of the layout.
# The team should extract the main content from create_app() into a
# function called create_home_content() in layout.py and call it here.
#
# For now, we import and call it:
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from layout import create_home_content

layout = create_home_content()
```

> **IMPORTANT**: The team must refactor `layout.py` to expose a `create_home_content()` function that returns only the inner content (everything inside the main container div), without the outer `html.Div` wrapper, header, or footer. These are now in `app.py`. See [Refactoring Notes](#refactoring-layoutpy) at the end of this document.

---

## 3. Data Layer - New Queries

All new query functions go in `shitty_ui/data.py`. They follow the same pattern as the existing functions: use `execute_query()`, return a `pd.DataFrame` or `Dict`, and handle errors gracefully.

### 3.1 Equity Curve Data

This query returns the cumulative P&L over time. Each row represents one prediction outcome with a running total.

```python
def get_equity_curve_data(days: int = None) -> pd.DataFrame:
    """
    Get daily cumulative P&L for the equity curve chart.

    Returns one row per prediction outcome, sorted by date, with a running
    cumulative P&L column. The P&L assumes a $1,000 position per prediction.

    Args:
        days: Number of days to look back. None means all time.

    Returns:
        DataFrame with columns:
            - prediction_date (date)
            - symbol (str)
            - prediction_sentiment (str)
            - pnl_t7 (float) - individual trade P&L
            - cumulative_pnl (float) - running total
            - prediction_confidence (float)
            - correct_t7 (bool)
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            po.prediction_date,
            po.symbol,
            po.prediction_sentiment,
            po.pnl_t7,
            po.prediction_confidence,
            po.correct_t7,
            SUM(po.pnl_t7) OVER (
                ORDER BY po.prediction_date, po.id
            ) AS cumulative_pnl
        FROM prediction_outcomes po
        WHERE po.pnl_t7 IS NOT NULL
            AND po.correct_t7 IS NOT NULL
            {date_filter}
        ORDER BY po.prediction_date, po.id
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading equity curve data: {e}")
        return pd.DataFrame()
```

### 3.2 Drawdown Data

Drawdown is calculated from the equity curve. We compute it in Python for flexibility rather than in SQL.

```python
def get_drawdown_data(days: int = None) -> pd.DataFrame:
    """
    Calculate drawdown series from the equity curve.

    Drawdown at any point = (current cumulative P&L - peak cumulative P&L).
    Max drawdown = the largest negative drawdown value.

    Args:
        days: Number of days to look back. None means all time.

    Returns:
        DataFrame with columns:
            - prediction_date (date)
            - cumulative_pnl (float)
            - peak_pnl (float) - running maximum of cumulative P&L
            - drawdown (float) - current drawdown (negative or zero)
            - drawdown_pct (float) - drawdown as percentage of peak
    """
    equity_df = get_equity_curve_data(days=days)

    if equity_df.empty:
        return pd.DataFrame()

    # Group by date to get daily P&L (multiple predictions per day possible)
    daily_df = (
        equity_df
        .groupby("prediction_date")
        .agg({"cumulative_pnl": "last", "pnl_t7": "sum"})
        .reset_index()
    )

    # Calculate running peak and drawdown
    daily_df["peak_pnl"] = daily_df["cumulative_pnl"].cummax()
    daily_df["drawdown"] = daily_df["cumulative_pnl"] - daily_df["peak_pnl"]
    daily_df["drawdown_pct"] = daily_df.apply(
        lambda row: (row["drawdown"] / row["peak_pnl"] * 100)
        if row["peak_pnl"] > 0 else 0.0,
        axis=1,
    )

    return daily_df
```

### 3.3 Win/Loss Streak Data

```python
def get_streak_data(days: int = None) -> Dict[str, Any]:
    """
    Calculate win/loss streak statistics.

    A 'win' is a prediction where correct_t7 = True.
    A 'loss' is a prediction where correct_t7 = False.
    A streak is a consecutive sequence of wins or losses.

    Args:
        days: Number of days to look back. None means all time.

    Returns:
        Dictionary with:
            - current_streak (int): Positive = winning streak, negative = losing streak
            - current_streak_type (str): 'win' or 'loss'
            - max_win_streak (int)
            - max_loss_streak (int)
            - streaks (list of dict): Each dict has 'type', 'length', 'start_date', 'end_date'
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            po.prediction_date,
            po.correct_t7,
            po.pnl_t7
        FROM prediction_outcomes po
        WHERE po.correct_t7 IS NOT NULL
            {date_filter}
        ORDER BY po.prediction_date, po.id
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
    except Exception as e:
        print(f"Error loading streak data: {e}")
        return {
            "current_streak": 0,
            "current_streak_type": "none",
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "streaks": [],
        }

    if df.empty:
        return {
            "current_streak": 0,
            "current_streak_type": "none",
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "streaks": [],
        }

    # Build streak list
    streaks = []
    current_type = None
    current_length = 0
    current_start = None

    for _, row in df.iterrows():
        is_win = bool(row["correct_t7"])
        streak_type = "win" if is_win else "loss"

        if streak_type == current_type:
            current_length += 1
        else:
            # Save previous streak
            if current_type is not None:
                streaks.append({
                    "type": current_type,
                    "length": current_length,
                    "start_date": str(current_start),
                    "end_date": str(row["prediction_date"]),
                })
            current_type = streak_type
            current_length = 1
            current_start = row["prediction_date"]

    # Save last streak
    if current_type is not None:
        streaks.append({
            "type": current_type,
            "length": current_length,
            "start_date": str(current_start),
            "end_date": str(df.iloc[-1]["prediction_date"]),
        })

    # Calculate maximums
    max_win = max((s["length"] for s in streaks if s["type"] == "win"), default=0)
    max_loss = max((s["length"] for s in streaks if s["type"] == "loss"), default=0)

    # Current streak
    last_streak = streaks[-1] if streaks else {"type": "none", "length": 0}

    return {
        "current_streak": last_streak["length"],
        "current_streak_type": last_streak["type"],
        "max_win_streak": max_win,
        "max_loss_streak": max_loss,
        "streaks": streaks,
    }
```

### 3.4 Rolling Accuracy Data

```python
def get_rolling_accuracy(window: int = 30, days: int = None) -> pd.DataFrame:
    """
    Calculate rolling accuracy over a sliding window.

    For each prediction date, compute the accuracy of the last `window`
    predictions. This shows how accuracy trends over time.

    Args:
        window: Number of predictions in the rolling window (default 30).
        days: Number of days to look back for the raw data. None means all time.

    Returns:
        DataFrame with columns:
            - prediction_date (date)
            - rolling_accuracy (float) - percentage 0-100
            - rolling_correct (int) - correct count in window
            - rolling_total (int) - total count in window
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            po.prediction_date,
            po.correct_t7
        FROM prediction_outcomes po
        WHERE po.correct_t7 IS NOT NULL
            {date_filter}
        ORDER BY po.prediction_date, po.id
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
    except Exception as e:
        print(f"Error loading rolling accuracy data: {e}")
        return pd.DataFrame()

    if df.empty or len(df) < window:
        return pd.DataFrame()

    # Convert correct_t7 to integer for rolling sum
    df["correct_int"] = df["correct_t7"].astype(int)

    # Calculate rolling metrics
    df["rolling_correct"] = df["correct_int"].rolling(window=window, min_periods=window).sum()
    df["rolling_total"] = window  # Fixed window size
    df["rolling_accuracy"] = (df["rolling_correct"] / window * 100).round(1)

    # Drop rows before the window is full
    df = df.dropna(subset=["rolling_accuracy"]).reset_index(drop=True)

    return df[["prediction_date", "rolling_accuracy", "rolling_correct", "rolling_total"]]
```

### 3.5 Confidence Calibration Data

```python
def get_confidence_calibration(bucket_size: float = 0.1) -> pd.DataFrame:
    """
    Get confidence calibration data.

    Groups predictions into confidence buckets (e.g., 0.5-0.6, 0.6-0.7, etc.)
    and computes the actual accuracy for each bucket. A well-calibrated model
    should have actual accuracy close to the predicted confidence.

    Args:
        bucket_size: Width of each confidence bucket (default 0.1 = 10%).

    Returns:
        DataFrame with columns:
            - confidence_bucket (str) - e.g., "50-60%"
            - bucket_midpoint (float) - e.g., 0.55
            - predicted_confidence (float) - average confidence in bucket
            - actual_accuracy (float) - percentage 0-100
            - total (int) - number of predictions in bucket
            - correct (int) - number of correct predictions in bucket
    """
    query = text("""
        SELECT
            po.prediction_confidence,
            po.correct_t7
        FROM prediction_outcomes po
        WHERE po.correct_t7 IS NOT NULL
            AND po.prediction_confidence IS NOT NULL
    """)

    try:
        rows, columns = execute_query(query)
        df = pd.DataFrame(rows, columns=columns)
    except Exception as e:
        print(f"Error loading confidence calibration data: {e}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Create confidence buckets
    import numpy as np
    bins = np.arange(0, 1.0 + bucket_size, bucket_size)
    labels = [
        f"{int(bins[i]*100)}-{int(bins[i+1]*100)}%"
        for i in range(len(bins) - 1)
    ]
    df["confidence_bucket"] = pd.cut(
        df["prediction_confidence"],
        bins=bins,
        labels=labels,
        include_lowest=True,
    )

    # Aggregate per bucket
    result = (
        df.groupby("confidence_bucket", observed=True)
        .agg(
            predicted_confidence=("prediction_confidence", "mean"),
            total=("correct_t7", "count"),
            correct=("correct_t7", "sum"),
        )
        .reset_index()
    )

    result["actual_accuracy"] = (result["correct"] / result["total"] * 100).round(1)
    result["bucket_midpoint"] = result["predicted_confidence"]

    # Only return buckets with enough data (at least 3 predictions)
    result = result[result["total"] >= 3].reset_index(drop=True)

    return result
```

### 3.6 Sentiment Performance Breakdown

```python
def get_sentiment_performance(days: int = None) -> pd.DataFrame:
    """
    Get performance metrics broken down by prediction sentiment.

    Computes accuracy, average return, total P&L, and count for each
    sentiment category (bullish, bearish, neutral).

    Args:
        days: Number of days to look back. None means all time.

    Returns:
        DataFrame with columns:
            - prediction_sentiment (str) - 'bullish', 'bearish', 'neutral'
            - total (int)
            - correct (int)
            - incorrect (int)
            - accuracy (float) - percentage 0-100
            - avg_return (float) - average return_t7
            - total_pnl (float) - sum of pnl_t7
            - avg_confidence (float) - average prediction confidence
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            po.prediction_sentiment,
            COUNT(*) as total,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(po.return_t7)::numeric, 2) as avg_return,
            ROUND(SUM(COALESCE(po.pnl_t7, 0))::numeric, 2) as total_pnl,
            ROUND(AVG(po.prediction_confidence)::numeric, 3) as avg_confidence
        FROM prediction_outcomes po
        WHERE po.correct_t7 IS NOT NULL
            AND po.prediction_sentiment IS NOT NULL
            {date_filter}
        GROUP BY po.prediction_sentiment
        ORDER BY po.prediction_sentiment
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total"] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading sentiment performance: {e}")
        return pd.DataFrame()
```

### 3.7 Monthly/Weekly Performance Summary

```python
def get_periodic_performance(period: str = "month", days: int = None) -> pd.DataFrame:
    """
    Get performance summary grouped by time period (week or month).

    Args:
        period: Either 'week' or 'month'.
        days: Number of days to look back. None means all time.

    Returns:
        DataFrame with columns:
            - period_label (str) - e.g., "2024-01" or "2024-W03"
            - total_predictions (int)
            - correct (int)
            - incorrect (int)
            - accuracy (float) - percentage 0-100
            - total_pnl (float)
            - avg_return (float)
            - avg_confidence (float)
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    if period == "week":
        period_expr = "TO_CHAR(po.prediction_date, 'IYYY-\"W\"IW')"
    else:
        period_expr = "TO_CHAR(po.prediction_date, 'YYYY-MM')"

    query = text(f"""
        SELECT
            {period_expr} as period_label,
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(po.return_t7)::numeric, 2) as avg_return,
            ROUND(SUM(COALESCE(po.pnl_t7, 0))::numeric, 2) as total_pnl,
            ROUND(AVG(po.prediction_confidence)::numeric, 3) as avg_confidence
        FROM prediction_outcomes po
        WHERE po.correct_t7 IS NOT NULL
            {date_filter}
        GROUP BY {period_expr}
        ORDER BY {period_expr} DESC
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading periodic performance: {e}")
        return pd.DataFrame()
```

### 3.8 Summary Statistics for Performance Page Header

```python
def get_performance_summary(days: int = None) -> Dict[str, Any]:
    """
    Get high-level summary stats for the performance page header cards.

    This extends get_performance_metrics() with additional fields needed
    by the performance page: total trades, win rate, profit factor, etc.

    Args:
        days: Number of days to look back. None means all time.

    Returns:
        Dictionary with keys:
            - total_trades (int)
            - win_rate (float) - percentage
            - total_pnl (float) - dollar amount
            - avg_pnl_per_trade (float)
            - profit_factor (float) - gross profit / gross loss
            - best_trade (float) - highest single pnl_t7
            - worst_trade (float) - lowest single pnl_t7
            - avg_confidence (float)
            - max_drawdown (float) - dollar amount (negative)
    """
    date_filter = ""
    params: dict = {}

    if days is not None:
        date_filter = "WHERE po.prediction_date >= :start_date"
        from datetime import datetime, timedelta
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            COUNT(*) as total_trades,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as wins,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) as losses,
            SUM(COALESCE(po.pnl_t7, 0)) as total_pnl,
            AVG(po.pnl_t7) as avg_pnl,
            SUM(CASE WHEN po.pnl_t7 > 0 THEN po.pnl_t7 ELSE 0 END) as gross_profit,
            SUM(CASE WHEN po.pnl_t7 < 0 THEN ABS(po.pnl_t7) ELSE 0 END) as gross_loss,
            MAX(po.pnl_t7) as best_trade,
            MIN(po.pnl_t7) as worst_trade,
            AVG(po.prediction_confidence) as avg_confidence
        FROM prediction_outcomes po
        {date_filter}
    """)

    try:
        rows, columns = execute_query(query, params)
        if rows and rows[0]:
            row = rows[0]
            total = row[0] or 0
            wins = row[1] or 0
            losses = row[2] or 0
            gross_profit = float(row[5]) if row[5] else 0.0
            gross_loss = float(row[6]) if row[6] else 0.0

            win_rate = (wins / total * 100) if total > 0 else 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

            # Get max drawdown from drawdown data
            dd_df = get_drawdown_data(days=days)
            max_drawdown = float(dd_df["drawdown"].min()) if not dd_df.empty else 0.0

            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(float(row[3]) if row[3] else 0.0, 2),
                "avg_pnl_per_trade": round(float(row[4]) if row[4] else 0.0, 2),
                "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "Inf",
                "best_trade": round(float(row[7]) if row[7] else 0.0, 2),
                "worst_trade": round(float(row[8]) if row[8] else 0.0, 2),
                "avg_confidence": round(float(row[9]) if row[9] else 0.0, 3),
                "max_drawdown": round(max_drawdown, 2),
            }
    except Exception as e:
        print(f"Error loading performance summary: {e}")

    return {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "avg_pnl_per_trade": 0.0,
        "profit_factor": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "avg_confidence": 0.0,
        "max_drawdown": 0.0,
    }
```

---

## 4. Layout - Performance Page Components

### File: `shitty_ui/pages/performance.py`

This is the complete performance page module. It registers itself with Dash's page system and defines both the layout and callbacks.

```python
"""
Performance Page - Detailed prediction performance analysis.
Registered as the '/performance' route in the multi-page app.

Components:
    1. Summary metric cards (top row)
    2. Equity curve chart
    3. Drawdown chart
    4. Win/loss streak display
    5. Rolling accuracy chart
    6. Confidence calibration chart
    7. Sentiment performance breakdown
    8. Monthly/weekly summary table
"""

import dash
from dash import html, dcc, dash_table, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import sys
import os

# Add parent directory to path for data imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import (
    get_equity_curve_data,
    get_drawdown_data,
    get_streak_data,
    get_rolling_accuracy,
    get_confidence_calibration,
    get_sentiment_performance,
    get_periodic_performance,
    get_performance_summary,
)
from components.common import create_metric_card, create_section_card, create_empty_chart_figure

# --------------------------------------------------------------------------
# Page Registration
# --------------------------------------------------------------------------

dash.register_page(
    __name__,
    path="/performance",
    name="Performance",
    title="Shitpost Alpha - Performance Analysis",
)

# --------------------------------------------------------------------------
# Color Palette (matches global theme)
# --------------------------------------------------------------------------

COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}

# Chart layout defaults - reused across all charts
CHART_LAYOUT_DEFAULTS = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color=COLORS["text"],
    margin=dict(l=50, r=30, t=30, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_muted"]),
    ),
    xaxis=dict(gridcolor=COLORS["border"], showgrid=True),
    yaxis=dict(gridcolor=COLORS["border"], showgrid=True),
)

# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

layout = html.Div([
    # Hidden store for time period filter
    dcc.Store(id="perf-period-days", data=None),

    # Page title
    html.Div([
        html.H2([
            html.I(className="fas fa-chart-line me-2"),
            "Performance Analysis",
        ], style={"margin": 0}),
        html.P(
            "Detailed backtesting results assuming $1,000 per prediction",
            style={"color": COLORS["text_muted"], "margin": "5px 0 0 0"},
        ),
    ], className="mb-4"),

    # Time period selector
    html.Div([
        html.Span("Time Period: ", style={"color": COLORS["text_muted"], "marginRight": "10px"}),
        dbc.ButtonGroup([
            dbc.Button("30D", id="perf-period-30d", color="secondary", outline=True, size="sm"),
            dbc.Button("90D", id="perf-period-90d", color="secondary", outline=True, size="sm"),
            dbc.Button("180D", id="perf-period-180d", color="secondary", outline=True, size="sm"),
            dbc.Button("1Y", id="perf-period-365d", color="secondary", outline=True, size="sm"),
            dbc.Button("All", id="perf-period-all", color="primary", size="sm"),  # Default
        ], size="sm"),
    ], className="mb-4", style={"textAlign": "right"}),

    # ---- ROW 1: Summary Metrics ----
    html.Div(id="perf-summary-metrics", className="mb-4"),

    # ---- ROW 2: Equity Curve + Drawdown ----
    dbc.Row([
        dbc.Col([
            create_section_card(
                title="Equity Curve (Cumulative P&L)",
                icon="chart-area",
                children=[
                    dcc.Graph(
                        id="equity-curve-chart",
                        config={"displayModeBar": False},
                        style={"height": "350px"},
                    ),
                ],
            ),
        ], md=12),
    ]),

    dbc.Row([
        dbc.Col([
            create_section_card(
                title="Drawdown Analysis",
                icon="arrow-down",
                children=[
                    dcc.Graph(
                        id="drawdown-chart",
                        config={"displayModeBar": False},
                        style={"height": "250px"},
                    ),
                ],
            ),
        ], md=12),
    ]),

    # ---- ROW 3: Rolling Accuracy + Streaks ----
    dbc.Row([
        dbc.Col([
            create_section_card(
                title="Rolling 30-Prediction Accuracy",
                icon="wave-square",
                children=[
                    dcc.Graph(
                        id="rolling-accuracy-chart",
                        config={"displayModeBar": False},
                        style={"height": "300px"},
                    ),
                ],
            ),
        ], md=8),

        dbc.Col([
            create_section_card(
                title="Win/Loss Streaks",
                icon="fire",
                children=[
                    html.Div(id="streak-display"),
                ],
            ),
        ], md=4),
    ]),

    # ---- ROW 4: Confidence Calibration + Sentiment Breakdown ----
    dbc.Row([
        dbc.Col([
            create_section_card(
                title="Confidence Calibration",
                icon="crosshairs",
                children=[
                    dcc.Graph(
                        id="calibration-chart",
                        config={"displayModeBar": False},
                        style={"height": "350px"},
                    ),
                ],
            ),
        ], md=6),

        dbc.Col([
            create_section_card(
                title="Performance by Sentiment",
                icon="balance-scale",
                children=[
                    html.Div(id="sentiment-performance-display"),
                ],
            ),
        ], md=6),
    ]),

    # ---- ROW 5: Periodic Summary Table ----
    dbc.Row([
        dbc.Col([
            create_section_card(
                title="Periodic Performance Summary",
                icon="calendar-alt",
                children=[
                    # Period toggle: Monthly vs Weekly
                    dbc.RadioItems(
                        id="periodic-toggle",
                        options=[
                            {"label": " Monthly", "value": "month"},
                            {"label": " Weekly", "value": "week"},
                        ],
                        value="month",
                        inline=True,
                        className="mb-3",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Div(id="periodic-table-container"),
                ],
            ),
        ], md=12),
    ]),

], style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"})


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------

# --- Time Period Selection ---

@callback(
    [
        Output("perf-period-days", "data"),
        Output("perf-period-30d", "color"),
        Output("perf-period-30d", "outline"),
        Output("perf-period-90d", "color"),
        Output("perf-period-90d", "outline"),
        Output("perf-period-180d", "color"),
        Output("perf-period-180d", "outline"),
        Output("perf-period-365d", "color"),
        Output("perf-period-365d", "outline"),
        Output("perf-period-all", "color"),
        Output("perf-period-all", "outline"),
    ],
    [
        Input("perf-period-30d", "n_clicks"),
        Input("perf-period-90d", "n_clicks"),
        Input("perf-period-180d", "n_clicks"),
        Input("perf-period-365d", "n_clicks"),
        Input("perf-period-all", "n_clicks"),
    ],
    prevent_initial_call=False,
)
def update_period_selection(n30, n90, n180, n365, nall):
    """Update the selected time period and button styles."""
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    period_map = {
        "perf-period-30d": 30,
        "perf-period-90d": 90,
        "perf-period-180d": 180,
        "perf-period-365d": 365,
        "perf-period-all": None,
    }

    # Default to "All" if no button clicked yet
    selected_days = period_map.get(triggered_id, None)

    # Generate button styles: (color, outline) for each button
    button_keys = ["perf-period-30d", "perf-period-90d", "perf-period-180d", "perf-period-365d", "perf-period-all"]
    styles = []
    for key in button_keys:
        if period_map[key] == selected_days:
            styles.extend(["primary", False])  # Active: solid blue
        else:
            styles.extend(["secondary", True])  # Inactive: outlined gray

    return [selected_days] + styles


# --- Main Performance Dashboard Update ---

@callback(
    [
        Output("perf-summary-metrics", "children"),
        Output("equity-curve-chart", "figure"),
        Output("drawdown-chart", "figure"),
        Output("rolling-accuracy-chart", "figure"),
        Output("streak-display", "children"),
        Output("calibration-chart", "figure"),
        Output("sentiment-performance-display", "children"),
    ],
    [
        Input("refresh-interval", "n_intervals"),
        Input("perf-period-days", "data"),
    ],
)
def update_performance_page(n_intervals, days):
    """Update all performance page components."""

    # ----- 1. Summary Metrics -----
    summary = get_performance_summary(days=days)
    summary_row = _build_summary_metrics(summary)

    # ----- 2. Equity Curve -----
    equity_fig = _build_equity_curve(days)

    # ----- 3. Drawdown Chart -----
    drawdown_fig = _build_drawdown_chart(days)

    # ----- 4. Rolling Accuracy -----
    rolling_fig = _build_rolling_accuracy_chart(days)

    # ----- 5. Streaks -----
    streak_display = _build_streak_display(days)

    # ----- 6. Confidence Calibration -----
    calibration_fig = _build_calibration_chart()

    # ----- 7. Sentiment Performance -----
    sentiment_display = _build_sentiment_display(days)

    return (
        summary_row,
        equity_fig,
        drawdown_fig,
        rolling_fig,
        streak_display,
        calibration_fig,
        sentiment_display,
    )


# --- Periodic Table Callback (separate because it has its own toggle) ---

@callback(
    Output("periodic-table-container", "children"),
    [
        Input("periodic-toggle", "value"),
        Input("perf-period-days", "data"),
    ],
)
def update_periodic_table(period, days):
    """Update the monthly/weekly performance summary table."""
    df = get_periodic_performance(period=period, days=days)

    if df.empty:
        return html.P(
            "No periodic data available.",
            style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "20px"},
        )

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[
            {"name": "Period", "id": "period_label"},
            {"name": "Predictions", "id": "total_predictions"},
            {"name": "Correct", "id": "correct"},
            {"name": "Incorrect", "id": "incorrect"},
            {"name": "Accuracy %", "id": "accuracy"},
            {"name": "Avg Return %", "id": "avg_return"},
            {"name": "Total P&L ($)", "id": "total_pnl"},
            {"name": "Avg Confidence", "id": "avg_confidence"},
        ],
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "center",
            "padding": "10px",
            "backgroundColor": COLORS["primary"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "fontSize": "0.85rem",
        },
        style_header={
            "backgroundColor": COLORS["secondary"],
            "fontWeight": "bold",
            "border": f"1px solid {COLORS['border']}",
        },
        style_data_conditional=[
            {
                "if": {
                    "filter_query": "{total_pnl} > 0",
                    "column_id": "total_pnl",
                },
                "color": COLORS["success"],
            },
            {
                "if": {
                    "filter_query": "{total_pnl} < 0",
                    "column_id": "total_pnl",
                },
                "color": COLORS["danger"],
            },
            {
                "if": {
                    "filter_query": "{accuracy} >= 60",
                    "column_id": "accuracy",
                },
                "color": COLORS["success"],
            },
            {
                "if": {
                    "filter_query": "{accuracy} < 50",
                    "column_id": "accuracy",
                },
                "color": COLORS["danger"],
            },
        ],
        page_size=12,
        sort_action="native",
    )


# --------------------------------------------------------------------------
# Private helper functions for building individual chart/components
# --------------------------------------------------------------------------

def _build_summary_metrics(summary: dict) -> dbc.Row:
    """Build the top row of summary metric cards."""
    pnl_color = COLORS["success"] if summary["total_pnl"] >= 0 else COLORS["danger"]
    wr_color = COLORS["success"] if summary["win_rate"] >= 55 else COLORS["danger"] if summary["win_rate"] < 45 else COLORS["warning"]
    dd_color = COLORS["danger"] if summary["max_drawdown"] < -500 else COLORS["warning"] if summary["max_drawdown"] < 0 else COLORS["success"]

    pf_display = str(summary["profit_factor"]) if summary["profit_factor"] != "Inf" else "Inf"

    return dbc.Row([
        dbc.Col(create_metric_card(
            "Total Trades",
            f"{summary['total_trades']:,}",
            f"{summary['wins']}W / {summary['losses']}L",
            "exchange-alt",
            COLORS["accent"],
        ), xs=6, sm=6, md=3),

        dbc.Col(create_metric_card(
            "Win Rate",
            f"{summary['win_rate']:.1f}%",
            f"Target: >55%",
            "bullseye",
            wr_color,
        ), xs=6, sm=6, md=3),

        dbc.Col(create_metric_card(
            "Total P&L",
            f"${summary['total_pnl']:,.0f}",
            f"Avg ${summary['avg_pnl_per_trade']:,.0f}/trade",
            "dollar-sign",
            pnl_color,
        ), xs=6, sm=6, md=3),

        dbc.Col(create_metric_card(
            "Max Drawdown",
            f"${summary['max_drawdown']:,.0f}",
            f"Profit Factor: {pf_display}",
            "arrow-down",
            dd_color,
        ), xs=6, sm=6, md=3),
    ], className="g-3")


def _build_equity_curve(days: int = None) -> go.Figure:
    """Build the equity curve chart."""
    df = get_equity_curve_data(days=days)

    if df.empty:
        return create_empty_chart_figure("No equity curve data available yet")

    fig = go.Figure()

    # Main equity line
    fig.add_trace(go.Scatter(
        x=df["prediction_date"],
        y=df["cumulative_pnl"],
        mode="lines",
        name="Cumulative P&L",
        line=dict(color=COLORS["accent"], width=2),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.1)",
        hovertemplate=(
            "<b>Date:</b> %{x}<br>"
            "<b>Cumulative P&L:</b> $%{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    # Color the fill: green above zero, red below
    # We accomplish this with a second trace at y=0 and conditional fill
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color=COLORS["text_muted"],
        opacity=0.5,
    )

    # Add markers for wins (green) and losses (red)
    wins = df[df["correct_t7"] == True]
    losses = df[df["correct_t7"] == False]

    fig.add_trace(go.Scatter(
        x=wins["prediction_date"],
        y=wins["cumulative_pnl"],
        mode="markers",
        name="Wins",
        marker=dict(color=COLORS["success"], size=5, symbol="circle"),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "P&L: $%{y:,.0f}<br>"
            "Symbol: %{customdata[0]}<br>"
            "Trade P&L: $%{customdata[1]:,.0f}<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(wins["symbol"], wins["pnl_t7"])),
    ))

    fig.add_trace(go.Scatter(
        x=losses["prediction_date"],
        y=losses["cumulative_pnl"],
        mode="markers",
        name="Losses",
        marker=dict(color=COLORS["danger"], size=5, symbol="x"),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "P&L: $%{y:,.0f}<br>"
            "Symbol: %{customdata[0]}<br>"
            "Trade P&L: $%{customdata[1]:,.0f}<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(losses["symbol"], losses["pnl_t7"])),
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=350,
        yaxis_title="Cumulative P&L ($)",
        xaxis_title="",
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )

    return fig


def _build_drawdown_chart(days: int = None) -> go.Figure:
    """Build the drawdown chart."""
    df = get_drawdown_data(days=days)

    if df.empty:
        return create_empty_chart_figure("No drawdown data available yet")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["prediction_date"],
        y=df["drawdown"],
        mode="lines",
        name="Drawdown",
        line=dict(color=COLORS["danger"], width=1.5),
        fill="tozeroy",
        fillcolor="rgba(239, 68, 68, 0.15)",
        hovertemplate=(
            "<b>Date:</b> %{x}<br>"
            "<b>Drawdown:</b> $%{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    # Highlight max drawdown point
    if not df.empty:
        max_dd_idx = df["drawdown"].idxmin()
        max_dd_row = df.loc[max_dd_idx]
        fig.add_trace(go.Scatter(
            x=[max_dd_row["prediction_date"]],
            y=[max_dd_row["drawdown"]],
            mode="markers+text",
            name="Max Drawdown",
            marker=dict(color=COLORS["danger"], size=10, symbol="diamond"),
            text=[f"${max_dd_row['drawdown']:,.0f}"],
            textposition="bottom center",
            textfont=dict(color=COLORS["danger"], size=11),
            hovertemplate=(
                "<b>Max Drawdown</b><br>"
                "Date: %{x}<br>"
                "Amount: $%{y:,.0f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text_muted"], opacity=0.3)

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=250,
        yaxis_title="Drawdown ($)",
        xaxis_title="",
        showlegend=False,
    )

    return fig


def _build_rolling_accuracy_chart(days: int = None) -> go.Figure:
    """Build the rolling accuracy line chart."""
    df = get_rolling_accuracy(window=30, days=days)

    if df.empty:
        return create_empty_chart_figure(
            "Need at least 30 evaluated predictions for rolling accuracy"
        )

    fig = go.Figure()

    # Rolling accuracy line
    fig.add_trace(go.Scatter(
        x=df["prediction_date"],
        y=df["rolling_accuracy"],
        mode="lines",
        name="30-Prediction Rolling Accuracy",
        line=dict(color=COLORS["accent"], width=2),
        hovertemplate=(
            "<b>Date:</b> %{x}<br>"
            "<b>Accuracy:</b> %{y:.1f}%<br>"
            "<b>Correct:</b> %{customdata}/30<br>"
            "<extra></extra>"
        ),
        customdata=df["rolling_correct"],
    ))

    # 50% baseline (random chance)
    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color=COLORS["warning"],
        opacity=0.7,
        annotation_text="50% (random)",
        annotation_position="bottom right",
        annotation_font_color=COLORS["warning"],
    )

    # 60% target line
    fig.add_hline(
        y=60,
        line_dash="dot",
        line_color=COLORS["success"],
        opacity=0.5,
        annotation_text="60% target",
        annotation_position="top right",
        annotation_font_color=COLORS["success"],
    )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        yaxis_title="Accuracy %",
        yaxis_range=[
            max(0, df["rolling_accuracy"].min() - 10),
            min(100, df["rolling_accuracy"].max() + 10),
        ],
        xaxis_title="",
        showlegend=False,
    )

    return fig


def _build_streak_display(days: int = None) -> html.Div:
    """Build the win/loss streak display panel."""
    data = get_streak_data(days=days)

    if data["current_streak"] == 0:
        return html.P(
            "No streak data available.",
            style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "20px"},
        )

    current_color = COLORS["success"] if data["current_streak_type"] == "win" else COLORS["danger"]
    current_icon = "fire" if data["current_streak_type"] == "win" else "snowflake"

    return html.Div([
        # Current streak - large display
        html.Div([
            html.H4("Current Streak", style={"color": COLORS["text_muted"], "marginBottom": "10px"}),
            html.Div([
                html.I(
                    className=f"fas fa-{current_icon}",
                    style={"fontSize": "2rem", "color": current_color, "marginRight": "10px"},
                ),
                html.Span(
                    f"{data['current_streak']} {data['current_streak_type'].upper()}S",
                    style={"fontSize": "1.8rem", "fontWeight": "bold", "color": current_color},
                ),
            ], className="d-flex align-items-center justify-content-center mb-4"),
        ], style={"textAlign": "center"}),

        # Max streaks
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="fas fa-trophy me-2", style={"color": COLORS["success"]}),
                    html.Span("Best Win Streak", style={"color": COLORS["text_muted"]}),
                ]),
                html.H4(
                    f"{data['max_win_streak']}",
                    style={"color": COLORS["success"], "margin": "5px 0"},
                ),
            ], style={
                "textAlign": "center",
                "padding": "15px",
                "borderRight": f"1px solid {COLORS['border']}",
                "flex": 1,
            }),

            html.Div([
                html.Div([
                    html.I(className="fas fa-skull-crossbones me-2", style={"color": COLORS["danger"]}),
                    html.Span("Worst Loss Streak", style={"color": COLORS["text_muted"]}),
                ]),
                html.H4(
                    f"{data['max_loss_streak']}",
                    style={"color": COLORS["danger"], "margin": "5px 0"},
                ),
            ], style={
                "textAlign": "center",
                "padding": "15px",
                "flex": 1,
            }),
        ], style={"display": "flex"}),

        # Recent streaks timeline (last 10)
        html.Hr(style={"borderColor": COLORS["border"]}),
        html.H6("Recent Streaks", style={"color": COLORS["text_muted"], "marginBottom": "10px"}),
        html.Div([
            html.Div([
                html.Div(
                    style={
                        "width": f"{min(s['length'] * 20, 100)}px",
                        "height": "20px",
                        "backgroundColor": COLORS["success"] if s["type"] == "win" else COLORS["danger"],
                        "borderRadius": "3px",
                        "display": "inline-block",
                        "marginRight": "8px",
                    },
                ),
                html.Span(
                    f"{s['length']} {s['type']}{'s' if s['length'] > 1 else ''}",
                    style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                ),
            ], className="mb-1")
            for s in data["streaks"][-10:]  # Show last 10 streaks
        ], style={"maxHeight": "200px", "overflowY": "auto"}),
    ])


def _build_calibration_chart() -> go.Figure:
    """Build the confidence calibration chart."""
    df = get_confidence_calibration(bucket_size=0.1)

    if df.empty:
        return create_empty_chart_figure("Not enough data for confidence calibration")

    fig = go.Figure()

    # Perfect calibration line (diagonal)
    fig.add_trace(go.Scatter(
        x=[0, 100],
        y=[0, 100],
        mode="lines",
        name="Perfect Calibration",
        line=dict(color=COLORS["text_muted"], width=1, dash="dash"),
        hoverinfo="skip",
    ))

    # Actual calibration bars
    fig.add_trace(go.Bar(
        x=df["confidence_bucket"],
        y=df["actual_accuracy"],
        name="Actual Accuracy",
        marker_color=COLORS["accent"],
        text=df["actual_accuracy"].apply(lambda x: f"{x:.0f}%"),
        textposition="outside",
        hovertemplate=(
            "<b>Confidence Bucket:</b> %{x}<br>"
            "<b>Actual Accuracy:</b> %{y:.1f}%<br>"
            "<b>Avg Confidence:</b> %{customdata[0]:.0%}<br>"
            "<b>Predictions:</b> %{customdata[1]}<br>"
            "<extra></extra>"
        ),
        customdata=list(zip(
            df["predicted_confidence"],
            df["total"],
        )),
    ))

    # Predicted confidence markers (for comparison)
    fig.add_trace(go.Scatter(
        x=df["confidence_bucket"],
        y=df["predicted_confidence"] * 100,
        mode="markers",
        name="Predicted Confidence",
        marker=dict(
            color=COLORS["warning"],
            size=10,
            symbol="diamond",
            line=dict(width=1, color=COLORS["text"]),
        ),
        hovertemplate=(
            "<b>Predicted:</b> %{y:.1f}%<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=350,
        yaxis_title="Accuracy / Confidence %",
        yaxis_range=[0, 105],
        xaxis_title="Confidence Bucket",
        barmode="group",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )

    return fig


def _build_sentiment_display(days: int = None) -> html.Div:
    """Build the sentiment performance breakdown."""
    df = get_sentiment_performance(days=days)

    if df.empty:
        return html.P(
            "No sentiment performance data available.",
            style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "20px"},
        )

    sentiment_configs = {
        "bullish": {"icon": "arrow-up", "color": COLORS["success"], "label": "BULLISH"},
        "bearish": {"icon": "arrow-down", "color": COLORS["danger"], "label": "BEARISH"},
        "neutral": {"icon": "minus", "color": COLORS["text_muted"], "label": "NEUTRAL"},
    }

    cards = []
    for _, row in df.iterrows():
        sentiment = row["prediction_sentiment"].lower()
        config = sentiment_configs.get(sentiment, sentiment_configs["neutral"])

        accuracy = row.get("accuracy", 0)
        accuracy_color = COLORS["success"] if accuracy >= 55 else COLORS["danger"]

        cards.append(
            html.Div([
                # Header
                html.Div([
                    html.I(
                        className=f"fas fa-{config['icon']}",
                        style={"color": config["color"], "fontSize": "1.2rem"},
                    ),
                    html.Span(
                        f" {config['label']}",
                        style={"color": config["color"], "fontWeight": "bold", "fontSize": "1rem"},
                    ),
                    html.Span(
                        f" ({row['total']} trades)",
                        style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
                    ),
                ], className="mb-2"),

                # Stats grid
                html.Div([
                    html.Div([
                        html.Div("Accuracy", style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                        html.Div(
                            f"{accuracy:.1f}%",
                            style={"color": accuracy_color, "fontWeight": "bold"},
                        ),
                    ], style={"flex": 1, "textAlign": "center"}),

                    html.Div([
                        html.Div("Avg Return", style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                        html.Div(
                            f"{row['avg_return']:+.2f}%",
                            style={
                                "color": COLORS["success"] if row["avg_return"] > 0 else COLORS["danger"],
                                "fontWeight": "bold",
                            },
                        ),
                    ], style={"flex": 1, "textAlign": "center"}),

                    html.Div([
                        html.Div("Total P&L", style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                        html.Div(
                            f"${row['total_pnl']:,.0f}",
                            style={
                                "color": COLORS["success"] if row["total_pnl"] > 0 else COLORS["danger"],
                                "fontWeight": "bold",
                            },
                        ),
                    ], style={"flex": 1, "textAlign": "center"}),

                    html.Div([
                        html.Div("W/L", style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                        html.Div(
                            f"{row['correct']}/{row['incorrect']}",
                            style={"fontWeight": "bold"},
                        ),
                    ], style={"flex": 1, "textAlign": "center"}),
                ], style={"display": "flex"}),
            ], style={
                "padding": "15px",
                "borderBottom": f"1px solid {COLORS['border']}",
            })
        )

    return html.Div(cards)
```

---

## 5. Callbacks

All callbacks are defined in `pages/performance.py` above. Here is a summary for reference:

### Callback Map

| Callback | Inputs | Outputs | Purpose |
|----------|--------|---------|---------|
| `update_period_selection` | 5 button clicks | `perf-period-days` store + 10 button styles | Switches time period, updates button visual state |
| `update_performance_page` | `refresh-interval`, `perf-period-days` | 7 component outputs | Main page refresh - updates all charts and metrics |
| `update_periodic_table` | `periodic-toggle`, `perf-period-days` | `periodic-table-container` | Switches between monthly/weekly summary table |

### Callback Dependency Graph

```
[perf-period-30d/90d/180d/365d/all buttons]
    |
    v
[perf-period-days store] ----+
    |                        |
    v                        v
[update_performance_page]  [update_periodic_table]
    |                        |
    +-- perf-summary-metrics |
    +-- equity-curve-chart   +-- periodic-table-container
    +-- drawdown-chart
    +-- rolling-accuracy-chart
    +-- streak-display
    +-- calibration-chart
    +-- sentiment-performance-display

[refresh-interval] ----------> [update_performance_page]
```

---

## 6. Test Specifications

Tests follow the existing patterns in `shit_tests/shitty_ui/`. All data functions are tested by mocking `execute_query()`. Layout helper functions are tested by verifying they return the correct component types.

### 6.1 Data Layer Tests

**File**: `shit_tests/shitty_ui/test_performance_data.py`

```python
"""
Tests for performance page data layer functions.
Tests all new query functions added to data.py for the /performance page.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date
import pandas as pd
import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))


class TestGetEquityCurveData:
    """Tests for get_equity_curve_data function."""

    @patch('data.execute_query')
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_equity_curve_data

        mock_execute.return_value = (
            [
                (date(2024, 1, 15), 'AAPL', 'bullish', 50.0, 0.8, True, 50.0),
                (date(2024, 1, 16), 'TSLA', 'bearish', -30.0, 0.6, False, 20.0),
            ],
            ['prediction_date', 'symbol', 'prediction_sentiment', 'pnl_t7',
             'prediction_confidence', 'correct_t7', 'cumulative_pnl']
        )

        result = get_equity_curve_data()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'cumulative_pnl' in result.columns

    @patch('data.execute_query')
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_equity_curve_data

        mock_execute.side_effect = Exception("Database error")

        result = get_equity_curve_data()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('data.execute_query')
    def test_days_parameter_adds_date_filter(self, mock_execute):
        """Test that days parameter adds date filtering to query."""
        from data import get_equity_curve_data

        mock_execute.return_value = ([], [])

        get_equity_curve_data(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        # The query text should contain start_date parameter
        assert 'start_date' in str(call_args[1])

    @patch('data.execute_query')
    def test_no_days_parameter_returns_all_data(self, mock_execute):
        """Test that no days parameter returns all data (no date filter)."""
        from data import get_equity_curve_data

        mock_execute.return_value = ([], [])

        get_equity_curve_data(days=None)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        # Should not have start_date in params
        assert call_args[1] == {}


class TestGetDrawdownData:
    """Tests for get_drawdown_data function."""

    @patch('data.get_equity_curve_data')
    def test_returns_dataframe_with_drawdown(self, mock_equity):
        """Test that function returns DataFrame with drawdown columns."""
        from data import get_drawdown_data

        mock_equity.return_value = pd.DataFrame({
            'prediction_date': [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)],
            'cumulative_pnl': [100.0, 150.0, 80.0],
            'pnl_t7': [100.0, 50.0, -70.0],
            'symbol': ['AAPL', 'TSLA', 'GOOGL'],
            'correct_t7': [True, True, False],
        })

        result = get_drawdown_data()

        assert isinstance(result, pd.DataFrame)
        assert 'drawdown' in result.columns
        assert 'peak_pnl' in result.columns
        # Peak should be 150, drawdown at end should be 80 - 150 = -70
        assert result.iloc[-1]['drawdown'] == -70.0

    @patch('data.get_equity_curve_data')
    def test_returns_empty_dataframe_when_no_equity_data(self, mock_equity):
        """Test that function returns empty DataFrame when equity data is empty."""
        from data import get_drawdown_data

        mock_equity.return_value = pd.DataFrame()

        result = get_drawdown_data()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('data.get_equity_curve_data')
    def test_peak_is_cumulative_max(self, mock_equity):
        """Test that peak tracks the running maximum."""
        from data import get_drawdown_data

        mock_equity.return_value = pd.DataFrame({
            'prediction_date': [
                date(2024, 1, 15),
                date(2024, 1, 16),
                date(2024, 1, 17),
                date(2024, 1, 18),
            ],
            'cumulative_pnl': [50.0, 200.0, 100.0, 300.0],
            'pnl_t7': [50.0, 150.0, -100.0, 200.0],
            'symbol': ['A', 'B', 'C', 'D'],
            'correct_t7': [True, True, False, True],
        })

        result = get_drawdown_data()

        # Peak should never decrease: [50, 200, 200, 300]
        expected_peaks = [50.0, 200.0, 200.0, 300.0]
        assert list(result['peak_pnl']) == expected_peaks


class TestGetStreakData:
    """Tests for get_streak_data function."""

    @patch('data.execute_query')
    def test_returns_streak_dict(self, mock_execute):
        """Test that function returns a dictionary with streak info."""
        from data import get_streak_data

        mock_execute.return_value = (
            [
                (date(2024, 1, 15), True, 50.0),
                (date(2024, 1, 16), True, 30.0),
                (date(2024, 1, 17), False, -20.0),
            ],
            ['prediction_date', 'correct_t7', 'pnl_t7']
        )

        result = get_streak_data()

        assert isinstance(result, dict)
        assert 'current_streak' in result
        assert 'current_streak_type' in result
        assert 'max_win_streak' in result
        assert 'max_loss_streak' in result
        assert 'streaks' in result

    @patch('data.execute_query')
    def test_calculates_current_streak_correctly(self, mock_execute):
        """Test that current streak reflects the last sequence."""
        from data import get_streak_data

        # Last 3 are wins
        mock_execute.return_value = (
            [
                (date(2024, 1, 15), False, -20.0),
                (date(2024, 1, 16), True, 30.0),
                (date(2024, 1, 17), True, 40.0),
                (date(2024, 1, 18), True, 50.0),
            ],
            ['prediction_date', 'correct_t7', 'pnl_t7']
        )

        result = get_streak_data()

        assert result['current_streak'] == 3
        assert result['current_streak_type'] == 'win'

    @patch('data.execute_query')
    def test_max_streaks_are_correct(self, mock_execute):
        """Test that max win and loss streaks are correctly identified."""
        from data import get_streak_data

        mock_execute.return_value = (
            [
                (date(2024, 1, 10), True, 10.0),
                (date(2024, 1, 11), True, 20.0),
                (date(2024, 1, 12), True, 30.0),   # 3-win streak
                (date(2024, 1, 13), False, -10.0),
                (date(2024, 1, 14), False, -20.0),  # 2-loss streak
                (date(2024, 1, 15), True, 40.0),    # 1-win streak
            ],
            ['prediction_date', 'correct_t7', 'pnl_t7']
        )

        result = get_streak_data()

        assert result['max_win_streak'] == 3
        assert result['max_loss_streak'] == 2

    @patch('data.execute_query')
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_streak_data

        mock_execute.side_effect = Exception("Database error")

        result = get_streak_data()

        assert result['current_streak'] == 0
        assert result['max_win_streak'] == 0

    @patch('data.execute_query')
    def test_returns_defaults_on_empty_data(self, mock_execute):
        """Test that function returns defaults when no data."""
        from data import get_streak_data

        mock_execute.return_value = ([], [])

        result = get_streak_data()

        assert result['current_streak'] == 0
        assert result['current_streak_type'] == 'none'


class TestGetRollingAccuracy:
    """Tests for get_rolling_accuracy function."""

    @patch('data.execute_query')
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_rolling_accuracy

        # Create 35 rows of data (enough for window of 30)
        rows = [
            (date(2024, 1, i + 1), i % 2 == 0)  # Alternating T/F
            for i in range(35)
        ]

        mock_execute.return_value = (
            rows,
            ['prediction_date', 'correct_t7']
        )

        result = get_rolling_accuracy(window=30)

        assert isinstance(result, pd.DataFrame)
        assert 'rolling_accuracy' in result.columns

    @patch('data.execute_query')
    def test_returns_empty_if_less_than_window(self, mock_execute):
        """Test returns empty DataFrame if fewer rows than window size."""
        from data import get_rolling_accuracy

        mock_execute.return_value = (
            [(date(2024, 1, i + 1), True) for i in range(10)],
            ['prediction_date', 'correct_t7']
        )

        result = get_rolling_accuracy(window=30)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('data.execute_query')
    def test_accuracy_values_between_0_and_100(self, mock_execute):
        """Test that rolling accuracy values are in valid range."""
        from data import get_rolling_accuracy

        rows = [(date(2024, 1, i + 1), True) for i in range(40)]

        mock_execute.return_value = (rows, ['prediction_date', 'correct_t7'])

        result = get_rolling_accuracy(window=30)

        if not result.empty:
            assert result['rolling_accuracy'].min() >= 0
            assert result['rolling_accuracy'].max() <= 100


class TestGetConfidenceCalibration:
    """Tests for get_confidence_calibration function."""

    @patch('data.execute_query')
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_confidence_calibration

        mock_execute.return_value = (
            [
                (0.55, True), (0.58, False), (0.52, True),
                (0.65, True), (0.68, True), (0.72, False),
                (0.82, True), (0.85, True), (0.88, True),
            ],
            ['prediction_confidence', 'correct_t7']
        )

        result = get_confidence_calibration(bucket_size=0.1)

        assert isinstance(result, pd.DataFrame)
        assert 'actual_accuracy' in result.columns
        assert 'confidence_bucket' in result.columns

    @patch('data.execute_query')
    def test_filters_buckets_with_few_predictions(self, mock_execute):
        """Test that buckets with fewer than 3 predictions are filtered out."""
        from data import get_confidence_calibration

        mock_execute.return_value = (
            [
                # Only 1 prediction in the 90-100% bucket
                (0.95, True),
                # 5 predictions in the 50-60% bucket
                (0.55, True), (0.58, False), (0.52, True), (0.55, True), (0.59, False),
            ],
            ['prediction_confidence', 'correct_t7']
        )

        result = get_confidence_calibration(bucket_size=0.1)

        # 90-100% bucket should be filtered (only 1 prediction)
        if not result.empty:
            bucket_labels = result['confidence_bucket'].tolist()
            assert '90-100%' not in bucket_labels

    @patch('data.execute_query')
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_confidence_calibration

        mock_execute.side_effect = Exception("Database error")

        result = get_confidence_calibration()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetSentimentPerformance:
    """Tests for get_sentiment_performance function."""

    @patch('data.execute_query')
    def test_returns_dataframe_with_accuracy(self, mock_execute):
        """Test that function returns DataFrame with accuracy column."""
        from data import get_sentiment_performance

        mock_execute.return_value = (
            [
                ('bullish', 50, 35, 15, 2.5, 1250.0, 0.72),
                ('bearish', 30, 18, 12, -0.5, -150.0, 0.65),
            ],
            ['prediction_sentiment', 'total', 'correct', 'incorrect',
             'avg_return', 'total_pnl', 'avg_confidence']
        )

        result = get_sentiment_performance()

        assert isinstance(result, pd.DataFrame)
        assert 'accuracy' in result.columns
        assert len(result) == 2

    @patch('data.execute_query')
    def test_accuracy_calculation(self, mock_execute):
        """Test that accuracy is calculated correctly per sentiment."""
        from data import get_sentiment_performance

        mock_execute.return_value = (
            [('bullish', 10, 7, 3, 1.0, 700.0, 0.8)],
            ['prediction_sentiment', 'total', 'correct', 'incorrect',
             'avg_return', 'total_pnl', 'avg_confidence']
        )

        result = get_sentiment_performance()

        assert result.iloc[0]['accuracy'] == 70.0  # 7/10 = 70%

    @patch('data.execute_query')
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_sentiment_performance

        mock_execute.side_effect = Exception("Database error")

        result = get_sentiment_performance()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('data.execute_query')
    def test_days_parameter_filtering(self, mock_execute):
        """Test that days parameter is applied."""
        from data import get_sentiment_performance

        mock_execute.return_value = ([], [])

        get_sentiment_performance(days=30)

        call_args = mock_execute.call_args[0]
        assert 'start_date' in str(call_args[1])


class TestGetPeriodicPerformance:
    """Tests for get_periodic_performance function."""

    @patch('data.execute_query')
    def test_returns_monthly_dataframe(self, mock_execute):
        """Test that function returns DataFrame with monthly data."""
        from data import get_periodic_performance

        mock_execute.return_value = (
            [
                ('2024-01', 25, 15, 10, 1.5, 375.0, 0.7),
                ('2024-02', 30, 20, 10, 2.0, 600.0, 0.72),
            ],
            ['period_label', 'total_predictions', 'correct', 'incorrect',
             'avg_return', 'total_pnl', 'avg_confidence']
        )

        result = get_periodic_performance(period='month')

        assert isinstance(result, pd.DataFrame)
        assert 'accuracy' in result.columns
        assert len(result) == 2

    @patch('data.execute_query')
    def test_returns_weekly_dataframe(self, mock_execute):
        """Test that function returns DataFrame with weekly data."""
        from data import get_periodic_performance

        mock_execute.return_value = (
            [('2024-W03', 5, 3, 2, 1.0, 50.0, 0.65)],
            ['period_label', 'total_predictions', 'correct', 'incorrect',
             'avg_return', 'total_pnl', 'avg_confidence']
        )

        result = get_periodic_performance(period='week')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @patch('data.execute_query')
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_periodic_performance

        mock_execute.side_effect = Exception("Database error")

        result = get_periodic_performance()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetPerformanceSummary:
    """Tests for get_performance_summary function."""

    @patch('data.get_drawdown_data')
    @patch('data.execute_query')
    def test_returns_summary_dict(self, mock_execute, mock_drawdown):
        """Test that function returns a dictionary with all expected keys."""
        from data import get_performance_summary

        mock_execute.return_value = (
            [(100, 60, 40, 5000.0, 50.0, 8000.0, 3000.0, 250.0, -150.0, 0.72)],
            ['total_trades', 'wins', 'losses', 'total_pnl', 'avg_pnl',
             'gross_profit', 'gross_loss', 'best_trade', 'worst_trade', 'avg_confidence']
        )
        mock_drawdown.return_value = pd.DataFrame({
            'prediction_date': [date(2024, 1, 15)],
            'drawdown': [-500.0],
        })

        result = get_performance_summary()

        assert isinstance(result, dict)
        assert result['total_trades'] == 100
        assert result['wins'] == 60
        assert result['losses'] == 40
        assert result['win_rate'] == 60.0
        assert result['total_pnl'] == 5000.0
        assert result['profit_factor'] == round(8000.0 / 3000.0, 2)
        assert result['max_drawdown'] == -500.0

    @patch('data.get_drawdown_data')
    @patch('data.execute_query')
    def test_handles_zero_gross_loss(self, mock_execute, mock_drawdown):
        """Test profit factor when gross loss is zero."""
        from data import get_performance_summary

        mock_execute.return_value = (
            [(10, 10, 0, 1000.0, 100.0, 1000.0, 0.0, 200.0, 50.0, 0.8)],
            ['total_trades', 'wins', 'losses', 'total_pnl', 'avg_pnl',
             'gross_profit', 'gross_loss', 'best_trade', 'worst_trade', 'avg_confidence']
        )
        mock_drawdown.return_value = pd.DataFrame({'drawdown': [0.0]})

        result = get_performance_summary()

        assert result['profit_factor'] == "Inf"

    @patch('data.execute_query')
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns defaults on error."""
        from data import get_performance_summary

        mock_execute.side_effect = Exception("Database error")

        result = get_performance_summary()

        assert result['total_trades'] == 0
        assert result['win_rate'] == 0.0
        assert result['total_pnl'] == 0.0
```

### 6.2 Layout / Component Tests

**File**: `shit_tests/shitty_ui/test_performance_layout.py`

```python
"""
Tests for performance page layout components.
Tests the component builder functions in pages/performance.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))


class TestBuildSummaryMetrics:
    """Tests for _build_summary_metrics function."""

    def test_returns_dbc_row(self):
        """Test that function returns a dbc.Row component."""
        from pages.performance import _build_summary_metrics
        import dash_bootstrap_components as dbc

        summary = {
            "total_trades": 100,
            "wins": 60,
            "losses": 40,
            "win_rate": 60.0,
            "total_pnl": 5000.0,
            "avg_pnl_per_trade": 50.0,
            "profit_factor": 2.67,
            "best_trade": 250.0,
            "worst_trade": -150.0,
            "avg_confidence": 0.72,
            "max_drawdown": -500.0,
        }

        result = _build_summary_metrics(summary)

        assert isinstance(result, dbc.Row)

    def test_handles_zero_values(self):
        """Test that function handles zero/default values."""
        from pages.performance import _build_summary_metrics

        summary = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl_per_trade": 0.0,
            "profit_factor": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_confidence": 0.0,
            "max_drawdown": 0.0,
        }

        result = _build_summary_metrics(summary)
        # Should not raise an error
        assert result is not None

    def test_handles_inf_profit_factor(self):
        """Test that function handles 'Inf' profit factor display."""
        from pages.performance import _build_summary_metrics

        summary = {
            "total_trades": 10,
            "wins": 10,
            "losses": 0,
            "win_rate": 100.0,
            "total_pnl": 1000.0,
            "avg_pnl_per_trade": 100.0,
            "profit_factor": "Inf",
            "best_trade": 200.0,
            "worst_trade": 50.0,
            "avg_confidence": 0.9,
            "max_drawdown": 0.0,
        }

        result = _build_summary_metrics(summary)
        assert result is not None


class TestBuildEquityCurve:
    """Tests for _build_equity_curve function."""

    @patch('pages.performance.get_equity_curve_data')
    def test_returns_figure(self, mock_data):
        """Test that function returns a plotly Figure."""
        import plotly.graph_objects as go
        from pages.performance import _build_equity_curve

        mock_data.return_value = pd.DataFrame({
            'prediction_date': [date(2024, 1, 15), date(2024, 1, 16)],
            'cumulative_pnl': [50.0, 80.0],
            'pnl_t7': [50.0, 30.0],
            'symbol': ['AAPL', 'TSLA'],
            'correct_t7': [True, True],
            'prediction_sentiment': ['bullish', 'bullish'],
            'prediction_confidence': [0.8, 0.7],
        })

        result = _build_equity_curve()

        assert isinstance(result, go.Figure)
        assert len(result.data) > 0  # Should have at least one trace

    @patch('pages.performance.get_equity_curve_data')
    def test_returns_empty_figure_when_no_data(self, mock_data):
        """Test that function returns empty figure when no data."""
        import plotly.graph_objects as go
        from pages.performance import _build_equity_curve

        mock_data.return_value = pd.DataFrame()

        result = _build_equity_curve()

        assert isinstance(result, go.Figure)


class TestBuildDrawdownChart:
    """Tests for _build_drawdown_chart function."""

    @patch('pages.performance.get_drawdown_data')
    def test_returns_figure(self, mock_data):
        """Test that function returns a plotly Figure."""
        import plotly.graph_objects as go
        from pages.performance import _build_drawdown_chart

        mock_data.return_value = pd.DataFrame({
            'prediction_date': [date(2024, 1, 15), date(2024, 1, 16)],
            'cumulative_pnl': [100.0, 80.0],
            'peak_pnl': [100.0, 100.0],
            'drawdown': [0.0, -20.0],
            'drawdown_pct': [0.0, -20.0],
        })

        result = _build_drawdown_chart()

        assert isinstance(result, go.Figure)

    @patch('pages.performance.get_drawdown_data')
    def test_handles_empty_data(self, mock_data):
        """Test that function handles empty data gracefully."""
        import plotly.graph_objects as go
        from pages.performance import _build_drawdown_chart

        mock_data.return_value = pd.DataFrame()

        result = _build_drawdown_chart()

        assert isinstance(result, go.Figure)


class TestBuildRollingAccuracyChart:
    """Tests for _build_rolling_accuracy_chart function."""

    @patch('pages.performance.get_rolling_accuracy')
    def test_returns_figure_with_data(self, mock_data):
        """Test that function returns a Figure with rolling accuracy line."""
        import plotly.graph_objects as go
        from pages.performance import _build_rolling_accuracy_chart

        mock_data.return_value = pd.DataFrame({
            'prediction_date': [date(2024, 1, i + 1) for i in range(10)],
            'rolling_accuracy': [55.0 + i for i in range(10)],
            'rolling_correct': [16 + i % 3 for i in range(10)],
            'rolling_total': [30] * 10,
        })

        result = _build_rolling_accuracy_chart()

        assert isinstance(result, go.Figure)

    @patch('pages.performance.get_rolling_accuracy')
    def test_shows_message_when_insufficient_data(self, mock_data):
        """Test that chart shows message when not enough data for rolling window."""
        import plotly.graph_objects as go
        from pages.performance import _build_rolling_accuracy_chart

        mock_data.return_value = pd.DataFrame()

        result = _build_rolling_accuracy_chart()

        assert isinstance(result, go.Figure)


class TestBuildStreakDisplay:
    """Tests for _build_streak_display function."""

    @patch('pages.performance.get_streak_data')
    def test_returns_div_with_streak_info(self, mock_data):
        """Test that function returns an html.Div with streak data."""
        from dash import html
        from pages.performance import _build_streak_display

        mock_data.return_value = {
            'current_streak': 3,
            'current_streak_type': 'win',
            'max_win_streak': 5,
            'max_loss_streak': 2,
            'streaks': [
                {'type': 'win', 'length': 5, 'start_date': '2024-01-10', 'end_date': '2024-01-15'},
                {'type': 'loss', 'length': 2, 'start_date': '2024-01-15', 'end_date': '2024-01-17'},
                {'type': 'win', 'length': 3, 'start_date': '2024-01-17', 'end_date': '2024-01-20'},
            ],
        }

        result = _build_streak_display()

        assert isinstance(result, html.Div)

    @patch('pages.performance.get_streak_data')
    def test_handles_no_streak_data(self, mock_data):
        """Test that function handles no streak data."""
        from dash import html
        from pages.performance import _build_streak_display

        mock_data.return_value = {
            'current_streak': 0,
            'current_streak_type': 'none',
            'max_win_streak': 0,
            'max_loss_streak': 0,
            'streaks': [],
        }

        result = _build_streak_display()

        # Should return a paragraph with a message, not crash
        assert result is not None


class TestBuildCalibrationChart:
    """Tests for _build_calibration_chart function."""

    @patch('pages.performance.get_confidence_calibration')
    def test_returns_figure(self, mock_data):
        """Test that function returns a plotly Figure."""
        import plotly.graph_objects as go
        from pages.performance import _build_calibration_chart

        mock_data.return_value = pd.DataFrame({
            'confidence_bucket': ['50-60%', '60-70%', '70-80%'],
            'bucket_midpoint': [0.55, 0.65, 0.75],
            'predicted_confidence': [0.55, 0.65, 0.75],
            'actual_accuracy': [52.0, 63.0, 71.0],
            'total': [20, 30, 15],
            'correct': [10, 19, 11],
        })

        result = _build_calibration_chart()

        assert isinstance(result, go.Figure)

    @patch('pages.performance.get_confidence_calibration')
    def test_handles_empty_data(self, mock_data):
        """Test that function handles empty calibration data."""
        import plotly.graph_objects as go
        from pages.performance import _build_calibration_chart

        mock_data.return_value = pd.DataFrame()

        result = _build_calibration_chart()

        assert isinstance(result, go.Figure)


class TestBuildSentimentDisplay:
    """Tests for _build_sentiment_display function."""

    @patch('pages.performance.get_sentiment_performance')
    def test_returns_div_with_sentiment_cards(self, mock_data):
        """Test that function returns div with sentiment breakdown cards."""
        from dash import html
        from pages.performance import _build_sentiment_display

        mock_data.return_value = pd.DataFrame({
            'prediction_sentiment': ['bullish', 'bearish'],
            'total': [50, 30],
            'correct': [35, 18],
            'incorrect': [15, 12],
            'accuracy': [70.0, 60.0],
            'avg_return': [2.5, -0.5],
            'total_pnl': [1250.0, -150.0],
            'avg_confidence': [0.72, 0.65],
        })

        result = _build_sentiment_display()

        assert isinstance(result, html.Div)

    @patch('pages.performance.get_sentiment_performance')
    def test_handles_empty_data(self, mock_data):
        """Test handles empty sentiment data gracefully."""
        from pages.performance import _build_sentiment_display

        mock_data.return_value = pd.DataFrame()

        result = _build_sentiment_display()

        # Should return something (a paragraph with message), not crash
        assert result is not None
```

### 6.3 Test Summary

| Test Class | Tests | File |
|------------|-------|------|
| `TestGetEquityCurveData` | 4 | `test_performance_data.py` |
| `TestGetDrawdownData` | 3 | `test_performance_data.py` |
| `TestGetStreakData` | 5 | `test_performance_data.py` |
| `TestGetRollingAccuracy` | 3 | `test_performance_data.py` |
| `TestGetConfidenceCalibration` | 3 | `test_performance_data.py` |
| `TestGetSentimentPerformance` | 4 | `test_performance_data.py` |
| `TestGetPeriodicPerformance` | 3 | `test_performance_data.py` |
| `TestGetPerformanceSummary` | 3 | `test_performance_data.py` |
| `TestBuildSummaryMetrics` | 3 | `test_performance_layout.py` |
| `TestBuildEquityCurve` | 2 | `test_performance_layout.py` |
| `TestBuildDrawdownChart` | 2 | `test_performance_layout.py` |
| `TestBuildRollingAccuracyChart` | 2 | `test_performance_layout.py` |
| `TestBuildStreakDisplay` | 2 | `test_performance_layout.py` |
| `TestBuildCalibrationChart` | 2 | `test_performance_layout.py` |
| `TestBuildSentimentDisplay` | 2 | `test_performance_layout.py` |
| **Total** | **43** | |

---

## 7. Implementation Checklist

### Phase A: Multi-Page Foundation (Day 1)

- [ ] Create `shitty_ui/pages/` directory with `__init__.py`
- [ ] Create `shitty_ui/components/` directory with `__init__.py`
- [ ] Create `shitty_ui/components/nav.py` with `create_navbar()`
- [ ] Create `shitty_ui/components/common.py` with shared components
  - [ ] Move `create_metric_card()` from `layout.py` to `common.py`
  - [ ] Add `create_empty_chart_figure()`
  - [ ] Add `create_section_card()`
- [ ] Update `shitty_ui/app.py` to use `use_pages=True`
- [ ] Create `shitty_ui/pages/home.py` to register existing dashboard as `/`
- [ ] Refactor `shitty_ui/layout.py`:
  - [ ] Extract main content into `create_home_content()` function
  - [ ] Update imports to use `components.common` for shared functions
  - [ ] Keep callbacks in `layout.py` (they are registered via `register_callbacks()`)
- [ ] Verify the existing dashboard still works at `/`
- [ ] Run existing tests to confirm nothing is broken

### Phase B: Data Layer (Day 1-2)

- [ ] Add `get_equity_curve_data()` to `data.py`
- [ ] Add `get_drawdown_data()` to `data.py`
- [ ] Add `get_streak_data()` to `data.py`
- [ ] Add `get_rolling_accuracy()` to `data.py`
- [ ] Add `get_confidence_calibration()` to `data.py`
- [ ] Add `get_sentiment_performance()` to `data.py`
- [ ] Add `get_periodic_performance()` to `data.py`
- [ ] Add `get_performance_summary()` to `data.py`
- [ ] Create `shit_tests/shitty_ui/test_performance_data.py`
- [ ] Write and pass all 28 data layer tests
- [ ] Run `ruff check .` and `ruff format .`

### Phase C: Performance Page Layout (Day 2-3)

- [ ] Create `shitty_ui/pages/performance.py`
- [ ] Register page with `dash.register_page()`
- [ ] Implement layout with all 7 sections:
  - [ ] Summary metrics row
  - [ ] Equity curve chart section
  - [ ] Drawdown chart section
  - [ ] Rolling accuracy + streak display row
  - [ ] Confidence calibration + sentiment breakdown row
  - [ ] Periodic summary table section
- [ ] Implement time period selector (30D, 90D, 180D, 1Y, All)
- [ ] Create `shit_tests/shitty_ui/test_performance_layout.py`
- [ ] Write and pass all 15 layout tests

### Phase D: Callbacks (Day 3)

- [ ] Implement `update_period_selection` callback
- [ ] Implement `update_performance_page` callback
- [ ] Implement `update_periodic_table` callback
- [ ] Implement all private builder functions:
  - [ ] `_build_summary_metrics()`
  - [ ] `_build_equity_curve()`
  - [ ] `_build_drawdown_chart()`
  - [ ] `_build_rolling_accuracy_chart()`
  - [ ] `_build_streak_display()`
  - [ ] `_build_calibration_chart()`
  - [ ] `_build_sentiment_display()`
- [ ] Verify callbacks fire correctly in browser

### Phase E: Polish and QA (Day 3-4)

- [ ] Test navigation between Home and Performance pages
- [ ] Test time period filter updates all charts
- [ ] Test periodic table switches between monthly and weekly
- [ ] Test with empty/no data (graceful degradation)
- [ ] Test with real production data (read-only)
- [ ] Check chart hover tooltips are correct
- [ ] Check responsive layout on narrow viewport (< 768px)
- [ ] Run full test suite: `pytest -v`
- [ ] Run `ruff check .` and `ruff format .`
- [ ] Update CHANGELOG.md

---

## 8. Definition of Done

- [ ] Performance page accessible at `/performance`
- [ ] Navigation bar visible on both Home and Performance pages
- [ ] All 7 chart/component sections render correctly
- [ ] Time period filter updates all components
- [ ] Monthly/weekly toggle works on periodic table
- [ ] Empty data states show helpful messages (not crashes)
- [ ] All 43 new tests pass
- [ ] All existing tests still pass
- [ ] No console errors in browser dev tools
- [ ] Code passes `ruff check .` and `ruff format .`
- [ ] CHANGELOG.md updated with "Added - Performance page" entry
- [ ] Tested at desktop (1400px) and mobile (375px) viewport widths

---

## Appendix: Refactoring `layout.py`

To make the existing dashboard work as a page in the multi-page app, you need to extract the main content from `create_app()` into a separate function. Here is the minimal refactor:

### Before (current `layout.py`):

```python
def create_app() -> Dash:
    app = Dash(...)
    app.layout = html.Div([
        dcc.Interval(...),
        dcc.Store(...),
        create_header(),
        html.Div([
            # ... all the main content ...
        ], style={"padding": "20px", ...}),
    ], style={...})
    return app
```

### After (refactored `layout.py`):

```python
def create_home_content():
    """Return the main dashboard content for the home page.

    This is the inner content only - no header, footer, or outer wrapper.
    Those are now handled by app.py in the multi-page layout.
    """
    return html.Div([
        # Store for selected asset
        dcc.Store(id="selected-asset", data=None),

        # Performance Metrics Row
        html.Div(id="performance-metrics", className="mb-4"),

        # Two column layout: Charts + Asset Drilldown
        dbc.Row([
            # Left column: Performance charts
            dbc.Col([
                # ... existing chart cards ...
            ], md=7),

            # Right column: Recent Signals + Asset Drilldown
            dbc.Col([
                # ... existing signal + drilldown cards ...
            ], md=5),
        ]),

        # Collapsible Full Data Table
        dbc.Card([
            # ... existing table card ...
        ], className="mt-4", style={"backgroundColor": COLORS["secondary"]}),

    ], style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"})


def create_app() -> Dash:
    """Create the Dash app - LEGACY single-page mode.

    Kept for backward compatibility. The multi-page app.py is the
    preferred entry point.
    """
    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
        ],
        suppress_callback_exceptions=True
    )

    app.title = "Shitpost Alpha - Prediction Performance Dashboard"

    app.layout = html.Div([
        dcc.Interval(
            id="refresh-interval",
            interval=5*60*1000,
            n_intervals=0,
        ),
        create_header(),
        create_home_content(),
        create_footer(),
    ], style={
        "backgroundColor": COLORS["primary"],
        "minHeight": "100vh",
        "color": COLORS["text"],
        "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    })

    return app
```

This keeps backward compatibility: the old `app.py` entry point still works, while the new multi-page `app.py` uses `create_home_content()` for the home page.

---

## Appendix: SQL Queries Quick Reference

All queries target the `prediction_outcomes` table as the primary data source, occasionally joining `predictions` and `truth_social_shitposts`.

| Function | Primary Table | Joins | Key Columns Used |
|----------|--------------|-------|-----------------|
| `get_equity_curve_data` | `prediction_outcomes` | None | `prediction_date`, `pnl_t7`, `correct_t7` |
| `get_drawdown_data` | (Python calc) | None | Uses equity curve output |
| `get_streak_data` | `prediction_outcomes` | None | `prediction_date`, `correct_t7` |
| `get_rolling_accuracy` | `prediction_outcomes` | None | `prediction_date`, `correct_t7` |
| `get_confidence_calibration` | `prediction_outcomes` | None | `prediction_confidence`, `correct_t7` |
| `get_sentiment_performance` | `prediction_outcomes` | None | `prediction_sentiment`, `correct_t7`, `pnl_t7` |
| `get_periodic_performance` | `prediction_outcomes` | None | `prediction_date`, `correct_t7`, `pnl_t7` |
| `get_performance_summary` | `prediction_outcomes` | None | All outcome columns |

No new indexes are required. The existing indexes on `prediction_outcomes(prediction_date)` and `prediction_outcomes(correct_t7)` are sufficient for these queries.
