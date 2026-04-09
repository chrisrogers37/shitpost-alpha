"""Feed queries for the single-post-at-a-time API.

Only returns posts with completed LLM analysis and non-empty assets.
"""

import json
from typing import Any, Optional

from api.dependencies import execute_query


def get_analyzed_post_at_offset(
    offset: int = 0,
) -> Optional[tuple[dict[str, Any], int]]:
    """Get the Nth most recent analyzed post and the total count.

    Uses COUNT(*) OVER() to get both in a single query, avoiding
    a separate round trip for the total count.

    Args:
        offset: 0 = latest, 1 = one older, etc.

    Returns:
        Tuple of (post+prediction dict, total_count), or None if out of range.
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
            tss.account_verified,
            tss.account_followers_count,
            tss.card,
            tss.media_attachments,
            tss.in_reply_to_id,
            tss.in_reply_to,
            tss.reblog,
            p.id AS prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            p.engagement_score,
            p.viral_score,
            p.sentiment_score,
            p.urgency_score,
            COUNT(*) OVER() AS total_count
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
    total = row.pop("total_count", 0)

    # Parse JSON fields
    json_keys = (
        "assets", "market_impact", "card",
        "media_attachments", "in_reply_to", "reblog",
    )
    for key in json_keys:
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])

    return row, int(total)


def get_outcomes_for_prediction(prediction_id: int) -> list[dict[str, Any]]:
    """Get all prediction_outcomes with ticker fundamentals and price snapshots.

    Single query joins outcomes, ticker_registry, and price_snapshots,
    eliminating the separate snapshot query and Python-side merge.

    Args:
        prediction_id: The prediction.id to look up.

    Returns:
        List of outcome dicts (one per ticker), each including snapshot fields.
    """
    query = """
        SELECT
            po.symbol,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.prediction_date,
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
            po.is_complete,
            tr.company_name,
            tr.asset_type,
            tr.exchange,
            tr.sector,
            tr.industry,
            tr.market_cap,
            tr.pe_ratio,
            tr.forward_pe,
            tr.beta,
            tr.dividend_yield,
            ps.price     AS snapshot_price,
            ps.captured_at AS snapshot_captured_at,
            ps.market_status AS snapshot_market_status,
            ps.previous_close AS snapshot_previous_close,
            ps.day_high  AS snapshot_day_high,
            ps.day_low   AS snapshot_day_low
        FROM prediction_outcomes po
        LEFT JOIN ticker_registry tr ON po.symbol = tr.symbol
        LEFT JOIN price_snapshots ps
            ON po.prediction_id = ps.prediction_id
            AND po.symbol = ps.symbol
        WHERE po.prediction_id = :prediction_id
        ORDER BY po.symbol
    """

    rows, columns = execute_query(query, {"prediction_id": prediction_id})
    return [dict(zip(columns, row)) for row in rows]


