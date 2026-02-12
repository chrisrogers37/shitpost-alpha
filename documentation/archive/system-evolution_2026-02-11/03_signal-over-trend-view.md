# Phase 03: Signal-Over-Trend Dashboard View

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat(ui): add signal-over-trend chart view with price overlays` |
| **Risk Level** | Low |
| **Estimated Effort** | Medium (2-3 days) |
| **Files Created** | `shitty_ui/pages/trends.py`, `shitty_ui/components/charts.py`, `shit_tests/shitty_ui/test_trends.py`, `shit_tests/shitty_ui/test_charts.py` |
| **Files Modified** | `shitty_ui/data.py`, `shitty_ui/layout.py`, `shitty_ui/pages/assets.py`, `shitty_ui/components/header.py`, `shitty_ui/constants.py`, `CHANGELOG.md` |
| **Files Deleted** | None |

---

## Context: Why This Matters

Currently, the asset page at `/assets/{symbol}` has a candlestick chart with basic prediction markers and a separate prediction timeline below it. However:

1. **No combined query** -- The price chart callback queries prices and predictions separately, then matches them by date. It does not pull confidence, thesis, or timeframe window data.
2. **Marker design is basic** -- Markers use correctness (green/red/yellow) as color, not sentiment. Marker size is fixed at 12px. Tooltips show only date, sentiment, and result -- no thesis or confidence.
3. **No timeframe visualization** -- The t1/t3/t7/t30 evaluation windows are not shown. Users cannot see when a prediction "expires."
4. **No standalone route** -- There is no `/trends` page for viewing signals overlaid on price charts with full controls.

This phase delivers a visual proof layer: "here is what the model predicted, here is what the market did." This is the core value prop for any user evaluating system quality.

---

## Dependencies

| Dependency | Status | Required? |
|---|---|---|
| Phase 01: Market Data Pipeline | Must be running (price data in `market_prices` table) | **Required** |
| Phase 02: Source-Agnostic Data Model | Nice-to-have (field names may change) | Optional |

---

## Detailed Implementation Plan

### Step 1: Add New Constants to `constants.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/constants.py`

After the existing `COLORS` dict (currently ends at line 15), add:

```python
# Sentiment-specific color mapping for chart overlays
SENTIMENT_COLORS = {
    "bullish": "#10b981",   # Emerald 500 (same as COLORS["success"])
    "bearish": "#ef4444",   # Red 500 (same as COLORS["danger"])
    "neutral": "#94a3b8",   # Slate 400 (same as COLORS["text_muted"])
}

# Marker configuration for signal overlays
MARKER_CONFIG = {
    "min_size": 8,          # Minimum marker size (pixels)
    "max_size": 22,         # Maximum marker size (pixels)
    "opacity": 0.85,        # Default marker opacity
    "border_width": 1.5,    # Marker border width
    "symbols": {
        "bullish": "triangle-up",
        "bearish": "triangle-down",
        "neutral": "circle",
    },
}

# Timeframe window colors (for shaded regions)
TIMEFRAME_COLORS = {
    "t1": "rgba(59, 130, 246, 0.06)",   # Blue, very light
    "t3": "rgba(59, 130, 246, 0.04)",
    "t7": "rgba(245, 158, 11, 0.04)",   # Amber, very light
    "t30": "rgba(245, 158, 11, 0.02)",
}
```

---

### Step 2: Add New Data Query Functions to `data.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

Add two new functions at the end of the file (after `get_sentiment_accuracy` which ends at line 1907):

#### Function 2a: `get_price_with_signals`

Core combined query that returns price data and signal data for a symbol within a date range.

