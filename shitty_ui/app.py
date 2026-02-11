"""
Main entry point for Shitty UI Dashboard
Obnoxiously American-themed dashboard for Shitpost Alpha.
"""

import os

from flask import request, jsonify
from layout import create_app, register_callbacks
from shit.logging import get_service_logger

logger = get_service_logger("dashboard_app")


def register_webhook_route(app):
    """
    Register the Telegram webhook endpoint on the Dash app's Flask server.

    This is a thin passthrough that receives Telegram updates and delegates
    to the standalone notifications module for processing.
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
