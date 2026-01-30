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
from dash import html, dcc, dash_table, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path for data imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data import (
    get_equity_curve_data,
    get_drawdown_data,
    get_win_loss_streaks,
    get_rolling_accuracy,
    get_confidence_calibration,
    get_sentiment_performance,
    get_periodic_performance,
    get_performance_summary,
)
from components.common import (
    create_metric_card,
    create_section_card,
    create_empty_chart_figure,
)

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

layout = html.Div(
    [
        # Hidden store for time period filter
        dcc.Store(id="perf-period-days", data=None),
        # Page title
        html.Div(
            [
                html.H2(
                    [
                        html.I(className="fas fa-chart-line me-2"),
                        "Performance Analysis",
                    ],
                    style={"margin": 0},
                ),
                html.P(
                    "Detailed backtesting results assuming $1,000 per prediction",
                    style={"color": COLORS["text_muted"], "margin": "5px 0 0 0"},
                ),
            ],
            className="mb-4",
        ),
        # Time period selector
        html.Div(
            [
                html.Span(
                    "Time Period: ",
                    style={"color": COLORS["text_muted"], "marginRight": "10px"},
                ),
                dbc.ButtonGroup(
                    [
                        dbc.Button(
                            "30D",
                            id="perf-period-30d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "90D",
                            id="perf-period-90d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "180D",
                            id="perf-period-180d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "1Y",
                            id="perf-period-365d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "All", id="perf-period-all", color="primary", size="sm"
                        ),  # Default
                    ],
                    size="sm",
                ),
            ],
            className="mb-4",
            style={"textAlign": "right"},
        ),
        # ---- ROW 1: Summary Metrics ----
        dcc.Loading(
            type="default",
            color=COLORS["accent"],
            children=html.Div(id="perf-summary-metrics", className="mb-4"),
        ),
        # ---- ROW 2: Equity Curve + Drawdown ----
        dbc.Row(
            [
                dbc.Col(
                    [
                        create_section_card(
                            title="Equity Curve (Cumulative P&L)",
                            icon="chart-area",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=dcc.Graph(
                                        id="equity-curve-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "350px"},
                                    ),
                                ),
                            ],
                        ),
                    ],
                    md=12,
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        create_section_card(
                            title="Drawdown Analysis",
                            icon="arrow-down",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=dcc.Graph(
                                        id="drawdown-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "250px"},
                                    ),
                                ),
                            ],
                        ),
                    ],
                    md=12,
                ),
            ]
        ),
        # ---- ROW 3: Rolling Accuracy + Streaks ----
        dbc.Row(
            [
                dbc.Col(
                    [
                        create_section_card(
                            title="Rolling 30-Day Accuracy",
                            icon="wave-square",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=dcc.Graph(
                                        id="rolling-accuracy-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "300px"},
                                    ),
                                ),
                            ],
                        ),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        create_section_card(
                            title="Win/Loss Streaks",
                            icon="fire",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=html.Div(id="streak-display"),
                                ),
                            ],
                        ),
                    ],
                    md=4,
                ),
            ]
        ),
        # ---- ROW 4: Confidence Calibration + Sentiment Breakdown ----
        dbc.Row(
            [
                dbc.Col(
                    [
                        create_section_card(
                            title="Confidence Calibration",
                            icon="crosshairs",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=dcc.Graph(
                                        id="calibration-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "350px"},
                                    ),
                                ),
                            ],
                        ),
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        create_section_card(
                            title="Performance by Sentiment",
                            icon="balance-scale",
                            children=[
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=html.Div(
                                        id="sentiment-performance-display"
                                    ),
                                ),
                            ],
                        ),
                    ],
                    md=6,
                ),
            ]
        ),
        # ---- ROW 5: Periodic Summary Table ----
        dbc.Row(
            [
                dbc.Col(
                    [
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
                                dcc.Loading(
                                    type="circle",
                                    color=COLORS["accent"],
                                    children=html.Div(id="periodic-table-container"),
                                ),
                            ],
                        ),
                    ],
                    md=12,
                ),
            ]
        ),
    ],
    style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
)


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------


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

    # Generate button styles
    button_keys = [
        "perf-period-30d",
        "perf-period-90d",
        "perf-period-180d",
        "perf-period-365d",
        "perf-period-all",
    ]
    styles = []
    for key in button_keys:
        if period_map[key] == selected_days:
            styles.extend(["primary", False])  # Active: solid blue
        else:
            styles.extend(["secondary", True])  # Inactive: outlined gray

    return [selected_days] + styles


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
    streak_display = _build_streak_display()

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
            style={
                "color": COLORS["text_muted"],
                "textAlign": "center",
                "padding": "20px",
            },
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
                "if": {"filter_query": "{total_pnl} > 0", "column_id": "total_pnl"},
                "color": COLORS["success"],
            },
            {
                "if": {"filter_query": "{total_pnl} < 0", "column_id": "total_pnl"},
                "color": COLORS["danger"],
            },
            {
                "if": {"filter_query": "{accuracy} >= 60", "column_id": "accuracy"},
                "color": COLORS["success"],
            },
            {
                "if": {"filter_query": "{accuracy} < 50", "column_id": "accuracy"},
                "color": COLORS["danger"],
            },
        ],
        page_size=12,
        sort_action="native",
    )


