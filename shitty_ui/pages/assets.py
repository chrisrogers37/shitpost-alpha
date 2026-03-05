"""Asset deep dive page layout and callbacks."""

import traceback
from typing import Optional

from dash import Dash, html, dcc, Input, Output, callback_context
import dash_bootstrap_components as dbc

from constants import COLORS, CHART_CONFIG
from components.utils import safe_format_pct, safe_format_dollar
from components.charts import build_annotated_price_chart, build_empty_signal_chart
from components.cards import (
    create_error_card,
    create_metric_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
)
from components.header import create_footer
from brand_copy import COPY
from data import (
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_price_with_signals,
    get_related_assets,
    get_ticker_fundamentals,
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
                    # Company Profile card (populated by callback)
                    dcc.Loading(
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="asset-company-profile", className="mb-4"),
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
                                                            config=CHART_CONFIG,
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
                                                    COPY["asset_performance_header"],
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
                                                    COPY["asset_related_header"],
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
                    # Signal summary stats for this asset
                    dcc.Loading(
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="asset-signal-summary", className="mb-4"),
                    ),
                    # Prediction timeline
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-history me-2"),
                                    COPY["asset_timeline_header"].format(symbol=symbol),
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
    Includes back navigation, symbol name, company name, and a placeholder for
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
                        [html.I(className="fas fa-arrow-left me-2"), "Screener"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
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
            # Symbol + Company Name + Price
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
                    # Company name + sector badge (populated by callback)
                    html.Div(
                        id="asset-company-subtitle",
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "8px",
                            "marginTop": "2px",
                        },
                    ),
                    html.P(
                        COPY["asset_page_subtitle"].format(symbol=symbol),
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                            "marginTop": "4px",
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
            Output("asset-company-subtitle", "children"),
            Output("asset-company-profile", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-signal-summary", "children"),
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
            return empty, "", [], html.Div(), empty, empty, empty, empty

        try:
            # --- COMPANY FUNDAMENTALS ---
            fundamentals = get_ticker_fundamentals(symbol)
            company_subtitle = _build_company_subtitle(fundamentals)
            company_profile = _build_company_profile_card(fundamentals)

            # --- STAT CARDS ---
            stats = get_asset_stats(symbol)
            stat_cards = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            "Prediction Accuracy",
                            f"{stats['accuracy']:.1f}%",
                            f"{stats['correct_predictions']}/{stats['total_predictions']} correct",
                            "bullseye",
                            (
                                COLORS["success"]
                                if stats["accuracy"] > 60
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
                            "Total P&L",
                            safe_format_dollar(stats["total_pnl"], fmt=",.0f"),
                            "Based on $1,000 positions",
                            "dollar-sign",
                            (
                                COLORS["success"]
                                if (stats["total_pnl"] or 0) > 0
                                else COLORS["danger"]
                            ),
                        ),
                        md=3,
                        xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Avg Return",
                            safe_format_pct(stats["avg_return"]),
                            f"Confidence: {stats['avg_confidence']:.0%}",
                            "chart-line",
                            (
                                COLORS["success"]
                                if (stats["avg_return"] or 0) > 0
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
                current_price_text = COPY["asset_no_price"]

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
                        COPY["asset_no_predictions"].format(symbol=symbol),
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                        },
                    )
                ]

            # --- SIGNAL SUMMARY ---
            signal_summary = _build_asset_signal_summary(symbol, predictions_df)

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
                        COPY["asset_no_related"],
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
                company_subtitle,
                company_profile,
                performance_summary,
                signal_summary,
                timeline_cards,
                related_links,
            )

        except Exception as e:
            print(f"Error loading asset page for {symbol}: {traceback.format_exc()}")
            error_card = create_error_card(f"Unable to load data for {symbol}", str(e))
            return (
                error_card,
                "",
                [],
                html.Div(),
                error_card,
                error_card,
                error_card,
                error_card,
            )

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

            return build_annotated_price_chart(
                prices_df=data["prices"],
                signals_df=data["signals"],
                symbol=symbol,
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


def _build_asset_signal_summary(symbol: str, predictions_df) -> html.Div:
    """Build a summary stats row for shitpost signals on this asset.

    Shows total post count, bullish %, accuracy, avg confidence, and total P&L
    as a compact stat row below the price chart.

    Args:
        symbol: Ticker symbol.
        predictions_df: DataFrame from get_asset_predictions() with columns
            prediction_sentiment, prediction_confidence, correct_t7, pnl_t7.

    Returns:
        html.Div containing a dbc.Row of mini stat cards, or an empty Div.
    """
    if predictions_df.empty:
        return html.Div(
            html.P(
                f"No predictions found for {symbol}.",
                style={
                    "color": COLORS["text_muted"],
                    "textAlign": "center",
                    "padding": "15px",
                },
            )
        )

    total = len(predictions_df)

    bullish = 0
    if "prediction_sentiment" in predictions_df.columns:
        bullish = (
            predictions_df["prediction_sentiment"].str.lower() == "bullish"
        ).sum()
    bullish_pct = (bullish / total * 100) if total > 0 else 0

    avg_conf = 0.0
    if "prediction_confidence" in predictions_df.columns:
        avg_conf = predictions_df["prediction_confidence"].mean() or 0.0

    evaluated = 0
    correct = 0
    accuracy = 0.0
    if "correct_t7" in predictions_df.columns:
        correct_col = predictions_df["correct_t7"]
        evaluated = correct_col.notna().sum()
        correct = (correct_col == True).sum()  # noqa: E712
        accuracy = (correct / evaluated * 100) if evaluated > 0 else 0.0

    total_pnl = 0.0
    if "pnl_t7" in predictions_df.columns:
        total_pnl = predictions_df["pnl_t7"].sum() or 0.0

    return dbc.Row(
        [
            dbc.Col(
                _mini_stat_card(
                    f"{total} posts",
                    f"mentioning {symbol}",
                    COLORS["accent"],
                ),
                md=2,
                sm=4,
                xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{bullish_pct:.0f}%",
                    "predicted bullish",
                    COLORS["success"],
                ),
                md=2,
                sm=4,
                xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{accuracy:.0f}%",
                    f"accuracy ({correct}/{evaluated})",
                    COLORS["success"] if accuracy > 50 else COLORS["danger"],
                ),
                md=2,
                sm=4,
                xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{avg_conf:.0%}",
                    "avg confidence",
                    COLORS["warning"],
                ),
                md=2,
                sm=4,
                xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"${total_pnl:+,.0f}",
                    "total P&L (7d)",
                    COLORS["success"] if total_pnl > 0 else COLORS["danger"],
                ),
                md=2,
                sm=4,
                xs=6,
            ),
        ],
        className="g-2",
    )


