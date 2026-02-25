"""Main dashboard content rendering callbacks.

Handles the primary dashboard update (insights, screener, KPIs)
and the post feed update.
"""

import traceback
from datetime import datetime

from dash import Dash, html, Input, Output
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import (
    create_error_card,
    create_metric_card,
    create_post_card,
)
from brand_copy import COPY
from data import (
    get_asset_screener_data,
    get_screener_sparkline_prices,
    load_recent_posts,
    get_dashboard_kpis_with_fallback,
    get_dynamic_insights,
)
from components.screener import build_screener_table
from components.insights import create_insight_cards


def register_content_callbacks(app: Dash) -> None:
    """Register main dashboard content callbacks.

    Args:
        app: The Dash application instance.
    """

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
