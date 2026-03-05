"""Centralized copy for the Shitpost Alpha dashboard.

All user-facing branded text lives here. This makes it easy to:
- Audit tone consistency across the whole app
- Update copy without digging through component files
- Test that branded strings actually render

DO NOT put functional labels here (axis labels, column headers,
filter options, badge text). Only descriptive/personality copy.
"""

COPY = {
    # ===== Header =====
    "app_subtitle": "Weaponizing shitposts for American profit since 2025",
    "footer_disclaimer": (
        "This is absolutely not financial advice. "
        "We are tracking a shitposter's tweets and pretending an AI can predict markets from them. "
        "Your gains are not real until you sell. Your losses are very real right now. "
        "Please do not bet your rent money on this."
    ),
    "footer_source_link": "View Source (yes, this is real and it's spectacular)",
    # ===== Dashboard: KPI Section =====
    "kpi_total_signals_title": "Total Signals",
    "kpi_total_signals_subtitle": "evaluated prediction outcomes",
    "kpi_accuracy_title": "Accuracy",
    "kpi_accuracy_subtitle": "{tf_label} prediction accuracy",
    "kpi_avg_return_title": "Avg 7-Day Return",
    "kpi_avg_return_subtitle": "mean {tf_label} return per signal",
    "kpi_pnl_title": "Total P&L",
    "kpi_pnl_subtitle": "simulated $1K per trade ({tf_label})",
    # ===== Dashboard: Analytics Section =====
    "analytics_header": "Show Me The Money",
    "tab_accuracy": "Accuracy Over Time",
    "tab_confidence": "By Confidence Level",
    "tab_asset": "By Asset (click to drill down)",
    # ===== Dashboard: Analytics Charts Section =====
    "analytics_section_subtitle": "equity curves, accuracy trends, and backtesting (the real stuff)",
    "analytics_pnl_tab": "Equity Curve",
    "analytics_rolling_tab": "Rolling Accuracy",
    "analytics_calibration_tab": "Calibration",
    "analytics_backtest_tab": "Backtest Simulator",
    "analytics_empty_pnl": "No P&L data yet. Predictions need 7+ trading days to mature.",
    "analytics_empty_rolling": "Not enough data points for rolling accuracy.",
    "analytics_empty_calibration": "No calibration data. Need evaluated predictions first.",
    "analytics_empty_backtest": "No backtest data for these settings.",
    "analytics_backtest_capital_label": "Starting Capital ($)",
    "analytics_backtest_confidence_label": "Min Confidence",
    # ===== Dashboard: Posts + Feed Columns =====
    "latest_posts_header": "Latest Shitposts",
    "latest_posts_subtitle": "fresh off Truth Social, with our AI's hot take on your portfolio",
    # ===== Dashboard: Data Table =====
    "data_table_header": "Full Prediction Ledger",
    # ===== Dashboard: Empty States =====
    "empty_feed_period": "No predictions in this period. Try a wider time range.",
    "empty_posts": "No posts to display. Waiting for new activity.",
    "empty_predictions_table": "No predictions match these filters. Adjust your criteria.",
    # ===== Dashboard: Insight Cards =====
    "insight_latest_call_label": "LATEST CALL",
    "insight_best_worst_label": "BEST & WORST",
    "insight_system_pulse_label": "SYSTEM PULSE",
    "insight_hot_asset_label": "HOT ASSET",
    "insight_hot_signal_label": "HIGH-CONFIDENCE SIGNAL",
    "insight_empty": "No insights available for this period. Check back soon.",
    "insight_section_aria": "Dynamic insight cards summarizing recent prediction performance",
    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy",
    "chart_empty_accuracy_hint": "Predictions need time to mature. Try a wider period or check back later.",
    "chart_empty_confidence": "No accuracy data for this period",
    "chart_empty_confidence_hint": "Not enough evaluated predictions. Try a wider time range.",
    "chart_empty_asset": "No asset performance data yet",
    "chart_empty_asset_hint": "Asset-level accuracy requires evaluated prediction outcomes.",
    # ===== Assets Page =====
    "asset_page_subtitle": "The Full Damage Report for {symbol}",
    "asset_no_predictions": "No predictions found for {symbol}.",
    "asset_no_related": "No co-occurring assets found.",
    "asset_no_price": "Price data unavailable",
    "asset_performance_header": "Performance Summary",
    "asset_related_header": "Related Assets",
    "asset_timeline_header": "Prediction Timeline for {symbol}",
    # ===== Cards: Analysis Status Labels =====
    "card_pending_analysis": "Pending Analysis",
    "card_bypassed": "Bypassed",
    "card_error_title": "Error Loading Data",
    # ===== Refresh Indicator =====
    "refresh_last_updated": "Last updated ",
    "refresh_next": "Next refresh ",
}