def _mini_stat_card(value: str, label: str, color: str) -> html.Div:
    """Compact stat display for the signal summary row.

    Args:
        value: The prominent value text (e.g., "12 posts", "67%").
        label: Descriptive label below the value.
        color: CSS color for the value text.

    Returns:
        html.Div styled as a small stat card.
    """
    return html.Div(
        [
            html.Div(
                value,
                style={
                    "fontSize": "1.1rem",
                    "fontWeight": "bold",
                    "color": color,
                },
            ),
            html.Div(
                label,
                style={
                    "fontSize": "0.75rem",
                    "color": COLORS["text_muted"],
                },
            ),
        ],
        style={
            "textAlign": "center",
            "padding": "10px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "border": f"1px solid {COLORS['border']}",
        },
    )


def _format_market_cap(market_cap: Optional[int]) -> str:
    """Format market cap as human-readable string.

    Args:
        market_cap: Market capitalization in USD.

    Returns:
        Formatted string like "$2.8T", "$150.3B", "$4.2M", or "N/A".
    """
    if market_cap is None:
        return "N/A"
    if market_cap >= 1_000_000_000_000:
        return f"${market_cap / 1_000_000_000_000:.1f}T"
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.1f}B"
    if market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.1f}M"
    return f"${market_cap:,.0f}"