# --------------------------------------------------------------------------
# Private helper functions for building individual components
# --------------------------------------------------------------------------


def _build_summary_metrics(summary: dict) -> dbc.Row:
    """Build the top row of summary metric cards."""
    pnl_color = COLORS["success"] if summary["total_pnl"] >= 0 else COLORS["danger"]
    wr_color = (
        COLORS["success"]
        if summary["win_rate"] >= 55
        else COLORS["danger"]
        if summary["win_rate"] < 45
        else COLORS["warning"]
    )
    dd_color = (
        COLORS["danger"]
        if summary["max_drawdown"] < -500
        else COLORS["warning"]
        if summary["max_drawdown"] < 0
        else COLORS["success"]
    )

    pf_display = (
        str(summary["profit_factor"]) if summary["profit_factor"] != "Inf" else "Inf"
    )

    return dbc.Row(
        [
            dbc.Col(
                create_metric_card(
                    "Total Trades",
                    f"{summary['total_trades']:,}",
                    f"{summary['wins']}W / {summary['losses']}L",
                    "exchange-alt",
                    COLORS["accent"],
                ),
                xs=6,
                sm=6,
                md=3,
            ),
            dbc.Col(
                create_metric_card(
                    "Win Rate",
                    f"{summary['win_rate']:.1f}%",
                    "Target: >55%",
                    "bullseye",
                    wr_color,
                ),
                xs=6,
                sm=6,
                md=3,
            ),
            dbc.Col(
                create_metric_card(
                    "Total P&L",
                    f"${summary['total_pnl']:,.0f}",
                    f"Avg ${summary['avg_pnl_per_trade']:,.0f}/trade",
                    "dollar-sign",
                    pnl_color,
                ),
                xs=6,
                sm=6,
                md=3,
            ),
            dbc.Col(
                create_metric_card(
                    "Max Drawdown",
                    f"${summary['max_drawdown']:,.0f}",
                    f"Profit Factor: {pf_display}",
                    "arrow-down",
                    dd_color,
                ),
                xs=6,
                sm=6,
                md=3,
            ),
        ],
        className="g-3",
    )


