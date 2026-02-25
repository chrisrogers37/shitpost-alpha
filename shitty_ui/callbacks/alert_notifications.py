"""Browser notification and status callbacks for the alert system.

Handles:
- Alert status indicator (active/disabled)
- Interval enable/disable based on master toggle
- Browser notification permission request
- Firing browser notifications
- Test alert
- Bell icon badge updates
"""

from dash import Dash, html, Input, Output

from constants import COLORS


def register_alert_notification_callbacks(app: Dash) -> None:
    """Register all notification and status indicator callbacks.

    Args:
        app: The Dash application instance.
    """

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
