"""Analytics chart callbacks.

Handles the analytics section: tab switching, chart rendering,
backtest controls visibility, and backtest summary display.
"""

import traceback

from dash import Dash, html, Input, Output, State
import dash_bootstrap_components as dbc

from constants import COLORS
from brand_copy import COPY
from components.charts import (
    build_cumulative_pnl_chart,
    build_rolling_accuracy_chart,
    build_confidence_calibration_chart,
    build_backtest_equity_chart,
    build_empty_signal_chart,
)
from data import (
    get_cumulative_pnl,
    get_rolling_accuracy,
    get_confidence_calibration,
    get_backtest_simulation,
    get_backtest_equity_curve,
)


def register_analytics_callbacks(app: Dash) -> None:
    """Register analytics chart callbacks.

    Args:
        app: The Dash application instance.
    """

    # ========== Collapse toggle ==========
    @app.callback(
        Output("collapse-analytics", "is_open"),
        [Input("collapse-analytics-button", "n_clicks")],
        [State("collapse-analytics", "is_open")],
    )
    def toggle_analytics_collapse(n_clicks, is_open):
        """Toggle the analytics section collapse."""
        if n_clicks:
            return not is_open
        return is_open

    # Chevron rotation (clientside)
    app.clientside_callback(
        """
        function(isOpen) {
            if (isOpen) {
                return 'fas fa-chevron-right me-2 collapse-chevron rotated';
            }
            return 'fas fa-chevron-right me-2 collapse-chevron';
        }
        """,
        Output("collapse-analytics-chevron", "className"),
        [Input("collapse-analytics", "is_open")],
    )

    # ========== Show/hide backtest controls based on active tab ==========
    @app.callback(
        [
            Output("backtest-controls-container", "style"),
            Output("backtest-summary-container", "style"),
        ],
        [Input("analytics-tabs", "active_tab")],
    )
    def toggle_backtest_controls(active_tab):
        """Show backtest controls only when backtest tab is active."""
        if active_tab == "tab-backtest":
            return (
                {"display": "block", "marginBottom": "16px"},
                {"display": "block"},
            )
        return (
            {"display": "none"},
            {"display": "none"},
        )

    # ========== Main chart rendering callback ==========
    @app.callback(
        [
            Output("analytics-chart", "figure"),
            Output("backtest-summary-container", "children"),
        ],
        [
            Input("analytics-tabs", "active_tab"),
            Input("selected-period", "data"),
            Input("collapse-analytics", "is_open"),
            Input("backtest-run-btn", "n_clicks"),
        ],
        [
            State("backtest-capital-input", "value"),
            State("backtest-confidence-slider", "value"),
        ],
    )
    def update_analytics_chart(
        active_tab, period, is_open, n_clicks, backtest_capital, backtest_confidence
    ):
        """Render the appropriate analytics chart based on active tab.

        Only fetches data when the analytics section is open to avoid
        unnecessary database queries.
        """
        # Don't fetch data if section is collapsed
        if not is_open:
            return build_empty_signal_chart("Expand to view analytics"), html.Div()

        # Convert period to days
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period, 90)

        backtest_summary = html.Div()  # Default empty

        try:
            if active_tab == "tab-pnl":
                df = get_cumulative_pnl(days=days)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_pnl"])
                else:
                    fig = build_cumulative_pnl_chart(df)

            elif active_tab == "tab-rolling":
                df = get_rolling_accuracy(window=30, days=days)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_rolling"])
                else:
                    fig = build_rolling_accuracy_chart(df)

            elif active_tab == "tab-calibration":
                df = get_confidence_calibration(buckets=10)
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_calibration"])
                else:
                    fig = build_confidence_calibration_chart(df)

            elif active_tab == "tab-backtest":
                capital = float(backtest_capital or 10000)
                confidence = float(backtest_confidence or 0.75)

                df = get_backtest_equity_curve(
                    initial_capital=capital,
                    min_confidence=confidence,
                    days=days,
                )
                if df.empty:
                    fig = build_empty_signal_chart(COPY["analytics_empty_backtest"])
                else:
                    fig = build_backtest_equity_chart(df, initial_capital=capital)

                # Also fetch the summary stats for the info panel
                summary = get_backtest_simulation(
                    initial_capital=capital,
                    min_confidence=confidence,
                    days=days if days is not None else 90,
                )
                backtest_summary = _build_backtest_summary(summary)

            else:
                fig = build_empty_signal_chart("Select a tab")

        except Exception as e:
            print(f"Error loading analytics chart: {traceback.format_exc()}")
            fig = build_empty_signal_chart(f"Error loading chart: {str(e)[:60]}")

        return fig, backtest_summary


def _build_backtest_summary(summary: dict) -> html.Div:
    """Build the backtest summary stats panel below the chart.

    Args:
        summary: Dict from get_backtest_simulation() with keys:
            initial_capital, final_value, total_return_pct,
            trade_count, wins, losses, win_rate.

    Returns:
        html.Div with a row of summary stats.
    """
    if summary["trade_count"] == 0:
        return html.Div()

    pnl = summary["final_value"] - summary["initial_capital"]
    pnl_color = COLORS["success"] if pnl >= 0 else COLORS["danger"]

    return dbc.Row(
        [
            _backtest_stat(
                f"${summary['final_value']:,.0f}",
                "Final Value",
                pnl_color,
            ),
            _backtest_stat(
                f"{summary['total_return_pct']:+.1f}%",
                "Total Return",
                pnl_color,
            ),
            _backtest_stat(
                f"{summary['trade_count']}",
                "Total Trades",
                COLORS["accent"],
            ),
            _backtest_stat(
                f"{summary['win_rate']:.1f}%",
                f"Win Rate ({summary['wins']}W / {summary['losses']}L)",
                COLORS["success"] if summary["win_rate"] > 50 else COLORS["danger"],
            ),
        ],
        className="g-2 mt-2",
    )


def _backtest_stat(value: str, label: str, color: str) -> dbc.Col:
    """Build a single backtest summary stat card.

    Args:
        value: Prominent display value.
        label: Description below the value.
        color: CSS color for the value.

    Returns:
        dbc.Col containing the stat card.
    """
    return dbc.Col(
        html.Div(
            [
                html.Div(
                    value,
                    style={
                        "fontSize": "1rem",
                        "fontWeight": "bold",
                        "color": color,
                    },
                ),
                html.Div(
                    label,
                    style={
                        "fontSize": "0.7rem",
                        "color": COLORS["text_muted"],
                    },
                ),
            ],
            style={
                "textAlign": "center",
                "padding": "8px",
                "backgroundColor": COLORS["bg"],
                "borderRadius": "8px",
                "border": f"1px solid {COLORS['border']}",
            },
        ),
        xs=6,
        md=3,
    )