def _build_equity_curve(days: int = None) -> go.Figure:
    """Build the equity curve chart."""
    df = get_equity_curve_data(days=days)

    if df.empty:
        return create_empty_chart_figure("No equity curve data available yet")

    fig = go.Figure()

    # Main equity line
    fig.add_trace(
        go.Scatter(
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
        )
    )

    # Zero line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color=COLORS["text_muted"],
        opacity=0.5,
    )

    # Add markers for wins (green) and losses (red)
    wins = df[df["correct_t7"] == True]  # noqa: E712
    losses = df[df["correct_t7"] == False]  # noqa: E712

    if not wins.empty:
        fig.add_trace(
            go.Scatter(
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
            )
        )

    if not losses.empty:
        fig.add_trace(
            go.Scatter(
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
            )
        )

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

    fig.add_trace(
        go.Scatter(
            x=df["prediction_date"],
            y=df["drawdown"],
            mode="lines",
            name="Drawdown",
            line=dict(color=COLORS["danger"], width=1.5),
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.15)",
            hovertemplate=(
                "<b>Date:</b> %{x}<br><b>Drawdown:</b> $%{y:,.0f}<br><extra></extra>"
            ),
        )
    )

    # Highlight max drawdown point
    if not df.empty and "drawdown" in df.columns:
        max_dd_idx = df["drawdown"].idxmin()
        max_dd_row = df.loc[max_dd_idx]
        fig.add_trace(
            go.Scatter(
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
            )
        )

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
            "Need at least 30 days of data for rolling accuracy"
        )

    fig = go.Figure()

    # Rolling accuracy line
    fig.add_trace(
        go.Scatter(
            x=df["prediction_date"],
            y=df["rolling_accuracy"],
            mode="lines",
            name="30-Day Rolling Accuracy",
            line=dict(color=COLORS["accent"], width=2),
            hovertemplate=(
                "<b>Date:</b> %{x}<br><b>Accuracy:</b> %{y:.1f}%<br><extra></extra>"
            ),
        )
    )

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

    y_min = max(0, df["rolling_accuracy"].min() - 10) if not df.empty else 0
    y_max = min(100, df["rolling_accuracy"].max() + 10) if not df.empty else 100

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        height=300,
        yaxis_title="Accuracy %",
        yaxis_range=[y_min, y_max],
        xaxis_title="",
        showlegend=False,
    )

    return fig


def _build_streak_display() -> html.Div:
    """Build the win/loss streak display panel."""
    data = get_win_loss_streaks()

    if data["current_streak"] == 0 and data["max_win_streak"] == 0:
        return html.P(
            "No streak data available.",
            style={
                "color": COLORS["text_muted"],
                "textAlign": "center",
                "padding": "20px",
            },
        )

    # Determine current streak type and styling
    if data["current_streak"] > 0:
        current_color = COLORS["success"]
        current_icon = "fire"
        streak_text = f"{data['current_streak']} WINS"
    elif data["current_streak"] < 0:
        current_color = COLORS["danger"]
        current_icon = "snowflake"
        streak_text = f"{abs(data['current_streak'])} LOSSES"
    else:
        current_color = COLORS["text_muted"]
        current_icon = "minus"
        streak_text = "No streak"

    return html.Div(
        [
            # Current streak - large display
            html.Div(
                [
                    html.H5(
                        "Current Streak",
                        style={"color": COLORS["text_muted"], "marginBottom": "10px"},
                    ),
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{current_icon}",
                                style={
                                    "fontSize": "2rem",
                                    "color": current_color,
                                    "marginRight": "10px",
                                },
                            ),
                            html.Span(
                                streak_text,
                                style={
                                    "fontSize": "1.5rem",
                                    "fontWeight": "bold",
                                    "color": current_color,
                                },
                            ),
                        ],
                        className="d-flex align-items-center justify-content-center mb-4",
                    ),
                ],
                style={"textAlign": "center"},
            ),
            # Max streaks
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-trophy me-2",
                                        style={"color": COLORS["success"]},
                                    ),
                                    html.Span(
                                        "Best Win Streak",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                ]
                            ),
                            html.H4(
                                f"{data['max_win_streak']}",
                                style={"color": COLORS["success"], "margin": "5px 0"},
                            ),
                        ],
                        style={
                            "textAlign": "center",
                            "padding": "15px",
                            "borderRight": f"1px solid {COLORS['border']}",
                            "flex": 1,
                        },
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-skull-crossbones me-2",
                                        style={"color": COLORS["danger"]},
                                    ),
                                    html.Span(
                                        "Worst Loss Streak",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                ]
                            ),
                            html.H4(
                                f"{data['max_loss_streak']}",
                                style={"color": COLORS["danger"], "margin": "5px 0"},
                            ),
                        ],
                        style={
                            "textAlign": "center",
                            "padding": "15px",
                            "flex": 1,
                        },
                    ),
                ],
                style={"display": "flex"},
            ),
        ]
    )


