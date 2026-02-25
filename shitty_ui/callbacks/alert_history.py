"""Alert history and periodic check callbacks.

Handles:
- Toggling alert history collapse
- Rendering alert history cards
- Clearing alert history
- The main periodic alert check (run_alert_check)
"""

from datetime import datetime

from dash import Dash, html, Input, Output, State, no_update

from constants import COLORS
from alerts import (
    check_for_new_alerts,
    is_in_quiet_hours,
    dispatch_server_notifications,
)
from callbacks.alerts import build_alert_history_card


def register_alert_history_callbacks(app: Dash) -> None:
    """Register all alert-history-related callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("alert-notification-store", "data"),
            Output("alert-history-store", "data"),
            Output("last-alert-check-store", "data"),
        ],
        [Input("alert-check-interval", "n_intervals")],
        [
            State("alert-preferences-store", "data"),
            State("last-alert-check-store", "data"),
            State("alert-history-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def run_alert_check(
        n_intervals: int,
        preferences: dict,
        last_check: str,
        alert_history: list,
    ):
        """Periodically check for new predictions that match alert preferences."""
        if not preferences or not preferences.get("enabled", False):
            return no_update, no_update, no_update

        if is_in_quiet_hours(preferences):
            return None, alert_history, datetime.utcnow().isoformat()

        result = check_for_new_alerts(preferences, last_check)
        matched_alerts = result["matched_alerts"]
        new_last_check = result["last_check"]

        if not matched_alerts:
            return None, alert_history, new_last_check

        updated_history = (alert_history or []) + matched_alerts
        updated_history = updated_history[-100:]

        for alert in matched_alerts:
            dispatch_server_notifications(alert, preferences)

        notification_data = matched_alerts[0] if matched_alerts else None
        return notification_data, updated_history, new_last_check

    @app.callback(
        Output("collapse-alert-history", "is_open"),
        [Input("collapse-alert-history-button", "n_clicks")],
        [State("collapse-alert-history", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_alert_history(n_clicks: int, is_open: bool) -> bool:
        """Toggle the alert history panel open/closed."""
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        [
            Output("alert-history-content", "children"),
            Output("alert-history-count-badge", "children"),
        ],
        [
            Input("collapse-alert-history", "is_open"),
            Input("alert-history-store", "data"),
        ],
    )
    def render_alert_history(is_open: bool, history: list):
        """Render the alert history list from localStorage data."""
        if not history:
            return (
                html.P(
                    "No alerts triggered yet. Enable alerts and set your preferences.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                ),
                "0",
            )

        count = len(history)
        alert_cards = [
            build_alert_history_card(alert) for alert in reversed(history[-50:])
        ]
        return alert_cards, str(count)

    @app.callback(
        Output("alert-history-store", "data", allow_duplicate=True),
        [Input("clear-alert-history-button", "n_clicks")],
        prevent_initial_call=True,
    )
    def clear_alert_history(n_clicks: int) -> list:
        """Clear all alert history from localStorage."""
        if n_clicks:
            return []
        return no_update
