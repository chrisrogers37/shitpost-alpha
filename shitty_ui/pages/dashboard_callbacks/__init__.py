"""Dashboard callback sub-modules.

Each module registers a focused group of callbacks:
- period: Time period selection and countdown
- content: Main dashboard content (KPIs, screener, insights, post feed)
- table: Data table management (collapse, filtering, row clicks, thesis expand)
- analytics: Analytics charts (P&L, accuracy, calibration, backtest)
"""

from pages.dashboard_callbacks.period import register_period_callbacks
from pages.dashboard_callbacks.content import register_content_callbacks
from pages.dashboard_callbacks.table import register_table_callbacks
from pages.dashboard_callbacks.analytics import register_analytics_callbacks

__all__ = [
    "register_period_callbacks",
    "register_content_callbacks",
    "register_table_callbacks",
    "register_analytics_callbacks",
]
