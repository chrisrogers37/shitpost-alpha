"""Tests for shitty_ui/components/cards.py - Card components and helpers."""

import sys
import os

# Add shitty_ui to path for imports (matches pattern from test_charts.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from datetime import datetime

from components.cards import strip_urls


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
