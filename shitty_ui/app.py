"""
Main entry point for Shitty UI Dashboard
Obnoxiously American-themed dashboard for Shitpost Alpha.
"""

import os
from layout import create_app, register_callbacks


def serve_app():
    """Serve the Dash application."""
    app = create_app()
    register_callbacks(app)

    # Get port from environment (Railway provides this)
    port = int(os.environ.get("PORT", 8050))

    print(f"🇺🇸 Starting Shitpost Alpha Dashboard on port {port}...")
    print("🇺🇸 Making America Trade Again, One Shitpost at a Time! 🚀📈")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    serve_app()