```python
def get_price_with_signals(
    symbol: str,
    days: int = 90,
) -> Dict[str, pd.DataFrame]:
    """
    Get combined price history and prediction signals for a symbol.

    Returns two DataFrames in a dict:
    - 'prices': OHLCV data from market_prices table
    - 'signals': Prediction signals with sentiment, confidence, thesis, outcomes

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        days: Number of days of history

    Returns:
        Dict with 'prices' and 'signals' DataFrames.
        Both may be empty if no data exists.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    price_query = text("""
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume,
            adjusted_close
        FROM market_prices
        WHERE symbol = :symbol
            AND date >= :start_date
        ORDER BY date ASC
    """)

    signal_query = text("""
        SELECT
            po.prediction_date,
            tss.timestamp AS post_timestamp,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.return_t30,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.correct_t30,
            po.pnl_t7,
            po.is_complete,
            p.thesis,
            p.assets,
            tss.text AS post_text
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :symbol
            AND po.prediction_date >= :start_date
        ORDER BY po.prediction_date ASC
    """)

    params = {"symbol": symbol.upper(), "start_date": start_date}

    result = {"prices": pd.DataFrame(), "signals": pd.DataFrame()}

    try:
        rows, columns = execute_query(price_query, params)
        price_df = pd.DataFrame(rows, columns=columns)
        if not price_df.empty:
            price_df["date"] = pd.to_datetime(price_df["date"])
        result["prices"] = price_df
    except Exception as e:
        logger.error(f"Error loading prices for {symbol}: {e}")

    try:
        rows, columns = execute_query(signal_query, params)
        signal_df = pd.DataFrame(rows, columns=columns)
        if not signal_df.empty:
            signal_df["prediction_date"] = pd.to_datetime(signal_df["prediction_date"])
            signal_df["post_timestamp"] = pd.to_datetime(signal_df["post_timestamp"])
        result["signals"] = signal_df
    except Exception as e:
        logger.error(f"Error loading signals for {symbol}: {e}")

    return result
```

#### Function 2b: `get_multi_asset_signals`

For cross-asset signal overview:

```python
def get_multi_asset_signals(
    days: int = 90,
    limit: int = 200,
) -> pd.DataFrame:
    """
    Get recent prediction signals across all assets for the trend overview.

    Args:
        days: Number of days to look back
        limit: Maximum signals to return

    Returns:
        DataFrame with signal data, or empty DataFrame on error.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    query = text("""
        SELECT
            po.symbol,
            po.prediction_date,
            tss.timestamp AS post_timestamp,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.return_t7,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete,
            p.thesis,
            tss.text AS post_text
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.prediction_date >= :start_date
        ORDER BY po.prediction_date DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, {"start_date": start_date, "limit": limit})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["prediction_date"] = pd.to_datetime(df["prediction_date"])
        return df
    except Exception as e:
        logger.error(f"Error loading multi-asset signals: {e}")
        return pd.DataFrame()
```

---

### Step 3: Create New Chart Component

**File to create**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/charts.py`

A reusable Plotly figure builder that takes price data and signal data and returns a `go.Figure` with:
- Candlestick trace for price
- Scatter traces for signal markers (color = sentiment, size = confidence, shape = sentiment direction)
- Optional shaded rectangles for prediction timeframe windows
- Rich tooltips with thesis, confidence, outcome

```python
"""Reusable Plotly chart builders for the Shitty UI dashboard."""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

from constants import COLORS, SENTIMENT_COLORS, MARKER_CONFIG, TIMEFRAME_COLORS


