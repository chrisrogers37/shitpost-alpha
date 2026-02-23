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
from pages.dashboard import (
    create_dashboard_page,
    register_dashboard_callbacks,
)
from pages.assets import (
    create_asset_page,
    register_asset_callbacks,
)
from callbacks.alerts import (
    create_alert_config_panel,
    register_alert_callbacks,
)
from alerts import DEFAULT_ALERT_PREFERENCES

# Re-export component/data functions consumed by tests via `from layout import ...`
from components.cards import (  # noqa: F401
    create_error_card,
    create_empty_chart,
    create_empty_state_chart,
    create_feed_signal_card,
    create_metric_card,
    create_new_signals_banner,
    create_signal_card,
)
from components.controls import create_filter_controls, get_period_button_styles  # noqa: F401
from components.header import create_header, create_footer  # noqa: F401
from callbacks.alerts import create_alert_history_panel  # noqa: F401
from data import (  # noqa: F401
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_asset_screener_data,
    get_screener_sparkline_prices,
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
            "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Trading Intelligence Dashboard"

    # Custom index template — CSS lives in assets/custom.css (auto-loaded by Dash)
    app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

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
        """Route to the correct page based on URL pathname.

        Only 2 views exist:
        - / (Home = Screener)
        - /assets/<symbol> (Asset Detail)

        Old routes (/signals, /trends, /performance) fall through to home.
        """
        if pathname and pathname.startswith("/assets/"):
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        return create_dashboard_page()

    # Delegate to page/callback modules
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_alert_callbacks(app)
