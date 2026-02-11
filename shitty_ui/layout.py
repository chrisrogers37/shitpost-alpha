"""
Dashboard layout and callbacks for Shitty UI.

This module serves as the app factory and callback registry.
Page layouts and callbacks are organized in submodules:
- constants: Color palette and shared constants
- components/: Reusable UI components (cards, controls, header)
- pages/: Page layouts and page-specific callbacks
- callbacks/: Cross-cutting callback groups (alerts)
"""

from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import (
    create_error_card,
    create_empty_chart,
    create_hero_signal_card,
    create_metric_card,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
)
from components.controls import create_filter_controls, get_period_button_styles
from components.header import create_header, create_footer
from pages.dashboard import (
    create_dashboard_page,
    create_performance_page,
    register_dashboard_callbacks,
)
from pages.assets import create_asset_page, create_asset_header, register_asset_callbacks
from callbacks.alerts import (
    create_alert_config_panel,
    create_alert_history_panel,
    register_alert_callbacks,
)
from alerts import DEFAULT_ALERT_PREFERENCES

# Re-export data functions for backwards compatibility with test patches
from data import (  # noqa: F401
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_active_assets_from_db,
    get_available_assets,
)


def create_app() -> Dash:
    """Create and configure the Dash app."""

    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Trading Intelligence Dashboard"

    # Custom CSS for mobile responsiveness and dark theme
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: #0F172A !important;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            }

            /* Card styling */
            .card {
                border-radius: 12px !important;
                border: 1px solid #334155 !important;
                overflow: hidden;
            }
            .card-header {
                border-bottom: 1px solid #334155 !important;
            }

            /* Hero signal card hover effect */
            .hero-signal-card {
                transition: transform 0.15s ease, box-shadow 0.15s ease;
                border-radius: 12px;
            }
            .hero-signal-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
            }

            /* Sentiment badges */
            .sentiment-badge {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 3px 10px;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            /* Nav links */
            .nav-link-custom {
                color: #94a3b8 !important;
                text-decoration: none !important;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.15s ease;
            }
            .nav-link-custom:hover, .nav-link-custom.active {
                color: #f1f5f9 !important;
                background-color: #334155;
            }

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
                h1 {
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
                .hero-signals-container {
                    flex-direction: column !important;
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

            /* Scrollbar styling for dark theme */
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #0F172A; }
            ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #475569; }
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

    # Main layout with URL routing
    app.layout = html.Div(
        [
            # URL tracking for multi-page routing
            dcc.Location(id="url", refresh=False),
            # Auto-refresh interval (5 minutes)
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
            # Store for selected asset
            dcc.Store(id="selected-asset", data=None),
            # Store for selected time period (default: 90d)
            dcc.Store(id="selected-period", data="90d"),
            # Store for last update timestamp
            dcc.Store(id="last-update-timestamp", data=None),
            # Alert system stores
            dcc.Store(
                id="alert-preferences-store",
                storage_type="local",
                data=DEFAULT_ALERT_PREFERENCES,
            ),
            dcc.Store(
                id="last-alert-check-store",
                storage_type="local",
                data=None,
            ),
            dcc.Store(
                id="alert-history-store",
                storage_type="local",
                data=[],
            ),
            dcc.Store(
                id="alert-notification-store",
                storage_type="memory",
                data=None,
            ),
            # Alert check interval (separate from dashboard refresh)
            dcc.Interval(
                id="alert-check-interval",
                interval=2 * 60 * 1000,  # 2 minutes
                n_intervals=0,
                disabled=True,  # Disabled until alerts are enabled
            ),
            # Alert configuration panel (offcanvas)
            create_alert_config_panel(),
            # Page content - swapped by router callback
            html.Div(id="page-content"),
        ],
        style={
            "backgroundColor": COLORS["bg"],
            "minHeight": "100vh",
            "color": COLORS["text"],
            "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        },
    )

    return app


def register_callbacks(app: Dash):
    """Register all callbacks for the dashboard."""

    # URL Router Callback
    @app.callback(
        Output("page-content", "children"),
        [Input("url", "pathname")],
    )
    def route_page(pathname: str):
        """Route to the correct page based on URL pathname."""
        if pathname and pathname.startswith("/assets/"):
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        if pathname == "/performance":
            return create_performance_page()

        return create_dashboard_page()

    # Delegate to page/callback modules
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_alert_callbacks(app)
