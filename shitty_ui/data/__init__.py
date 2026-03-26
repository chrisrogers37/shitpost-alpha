"""
Database access layer for Shitty UI Dashboard.

This package re-exports all query functions for backward compatibility.
All existing `from data import X` statements continue to work unchanged.

Internal structure:
    data/base.py              -- execute_query, ttl_cache, logger
    data/signal_queries.py    -- Signal loading, feed, filtering
    data/performance_queries.py -- KPIs, accuracy, P&L, streaks
    data/asset_queries.py     -- Screener, sparklines, asset stats
    data/insight_queries.py   -- Dynamic insight cards
    data/timeframe.py         -- Timeframe column mapping helper
"""

# --- Timeframe helpers ---
from data.timeframe import (  # noqa: F401
    get_tf_columns,
    TIMEFRAME_OPTIONS,
    VALID_TIMEFRAMES,
    DEFAULT_TIMEFRAME,
)

# --- Base infrastructure ---
from data.base import (  # noqa: F401
    execute_query,
    ttl_cache,
    logger,
    DATABASE_URL,
)

# --- Signal queries ---
from data.signal_queries import (  # noqa: F401
    load_recent_posts,
    load_filtered_posts,
    get_recent_signals,
    get_active_signals,
    get_active_signals_with_fallback,
    get_unified_feed,
    get_weekly_signal_count,
    get_signal_feed,
    get_signal_feed_count,
    get_new_signals_since,
    get_signal_feed_csv,
    get_price_with_signals,
    get_multi_asset_signals,
)

# --- Performance queries ---
from data.performance_queries import (  # noqa: F401
    get_available_assets,
    get_prediction_stats,
    get_performance_metrics,
    get_dashboard_kpis,
    get_dashboard_kpis_with_fallback,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_sentiment_distribution,
    get_active_assets_from_db,
    get_top_predicted_asset,
    get_cumulative_pnl,
    get_rolling_accuracy,
    get_win_loss_streaks,
    get_confidence_calibration,
    get_monthly_performance,
    get_high_confidence_metrics,
    get_empty_state_context,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
)

# --- Asset queries ---
from data.asset_queries import (  # noqa: F401
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_asset_price_history,
    get_sparkline_prices,
    get_asset_predictions,
    get_asset_stats,
    get_related_assets,
    get_ticker_fundamentals,
    get_screener_sectors,
)

# --- Insight queries ---
from data.insight_queries import (  # noqa: F401
    get_dynamic_insights,
)

# --- Backtest queries ---
from data.backtest_queries import (  # noqa: F401
    get_backtest_equity_curve,
)


def clear_all_caches() -> None:
    """Clear all data layer caches. Call when forcing a full refresh.

    Wires up clear_cache() calls for every @ttl_cache-decorated function
    across all submodules.
    """
    # Performance queries (11 cached functions)
    get_prediction_stats.clear_cache()  # type: ignore
    get_performance_metrics.clear_cache()  # type: ignore
    get_dashboard_kpis.clear_cache()  # type: ignore
    get_accuracy_by_confidence.clear_cache()  # type: ignore
    get_accuracy_by_asset.clear_cache()  # type: ignore
    get_sentiment_distribution.clear_cache()  # type: ignore
    get_active_assets_from_db.clear_cache()  # type: ignore
    get_available_assets.clear_cache()  # type: ignore
    get_high_confidence_metrics.clear_cache()  # type: ignore
    get_best_performing_asset.clear_cache()  # type: ignore
    get_backtest_simulation.clear_cache()  # type: ignore
    get_top_predicted_asset.clear_cache()  # type: ignore
    get_empty_state_context.clear_cache()  # type: ignore

    # Asset queries (6 cached functions)
    get_asset_stats.clear_cache()  # type: ignore
    get_asset_screener_data.clear_cache()  # type: ignore
    get_screener_sparkline_prices.clear_cache()  # type: ignore
    get_sparkline_prices.clear_cache()  # type: ignore
    get_ticker_fundamentals.clear_cache()  # type: ignore
    get_screener_sectors.clear_cache()  # type: ignore

    # Insight queries (1 cached function)
    get_dynamic_insights.clear_cache()  # type: ignore

    # Backtest queries (1 cached function)
    get_backtest_equity_curve.clear_cache()  # type: ignore


__all__ = [
    # Timeframe
    "get_tf_columns",
    "TIMEFRAME_OPTIONS",
    "VALID_TIMEFRAMES",
    "DEFAULT_TIMEFRAME",
    # Base
    "execute_query",
    "ttl_cache",
    "logger",
    "DATABASE_URL",
    "clear_all_caches",
    # Signal queries
    "load_recent_posts",
    "load_filtered_posts",
    "get_recent_signals",
    "get_active_signals",
    "get_active_signals_with_fallback",
    "get_unified_feed",
    "get_weekly_signal_count",
    "get_signal_feed",
    "get_signal_feed_count",
    "get_new_signals_since",
    "get_signal_feed_csv",
    "get_price_with_signals",
    "get_multi_asset_signals",
    # Performance queries
    "get_available_assets",
    "get_prediction_stats",
    "get_performance_metrics",
    "get_dashboard_kpis",
    "get_dashboard_kpis_with_fallback",
    "get_accuracy_by_confidence",
    "get_accuracy_by_asset",
    "get_sentiment_distribution",
    "get_active_assets_from_db",
    "get_top_predicted_asset",
    "get_cumulative_pnl",
    "get_rolling_accuracy",
    "get_win_loss_streaks",
    "get_confidence_calibration",
    "get_monthly_performance",
    "get_high_confidence_metrics",
    "get_empty_state_context",
    "get_best_performing_asset",
    "get_accuracy_over_time",
    "get_backtest_simulation",
    "get_sentiment_accuracy",
    # Asset queries
    "get_asset_screener_data",
    "get_screener_sparkline_prices",
    "get_similar_predictions",
    "get_predictions_with_outcomes",
    "get_asset_price_history",
    "get_sparkline_prices",
    "get_asset_predictions",
    "get_asset_stats",
    "get_related_assets",
    "get_ticker_fundamentals",
    "get_screener_sectors",
    # Insight queries
    "get_dynamic_insights",
    # Backtest queries
    "get_backtest_equity_curve",
]
