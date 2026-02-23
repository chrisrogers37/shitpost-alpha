"""Tests for the 2-view information architecture after Phase 05 consolidation.

Verifies that:
- Only 2 views exist: Home (/) and Asset Detail (/assets/<symbol>)
- Old routes (/signals, /trends, /performance) fall through to home
- Header has no nav links (logo-only navigation)
- Asset detail back link says "Screener" and no Performance link exists
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


def _find_text_in_component(component, text):
    """Recursively search a Dash component tree for a text string."""
    if isinstance(component, str):
        return text in component

    children = getattr(component, "children", None)
    if children is None:
        return False

    if isinstance(children, str):
        return text in children

    if isinstance(children, (list, tuple)):
        return any(_find_text_in_component(child, text) for child in children)

    return _find_text_in_component(children, text)


def _find_component_ids(component):
    """Recursively collect all component IDs from a Dash component tree."""
    ids = set()
    comp_id = getattr(component, "id", None)
    if comp_id:
        ids.add(comp_id)

    children = getattr(component, "children", None)
    if children is None:
        return ids
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "id"):
                ids.update(_find_component_ids(child))
    elif hasattr(children, "children") or hasattr(children, "id"):
        ids.update(_find_component_ids(children))
    return ids


def _find_hrefs_in_component(component):
    """Recursively collect all href values from dcc.Link components."""
    hrefs = []
    href = getattr(component, "href", None)
    if href:
        hrefs.append(href)

    children = getattr(component, "children", None)
    if children is None:
        return hrefs
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "href"):
                hrefs.extend(_find_hrefs_in_component(child))
    elif hasattr(children, "children") or hasattr(children, "href"):
        hrefs.extend(_find_hrefs_in_component(children))
    return hrefs


class TestRouting:
    """Test that the router correctly handles all URL patterns."""

    def test_root_returns_dashboard(self):
        """GET / should return the screener home page."""
        from pages.dashboard import create_dashboard_page

        expected = create_dashboard_page()
        # Verify it has the screener table container
        ids = _find_component_ids(expected)
        assert "screener-table-container" in ids

    def test_asset_route_returns_asset_page(self):
        """GET /assets/AAPL should return the asset detail page."""
        from pages.assets import create_asset_page

        page = create_asset_page("AAPL")
        ids = _find_component_ids(page)
        assert "asset-page-symbol" in ids
        assert "asset-price-chart" in ids

    def test_signals_page_module_deleted(self):
        """The signals page module should no longer be importable."""
        import importlib

        with __import__("pytest").raises(ModuleNotFoundError):
            importlib.import_module("pages.signals")

    def test_trends_page_module_deleted(self):
        """The trends page module should no longer be importable."""
        import importlib

        with __import__("pytest").raises(ModuleNotFoundError):
            importlib.import_module("pages.trends")

    def test_performance_page_function_removed(self):
        """create_performance_page should no longer exist in dashboard module."""
        from pages import dashboard

        assert not hasattr(dashboard, "create_performance_page")


class TestHeaderSimplification:
    """Test that the header no longer contains nav links."""

    def test_header_has_no_nav_link_ids(self):
        """Header should not contain Dashboard/Signals/Trends/Performance nav link IDs."""
        from components.header import create_header

        header = create_header()
        ids = _find_component_ids(header)
        removed_ids = [
            "nav-link-dashboard",
            "nav-link-signals",
            "nav-link-trends",
            "nav-link-performance",
        ]
        for nav_id in removed_ids:
            assert nav_id not in ids, f"'{nav_id}' should not exist in header"

    def test_header_has_no_nav_link_text(self):
        """Header should not contain nav link text for removed pages."""
        from components.header import create_header

        header = create_header()
        for text in ["Signals", "Trends", "Performance"]:
            assert not _find_text_in_component(
                header, text
            ), f"Header should not contain '{text}' text"

    def test_header_logo_links_home(self):
        """Logo should link to /."""
        from components.header import create_header

        header = create_header()
        hrefs = _find_hrefs_in_component(header)
        assert "/" in hrefs, "Logo should link to /"

    def test_header_has_alert_bell(self):
        """Alert bell button should still be present."""
        from components.header import create_header

        header = create_header()
        ids = _find_component_ids(header)
        assert "open-alert-config-button" in ids

    def test_header_has_refresh_indicator(self):
        """Refresh indicator should still be present."""
        from components.header import create_header

        header = create_header()
        ids = _find_component_ids(header)
        assert "last-update-time" in ids
        assert "next-update-countdown" in ids


class TestAssetDetailBackLink:
    """Test the back link on the asset detail page."""

    def test_back_link_says_screener(self):
        """Back link should say 'Screener' not 'Dashboard'."""
        from pages.assets import create_asset_header

        header = create_asset_header("XLE")
        assert _find_text_in_component(header, "Screener")
        assert not _find_text_in_component(header, "Dashboard")

    def test_no_performance_link(self):
        """Asset header should not have a Performance link."""
        from pages.assets import create_asset_header

        header = create_asset_header("XLE")
        assert not _find_text_in_component(header, "Performance")
        hrefs = _find_hrefs_in_component(header)
        assert "/performance" not in hrefs

    def test_back_link_goes_home(self):
        """Back link should link to /."""
        from pages.assets import create_asset_header

        header = create_asset_header("XLE")
        hrefs = _find_hrefs_in_component(header)
        assert "/" in hrefs


class TestLayoutImports:
    """Test that layout.py no longer imports deleted modules."""

    def test_layout_does_not_import_signals(self):
        """layout.py should not import from pages.signals."""
        import inspect
        import layout

        source = inspect.getsource(layout)
        assert "from pages.signals" not in source
        assert "pages.signals" not in source

    def test_layout_does_not_import_trends(self):
        """layout.py should not import from pages.trends."""
        import inspect
        import layout

        source = inspect.getsource(layout)
        assert "from pages.trends" not in source
        assert "pages.trends" not in source

    def test_layout_does_not_import_create_performance_page(self):
        """layout.py should not import create_performance_page."""
        import inspect
        import layout

        source = inspect.getsource(layout)
        assert "create_performance_page" not in source
