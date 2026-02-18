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
    "app_subtitle": "Weaponizing shitposts since 2025",
    "footer_disclaimer": (
        "This is absolutely not financial advice. "
        "We are tracking a shitposter's tweets and pretending an AI can predict markets from them. "
        "Please do not bet your rent money on this."
    ),
    "footer_source_link": "View Source (yes, this is real)",

    # ===== Dashboard: KPI Section =====
    "kpi_total_signals_title": "Total Signals",
    "kpi_total_signals_subtitle": "predictions we actually checked",
    "kpi_accuracy_title": "Accuracy",
    "kpi_accuracy_subtitle": "correct after 7 days (coin flip is 50%)",
    "kpi_avg_return_title": "Avg 7-Day Return",
    "kpi_avg_return_subtitle": "mean return per signal (not great, not terrible)",
    "kpi_pnl_title": "Total P&L",
    "kpi_pnl_subtitle": "simulated $1k trades (monopoly money)",

    # ===== Dashboard: Analytics Section =====
    "analytics_header": "The Numbers",
    "tab_accuracy": "Accuracy Over Time",
    "tab_confidence": "By Confidence Level",
    "tab_asset": "By Asset (click to drill down)",

    # ===== Dashboard: Posts + Feed Columns =====
    "latest_posts_header": "Latest Shitposts",
    "latest_posts_subtitle": "fresh off Truth Social, with our AI's hot take",

    # ===== Dashboard: Data Table =====
    "data_table_header": "Full Prediction Data",

    # ===== Dashboard: Empty States =====
    "empty_feed_period": "No predictions for this period. Try a wider range.",
    "empty_posts": "No posts to show. Even shitposters sleep sometimes.",
    "empty_predictions_table": "No predictions match these filters. We're not THAT prolific.",

    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy yet",
    "chart_empty_accuracy_hint": "Predictions need 7+ trading days to mature. Patience.",
    "chart_empty_confidence": "No accuracy data for this period",
    "chart_empty_confidence_hint": "Takes 7+ days per prediction. We'll get there.",
    "chart_empty_asset": "No asset performance data yet",
    "chart_empty_asset_hint": "Asset accuracy appears after the market proves us wrong (or right)",

    # ===== Signals Page =====
    "signals_page_title": "Signal Feed",
    "signals_page_subtitle": "Every prediction, including the embarrassing ones",
    "signals_empty_filters": "No signals match your filters. Maybe lower your standards?",
    "signals_error": "Failed to load signals. The irony of our own system failing is not lost on us.",
    "signals_load_more": "Load More Signals",
    "signals_export": "Export CSV",

    # ===== Trends Page =====
    "trends_page_title": "Signal Over Trend",
    "trends_page_subtitle": "Our predictions vs. what the market actually did",
    "trends_chart_default": "Pick an asset to see how wrong we are",
    "trends_no_asset_data": "No Asset Data Available",
    "trends_no_asset_hint": (
        "Predictions need to be analyzed and validated before "
        "we can show you how wrong we were. Check back later."
    ),
    "trends_no_signals_for_asset": "No prediction signals for {symbol} in this period. We had nothing to say.",

    # ===== Assets Page =====
    "asset_page_subtitle": "The Full Damage Report for {symbol}",
    "asset_no_predictions": "No predictions found for {symbol}. We kept our mouth shut for once.",
    "asset_no_related": "No related assets. This one's a loner.",
    "asset_no_price": "Price unavailable (the market is keeping secrets)",
    "asset_performance_header": "Performance Summary",
    "asset_related_header": "Related Assets",
    "asset_timeline_header": "Prediction Timeline for {symbol}",

    # ===== Performance Page =====
    "backtest_title": "Backtest Results",
    "backtest_subtitle": (
        "Simulated P&L following high-confidence signals with $10,000. "
        "In hindsight, everything is obvious."
    ),
    "perf_confidence_header": "Accuracy by Confidence Level",
    "perf_sentiment_header": "Sentiment Breakdown",
    "perf_asset_header": "Performance by Asset",
    "perf_empty_confidence": "No confidence breakdown yet",
    "perf_empty_confidence_hint": "We need more predictions to evaluate. Patience is a virtue we don't have.",
    "perf_empty_sentiment": "No sentiment breakdown yet",
    "perf_empty_sentiment_hint": "We need evaluated predictions to know if our vibes were right.",
    "perf_empty_asset_table": "No asset data yet. The market hasn't had time to prove us wrong.",

    # ===== Cards: Analysis Status Labels =====
    "card_pending_analysis": "Pending Analysis",
    "card_bypassed": "Bypassed",
    "card_error_title": "Error Loading Data",

    # ===== Refresh Indicator =====
    "refresh_last_updated": "Last updated ",
    "refresh_next": "Next refresh ",
}