def _build_calibration_chart() -> go.Figure:
    """Build the confidence calibration chart."""
    df = get_confidence_calibration(buckets=10)

    if df.empty:
        return create_empty_chart_figure("Not enough data for confidence calibration")

    fig = go.Figure()

    # Perfect calibration line (diagonal)
    fig.add_trace(
        go.Scatter(
            x=[0, 100],
            y=[0, 100],
            mode="lines",
            name="Perfect Calibration",
            line=dict(color=COLORS["text_muted"], width=1, dash="dash"),
            hoverinfo="skip",
        )
    )

    # Actual calibration bars
    fig.add_trace(
        go.Bar(
            x=df["bucket_label"],
            y=df["actual_accuracy"],
            name="Actual Accuracy",
            marker_color=COLORS["accent"],
            text=df["actual_accuracy"].apply(lambda x: f"{x:.0f}%"),
            textposition="outside",
            hovertemplate=(
                "<b>Confidence Bucket:</b> %{x}<br>"
                "<b>Actual Accuracy:</b> %{y:.1f}%<br>"
                "<b>Predictions:</b> %{customdata}<br>"
                "<extra></extra>"
            ),
            customdata=df["total"],
        )
    )

    # Predicted confidence markers
    fig.add_trace(
        go.Scatter(
            x=df["bucket_label"],
            y=df["predicted_confidence"],
            mode="markers",
            name="Predicted Confidence",
            marker=dict(
                color=COLORS["warning"],
                size=10,
                symbol="diamond",
                line=dict(width=1, color=COLORS["text"]),
            ),
            hovertemplate=("<b>Predicted:</b> %{y:.1f}%<br><extra></extra>"),
        )
    )

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
            style={
                "color": COLORS["text_muted"],
                "textAlign": "center",
                "padding": "20px",
            },
        )

    sentiment_configs = {
        "bullish": {"icon": "arrow-up", "color": COLORS["success"], "label": "BULLISH"},
        "bearish": {
            "icon": "arrow-down",
            "color": COLORS["danger"],
            "label": "BEARISH",
        },
        "neutral": {"icon": "minus", "color": COLORS["text_muted"], "label": "NEUTRAL"},
    }

    cards = []
    for _, row in df.iterrows():
        sentiment = row["prediction_sentiment"].lower()
        config = sentiment_configs.get(sentiment, sentiment_configs["neutral"])

        accuracy = row.get("accuracy", 0)
        accuracy_color = COLORS["success"] if accuracy >= 55 else COLORS["danger"]

        cards.append(
            html.Div(
                [
                    # Header
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{config['icon']}",
                                style={"color": config["color"], "fontSize": "1.2rem"},
                            ),
                            html.Span(
                                f" {config['label']}",
                                style={
                                    "color": config["color"],
                                    "fontWeight": "bold",
                                    "fontSize": "1rem",
                                },
                            ),
                            html.Span(
                                f" ({row['total']} trades)",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                },
                            ),
                        ],
                        className="mb-2",
                    ),
                    # Stats grid
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        "Accuracy",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                    html.Div(
                                        f"{accuracy:.1f}%",
                                        style={
                                            "color": accuracy_color,
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={"flex": 1, "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Avg Return",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                    html.Div(
                                        f"{row['avg_return']:+.2f}%",
                                        style={
                                            "color": COLORS["success"]
                                            if row["avg_return"] > 0
                                            else COLORS["danger"],
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={"flex": 1, "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Total P&L",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                    html.Div(
                                        f"${row['total_pnl']:,.0f}",
                                        style={
                                            "color": COLORS["success"]
                                            if row["total_pnl"] > 0
                                            else COLORS["danger"],
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={"flex": 1, "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "W/L",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                    html.Div(
                                        f"{row['correct']}/{row['incorrect']}",
                                        style={"fontWeight": "bold"},
                                    ),
                                ],
                                style={"flex": 1, "textAlign": "center"},
                            ),
                        ],
                        style={"display": "flex"},
                    ),
                ],
                style={
                    "padding": "15px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            )
        )

    return html.Div(cards)
