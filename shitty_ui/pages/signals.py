"""Signal feed page layout and callbacks for the /signals route."""

from datetime import datetime

from dash import Dash, html, dcc, Input, Output, State, MATCH
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

import pandas as pd

from constants import COLORS
from brand_copy import COPY
from components.cards import create_feed_signal_card, create_new_signals_banner
from data import get_sparkline_prices

PAGE_SIZE = 20


def create_signal_feed_page() -> html.Div:
    """
    Create the full /signals feed page layout.

    Structure:
    - Header with "New signals" indicator
    - Filter bar (sentiment, confidence, asset, outcome)
    - Signal card feed (scrollable list)
    - "Load More" button at the bottom
    - Export CSV button
    """
    return html.Div(
        [
            # Page header
            html.Div(
                [
                    html.H2(
                        [
                            html.I(className="fas fa-rss me-2"),
                            COPY["signals_page_title"],
                        ],
                        style={"margin": 0, "fontWeight": "bold"},
                    ),
                    html.P(
                        COPY["signals_page_subtitle"],
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            # New-signals banner (hidden by default)
            html.Div(
                id="new-signals-banner",
                children=[],
                style={"display": "none"},
            ),
            # Polling interval (2 minutes) — only for new-signals check
            dcc.Interval(
                id="signal-feed-poll-interval",
                interval=2 * 60 * 1000,
                n_intervals=0,
            ),
            # Client-side stores
            dcc.Store(id="signal-feed-last-seen-ts", data=None),
            dcc.Store(id="signal-feed-offset", data=0),
            dcc.Store(id="signal-feed-refresh-trigger", data=0),
            dcc.Download(id="signal-feed-csv-download"),
            # Filter bar
            dbc.Card(
                [
                    dbc.CardBody(
                        [
                            dbc.Row(
                                [
                                    # Sentiment filter
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Sentiment",
                                                className="small",
                                                style={
                                                    "color": COLORS["text_muted"]
                                                },
                                            ),
                                            dcc.Dropdown(
                                                id="signal-feed-sentiment-filter",
                                                options=[
                                                    {
                                                        "label": "All Sentiments",
                                                        "value": "all",
                                                    },
                                                    {
                                                        "label": "Bullish",
                                                        "value": "bullish",
                                                    },
                                                    {
                                                        "label": "Bearish",
                                                        "value": "bearish",
                                                    },
                                                ],
                                                value="all",
                                                clearable=False,
                                                style={"fontSize": "0.9rem"},
                                            ),
                                        ],
                                        xs=12,
                                        sm=6,
                                        md=3,
                                    ),
                                    # Confidence slider
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Confidence Range",
                                                className="small",
                                                style={
                                                    "color": COLORS["text_muted"]
                                                },
                                            ),
                                            dcc.RangeSlider(
                                                id="signal-feed-confidence-slider",
                                                min=0,
                                                max=1,
                                                step=0.05,
                                                value=[0, 1],
                                                marks={
                                                    0: {
                                                        "label": "0%",
                                                        "style": {
                                                            "color": COLORS[
                                                                "text_muted"
                                                            ]
                                                        },
                                                    },
                                                    0.5: {
                                                        "label": "50%",
                                                        "style": {
                                                            "color": COLORS[
                                                                "text_muted"
                                                            ]
                                                        },
                                                    },
                                                    1: {
                                                        "label": "100%",
                                                        "style": {
                                                            "color": COLORS[
                                                                "text_muted"
                                                            ]
                                                        },
                                                    },
                                                },
                                                tooltip={
                                                    "placement": "bottom",
                                                    "always_visible": False,
                                                },
                                            ),
                                        ],
                                        xs=12,
                                        sm=6,
                                        md=3,
                                    ),
                                    # Asset filter
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Asset",
                                                className="small",
                                                style={
                                                    "color": COLORS["text_muted"]
                                                },
                                            ),
                                            dcc.Dropdown(
                                                id="signal-feed-asset-filter",
                                                options=[],
                                                placeholder="All Assets",
                                                style={"fontSize": "0.9rem"},
                                            ),
                                        ],
                                        xs=12,
                                        sm=6,
                                        md=3,
                                    ),
                                    # Outcome filter
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Outcome",
                                                className="small",
                                                style={
                                                    "color": COLORS["text_muted"]
                                                },
                                            ),
                                            dcc.Dropdown(
                                                id="signal-feed-outcome-filter",
                                                options=[
                                                    {
                                                        "label": "All Outcomes",
                                                        "value": "all",
                                                    },
                                                    {
                                                        "label": "Evaluated (has outcome)",
                                                        "value": "evaluated",
                                                    },
                                                    {
                                                        "label": "Correct",
                                                        "value": "correct",
                                                    },
                                                    {
                                                        "label": "Incorrect",
                                                        "value": "incorrect",
                                                    },
                                                    {
                                                        "label": "Pending",
                                                        "value": "pending",
                                                    },
                                                ],
                                                value="all",
                                                clearable=False,
                                                style={"fontSize": "0.9rem"},
                                            ),
                                        ],
                                        xs=12,
                                        sm=6,
                                        md=3,
                                    ),
                                ],
                                className="g-3",
                            )
                        ]
                    )
                ],
                style={
                    "backgroundColor": COLORS["secondary"],
                    "border": f"1px solid {COLORS['border']}",
                    "marginBottom": "20px",
                },
            ),
            # Signal count + Export button row
            html.Div(
                [
                    html.Span(
                        id="signal-feed-count-label",
                        children="",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.85rem",
                        },
                    ),
                    dbc.Button(
                        [
                            html.I(className="fas fa-download me-2"),
                            COPY["signals_export"],
                        ],
                        id="signal-feed-export-btn",
                        color="secondary",
                        size="sm",
                        outline=True,
                        style={"float": "right"},
                    ),
                ],
                style={
                    "marginBottom": "15px",
                    "overflow": "hidden",
                },
            ),
            # Signal cards container
            dcc.Loading(
                id="signal-feed-loading",
                type="circle",
                color=COLORS["accent"],
                children=html.Div(
                    id="signal-feed-cards-container",
                    children=[],
                ),
            ),
            # Load More button
            html.Div(
                id="signal-feed-load-more-container",
                children=[
                    dbc.Button(
                        [
                            html.I(className="fas fa-chevron-down me-2"),
                            COPY["signals_load_more"],
                        ],
                        id="signal-feed-load-more-btn",
                        color="secondary",
                        outline=True,
                        className="w-100 mt-3",
                    ),
                ],
            ),
        ],
        style={
            "padding": "20px",
            "maxWidth": "900px",
            "margin": "0 auto",
        },
    )


