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
    "kpi_total_signals_subtitle": "predictions we actually checked",
    "kpi_accuracy_title": "Accuracy",
    "kpi_accuracy_subtitle": "correct after 7 days (coin flip is 50%)",
    "kpi_avg_return_title": "Avg 7-Day Return",
    "kpi_avg_return_subtitle": "mean return per signal (not great, not terrible)",
    "kpi_pnl_title": "Total P&L",
    "kpi_pnl_subtitle": "simulated $1k trades (Monopoly money, for now)",
    # ===== Dashboard: Analytics Section =====
    "analytics_header": "Show Me The Money",
    "tab_accuracy": "Accuracy Over Time",
    "tab_confidence": "By Confidence Level",
    "tab_asset": "By Asset (click to drill down)",
    # ===== Dashboard: Posts + Feed Columns =====
    "latest_posts_header": "Latest Shitposts",
    "latest_posts_subtitle": "fresh off Truth Social, with our AI's hot take on your portfolio",
    # ===== Dashboard: Data Table =====
    "data_table_header": "Full Prediction Ledger",
    # ===== Dashboard: Empty States =====
    "empty_feed_period": "No predictions for this period. The money printer is paused.",
    "empty_posts": "No posts to show. Even shitposters sleep sometimes.",
    "empty_predictions_table": "No predictions match these filters. We're not THAT prolific.",
    # ===== Dashboard: Insight Cards =====
    "insight_latest_call_label": "LATEST CALL",
    "insight_best_worst_label": "BEST & WORST",
    "insight_system_pulse_label": "SYSTEM PULSE",
    "insight_hot_asset_label": "HOT ASSET",
    "insight_hot_signal_label": "HIGH-CONFIDENCE SIGNAL",
    "insight_empty": "Nothing interesting to report. Check back in 5 minutes.",
    "insight_section_aria": "Dynamic insight cards summarizing recent prediction performance",
    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy yet",
    "chart_empty_accuracy_hint": "Predictions need 7+ trading days to mature. Patience, money isn't made overnight.",
    "chart_empty_confidence": "No accuracy data for this period",
    "chart_empty_confidence_hint": "Takes 7+ days per prediction. We'll get there.",
    "chart_empty_asset": "No asset performance data yet",
    "chart_empty_asset_hint": "Asset accuracy appears after the market proves us wrong (or makes us rich)",
    # ===== Assets Page =====
    "asset_page_subtitle": "The Full Damage Report for {symbol}",
    "asset_no_predictions": "No predictions found for {symbol}. We kept our mouth shut for once.",
    "asset_no_related": "No related assets. This one's a loner.",
    "asset_no_price": "Price unavailable (the market is keeping secrets)",
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
