"""
Tests for data package re-export contract.

Verifies that all public functions are accessible via `from data import X`
after the split into submodules.
"""

import sys
import os
import pytest

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestDataPackageExports:
    """Verify every public function is re-exported from data/__init__.py."""

    def test_all_signal_query_functions_exported(self):
        """Signal query functions accessible from data package."""
        from data import (
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
        assert callable(load_recent_posts)
        assert callable(get_signal_feed)

    def test_all_performance_query_functions_exported(self):
        """Performance query functions accessible from data package."""
        from data import (
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
        assert callable(get_prediction_stats)
        assert callable(get_dashboard_kpis)

    def test_all_asset_query_functions_exported(self):
        """Asset query functions accessible from data package."""
        from data import (
            get_asset_screener_data,
            get_screener_sparkline_prices,
            get_similar_predictions,
            get_predictions_with_outcomes,
            get_asset_price_history,
            get_sparkline_prices,
            get_asset_predictions,
            get_asset_stats,
            get_related_assets,
        )
        assert callable(get_asset_screener_data)
        assert callable(get_asset_stats)

    def test_all_insight_query_functions_exported(self):
        """Insight query functions accessible from data package."""
        from data import get_dynamic_insights
        assert callable(get_dynamic_insights)

    def test_base_infrastructure_exported(self):
        """Base infrastructure accessible from data package."""
        from data import execute_query, ttl_cache, clear_all_caches, logger
        assert callable(execute_query)
        assert callable(ttl_cache)
        assert callable(clear_all_caches)

    def test_clear_all_caches_runs_without_error(self):
        """clear_all_caches() should not raise even with empty caches."""
        from data import clear_all_caches
        clear_all_caches()  # Should not raise

    def test_dunder_all_matches_exports(self):
        """__all__ should list every re-exported name."""
        import data
        for name in data.__all__:
            assert hasattr(data, name), f"{name} in __all__ but not accessible"
