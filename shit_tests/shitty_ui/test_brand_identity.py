"""Tests for brand identity integration across UI components.

Verifies that COPY strings from brand_copy.py are actually used
in rendered components, not just defined.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

from brand_copy import COPY


def _extract_all_text(component) -> str:
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
                    parts.append(_extract_all_text(child))
        elif children is not None:
            parts.append(_extract_all_text(children))
    return " ".join(parts)


class TestHeaderBranding:
    """Test that header components use branded copy."""

    def test_header_contains_branded_subtitle(self):
        from components.header import create_header

        header = create_header()
        text = _extract_all_text(header)
        assert COPY["app_subtitle"] in text

    def test_header_does_not_contain_old_subtitle(self):
        from components.header import create_header

        header = create_header()
        text = _extract_all_text(header)
        assert "Trading Intelligence Dashboard" not in text

    def test_footer_contains_branded_disclaimer(self):
        from components.header import create_footer

        footer = create_footer()
        text = _extract_all_text(footer)
        assert "rent money" in text.lower()

    def test_footer_contains_branded_source_link(self):
        from components.header import create_footer

        footer = create_footer()
        text = _extract_all_text(footer)
        assert COPY["footer_source_link"] in text


class TestDashboardBranding:
    """Test that dashboard page uses branded copy."""

    def test_dashboard_layout_contains_latest_shitposts(self):
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        text = _extract_all_text(page)
        assert COPY["latest_posts_header"] in text

    def test_dashboard_layout_contains_analytics_header(self):
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        text = _extract_all_text(page)
        assert COPY["analytics_header"] in text

    def test_dashboard_layout_does_not_contain_old_analytics(self):
        """The old generic 'Analytics' header is replaced with 'The Numbers'."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        text = _extract_all_text(page)
        assert COPY["analytics_header"] in text


class TestSignalsPageBranding:
    """Test that signals page uses branded copy."""

    def test_signals_page_contains_branded_subtitle(self):
        from pages.signals import create_signal_feed_page

        page = create_signal_feed_page()
        text = _extract_all_text(page)
        assert COPY["signals_page_subtitle"] in text

    def test_signals_page_does_not_contain_old_subtitle(self):
        from pages.signals import create_signal_feed_page

        page = create_signal_feed_page()
        text = _extract_all_text(page)
        assert "Live predictions from Trump" not in text


class TestTrendsPageBranding:
    """Test that trends page uses branded copy."""

    def test_trends_page_contains_branded_subtitle(self):
        from pages.trends import create_trends_page

        page = create_trends_page()
        text = _extract_all_text(page)
        assert COPY["trends_page_subtitle"] in text

    def test_trends_page_contains_branded_chart_default(self):
        from pages.trends import create_trends_page

        page = create_trends_page()
        text = _extract_all_text(page)
        assert COPY["trends_chart_default"] in text


class TestAssetPageBranding:
    """Test that asset page uses branded copy."""

    def test_asset_header_contains_branded_subtitle(self):
        from pages.assets import create_asset_header

        header = create_asset_header("AAPL")
        text = _extract_all_text(header)
        expected = COPY["asset_page_subtitle"].format(symbol="AAPL")
        assert expected in text

    def test_asset_header_does_not_contain_old_subtitle(self):
        from pages.assets import create_asset_header

        header = create_asset_header("TSLA")
        text = _extract_all_text(header)
        assert "Prediction Performance Deep Dive" not in text
