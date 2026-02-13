"""Tests for shitty_ui/components/cards.py - Card components and helpers."""

import sys
import os

# Add shitty_ui to path for imports (matches pattern from test_charts.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from datetime import datetime

from components.cards import (
    strip_urls,
    create_hero_signal_card,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_feed_signal_card,
    get_sentiment_style,
)
from constants import SENTIMENT_COLORS, SENTIMENT_BG_COLORS


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)


def _make_row(**overrides):
    """Create a minimal row dict for card rendering."""
    base = {
        "timestamp": datetime(2025, 6, 15, 10, 30),
        "text": "Big announcement about tariffs today",
        "confidence": 0.75,
        "assets": ["AAPL", "TSLA"],
        "market_impact": {"AAPL": "bullish"},
        "correct_t7": None,
        "pnl_t7": None,
        "analysis_status": "completed",
        "thesis": "Tariffs expected to boost domestic production",
        "replies_count": 10,
        "reblogs_count": 5,
        "favourites_count": 20,
    }
    base.update(overrides)
    return base


def _make_timeline_row(**overrides):
    """Create a minimal row dict for prediction timeline card."""
    base = {
        "prediction_date": datetime(2025, 6, 15),
        "timestamp": datetime(2025, 6, 15, 10, 30),
        "text": "Trade deal announcement",
        "prediction_sentiment": "bullish",
        "prediction_confidence": 0.75,
        "return_t7": 2.5,
        "correct_t7": True,
        "pnl_t7": 250.0,
        "price_at_prediction": 150.0,
        "price_t7": 153.75,
    }
    base.update(overrides)
    return base


class TestStripUrls:
    """Tests for the strip_urls helper function."""

    def test_removes_https_url(self):
        """Test that a single https URL is removed."""
        text = "Check this out https://www.wsj.com/article/something great news"
        assert strip_urls(text) == "Check this out great news"

    def test_removes_http_url(self):
        """Test that a single http URL is removed."""
        text = "See http://example.com/path for details"
        assert strip_urls(text) == "See for details"

    def test_removes_url_with_long_path(self):
        """Test removal of URLs with long paths and query params."""
        text = "Breaking https://www.wsj.com/politics/national-security/pentagon-prepares-second-aircraft-carrier-to-deploy-to-the-middle-east-e7140a64 wow"
        assert strip_urls(text) == "Breaking wow"

    def test_removes_url_with_query_params(self):
        """Test removal of URLs with query parameters."""
        text = "Link https://example.com/page?foo=bar&baz=qux#section end"
        assert strip_urls(text) == "Link end"

    def test_removes_multiple_urls(self):
        """Test that multiple URLs in the same text are all removed."""
        text = "See https://a.com and https://b.com/path for info"
        assert strip_urls(text) == "See and for info"

    def test_text_with_no_urls_unchanged(self):
        """Test that text without URLs passes through unchanged."""
        text = "This is a normal post about tariffs"
        assert strip_urls(text) == "This is a normal post about tariffs"

    def test_empty_string(self):
        """Test that an empty string returns the link placeholder."""
        assert strip_urls("") == "[link]"

    def test_url_only_text_returns_placeholder(self):
        """Test that text consisting only of a URL returns '[link]'."""
        assert strip_urls("https://example.com/some/long/path") == "[link]"

    def test_multiple_urls_only_returns_placeholder(self):
        """Test text with only URLs and whitespace returns placeholder."""
        assert strip_urls("https://a.com https://b.com") == "[link]"

    def test_collapses_double_spaces(self):
        """Test that spaces left by URL removal are collapsed."""
        text = "Before https://url.com after"
        result = strip_urls(text)
        assert "  " not in result
        assert result == "Before after"

    def test_strips_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "https://url.com some text"
        assert strip_urls(text) == "some text"

    def test_url_at_end_of_text(self):
        """Test URL at the end of the text."""
        text = "Great article here https://example.com/article"
        assert strip_urls(text) == "Great article here"

    def test_url_at_start_of_text(self):
        """Test URL at the start of the text."""
        text = "https://example.com/article Great article here"
        assert strip_urls(text) == "Great article here"

    def test_preserves_non_url_content(self):
        """Test that dollar amounts, tickers, etc. are preserved."""
        text = "$AAPL is up 5% today https://finance.yahoo.com/quote/AAPL check it"
        assert strip_urls(text) == "$AAPL is up 5% today check it"

    def test_does_not_strip_bare_domains(self):
        """Test that bare domains without protocol are NOT stripped."""
        text = "Visit wsj.com for more info"
        assert strip_urls(text) == "Visit wsj.com for more info"

    def test_url_with_parentheses(self):
        """Test URL containing parentheses (e.g., Wikipedia)."""
        text = "See https://en.wikipedia.org/wiki/Test_(computing) for more"
        result = strip_urls(text)
        # The regex will consume up to the closing paren since it's non-whitespace
        assert "https://" not in result

    def test_preserves_newlines(self):
        """Test that newlines in text are preserved."""
        text = "First line\nhttps://url.com\nThird line"
        assert strip_urls(text) == "First line\n\nThird line"