def build_signal_over_trend_chart(
    prices_df: pd.DataFrame,
    signals_df: pd.DataFrame,
    symbol: str = "",
    show_timeframe_windows: bool = False,
    chart_height: int = 500,
) -> go.Figure:
    """
    Build a candlestick chart with prediction signal markers overlaid.

    Args:
        prices_df: DataFrame with columns: date, open, high, low, close, volume
        signals_df: DataFrame with columns: prediction_date, prediction_sentiment,
                    prediction_confidence, thesis, correct_t7, return_t7, pnl_t7,
                    post_text, price_at_prediction
        symbol: Ticker symbol for chart title
        show_timeframe_windows: If True, draw shaded regions for t7 windows
        chart_height: Height of the chart in pixels

    Returns:
        go.Figure ready to be rendered by dcc.Graph
    """
    fig = go.Figure()

    # --- Trace 1: Candlestick ---
    if not prices_df.empty:
        fig.add_trace(
            go.Candlestick(
                x=prices_df["date"],
                open=prices_df["open"],
                high=prices_df["high"],
                low=prices_df["low"],
                close=prices_df["close"],
                name=symbol or "Price",
                increasing_line_color=COLORS["success"],
                decreasing_line_color=COLORS["danger"],
                showlegend=False,
            )
        )

    # --- Trace 2: Signal Markers ---
    if not signals_df.empty and not prices_df.empty:
        for _, signal in signals_df.iterrows():
            pred_date = signal["prediction_date"]
            sentiment = (signal.get("prediction_sentiment") or "neutral").lower()
            confidence = signal.get("prediction_confidence") or 0.5
            thesis = signal.get("thesis") or ""
            correct_t7 = signal.get("correct_t7")
            return_t7 = signal.get("return_t7")
            pnl_t7 = signal.get("pnl_t7")
            post_text = signal.get("post_text") or ""

            # Find the price at this date for y-placement
            price_row = prices_df[prices_df["date"].dt.date == pred_date.date()]
            if price_row.empty:
                continue

            y_val = float(price_row.iloc[0]["high"]) * 1.03

            # Color from sentiment
            marker_color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])

            # Size from confidence (scale min_size to max_size)
            size_range = MARKER_CONFIG["max_size"] - MARKER_CONFIG["min_size"]
            marker_size = MARKER_CONFIG["min_size"] + (confidence * size_range)

            # Shape from sentiment
            marker_symbol = MARKER_CONFIG["symbols"].get(
                sentiment, MARKER_CONFIG["symbols"]["neutral"]
            )

            # Outcome text for tooltip
            if correct_t7 is True:
                outcome_text = "CORRECT"
            elif correct_t7 is False:
                outcome_text = "INCORRECT"
            else:
                outcome_text = "PENDING"

            # Build hover text
            thesis_preview = (thesis[:100] + "...") if len(thesis) > 100 else thesis
            post_preview = (post_text[:80] + "...") if len(post_text) > 80 else post_text

            hover_parts = [
                f"<b>{pred_date.strftime('%Y-%m-%d')}</b>",
                f"Sentiment: <b>{sentiment.upper()}</b>",
                f"Confidence: <b>{confidence:.0%}</b>",
                f"Outcome: <b>{outcome_text}</b>",
            ]
            if return_t7 is not None:
                hover_parts.append(f"7d Return: <b>{return_t7:+.2f}%</b>")
            if pnl_t7 is not None:
                hover_parts.append(f"P&L: <b>${pnl_t7:+,.0f}</b>")
            if thesis_preview:
                hover_parts.append(f"<br><i>{thesis_preview}</i>")

            hover_text = "<br>".join(hover_parts)

            fig.add_trace(
                go.Scatter(
                    x=[pred_date],
                    y=[y_val],
                    mode="markers",
                    marker=dict(
                        size=marker_size,
                        color=marker_color,
                        symbol=marker_symbol,
                        opacity=MARKER_CONFIG["opacity"],
                        line=dict(
                            width=MARKER_CONFIG["border_width"],
                            color=COLORS["text"],
                        ),
                    ),
                    hovertemplate=hover_text + "<extra></extra>",
                    showlegend=False,
                    name=f"{sentiment} signal",
                )
            )

            # --- Optional: Timeframe windows ---
            if show_timeframe_windows and not price_row.empty:
                _add_timeframe_window(fig, pred_date, y_val)

    # --- Layout ---
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(
            gridcolor=COLORS["border"],
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            gridcolor=COLORS["border"],
            title="Price ($)",
        ),
        height=chart_height,
        showlegend=False,
        hovermode="closest",
    )

    # Add a custom legend for sentiment markers
    _add_sentiment_legend(fig)

    return fig


def _add_timeframe_window(
    fig: go.Figure,
    pred_date: pd.Timestamp,
    y_val: float,
) -> None:
    """Add a shaded rectangle for the 7-day evaluation window."""
    t7_end = pred_date + timedelta(days=7)
    fig.add_vrect(
        x0=pred_date,
        x1=t7_end,
        fillcolor=TIMEFRAME_COLORS["t7"],
        layer="below",
        line_width=0,
    )


def _add_sentiment_legend(fig: go.Figure) -> None:
    """Add invisible traces to serve as a sentiment color legend."""
    for sentiment, color in SENTIMENT_COLORS.items():
        symbol = MARKER_CONFIG["symbols"][sentiment]
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=color, symbol=symbol),
                name=sentiment.capitalize(),
                showlegend=True,
            )
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )


