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


def create_alert_config_panel():
    """
    Create the alert configuration slide-out panel.

    Returns a dbc.Offcanvas component that slides in from the right
    when the user clicks the bell icon in the header.
    """
    return dbc.Offcanvas(
        id="alert-config-offcanvas",
        title="Alert Configuration",
        placement="end",  # Slide in from the right
        is_open=False,
        backdrop=True,
        scrollable=True,
        style={
            "backgroundColor": COLORS["primary"],
            "color": COLORS["text"],
            "width": "400px",
        },
        children=[
            # Master toggle
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-power-off me-2",
                                style={"color": COLORS["accent"]},
                            ),
                            html.Span(
                                "Enable Alerts",
                                style={"fontWeight": "bold", "fontSize": "1rem"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    dbc.Switch(
                        id="alert-master-toggle",
                        value=False,
                        className="ms-auto",
                        style={"transform": "scale(1.3)"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "20px",
                },
            ),
            # Alert status indicator
            html.Div(
                id="alert-status-indicator",
                children=[
                    html.I(
                        className="fas fa-circle me-2",
                        style={"color": COLORS["danger"], "fontSize": "0.6rem"},
                    ),
                    html.Span(
                        "Alerts disabled",
                        style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
                    ),
                ],
                style={"marginBottom": "20px", "textAlign": "center"},
            ),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Filter Settings ---
            html.H6(
                [
                    html.I(className="fas fa-filter me-2"),
                    "Filter Settings",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            # Minimum confidence threshold
            html.Div(
                [
                    html.Label(
                        "Minimum Confidence",
                        style={
                            "color": COLORS["text"],
                            "fontWeight": "500",
                            "fontSize": "0.9rem",
                        },
                    ),
                    html.Div(
                        id="confidence-threshold-display",
                        children="70%",
                        style={
                            "color": COLORS["accent"],
                            "fontWeight": "bold",
                            "fontSize": "0.9rem",
                            "float": "right",
                        },
                    ),
                    dcc.Slider(
                        id="alert-confidence-slider",
                        min=0.0,
                        max=1.0,
                        step=0.05,
                        value=0.7,
                        marks={
                            0.0: {
                                "label": "0%",
                                "style": {"color": COLORS["text_muted"]},
                            },
                            0.5: {
                                "label": "50%",
                                "style": {"color": COLORS["text_muted"]},
                            },
                            0.7: {
                                "label": "70%",
                                "style": {"color": COLORS["warning"]},
                            },
                            1.0: {
                                "label": "100%",
                                "style": {"color": COLORS["text_muted"]},
                            },
                        },
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                    html.Small(
                        "Only alert when prediction confidence is at or above this level.",
                        style={"color": COLORS["text_muted"]},
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            # Assets of interest
            html.Div(
                [
                    html.Label(
                        "Assets of Interest",
                        style={
                            "color": COLORS["text"],
                            "fontWeight": "500",
                            "fontSize": "0.9rem",
                        },
                    ),
                    dcc.Dropdown(
                        id="alert-assets-dropdown",
                        options=[],  # Populated by callback from DB
                        value=[],
                        multi=True,
                        placeholder="All assets (leave empty for all)",
                        style={
                            "backgroundColor": COLORS["primary"],
                            "color": COLORS["text"],
                        },
                        className="mb-1",
                    ),
                    html.Small(
                        "Leave empty to receive alerts for all assets. Select specific tickers to filter.",
                        style={"color": COLORS["text_muted"]},
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            # Sentiment filter
            html.Div(
                [
                    html.Label(
                        "Sentiment Filter",
                        style={
                            "color": COLORS["text"],
                            "fontWeight": "500",
                            "fontSize": "0.9rem",
                        },
                    ),
                    dbc.RadioItems(
                        id="alert-sentiment-radio",
                        options=[
                            {"label": " All Sentiments", "value": "all"},
                            {"label": " Bullish Only", "value": "bullish"},
                            {"label": " Bearish Only", "value": "bearish"},
                            {"label": " Neutral Only", "value": "neutral"},
                        ],
                        value="all",
                        inline=False,
                        style={"color": COLORS["text"]},
                        labelStyle={
                            "display": "block",
                            "padding": "6px 0",
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                style={"marginBottom": "20px"},
            ),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Notification Channels ---
            html.H6(
                [
                    html.I(className="fas fa-paper-plane me-2"),
                    "Notification Channels",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            # Browser notifications toggle
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-globe me-2",
                                style={"color": COLORS["text_muted"]},
                            ),
                            html.Span(
                                "Browser Notifications", style={"fontSize": "0.9rem"}
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    dbc.Switch(
                        id="alert-browser-toggle",
                        value=True,
                        className="ms-auto",
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "10px 15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "10px",
                },
            ),
            # Browser notification permission status
            html.Div(
                id="browser-notification-status",
                style={"marginBottom": "15px", "fontSize": "0.8rem"},
            ),
            # Email notifications
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-envelope me-2",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                    html.Span(
                                        "Email Notifications",
                                        style={"fontSize": "0.9rem"},
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            dbc.Switch(
                                id="alert-email-toggle",
                                value=False,
                                className="ms-auto",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                        },
                    ),
                    # Email input (shown only when email is enabled)
                    dbc.Collapse(
                        dbc.Input(
                            id="alert-email-input",
                            type="email",
                            placeholder="your@email.com",
                            className="mt-2",
                            style={
                                "backgroundColor": COLORS["primary"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                            },
                        ),
                        id="email-input-collapse",
                        is_open=False,
                    ),
                ],
                style={
                    "padding": "10px 15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "10px",
                },
            ),
            # SMS notifications
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-sms me-2",
                                        style={"color": COLORS["text_muted"]},
                                    ),
                                    html.Span(
                                        "SMS Notifications",
                                        style={"fontSize": "0.9rem"},
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            dbc.Switch(
                                id="alert-sms-toggle",
                                value=False,
                                className="ms-auto",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                        },
                    ),
                    # Phone input (shown only when SMS is enabled)
                    dbc.Collapse(
                        html.Div(
                            [
                                dbc.Input(
                                    id="alert-sms-input",
                                    type="tel",
                                    placeholder="+1 (555) 123-4567",
                                    className="mt-2",
                                    style={
                                        "backgroundColor": COLORS["primary"],
                                        "color": COLORS["text"],
                                        "border": f"1px solid {COLORS['border']}",
                                    },
                                ),
                                html.Small(
                                    "Enter phone number in E.164 format (e.g., +15551234567).",
                                    className="mt-1",
                                    style={"color": COLORS["text_muted"]},
                                ),
                            ]
                        ),
                        id="sms-input-collapse",
                        is_open=False,
                    ),
                ],
                style={
                    "padding": "10px 15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "10px",
                },
            ),
            # Telegram notifications (multi-tenant via bot)
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fab fa-telegram me-2",
                                        style={"color": "#0088cc"},
                                    ),
                                    html.Span(
                                        "Telegram Notifications",
                                        style={
                                            "fontSize": "0.9rem",
                                            "fontWeight": "bold",
                                        },
                                    ),
                                    html.Span(
                                        " (Free!)",
                                        style={
                                            "fontSize": "0.75rem",
                                            "color": COLORS["success"],
                                            "marginLeft": "5px",
                                        },
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.P(
                                [
                                    "Get unlimited free alerts via Telegram! ",
                                    "Add our bot to receive predictions directly in your chat.",
                                ],
                                style={
                                    "fontSize": "0.85rem",
                                    "color": COLORS["text_muted"],
                                    "margin": "10px 0",
                                },
                            ),
                            html.Div(
                                [
                                    html.A(
                                        [
                                            html.I(className="fab fa-telegram me-2"),
                                            "Open @ShitpostAlphaBot",
                                        ],
                                        href="https://t.me/ShitpostAlphaBot",
                                        target="_blank",
                                        className="btn btn-info btn-sm",
                                        style={
                                            "backgroundColor": "#0088cc",
                                            "border": "none",
                                            "color": "white",
                                        },
                                    ),
                                ],
                                className="mb-2",
                            ),
                            html.Small(
                                [
                                    "1. Click the link above to open the bot",
                                    html.Br(),
                                    "2. Send /start to subscribe",
                                    html.Br(),
                                    "3. Use /settings to customize your alerts",
                                ],
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.75rem",
                                    "lineHeight": "1.5",
                                },
                            ),
                        ]
                    ),
                ],
                style={
                    "padding": "10px 15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "10px",
                    "border": "1px solid #0088cc33",
                },
            ),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Quiet Hours ---
            html.H6(
                [
                    html.I(className="fas fa-moon me-2"),
                    "Quiet Hours",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                "Enable Quiet Hours", style={"fontSize": "0.9rem"}
                            ),
                            dbc.Switch(
                                id="alert-quiet-hours-toggle",
                                value=False,
                                className="ms-auto",
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                            "marginBottom": "10px",
                        },
                    ),
                    dbc.Collapse(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Start",
                                            style={
                                                "fontSize": "0.85rem",
                                                "color": COLORS["text_muted"],
                                            },
                                        ),
                                        dbc.Input(
                                            id="quiet-hours-start",
                                            type="time",
                                            value="22:00",
                                            style={
                                                "backgroundColor": COLORS["primary"],
                                                "color": COLORS["text"],
                                                "border": f"1px solid {COLORS['border']}",
                                            },
                                        ),
                                    ],
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        html.Label(
                                            "End",
                                            style={
                                                "fontSize": "0.85rem",
                                                "color": COLORS["text_muted"],
                                            },
                                        ),
                                        dbc.Input(
                                            id="quiet-hours-end",
                                            type="time",
                                            value="08:00",
                                            style={
                                                "backgroundColor": COLORS["primary"],
                                                "color": COLORS["text"],
                                                "border": f"1px solid {COLORS['border']}",
                                            },
                                        ),
                                    ],
                                    width=6,
                                ),
                            ]
                        ),
                        id="quiet-hours-collapse",
                        is_open=False,
                    ),
                ],
                style={
                    "padding": "10px 15px",
                    "backgroundColor": COLORS["secondary"],
                    "borderRadius": "8px",
                    "marginBottom": "20px",
                },
            ),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Save / Test Buttons ---
            html.Div(
                [
                    dbc.Button(
                        [html.I(className="fas fa-save me-2"), "Save Preferences"],
                        id="save-alert-prefs-button",
                        color="primary",
                        className="w-100 mb-2",
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-bell me-2"), "Send Test Alert"],
                        id="test-alert-button",
                        color="secondary",
                        outline=True,
                        className="w-100 mb-2",
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-trash me-2"), "Clear Alert History"],
                        id="clear-alert-history-button",
                        color="danger",
                        outline=True,
                        size="sm",
                        className="w-100",
                    ),
                ]
            ),
            # Save confirmation toast
            dbc.Toast(
                id="alert-save-toast",
                header="Preferences Saved",
                is_open=False,
                dismissable=True,
                duration=3000,
                icon="success",
                style={
                    "position": "fixed",
                    "bottom": 20,
                    "right": 20,
                    "width": 280,
                    "zIndex": 9999,
                },
                children="Your alert preferences have been saved.",
            ),
            # localStorage note
            html.Small(
                "Preferences are stored in your browser. They are not synced across devices.",
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.75rem",
                    "display": "block",
                    "marginTop": "15px",
                    "textAlign": "center",
                },
            ),
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
        preferences = {
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
        alert_cards = []

        # Show most recent first
        for alert in reversed(history[-50:]):
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
            except (ValueError, TypeError):
                time_str = str(triggered_at)[:16]

            asset_str = (
                ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
            )

            card = html.Div(
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

            alert_cards.append(card)

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