class TestConfidenceDisplayConsistency:
    """Verify all card types display confidence in standardized format."""

    def test_hero_signal_card_no_conf_label(self):
        """Hero signal card should show '75%' not 'Conf: 75%'."""
        card = create_hero_signal_card(_make_row(confidence=0.75))
        text = _extract_text(card)
        assert "75%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_signal_card_bare_percentage(self):
        """Signal card should show bare percentage."""
        card = create_signal_card(_make_row(confidence=0.80))
        text = _extract_text(card)
        assert "80%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_post_card_no_confidence_label(self):
        """Post card should show '| 75%' not '| Confidence: 75%'."""
        card = create_post_card(_make_row(confidence=0.75))
        text = _extract_text(card)
        assert "75%" in text
        assert "Confidence:" not in text

    def test_prediction_timeline_card_no_confidence_label(self):
        """Prediction timeline card should show '| 75%' not '| Confidence: 75%'."""
        card = create_prediction_timeline_card(
            _make_timeline_row(prediction_confidence=0.75)
        )
        text = _extract_text(card)
        assert "75%" in text
        assert "Confidence:" not in text

    def test_feed_signal_card_bare_percentage(self):
        """Feed signal card should show bare percentage."""
        card = create_feed_signal_card(_make_row(confidence=0.85))
        text = _extract_text(card)
        assert "85%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_confidence_zero_renders(self):
        """0% confidence should still render, not be suppressed."""
        card = create_hero_signal_card(_make_row(confidence=0.0))
        text = _extract_text(card)
        assert "0%" in text

    def test_confidence_one_hundred_renders(self):
        """100% confidence should render correctly."""
        card = create_signal_card(_make_row(confidence=1.0))
        text = _extract_text(card)
        assert "100%" in text

    def test_post_card_no_confidence_when_none(self):
        """Post card should render empty string when confidence is None."""
        card = create_post_card(_make_row(confidence=None))
        text = _extract_text(card)
        assert "Confidence:" not in text
        # Should not crash

    def test_prediction_timeline_no_confidence_when_zero(self):
        """Prediction timeline card hides confidence when falsy (0)."""
        card = create_prediction_timeline_card(
            _make_timeline_row(prediction_confidence=0)
        )
        text = _extract_text(card)
        # When confidence is 0 (falsy), the conditional hides it entirely
        assert "Confidence:" not in text


class TestGetSentimentStyle:
    """Tests for the get_sentiment_style helper function."""

    def test_bullish_returns_green(self):
        style = get_sentiment_style("bullish")
        assert style["color"] == SENTIMENT_COLORS["bullish"]
        assert style["bg_color"] == SENTIMENT_BG_COLORS["bullish"]
        assert style["icon"] == "arrow-up"

    def test_bearish_returns_red(self):
        style = get_sentiment_style("bearish")
        assert style["color"] == SENTIMENT_COLORS["bearish"]
        assert style["bg_color"] == SENTIMENT_BG_COLORS["bearish"]
        assert style["icon"] == "arrow-down"

    def test_neutral_returns_gray(self):
        style = get_sentiment_style("neutral")
        assert style["color"] == SENTIMENT_COLORS["neutral"]
        assert style["bg_color"] == SENTIMENT_BG_COLORS["neutral"]
        assert style["icon"] == "minus"

    def test_none_defaults_to_neutral(self):
        style = get_sentiment_style(None)
        assert style["color"] == SENTIMENT_COLORS["neutral"]

    def test_case_insensitive(self):
        style = get_sentiment_style("BULLISH")
        assert style["color"] == SENTIMENT_COLORS["bullish"]

    def test_unknown_defaults_to_neutral(self):
        style = get_sentiment_style("confused")
        assert style["color"] == SENTIMENT_COLORS["neutral"]