def build_empty_signal_chart(message: str = "No data available") -> go.Figure:
    """Build an empty chart with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=14),
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=400,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig
```

---

### Step 4: Create Standalone `/trends` Page

**File to create**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/trends.py`

A new page at route `/trends` with:
- An asset selector dropdown
- Time range selector (30D, 90D, 180D, 1Y)
- Toggle for timeframe window overlays
- The signal-over-trend chart from Step 3
- A summary panel below the chart showing signal statistics

```python
"""Signal-over-trend page layout and callbacks for /trends route."""

import traceback

from dash import Dash, html, dcc, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import create_error_card
from components.charts import build_signal_over_trend_chart, build_empty_signal_chart
from data import get_price_with_signals, get_active_assets_from_db


def create_trends_page() -> html.Div:
    """Create the /trends page layout."""
    return html.Div(
        [
            # Page header
            html.Div(
                [
                    html.H2(
                        [
                            html.I(className="fas fa-chart-area me-2"),
                            "Signal Over Trend",
                        ],
                        style={"margin": 0, "fontWeight": "bold"},
                    ),
                    html.P(
                        "Prediction signals overlaid on market price charts",
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            # Controls row
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            # Asset selector
                            dbc.Col(
                                [
                                    html.Label(
                                        "Asset",
                                        className="small",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                    dcc.Dropdown(
                                        id="trends-asset-selector",
                                        options=[],
                                        placeholder="Select an asset...",
                                        style={"fontSize": "0.9rem"},
                                    ),
                                ],
                                xs=12, sm=6, md=4,
                            ),
                            # Time range buttons
                            dbc.Col(
                                [
                                    html.Label(
                                        "Time Range",
                                        className="small",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                    html.Div(
                                        dbc.ButtonGroup(
                                            [
                                                dbc.Button("30D", id="trends-range-30d", color="secondary", outline=True, size="sm"),
                                                dbc.Button("90D", id="trends-range-90d", color="primary", size="sm"),
                                                dbc.Button("180D", id="trends-range-180d", color="secondary", outline=True, size="sm"),
                                                dbc.Button("1Y", id="trends-range-1y", color="secondary", outline=True, size="sm"),
                                            ],
                                            size="sm",
                                        ),
                                    ),
                                ],
                                xs=12, sm=6, md=4,
                            ),
                            # Timeframe window toggle
                            dbc.Col(
                                [
                                    html.Label(
                                        "Options",
                                        className="small",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                    dbc.Checklist(
                                        options=[{"label": " Show 7-day windows", "value": "show_windows"}],
                                        value=[],
                                        id="trends-options-checklist",
                                        switch=True,
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ],
                                xs=12, sm=6, md=4,
                            ),
                        ],
                        className="g-3",
                    ),
                ),
                style={
                    "backgroundColor": COLORS["secondary"],
                    "border": f"1px solid {COLORS['border']}",
                    "marginBottom": "20px",
                },
            ),
            # Chart card
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            html.I(className="fas fa-chart-area me-2"),
                            html.Span(id="trends-chart-title", children="Select an asset to view chart"),
                        ],
                        className="fw-bold",
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            type="circle",
                            color=COLORS["accent"],
                            children=dcc.Graph(
                                id="trends-signal-chart",
                                config={"displayModeBar": True, "displaylogo": False},
                            ),
                        ),
                    ),
                ],
                style={"backgroundColor": COLORS["secondary"]},
                className="mb-4",
            ),
            # Signal summary stats row
            dcc.Loading(
                type="default",
                color=COLORS["accent"],
                children=html.Div(id="trends-signal-summary", className="mb-4"),
            ),
        ],
        style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
    )


def register_trends_callbacks(app: Dash):
    """Register all /trends page callbacks."""

    @app.callback(
        Output("trends-asset-selector", "options"),
        [Input("url", "pathname")],
    )
    def populate_trends_assets(pathname):
        if pathname != "/trends":
            return no_update
        assets = get_active_assets_from_db()
        return [{"label": a, "value": a} for a in assets]

    @app.callback(
        [
            Output("trends-signal-chart", "figure"),
            Output("trends-chart-title", "children"),
            Output("trends-signal-summary", "children"),
        ],
        [
            Input("trends-asset-selector", "value"),
            Input("trends-range-30d", "n_clicks"),
            Input("trends-range-90d", "n_clicks"),
            Input("trends-range-180d", "n_clicks"),
            Input("trends-range-1y", "n_clicks"),
            Input("trends-options-checklist", "value"),
        ],
    )
    def update_trends_chart(symbol, n30, n90, n180, n1y, options):
        if not symbol:
            return (
                build_empty_signal_chart("Select an asset to view the chart"),
                "Select an asset to view chart",
                html.Div(),
            )

        ctx = callback_context
        days = 90
        if ctx.triggered:
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            if button_id == "trends-range-30d":
                days = 30
            elif button_id == "trends-range-90d":
                days = 90
            elif button_id == "trends-range-180d":
                days = 180
            elif button_id == "trends-range-1y":
                days = 365

        show_windows = "show_windows" in (options or [])

        try:
            data = get_price_with_signals(symbol, days=days)
            prices_df = data["prices"]
            signals_df = data["signals"]

            if prices_df.empty:
                return (
                    build_empty_signal_chart(f"No price data for {symbol}"),
                    f"{symbol} - No Price Data",
                    html.Div(),
                )

            fig = build_signal_over_trend_chart(
                prices_df=prices_df,
                signals_df=signals_df,
                symbol=symbol,
                show_timeframe_windows=show_windows,
                chart_height=500,
            )

            title = f"{symbol} Price with Prediction Signals"
            summary = _build_signal_summary(symbol, signals_df)

            return fig, title, summary

        except Exception as e:
            print(f"Error in trends chart: {traceback.format_exc()}")
            return (
                build_empty_signal_chart(f"Error: {str(e)[:60]}"),
                f"{symbol} - Error",
                create_error_card(f"Error loading data for {symbol}", str(e)),
            )

    @app.callback(
        [
            Output("trends-range-30d", "color"),
            Output("trends-range-30d", "outline"),
            Output("trends-range-90d", "color"),
            Output("trends-range-90d", "outline"),
            Output("trends-range-180d", "color"),
            Output("trends-range-180d", "outline"),
            Output("trends-range-1y", "color"),
            Output("trends-range-1y", "outline"),
        ],
        [
            Input("trends-range-30d", "n_clicks"),
            Input("trends-range-90d", "n_clicks"),
            Input("trends-range-180d", "n_clicks"),
            Input("trends-range-1y", "n_clicks"),
        ],
    )
    def update_trends_range_buttons(n30, n90, n180, n1y):
        ctx = callback_context
        if not ctx.triggered:
            return "secondary", True, "primary", False, "secondary", True, "secondary", True

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        styles = ["secondary", True, "secondary", True, "secondary", True, "secondary", True]
        if button_id == "trends-range-30d":
            styles[0:2] = ["primary", False]
        elif button_id == "trends-range-90d":
            styles[2:4] = ["primary", False]
        elif button_id == "trends-range-180d":
            styles[4:6] = ["primary", False]
        elif button_id == "trends-range-1y":
            styles[6:8] = ["primary", False]
        else:
            styles[2:4] = ["primary", False]
        return tuple(styles)


def _build_signal_summary(symbol: str, signals_df) -> html.Div:
    """Build a summary stats row for the signals shown on the chart."""
    if signals_df.empty:
        return html.Div(
            html.P(
                f"No prediction signals found for {symbol} in this period.",
                style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "15px"},
            )
        )

    total = len(signals_df)
    bullish = (signals_df["prediction_sentiment"].str.lower() == "bullish").sum()
    bearish = (signals_df["prediction_sentiment"].str.lower() == "bearish").sum()
    avg_conf = signals_df["prediction_confidence"].mean() if "prediction_confidence" in signals_df.columns else 0

    correct_col = signals_df.get("correct_t7")
    if correct_col is not None:
        evaluated = correct_col.notna().sum()
        correct = (correct_col == True).sum()  # noqa: E712
        accuracy = (correct / evaluated * 100) if evaluated > 0 else 0
    else:
        evaluated = 0
        correct = 0
        accuracy = 0

    return dbc.Row(
        [
            dbc.Col(_mini_stat("Total Signals", str(total), COLORS["accent"]), md=2, xs=4),
            dbc.Col(_mini_stat("Bullish", str(bullish), COLORS["success"]), md=2, xs=4),
            dbc.Col(_mini_stat("Bearish", str(bearish), COLORS["danger"]), md=2, xs=4),
            dbc.Col(_mini_stat("Avg Confidence", f"{avg_conf:.0%}", COLORS["warning"]), md=2, xs=4),
            dbc.Col(_mini_stat("Evaluated", str(evaluated), COLORS["text_muted"]), md=2, xs=4),
            dbc.Col(
                _mini_stat(
                    "Accuracy",
                    f"{accuracy:.0f}%",
                    COLORS["success"] if accuracy > 50 else COLORS["danger"],
                ),
                md=2, xs=4,
            ),
        ],
        className="g-2",
    )


def _mini_stat(label: str, value: str, color: str) -> html.Div:
    """Small stat display for the summary row."""
    return html.Div(
        [
            html.Div(value, style={"fontSize": "1.2rem", "fontWeight": "bold", "color": color}),
            html.Div(label, style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
        ],
        style={
            "textAlign": "center",
            "padding": "10px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "border": f"1px solid {COLORS['border']}",
        },
    )
```

---

### Step 5: Enhance the Existing Asset Page Chart

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/assets.py`

Replace the `update_asset_price_chart` callback (lines 445-577) to use the new chart component.

**Add new imports at top of file (after line 8):**

```python
from components.charts import build_signal_over_trend_chart, build_empty_signal_chart
from data import get_price_with_signals
```

**Replace the `update_asset_price_chart` callback body (lines 455-577) with:**

```python
    @app.callback(
        Output("asset-price-chart", "figure"),
        [
            Input("asset-page-symbol", "data"),
            Input("asset-range-30d", "n_clicks"),
            Input("asset-range-90d", "n_clicks"),
            Input("asset-range-180d", "n_clicks"),
            Input("asset-range-1y", "n_clicks"),
        ],
    )
    def update_asset_price_chart(symbol, n30, n90, n180, n1y):
        """Update the price chart with prediction signal overlays."""
        if not symbol:
            return build_empty_signal_chart("No asset selected")

        ctx = callback_context
        days = 90
        if ctx.triggered:
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            if button_id == "asset-range-30d":
                days = 30
            elif button_id == "asset-range-90d":
                days = 90
            elif button_id == "asset-range-180d":
                days = 180
            elif button_id == "asset-range-1y":
                days = 365

        try:
            data = get_price_with_signals(symbol, days=days)

            if data["prices"].empty:
                return build_empty_signal_chart(f"No price data available for {symbol}")

            return build_signal_over_trend_chart(
                prices_df=data["prices"],
                signals_df=data["signals"],
                symbol=symbol,
                show_timeframe_windows=False,
                chart_height=400,
            )

        except Exception as e:
            print(f"Error loading price chart for {symbol}: {traceback.format_exc()}")
            return build_empty_signal_chart(f"Error: {str(e)[:50]}")
```

**Note:** Do NOT remove `get_asset_price_history` or `get_asset_predictions` imports -- they are still used by other callbacks on the asset page.

---

### Step 6: Register the New Route and Callbacks

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py`

1. **Add imports** (after line 37):
```python
from pages.trends import create_trends_page, register_trends_callbacks
```

2. **Add route** in `route_page` callback (after line 283, before the dashboard default return):
```python
        if pathname == "/trends":
            return create_trends_page()
```

3. **Register callbacks** in `register_callbacks` function (after line 292):
```python
    register_trends_callbacks(app)
```

---

### Step 7: Add Navigation Link

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/header.py`

Add a "Trends" link to the navigation bar. Currently there are three links: Dashboard, Signals, Performance (lines 49-69). Add after "Signals" (after line 61):

```python
                            dcc.Link(
                                [
                                    html.I(className="fas fa-chart-area me-1"),
                                    "Trends",
                                ],
                                href="/trends",
                                className="nav-link-custom",
                            ),
```

---

## Test Plan

### New Test File: `shit_tests/shitty_ui/test_trends.py`

#### Data Layer Tests (additions to `test_data.py`)

```
TestGetPriceWithSignals:
    test_returns_dict_with_prices_and_signals_keys
    test_prices_df_has_expected_columns
    test_signals_df_has_expected_columns
    test_handles_empty_prices
    test_handles_empty_signals
    test_handles_both_empty
    test_handles_database_error_gracefully
    test_date_columns_are_datetime_type
    test_respects_days_parameter

TestGetMultiAssetSignals:
    test_returns_dataframe
    test_handles_empty_result
    test_handles_database_error
    test_respects_limit_parameter
```

#### Chart Component Tests (`test_charts.py`)

```
TestBuildSignalOverTrendChart:
    test_returns_figure_with_valid_data
    test_returns_figure_with_empty_signals
    test_returns_figure_with_empty_prices
    test_marker_color_matches_sentiment
    test_marker_size_scales_with_confidence
    test_timeframe_windows_added_when_enabled
    test_timeframe_windows_not_added_when_disabled
    test_hover_template_contains_thesis
    test_hover_template_contains_confidence
    test_sentiment_legend_traces_added

TestBuildEmptySignalChart:
    test_returns_figure
    test_contains_annotation_message
```

#### Page Layout Tests (`test_trends.py`)

```
TestCreateTrendsPage:
    test_returns_html_div
    test_contains_asset_dropdown
    test_contains_range_buttons
    test_contains_chart_graph
    test_contains_options_checklist

TestRegisterTrendsCallbacks:
    test_callbacks_registered_without_error
```

**Total new tests: ~25**

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Signal-Over-Trend Chart View** - New `/trends` page showing prediction signals overlaid on candlestick price charts
  - Sentiment-colored markers (green=bullish, red=bearish, gray=neutral)
  - Marker size scales with prediction confidence
  - Rich tooltips with thesis text, confidence score, and outcome
  - Optional 7-day evaluation window overlays
  - Asset selector and time range controls (30D/90D/180D/1Y)
  - Signal summary statistics panel below chart
- **Enhanced Asset Page Chart** - Existing asset page now uses the improved signal overlay component
- **New navigation link** - "Trends" added to top navigation bar
```

---

## Stress Testing & Edge Cases

| Scenario | Expected Behavior |
|---|---|
| **No market price data for symbol** | Show "No price data for {symbol}" empty chart |
| **No predictions for symbol** | Show candlestick chart only, no markers. Summary says "No prediction signals found" |
| **Many overlapping signals (10+ on same day)** | Markers stack vertically. `hovermode="closest"` ensures individual selection |
| **Signal date on weekend/holiday** | Marker is skipped (no matching price date) |
| **Confidence is None** | Default to 0.5, marker rendered at medium size |
| **Thesis is None or empty** | Tooltip omits thesis line |
| **Database connection error** | Error card shown, chart shows error message |
| **Very long date range (1Y)** | ~365 trading days + ~100 signals. Plotly handles this fine |
| **Prediction outcome not yet evaluated** | Outcome shown as "PENDING" in tooltip |

---

## Verification Checklist

- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` passes with all new tests
- [ ] `python3 -m ruff check shitty_ui/` returns no errors
- [ ] `python3 -m ruff format shitty_ui/` applies no changes
- [ ] Navigate to `/trends` in browser -- page loads without errors
- [ ] Select an asset with known price + signal data -- chart renders with markers
- [ ] Hover over a marker -- tooltip shows sentiment, confidence, thesis, outcome
- [ ] Click 30D/90D/180D/1Y buttons -- chart re-renders with correct date range
- [ ] Toggle "Show 7-day windows" -- shaded regions appear/disappear
- [ ] Navigate to `/assets/AAPL` -- enhanced chart shows signal overlays
- [ ] Test with a symbol that has no price data -- empty chart message shown
- [ ] Test with a symbol that has prices but no predictions -- candlestick only
- [ ] Console shows no JavaScript errors
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT add a new database table.** This feature reads from existing `market_prices`, `predictions`, `prediction_outcomes`, and `truth_social_shitposts` tables.

2. **Do NOT use `go.Candlestick` with `rangeslider=True`.** The rangeslider consumes too much vertical space. Keep `rangeslider=dict(visible=False)`.

3. **Do NOT create separate callbacks for each signal marker.** Build all markers in a single callback pass. One `go.Scatter` per signal is fine for up to ~200 signals.

4. **Do NOT add real-time WebSocket or live streaming.** The existing refresh interval is sufficient.

5. **Do NOT modify the database session management.** Continue using `execute_query()` from `data.py` with `SessionLocal()`.

6. **Do NOT add `@ttl_cache` to `get_price_with_signals`.** The function takes variable parameters, making the cache key matrix too large.

7. **Do NOT remove existing `get_asset_price_history` or `get_asset_predictions` functions.** They are still used by other callbacks.

8. **Do NOT use Plotly Express (`px`).** The codebase consistently uses `plotly.graph_objects` (`go`).

9. **Do NOT create a `__main__.py` for the trends page.** It is a Dash page, not a CLI module.

10. **Do NOT forget `suppress_callback_exceptions=True`.** It is already set in `create_app()` at line 67 of `layout.py` and covers dynamically rendered component IDs.
