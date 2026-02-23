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
    create_empty_state_chart,
    create_feed_signal_card,
    create_hero_signal_card,
    create_metric_card,
    create_new_signals_banner,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
    create_unified_signal_card,
)
from components.controls import create_filter_controls, get_period_button_styles
from components.header import create_header, create_footer
from pages.dashboard import (
    create_dashboard_page,
    create_performance_page,
    register_dashboard_callbacks,
)
from pages.assets import (
    create_asset_page,
    create_asset_header,
    register_asset_callbacks,
)
from pages.signals import create_signal_feed_page, register_signal_callbacks
from pages.trends import create_trends_page, register_trends_callbacks
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

    # Custom CSS for mobile responsiveness and dark theme
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                overflow-x: hidden;
            }
            body {
                background-color: #0B1215 !important;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            }

            /* Card styling */
            .card {
                border-radius: 12px !important;
                border: 1px solid #2A3A2E !important;
                overflow: hidden;
                transition: box-shadow 0.15s ease;
            }
            .card-header {
                border-bottom: 1px solid #2A3A2E !important;
            }

            /* Hero signal card hover effect */
            .hero-signal-card {
                transition: transform 0.15s ease, box-shadow 0.15s ease;
                border-radius: 12px;
            }
            .hero-signal-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 20px rgba(133, 187, 101, 0.15);
            }

            /* Unified signal card hover effect */
            .unified-signal-card {
                transition: transform 0.15s ease, box-shadow 0.15s ease;
                border-radius: 8px;
            }
            .unified-signal-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 20px rgba(133, 187, 101, 0.15);
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

            /* Nav links with active state accent */
            .nav-link-custom {
                color: #8B9A7E !important;
                text-decoration: none !important;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 0.9rem;
                transition: all 0.15s ease;
                position: relative;
            }
            .nav-link-custom:hover {
                color: #F5F1E8 !important;
                background-color: #2A3A2E;
            }
            .nav-link-custom.active {
                color: #F5F1E8 !important;
                background-color: transparent;
            }
            .nav-link-custom.active::after {
                content: '';
                position: absolute;
                bottom: -2px;
                left: 16px;
                right: 16px;
                height: 2px;
                background-color: #FFD700;
                border-radius: 1px;
            }

            /* ======================================
               Responsive: Tablet (max-width: 768px)
               ====================================== */
            @media (max-width: 768px) {
                /* Header: stack logo and nav vertically */
                .header-container {
                    flex-direction: column !important;
                    text-align: center !important;
                    padding: 12px 16px !important;
                }
                .header-right {
                    margin-top: 10px !important;
                    width: 100% !important;
                    justify-content: center !important;
                }

                /* Navigation: horizontal scroll instead of wrapping */
                .nav-links-row {
                    overflow-x: auto !important;
                    -webkit-overflow-scrolling: touch;
                    scrollbar-width: none;
                    flex-wrap: nowrap !important;
                    justify-content: flex-start !important;
                    width: 100% !important;
                    padding-bottom: 4px;
                }
                .nav-links-row::-webkit-scrollbar {
                    display: none;
                }

                /* Touch targets: minimum 48px height for tap */
                .nav-link-custom {
                    min-height: 48px !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    padding: 12px 16px !important;
                    white-space: nowrap !important;
                    font-size: 0.85rem !important;
                }

                /* KPI metric cards */
                .metric-card {
                    margin-bottom: 8px;
                }
                .metric-card .card-body {
                    padding: 10px !important;
                }
                .metric-card h3 {
                    font-size: 1.25rem !important;
                }

                /* Charts: cap height */
                .chart-container {
                    height: 220px !important;
                }
                .js-plotly-plot .plotly .main-svg {
                    max-width: 100% !important;
                }

                /* Signal cards */
                .signal-card {
                    padding: 10px !important;
                }

                /* Page title */
                .page-title {
                    font-size: 1.4rem !important;
                }

                /* Period selector: center and allow wrapping */
                .period-selector {
                    justify-content: center !important;
                    flex-wrap: wrap !important;
                    gap: 6px;
                }

                /* Hero signals: stack vertically */
                .hero-signals-container {
                    flex-direction: column !important;
                }
                .hero-signal-card {
                    min-width: unset !important;
                    width: 100% !important;
                }

                /* Content container: reduce side padding */
                .main-content-container {
                    padding: 16px 12px !important;
                }

                /* Analytics tabs: smaller text */
                .analytics-tabs .nav-link {
                    padding: 10px 14px !important;
                    font-size: 0.82rem !important;
                }

                /* Data table: allow horizontal scroll */
                .dash-spreadsheet-container {
                    overflow-x: auto !important;
                }
            }

            /* ======================================
               Responsive: Large phone (max-width: 480px)
               ====================================== */
            @media (max-width: 480px) {
                /* Content container: tighter padding */
                .main-content-container {
                    padding: 12px 8px !important;
                }

                /* Logo: smaller to prevent clipping */
                .header-logo {
                    margin-right: 0 !important;
                }
                .header-logo h1 {
                    font-size: 1.1rem !important;
                }
                .header-logo p {
                    font-size: 0.65rem !important;
                }

                /* KPI hero values: scale down to fit 50% column */
                .kpi-hero-value {
                    font-size: 1.4rem !important;
                }
                .kpi-hero-card .card-body {
                    padding: 6px 4px !important;
                    min-height: auto !important;
                }

                /* KPI icon circles: shrink */
                .kpi-hero-card .card-body > div:first-child {
                    width: 28px !important;
                    height: 28px !important;
                    margin-bottom: 6px !important;
                }
                .kpi-hero-card .card-body > div:first-child .fas {
                    font-size: 0.8rem !important;
                }

                /* Tighter padding on cards */
                .metric-card .card-body {
                    padding: 8px !important;
                }
                .metric-card h3 {
                    font-size: 1.1rem !important;
                }
                .metric-card p {
                    font-size: 0.7rem !important;
                }

                /* Period selector: center and wrap */
                .period-selector {
                    justify-content: center !important;
                    flex-wrap: wrap !important;
                    gap: 6px;
                }

                /* Reduce chart height further */
                .chart-container {
                    height: 200px !important;
                }

                /* Section headers */
                .section-header {
                    font-size: 1rem !important;
                }

                /* Card headers */
                .card-header {
                    font-size: 0.85rem !important;
                    padding: 10px 12px !important;
                }

                /* Hide refresh countdown text to save space */
                .refresh-detail {
                    display: none !important;
                }

                /* Signal feed cards: reduce padding */
                .feed-signal-card {
                    padding: 12px !important;
                }
            }

            /* ======================================
               Responsive: Small phone (max-width: 375px)
               ====================================== */
            @media (max-width: 375px) {
                /* Header: minimal padding */
                .header-container {
                    padding: 10px 8px !important;
                }

                /* Logo: smaller to prevent clipping */
                .header-logo {
                    margin-right: 0 !important;
                }
                .header-logo h1 {
                    font-size: 1.1rem !important;
                }
                .header-logo p {
                    font-size: 0.65rem !important;
                }

                /* KPI cards: full width at 375px */
                .kpi-col-mobile {
                    flex: 0 0 50% !important;
                    max-width: 50% !important;
                }

                /* KPI hero values: scale down to fit 50% column */
                .kpi-hero-value {
                    font-size: 1.4rem !important;
                }
                .kpi-hero-card .card-body {
                    padding: 6px 4px !important;
                    min-height: auto !important;
                }

                /* KPI icon circles: shrink */
                .kpi-hero-card .card-body > div:first-child {
                    width: 28px !important;
                    height: 28px !important;
                    margin-bottom: 6px !important;
                }
                .kpi-hero-card .card-body > div:first-child .fas {
                    font-size: 0.8rem !important;
                }

                /* KPI title labels: tighter */
                .metric-card h3 {
                    font-size: 1rem !important;
                    word-break: break-all;
                }
                .metric-card .card-body {
                    padding: 6px !important;
                }
                .metric-card p {
                    font-size: 0.7rem !important;
                }

                /* Icon size reduction (legacy metric-card) */
                .metric-card .fas {
                    font-size: 1.1rem !important;
                }

                /* Period selector: center and wrap to prevent "All" clipping */
                .period-selector {
                    justify-content: center !important;
                    flex-wrap: wrap !important;
                    gap: 6px;
                }
                .period-selector .btn {
                    font-size: 0.75rem !important;
                    padding: 4px 8px !important;
                    min-height: 36px;
                }

                /* Chart height: compact */
                .chart-container {
                    height: 180px !important;
                }

                /* Post/signal text: smaller line height */
                .signal-card p, .feed-signal-card p {
                    font-size: 0.82rem !important;
                    line-height: 1.35 !important;
                }

                /* Engagement icons row */
                .engagement-row {
                    font-size: 0.7rem !important;
                }

                /* Analytics tabs: compress further */
                .analytics-tabs .nav-link {
                    padding: 8px 10px !important;
                    font-size: 0.78rem !important;
                }

                /* Sentiment badges: smaller */
                .sentiment-badge {
                    font-size: 0.65rem !important;
                    padding: 2px 6px !important;
                }

                /* Footer: smaller text */
                footer p {
                    font-size: 0.7rem !important;
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
            ::-webkit-scrollbar-track { background: #0B1215; }
            ::-webkit-scrollbar-thumb { background: #2A3A2E; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #3D5440; }

            /* ======================================
               Typography hierarchy classes
               ====================================== */

            /* Page title - used for top-level page headers */
            .page-title {
                font-size: 1.75rem;
                font-weight: 700;
                color: #F5F1E8;
                margin: 0 0 4px 0;
                line-height: 1.2;
            }
            .page-title .page-subtitle {
                display: block;
                font-size: 0.8rem;
                font-weight: 400;
                color: #8B9A7E;
                margin-top: 4px;
            }

            /* Section header - major sections within a page */
            .section-header {
                font-size: 1.15rem;
                font-weight: 600;
                color: #F5F1E8;
                margin: 0;
                padding-bottom: 8px;
                border-bottom: 2px solid #85BB65;
                margin-bottom: 16px;
                display: inline-block;
            }

            /* Card header title override - consistent sizing for all card headers */
            .card-header {
                font-size: 0.95rem !important;
                font-weight: 600 !important;
                color: #F5F1E8 !important;
                letter-spacing: 0.01em;
            }
            .card-header .card-header-subtitle {
                font-size: 0.8rem;
                font-weight: 400;
                color: #8B9A7E;
                margin-left: 8px;
            }

            /* Body text class for standard content */
            .text-body-default {
                font-size: 0.9rem;
                font-weight: 400;
                color: #F5F1E8;
                line-height: 1.5;
            }

            /* Label text for form labels and metadata labels */
            .text-label {
                font-size: 0.8rem;
                font-weight: 500;
                color: #8B9A7E;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            /* Metadata text for timestamps, IDs, fine print */
            .text-meta {
                font-size: 0.75rem;
                font-weight: 400;
                color: #8B9A7E;
                line-height: 1.4;
            }

            /* Active signals section header (uppercase label style) */
            .section-label {
                font-size: 0.85rem;
                font-weight: 700;
                letter-spacing: 0.05em;
                text-transform: uppercase;
                color: #F5F1E8;
            }
            .section-label .section-label-muted {
                font-weight: 400;
                text-transform: none;
                letter-spacing: normal;
                color: #8B9A7E;
                font-size: 0.8rem;
            }

            /* ======================================
               Analytics tab interface
               ====================================== */
            .analytics-tabs .nav-tabs {
                border-bottom: 1px solid #2A3A2E;
                background-color: transparent;
            }
            .analytics-tabs .nav-link {
                color: #8B9A7E !important;
                border: none !important;
                border-bottom: 2px solid transparent !important;
                background-color: transparent !important;
                padding: 10px 20px;
                font-size: 0.9rem;
                font-weight: 500;
                transition: all 0.15s ease;
            }
            .analytics-tabs .nav-link:hover {
                color: #F5F1E8 !important;
                border-bottom-color: #3D5440 !important;
            }
            .analytics-tabs .nav-link.active {
                color: #85BB65 !important;
                border-bottom-color: #85BB65 !important;
                background-color: transparent !important;
            }
            .analytics-tabs .tab-content {
                padding-top: 16px;
            }

            /* ======================================
               Collapsible section chevrons
               ====================================== */
            .collapse-toggle-btn {
                display: flex;
                align-items: center;
                gap: 8px;
                width: 100%;
                text-align: left;
            }
            .collapse-chevron {
                transition: transform 0.2s ease;
                font-size: 0.8rem;
            }
            .collapse-chevron.rotated {
                transform: rotate(90deg);
            }

            /* ======================================
               Visual hierarchy tiers
               ====================================== */

            /* Primary tier: KPI metrics (most important) */
            .kpi-hero-card {
                border-radius: 16px !important;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .kpi-hero-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 32px rgba(133, 187, 101, 0.12), 0 2px 6px rgba(0, 0, 0, 0.25) !important;
            }
            .kpi-hero-value {
                font-variant-numeric: tabular-nums;
            }

            /* Tertiary tier: posts, data table (receded) */
            .section-tertiary {
                border-radius: 10px;
            }
            .section-tertiary .card-header {
                background-color: #0E1719 !important;
                border-bottom-color: #2A3A2E !important;
            }
            .section-tertiary .card-body {
                background-color: #0E1719 !important;
            }

            /* Header elevation shadow */
            .header-container {
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                position: relative;
                z-index: 10;
            }

            /* ======================================
               Thesis expand/collapse
               ====================================== */
            .thesis-toggle-area {
                cursor: pointer;
                user-select: none;
            }
            .thesis-toggle-area:hover {
                text-decoration: underline;
            }

            /* ======================================
               Asset Screener Table
               ====================================== */
            .screener-row:hover {
                background-color: rgba(133, 187, 101, 0.06) !important;
            }
            .screener-row:hover td {
                background-color: rgba(133, 187, 101, 0.06) !important;
            }

            /* ======================================
               Screener: Tablet (max-width: 768px)
               ====================================== */
            @media (max-width: 768px) {
                .screener-table-container {
                    overflow-x: auto !important;
                    -webkit-overflow-scrolling: touch;
                }
                .screener-hide-tablet {
                    display: none !important;
                }
            }

            /* ======================================
               Screener: Mobile (max-width: 480px)
               ====================================== */
            @media (max-width: 480px) {
                .screener-row td {
                    padding: 6px 8px !important;
                    font-size: 0.8rem !important;
                }
                .screener-hide-mobile {
                    display: none !important;
                }
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

        if pathname == "/signals":
            return create_signal_feed_page()

        if pathname == "/trends":
            return create_trends_page()

        return create_dashboard_page()

    # Active nav link highlighting
    app.clientside_callback(
        """
        function(pathname) {
            var links = {
                '/': 'nav-link-dashboard',
                '/signals': 'nav-link-signals',
                '/trends': 'nav-link-trends',
                '/performance': 'nav-link-performance'
            };
            var classes = [];
            for (var path in links) {
                var isActive = (pathname === path) ||
                    (path === '/' && (pathname === '' || pathname === null));
                classes.push(isActive ? 'nav-link-custom active' : 'nav-link-custom');
            }
            return classes;
        }
        """,
        [
            Output("nav-link-dashboard", "className"),
            Output("nav-link-signals", "className"),
            Output("nav-link-trends", "className"),
            Output("nav-link-performance", "className"),
        ],
        [Input("url", "pathname")],
    )

    # Delegate to page/callback modules
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_signal_callbacks(app)
    register_trends_callbacks(app)
    register_alert_callbacks(app)
