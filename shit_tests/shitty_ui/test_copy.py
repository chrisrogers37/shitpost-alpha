"""Tests for shitty_ui/brand_copy.py - Centralized copy dictionary."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from brand_copy import COPY


class TestCopyDictStructure:
    """Tests for COPY dictionary completeness and types."""

    def test_copy_is_dict(self):
        assert isinstance(COPY, dict)

    def test_copy_has_required_keys(self):
        required_keys = [
            # Header
            "app_subtitle",
            "footer_disclaimer",
            "footer_source_link",
            # Dashboard KPIs
            "kpi_total_signals_title",
            "kpi_total_signals_subtitle",
            "kpi_accuracy_title",
            "kpi_accuracy_subtitle",
            "kpi_avg_return_title",
            "kpi_avg_return_subtitle",
            "kpi_pnl_title",
            "kpi_pnl_subtitle",
            # Dashboard analytics
            "analytics_header",
            "tab_accuracy",
            "tab_confidence",
            "tab_asset",
            # Dashboard sections
            "latest_posts_header",
            "latest_posts_subtitle",
            "data_table_header",
            # Dashboard empty states
            "empty_feed_period",
            "empty_posts",
            "empty_predictions_table",
            # Chart empty states
            "chart_empty_accuracy",
            "chart_empty_accuracy_hint",
            "chart_empty_confidence",
            "chart_empty_confidence_hint",
            "chart_empty_asset",
            "chart_empty_asset_hint",
            # Signals page
            "signals_page_title",
            "signals_page_subtitle",
            "signals_empty_filters",
            "signals_error",
            "signals_load_more",
            "signals_export",
            # Trends page
            "trends_page_title",
            "trends_page_subtitle",
            "trends_chart_default",
            "trends_no_asset_data",
            "trends_no_asset_hint",
            "trends_no_signals_for_asset",
            # Assets page
            "asset_page_subtitle",
            "asset_no_predictions",
            "asset_no_related",
            "asset_no_price",
            "asset_performance_header",
            "asset_related_header",
            "asset_timeline_header",
            # Performance page
            "backtest_title",
            "backtest_subtitle",
            "perf_confidence_header",
            "perf_sentiment_header",
            "perf_asset_header",
            "perf_empty_confidence",
            "perf_empty_confidence_hint",
            "perf_empty_sentiment",
            "perf_empty_sentiment_hint",
            "perf_empty_asset_table",
            # Cards
            "card_pending_analysis",
            "card_bypassed",
            "card_error_title",
            # Refresh
            "refresh_last_updated",
            "refresh_next",
        ]
        for key in required_keys:
            assert key in COPY, f"COPY missing required key: '{key}'"

    def test_all_values_are_strings(self):
        for key, value in COPY.items():
            assert isinstance(value, str), f"COPY['{key}'] should be str, got {type(value)}"
            assert len(value) > 0, f"COPY['{key}'] should not be empty"

    def test_no_double_spaces(self):
        for key, value in COPY.items():
            assert "  " not in value, f"COPY['{key}'] contains double spaces: {value!r}"

    def test_format_placeholders_are_valid(self):
        format_keys = [
            "trends_no_signals_for_asset",
            "asset_page_subtitle",
            "asset_no_predictions",
            "asset_timeline_header",
        ]
        for key in format_keys:
            result = COPY[key].format(symbol="AAPL")
            assert "AAPL" in result, f"COPY['{key}'].format(symbol='AAPL') should contain 'AAPL'"


class TestCopyToneGuard:
    """Ensure copy stays on-brand and avoids known antipatterns."""

    def test_no_stale_memes(self):
        banned_phrases = [
            "stonks",
            "to the moon",
            "wen lambo",
            "diamond hands",
            "paper hands",
            "HODL",
            "this is the way",
            "brrrr",
        ]
        for key, value in COPY.items():
            for phrase in banned_phrases:
                assert phrase.lower() not in value.lower(), (
                    f"COPY['{key}'] contains banned meme phrase '{phrase}'"
                )

    def test_no_excessive_punctuation(self):
        for key, value in COPY.items():
            assert "!!" not in value, f"COPY['{key}'] contains '!!' -- too try-hard"
            assert "???" not in value, f"COPY['{key}'] contains '???' -- too try-hard"

    def test_no_all_caps_words(self):
        allowed_caps = {"AI", "LLM", "P&L", "CSV", "ACTIVE", "SIGNALS", "NOT", "THAT"}
        for key, value in COPY.items():
            words = value.split()
            for word in words:
                clean = word.strip(".,;:!?()[]{}\"'")
                if len(clean) > 3 and clean.isupper() and clean not in allowed_caps:
                    if not clean.startswith("{"):
                        pytest.fail(
                            f"COPY['{key}'] contains ALL-CAPS word '{word}' -- too shouty"
                        )

    def test_footer_does_not_say_wink(self):
        disclaimer = COPY["footer_disclaimer"]
        assert "wink" not in disclaimer.lower()
        assert "nudge" not in disclaimer.lower()
        assert "just kidding" not in disclaimer.lower()

    def test_subtitle_is_not_corporate(self):
        subtitle = COPY["app_subtitle"]
        banned_corporate = [
            "intelligence dashboard",
            "analytics platform",
            "insights engine",
            "data-driven",
            "enterprise",
            "solution",
        ]
        for phrase in banned_corporate:
            assert phrase.lower() not in subtitle.lower(), (
                f"app_subtitle sounds too corporate: contains '{phrase}'"
            )
