"""
Dashboard layout and callbacks for Shitty UI
Redesigned to focus on prediction performance and insights.

Enhancements:
- Loading states for all data components
- Error boundaries with graceful degradation
- Time period selector (7d/30d/90d/All)
- Chart interactivity (click to filter)
- Mobile responsiveness
- Refresh indicator with countdown
"""

from datetime import datetime, timedelta
import traceback
from dash import Dash, html, dcc, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from data import (
    get_prediction_stats,
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_related_assets,
)
from typing import Dict, Any

# Color palette - cleaner, more professional
COLORS = {
    "primary": "#1e293b",  # Slate 800 - main background
    "secondary": "#334155",  # Slate 700 - cards
    "accent": "#3b82f6",  # Blue 500 - highlights
    "success": "#10b981",  # Emerald 500 - bullish/correct
    "danger": "#ef4444",  # Red 500 - bearish/incorrect
    "warning": "#f59e0b",  # Amber 500 - pending
    "text": "#f1f5f9",  # Slate 100 - primary text
    "text_muted": "#94a3b8",  # Slate 400 - secondary text
    "border": "#475569",  # Slate 600 - borders
}


def create_error_card(message: str, details: str = None):
    """Create an error display card for graceful degradation."""
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-exclamation-triangle me-2",
                                style={"color": COLORS["danger"]},
                            ),
                            html.Span(
                                "Error Loading Data",
                                style={"color": COLORS["danger"], "fontWeight": "bold"},
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.P(
                        message,
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                        },
                    ),
                    html.Small(
                        details,
                        style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                    )
                    if details
                    else None,
                ],
                style={"padding": "15px"},
            )
        ],
        style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['danger']}",
        },
    )


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
            styles.extend(["primary", False])  # color, outline
        else:
            styles.extend(["secondary", True])
    return styles


def create_app() -> Dash:
    """Create and configure the Dash app."""

    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Prediction Performance Dashboard"

    # Custom CSS for mobile responsiveness
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Mobile-specific styles */
            @media (max-width: 768px) {
                .metric-card {
                    margin-bottom: 10px;
                }
                .metric-card .card-body {
                    padding: 10px !important;
                }
                .metric-card h3 {
                    font-size: 1.25rem !important;
                }
                .chart-container {
                    height: 200px !important;
                }
                .signal-card {
                    padding: 8px !important;
                }
                h1 {
                    font-size: 1.5rem !important;
                }
                .header-container {
                    flex-direction: column !important;
                    text-align: center !important;
                }
                .header-right {
                    margin-top: 10px !important;
                    flex-direction: column !important;
                    gap: 8px !important;
                }
                .period-selector {
                    justify-content: center !important;
                }
            }

            /* Ensure charts resize properly */
            .js-plotly-plot {
                width: 100% !important;
            }

            /* Loading spinner styling */
            ._dash-loading {
                margin: 20px auto;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

    # Main layout with URL routing
    app.layout = html.Div(
        [
            # URL tracking for multi-page routing
            dcc.Location(id="url", refresh=False),
            # Auto-refresh interval (5 minutes)
            dcc.Interval(
                id="refresh-interval",
                interval=5 * 60 * 1000,  # 5 minutes
                n_intervals=0,
            ),
            # Countdown interval (1 second)
            dcc.Interval(
                id="countdown-interval",
                interval=1000,  # 1 second
                n_intervals=0,
            ),
            # Store for selected asset
            dcc.Store(id="selected-asset", data=None),
            # Store for selected time period (default: 90d)
            dcc.Store(id="selected-period", data="90d"),
            # Store for last update timestamp
            dcc.Store(id="last-update-timestamp", data=None),
            # Page content - swapped by router callback
            html.Div(id="page-content"),
        ],
        style={
            "backgroundColor": COLORS["primary"],
            "minHeight": "100vh",
            "color": COLORS["text"],
            "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        },
    )

    return app


def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    return html.Div(
        [
            # Header
            create_header(),
            # Main content container
            html.Div(
                [
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
                                    ),  # Default selected
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
                            # Left column: Performance charts (full width on mobile)
                            dbc.Col(
                                [
                                    # Accuracy by Confidence Chart with loading
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-chart-bar me-2"
                                                    ),
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
                                                            config={
                                                                "displayModeBar": False
                                                            },
                                                        ),
                                                    )
                                                ]
                                            ),
                                        ],
                                        className="mb-3",
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                    # Accuracy by Asset Chart with loading and click interactivity
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-coins me-2"
                                                    ),
                                                    "Performance by Asset ",
                                                    html.Small(
                                                        "(click bar to drill down)",
                                                        style={
                                                            "color": COLORS[
                                                                "text_muted"
                                                            ],
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
                                                            config={
                                                                "displayModeBar": False
                                                            },
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
                            # Right column: Recent Signals + Asset Drilldown (full width on mobile)
                            dbc.Col(
                                [
                                    # Recent Signals with loading
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-bolt me-2"
                                                    ),
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
                                    # Asset Deep Dive with loading
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-search me-2"
                                                    ),
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
                                                            "backgroundColor": COLORS[
                                                                "primary"
                                                            ],
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
                                        # Filter controls
                                        create_filter_controls(),
                                        # Data table with loading
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
                    # Footer
                    create_footer(),
                ],
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
            ),
        ]
    )