def _sector_badge(sector: Optional[str]) -> html.Span:
    """Render a compact sector badge.

    Args:
        sector: Sector name (e.g. "Technology"). None renders nothing.

    Returns:
        html.Span badge component, or empty Span if sector is None.
    """
    if not sector:
        return html.Span()

    return html.Span(
        sector,
        style={
            "backgroundColor": f"{COLORS['navy']}40",
            "color": COLORS["text"],
            "fontSize": "0.75rem",
            "padding": "2px 10px",
            "borderRadius": "9999px",
            "fontWeight": "500",
            "letterSpacing": "0.02em",
            "display": "inline-block",
        },
    )


def _build_company_subtitle(fundamentals: dict) -> list:
    """Build the company name + sector badge row for the header.

    Args:
        fundamentals: Dict from get_ticker_fundamentals().

    Returns:
        List of Dash components for the subtitle div.
    """
    children = []

    company_name = fundamentals.get("company_name")
    if company_name:
        children.append(
            html.Span(
                company_name,
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "1rem",
                    "fontWeight": "400",
                },
            )
        )

    sector = fundamentals.get("sector")
    if sector:
        children.append(_sector_badge(sector))

    return children


def _build_company_profile_card(fundamentals: dict) -> html.Div:
    """Build the Company Profile card for the asset page.

    Shows sector, industry, market cap, P/E, dividend yield, beta, and description.
    Returns an empty Div if no fundamental data is available.

    Args:
        fundamentals: Dict from get_ticker_fundamentals().

    Returns:
        dbc.Card component or empty html.Div.
    """
    # Check if any meaningful data exists
    has_data = any(
        fundamentals.get(key) is not None
        for key in ["company_name", "sector", "market_cap", "pe_ratio", "description"]
    )

    if not has_data:
        return html.Div()  # No fundamentals, render nothing

    # Build metric items
    metrics = []

    def _add_metric(label: str, value: str, icon: str):
        metrics.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon} me-2",
                                style={"color": COLORS["accent"], "width": "16px"},
                            ),
                            html.Span(
                                label,
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.8rem",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    html.Div(
                        value,
                        style={
                            "color": COLORS["text"],
                            "fontSize": "0.9rem",
                            "fontWeight": "600",
                            "marginTop": "2px",
                        },
                    ),
                ],
                style={
                    "padding": "8px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            )
        )

    if fundamentals.get("sector"):
        _add_metric("Sector", fundamentals["sector"], "layer-group")

    if fundamentals.get("industry"):
        _add_metric("Industry", fundamentals["industry"], "industry")

    if fundamentals.get("market_cap") is not None:
        _add_metric(
            "Market Cap", _format_market_cap(fundamentals["market_cap"]), "coins"
        )

    if fundamentals.get("pe_ratio") is not None:
        pe_str = f"{fundamentals['pe_ratio']:.1f}"
        if fundamentals.get("forward_pe") is not None:
            pe_str += f" / {fundamentals['forward_pe']:.1f} fwd"
        _add_metric("P/E Ratio", pe_str, "calculator")

    if fundamentals.get("dividend_yield") is not None:
        _add_metric(
            "Dividend Yield",
            f"{fundamentals['dividend_yield'] * 100:.2f}%",
            "percentage",
        )

    if fundamentals.get("beta") is not None:
        _add_metric("Beta", f"{fundamentals['beta']:.2f}", "wave-square")

    if fundamentals.get("exchange"):
        _add_metric("Exchange", fundamentals["exchange"], "building-columns")

    # Build the card
    card_body_children = []

    if metrics:
        card_body_children.append(html.Div(metrics))

    # Description (truncated)
    if fundamentals.get("description"):
        card_body_children.append(
            html.P(
                fundamentals["description"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "lineHeight": "1.5",
                    "marginTop": "12px",
                    "marginBottom": "0",
                },
            )
        )

    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="fas fa-building me-2"),
                    "Company Profile",
                ],
                className="fw-bold",
            ),
            dbc.CardBody(card_body_children),
        ],
        style={"backgroundColor": COLORS["secondary"]},
    )
