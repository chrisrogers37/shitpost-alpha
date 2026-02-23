"""Alert system callbacks and alert panel components."""

from datetime import datetime

from dash import Dash, html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc

from constants import COLORS
from data import get_available_assets
from alerts import (
    check_for_new_alerts,
    is_in_quiet_hours,
    dispatch_server_notifications,
)
from callbacks.alert_components import (
    build_master_toggle_section,
    build_status_indicator,
    build_confidence_threshold_section,
    build_asset_selection_section,
    build_sentiment_filter_section,
    build_notification_channels_section,
    build_quiet_hours_section,
    build_action_buttons_section,
)


def create_alert_config_panel():
    """
    Create the alert configuration slide-out panel.

    Returns a dbc.Offcanvas component that slides in from the right
    when the user clicks the bell icon in the header. Each section
    is built by a dedicated function in alert_components.py.
    """
    notification_channels = build_notification_channels_section()
    action_buttons = build_action_buttons_section()

    return dbc.Offcanvas(
        id="alert-config-offcanvas",
        title="Alert Configuration",
        placement="end",
        is_open=False,
        backdrop=True,
        scrollable=True,
        style={
            "backgroundColor": COLORS["primary"],
            "color": COLORS["text"],
            "width": "400px",
        },
        children=[
            build_master_toggle_section(),
            build_status_indicator(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Filter Settings ---
            html.H6(
                [
                    html.I(className="fas fa-filter me-2"),
                    "Filter Settings",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            build_confidence_threshold_section(),
            build_asset_selection_section(),
            build_sentiment_filter_section(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Notification Channels ---
            html.H6(
                [
                    html.I(className="fas fa-paper-plane me-2"),
                    "Notification Channels",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            *notification_channels,
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Quiet Hours ---
            html.H6(
                [
                    html.I(className="fas fa-moon me-2"),
                    "Quiet Hours",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            build_quiet_hours_section(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Save / Test Buttons ---
            *action_buttons,
        ],
    )


def create_alert_history_panel():
    """
    Create the alert history card for the main dashboard.

    Shows recent alerts with timestamp, prediction details,
    and whether they were triggered (matched preferences).
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    dbc.Button(
                        [
                            html.I(className="fas fa-history me-2"),
                            "Alert History",
                            html.Span(
                                id="alert-history-count-badge",
                                className="badge bg-primary ms-2",
                                children="0",
                            ),
                        ],
                        id="collapse-alert-history-button",
                        color="link",
                        className="text-white fw-bold p-0",
                    ),
                ],
                className="fw-bold",
            ),
            dbc.Collapse(
                dbc.CardBody(
                    id="alert-history-content",
                    style={"maxHeight": "400px", "overflowY": "auto"},
                ),
                id="collapse-alert-history",
                is_open=False,
            ),
        ],
        className="mt-4",
        style={"backgroundColor": COLORS["secondary"]},
    )


def build_preferences_dict(
    enabled: bool,
    min_confidence: float,
    assets: list,
    sentiment: str,
    browser_on: bool,
    email_on: bool,
    email_addr: str,
    sms_on: bool,
    sms_phone: str,
    quiet_on: bool,
    quiet_start: str,
    quiet_end: str,
) -> dict:
    """
    Assemble a preferences dict from individual form field values.

    This is the canonical shape of the preferences object stored
    in localStorage via alert-preferences-store.

    Args:
        enabled: Master toggle state.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        assets: List of ticker symbols to filter on.
        sentiment: Sentiment filter ("all", "bullish", "bearish", "neutral").
        browser_on: Whether browser notifications are enabled.
        email_on: Whether email notifications are enabled.
        email_addr: Email address for notifications.
        sms_on: Whether SMS notifications are enabled.
        sms_phone: Phone number for SMS notifications.
        quiet_on: Whether quiet hours are enabled.
        quiet_start: Quiet hours start time (HH:MM).
        quiet_end: Quiet hours end time (HH:MM).

    Returns:
        dict with all preference keys populated with safe defaults for None values.
    """
    return {
        "enabled": bool(enabled),
        "min_confidence": float(min_confidence or 0.7),
        "assets_of_interest": assets or [],
        "sentiment_filter": sentiment or "all",
        "browser_notifications": bool(browser_on),
        "email_enabled": bool(email_on),
        "email_address": email_addr or "",
        "sms_enabled": bool(sms_on),
        "sms_phone_number": sms_phone or "",
        "quiet_hours_enabled": bool(quiet_on),
        "quiet_hours_start": quiet_start or "22:00",
        "quiet_hours_end": quiet_end or "08:00",
        "max_alerts_per_hour": 10,
    }


def extract_preferences_tuple(prefs: dict) -> tuple:
    """
    Extract form field values from a preferences dict.

    Returns a 12-element tuple matching the Output order of
    load_preferences_into_form().

    Args:
        prefs: Preferences dict from localStorage.

    Returns:
        Tuple of (enabled, min_confidence, assets, sentiment,
        browser_on, email_on, email_addr, sms_on, sms_phone,
        quiet_on, quiet_start, quiet_end).
    """
    return (
        prefs.get("enabled", False),
        prefs.get("min_confidence", 0.7),
        prefs.get("assets_of_interest", []),
        prefs.get("sentiment_filter", "all"),
        prefs.get("browser_notifications", True),
        prefs.get("email_enabled", False),
        prefs.get("email_address", ""),
        prefs.get("sms_enabled", False),
        prefs.get("sms_phone_number", ""),
        prefs.get("quiet_hours_enabled", False),
        prefs.get("quiet_hours_start", "22:00"),
        prefs.get("quiet_hours_end", "08:00"),
    )


def build_alert_history_card(alert: dict) -> html.Div:
    """
    Build a single alert history card from an alert dict.

    Handles sentiment coloring, timestamp formatting, text truncation,
    and asset display.

    Args:
        alert: Dict with keys: sentiment, confidence, assets, text,
               alert_triggered_at.

    Returns:
        html.Div component for one alert history entry.
    """
    sentiment = alert.get("sentiment", "neutral")
    confidence = alert.get("confidence", 0)
    assets = alert.get("assets", [])
    text = alert.get("text", "")[:120]
    triggered_at = alert.get("alert_triggered_at", "")

    # Sentiment styling
    if sentiment == "bullish":
        sentiment_color = COLORS["success"]
        sentiment_icon = "arrow-up"
    elif sentiment == "bearish":
        sentiment_color = COLORS["danger"]
        sentiment_icon = "arrow-down"
    else:
        sentiment_color = COLORS["text_muted"]
        sentiment_icon = "minus"

    # Format timestamp
    try:
        ts = datetime.fromisoformat(triggered_at.replace("Z", "+00:00"))
        time_str = ts.strftime("%b %d, %H:%M")
    except (ValueError, TypeError, AttributeError):
        time_str = str(triggered_at)[:16]

    asset_str = (
        ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        time_str,
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                    html.Span(
                        [
                            html.I(className=f"fas fa-{sentiment_icon} me-1"),
                            sentiment.upper(),
                        ],
                        style={
                            "color": sentiment_color,
                            "fontSize": "0.75rem",
                            "fontWeight": "bold",
                        },
                        className="ms-2",
                    ),
                    html.Span(
                        f" | {confidence:.0%}" if confidence else "",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                ],
                className="d-flex align-items-center mb-1",
            ),
            html.P(
                text + "..." if len(text) >= 120 else text,
                style={
                    "fontSize": "0.8rem",
                    "margin": "3px 0",
                    "lineHeight": "1.3",
                    "color": COLORS["text"],
                },
            ),
            html.Div(
                [
                    html.Span(
                        f"Assets: {asset_str}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                ]
            ),
        ],
        style={
            "padding": "10px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def register_alert_callbacks(app: Dash):
    """Register all alert-related callbacks."""
    from dash import no_update

    # --- Open/Close the alert config offcanvas ---
    @app.callback(
        Output("alert-config-offcanvas", "is_open"),
        [Input("open-alert-config-button", "n_clicks")],
        [State("alert-config-offcanvas", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_alert_config(n_clicks: int, is_open: bool) -> bool:
        """Toggle the alert configuration panel open/closed."""
        if n_clicks:
            return not is_open
        return is_open

    # --- Show/hide email input ---
    @app.callback(
        Output("email-input-collapse", "is_open"),
        [Input("alert-email-toggle", "value")],
    )
    def toggle_email_input(email_enabled: bool) -> bool:
        """Show email input when email alerts are enabled."""
        return bool(email_enabled)

    # --- Show/hide SMS input ---
    @app.callback(
        Output("sms-input-collapse", "is_open"),
        [Input("alert-sms-toggle", "value")],
    )
    def toggle_sms_input(sms_enabled: bool) -> bool:
        """Show SMS input when SMS alerts are enabled."""
        return bool(sms_enabled)

    # --- Show/hide quiet hours inputs ---
    @app.callback(
        Output("quiet-hours-collapse", "is_open"),
        [Input("alert-quiet-hours-toggle", "value")],
    )
    def toggle_quiet_hours(quiet_enabled: bool) -> bool:
        """Show quiet hours time inputs when quiet hours are enabled."""
        return bool(quiet_enabled)

    # --- Update confidence threshold display ---
    @app.callback(
        Output("confidence-threshold-display", "children"),
        [Input("alert-confidence-slider", "value")],
    )
    def update_confidence_display(value: float) -> str:
        """Display the confidence slider value as a percentage."""
        return f"{int(value * 100)}%"

    # --- Update alert status indicator ---
    @app.callback(
        Output("alert-status-indicator", "children"),
        [Input("alert-master-toggle", "value")],
    )
    def update_alert_status(enabled: bool):
        """Update the status indicator when alerts are toggled."""
        if enabled:
            return [
                html.I(
                    className="fas fa-circle me-2",
                    style={"color": COLORS["success"], "fontSize": "0.6rem"},
                ),
                html.Span(
                    "Alerts active - checking every 2 minutes",
                    style={"color": COLORS["success"], "fontSize": "0.85rem"},
                ),
            ]
        return [
            html.I(
                className="fas fa-circle me-2",
                style={"color": COLORS["danger"], "fontSize": "0.6rem"},
            ),
            html.Span(
                "Alerts disabled",
                style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
            ),
        ]

    # --- Populate asset dropdown from DB ---
    @app.callback(
        Output("alert-assets-dropdown", "options"),
        [Input("alert-config-offcanvas", "is_open")],
    )
    def populate_alert_assets(is_open: bool):
        """Populate the assets dropdown when the panel opens."""
        if not is_open:
            return no_update
        available_assets = get_available_assets()
        return [{"label": asset, "value": asset} for asset in available_assets]

    # --- Save preferences to localStorage ---
    @app.callback(
        [
            Output("alert-preferences-store", "data"),
            Output("alert-save-toast", "is_open"),
        ],
        [Input("save-alert-prefs-button", "n_clicks")],
        [
            State("alert-master-toggle", "value"),
            State("alert-confidence-slider", "value"),
            State("alert-assets-dropdown", "value"),
            State("alert-sentiment-radio", "value"),
            State("alert-browser-toggle", "value"),
            State("alert-email-toggle", "value"),
            State("alert-email-input", "value"),
            State("alert-sms-toggle", "value"),
            State("alert-sms-input", "value"),
            State("alert-quiet-hours-toggle", "value"),
            State("quiet-hours-start", "value"),
            State("quiet-hours-end", "value"),
        ],
        prevent_initial_call=True,
    )
    def save_alert_preferences(
        n_clicks: int,
        enabled: bool,
        min_confidence: float,
        assets: list,
        sentiment: str,
        browser_on: bool,
        email_on: bool,
        email_addr: str,
        sms_on: bool,
        sms_phone: str,
        quiet_on: bool,
        quiet_start: str,
        quiet_end: str,
    ):
        """
        Gather all form values and write them to the localStorage-backed store.
        Also show a confirmation toast.
        """
        preferences = build_preferences_dict(
            enabled, min_confidence, assets, sentiment,
            browser_on, email_on, email_addr,
            sms_on, sms_phone,
            quiet_on, quiet_start, quiet_end,
        )
        return preferences, True  # True opens the toast

    # --- Load preferences into form when panel opens ---
    @app.callback(
        [
            Output("alert-master-toggle", "value"),
            Output("alert-confidence-slider", "value"),
            Output("alert-assets-dropdown", "value"),
            Output("alert-sentiment-radio", "value"),
            Output("alert-browser-toggle", "value"),
            Output("alert-email-toggle", "value"),
            Output("alert-email-input", "value"),
            Output("alert-sms-toggle", "value"),
            Output("alert-sms-input", "value"),
            Output("alert-quiet-hours-toggle", "value"),
            Output("quiet-hours-start", "value"),
            Output("quiet-hours-end", "value"),
        ],
        [Input("alert-config-offcanvas", "is_open")],
        [State("alert-preferences-store", "data")],
    )
    def load_preferences_into_form(is_open: bool, prefs: dict):
        """When the offcanvas opens, populate form fields from stored preferences."""
        if not is_open or not prefs:
            return (no_update,) * 12

        return extract_preferences_tuple(prefs)

    # --- Enable/disable alert check interval based on master toggle ---
    app.clientside_callback(
        """
        function(prefs) {
            if (prefs && prefs.enabled) {
                return false;  // disabled=false means interval IS running
            }
            return true;  // disabled=true means interval is NOT running
        }
        """,
        Output("alert-check-interval", "disabled"),
        Input("alert-preferences-store", "data"),
    )

    # --- Request browser notification permission ---
    app.clientside_callback(
        """
        function(browserToggle) {
            if (!browserToggle) {
                return "Browser notifications disabled.";
            }

            if (!("Notification" in window)) {
                return "Browser does not support notifications.";
            }

            if (Notification.permission === "granted") {
                return "Permission granted. Notifications active.";
            }

            if (Notification.permission === "denied") {
                return "Permission denied. Enable in browser settings.";
            }

            // Permission is "default" - request it
            Notification.requestPermission().then(function(permission) {
                console.log("Notification permission:", permission);
            });

            return "Requesting permission...";
        }
        """,
        Output("browser-notification-status", "children"),
        Input("alert-browser-toggle", "value"),
    )

    # --- Show browser notification when alert fires ---
    app.clientside_callback(
        """
        function(notificationData) {
            if (!notificationData) {
                return window.dash_clientside.no_update;
            }

            // Check if browser notifications are supported and permitted
            if (!("Notification" in window)) {
                console.warn("Browser does not support notifications");
                return window.dash_clientside.no_update;
            }

            if (Notification.permission !== "granted") {
                console.warn("Notification permission not granted:", Notification.permission);
                return window.dash_clientside.no_update;
            }

            // Build notification content
            var sentiment = (notificationData.sentiment || "neutral").toUpperCase();
            var confidence = notificationData.confidence
                ? (notificationData.confidence * 100).toFixed(0) + "%"
                : "N/A";
            var assets = Array.isArray(notificationData.assets)
                ? notificationData.assets.slice(0, 3).join(", ")
                : "Unknown";
            var text = notificationData.text || "";
            var body = sentiment + " (" + confidence + " confidence)\\n"
                     + "Assets: " + assets + "\\n"
                     + text.substring(0, 100) + "...";

            // Create the notification
            try {
                var notification = new Notification("Shitpost Alpha Alert", {
                    body: body,
                    icon: "/assets/favicon.ico",
                    badge: "/assets/favicon.ico",
                    tag: "shitpost-alert-" + (notificationData.prediction_id || Date.now()),
                    requireInteraction: false,
                    silent: false,
                });

                // Close after 10 seconds
                setTimeout(function() {
                    notification.close();
                }, 10000);

                // Focus dashboard on click
                notification.onclick = function(event) {
                    event.preventDefault();
                    window.focus();
                    notification.close();
                };

                console.log("Notification sent:", notificationData.prediction_id);
            } catch (err) {
                console.error("Failed to create notification:", err);
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("alert-notification-store", "data", allow_duplicate=True),
        Input("alert-notification-store", "data"),
        prevent_initial_call=True,
    )

    # --- Send test alert ---
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) {
                return window.dash_clientside.no_update;
            }

            if (!("Notification" in window)) {
                alert("Browser does not support notifications.");
                return window.dash_clientside.no_update;
            }

            if (Notification.permission !== "granted") {
                Notification.requestPermission();
                return window.dash_clientside.no_update;
            }

            var notification = new Notification("Shitpost Alpha - Test Alert", {
                body: "BULLISH (85% confidence)\\nAssets: AAPL, TSLA\\nThis is a test notification. Your alerts are working!",
                icon: "/assets/favicon.ico",
                tag: "shitpost-test-alert",
            });

            setTimeout(function() { notification.close(); }, 8000);

            return window.dash_clientside.no_update;
        }
        """,
        Output("alert-notification-store", "data", allow_duplicate=True),
        Input("test-alert-button", "n_clicks"),
        prevent_initial_call=True,
    )

    # --- Main alert check callback ---
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
        """
        Periodically check for new predictions that match alert preferences.
        Triggered by alert-check-interval (every 2 minutes when enabled).
        """
        if not preferences or not preferences.get("enabled", False):
            return no_update, no_update, no_update

        # Check quiet hours
        if is_in_quiet_hours(preferences):
            # Still update last_check to avoid alert flood after quiet hours
            return None, alert_history, datetime.utcnow().isoformat()

        # Run the alert check
        result = check_for_new_alerts(preferences, last_check)

        matched_alerts = result["matched_alerts"]
        new_last_check = result["last_check"]

        if not matched_alerts:
            return None, alert_history, new_last_check

        # Append matched alerts to history (keep last 100)
        updated_history = (alert_history or []) + matched_alerts
        updated_history = updated_history[-100:]  # Keep most recent 100

        # Dispatch server-side notifications (email, SMS)
        for alert in matched_alerts:
            dispatch_server_notifications(alert, preferences)

        # Return the first matched alert to trigger browser notification
        notification_data = matched_alerts[0] if matched_alerts else None

        return notification_data, updated_history, new_last_check

    # --- Toggle alert history collapse ---
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

    # --- Render alert history ---
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

    # --- Clear alert history ---
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

    # --- Update bell icon badge count ---
    app.clientside_callback(
        """
        function(history) {
            if (!history || history.length === 0) {
                return {"display": "none"};
            }
            // Show count of alerts in last 24 hours
            var now = new Date();
            var oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            var recentCount = 0;
            for (var i = 0; i < history.length; i++) {
                var alertTime = new Date(history[i].alert_triggered_at);
                if (alertTime > oneDayAgo) {
                    recentCount++;
                }
            }
            if (recentCount === 0) {
                return {"display": "none"};
            }
            return {"display": "inline", "fontSize": "0.6rem"};
        }
        """,
        Output("alert-badge", "style"),
        Input("alert-history-store", "data"),
    )

    app.clientside_callback(
        """
        function(history) {
            if (!history || history.length === 0) {
                return "";
            }
            var now = new Date();
            var oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            var recentCount = 0;
            for (var i = 0; i < history.length; i++) {
                var alertTime = new Date(history[i].alert_triggered_at);
                if (alertTime > oneDayAgo) {
                    recentCount++;
                }
            }
            return recentCount > 0 ? String(recentCount) : "";
        }
        """,
        Output("alert-badge", "children"),
        Input("alert-history-store", "data"),
    )