def create_header():
    """Create the dashboard header with refresh indicator."""
    return html.Div(
        [
            html.Div(
                [
                    html.H1(
                        [
                            html.Span(
                                "Shitpost Alpha", style={"color": COLORS["accent"]}
                            ),
                        ],
                        style={"fontSize": "2rem", "fontWeight": "bold", "margin": 0},
                    ),
                    html.P(
                        "Trump Tweet Prediction Performance Dashboard",
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
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
                                "Last updated: ", style={"color": COLORS["text_muted"]}
                            ),
                            html.Span(
                                id="last-update-time",
                                children="--:--",
                                style={"color": COLORS["text"]},
                            ),
                        ],
                        style={"marginBottom": "4px"},
                    ),
                    html.Div(
                        [
                            html.Span(
                                "Next refresh: ", style={"color": COLORS["text_muted"]}
                            ),
                            html.Span(
                                id="next-update-countdown",
                                children="5:00",
                                style={"color": COLORS["accent"], "fontWeight": "bold"},
                            ),
                        ]
                    ),
                ],
                className="header-right",
                style={
                    "fontSize": "0.8rem",
                    "textAlign": "right",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-end",
                },
            ),
        ],
        className="header-container",
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
        },
    )


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
                    html.Label("Date Range:", className="small text-muted"),
                    dcc.DatePickerRange(
                        id="date-range-picker",
                        start_date=(datetime.now() - timedelta(days=90)).date(),
                        end_date=datetime.now().date(),
                        display_format="YYYY-MM-DD",
                        style={"fontSize": "0.8rem"},
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
                            {"label": "25", "value": 25},
                            {"label": "50", "value": 50},
                            {"label": "100", "value": 100},
                        ],
                        value=50,
                        clearable=False,
                        style={"fontSize": "0.9rem"},
                    ),
                ],
                md=2,
            ),
        ],
        className="g-3",
    )


def create_footer():
    """Create the dashboard footer."""
    return html.Div(
        [
            html.Hr(style={"borderColor": COLORS["border"], "margin": "40px 0 20px 0"}),
            html.P(
                [
                    "Disclaimer: This is NOT financial advice. For entertainment and research purposes only."
                ],
                style={
                    "textAlign": "center",
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "fontStyle": "italic",
                },
            ),
            html.P(
                [
                    html.A(
                        [html.I(className="fab fa-github me-1"), "View Source"],
                        href="https://github.com/chrisrogers37/shitpost-alpha",
                        target="_blank",
                        style={"color": COLORS["accent"], "textDecoration": "none"},
                    )
                ],
                style={"textAlign": "center", "marginBottom": "20px"},
            ),
        ]
    )


def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
):
    """Create a metric card component with responsive styling."""
    color = color or COLORS["accent"]
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon}",
                                style={"fontSize": "1.5rem", "color": color},
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.H3(
                        value, style={"margin": 0, "color": color, "fontWeight": "bold"}
                    ),
                    html.P(
                        title,
                        style={
                            "margin": 0,
                            "color": COLORS["text_muted"],
                            "fontSize": "0.85rem",
                        },
                    ),
                    html.Small(subtitle, style={"color": COLORS["text_muted"]})
                    if subtitle
                    else None,
                ],
                style={"textAlign": "center", "padding": "15px"},
            )
        ],
        className="metric-card",
        style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
        },
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

    # Determine sentiment from market_impact
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    # Format assets
    asset_str = ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
    if isinstance(assets, list) and len(assets) > 3:
        asset_str += f" +{len(assets) - 3}"

    # Outcome badge
    if correct_t7 is True:
        outcome_badge = html.Span("Correct", className="badge bg-success ms-2")
    elif correct_t7 is False:
        outcome_badge = html.Span("Incorrect", className="badge bg-danger ms-2")
    else:
        outcome_badge = html.Span(
            "Pending", className="badge bg-warning text-dark ms-2"
        )

    # Sentiment color
    sentiment_color = (
        COLORS["success"]
        if sentiment == "bullish"
        else COLORS["danger"]
        if sentiment == "bearish"
        else COLORS["text_muted"]
    )
    sentiment_icon = (
        "arrow-up"
        if sentiment == "bullish"
        else "arrow-down"
        if sentiment == "bearish"
        else "minus"
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        timestamp.strftime("%b %d, %H:%M")
                        if isinstance(timestamp, datetime)
                        else str(timestamp)[:16],
                        style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                    ),
                    outcome_badge,
                ],
                className="d-flex justify-content-between align-items-center mb-1",
            ),
            html.P(
                text,
                style={"fontSize": "0.85rem", "margin": "5px 0", "lineHeight": "1.4"},
            ),
            html.Div(
                [
                    html.Span(
                        [
                            html.I(className=f"fas fa-{sentiment_icon} me-1"),
                            sentiment.upper(),
                        ],
                        style={
                            "color": sentiment_color,
                            "fontSize": "0.8rem",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Span(
                        f" | {asset_str}",
                        style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                    ),
                    html.Span(
                        f" | Conf: {confidence:.0%}",
                        style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                    ),
                    html.Span(
                        f" | Return: {return_t7:+.1f}%"
                        if return_t7 is not None
                        else "",
                        style={
                            "color": COLORS["success"]
                            if return_t7 and return_t7 > 0
                            else COLORS["danger"],
                            "fontSize": "0.8rem",
                        },
                    )
                    if return_t7 is not None
                    else None,
                ]
            ),
        ],
        style={
            "padding": "12px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "cursor": "pointer",
        },
        className="signal-card",
    )


# =============================================================================
# Asset Deep Dive Page Components
# =============================================================================


