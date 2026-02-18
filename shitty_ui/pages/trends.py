"""Signal-over-trend page layout and callbacks for /trends route."""

import traceback

from dash import Dash, html, dcc, Input, Output, callback_context, no_update
import dash_bootstrap_components as dbc

from constants import COLORS, CHART_CONFIG
from brand_copy import COPY
from components.cards import create_error_card
from components.charts import build_signal_over_trend_chart, build_empty_signal_chart
from data import get_price_with_signals, get_active_assets_from_db, get_top_predicted_asset


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
                            COPY["trends_page_title"],
                        ],
                        style={"margin": 0, "fontWeight": "bold"},
                    ),
                    html.P(
                        COPY["trends_page_subtitle"],
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
                            html.Span(id="trends-chart-title", children=COPY["trends_chart_default"]),
                        ],
                        className="fw-bold",
                    ),
                    dbc.CardBody(
                        dcc.Loading(
                            type="circle",
                            color=COLORS["accent"],
                            children=dcc.Graph(
                                id="trends-signal-chart",
                                config=CHART_CONFIG,
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
        [
            Output("trends-asset-selector", "options"),
            Output("trends-asset-selector", "value"),
        ],
        [Input("url", "pathname")],
    )
    def populate_trends_assets(pathname):
        if pathname != "/trends":
            return no_update, no_update
        assets = get_active_assets_from_db()
        options = [{"label": a, "value": a} for a in assets]

        # Auto-select the most-predicted asset as default
        top_asset = get_top_predicted_asset()
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        return options, default_value

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
                build_empty_signal_chart(
                    COPY["trends_no_asset_hint"]
                ),
                COPY["trends_no_asset_data"],
                html.Div(
                    html.P(
                        COPY["trends_no_asset_hint"],
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                            "fontSize": "0.9rem",
                        },
                    )
                ),
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
                COPY["trends_no_signals_for_asset"].format(symbol=symbol),
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
