"""Asset deep dive page layout and callbacks."""

from datetime import datetime
import traceback

from dash import Dash, html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from constants import COLORS
from components.charts import build_signal_over_trend_chart, build_empty_signal_chart
from components.cards import (
    create_error_card,
    create_empty_chart,
    create_metric_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
)
from components.header import create_footer
from data import (
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_price_with_signals,
    get_related_assets,
)


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
            # Navigation row
            html.Div(
                [
                    dcc.Link(
                        [html.I(className="fas fa-arrow-left me-2"), "Dashboard"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                            "marginRight": "16px",
                        },
                    ),
                    dcc.Link(
                        [html.I(className="fas fa-chart-pie me-2"), "Performance"],
                        href="/performance",
                        style={
                            "color": COLORS["text_muted"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "10px",
                },
            ),
            # Symbol + Price
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



def register_asset_callbacks(app: Dash):
    """Register all asset page callbacks."""

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

