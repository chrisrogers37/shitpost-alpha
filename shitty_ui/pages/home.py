"""
Home page - main dashboard.
Registered as the default '/' route in the multi-page app.

This page wraps the existing layout.py dashboard content.
"""

import dash
from dash import html, dcc, Input, Output, State, callback, callback_context
import dash_bootstrap_components as dbc
from datetime import datetime
import traceback
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data import (
    get_prediction_stats,
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
)
from components.common import create_metric_card, create_error_card
import plotly.graph_objects as go

# Register this module as the home page
dash.register_page(
    __name__,
    path="/",
    name="Dashboard",
    title="Shitpost Alpha - Dashboard",
)

# Color palette - matches layout.py
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


def create_empty_chart(message: str = "No data available"):
    """Create an empty chart with a message for error states."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False, font=dict(color=COLORS["text_muted"], size=14)
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=250,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


def get_period_button_styles(selected: str):
    """Return button colors/outlines for each period button."""
    periods = ["7d", "30d", "90d", "all"]
    styles = []
    for p in periods:
        if p == selected:
            styles.extend(["primary", False])
        else:
            styles.extend(["secondary", True])
    return styles


def create_filter_controls():
    """Create filter controls for the data table."""
    return dbc.Row(
        [
            dbc.Col(
                [
                    html.Label("Confidence Range:", className="small text-muted"),
                    dcc.RangeSlider(
                        id="confidence-slider",
                        min=0,
                        max=1,
                        step=0.05,
                        value=[0, 1],
                        marks={0: "0", 0.5: "0.5", 1: "1"},
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                [
                    html.Label("Show:", className="small text-muted"),
                    dcc.Dropdown(
                        id="outcome-filter",
                        options=[
                            {"label": "All Predictions", "value": "all"},
                            {"label": "Correct Only", "value": "correct"},
                            {"label": "Incorrect Only", "value": "incorrect"},
                            {"label": "Pending Only", "value": "pending"},
                        ],
                        value="all",
                        clearable=False,
                        style={"backgroundColor": COLORS["primary"]},
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                [
                    html.Label("Results:", className="small text-muted"),
                    dcc.Dropdown(
                        id="limit-selector",
                        options=[
                            {"label": "25 results", "value": 25},
                            {"label": "50 results", "value": 50},
                            {"label": "100 results", "value": 100},
                        ],
                        value=50,
                        clearable=False,
                        style={"backgroundColor": COLORS["primary"]},
                    ),
                ],
                md=4,
            ),
        ],
        className="g-2",
    )


def create_signal_card(row):
    """Create a signal card for recent predictions."""
    timestamp = row.get("timestamp")
    text = (
        row.get("text", "")[:150] + "..."
        if len(row.get("text", "")) > 150
        else row.get("text", "")
    )
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")

    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    sentiment_color = {
        "bullish": COLORS["success"],
        "bearish": COLORS["danger"],
        "neutral": COLORS["warning"],
    }.get(sentiment, COLORS["warning"])

    outcome_badge = None
    if correct_t7 is True:
        outcome_badge = dbc.Badge("CORRECT", color="success", className="ms-2")
    elif correct_t7 is False:
        outcome_badge = dbc.Badge("INCORRECT", color="danger", className="ms-2")
    elif return_t7 is not None:
        outcome_badge = dbc.Badge("PENDING", color="warning", className="ms-2")

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        timestamp.strftime("%m/%d %H:%M") if timestamp else "N/A",
                        style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                    ),
                    html.Span(
                        f" | {sentiment.upper()}",
                        style={
                            "color": sentiment_color,
                            "fontWeight": "bold",
                            "fontSize": "0.8rem",
                        },
                    ),
                    html.Span(
                        f" | {confidence:.0%}",
                        style={"color": COLORS["accent"], "fontSize": "0.8rem"},
                    ),
                    outcome_badge,
                ],
                className="mb-1",
            ),
            html.P(text, style={"fontSize": "0.85rem", "margin": "5px 0"}),
            html.Div(
                [
                    dbc.Badge(asset, color="info", className="me-1")
                    for asset in (assets if isinstance(assets, list) else [])[:5]
                ]
            ),
            html.Div(
                [
                    html.Span(
                        f"7d Return: {return_t7:+.2f}%",
                        style={
                            "color": COLORS["success"]
                            if return_t7 and return_t7 > 0
                            else COLORS["danger"],
                            "fontSize": "0.8rem",
                        },
                    )
                ],
                className="mt-1",
            )
            if return_t7 is not None
            else None,
        ],
        className="signal-card",
        style={
            "padding": "10px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

layout = html.Div(
    [
        # Store for selected asset
        dcc.Store(id="selected-asset", data=None),
        # Store for selected time period (default: 90d)
        dcc.Store(id="selected-period", data="90d"),
        # Store for last update timestamp
        dcc.Store(id="last-update-timestamp", data=None),
        # Page Header
        html.Div(
            [
                html.Div(
                    [
                        html.H2(
                            [
                                html.I(className="fas fa-home me-2"),
                                "Dashboard",
                            ],
                            style={"margin": 0},
                        ),
                        html.P(
                            "Trump Tweet Prediction Performance Overview",
                            style={
                                "color": COLORS["text_muted"],
                                "margin": "5px 0 0 0",
                            },
                        ),
                    ],
                    style={"flex": 1},
                ),
                # Refresh indicator
                html.Div(
                    [
                        html.Div(
                            [
                                html.I(
                                    className="fas fa-sync-alt me-2",
                                    style={"color": COLORS["accent"]},
                                ),
                                html.Span(
                                    "Last updated: ",
                                    style={"color": COLORS["text_muted"]},
                                ),
                                html.Span(
                                    id="last-update-time",
                                    children="--:--",
                                    style={"color": COLORS["text"]},
                                ),
                            ],
                            style={"marginBottom": "4px"},
                        ),
                    ],
                    style={
                        "fontSize": "0.8rem",
                        "textAlign": "right",
                    },
                ),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "20px",
            },
        ),
        # Time Period Selector Row
        html.Div(
            [
                html.Span(
                    "Time Period: ",
                    style={
                        "color": COLORS["text_muted"],
                        "marginRight": "10px",
                        "fontSize": "0.9rem",
                    },
                ),
                dbc.ButtonGroup(
                    [
                        dbc.Button(
                            "7D",
                            id="period-7d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "30D",
                            id="period-30d",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                        dbc.Button(
                            "90D",
                            id="period-90d",
                            color="primary",
                            size="sm",
                        ),
                        dbc.Button(
                            "All",
                            id="period-all",
                            color="secondary",
                            outline=True,
                            size="sm",
                        ),
                    ],
                    size="sm",
                ),
            ],
            className="period-selector",
            style={
                "marginBottom": "20px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "flex-end",
            },
        ),
        # Performance Metrics Row with loading spinner
        dcc.Loading(
            id="performance-metrics-loading",
            type="default",
            color=COLORS["accent"],
            children=html.Div(id="performance-metrics", className="mb-4"),
        ),
        # Two column layout: Charts + Asset Drilldown
        dbc.Row(
            [
                # Left column: Performance charts
                dbc.Col(
                    [
                        # Accuracy by Confidence Chart
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.I(className="fas fa-chart-bar me-2"),
                                        "Accuracy by Confidence Level",
                                    ],
                                    className="fw-bold",
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Loading(
                                            type="circle",
                                            color=COLORS["accent"],
                                            children=dcc.Graph(
                                                id="confidence-accuracy-chart",
                                                config={"displayModeBar": False},
                                            ),
                                        )
                                    ]
                                ),
                            ],
                            className="mb-3",
                            style={"backgroundColor": COLORS["secondary"]},
                        ),
                        # Accuracy by Asset Chart
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.I(className="fas fa-coins me-2"),
                                        "Performance by Asset ",
                                        html.Small(
                                            "(click bar to drill down)",
                                            style={
                                                "color": COLORS["text_muted"],
                                                "fontWeight": "normal",
                                            },
                                        ),
                                    ],
                                    className="fw-bold",
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Loading(
                                            type="circle",
                                            color=COLORS["accent"],
                                            children=dcc.Graph(
                                                id="asset-accuracy-chart",
                                                config={"displayModeBar": False},
                                                style={"cursor": "pointer"},
                                            ),
                                        )
                                    ]
                                ),
                            ],
                            className="mb-3",
                            style={"backgroundColor": COLORS["secondary"]},
                        ),
                    ],
                    xs=12,
                    sm=12,
                    md=7,
                    lg=7,
                    xl=7,
                ),
                # Right column: Recent Signals + Asset Drilldown
                dbc.Col(
                    [
                        # Recent Signals
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.I(className="fas fa-bolt me-2"),
                                        "Recent Signals",
                                    ],
                                    className="fw-bold",
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Loading(
                                            type="circle",
                                            color=COLORS["accent"],
                                            children=html.Div(
                                                id="recent-signals-list",
                                                style={
                                                    "maxHeight": "400px",
                                                    "overflowY": "auto",
                                                },
                                            ),
                                        )
                                    ]
                                ),
                            ],
                            className="mb-3",
                            style={"backgroundColor": COLORS["secondary"]},
                        ),
                        # Asset Deep Dive
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.I(className="fas fa-search me-2"),
                                        "Asset Deep Dive",
                                    ],
                                    className="fw-bold",
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Dropdown(
                                            id="asset-selector",
                                            placeholder="Select an asset to see historical predictions...",
                                            className="mb-3",
                                            style={
                                                "backgroundColor": COLORS["primary"],
                                                "color": COLORS["text"],
                                            },
                                        ),
                                        dcc.Loading(
                                            type="circle",
                                            color=COLORS["accent"],
                                            children=html.Div(
                                                id="asset-drilldown-content"
                                            ),
                                        ),
                                    ]
                                ),
                            ],
                            style={"backgroundColor": COLORS["secondary"]},
                        ),
                    ],
                    xs=12,
                    sm=12,
                    md=5,
                    lg=5,
                    xl=5,
                ),
            ]
        ),
        # Collapsible Full Data Table
        dbc.Card(
            [
                dbc.CardHeader(
                    [
                        dbc.Button(
                            [
                                html.I(className="fas fa-table me-2"),
                                "Full Prediction Data",
                            ],
                            id="collapse-table-button",
                            color="link",
                            className="text-white fw-bold p-0",
                        ),
                    ],
                    className="fw-bold",
                ),
                dbc.Collapse(
                    dbc.CardBody(
                        [
                            create_filter_controls(),
                            dcc.Loading(
                                type="default",
                                color=COLORS["accent"],
                                children=html.Div(
                                    id="predictions-table-container",
                                    className="mt-3",
                                ),
                            ),
                        ]
                    ),
                    id="collapse-table",
                    is_open=False,
                ),
            ],
            className="mt-4",
            style={"backgroundColor": COLORS["secondary"]},
        ),
    ],
    style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
)


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------


@callback(
    [
        Output("selected-period", "data"),
        Output("period-7d", "color"),
        Output("period-7d", "outline"),
        Output("period-30d", "color"),
        Output("period-30d", "outline"),
        Output("period-90d", "color"),
        Output("period-90d", "outline"),
        Output("period-all", "color"),
        Output("period-all", "outline"),
    ],
    [
        Input("period-7d", "n_clicks"),
        Input("period-30d", "n_clicks"),
        Input("period-90d", "n_clicks"),
        Input("period-all", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def update_period_selection(n7, n30, n90, nall):
    """Update selected time period based on button clicks."""
    ctx = callback_context
    if not ctx.triggered:
        return "90d", *get_period_button_styles("90d")

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    period_map = {
        "period-7d": "7d",
        "period-30d": "30d",
        "period-90d": "90d",
        "period-all": "all",
    }
    selected = period_map.get(button_id, "90d")
    return selected, *get_period_button_styles(selected)


@callback(
    [
        Output("performance-metrics", "children"),
        Output("confidence-accuracy-chart", "figure"),
        Output("asset-accuracy-chart", "figure"),
        Output("recent-signals-list", "children"),
        Output("asset-selector", "options"),
        Output("last-update-timestamp", "data"),
        Output("last-update-time", "children"),
    ],
    [
        Input("refresh-interval", "n_intervals"),
        Input("selected-period", "data"),
    ],
)
def update_dashboard(n_intervals, period):
    """Update main dashboard components with error boundaries."""
    # Convert period to days
    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(period, 90)

    # Current timestamp
    current_time = datetime.now()
    time_str = current_time.strftime("%H:%M:%S")

    # ===== Performance Metrics =====
    try:
        perf = get_performance_metrics(days=days)
        stats = get_prediction_stats()

        metrics_row = dbc.Row(
            [
                dbc.Col(
                    create_metric_card(
                        "Prediction Accuracy",
                        f"{perf['accuracy_t7']:.1f}%",
                        f"{perf['correct_predictions']}/{perf['evaluated_predictions']} correct",
                        "bullseye",
                        COLORS["success"]
                        if perf["accuracy_t7"] > 60
                        else COLORS["danger"],
                    ),
                    xs=6,
                    sm=6,
                    md=3,
                ),
                dbc.Col(
                    create_metric_card(
                        "Total P&L (7-day)",
                        f"${perf['total_pnl_t7']:,.0f}",
                        "Based on $1,000 positions",
                        "dollar-sign",
                        COLORS["success"]
                        if perf["total_pnl_t7"] > 0
                        else COLORS["danger"],
                    ),
                    xs=6,
                    sm=6,
                    md=3,
                ),
                dbc.Col(
                    create_metric_card(
                        "Avg Return",
                        f"{perf['avg_return_t7']:+.2f}%",
                        "7-day average",
                        "chart-line",
                        COLORS["success"]
                        if perf["avg_return_t7"] > 0
                        else COLORS["danger"],
                    ),
                    xs=6,
                    sm=6,
                    md=3,
                ),
                dbc.Col(
                    create_metric_card(
                        "Predictions Evaluated",
                        f"{perf['evaluated_predictions']:,}",
                        f"of {stats['completed_analyses']:,} completed",
                        "clipboard-check",
                        COLORS["accent"],
                    ),
                    xs=6,
                    sm=6,
                    md=3,
                ),
            ],
            className="g-2 g-md-3",
        )
    except Exception as e:
        print(f"Error loading performance metrics: {traceback.format_exc()}")
        metrics_row = create_error_card("Unable to load performance metrics", str(e))

    # ===== Confidence Chart =====
    try:
        conf_df = get_accuracy_by_confidence(days=days)
        if not conf_df.empty:
            conf_fig = go.Figure()
            conf_fig.add_trace(
                go.Bar(
                    x=conf_df["confidence_level"],
                    y=conf_df["accuracy"],
                    text=conf_df["accuracy"].apply(lambda x: f"{x:.1f}%"),
                    textposition="outside",
                    marker_color=[
                        COLORS["danger"],
                        COLORS["warning"],
                        COLORS["success"],
                    ],
                    hovertemplate="<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Total: %{customdata}<extra></extra>",
                    customdata=conf_df["total"],
                )
            )
            conf_fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=COLORS["text"],
                margin=dict(l=40, r=40, t=20, b=40),
                yaxis=dict(
                    range=[0, 100], title="Accuracy %", gridcolor=COLORS["border"]
                ),
                xaxis=dict(title=""),
                height=250,
            )
        else:
            conf_fig = create_empty_chart("No outcome data available for this period")
    except Exception as e:
        print(f"Error loading confidence chart: {traceback.format_exc()}")
        conf_fig = create_empty_chart(f"Error: {str(e)[:50]}")

    # ===== Asset Chart =====
    try:
        asset_df = get_accuracy_by_asset(limit=15, days=days)
        if not asset_df.empty:
            colors = [
                COLORS["success"]
                if acc >= 60
                else COLORS["danger"]
                if acc < 50
                else COLORS["warning"]
                for acc in asset_df["accuracy"]
            ]
            asset_fig = go.Figure()
            asset_fig.add_trace(
                go.Bar(
                    x=asset_df["symbol"],
                    y=asset_df["accuracy"],
                    text=asset_df["accuracy"].apply(lambda x: f"{x:.0f}%"),
                    textposition="outside",
                    marker_color=colors,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Accuracy: %{y:.1f}%<br>"
                        "Predictions: %{customdata[0]}<br>"
                        "P&L: $%{customdata[1]:,.0f}<extra></extra>"
                    ),
                    customdata=list(
                        zip(asset_df["total_predictions"], asset_df["total_pnl"])
                    ),
                )
            )
            asset_fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=COLORS["text"],
                margin=dict(l=40, r=40, t=20, b=60),
                yaxis=dict(
                    range=[0, 100], title="Accuracy %", gridcolor=COLORS["border"]
                ),
                xaxis=dict(title="", tickangle=45),
                height=300,
            )
        else:
            asset_fig = create_empty_chart("No asset data available for this period")
    except Exception as e:
        print(f"Error loading asset chart: {traceback.format_exc()}")
        asset_fig = create_empty_chart(f"Error: {str(e)[:50]}")

    # ===== Recent Signals =====
    try:
        signals_df = get_recent_signals(limit=10, min_confidence=0.5, days=days)
        if not signals_df.empty:
            signals_list = [create_signal_card(row) for _, row in signals_df.iterrows()]
        else:
            signals_list = [
                html.P(
                    "No recent signals available",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )
            ]
    except Exception as e:
        print(f"Error loading signals: {traceback.format_exc()}")
        signals_list = [create_error_card("Unable to load signals", str(e))]

    # ===== Asset Selector Options =====
    try:
        active_assets = get_active_assets_from_db()
        asset_options = [{"label": asset, "value": asset} for asset in active_assets]
    except Exception:
        asset_options = []

    return (
        metrics_row,
        conf_fig,
        asset_fig,
        signals_list,
        asset_options,
        current_time.isoformat(),
        time_str,
    )


@callback(
    Output("asset-drilldown-content", "children"),
    [Input("asset-selector", "value"), Input("selected-period", "data")],
)
def update_asset_drilldown(selected_asset, period):
    """Update asset drilldown when an asset is selected."""
    if not selected_asset:
        return html.P(
            "Select an asset to see historical predictions",
            style={"color": COLORS["text_muted"], "textAlign": "center"},
        )

    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(period, 90)

    try:
        df = get_similar_predictions(asset=selected_asset, limit=10, days=days)
        if df.empty:
            return html.P(
                f"No historical predictions for {selected_asset}",
                style={"color": COLORS["text_muted"], "textAlign": "center"},
            )

        cards = []
        for _, row in df.iterrows():
            sentiment = row.get("prediction_sentiment", "neutral")
            if sentiment:
                sentiment = sentiment.lower()
            sentiment_color = {
                "bullish": COLORS["success"],
                "bearish": COLORS["danger"],
            }.get(sentiment, COLORS["warning"])

            return_t7 = row.get("return_t7")
            correct_t7 = row.get("correct_t7")

            outcome_badge = None
            if correct_t7 is True:
                outcome_badge = dbc.Badge("CORRECT", color="success", className="ms-2")
            elif correct_t7 is False:
                outcome_badge = dbc.Badge("INCORRECT", color="danger", className="ms-2")

            cards.append(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(
                                    row["timestamp"].strftime("%m/%d/%y")
                                    if row.get("timestamp")
                                    else "N/A",
                                    style={
                                        "color": COLORS["text_muted"],
                                        "fontSize": "0.8rem",
                                    },
                                ),
                                html.Span(
                                    f" | {sentiment.upper() if sentiment else 'N/A'}",
                                    style={
                                        "color": sentiment_color,
                                        "fontWeight": "bold",
                                        "fontSize": "0.8rem",
                                    },
                                ),
                                outcome_badge,
                            ]
                        ),
                        html.Div(
                            [
                                html.Span(
                                    f"7d Return: {return_t7:+.2f}%"
                                    if return_t7 is not None
                                    else "Pending...",
                                    style={
                                        "color": COLORS["success"]
                                        if return_t7 and return_t7 > 0
                                        else COLORS["danger"]
                                        if return_t7
                                        else COLORS["text_muted"],
                                        "fontSize": "0.85rem",
                                    },
                                )
                            ]
                        ),
                    ],
                    style={
                        "padding": "8px 0",
                        "borderBottom": f"1px solid {COLORS['border']}",
                    },
                )
            )

        return html.Div(cards)

    except Exception as e:
        return create_error_card(f"Error loading {selected_asset} data", str(e))


@callback(
    Output("selected-asset", "data"),
    Input("asset-accuracy-chart", "clickData"),
    prevent_initial_call=True,
)
def handle_asset_chart_click(click_data):
    """Handle click on asset chart bar to select asset."""
    if click_data and "points" in click_data:
        clicked_asset = click_data["points"][0].get("x")
        return clicked_asset
    return None


@callback(
    Output("asset-selector", "value"),
    Input("selected-asset", "data"),
)
def sync_asset_selector(selected_asset):
    """Sync asset selector dropdown with clicked asset."""
    return selected_asset


@callback(
    Output("collapse-table", "is_open"),
    Input("collapse-table-button", "n_clicks"),
    State("collapse-table", "is_open"),
    prevent_initial_call=True,
)
def toggle_table_collapse(n_clicks, is_open):
    """Toggle the data table collapse."""
    return not is_open


@callback(
    Output("predictions-table-container", "children"),
    [
        Input("collapse-table", "is_open"),
        Input("confidence-slider", "value"),
        Input("outcome-filter", "value"),
        Input("limit-selector", "value"),
        Input("selected-period", "data"),
    ],
)
def update_predictions_table(is_open, conf_range, outcome_filter, limit, period):
    """Update predictions data table when filters change."""
    if not is_open:
        return None

    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    days = days_map.get(period, 90)

    try:
        df = get_predictions_with_outcomes(limit=limit, days=days)
        if df.empty:
            return html.P(
                "No prediction data available",
                style={"color": COLORS["text_muted"], "textAlign": "center"},
            )

        # Apply filters
        if conf_range:
            df = df[
                (df["confidence"] >= conf_range[0])
                & (df["confidence"] <= conf_range[1])
            ]

        if outcome_filter == "correct":
            df = df[df["correct_t7"] == True]  # noqa: E712
        elif outcome_filter == "incorrect":
            df = df[df["correct_t7"] == False]  # noqa: E712
        elif outcome_filter == "pending":
            df = df[df["correct_t7"].isna()]

        if df.empty:
            return html.P(
                "No matching predictions",
                style={"color": COLORS["text_muted"], "textAlign": "center"},
            )

        # Prepare display dataframe
        display_df = df[
            [
                "timestamp",
                "outcome_symbol",
                "prediction_sentiment",
                "confidence",
                "return_t7",
                "correct_t7",
                "pnl_t7",
            ]
        ].copy()

        display_df["timestamp"] = display_df["timestamp"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M") if x else "N/A"
        )
        display_df["confidence"] = display_df["confidence"].apply(
            lambda x: f"{x:.0%}" if x else "N/A"
        )
        display_df["return_t7"] = display_df["return_t7"].apply(
            lambda x: f"{x:+.2f}%" if x is not None else "Pending"
        )
        display_df["correct_t7"] = display_df["correct_t7"].apply(
            lambda x: "Correct"
            if x is True
            else "Incorrect"
            if x is False
            else "Pending"
        )
        display_df["pnl_t7"] = display_df["pnl_t7"].apply(
            lambda x: f"${x:,.0f}" if x is not None else "N/A"
        )

        display_df.columns = [
            "Date",
            "Symbol",
            "Sentiment",
            "Confidence",
            "Return (7d)",
            "Outcome",
            "P&L",
        ]

        from dash import dash_table

        return dash_table.DataTable(
            data=display_df.to_dict("records"),
            columns=[{"name": col, "id": col} for col in display_df.columns],
            style_table={"overflowX": "auto"},
            style_cell={
                "textAlign": "center",
                "padding": "8px",
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
                    "if": {"filter_query": '{Outcome} = "Correct"'},
                    "color": COLORS["success"],
                },
                {
                    "if": {"filter_query": '{Outcome} = "Incorrect"'},
                    "color": COLORS["danger"],
                },
            ],
            page_size=15,
            sort_action="native",
        )

    except Exception as e:
        return create_error_card("Error loading predictions", str(e))
