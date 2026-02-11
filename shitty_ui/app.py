"""
Main entry point for Shitty UI Dashboard
Obnoxiously American-themed dashboard for Shitpost Alpha.
"""

import os
import sys

# Add project root to Python path so imports like shit.db, notifications work
# when running from shitty_ui/ directory (e.g. Railway: cd shitty_ui && python app.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import request, jsonify
from layout import create_app, register_callbacks
from shit.logging import get_service_logger

logger = get_service_logger("dashboard_app")


def register_webhook_route(app):
    """
    Register the Telegram webhook and health check endpoints on the Dash app's Flask server.

    Endpoints:
        POST /telegram/webhook - Receives Telegram updates
        GET  /telegram/health  - Alert system health check
    """
    server = app.server

    @server.route("/telegram/webhook", methods=["POST"])
    def telegram_webhook():
        try:
            update = request.get_json(force=True)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid JSON"}), 400

        try:
            from notifications.telegram_bot import process_update

            process_update(update)
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")

        # Always return 200 to Telegram so it doesn't retry
        return jsonify({"ok": True})

    @server.route("/telegram/health", methods=["GET"])
    def telegram_health():
        """Health check endpoint for the alert system."""
        health = {"ok": True, "service": "telegram_alerts"}
        try:
            from notifications.db import get_subscription_stats, get_last_alert_check
            from notifications.telegram_sender import get_bot_token

            stats = get_subscription_stats()
            last_check = get_last_alert_check()
            has_token = bool(get_bot_token())

            health["bot_configured"] = has_token
            health["subscribers"] = {
                "total": stats.get("total", 0),
                "active": stats.get("active", 0),
            }
            health["last_alert_check"] = last_check.isoformat() if last_check else None
            health["total_alerts_sent"] = stats.get("total_alerts_sent", 0)
        except Exception as e:
            health["ok"] = False
            health["error"] = str(e)
            logger.error(f"Health check failed: {e}")

        status_code = 200 if health["ok"] else 503
        return jsonify(health), status_code


def serve_app():
    """Serve the Dash application."""
    app = create_app()
    register_callbacks(app)
    register_webhook_route(app)

    # Get port from environment (Railway provides this)
    port = int(os.environ.get("PORT", 8050))

    print(f"\U0001f1fa\U0001f1f8 Starting Shitpost Alpha Dashboard on port {port}...")
    print(
        "\U0001f1fa\U0001f1f8 Making America Trade Again, One Shitpost at a Time! \U0001f680\U0001f4c8"
    )

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    serve_app()
