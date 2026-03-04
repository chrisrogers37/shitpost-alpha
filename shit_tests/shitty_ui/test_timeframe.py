"""Tests for the timeframe column mapping helper module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest

from data.timeframe import (
    get_tf_columns,
    TIMEFRAME_OPTIONS,
    VALID_TIMEFRAMES,
    DEFAULT_TIMEFRAME,
)


class TestTimeframeConstants:
    """Tests for module-level constants."""

    def test_valid_timeframes_tuple(self):
        """VALID_TIMEFRAMES is a tuple of all timeframe keys."""
        assert isinstance(VALID_TIMEFRAMES, tuple)
        assert set(VALID_TIMEFRAMES) == {"t1", "t3", "t7", "t30"}

    def test_default_timeframe_is_t7(self):
        """Default timeframe is t7."""
        assert DEFAULT_TIMEFRAME == "t7"

    def test_default_timeframe_in_valid(self):
        """Default timeframe is in the valid set."""
        assert DEFAULT_TIMEFRAME in VALID_TIMEFRAMES

    def test_timeframe_options_has_all_keys(self):
        """TIMEFRAME_OPTIONS has entries for all valid timeframes."""
        for tf in VALID_TIMEFRAMES:
            assert tf in TIMEFRAME_OPTIONS

    def test_each_option_has_required_keys(self):
        """Each timeframe option has all required column mapping keys."""
        required = {
            "correct_col",
            "return_col",
            "pnl_col",
            "price_col",
            "label_short",
            "label_long",
            "label_days",
        }
        for tf, mapping in TIMEFRAME_OPTIONS.items():
            assert set(mapping.keys()) == required, f"{tf} missing keys"


class TestGetTfColumns:
    """Tests for get_tf_columns()."""

    def test_default_returns_t7(self):
        """Calling with no argument returns t7 columns."""
        result = get_tf_columns()
        assert result["correct_col"] == "correct_t7"
        assert result["return_col"] == "return_t7"
        assert result["pnl_col"] == "pnl_t7"
        assert result["price_col"] == "price_t7"

    def test_t1_columns(self):
        """T+1 timeframe returns correct column names."""
        result = get_tf_columns("t1")
        assert result["correct_col"] == "correct_t1"
        assert result["return_col"] == "return_t1"
        assert result["pnl_col"] == "pnl_t1"
        assert result["price_col"] == "price_t1"
        assert result["label_short"] == "1D"
        assert result["label_long"] == "1-Day"

    def test_t3_columns(self):
        """T+3 timeframe returns correct column names."""
        result = get_tf_columns("t3")
        assert result["correct_col"] == "correct_t3"
        assert result["return_col"] == "return_t3"

    def test_t30_columns(self):
        """T+30 timeframe returns correct column names."""
        result = get_tf_columns("t30")
        assert result["correct_col"] == "correct_t30"
        assert result["return_col"] == "return_t30"
        assert result["pnl_col"] == "pnl_t30"
        assert result["label_short"] == "30D"

    def test_invalid_timeframe_raises(self):
        """Invalid timeframe key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            get_tf_columns("t99")

    def test_empty_string_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            get_tf_columns("")

    def test_returns_copy_not_reference(self):
        """get_tf_columns returns a new dict, not a reference to the global."""
        result = get_tf_columns("t7")
        result["correct_col"] = "mutated"
        assert TIMEFRAME_OPTIONS["t7"]["correct_col"] == "correct_t7"
