"""Shared utility functions for UI components.

Provides NaN-safe data extraction and formatting helpers used across
multiple card types and callback modules.
"""

import math
from typing import Any, Optional


def safe_get(row, key: str, default: Any = None) -> Any:
    """NaN-safe field extraction from a Pandas Series or dict.

    Pandas Series.get() returns NaN (not the default) when the key
    exists but the value is NaN. This helper normalizes NaN to the
    provided default, preventing '+nan%' and '$nan' display bugs.

    Args:
        row: Dict-like object (Pandas Series or plain dict).
        key: Field name to extract.
        default: Value to return if the field is missing or NaN.

    Returns:
        The field value, or default if missing/None/NaN.
    """
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def safe_format_pct(value: Optional[float], fmt: str = "+.2f") -> str:
    """Format a float as a percentage string, returning '--' for None/NaN.

    Args:
        value: Float value to format, or None.
        fmt: Format spec string (default '+.2f' for '+1.23').

    Returns:
        Formatted string like '+1.23%' or '--'.
    """
    if value is None:
        return "--"
    try:
        if isinstance(value, float) and math.isnan(value):
            return "--"
    except (TypeError, ValueError):
        return "--"
    return f"{value:{fmt}}%"


def safe_format_dollar(value: Optional[float], fmt: str = "+,.0f") -> str:
    """Format a float as a dollar string, returning '--' for None/NaN.

    Args:
        value: Float value to format, or None.
        fmt: Format spec string (default '+,.0f' for '$+1,234').

    Returns:
        Formatted string like '$+1,234' or '--'.
    """
    if value is None:
        return "--"
    try:
        if isinstance(value, float) and math.isnan(value):
            return "--"
    except (TypeError, ValueError):
        return "--"
    return f"${value:{fmt}}"