def create_asset_page(symbol: str) -> html.Div:
    """
    Create the full asset deep dive page for a given symbol.

    This function is called by the router callback when the URL
    matches /assets/{symbol}.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')

    Returns:
        html.Div containing the full asset page layout
    """
    return html.Div(
        [
            # Store the symbol so callbacks can access it
            dcc.Store(id="asset-page-symbol", data=symbol),
            # Asset header with back navigation
            create_asset_header(symbol),
            # Main content
            html.Div(
                [
                    # Stat cards row (populated by callback)
                    dcc.Loading(
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="asset-stat-cards", className="mb-4"),
                    ),
                    # Price chart + Performance summary
                    dbc.Row(
                        [
                            # Left: Price chart with prediction overlays
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-chart-line me-2"
                                                    ),
                                                    f"{symbol} Price History",
                                                    # Date range selector
                                                    html.Div(
                                                        [
                                                            dbc.ButtonGroup(
                                                                [
                                                                    dbc.Button(
                                                                        "30D",
                                                                        id="asset-range-30d",
                                                                        color="secondary",
                                                                        outline=True,
                                                                        size="sm",
                                                                    ),
                                                                    dbc.Button(
                                                                        "90D",
                                                                        id="asset-range-90d",
                                                                        color="primary",
                                                                        size="sm",
                                                                    ),
                                                                    dbc.Button(
                                                                        "180D",
                                                                        id="asset-range-180d",
                                                                        color="secondary",
                                                                        outline=True,
                                                                        size="sm",
                                                                    ),
                                                                    dbc.Button(
                                                                        "1Y",
                                                                        id="asset-range-1y",
                                                                        color="secondary",
                                                                        outline=True,
                                                                        size="sm",
                                                                    ),
                                                                ],
                                                                size="sm",
                                                            ),
                                                        ],
                                                        style={"float": "right"},
                                                    ),
                                                ],
                                                className="fw-bold d-flex justify-content-between align-items-center",
                                            ),
                                            dbc.CardBody(
                                                [
                                                    dcc.Loading(
                                                        type="circle",
                                                        color=COLORS["accent"],
                                                        children=dcc.Graph(
                                                            id="asset-price-chart",
                                                            config={
                                                                "displayModeBar": False
                                                            },
                                                        ),
                                                    )
                                                ]
                                            ),
                                        ],
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                ],
                                md=8,
                                xs=12,
                            ),
                            # Right: Performance summary
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-chart-pie me-2"
                                                    ),
                                                    "Performance Summary",
                                                ],
                                                className="fw-bold",
                                            ),
                                            dbc.CardBody(
                                                id="asset-performance-summary"
                                            ),
                                        ],
                                        className="mb-3",
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                    # Related assets card
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-project-diagram me-2"
                                                    ),
                                                    "Related Assets",
                                                ],
                                                className="fw-bold",
                                            ),
                                            dbc.CardBody(id="asset-related-assets"),
                                        ],
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                ],
                                md=4,
                                xs=12,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Prediction timeline
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-history me-2"),
                                    f"Prediction Timeline for {symbol}",
                                ],
                                className="fw-bold",
                            ),
                            dbc.CardBody(
                                id="asset-prediction-timeline",
                                style={"maxHeight": "600px", "overflowY": "auto"},
                            ),
                        ],
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
                    # Footer
                    create_footer(),
                ],
                style={
                    "padding": "20px",
                    "maxWidth": "1400px",
                    "margin": "0 auto",
                },
            ),
        ]
    )


