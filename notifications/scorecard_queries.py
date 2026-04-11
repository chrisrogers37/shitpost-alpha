"""Queries for generating the weekly scorecard."""

from datetime import date
from typing import Any, Dict, List

from notifications.db import _execute_read, _row_to_dict
from shit.logging import get_service_logger

logger = get_service_logger("scorecard_queries")


def get_weekly_prediction_stats(
    week_start: date,
    week_end: date,
) -> Dict[str, Any]:
    """Get aggregate prediction stats for a date range.

    Args:
        week_start: Start date (inclusive, Monday).
        week_end: End date (inclusive, Sunday).

    Returns:
        Dict with total_predictions, completed, bypassed, errors, avg_confidence.
    """
    return _execute_read(
        """
        SELECT
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN p.analysis_status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN p.analysis_status = 'bypassed' THEN 1 END) as bypassed,
            COUNT(CASE WHEN p.analysis_status = 'error' THEN 1 END) as errors,
            AVG(CASE WHEN p.analysis_status = 'completed' THEN p.confidence END) as avg_confidence
        FROM predictions p
        WHERE p.post_timestamp::date >= :week_start
            AND p.post_timestamp::date <= :week_end
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"total_predictions": 0},
        context="get_weekly_prediction_stats",
    )


def get_weekly_accuracy(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> Dict[str, Any]:
    """Get accuracy stats for predictions made during the week.

    Args:
        week_start: Start date.
        week_end: End date.
        timeframe: Which timeframe to evaluate (t1, t3, t7, t30).

    Returns:
        Dict with correct, incorrect, pending, bullish/bearish splits.
    """
    correct_col = f"correct_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN po.{correct_col} = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.{correct_col} = false THEN 1 END) as incorrect,
            COUNT(CASE WHEN po.{correct_col} IS NULL THEN 1 END) as pending,
            COUNT(CASE WHEN po.prediction_sentiment = 'bullish'
                AND po.{correct_col} = true THEN 1 END) as bullish_correct,
            COUNT(CASE WHEN po.prediction_sentiment = 'bullish'
                AND po.{correct_col} IS NOT NULL THEN 1 END) as bullish_total,
            COUNT(CASE WHEN po.prediction_sentiment = 'bearish'
                AND po.{correct_col} = true THEN 1 END) as bearish_correct,
            COUNT(CASE WHEN po.prediction_sentiment = 'bearish'
                AND po.{correct_col} IS NOT NULL THEN 1 END) as bearish_total
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"total_outcomes": 0},
        context="get_weekly_accuracy",
    )


def get_weekly_pnl(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> Dict[str, Any]:
    """Get simulated P&L for predictions made during the week.

    Returns:
        Dict with total_pnl, avg_pnl, best_pnl, worst_pnl, trade_count.
    """
    pnl_col = f"pnl_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            COUNT(*) as trade_count,
            COALESCE(SUM(po.{pnl_col}), 0) as total_pnl,
            COALESCE(AVG(po.{pnl_col}), 0) as avg_pnl,
            MAX(po.{pnl_col}) as best_pnl,
            MIN(po.{pnl_col}) as worst_pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        """,
        params={"week_start": week_start, "week_end": week_end},
        processor=_row_to_dict,
        default={"trade_count": 0, "total_pnl": 0},
        context="get_weekly_pnl",
    )


def get_top_wins(
    week_start: date,
    week_end: date,
    limit: int = 3,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get the best-performing predictions of the week."""
    pnl_col = f"pnl_{timeframe}"
    return_col = f"return_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            po.prediction_sentiment as sentiment,
            po.prediction_confidence as confidence,
            po.{return_col} as return_pct,
            po.{pnl_col} as pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        ORDER BY po.{pnl_col} DESC
        LIMIT :limit
        """,
        params={"week_start": week_start, "week_end": week_end, "limit": limit},
        default=[],
        context="get_top_wins",
    )


def get_worst_misses(
    week_start: date,
    week_end: date,
    limit: int = 3,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get the worst-performing predictions of the week."""
    pnl_col = f"pnl_{timeframe}"
    return_col = f"return_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            po.prediction_sentiment as sentiment,
            po.prediction_confidence as confidence,
            po.{return_col} as return_pct,
            po.{pnl_col} as pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
            AND po.{pnl_col} IS NOT NULL
        ORDER BY po.{pnl_col} ASC
        LIMIT :limit
        """,
        params={"week_start": week_start, "week_end": week_end, "limit": limit},
        default=[],
        context="get_worst_misses",
    )


def get_asset_breakdown(
    week_start: date,
    week_end: date,
    timeframe: str = "t7",
) -> List[Dict[str, Any]]:
    """Get per-asset performance summary."""
    correct_col = f"correct_{timeframe}"
    pnl_col = f"pnl_{timeframe}"

    return _execute_read(
        f"""
        SELECT
            po.symbol,
            COUNT(*) as signal_count,
            COUNT(CASE WHEN po.{correct_col} = true THEN 1 END) as correct,
            COUNT(CASE WHEN po.{correct_col} IS NOT NULL THEN 1 END) as evaluated,
            ROUND(
                COUNT(CASE WHEN po.{correct_col} = true THEN 1 END)::numeric
                / NULLIF(COUNT(CASE WHEN po.{correct_col} IS NOT NULL THEN 1 END), 0)
                * 100, 1
            ) as accuracy_pct,
            COALESCE(SUM(po.{pnl_col}), 0) as total_pnl
        FROM prediction_outcomes po
        WHERE po.prediction_date >= :week_start
            AND po.prediction_date <= :week_end
        GROUP BY po.symbol
        ORDER BY COUNT(*) DESC
        LIMIT 5
        """,
        params={"week_start": week_start, "week_end": week_end},
        default=[],
        context="get_asset_breakdown",
    )


def get_weekly_streak() -> Dict[str, Any]:
    """Calculate the current streak of winning/losing weeks.

    Returns:
        Dict with streak_type ('winning' or 'losing') and streak_length.
    """
    rows = _execute_read(
        """
        WITH weekly_performance AS (
            SELECT
                DATE_TRUNC('week', po.prediction_date)::date as week_start,
                COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) as evaluated,
                COALESCE(SUM(po.pnl_t7), 0) as total_pnl
            FROM prediction_outcomes po
            WHERE po.prediction_date >= CURRENT_DATE - INTERVAL '12 weeks'
            GROUP BY DATE_TRUNC('week', po.prediction_date)
            HAVING COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) >= 3
            ORDER BY week_start DESC
        )
        SELECT
            week_start,
            correct,
            evaluated,
            total_pnl,
            CASE
                WHEN evaluated > 0 AND (correct::float / evaluated) >= 0.5
                    AND total_pnl >= 0 THEN true
                ELSE false
            END as is_winning_week
        FROM weekly_performance
        ORDER BY week_start DESC
        """,
        default=[],
        context="get_weekly_streak",
    )

    if not rows:
        return {"streak_type": None, "streak_length": 0}

    current_is_winning = rows[0].get("is_winning_week", False)
    streak = 0

    for row in rows:
        if row.get("is_winning_week") == current_is_winning:
            streak += 1
        else:
            break

    return {
        "streak_type": "winning" if current_is_winning else "losing",
        "streak_length": streak,
    }
