"""Tests for _build_asset_signal_summary and _mini_stat_card in assets.py."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pandas as pd
from dash import html
import dash_bootstrap_components as dbc

from pages.assets import _build_asset_signal_summary, _mini_stat_card
from constants import COLORS


class TestBuildAssetSignalSummaryEmpty:
    """Tests for _build_asset_signal_summary with empty data."""

    def test_empty_dataframe_shows_message(self):
        """Empty predictions returns a 'no predictions' message."""
        result = _build_asset_signal_summary("XLE", pd.DataFrame())
        assert isinstance(result, html.Div)
        # Should contain P element with message
        inner_p = result.children
        assert isinstance(inner_p, html.P)
        assert "No predictions found for XLE" in inner_p.children


class TestBuildAssetSignalSummaryWithData:
    """Tests for _build_asset_signal_summary with prediction data."""

    @staticmethod
    def _make_predictions(n=10, bullish=6, evaluated=7, correct=4, total_pnl=150.0):
        """Build a predictions DataFrame for testing."""
        sentiments = ["bullish"] * bullish + ["bearish"] * (n - bullish)
        confidences = [0.7] * n
        correct_vals = (
            [True] * correct
            + [False] * (evaluated - correct)
            + [None] * (n - evaluated)
        )
        pnl_vals = [total_pnl / evaluated] * evaluated + [None] * (n - evaluated)

        return pd.DataFrame(
            {
                "prediction_sentiment": sentiments,
                "prediction_confidence": confidences,
                "correct_t7": correct_vals,
                "pnl_t7": pnl_vals,
            }
        )

    def test_returns_row(self):
        """Summary returns a dbc.Row with stat cards."""
        result = _build_asset_signal_summary("XLE", self._make_predictions())
        assert isinstance(result, dbc.Row)

    def test_contains_five_columns(self):
        """Summary has 5 stat card columns."""
        result = _build_asset_signal_summary("XLE", self._make_predictions())
        assert len(result.children) == 5

    def test_post_count_displayed(self):
        """First card shows total post count."""
        result = _build_asset_signal_summary("XLE", self._make_predictions(n=10))
        first_col = result.children[0]
        card_div = first_col.children
        value_text = card_div.children[0].children
        assert "10 posts" in value_text

    def test_bullish_percentage(self):
        """Second card shows bullish percentage."""
        result = _build_asset_signal_summary(
            "XLE", self._make_predictions(n=10, bullish=6)
        )
        second_col = result.children[1]
        card_div = second_col.children
        value_text = card_div.children[0].children
        assert "60%" in value_text

    def test_accuracy_calculated(self):
        """Third card shows accuracy (correct / evaluated)."""
        result = _build_asset_signal_summary(
            "XLE", self._make_predictions(n=10, evaluated=7, correct=4)
        )
        third_col = result.children[2]
        card_div = third_col.children
        value_text = card_div.children[0].children
        assert "57%" in value_text
        label_text = third_col.children.children[1].children
        assert "4/7" in label_text

    def test_pnl_positive_uses_success_color(self):
        """Positive P&L uses success color."""
        result = _build_asset_signal_summary(
            "XLE", self._make_predictions(total_pnl=150.0)
        )
        fifth_col = result.children[4]
        card_div = fifth_col.children
        color = card_div.children[0].style["color"]
        assert color == COLORS["success"]

    def test_pnl_negative_uses_danger_color(self):
        """Negative P&L uses danger color."""
        result = _build_asset_signal_summary(
            "XLE", self._make_predictions(total_pnl=-50.0)
        )
        fifth_col = result.children[4]
        card_div = fifth_col.children
        color = card_div.children[0].style["color"]
        assert color == COLORS["danger"]


class TestMiniStatCard:
    """Tests for _mini_stat_card helper."""

    def test_returns_div(self):
        """Returns an html.Div."""
        result = _mini_stat_card("42%", "accuracy", "#10b981")
        assert isinstance(result, html.Div)

    def test_value_displayed(self):
        """Value text appears in the card."""
        result = _mini_stat_card("42%", "accuracy", "#10b981")
        value_div = result.children[0]
        assert value_div.children == "42%"

    def test_label_displayed(self):
        """Label text appears in the card."""
        result = _mini_stat_card("42%", "accuracy", "#10b981")
        label_div = result.children[1]
        assert label_div.children == "accuracy"

    def test_color_applied_to_value(self):
        """Color is applied to the value div."""
        result = _mini_stat_card("42%", "accuracy", "#ff0000")
        value_div = result.children[0]
        assert value_div.style["color"] == "#ff0000"
