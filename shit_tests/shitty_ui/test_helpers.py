"""Tests for shitty_ui/components/helpers.py - Shared UI helper functions."""

import sys
import os

# Add shitty_ui to path for imports (matches pattern from test_cards.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

from datetime import datetime, timedelta

from components.helpers import (
    format_time_ago,
    extract_sentiment,
    create_outcome_badge,
    format_asset_display,
)
from constants import COLORS


class TestFormatTimeAgo:
    """Tests for format_time_ago()."""

    def test_none_returns_empty_string(self):
        assert format_time_ago(None) == ""

    def test_non_datetime_returns_truncated_string(self):
        assert format_time_ago("2025-06-15T10:30:00") == "2025-06-15"

    def test_integer_returns_truncated_string(self):
        assert format_time_ago(1234567890) == "1234567890"

    def test_weeks_ago(self):
        # 15 days ago -> 2 weeks
        ts = datetime.now() - timedelta(days=15)
        result = format_time_ago(ts)
        assert result == "2w ago"

    def test_days_ago(self):
        ts = datetime.now() - timedelta(days=3)
        result = format_time_ago(ts)
        assert result == "3d ago"

    def test_hours_ago(self):
        ts = datetime.now() - timedelta(hours=3)
        result = format_time_ago(ts)
        assert result == "3h ago"

    def test_minutes_ago(self):
        ts = datetime.now() - timedelta(minutes=25)
        result = format_time_ago(ts)
        assert result == "25m ago"

    def test_just_now(self):
        ts = datetime.now() - timedelta(seconds=5)
        result = format_time_ago(ts)
        assert result == "just now"

    def test_exactly_7_days_shows_days(self):
        """7 days is NOT > 7, should show days not weeks."""
        ts = datetime.now() - timedelta(days=7)
        result = format_time_ago(ts)
        assert result == "7d ago"

    def test_8_days_shows_weeks(self):
        ts = datetime.now() - timedelta(days=8)
        result = format_time_ago(ts)
        assert result == "1w ago"


class TestExtractSentiment:
    """Tests for extract_sentiment()."""

    def test_bullish_dict(self):
        assert extract_sentiment({"AAPL": "bullish"}) == "bullish"

    def test_bearish_dict(self):
        assert extract_sentiment({"TSLA": "Bearish"}) == "bearish"

    def test_neutral_dict(self):
        assert extract_sentiment({"SPY": "neutral"}) == "neutral"

    def test_empty_dict_returns_neutral(self):
        assert extract_sentiment({}) == "neutral"

    def test_none_returns_neutral(self):
        assert extract_sentiment(None) == "neutral"

    def test_non_dict_returns_neutral(self):
        assert extract_sentiment("bullish") == "neutral"

    def test_non_string_value_returns_neutral(self):
        assert extract_sentiment({"AAPL": 42}) == "neutral"

    def test_multi_asset_uses_first(self):
        # Dicts preserve insertion order in Python 3.7+
        result = extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"})
        assert result == "bullish"

    def test_mixed_case_normalized(self):
        assert extract_sentiment({"AAPL": "BULLISH"}) == "bullish"


class TestCreateOutcomeBadge:
    """Tests for create_outcome_badge()."""

    def test_correct_with_pnl(self):
        badge = create_outcome_badge(True, pnl_display=150.0)
        assert badge.style["color"] == COLORS["success"]
        text = _extract_text(badge)
        assert "+$150" in text

    def test_correct_without_pnl(self):
        badge = create_outcome_badge(True, pnl_display=None)
        text = _extract_text(badge)
        assert "Correct" in text

    def test_incorrect_with_pnl(self):
        badge = create_outcome_badge(False, pnl_display=-75.0)
        assert badge.style["color"] == COLORS["danger"]
        text = _extract_text(badge)
        assert "$-75" in text

    def test_incorrect_without_pnl(self):
        badge = create_outcome_badge(False, pnl_display=None)
        text = _extract_text(badge)
        assert "Incorrect" in text

    def test_pending(self):
        badge = create_outcome_badge(None)
        assert badge.style["color"] == COLORS["warning"]
        text = _extract_text(badge)
        assert "Pending" in text

    def test_default_font_size(self):
        badge = create_outcome_badge(True)
        assert badge.style["fontSize"] == "0.75rem"

    def test_custom_font_size(self):
        badge = create_outcome_badge(True, font_size="0.8rem")
        assert badge.style["fontSize"] == "0.8rem"

    def test_correct_with_zero_pnl(self):
        """Zero P&L is falsy -- should show 'Correct', not '$0'."""
        badge = create_outcome_badge(True, pnl_display=0)
        text = _extract_text(badge)
        assert "Correct" in text

    def test_incorrect_with_zero_pnl(self):
        """Zero P&L is falsy -- should show 'Incorrect', not '$0'."""
        badge = create_outcome_badge(False, pnl_display=0)
        text = _extract_text(badge)
        assert "Incorrect" in text


class TestFormatAssetDisplay:
    """Tests for format_asset_display()."""

    def test_single_asset(self):
        assert format_asset_display(["AAPL"]) == "AAPL"

    def test_two_assets(self):
        assert format_asset_display(["AAPL", "TSLA"]) == "AAPL, TSLA"

    def test_three_assets_at_limit(self):
        assert format_asset_display(["AAPL", "TSLA", "GOOG"]) == "AAPL, TSLA, GOOG"

    def test_four_assets_shows_overflow(self):
        result = format_asset_display(["AAPL", "TSLA", "GOOG", "AMZN"])
        assert result == "AAPL, TSLA, GOOG +1"

    def test_custom_max_count(self):
        result = format_asset_display(["AAPL", "TSLA", "GOOG", "AMZN"], max_count=4)
        assert result == "AAPL, TSLA, GOOG, AMZN"

    def test_overflow_disabled(self):
        result = format_asset_display(
            ["AAPL", "TSLA", "GOOG", "AMZN"], max_count=3, show_overflow=False
        )
        assert result == "AAPL, TSLA, GOOG"
        assert "+" not in result

    def test_non_list_stringified(self):
        assert format_asset_display("AAPL") == "AAPL"

    def test_none_returns_empty(self):
        assert format_asset_display(None) == ""

    def test_empty_list(self):
        assert format_asset_display([]) == ""

    def test_max_count_5(self):
        assets = ["A", "B", "C", "D", "E", "F"]
        result = format_asset_display(assets, max_count=5)
        assert result == "A, B, C, D, E +1"


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if isinstance(component, (int, float)):
        return str(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, (int, float)):
            parts.append(str(children))
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)