def register_signal_callbacks(app: Dash):
    """Register all callbacks for the signal feed page."""

    # 3.1 Main Feed Loader — fires on filter changes and refresh trigger
    @app.callback(
        [
            Output("signal-feed-cards-container", "children"),
            Output("signal-feed-count-label", "children"),
            Output("signal-feed-offset", "data"),
            Output("signal-feed-last-seen-ts", "data"),
            Output("signal-feed-load-more-container", "style"),
        ],
        [
            Input("signal-feed-sentiment-filter", "value"),
            Input("signal-feed-confidence-slider", "value"),
            Input("signal-feed-asset-filter", "value"),
            Input("signal-feed-outcome-filter", "value"),
            Input("signal-feed-refresh-trigger", "data"),
        ],
    )
    def update_signal_feed(
        sentiment, confidence_range, asset, outcome, refresh_trigger
    ):
        """Load or reload the signal feed with current filter values."""
        from data import get_signal_feed, get_signal_feed_count

        try:
            # Normalize filter values
            sentiment_val = sentiment if sentiment != "all" else None
            outcome_val = outcome if outcome != "all" else None
            conf_min = confidence_range[0] if confidence_range else None
            conf_max = confidence_range[1] if confidence_range else None

            if conf_min == 0 and conf_max == 1:
                conf_min = None
                conf_max = None

            df = get_signal_feed(
                limit=PAGE_SIZE,
                offset=0,
                sentiment_filter=sentiment_val,
                confidence_min=conf_min,
                confidence_max=conf_max,
                asset_filter=asset,
                outcome_filter=outcome_val,
            )

            total_count = get_signal_feed_count(
                sentiment_filter=sentiment_val,
                confidence_min=conf_min,
                confidence_max=conf_max,
                asset_filter=asset,
                outcome_filter=outcome_val,
            )

            if df.empty:
                empty_card = html.Div(
                    [
                        html.I(
                            className="fas fa-inbox",
                            style={
                                "fontSize": "2rem",
                                "color": COLORS["text_muted"],
                            },
                        ),
                        html.P(
                            COPY["signals_empty_filters"],
                            style={
                                "color": COLORS["text_muted"],
                                "marginTop": "10px",
                            },
                        ),
                    ],
                    style={"textAlign": "center", "padding": "40px"},
                )
                return [empty_card], COPY["signals_empty_filters"], 0, None, {"display": "none"}

            # Batch-fetch sparkline price data for all symbols in this page
            sparkline_prices = {}
            if not df.empty and "symbol" in df.columns:
                unique_symbols = df["symbol"].dropna().unique().tolist()
                if unique_symbols:
                    center_ts = pd.to_datetime(df["timestamp"]).median()
                    center_date = (
                        center_ts.strftime("%Y-%m-%d") if pd.notna(center_ts) else None
                    )
                    if center_date:
                        sparkline_prices = get_sparkline_prices(
                            symbols=tuple(sorted(unique_symbols)),
                            center_date=center_date,
                        )

            cards = [
                create_feed_signal_card(
                    row, card_index=idx, sparkline_prices=sparkline_prices
                )
                for idx, (_, row) in enumerate(df.iterrows())
            ]
            count_label = f"Showing {len(df)} of {total_count} signals"

            newest_ts = df["timestamp"].iloc[0]
            if isinstance(newest_ts, datetime):
                last_seen_ts = newest_ts.isoformat()
            else:
                last_seen_ts = str(newest_ts)

            load_more_style = (
                {"display": "block"}
                if total_count > PAGE_SIZE
                else {"display": "none"}
            )

            return cards, count_label, PAGE_SIZE, last_seen_ts, load_more_style

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error loading signal feed: {e}", exc_info=True)

            error_card = html.Div(
                [
                    html.I(
                        className="fas fa-exclamation-triangle",
                        style={
                            "fontSize": "2rem",
                            "color": COLORS["danger"],
                        },
                    ),
                    html.P(
                        COPY["signals_error"],
                        style={
                            "color": COLORS["text_muted"],
                            "marginTop": "10px",
                        },
                    ),
                ],
                style={"textAlign": "center", "padding": "40px"},
            )
            return [error_card], "Error loading signals", 0, None, {"display": "none"}

    # 3.2 Load More Button
    @app.callback(
        [
            Output(
                "signal-feed-cards-container", "children", allow_duplicate=True
            ),
            Output("signal-feed-offset", "data", allow_duplicate=True),
            Output(
                "signal-feed-count-label", "children", allow_duplicate=True
            ),
            Output(
                "signal-feed-load-more-container", "style", allow_duplicate=True
            ),
        ],
        [Input("signal-feed-load-more-btn", "n_clicks")],
        [
            State("signal-feed-cards-container", "children"),
            State("signal-feed-offset", "data"),
            State("signal-feed-sentiment-filter", "value"),
            State("signal-feed-confidence-slider", "value"),
            State("signal-feed-asset-filter", "value"),
            State("signal-feed-outcome-filter", "value"),
        ],
        prevent_initial_call=True,
    )
    def load_more_signals(
        n_clicks,
        existing_cards,
        current_offset,
        sentiment,
        confidence_range,
        asset,
        outcome,
    ):
        """Append the next page of signal cards to the feed."""
        from data import get_signal_feed, get_signal_feed_count

        if not n_clicks:
            raise PreventUpdate

        try:
            sentiment_val = sentiment if sentiment != "all" else None
            outcome_val = outcome if outcome != "all" else None
            conf_min = confidence_range[0] if confidence_range else None
            conf_max = confidence_range[1] if confidence_range else None

            if conf_min == 0 and conf_max == 1:
                conf_min = None
                conf_max = None

            df = get_signal_feed(
                limit=PAGE_SIZE,
                offset=current_offset,
                sentiment_filter=sentiment_val,
                confidence_min=conf_min,
                confidence_max=conf_max,
                asset_filter=asset,
                outcome_filter=outcome_val,
            )

            total_count = get_signal_feed_count(
                sentiment_filter=sentiment_val,
                confidence_min=conf_min,
                confidence_max=conf_max,
                asset_filter=asset,
                outcome_filter=outcome_val,
            )

            if df.empty:
                return (
                    existing_cards,
                    current_offset,
                    f"Showing all {current_offset} signals",
                    {"display": "none"},
                )

            # Batch-fetch sparkline price data for new page
            sparkline_prices = {}
            if not df.empty and "symbol" in df.columns:
                unique_symbols = df["symbol"].dropna().unique().tolist()
                if unique_symbols:
                    center_ts = pd.to_datetime(df["timestamp"]).median()
                    center_date = (
                        center_ts.strftime("%Y-%m-%d") if pd.notna(center_ts) else None
                    )
                    if center_date:
                        sparkline_prices = get_sparkline_prices(
                            symbols=tuple(sorted(unique_symbols)),
                            center_date=center_date,
                        )

            new_cards = [
                create_feed_signal_card(
                    row, card_index=current_offset + idx, sparkline_prices=sparkline_prices
                )
                for idx, (_, row) in enumerate(df.iterrows())
            ]
            updated_cards = (existing_cards or []) + new_cards

            new_offset = current_offset + len(df)
            count_label = f"Showing {new_offset} of {total_count} signals"

            load_more_style = (
                {"display": "block"}
                if new_offset < total_count
                else {"display": "none"}
            )

            return updated_cards, new_offset, count_label, load_more_style

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error loading more signals: {e}", exc_info=True)

            return (
                existing_cards,
                current_offset,
                "Error loading more signals",
                {"display": "none"},
            )

    # 3.3 New-Signals Polling
    @app.callback(
        [
            Output("new-signals-banner", "children"),
            Output("new-signals-banner", "style"),
        ],
        [Input("signal-feed-poll-interval", "n_intervals")],
        [State("signal-feed-last-seen-ts", "data")],
    )
    def check_for_new_signals(n_intervals, last_seen_ts):
        """Poll for new signals and show/hide the banner."""
        from data import get_new_signals_since

        if not last_seen_ts:
            return [], {"display": "none"}

        try:
            new_count = get_new_signals_since(last_seen_ts)

            if new_count > 0:
                banner = create_new_signals_banner(new_count)
                return [banner], {"display": "block"}
            else:
                return [], {"display": "none"}
        except Exception:
            return [], {"display": "none"}

    # 3.4 Show New Signals Button — triggers feed reload via refresh store
    @app.callback(
        Output("signal-feed-refresh-trigger", "data"),
        [Input("signal-feed-show-new-btn", "n_clicks")],
        [State("signal-feed-refresh-trigger", "data")],
        prevent_initial_call=True,
    )
    def trigger_feed_reload_on_show_new(n_clicks, current_value):
        """Force a feed reload when user clicks 'Show New Signals'."""
        if not n_clicks:
            raise PreventUpdate
        return (current_value or 0) + 1

    # 3.5 CSV Export
    @app.callback(
        Output("signal-feed-csv-download", "data"),
        [Input("signal-feed-export-btn", "n_clicks")],
        [
            State("signal-feed-sentiment-filter", "value"),
            State("signal-feed-confidence-slider", "value"),
            State("signal-feed-asset-filter", "value"),
            State("signal-feed-outcome-filter", "value"),
        ],
        prevent_initial_call=True,
    )
    def export_signal_feed_csv(
        n_clicks, sentiment, confidence_range, asset, outcome
    ):
        """Export the current filtered signal feed to a CSV file."""
        from data import get_signal_feed_csv

        if not n_clicks:
            raise PreventUpdate

        try:
            sentiment_val = sentiment if sentiment != "all" else None
            outcome_val = outcome if outcome != "all" else None
            conf_min = confidence_range[0] if confidence_range else None
            conf_max = confidence_range[1] if confidence_range else None

            if conf_min == 0 and conf_max == 1:
                conf_min = None
                conf_max = None

            export_df = get_signal_feed_csv(
                sentiment_filter=sentiment_val,
                confidence_min=conf_min,
                confidence_max=conf_max,
                asset_filter=asset,
                outcome_filter=outcome_val,
            )

            if export_df.empty:
                return None

            filename = f"shitpost_alpha_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return dcc.send_data_frame(export_df.to_csv, filename, index=False)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error exporting signal feed CSV: {e}", exc_info=True)
            return None

    # 3.6 Asset Filter Dropdown Population
    @app.callback(
        Output("signal-feed-asset-filter", "options"),
        [Input("signal-feed-poll-interval", "n_intervals")],
    )
    def populate_signal_feed_asset_filter(n_intervals):
        """Populate the asset filter dropdown with assets from the database."""
        from data import get_active_assets_from_db

        try:
            assets = get_active_assets_from_db()
            return [{"label": a, "value": a} for a in assets]
        except Exception:
            return []

    # 3.7 Thesis Expand/Collapse — clientside callback for zero-latency toggling
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks || n_clicks === 0) {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
            var isExpanded = (n_clicks % 2) === 1;
            if (isExpanded) {
                return [
                    {"display": "none"},
                    {"display": "block"},
                    "Hide thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(180deg)"}
                ];
            } else {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
        }
        """,
        [
            Output({"type": "thesis-preview", "index": MATCH}, "style"),
            Output({"type": "thesis-full", "index": MATCH}, "style"),
            Output({"type": "thesis-toggle-text", "index": MATCH}, "children"),
            Output({"type": "thesis-chevron", "index": MATCH}, "style"),
        ],
        [Input({"type": "thesis-toggle", "index": MATCH}, "n_clicks")],
    )
