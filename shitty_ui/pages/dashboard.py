"""Dashboard page layout and callbacks."""

from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS, HIERARCHY, CHART_CONFIG
from components.controls import create_filter_controls
from components.header import create_header, create_footer
from brand_copy import COPY


def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    return html.Div(
        [
            # Header with navigation
            create_header(),
            # Main content container
            html.Div(
                [
                    # Time Period & Timeframe Selector Row
                    html.Div(
                        [
                            # Outcome Timeframe selector (left)
                            html.Div(
                                [
                                    html.Span(
                                        "Outcome Window: ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "marginRight": "10px",
                                            "fontSize": "0.9rem",
                                        },
                                    ),
                                    dbc.ButtonGroup(
                                        [
                                            dbc.Button(
                                                "T+1",
                                                id="tf-t1",
                                                color="secondary",
                                                outline=True,
                                                size="sm",
                                            ),
                                            dbc.Button(
                                                "T+3",
                                                id="tf-t3",
                                                color="secondary",
                                                outline=True,
                                                size="sm",
                                            ),
                                            dbc.Button(
                                                "T+7",
                                                id="tf-t7",
                                                color="primary",
                                                size="sm",
                                            ),
                                            dbc.Button(
                                                "T+30",
                                                id="tf-t30",
                                                color="secondary",
                                                outline=True,
                                                size="sm",
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                },
                            ),
                            # Time Period selector (right)
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
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                },
                            ),
                        ],
                        className="period-selector",
                        style={
                            "marginBottom": "20px",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "space-between",
                            "flexWrap": "wrap",
                            "gap": "12px",
                        },
                    ),
                    # Dynamic Insight Cards (above KPIs, answer "so what right now?")
                    dcc.Loading(
                        id="insight-cards-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="insight-cards-container",
                            style={"marginBottom": "16px"},
                        ),
                    ),
                    # Key Metrics Row (Primary tier - hero treatment)
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="performance-metrics",
                            style={"marginBottom": "32px"},
                        ),
                    ),
                    # ========== Asset Screener Table (Secondary tier) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-th-list me-2"),
                                    "Asset Screener",
                                    html.Small(
                                        " - performance by ticker, sorted"
                                        " & heat-mapped",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                                style={
                                    "backgroundColor": HIERARCHY["secondary"][
                                        "background"
                                    ]
                                },
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="screener-table-container",
                                        ),
                                    ),
                                ],
                                style={
                                    "backgroundColor": HIERARCHY["secondary"][
                                        "background"
                                    ],
                                    "padding": "12px",
                                },
                            ),
                        ],
                        className="mb-4",
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                        },
                    ),
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
                                                    label=COPY[
                                                        "analytics_calibration_tab"
                                                    ],
                                                    tab_id="tab-calibration",
                                                ),
                                                dbc.Tab(
                                                    label=COPY[
                                                        "analytics_backtest_tab"
                                                    ],
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
                                                                    COPY[
                                                                        "analytics_backtest_capital_label"
                                                                    ],
                                                                    style={
                                                                        "color": COLORS[
                                                                            "text_muted"
                                                                        ],
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
                                                                        "backgroundColor": COLORS[
                                                                            "bg"
                                                                        ],
                                                                        "color": COLORS[
                                                                            "text"
                                                                        ],
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
                                                                    COPY[
                                                                        "analytics_backtest_confidence_label"
                                                                    ],
                                                                    style={
                                                                        "color": COLORS[
                                                                            "text_muted"
                                                                        ],
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
                                                # "Run Backtest" button instead of live slider updates
                                                dbc.Button(
                                                    "Run Backtest",
                                                    id="backtest-run-btn",
                                                    color="primary",
                                                    size="sm",
                                                    className="mt-2",
                                                ),
                                            ],
                                            id="backtest-controls-container",
                                            style={
                                                "display": "none",
                                                "marginBottom": "16px",
                                            },
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
                    # ========== Latest Posts (Tertiary tier) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-rss me-2"),
                                    COPY["latest_posts_header"],
                                    html.Small(
                                        f" - {COPY['latest_posts_subtitle']}",
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
                                        children=html.Div(
                                            id="post-feed-container",
                                            style={
                                                "maxHeight": "600px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    )
                                ]
                            ),
                        ],
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
                    ),
                    # ========== Collapsible Full Data Table (Tertiary tier) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    dbc.Button(
                                        [
                                            html.I(
                                                className="fas fa-chevron-right me-2 collapse-chevron",
                                                id="collapse-table-chevron",
                                            ),
                                            html.I(className="fas fa-table me-2"),
                                            COPY["data_table_header"],
                                        ],
                                        id="collapse-table-button",
                                        color="link",
                                        className="text-white fw-bold p-0 collapse-toggle-btn",
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
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
                    ),
                    # Footer
                    create_footer(),
                ],
                className="main-content-container",
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
            ),
        ]
    )


def register_dashboard_callbacks(app: Dash):
    """Register all dashboard-specific callbacks.

    Delegates to focused sub-modules. This function is the single
    entry point called by layout.register_callbacks().
    """
    from pages.dashboard_callbacks import (
        register_period_callbacks,
        register_content_callbacks,
        register_table_callbacks,
        register_analytics_callbacks,
    )

    register_period_callbacks(app)
    register_content_callbacks(app)
    register_table_callbacks(app)
    register_analytics_callbacks(app)
