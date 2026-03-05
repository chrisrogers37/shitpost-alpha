"""Tests for shitty_ui/components/screener.py - Asset screener table component."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
from dash import html, dcc

from components.screener import (
    build_screener_table,
    _heat_bg,
    _hex_to_rgb,
    _text_color,
    _sentiment_badge,
    _screener_sector_badge,
    _SECTOR_ABBREV,
    _SUCCESS_RGB,
    _DANGER_RGB,
)
from constants import COLORS, SENTIMENT_COLORS, SENTIMENT_BG_COLORS


def _make_screener_df(n_rows=5):
    """Create a sample screener DataFrame for testing."""
    symbols = ["XLE", "DIS", "CMCSA", "LMT", "USO"][:n_rows]
    return pd.DataFrame(
        {
            "symbol": symbols,
            "total_predictions": [29, 17, 17, 16, 15][:n_rows],
            "correct": [14, 8, 7, 9, 7][:n_rows],
            "incorrect": [15, 9, 10, 7, 8][:n_rows],
            "avg_return": [2.48, -2.58, -1.53, 3.00, 1.81][:n_rows],
            "total_pnl": [719.0, -438.0, -259.0, 481.0, 271.0][:n_rows],
            "accuracy": [48.3, 47.1, 41.2, 56.3, 46.7][:n_rows],
            "latest_sentiment": [
                "bullish",
                "bearish",
                "bullish",
                "bullish",
                "neutral",
            ][:n_rows],
            "avg_confidence": [0.72, 0.65, 0.58, 0.80, 0.55][:n_rows],
        }
    )


def _make_sparkline_data():
    """Create sample sparkline data dict."""
    dates = pd.to_datetime(["2025-06-01", "2025-06-02", "2025-06-03"])
    return {
        "XLE": pd.DataFrame({"date": dates, "close": [80.0, 81.5, 82.0]}),
        "DIS": pd.DataFrame({"date": dates, "close": [100.0, 99.0, 98.5]}),
        "LMT": pd.DataFrame({"date": dates, "close": [450.0, 455.0, 460.0]}),
    }


# ── hex_to_rgb ────────────────────────────────────────────────────────


class TestHexToRgb:
    """Tests for _hex_to_rgb helper."""

    def test_converts_success_color(self):
        assert _hex_to_rgb(COLORS["success"]) == _SUCCESS_RGB

    def test_converts_danger_color(self):
        assert _hex_to_rgb(COLORS["danger"]) == _DANGER_RGB

    def test_converts_with_hash(self):
        assert _hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_converts_without_hash(self):
        assert _hex_to_rgb("00FF00") == (0, 255, 0)


# ── heat_bg ───────────────────────────────────────────────────────────


class TestHeatBg:
    """Tests for heat-mapped background color helper."""

    def test_positive_value_returns_green(self):
        result = _heat_bg(3.0, threshold=5.0)
        r, g, b = _SUCCESS_RGB
        assert f"rgba({r}, {g}, {b}," in result

    def test_negative_value_returns_red(self):
        result = _heat_bg(-2.5, threshold=5.0)
        r, g, b = _DANGER_RGB
        assert f"rgba({r}, {g}, {b}," in result

    def test_zero_returns_transparent(self):
        assert _heat_bg(0.0, threshold=5.0) == "rgba(0, 0, 0, 0)"

    def test_intensity_scales_with_value(self):
        # 3/5 * 0.15 = 0.09
        result = _heat_bg(3.0, threshold=5.0)
        assert "0.090" in result

    def test_intensity_caps_at_max(self):
        # 10/5 > 1.0 → capped at 1.0 * 0.15 = 0.15
        result = _heat_bg(10.0, threshold=5.0)
        assert "0.150" in result

    def test_win_rate_above_50_returns_green(self):
        result = _heat_bg(65.0, threshold=20.0, center=50.0)
        r, g, b = _SUCCESS_RGB
        assert f"rgba({r}, {g}, {b}," in result

    def test_win_rate_below_50_returns_red(self):
        result = _heat_bg(35.0, threshold=20.0, center=50.0)
        r, g, b = _DANGER_RGB
        assert f"rgba({r}, {g}, {b}," in result

    def test_win_rate_at_50_returns_transparent(self):
        assert _heat_bg(50.0, threshold=20.0, center=50.0) == "rgba(0, 0, 0, 0)"


# ── text_color ────────────────────────────────────────────────────────


class TestTextColor:
    """Tests for text color helper."""

    def test_positive_returns_success(self):
        assert _text_color(1.0) == COLORS["success"]

    def test_negative_returns_danger(self):
        assert _text_color(-1.0) == COLORS["danger"]

    def test_zero_returns_muted(self):
        assert _text_color(0.0) == COLORS["text_muted"]

    def test_custom_center(self):
        assert _text_color(60.0, center=50.0) == COLORS["success"]
        assert _text_color(40.0, center=50.0) == COLORS["danger"]


# ── sentiment_badge ───────────────────────────────────────────────────


class TestSentimentBadge:
    """Tests for sentiment badge rendering."""

    def test_bullish_shows_bull(self):
        badge = _sentiment_badge("bullish")
        assert badge.children == "BULL"
        assert badge.style["color"] == SENTIMENT_COLORS["bullish"]

    def test_bearish_shows_bear(self):
        badge = _sentiment_badge("bearish")
        assert badge.children == "BEAR"
        assert badge.style["color"] == SENTIMENT_COLORS["bearish"]

    def test_neutral_shows_neut(self):
        badge = _sentiment_badge("neutral")
        assert badge.children == "NEUT"
        assert badge.style["color"] == SENTIMENT_COLORS["neutral"]

    def test_none_defaults_to_neutral(self):
        badge = _sentiment_badge(None)
        assert badge.children == "NEUT"
        assert badge.style["color"] == SENTIMENT_COLORS["neutral"]

    def test_case_insensitive(self):
        badge = _sentiment_badge("BULLISH")
        assert badge.children == "BULL"

    def test_has_pill_styling(self):
        badge = _sentiment_badge("bullish")
        assert badge.style["borderRadius"] == "9999px"
        assert badge.style["textTransform"] == "uppercase"


# ── build_screener_table ──────────────────────────────────────────────


class TestBuildScreenerTable:
    """Tests for the main screener table builder."""

    def test_returns_div_with_data(self):
        result = build_screener_table(_make_screener_df(), _make_sparkline_data())
        assert isinstance(result, html.Div)

    def test_table_has_correct_row_count(self):
        result = build_screener_table(_make_screener_df(5), _make_sparkline_data())
        table = result.children
        assert isinstance(table, html.Table)
        tbody = table.children[1]
        assert len(tbody.children) == 5

    def test_empty_df_returns_empty_state(self):
        result = build_screener_table(pd.DataFrame(), {})
        # Should NOT contain an html.Table
        assert not isinstance(result.children, html.Table)

    def test_missing_sparkline_gets_placeholder(self):
        """CMCSA and USO have no sparkline data."""
        df = _make_screener_df(5)
        sparklines = _make_sparkline_data()  # Only XLE, DIS, LMT
        result = build_screener_table(df, sparklines)
        table = result.children
        tbody = table.children[1]
        # Row 2 (CMCSA) should have a placeholder in cell 2 (sparkline, after sector)
        cmcsa_row = tbody.children[2]
        spark_cell = cmcsa_row.children[2]
        # Placeholder is an html.Div, not a dcc.Graph
        assert not isinstance(spark_cell.children, dcc.Graph)

    def test_sort_by_total_pnl_descending(self):
        df = _make_screener_df(5)
        result = build_screener_table(
            df, {}, sort_column="total_pnl", sort_ascending=False
        )
        table = result.children
        tbody = table.children[1]
        # First row should be XLE (highest P&L = 719)
        first_ticker = tbody.children[0].children[0].children
        assert first_ticker.children == "XLE"

    def test_sort_by_accuracy_ascending(self):
        df = _make_screener_df(5)
        result = build_screener_table(
            df, {}, sort_column="accuracy", sort_ascending=True
        )
        table = result.children
        tbody = table.children[1]
        # First row should be CMCSA (lowest accuracy = 41.2)
        first_ticker = tbody.children[0].children[0].children
        assert first_ticker.children == "CMCSA"

    def test_row_has_screener_row_class(self):
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        tbody = table.children[1]
        row = tbody.children[0]
        assert row.className == "screener-row"

    def test_row_has_pattern_match_id(self):
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        tbody = table.children[1]
        row = tbody.children[0]
        assert row.id == {"type": "screener-row", "index": "XLE"}

    def test_asset_link_href(self):
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        tbody = table.children[1]
        row = tbody.children[0]
        link = row.children[0].children  # First td -> dcc.Link
        assert link.href == "/assets/XLE"

    def test_header_has_nine_columns(self):
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        thead = table.children[0]
        header_row = thead.children
        assert len(header_row.children) == 9

    def test_sparkline_cell_has_hide_class(self):
        """Sparkline column should have screener-hide-mobile class."""
        result = build_screener_table(_make_screener_df(1), _make_sparkline_data())
        table = result.children
        tbody = table.children[1]
        spark_td = tbody.children[0].children[2]  # After sector column
        assert "screener-hide-mobile" in spark_td.className

    def test_confidence_cell_has_hide_class(self):
        """Confidence column should have screener-hide-mobile class."""
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        tbody = table.children[1]
        # Confidence is the last column (index 8, after adding sector)
        conf_td = tbody.children[0].children[8]
        assert "screener-hide-mobile" in conf_td.className

    def test_heat_mapped_return_positive_has_green_bg(self):
        """Positive avg_return should get green background."""
        result = build_screener_table(
            _make_screener_df(1),
            {},  # XLE has avg_return=2.48
        )
        table = result.children
        tbody = table.children[1]
        # 7d Return is column index 5 (after sector column)
        return_td = tbody.children[0].children[5]
        bg = return_td.style["backgroundColor"]
        r, g, b = _SUCCESS_RGB
        assert f"rgba({r}, {g}, {b}," in bg


# ── screener_sector_badge ────────────────────────────────────────────


class TestScreenerSectorBadge:
    """Tests for _screener_sector_badge helper."""

    def test_renders_known_sector_abbreviation(self):
        badge = _screener_sector_badge("Technology")
        assert badge.children == "TECH"

    def test_renders_unknown_sector_truncated(self):
        badge = _screener_sector_badge("Quantum Computing")
        assert badge.children == "QUAN"

    def test_renders_dash_for_none_sector(self):
        badge = _screener_sector_badge(None)
        assert badge.children == "-"

    def test_sector_badge_has_tooltip(self):
        badge = _screener_sector_badge("Financial Services")
        assert badge.title == "Financial Services"
        assert badge.children == "FIN"


# ── build_screener_table with sectors ────────────────────────────────


class TestBuildScreenerTableWithSectors:
    """Tests for sector integration in the screener table."""

    def test_table_has_sector_column_header(self):
        result = build_screener_table(_make_screener_df(1), {})
        table = result.children
        thead = table.children[0]
        header_row = thead.children
        # Sector is the second column header (index 1)
        sector_th = header_row.children[1]
        assert sector_th.children == "Sector"

    def test_rows_include_sector_badges(self):
        sector_data = {"XLE": "Energy", "DIS": "Communication Services"}
        result = build_screener_table(_make_screener_df(2), {}, sector_data=sector_data)
        table = result.children
        tbody = table.children[1]
        # XLE row: sector cell at index 1
        xle_sector_td = tbody.children[0].children[1]
        assert xle_sector_td.children.children == "ENGY"
        # DIS row: sector cell at index 1
        dis_sector_td = tbody.children[1].children[1]
        assert dis_sector_td.children.children == "COMM"

    def test_works_without_sector_data(self):
        """sector_data=None should render dashes for all sectors."""
        result = build_screener_table(_make_screener_df(1), {}, sector_data=None)
        table = result.children
        tbody = table.children[1]
        sector_td = tbody.children[0].children[1]
        assert sector_td.children.children == "-"
