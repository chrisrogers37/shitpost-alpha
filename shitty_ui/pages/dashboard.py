"""Dashboard page layout and callbacks."""

from datetime import datetime
import traceback

import dash
from dash import (
    Dash,
    html,
    dcc,
    dash_table,
    Input,
    Output,
    State,
    callback_context,
    MATCH,
)
import dash_bootstrap_components as dbc
import pandas as pd

from constants import COLORS, HIERARCHY
from components.cards import (
    create_error_card,
    create_metric_card,
    create_post_card,
)
from components.controls import create_filter_controls, get_period_button_styles
from components.header import create_header, create_footer
from brand_copy import COPY
from data import (
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_predictions_with_outcomes,
    load_recent_posts,
    get_dashboard_kpis_with_fallback,
    get_dynamic_insights,
)
from components.screener import build_screener_table
from components.insights import create_insight_cards


def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    return html.Div(
        [
            # Header with navigation
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
    """Register all dashboard-specific callbacks."""

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
            Output("insight-cards-container", "children"),
            Output("screener-table-container", "children"),
            Output("performance-metrics", "children"),
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

        # ===== Dynamic Insight Cards =====
        try:
            insight_pool = get_dynamic_insights(days=days)
            insight_cards = create_insight_cards(insight_pool, max_cards=3)
        except Exception as e:
            errors.append(f"Insight cards: {e}")
            print(f"Error loading insight cards: {traceback.format_exc()}")
            insight_cards = html.Div()  # Silent failure -- insights are not critical

        # ===== Asset Screener Table =====
        try:
            screener_df = get_asset_screener_data(days=days)
            sparkline_data = {}
            if not screener_df.empty:
                symbols = tuple(screener_df["symbol"].tolist())
                sparkline_data = get_screener_sparkline_prices(symbols=symbols)

            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
            )
        except Exception as e:
            errors.append(f"Asset screener: {e}")
            print(f"Error loading asset screener: {traceback.format_exc()}")
            screener_table = create_error_card("Unable to load asset screener", str(e))

        # ===== Performance Metrics with error handling =====
        try:
            kpis = get_dashboard_kpis_with_fallback(days=days)
            fallback_note = kpis["fallback_label"] if kpis["is_fallback"] else ""

            # Create KPI metrics row
            metrics_row = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_total_signals_title"],
                            f"{kpis['total_signals']}",
                            COPY["kpi_total_signals_subtitle"],
                            "signal",
                            COLORS["accent"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_accuracy_title"],
                            f"{kpis['accuracy_pct']:.1f}%",
                            COPY["kpi_accuracy_subtitle"],
                            "bullseye",
                            COLORS["success"]
                            if kpis["accuracy_pct"] > 50
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_avg_return_title"],
                            f"{kpis['avg_return_t7']:+.2f}%",
                            COPY["kpi_avg_return_subtitle"],
                            "chart-line",
                            COLORS["success"]
                            if kpis["avg_return_t7"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_pnl_title"],
                            f"${kpis['total_pnl']:+,.0f}",
                            COPY["kpi_pnl_subtitle"],
                            "dollar-sign",
                            COLORS["success"]
                            if kpis["total_pnl"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                ],
                className="g-2 g-md-2",
            )
        except Exception as e:
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )

        # Log any errors that occurred
        if errors:
            print(f"Dashboard update completed with errors: {errors}")

        return (
            insight_cards,
            screener_table,
            metrics_row,
            current_time,
        )

    # ========== Post Feed Callback ==========
    @app.callback(
        Output("post-feed-container", "children"),
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
    def update_post_feed(n_intervals, period):
        """Update the Latest Posts feed with posts and their LLM analysis."""
        try:
            df = load_recent_posts(limit=20)

            if df.empty:
                return html.P(
                    COPY["empty_posts"],
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )

            post_cards = [
                create_post_card(row, card_index=idx)
                for idx, (_, row) in enumerate(df.iterrows())
            ]
            return post_cards

        except Exception as e:
            print(f"Error loading post feed: {traceback.format_exc()}")
            return create_error_card("Unable to load post feed", str(e))

    # ========== Screener Row Click Handler ==========
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        [Input({"type": "screener-row", "index": dash.ALL}, "n_clicks")],
        prevent_initial_call=True,
    )
    def handle_screener_row_click(n_clicks_list):
        """Navigate to asset page when a screener row is clicked."""
        import json
        from dash import no_update

        if not any(n_clicks_list):
            return no_update

        ctx = callback_context
        if not ctx.triggered:
            return no_update

        triggered_id = ctx.triggered[0]["prop_id"]
        try:
            id_str = triggered_id.split(".")[0]
            id_dict = json.loads(id_str)
            symbol = id_dict["index"]
            return f"/assets/{symbol}"
        except (json.JSONDecodeError, KeyError):
            return no_update

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

    # Chevron rotation for collapsible sections
    app.clientside_callback(
        """
        function(isOpen) {
            if (isOpen) {
                return 'fas fa-chevron-right me-2 collapse-chevron rotated';
            }
            return 'fas fa-chevron-right me-2 collapse-chevron';
        }
        """,
        Output("collapse-table-chevron", "className"),
        [Input("collapse-table", "is_open")],
    )

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
            # Extract confidence range from slider
            conf_min = confidence_range[0] if confidence_range else None
            conf_max = confidence_range[1] if confidence_range else None

            # Only pass confidence filters if they differ from full range
            if conf_min == 0:
                conf_min = None
            if conf_max == 1:
                conf_max = None

            df = get_predictions_with_outcomes(
                limit=limit or 50,
                confidence_min=conf_min,
                confidence_max=conf_max,
                start_date=start_date,
                end_date=end_date,
            )

            if df.empty:
                return html.P(
                    COPY["empty_predictions_table"],
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
                    lambda x: (
                        ", ".join(x[:3]) + (f" +{len(x) - 3}" if len(x) > 3 else "")
                        if isinstance(x, list)
                        else str(x)
                    )
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
                    lambda x: (
                        "Correct"
                        if x is True
                        else "Incorrect"
                        if x is False
                        else "Pending"
                    )
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

    # Post-card thesis expand/collapse — clientside callback
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
            Output({"type": "post-thesis-preview", "index": MATCH}, "style"),
            Output({"type": "post-thesis-full", "index": MATCH}, "style"),
            Output({"type": "post-thesis-toggle-text", "index": MATCH}, "children"),
            Output({"type": "post-thesis-chevron", "index": MATCH}, "style"),
        ],
        [Input({"type": "post-thesis-toggle", "index": MATCH}, "n_clicks")],
    )
