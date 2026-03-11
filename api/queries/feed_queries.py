"""Feed queries for the single-post-at-a-time API.

Adapted from shitty_ui/data/signal_queries.py patterns.
Only returns posts with completed LLM analysis and non-empty assets.
"""

import json
from typing import Any, Optional

from api.dependencies import execute_query


def get_analyzed_post_at_offset(offset: int = 0) -> Optional[dict[str, Any]]:
    """Get the Nth most recent post with a completed LLM analysis.

    Args:
        offset: 0 = latest, 1 = one older, etc.

    Returns:
        Dict with post + prediction data, or None if offset is out of range.
    """
    query = """
        SELECT
            tss.shitpost_id,
            tss.text,
            tss.content AS content_html,
            tss.timestamp,
            tss.username,
            tss.url,
            tss.replies_count,
            tss.reblogs_count,
            tss.favourites_count,
            tss.upvotes_count,
            tss.downvotes_count,
            p.id AS prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            p.engagement_score,
            p.viral_score,
            p.sentiment_score,
            p.urgency_score
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::text <> '[]'
            AND p.assets::text <> 'null'
        ORDER BY tss.timestamp DESC
        OFFSET :offset
        LIMIT 1
    """

    rows, columns = execute_query(query, {"offset": offset})
    if not rows:
        return None

    row = dict(zip(columns, rows[0]))

    # Parse JSON fields
    if isinstance(row.get("assets"), str):
        row["assets"] = json.loads(row["assets"])
    if isinstance(row.get("market_impact"), str):
        row["market_impact"] = json.loads(row["market_impact"])

    return row


def get_outcomes_for_prediction(prediction_id: int) -> list[dict[str, Any]]:
    """Get all prediction_outcomes for a given prediction.

    Args:
        prediction_id: The prediction.id to look up.

    Returns:
        List of outcome dicts, one per ticker symbol.
    """
    query = """
        SELECT
            po.symbol,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.price_at_post,
            po.price_at_next_close,
            po.price_1h_after,
            po.price_t1,
            po.price_t3,
            po.price_t7,
            po.price_t30,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.return_t30,
            po.return_same_day,
            po.return_1h,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.correct_t30,
            po.correct_same_day,
            po.correct_1h,
            po.pnl_t1,
            po.pnl_t3,
            po.pnl_t7,
            po.pnl_t30,
            po.pnl_same_day,
            po.pnl_1h,
            po.is_complete
        FROM prediction_outcomes po
        WHERE po.prediction_id = :prediction_id
        ORDER BY po.symbol
    """

    rows, columns = execute_query(query, {"prediction_id": prediction_id})
    return [dict(zip(columns, row)) for row in rows]


def get_total_analyzed_posts() -> int:
    """Get total count of analyzed posts (for navigation bounds)."""
    query = """
        SELECT COUNT(*) AS total
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::text <> '[]'
            AND p.assets::text <> 'null'
    """

    rows, _ = execute_query(query)
    return rows[0][0] if rows else 0
