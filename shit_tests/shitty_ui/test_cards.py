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
    create_empty_state_html,
    get_sentiment_style,
    _build_expandable_thesis,
)
from constants import COLORS, SENTIMENT_COLORS, SENTIMENT_BG_COLORS


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


def _find_component_by_pattern_id(component, type_str, index):
    """Recursively find a component whose id matches {"type": type_str, "index": index}."""
    comp_id = getattr(component, "id", None)
    if (
        isinstance(comp_id, dict)
        and comp_id.get("type") == type_str
        and comp_id.get("index") == index
    ):
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            if child is not None and not isinstance(child, str):
                result = _find_component_by_pattern_id(child, type_str, index)
                if result:
                    return result
    elif not isinstance(children, str):
        result = _find_component_by_pattern_id(children, type_str, index)
        if result:
            return result
    return None


class TestExpandableThesis:
    """Tests for expandable thesis rendering in signal feed cards."""

    def test_short_thesis_no_toggle(self):
        """Short thesis (<= 120 chars) should render as plain text, no toggle."""
        short_thesis = "Tariffs will boost domestic steel production."
        card = create_feed_signal_card(
            _make_row(thesis=short_thesis), card_index=0
        )
        text = _extract_text(card)
        assert short_thesis in text
        assert "Show full thesis" not in text

    def test_long_thesis_shows_truncated_preview(self):
        """Long thesis (> 120 chars) should show truncated preview by default."""
        long_thesis = "A" * 200
        card = create_feed_signal_card(
            _make_row(thesis=long_thesis), card_index=1
        )
        text = _extract_text(card)
        assert "A" * 120 + "..." in text
        assert "Show full thesis" in text

    def test_long_thesis_contains_full_text_hidden(self):
        """Long thesis should have the full text in a hidden element."""
        long_thesis = "B" * 300
        card = create_feed_signal_card(
            _make_row(thesis=long_thesis), card_index=2
        )
        full_el = _find_component_by_pattern_id(card, "thesis-full", 2)
        assert full_el is not None
        assert full_el.style.get("display") == "none"
        assert full_el.children == long_thesis

    def test_toggle_has_pattern_matching_id(self):
        """Toggle div should have pattern-matching ID with correct index."""
        card = create_feed_signal_card(
            _make_row(thesis="X" * 200), card_index=42
        )
        toggle = _find_component_by_pattern_id(card, "thesis-toggle", 42)
        assert toggle is not None
        assert toggle.id == {"type": "thesis-toggle", "index": 42}
        assert toggle.n_clicks == 0

    def test_empty_thesis_no_expand_section(self):
        """Empty thesis should not render any thesis section."""
        card = create_feed_signal_card(
            _make_row(thesis=""), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text

    def test_none_thesis_no_expand_section(self):
        """None thesis should not render any thesis section."""
        card = create_feed_signal_card(
            _make_row(thesis=None), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text

    def test_thesis_exactly_at_boundary_no_toggle(self):
        """Thesis exactly 120 chars should NOT show toggle."""
        thesis_120 = "C" * 120
        card = create_feed_signal_card(
            _make_row(thesis=thesis_120), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text
        assert thesis_120 in text

    def test_thesis_one_over_boundary_shows_toggle(self):
        """Thesis at 121 chars should show toggle."""
        thesis_121 = "D" * 121
        card = create_feed_signal_card(
            _make_row(thesis=thesis_121), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" in text

    def test_card_index_default_zero(self):
        """Card should render without explicit card_index (defaults to 0)."""
        card = create_feed_signal_card(
            _make_row(thesis="E" * 200)
        )
        toggle = _find_component_by_pattern_id(card, "thesis-toggle", 0)
        assert toggle is not None

    def test_backward_compatible_without_card_index(self):
        """Existing callers that don't pass card_index should still work."""
        card = create_feed_signal_card(_make_row(thesis="Short"))
        assert card is not None


class TestExpandableThesisPostCard:
    """Tests for expandable thesis in create_post_card()."""

    def test_post_card_short_thesis_no_toggle(self):
        """Post card with short thesis (<=200 chars) shows full text, no toggle."""
        card = create_post_card(
            _make_row(thesis="Short thesis text"), card_index=0
        )
        text = _extract_text(card)
        assert "Short thesis text" in text
        assert "Show full thesis" not in text

    def test_post_card_long_thesis_shows_toggle(self):
        """Post card with long thesis (>200 chars) shows truncated preview + toggle."""
        long_thesis = "F" * 300
        card = create_post_card(
            _make_row(thesis=long_thesis), card_index=0
        )
        text = _extract_text(card)
        assert "F" * 200 + "..." in text
        assert "Show full thesis" in text

    def test_post_card_uses_post_thesis_prefix(self):
        """Post card toggle should use 'post-thesis' prefix for ID types."""
        card = create_post_card(
            _make_row(thesis="G" * 250), card_index=5
        )
        toggle = _find_component_by_pattern_id(card, "post-thesis-toggle", 5)
        assert toggle is not None

    def test_post_card_backward_compatible(self):
        """create_post_card() without card_index should still work."""
        card = create_post_card(_make_row(thesis="G" * 250))
        assert card is not None


class TestBuildExpandableThesisHelper:
    """Tests for the _build_expandable_thesis() helper function."""

    def test_short_text_returns_plain_p(self):
        """Text under threshold returns a plain html.P."""
        from dash import html

        result = _build_expandable_thesis("Short", card_index=0, truncate_len=120)
        assert isinstance(result, html.P)
        assert result.children == "Short"

    def test_long_text_returns_div_with_three_children(self):
        """Text over threshold returns html.Div with preview, full, toggle."""
        from dash import html

        result = _build_expandable_thesis("H" * 200, card_index=5, truncate_len=120)
        assert isinstance(result, html.Div)
        assert len(result.children) == 3

    def test_custom_truncate_len(self):
        """Custom truncate_len is respected."""
        result = _build_expandable_thesis("I" * 60, card_index=0, truncate_len=50)
        from dash import html

        assert isinstance(result, html.Div)
        preview = result.children[0]
        assert preview.children == "I" * 50 + "..."

    def test_custom_id_prefix(self):
        """Custom id_prefix changes the component ID types."""
        result = _build_expandable_thesis(
            "J" * 200, card_index=3, id_prefix="post-thesis"
        )
        toggle = result.children[2]
        assert toggle.id == {"type": "post-thesis-toggle", "index": 3}


class TestEmptyStateHtml:
    """Tests for create_empty_state_html function."""

    def test_returns_html_div(self):
        """Test that function returns a Dash html.Div."""
        from dash import html

        result = create_empty_state_html("No data here")
        assert isinstance(result, html.Div)

    def test_message_appears_in_text(self):
        """Test that the primary message appears in the output."""
        result = create_empty_state_html("Nothing to show")
        # The message is in a Span inside the first child Div
        inner_div = result.children[0]
        span = inner_div.children[1]
        assert "Nothing to show" in span.children

    def test_hint_appears_when_provided(self):
        """Test that hint text renders when provided."""
        result = create_empty_state_html("Main", hint="Some hint")
        # hint is the first sub_child after the main div
        hint_div = result.children[1]
        assert "Some hint" in hint_div.children

    def test_context_line_appears_when_provided(self):
        """Test that context_line renders when provided."""
        result = create_empty_state_html("Main", context_line="42 trades all-time")
        # context_line is a sub_child
        found = False
        for child in result.children[1:]:
            if hasattr(child, "children") and "42 trades all-time" in str(child.children):
                found = True
                break
        assert found

    def test_action_text_with_href_creates_link(self):
        """Test that action_text with action_href creates a dcc.Link."""
        from dash import dcc

        result = create_empty_state_html(
            "Main", action_text="Go to performance", action_href="/performance"
        )
        # Find the link in sub_children
        found_link = False
        for child in result.children[1:]:
            inner = child.children if hasattr(child, "children") else None
            if isinstance(inner, dcc.Link):
                assert inner.href == "/performance"
                found_link = True
                break
        assert found_link

    def test_action_text_without_href_creates_span(self):
        """Test that action_text without href creates a plain Span."""
        from dash import html

        result = create_empty_state_html("Main", action_text="Try expanding to All")
        found_span = False
        for child in result.children[1:]:
            inner = child.children if hasattr(child, "children") else None
            if isinstance(inner, html.Span):
                assert "Try expanding to All" in inner.children
                found_span = True
                break
        assert found_span

    def test_icon_class_applied(self):
        """Test that a custom icon class is applied."""
        result = create_empty_state_html("Main", icon_class="fas fa-rocket")
        icon = result.children[0].children[0]
        assert "fas fa-rocket" in icon.className

    def test_minimal_call_only_message(self):
        """Test that calling with just a message works without extras."""
        result = create_empty_state_html("Just a message")
        # Should have 1 child (the main div with icon+span), no sub_children
        assert len(result.children) == 1
        assert result.style["textAlign"] == "center"
