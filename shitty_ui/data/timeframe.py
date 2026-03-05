"""Timeframe column mapping for multi-timeframe queries.

Provides a helper that maps a timeframe key (e.g., "t7") to the
corresponding database column names in the prediction_outcomes table.

Valid timeframe keys: "t1", "t3", "t7", "t30".
"""

from typing import Dict, Literal

TimeframeKey = Literal["t1", "t3", "t7", "t30"]

TIMEFRAME_OPTIONS: Dict[str, Dict[str, str]] = {
    "t1": {
        "correct_col": "correct_t1",
        "return_col": "return_t1",
        "pnl_col": "pnl_t1",
        "price_col": "price_t1",
        "label_short": "1D",
        "label_long": "1-Day",
        "label_days": "1",
    },
    "t3": {
        "correct_col": "correct_t3",
        "return_col": "return_t3",
        "pnl_col": "pnl_t3",
        "price_col": "price_t3",
        "label_short": "3D",
        "label_long": "3-Day",
        "label_days": "3",
    },
    "t7": {
        "correct_col": "correct_t7",
        "return_col": "return_t7",
        "pnl_col": "pnl_t7",
        "price_col": "price_t7",
        "label_short": "7D",
        "label_long": "7-Day",
        "label_days": "7",
    },
    "t30": {
        "correct_col": "correct_t30",
        "return_col": "return_t30",
        "pnl_col": "pnl_t30",
        "price_col": "price_t30",
        "label_short": "30D",
        "label_long": "30-Day",
        "label_days": "30",
    },
}

VALID_TIMEFRAMES = tuple(TIMEFRAME_OPTIONS.keys())
DEFAULT_TIMEFRAME: TimeframeKey = "t7"


def get_tf_columns(timeframe: str = "t7") -> Dict[str, str]:
    """Get column names and labels for a given timeframe key.

    Args:
        timeframe: One of "t1", "t3", "t7", "t30". Defaults to "t7".

    Returns:
        Dict with keys: correct_col, return_col, pnl_col, price_col,
        label_short, label_long, label_days.

    Raises:
        ValueError: If timeframe is not a valid key.
    """
    if timeframe not in TIMEFRAME_OPTIONS:
        raise ValueError(
            f"Invalid timeframe '{timeframe}'. Valid options: {VALID_TIMEFRAMES}"
        )
    return dict(TIMEFRAME_OPTIONS[timeframe])
