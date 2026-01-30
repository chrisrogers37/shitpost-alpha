"""
Main entry point for Shitty UI Dashboard.
Multi-page Dash application for Shitpost Alpha.

Routes:
    / - Main dashboard (home page)
    /performance - Detailed performance analysis
"""

import os
import dash
from dash import html, dcc, page_container
import dash_bootstrap_components as dbc

from components.nav import create_navbar

# Color palette - must match layout.py and pages
COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}


def create_app() -> dash.Dash:
    """Create and configure the multi-page Dash app."""

    app = dash.Dash(
        __name__,
        use_pages=True,
        pages_folder="pages",
        external_stylesheets=[
            dbc.themes.DARKLY,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Prediction Performance Dashboard"

    # Custom CSS for mobile responsiveness
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Mobile-specific styles */
            @media (max-width: 768px) {
                .metric-card {
                    margin-bottom: 10px;
                }
                .metric-card .card-body {
                    padding: 10px !important;
                }
                .metric-card h3 {
                    font-size: 1.25rem !important;
                }
                .chart-container {
                    height: 200px !important;
                }
                .signal-card {
                    padding: 8px !important;
                }
                h1, h2 {
                    font-size: 1.5rem !important;
                }
                .header-container {
                    flex-direction: column !important;
                    text-align: center !important;
                }
                .header-right {
                    margin-top: 10px !important;
                    flex-direction: column !important;
                    gap: 8px !important;
                }
                .period-selector {
                    justify-content: center !important;
                }
            }

            /* Ensure charts resize properly */
            .js-plotly-plot {
                width: 100% !important;
            }

            /* Loading spinner styling */
            ._dash-loading {
                margin: 20px auto;
            }

            /* Navigation active state */
            .nav-link.active {
                background-color: rgba(59, 130, 246, 0.2) !important;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

    # Root layout wraps all pages
    app.layout = html.Div(
        [
            # Auto-refresh interval (shared across pages)
            dcc.Interval(
                id="refresh-interval",
                interval=5 * 60 * 1000,  # 5 minutes
                n_intervals=0,
            ),
            # Countdown interval (1 second)
            dcc.Interval(
                id="countdown-interval",
                interval=1000,  # 1 second
                n_intervals=0,
            ),
            # Navigation bar
            create_navbar(),
            # Page content - Dash renders the active page here
            page_container,
            # Footer
            html.Div(
                [
                    html.Hr(
                        style={
                            "borderColor": COLORS["border"],
                            "margin": "40px 0 20px 0",
                        }
                    ),
                    html.P(
                        "Disclaimer: This is NOT financial advice. For entertainment and research purposes only.",
                        style={
                            "textAlign": "center",
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                            "fontStyle": "italic",
                        },
                    ),
                    html.P(
                        [
                            html.A(
                                [html.I(className="fab fa-github me-1"), "View Source"],
                                href="https://github.com/chrisrogers37/shitpost-alpha",
                                target="_blank",
                                style={
                                    "color": COLORS["accent"],
                                    "textDecoration": "none",
                                },
                            )
                        ],
                        style={"textAlign": "center", "marginBottom": "20px"},
                    ),
                ],
                style={"padding": "0 20px", "maxWidth": "1400px", "margin": "0 auto"},
            ),
        ],
        style={
            "backgroundColor": COLORS["primary"],
            "minHeight": "100vh",
            "color": COLORS["text"],
            "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        },
    )

    return app


def serve_app():
    """Serve the Dash application."""
    app = create_app()

    # Get port from environment (Railway provides this)
    port = int(os.environ.get("PORT", 8050))

    print(f"Starting Shitpost Alpha Dashboard on port {port}...")
    print("Multi-page mode: / (home), /performance")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )


if __name__ == "__main__":
    serve_app()