class TestSentimentLeftBorder:
    """Verify all card types have a sentiment-colored left border."""

    def test_hero_card_has_left_border_bullish(self):
        card = create_hero_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_hero_card_has_left_border_bearish(self):
        card = create_hero_signal_card(_make_row(market_impact={"AAPL": "bearish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bearish"] in card.style["borderLeft"]

    def test_signal_card_has_left_border_bullish(self):
        card = create_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_signal_card_has_left_border_bearish(self):
        card = create_signal_card(_make_row(market_impact={"AAPL": "bearish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bearish"] in card.style["borderLeft"]

    def test_post_card_has_left_border_bullish(self):
        card = create_post_card(_make_row(market_impact={"AAPL": "bullish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_post_card_has_left_border_bearish(self):
        card = create_post_card(_make_row(market_impact={"AAPL": "bearish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bearish"] in card.style["borderLeft"]

    def test_post_card_has_left_border_neutral_when_bypassed(self):
        card = create_post_card(_make_row(analysis_status="bypassed", market_impact={}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["neutral"] in card.style["borderLeft"]

    def test_prediction_timeline_card_has_left_border_bullish(self):
        card = create_prediction_timeline_card(
            _make_timeline_row(prediction_sentiment="bullish")
        )
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_prediction_timeline_card_has_left_border_bearish(self):
        card = create_prediction_timeline_card(
            _make_timeline_row(prediction_sentiment="bearish")
        )
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bearish"] in card.style["borderLeft"]

    def test_feed_signal_card_has_left_border_bullish(self):
        card = create_feed_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_feed_signal_card_has_left_border_bearish(self):
        card = create_feed_signal_card(_make_row(market_impact={"AAPL": "bearish"}))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bearish"] in card.style["borderLeft"]

    def test_left_border_format_is_3px(self):
        """All left borders should be 3px solid."""
        card = create_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        assert card.style["borderLeft"].startswith("3px solid")


class TestSentimentBadgeBackground:
    """Verify sentiment badges have background fill colors."""

    def _extract_text(self, component) -> str:
        """Recursively extract all text from a Dash component."""
        parts = []
        if isinstance(component, str):
            return component
        if hasattr(component, "children"):
            children = component.children
            if isinstance(children, str):
                parts.append(children)
            elif isinstance(children, list):
                for child in children:
                    if child is not None:
                        parts.append(self._extract_text(child))
            elif children is not None:
                parts.append(self._extract_text(children))
        return " ".join(parts)

    def _find_sentiment_badge(self, component):
        """Find the deepest component containing the sentiment text with backgroundColor.

        Searches depth-first and returns the deepest (most specific) match,
        avoiding false positives from outer wrapper divs that also contain
        the sentiment text as descendants.
        """
        if not hasattr(component, "children"):
            return None

        # First, search children for a deeper match
        children = component.children
        if isinstance(children, list):
            for child in children:
                if child is not None and not isinstance(child, str):
                    result = self._find_sentiment_badge(child)
                    if result:
                        return result
        elif children is not None and not isinstance(children, str):
            result = self._find_sentiment_badge(children)
            if result:
                return result

        # No deeper match found -- check this component
        text = self._extract_text(component)
        if hasattr(component, "style") and isinstance(component.style, dict):
            if any(s in text for s in ["BULLISH", "BEARISH", "NEUTRAL"]):
                if "backgroundColor" in component.style:
                    return component
        return None

    def test_hero_card_badge_has_background(self):
        card = create_hero_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Sentiment badge with backgroundColor not found"
        assert SENTIMENT_BG_COLORS["bullish"] in badge.style["backgroundColor"]

    def test_signal_card_badge_has_background(self):
        card = create_signal_card(_make_row(market_impact={"AAPL": "bearish"}))
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Sentiment badge with backgroundColor not found"
        assert SENTIMENT_BG_COLORS["bearish"] in badge.style["backgroundColor"]

    def test_post_card_badge_has_background(self):
        card = create_post_card(_make_row(market_impact={"AAPL": "bullish"}))
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Sentiment badge with backgroundColor not found"

    def test_prediction_timeline_badge_has_background(self):
        card = create_prediction_timeline_card(
            _make_timeline_row(prediction_sentiment="bearish")
        )
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Sentiment badge with backgroundColor not found"

    def test_feed_signal_card_badge_has_background(self):
        card = create_feed_signal_card(_make_row(market_impact={"AAPL": "bullish"}))
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Sentiment badge with backgroundColor not found"

    def test_neutral_badge_has_background(self):
        card = create_signal_card(_make_row(market_impact={"AAPL": "neutral"}))
        badge = self._find_sentiment_badge(card)
        assert badge is not None, "Neutral sentiment badge should also have backgroundColor"