def create_asset_header(symbol: str) -> html.Div:
    """
    Create the header bar for an asset page.
    Includes back navigation, symbol name, and a placeholder for
    current price (populated by callback).

    Args:
        symbol: Ticker symbol

    Returns:
        html.Div header component
    """
    return html.Div(
        [
            html.Div(
                [
                    # Back link
                    dcc.Link(
                        [html.I(className="fas fa-arrow-left me-2"), "Dashboard"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
                            "textDecoration": "none",
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1(
                                symbol,
                                style={
                                    "fontSize": "2rem",
                                    "fontWeight": "bold",
                                    "margin": 0,
                                    "color": COLORS["text"],
                                },
                            ),
                            html.Span(
                                id="asset-current-price",
                                style={
                                    "fontSize": "1.5rem",
                                    "color": COLORS["accent"],
                                    "marginLeft": "15px",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    html.P(
                        "Prediction Performance Deep Dive",
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                        },
                    ),
                ]
            ),
        ],
        style={
            "padding": "20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
        },
    )


def create_prediction_timeline_card(row: dict) -> html.Div:
    """
    Create a single prediction card for the timeline.

    Args:
        row: Dictionary with keys from get_asset_predictions() DataFrame row

    Returns:
        html.Div component for one timeline entry
    """
    prediction_date = row.get("prediction_date")
    timestamp = row.get("timestamp")
    tweet_text = row.get("text", "")
    sentiment = row.get("prediction_sentiment", "neutral")
    confidence = row.get("prediction_confidence", 0)
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
    price_at = row.get("price_at_prediction")
    price_after = row.get("price_t7")

    # Sentiment styling
    if sentiment and sentiment.lower() == "bullish":
        sentiment_color = COLORS["success"]
        sentiment_icon = "arrow-up"
    elif sentiment and sentiment.lower() == "bearish":
        sentiment_color = COLORS["danger"]
        sentiment_icon = "arrow-down"
    else:
        sentiment_color = COLORS["text_muted"]
        sentiment_icon = "minus"

    # Outcome badge
    if correct_t7 is True:
        outcome_badge = html.Span(
            "Correct",
            className="badge",
            style={
                "backgroundColor": COLORS["success"],
                "marginLeft": "8px",
            },
        )
    elif correct_t7 is False:
        outcome_badge = html.Span(
            "Incorrect",
            className="badge",
            style={
                "backgroundColor": COLORS["danger"],
                "marginLeft": "8px",
            },
        )
    else:
        outcome_badge = html.Span(
            "Pending",
            className="badge",
            style={
                "backgroundColor": COLORS["warning"],
                "color": "#000",
                "marginLeft": "8px",
            },
        )

    # Format the date
    if isinstance(prediction_date, datetime):
        date_str = prediction_date.strftime("%b %d, %Y")
    elif hasattr(prediction_date, "strftime"):
        date_str = prediction_date.strftime("%b %d, %Y")
    else:
        date_str = str(prediction_date)[:10] if prediction_date else "Unknown"

    # Format timestamp for the tweet time
    if isinstance(timestamp, datetime):
        time_str = timestamp.strftime("%H:%M")
    else:
        time_str = str(timestamp)[11:16] if timestamp else ""

    # Truncate tweet text
    display_text = tweet_text[:200] + "..." if len(tweet_text) > 200 else tweet_text

    # Price change display
    price_info = []
    if price_at is not None:
        price_info.append(
            html.Span(
                f"Entry: ${price_at:,.2f}",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )
    if price_after is not None:
        price_info.append(
            html.Span(
                f" -> ${price_after:,.2f} (7d)",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )

    return html.Div(
        [
            # Top row: date, sentiment, outcome badge
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                date_str,
                                style={
                                    "fontWeight": "bold",
                                    "color": COLORS["text"],
                                    "fontSize": "0.9rem",
                                },
                            ),
                            html.Span(
                                f" at {time_str}" if time_str else "",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.8rem",
                                },
                            ),
                            outcome_badge,
                        ]
                    ),
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{sentiment_icon} me-1",
                                style={"color": sentiment_color},
                            ),
                            html.Span(
                                (sentiment or "neutral").upper(),
                                style={
                                    "color": sentiment_color,
                                    "fontWeight": "bold",
                                    "fontSize": "0.85rem",
                                },
                            ),
                            html.Span(
                                f" | Confidence: {confidence:.0%}"
                                if confidence
                                else "",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                            ),
                        ],
                        style={"marginTop": "4px"},
                    ),
                ]
            ),
            # Tweet text
            html.P(
                display_text,
                style={
                    "fontSize": "0.85rem",
                    "color": COLORS["text_muted"],
                    "margin": "8px 0",
                    "lineHeight": "1.5",
                    "fontStyle": "italic",
                    "borderLeft": f"3px solid {sentiment_color}",
                    "paddingLeft": "12px",
                },
            ),
            # Metrics row: return, P&L, prices
            html.Div(
                [
                    # 7-day return
                    html.Span(
                        f"Return (7d): {return_t7:+.2f}%"
                        if return_t7 is not None
                        else "Return (7d): --",
                        style={
                            "color": (
                                COLORS["success"]
                                if return_t7 and return_t7 > 0
                                else COLORS["danger"]
                                if return_t7 and return_t7 < 0
                                else COLORS["text_muted"]
                            ),
                            "fontSize": "0.85rem",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Span(" | ", style={"color": COLORS["border"]}),
                    # P&L
                    html.Span(
                        f"P&L: ${pnl_t7:+,.0f}" if pnl_t7 is not None else "P&L: --",
                        style={
                            "color": (
                                COLORS["success"]
                                if pnl_t7 and pnl_t7 > 0
                                else COLORS["danger"]
                                if pnl_t7 and pnl_t7 < 0
                                else COLORS["text_muted"]
                            ),
                            "fontSize": "0.85rem",
                        },
                    ),
                    html.Span(" | ", style={"color": COLORS["border"]}),
                    # Price info
                    *price_info,
                ],
                style={"marginBottom": "4px"},
            ),
        ],
        style={
            "padding": "16px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def create_related_asset_link(row: dict) -> html.Div:
    """
    Create a clickable link for a related asset.

    Args:
        row: Dictionary with keys: related_symbol, co_occurrence_count, avg_return_t7

    Returns:
        html.Div component
    """
    symbol = row.get("related_symbol", "???")
    count = row.get("co_occurrence_count", 0)
    avg_return = row.get("avg_return_t7")

    return_color = COLORS["text_muted"]
    return_str = "--"
    if avg_return is not None:
        return_color = COLORS["success"] if avg_return > 0 else COLORS["danger"]
        return_str = f"{avg_return:+.2f}%"

    return html.Div(
        [
            dcc.Link(
                html.Span(
                    symbol,
                    style={
                        "fontWeight": "bold",
                        "color": COLORS["accent"],
                        "fontSize": "0.95rem",
                    },
                ),
                href=f"/assets/{symbol}",
                style={"textDecoration": "none"},
            ),
            html.Span(
                f" ({count} shared predictions)",
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "marginLeft": "8px",
                },
            ),
            html.Span(
                f" | Avg return: {return_str}",
                style={
                    "color": return_color,
                    "fontSize": "0.8rem",
                    "marginLeft": "8px",
                },
            ),
        ],
        style={
            "padding": "10px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def create_performance_summary(stats: Dict[str, Any]) -> html.Div:
    """
    Create the performance summary comparing this asset vs overall system.

    Args:
        stats: Dictionary from get_asset_stats()

    Returns:
        html.Div with comparison metrics
    """
    asset_accuracy = stats.get("accuracy_t7", 0)
    overall_accuracy = stats.get("overall_accuracy_t7", 0)
    accuracy_diff = asset_accuracy - overall_accuracy

    asset_return = stats.get("avg_return_t7", 0)
    overall_return = stats.get("overall_avg_return_t7", 0)
    return_diff = asset_return - overall_return

    best = stats.get("best_return_t7")
    worst = stats.get("worst_return_t7")

    return html.Div(
        [
            # Accuracy comparison
            html.Div(
                [
                    html.H6(
                        "Accuracy vs Overall", style={"color": COLORS["text_muted"]}
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        f"{asset_accuracy:.1f}%",
                                        style={
                                            "fontSize": "1.5rem",
                                            "fontWeight": "bold",
                                            "color": (
                                                COLORS["success"]
                                                if asset_accuracy > 60
                                                else COLORS["danger"]
                                            ),
                                        },
                                    ),
                                    html.Span(
                                        " this asset",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"{overall_accuracy:.1f}%",
                                        style={
                                            "fontSize": "1rem",
                                            "color": COLORS["text_muted"],
                                        },
                                    ),
                                    html.Span(
                                        " overall",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"{accuracy_diff:+.1f}pp",
                                        style={
                                            "color": (
                                                COLORS["success"]
                                                if accuracy_diff > 0
                                                else COLORS["danger"]
                                            ),
                                            "fontWeight": "bold",
                                            "fontSize": "0.9rem",
                                        },
                                    ),
                                    html.Span(
                                        " vs average",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                        ]
                    ),
                ],
                style={
                    "padding": "12px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ),
            # Return comparison
            html.Div(
                [
                    html.H6(
                        "Avg 7-Day Return vs Overall",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Div(
                        [
                            html.Span(
                                f"{asset_return:+.2f}%",
                                style={
                                    "fontSize": "1.2rem",
                                    "fontWeight": "bold",
                                    "color": (
                                        COLORS["success"]
                                        if asset_return > 0
                                        else COLORS["danger"]
                                    ),
                                },
                            ),
                            html.Span(
                                f" vs {overall_return:+.2f}% overall",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                            ),
                            html.Span(
                                f" ({return_diff:+.2f}pp)",
                                style={
                                    "color": (
                                        COLORS["success"]
                                        if return_diff > 0
                                        else COLORS["danger"]
                                    ),
                                    "fontSize": "0.85rem",
                                    "marginLeft": "5px",
                                },
                            ),
                        ]
                    ),
                ],
                style={
                    "padding": "12px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ),
            # Best/Worst predictions
            html.Div(
                [
                    html.H6(
                        "Best / Worst Predictions",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Div(
                        [
                            html.Span(
                                f"Best: {best:+.2f}%"
                                if best is not None
                                else "Best: --",
                                style={
                                    "color": COLORS["success"],
                                    "fontSize": "0.9rem",
                                    "fontWeight": "bold",
                                },
                            ),
                            html.Span(" | ", style={"color": COLORS["border"]}),
                            html.Span(
                                f"Worst: {worst:+.2f}%"
                                if worst is not None
                                else "Worst: --",
                                style={
                                    "color": COLORS["danger"],
                                    "fontSize": "0.9rem",
                                    "fontWeight": "bold",
                                },
                            ),
                        ]
                    ),
                ],
                style={"padding": "12px 0"},
            ),
        ]
    )


def register_callbacks(app: Dash):
    """Register all callbacks for the dashboard."""

    # ========== URL Router Callback ==========
    @app.callback(
        Output("page-content", "children"),
        [Input("url", "pathname")],
    )
    def route_page(pathname: str):
        """Route to the correct page based on URL pathname."""
        if pathname and pathname.startswith("/assets/"):
            # Extract symbol from URL: /assets/AAPL -> AAPL
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        # Default: show main dashboard
        return create_dashboard_page()

    # ========== Time Period Selection Callback ==========
    @app.callback(
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

    # ========== Refresh Countdown Clientside Callback ==========
    app.clientside_callback(
        """
        function(n, lastUpdate) {
            if (!lastUpdate) return ["--:--", "5:00"];

            const last = new Date(lastUpdate);
            const now = new Date();
            const nextRefresh = new Date(last.getTime() + 5 * 60 * 1000);
            const remaining = Math.max(0, (nextRefresh - now) / 1000);

            const mins = Math.floor(remaining / 60);
            const secs = Math.floor(remaining % 60);
            const countdown = `${mins}:${secs.toString().padStart(2, '0')}`;

            const timeStr = last.toLocaleTimeString();

            return [timeStr, countdown];
        }
        """,
        [
            Output("last-update-time", "children"),
            Output("next-update-countdown", "children"),
        ],
        [Input("countdown-interval", "n_intervals")],
        [State("last-update-timestamp", "data")],
    )

    # ========== Main Dashboard Update Callback ==========
    @app.callback(
        [
            Output("performance-metrics", "children"),
            Output("confidence-accuracy-chart", "figure"),
            Output("asset-accuracy-chart", "figure"),
            Output("recent-signals-list", "children"),
            Output("asset-selector", "options"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
    def update_dashboard(n_intervals, period):
        """Update main dashboard components with error boundaries."""
        errors = []

        # Convert period to days
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period, 90)

        # Current timestamp for refresh indicator
        current_time = datetime.now().isoformat()

        # ===== Performance Metrics with error handling =====
        try:
            perf = get_performance_metrics(days=days)
            stats = get_prediction_stats()

            # Create metrics row with responsive columns
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
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )

        # ===== Confidence Chart with error handling =====
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
                conf_fig = create_empty_chart(
                    "No outcome data available for this period"
                )
        except Exception as e:
            errors.append(f"Confidence chart: {e}")
            print(f"Error loading confidence chart: {traceback.format_exc()}")
            conf_fig = create_empty_chart(f"Error: {str(e)[:50]}")

        # ===== Asset Chart with error handling =====
        try:
            asset_df = get_accuracy_by_asset(limit=10, days=days)
            if not asset_df.empty:
                asset_fig = go.Figure()
                colors = [
                    COLORS["success"] if x >= 60 else COLORS["danger"]
                    for x in asset_df["accuracy"]
                ]
                asset_fig.add_trace(
                    go.Bar(
                        x=asset_df["symbol"],
                        y=asset_df["accuracy"],
                        text=asset_df["accuracy"].apply(lambda x: f"{x:.0f}%"),
                        textposition="outside",
                        marker_color=colors,
                        hovertemplate="<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Predictions: %{customdata[0]}<br>Total P&L: $%{customdata[1]:,.0f}<br><i>Click to drill down</i><extra></extra>",
                        customdata=list(
                            zip(asset_df["total_predictions"], asset_df["total_pnl"])
                        ),
                    )
                )
                asset_fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color=COLORS["text"],
                    margin=dict(l=40, r=40, t=20, b=40),
                    yaxis=dict(
                        range=[0, 100], title="Accuracy %", gridcolor=COLORS["border"]
                    ),
                    xaxis=dict(title=""),
                    height=250,
                    hovermode="x unified",
                )
            else:
                asset_fig = create_empty_chart(
                    "No outcome data available for this period"
                )
        except Exception as e:
            errors.append(f"Asset chart: {e}")
            print(f"Error loading asset chart: {traceback.format_exc()}")
            asset_fig = create_empty_chart(f"Error: {str(e)[:50]}")

        # ===== Recent Signals with error handling =====
        try:
            signals_df = get_recent_signals(limit=10, days=days)
            if not signals_df.empty:
                signal_cards = [
                    create_signal_card(row) for _, row in signals_df.iterrows()
                ]
            else:
                signal_cards = [
                    html.P(
                        "No recent signals for this period",
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                        },
                    )
                ]
        except Exception as e:
            errors.append(f"Recent signals: {e}")
            print(f"Error loading recent signals: {traceback.format_exc()}")
            signal_cards = [create_error_card("Unable to load recent signals", str(e))]

        # ===== Asset Selector Options with error handling =====
        try:
            active_assets = get_active_assets_from_db()
            asset_options = [
                {"label": asset, "value": asset} for asset in active_assets
            ]
        except Exception as e:
            errors.append(f"Asset options: {e}")
            print(f"Error loading asset options: {traceback.format_exc()}")
            asset_options = []

        # Log any errors that occurred
        if errors:
            print(f"Dashboard update completed with errors: {errors}")

        return (
            metrics_row,
            conf_fig,
            asset_fig,
            signal_cards,
            asset_options,
            current_time,
        )

    # ========== Chart Click Handler ==========
    @app.callback(
        Output("asset-selector", "value"),
        [Input("asset-accuracy-chart", "clickData")],
        prevent_initial_call=True,
    )
    def handle_asset_chart_click(click_data):
        """When user clicks a bar in asset chart, select that asset in drilldown."""
        if not click_data:
            return None

        # Extract clicked asset from click data
        try:
            point = click_data["points"][0]
            asset = point["x"]  # The x-axis label is the asset symbol
            return asset
        except (KeyError, IndexError):
            return None

    @app.callback(
        Output("asset-drilldown-content", "children"),
        [Input("asset-selector", "value")],
    )
    def update_asset_drilldown(asset):
        """Update the asset deep dive section with error handling."""
        if not asset:
            return html.P(
                "Select an asset above to see historical predictions and their outcomes.",
                style={
                    "color": COLORS["text_muted"],
                    "textAlign": "center",
                    "padding": "20px",
                },
            )

        try:
            similar_df = get_similar_predictions(asset, limit=10)

            if similar_df.empty:
                return html.P(
                    f"No historical predictions found for {asset}.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )

            # Calculate summary stats for this asset
            total = len(similar_df)
            correct = (
                similar_df["correct_t7"].sum()
                if "correct_t7" in similar_df.columns
                else 0
            )
            accuracy = (correct / total * 100) if total > 0 else 0
            avg_return = (
                similar_df["return_t7"].mean()
                if "return_t7" in similar_df.columns
                else 0
            )
            total_pnl = (
                similar_df["pnl_t7"].sum() if "pnl_t7" in similar_df.columns else 0
            )

            # Create summary
            summary = html.Div(
                [
                    html.H5(asset, className="mb-2"),
                    html.Div(
                        [
                            html.Span(
                                "Accuracy: ", style={"color": COLORS["text_muted"]}
                            ),
                            html.Span(
                                f"{accuracy:.0f}%",
                                style={
                                    "color": COLORS["success"]
                                    if accuracy >= 60
                                    else COLORS["danger"],
                                    "fontWeight": "bold",
                                },
                            ),
                            html.Span(
                                " | Avg Return: ", style={"color": COLORS["text_muted"]}
                            ),
                            html.Span(
                                f"{avg_return:+.2f}%",
                                style={
                                    "color": COLORS["success"]
                                    if avg_return > 0
                                    else COLORS["danger"],
                                    "fontWeight": "bold",
                                },
                            ),
                            html.Span(
                                " | P&L: ", style={"color": COLORS["text_muted"]}
                            ),
                            html.Span(
                                f"${total_pnl:,.0f}",
                                style={
                                    "color": COLORS["success"]
                                    if total_pnl > 0
                                    else COLORS["danger"],
                                    "fontWeight": "bold",
                                },
                            ),
                        ],
                        className="mb-3",
                        style={"fontSize": "0.9rem"},
                    ),
                ]
            )

            # Create prediction timeline
            predictions = []
            for _, row in similar_df.iterrows():
                timestamp = row.get("timestamp")
                text = (
                    row.get("text", "")[:100] + "..."
                    if len(row.get("text", "")) > 100
                    else row.get("text", "")
                )
                sentiment = row.get("prediction_sentiment", "neutral")
                return_t7 = row.get("return_t7")
                correct = row.get("correct_t7")

                sentiment_color = (
                    COLORS["success"]
                    if sentiment == "bullish"
                    else COLORS["danger"]
                    if sentiment == "bearish"
                    else COLORS["text_muted"]
                )
                outcome_icon = (
                    "check-circle"
                    if correct
                    else "times-circle"
                    if correct is False
                    else "clock"
                )
                outcome_color = (
                    COLORS["success"]
                    if correct
                    else COLORS["danger"]
                    if correct is False
                    else COLORS["warning"]
                )

                predictions.append(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className=f"fas fa-{outcome_icon}",
                                        style={"color": outcome_color},
                                    ),
                                    html.Span(
                                        timestamp.strftime("%b %d")
                                        if isinstance(timestamp, datetime)
                                        else str(timestamp)[:10],
                                        style={
                                            "marginLeft": "8px",
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                    html.Span(
                                        f" {sentiment.upper()}",
                                        style={
                                            "marginLeft": "8px",
                                            "color": sentiment_color,
                                            "fontSize": "0.8rem",
                                            "fontWeight": "bold",
                                        },
                                    ),
                                    html.Span(
                                        f" {return_t7:+.1f}%"
                                        if return_t7 is not None
                                        else "",
                                        style={
                                            "marginLeft": "8px",
                                            "color": COLORS["success"]
                                            if return_t7 and return_t7 > 0
                                            else COLORS["danger"],
                                            "fontSize": "0.8rem",
                                        },
                                    )
                                    if return_t7 is not None
                                    else None,
                                ]
                            ),
                            html.P(
                                text,
                                style={
                                    "fontSize": "0.8rem",
                                    "color": COLORS["text_muted"],
                                    "margin": "5px 0 0 24px",
                                    "lineHeight": "1.3",
                                },
                            ),
                        ],
                        style={
                            "padding": "10px 0",
                            "borderBottom": f"1px solid {COLORS['border']}",
                        },
                    )
                )

            return html.Div(
                [
                    summary,
                    html.Div(
                        predictions, style={"maxHeight": "300px", "overflowY": "auto"}
                    ),
                ]
            )

        except Exception as e:
            print(
                f"Error loading asset drilldown for {asset}: {traceback.format_exc()}"
            )
            return create_error_card(f"Unable to load data for {asset}", str(e))

    @app.callback(
        Output("collapse-table", "is_open"),
        [Input("collapse-table-button", "n_clicks")],
        [State("collapse-table", "is_open")],
    )
    def toggle_collapse(n_clicks, is_open):
        """Toggle the data table collapse."""
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        Output("predictions-table-container", "children"),
        [
            Input("collapse-table", "is_open"),
            Input("confidence-slider", "value"),
            Input("date-range-picker", "start_date"),
            Input("date-range-picker", "end_date"),
            Input("limit-selector", "value"),
        ],
    )
    def update_predictions_table(
        is_open, confidence_range, start_date, end_date, limit
    ):
        """Update the predictions data table with error handling."""
        if not is_open:
            return None

        try:
            df = get_predictions_with_outcomes(limit=limit or 50)

            if df.empty:
                return html.P(
                    "No prediction data available.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )

            # Format columns for display
            display_df = df.copy()

            # Format timestamp
            if "timestamp" in display_df.columns:
                display_df["timestamp"] = pd.to_datetime(
                    display_df["timestamp"]
                ).dt.strftime("%Y-%m-%d %H:%M")

            # Format assets
            if "assets" in display_df.columns:
                display_df["assets"] = display_df["assets"].apply(
                    lambda x: ", ".join(x[:3])
                    + (f" +{len(x) - 3}" if len(x) > 3 else "")
                    if isinstance(x, list)
                    else str(x)
                )

            # Format returns
            for col in ["return_t1", "return_t3", "return_t7"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: f"{x:+.2f}%" if pd.notna(x) else "-"
                    )

            # Format outcome
            if "correct_t7" in display_df.columns:
                display_df["outcome"] = display_df["correct_t7"].apply(
                    lambda x: "Correct"
                    if x is True
                    else "Incorrect"
                    if x is False
                    else "Pending"
                )

            # Select columns to display
            display_cols = ["timestamp", "assets", "confidence", "return_t7", "outcome"]
            display_cols = [c for c in display_cols if c in display_df.columns]

            return dash_table.DataTable(
                data=display_df[display_cols].to_dict("records"),
                columns=[
                    {"name": c.replace("_", " ").title(), "id": c} for c in display_cols
                ],
                style_table={"overflowX": "auto"},
                style_cell={
                    "textAlign": "left",
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
                        "if": {"filter_query": "{outcome} = 'Correct'"},
                        "backgroundColor": "rgba(16, 185, 129, 0.1)",
                    },
                    {
                        "if": {"filter_query": "{outcome} = 'Incorrect'"},
                        "backgroundColor": "rgba(239, 68, 68, 0.1)",
                    },
                ],
                page_size=15,
                sort_action="native",
                filter_action="native",
            )

        except Exception as e:
            print(f"Error loading predictions table: {traceback.format_exc()}")
            return create_error_card("Unable to load prediction data", str(e))

    # ========== Asset Page Callbacks ==========

    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")],
    )
    def update_asset_page(symbol):
        """
        Populate all data-driven sections of the asset deep dive page.
        Fires when the page first loads (symbol store receives data).
        """
        if not symbol:
            empty = html.P("No asset selected.", style={"color": COLORS["text_muted"]})
            return empty, "", empty, empty, empty

        try:
            # --- STAT CARDS ---
            stats = get_asset_stats(symbol)
            stat_cards = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            "Prediction Accuracy",
                            f"{stats['accuracy_t7']:.1f}%",
                            f"{stats['correct_predictions']}/{stats['total_predictions']} correct",
                            "bullseye",
                            (
                                COLORS["success"]
                                if stats["accuracy_t7"] > 60
                                else COLORS["danger"]
                            ),
                        ),
                        md=3,
                        xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Total Predictions",
                            f"{stats['total_predictions']}",
                            f"{stats['bullish_count']} bullish / {stats['bearish_count']} bearish",
                            "clipboard-list",
                            COLORS["accent"],
                        ),
                        md=3,
                        xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Total P&L (7-day)",
                            f"${stats['total_pnl_t7']:,.0f}",
                            "Based on $1,000 positions",
                            "dollar-sign",
                            (
                                COLORS["success"]
                                if stats["total_pnl_t7"] > 0
                                else COLORS["danger"]
                            ),
                        ),
                        md=3,
                        xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Avg 7-Day Return",
                            f"{stats['avg_return_t7']:+.2f}%",
                            f"Confidence: {stats['avg_confidence']:.0%}",
                            "chart-line",
                            (
                                COLORS["success"]
                                if stats["avg_return_t7"] > 0
                                else COLORS["danger"]
                            ),
                        ),
                        md=3,
                        xs=6,
                    ),
                ],
                className="g-3",
            )

            # --- CURRENT PRICE ---
            price_df = get_asset_price_history(symbol, days=7)
            if not price_df.empty:
                latest_close = price_df.iloc[-1]["close"]
                current_price_text = f"${latest_close:,.2f}"
            else:
                current_price_text = "Price unavailable"

            # --- PERFORMANCE SUMMARY ---
            performance_summary = create_performance_summary(stats)

            # --- PREDICTION TIMELINE ---
            predictions_df = get_asset_predictions(symbol, limit=50)
            if not predictions_df.empty:
                timeline_cards = [
                    create_prediction_timeline_card(row.to_dict())
                    for _, row in predictions_df.iterrows()
                ]
            else:
                timeline_cards = [
                    html.P(
                        f"No predictions found for {symbol}.",
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                        },
                    )
                ]

            # --- RELATED ASSETS ---
            related_df = get_related_assets(symbol, limit=8)
            if not related_df.empty:
                related_links = [
                    create_related_asset_link(row.to_dict())
                    for _, row in related_df.iterrows()
                ]
            else:
                related_links = [
                    html.P(
                        "No related assets found.",
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "10px",
                        },
                    )
                ]

            return (
                stat_cards,
                current_price_text,
                performance_summary,
                timeline_cards,
                related_links,
            )

        except Exception as e:
            print(f"Error loading asset page for {symbol}: {traceback.format_exc()}")
            error_card = create_error_card(f"Unable to load data for {symbol}", str(e))
            return error_card, "", error_card, error_card, error_card

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
        """Update the price chart with prediction overlays."""
        if not symbol:
            return create_empty_chart("No asset selected")

        # Determine date range from button click
        ctx = callback_context
        days = 90  # Default
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
            # Get price data
            price_df = get_asset_price_history(symbol, days=days)
            if price_df.empty:
                return create_empty_chart(f"No price data available for {symbol}")

            # Get predictions for this asset
            predictions_df = get_asset_predictions(symbol, limit=100)

            # Create the candlestick chart
            fig = go.Figure()

            # Add candlestick trace
            fig.add_trace(
                go.Candlestick(
                    x=price_df["date"],
                    open=price_df["open"],
                    high=price_df["high"],
                    low=price_df["low"],
                    close=price_df["close"],
                    name=symbol,
                    increasing_line_color=COLORS["success"],
                    decreasing_line_color=COLORS["danger"],
                )
            )

            # Add prediction markers
            if not predictions_df.empty:
                # Filter predictions within the date range
                cutoff_date = price_df["date"].min()
                pred_in_range = predictions_df[
                    predictions_df["prediction_date"] >= cutoff_date
                ]

                if not pred_in_range.empty:
                    # Get price at prediction dates for marker placement
                    for _, pred in pred_in_range.iterrows():
                        pred_date = pred["prediction_date"]
                        correct = pred.get("correct_t7")
                        sentiment = pred.get("prediction_sentiment", "neutral")

                        # Determine marker color and symbol
                        if correct is True:
                            marker_color = COLORS["success"]
                            marker_symbol = "triangle-up"
                        elif correct is False:
                            marker_color = COLORS["danger"]
                            marker_symbol = "triangle-down"
                        else:
                            marker_color = COLORS["warning"]
                            marker_symbol = "circle"

                        # Find price at prediction date
                        price_at_date = price_df[
                            price_df["date"].dt.date == pred_date.date()
                        ]
                        if not price_at_date.empty:
                            y_val = price_at_date.iloc[0]["high"] * 1.02

                            fig.add_trace(
                                go.Scatter(
                                    x=[pred_date],
                                    y=[y_val],
                                    mode="markers",
                                    marker=dict(
                                        size=12,
                                        color=marker_color,
                                        symbol=marker_symbol,
                                        line=dict(width=1, color=COLORS["text"]),
                                    ),
                                    name=f"{sentiment} prediction",
                                    hovertemplate=(
                                        f"<b>{pred_date.strftime('%Y-%m-%d')}</b><br>"
                                        f"Sentiment: {sentiment}<br>"
                                        f"Result: {'Correct' if correct else 'Incorrect' if correct is False else 'Pending'}<br>"
                                        "<extra></extra>"
                                    ),
                                    showlegend=False,
                                )
                            )

            # Update layout
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=COLORS["text"],
                margin=dict(l=40, r=40, t=20, b=40),
                xaxis=dict(
                    gridcolor=COLORS["border"],
                    rangeslider=dict(visible=False),
                ),
                yaxis=dict(
                    gridcolor=COLORS["border"],
                    title="Price ($)",
                ),
                height=400,
                showlegend=False,
            )

            return fig

        except Exception as e:
            print(f"Error loading price chart for {symbol}: {traceback.format_exc()}")
            return create_empty_chart(f"Error: {str(e)[:50]}")

    @app.callback(
        [
            Output("asset-range-30d", "color"),
            Output("asset-range-30d", "outline"),
            Output("asset-range-90d", "color"),
            Output("asset-range-90d", "outline"),
            Output("asset-range-180d", "color"),
            Output("asset-range-180d", "outline"),
            Output("asset-range-1y", "color"),
            Output("asset-range-1y", "outline"),
        ],
        [
            Input("asset-range-30d", "n_clicks"),
            Input("asset-range-90d", "n_clicks"),
            Input("asset-range-180d", "n_clicks"),
            Input("asset-range-1y", "n_clicks"),
        ],
    )
    def update_asset_range_buttons(n30, n90, n180, n1y):
        """Update button styles when date range is changed."""
        ctx = callback_context
        if not ctx.triggered:
            # Default: 90d selected
            return (
                "secondary",
                True,
                "primary",
                False,
                "secondary",
                True,
                "secondary",
                True,
            )

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Default all to unselected
        styles = [
            "secondary",
            True,
            "secondary",
            True,
            "secondary",
            True,
            "secondary",
            True,
        ]

        # Set selected button
        if button_id == "asset-range-30d":
            styles[0:2] = ["primary", False]
        elif button_id == "asset-range-90d":
            styles[2:4] = ["primary", False]
        elif button_id == "asset-range-180d":
            styles[4:6] = ["primary", False]
        elif button_id == "asset-range-1y":
            styles[6:8] = ["primary", False]
        else:
            # Default to 90d
            styles[2:4] = ["primary", False]

        return tuple(styles)
