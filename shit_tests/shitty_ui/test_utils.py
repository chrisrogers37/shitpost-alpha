"""Tests for shitty_ui/components/utils.py -- NaN-safe utilities."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

from components.utils import safe_get, safe_format_pct, safe_format_dollar


class TestSafeGet:
    """Tests for the safe_get NaN-guard helper."""

    def test_returns_value_for_normal_float(self):
        assert safe_get({"key": 1.5}, "key") == 1.5

    def test_returns_default_for_nan(self):
        assert safe_get({"key": float("nan")}, "key", 0.0) == 0.0

    def test_returns_default_for_missing_key(self):
        assert safe_get({}, "key", "fallback") == "fallback"

    def test_returns_none_for_missing_key_no_default(self):
        assert safe_get({}, "key") is None

    def test_returns_default_for_none_value(self):
        assert safe_get({"key": None}, "key", 42) == 42

    def test_returns_string_value_unchanged(self):
        assert safe_get({"key": "hello"}, "key") == "hello"

    def test_returns_list_value_unchanged(self):
        assert safe_get({"key": [1, 2]}, "key") == [1, 2]

    def test_returns_zero_float_not_treated_as_nan(self):
        assert safe_get({"key": 0.0}, "key", 999) == 0.0

    def test_returns_negative_float_unchanged(self):
        assert safe_get({"key": -3.14}, "key") == -3.14

    def test_works_with_pandas_series(self):
        import pandas as pd

        row = pd.Series({"val": float("nan"), "ok": 42})
        assert safe_get(row, "val", 0) == 0
        assert safe_get(row, "ok", 0) == 42

    def test_returns_bool_unchanged(self):
        assert safe_get({"key": True}, "key") is True
        assert safe_get({"key": False}, "key") is False


class TestSafeFormatPct:
    """Tests for safe_format_pct."""

    def test_formats_positive_float(self):
        assert safe_format_pct(2.5) == "+2.50%"

    def test_formats_negative_float(self):
        assert safe_format_pct(-1.23) == "-1.23%"

    def test_returns_dash_for_none(self):
        assert safe_format_pct(None) == "--"

    def test_returns_dash_for_nan(self):
        assert safe_format_pct(float("nan")) == "--"

    def test_formats_zero(self):
        assert safe_format_pct(0.0) == "+0.00%"

    def test_custom_format(self):
        assert safe_format_pct(5.0, fmt=".1f") == "5.0%"


class TestSafeFormatDollar:
    """Tests for safe_format_dollar."""

    def test_formats_positive_amount(self):
        assert safe_format_dollar(1234.0) == "$+1,234"

    def test_formats_negative_amount(self):
        assert safe_format_dollar(-500.0) == "$-500"

    def test_returns_dash_for_none(self):
        assert safe_format_dollar(None) == "--"

    def test_returns_dash_for_nan(self):
        assert safe_format_dollar(float("nan")) == "--"

    def test_formats_zero(self):
        assert safe_format_dollar(0.0) == "$+0"

    def test_custom_format_no_sign(self):
        assert safe_format_dollar(1234.0, fmt=",.0f") == "$1,234"
