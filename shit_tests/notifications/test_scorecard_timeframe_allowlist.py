"""The scorecard timeframe allowlist keeps interpolated column names injection-safe.

`timeframe` is interpolated directly into SQL column names (correct_t7, pnl_t30),
so every query function validates it against VALID_TIMEFRAMES first. These tests
pin both the helper and its wiring into each interpolating function.
"""

from datetime import date

import pytest

from notifications import scorecard_queries as sq
from notifications.scorecard_queries import VALID_TIMEFRAMES, _validate_timeframe


BAD_TIMEFRAMES = [
    "t7; DROP TABLE prediction_outcomes",
    "t99",
    "",
    "pnl_t7",
    "t7 OR 1=1",
]


def test_valid_timeframes_pass():
    for tf in VALID_TIMEFRAMES:
        _validate_timeframe(tf)  # must not raise


@pytest.mark.parametrize("bad", BAD_TIMEFRAMES)
def test_helper_rejects_injection_shaped_timeframes(bad):
    with pytest.raises(ValueError):
        _validate_timeframe(bad)


@pytest.mark.parametrize(
    "fn",
    [
        sq.get_weekly_accuracy,
        sq.get_weekly_pnl,
        sq.get_top_wins,
        sq.get_worst_misses,
        sq.get_asset_breakdown,
    ],
)
def test_query_functions_reject_bad_timeframe_before_db(fn):
    """Each interpolating function validates before touching the DB (raises early)."""
    with pytest.raises(ValueError):
        fn(date(2026, 1, 1), date(2026, 1, 7), timeframe="t7; DROP TABLE x")
