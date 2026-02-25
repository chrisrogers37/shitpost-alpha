"""Data table management callbacks.

Handles screener row clicks, collapse toggling, predictions table
filtering, and thesis expand/collapse.
"""

import traceback

import dash
from dash import (
    Dash,
    html,
    dash_table,
    Input,
    Output,
    State,
    callback_context,
    MATCH,
    no_update,
)
import pandas as pd

from constants import COLORS
from components.cards import create_error_card
from brand_copy import COPY
from data import get_predictions_with_outcomes


def register_table_callbacks(app: Dash) -> None:
    """Register data table management callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        [Input({"type": "screener-row", "index": dash.ALL}, "n_clicks")],
        prevent_initial_call=True,
    )
    def handle_screener_row_click(n_clicks_list):
        """Navigate to asset page when a screener row is clicked."""
        import json

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

    # Post-card thesis expand/collapse -- clientside callback
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
