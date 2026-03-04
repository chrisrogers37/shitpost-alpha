"""
Dynamic insight query functions.

Generates a pool of insight candidates for dashboard cards by running
multiple targeted queries and formatting results with personality-driven copy.
"""

from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any

import data.base as _base
from data.base import ttl_cache, logger


@ttl_cache(ttl_seconds=300)
def get_dynamic_insights(days: int = None) -> List[Dict[str, Any]]:
    """Generate a pool of dynamic insight candidates for the dashboard.

    Queries for multiple insight types and returns them as structured dicts.
    The UI layer picks the top 2-3 most interesting/recent from this pool.

    Each insight dict has:
        type: str -- "latest_call", "best_worst", "system_pulse", "hot_asset", "hot_signal"
        headline: str -- Primary text (personality-driven)
        body: str -- Secondary commentary
        assets: List[str] -- Tickers mentioned (for linking)
        sentiment: str -- "positive", "negative", "neutral" (for border color)
        timestamp: datetime or None -- When this insight became relevant
        priority: int -- Lower = more important (for ranking)

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        List of insight dicts, unranked (caller sorts by priority + recency).
        Returns empty list if no data available.
    """
    insights: List[Dict[str, Any]] = []

    date_filter = ""
    params: Dict[str, Any] = {}
    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    # ---- Insight 1: Most recent prediction with an outcome ----
    try:
        latest_query = text(f"""
            SELECT
                po.symbol,
                po.prediction_sentiment,
                po.return_t7,
                po.correct_t7,
                po.pnl_t7,
                po.prediction_date,
                po.prediction_confidence,
                tss.timestamp AS post_timestamp
            FROM prediction_outcomes po
            INNER JOIN predictions p ON po.prediction_id = p.id
            INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
            WHERE po.correct_t7 IS NOT NULL
                {date_filter}
            ORDER BY po.prediction_date DESC
            LIMIT 1
        """)
        rows, columns = _base.execute_query(latest_query, params)
        if rows and rows[0]:
            r = rows[0]
            symbol = r[0]
            return_t7 = float(r[2]) if r[2] is not None else None
            correct = r[3]
            post_ts = r[7]

            if return_t7 is not None:
                ret_str = f"{return_t7:+.2f}%"
                if correct:
                    headline = f"Trump mentioned {symbol} -- it's {ret_str} in 7 days."
                    body = (
                        f"Predicted correctly with {ret_str} return."
                        if return_t7 > 2
                        else f"Called it. {ret_str} return."
                    )
                    ins_sentiment = "positive"
                else:
                    headline = (
                        f"Trump mentioned {symbol} -- it went {ret_str} in 7 days."
                    )
                    body = (
                        "Missed by a wide margin."
                        if return_t7 < -2
                        else "Close to the threshold."
                    )
                    ins_sentiment = "negative"

                insights.append(
                    {
                        "type": "latest_call",
                        "headline": headline,
                        "body": body,
                        "assets": [symbol],
                        "sentiment": ins_sentiment,
                        "timestamp": post_ts,
                        "priority": 1,
                    }
                )
    except Exception as e:
        logger.error(f"Error generating latest_call insight: {e}")

    # ---- Insight 2: Best and worst performing prediction in period ----
    try:
        date_filter_bare = ""
        if days is not None:
            date_filter_bare = "AND prediction_date >= :start_date"

        best_worst_query = text(f"""
            (
                SELECT symbol, return_t7, correct_t7, prediction_date, 'best' AS rank_type
                FROM prediction_outcomes
                WHERE correct_t7 IS NOT NULL AND return_t7 IS NOT NULL
                    {date_filter_bare}
                ORDER BY return_t7 DESC
                LIMIT 1
            )
            UNION ALL
            (
                SELECT symbol, return_t7, correct_t7, prediction_date, 'worst' AS rank_type
                FROM prediction_outcomes
                WHERE correct_t7 IS NOT NULL AND return_t7 IS NOT NULL
                    {date_filter_bare}
                ORDER BY return_t7 ASC
                LIMIT 1
            )
        """)
        rows, columns = _base.execute_query(best_worst_query, params)
        if rows and len(rows) == 2:
            best_row = rows[0] if rows[0][4] == "best" else rows[1]
            worst_row = rows[1] if rows[1][4] == "worst" else rows[0]
            best_sym = best_row[0]
            best_ret = float(best_row[1])
            worst_sym = worst_row[0]
            worst_ret = float(worst_row[1])

            headline = f"Best: {best_sym} {best_ret:+.2f}%. Worst: {worst_sym} {worst_ret:+.2f}%."
            body = "Range of outcomes across the period."

            insights.append(
                {
                    "type": "best_worst",
                    "headline": headline,
                    "body": body,
                    "assets": [best_sym, worst_sym],
                    "sentiment": "neutral",
                    "timestamp": None,
                    "priority": 2,
                }
            )
    except Exception as e:
        logger.error(f"Error generating best_worst insight: {e}")

    # ---- Insight 3: System accuracy vs coin flip ----
    try:
        date_filter_bare = ""
        if days is not None:
            date_filter_bare = "AND prediction_date >= :start_date"

        accuracy_query = text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN correct_t7 = true THEN 1 END) AS correct
            FROM prediction_outcomes
            WHERE correct_t7 IS NOT NULL
                {date_filter_bare}
        """)
        rows, columns = _base.execute_query(accuracy_query, params)
        if rows and rows[0] and rows[0][0] and rows[0][0] >= 5:
            total = rows[0][0]
            correct = rows[0][1] or 0
            accuracy = round(correct / total * 100, 1)

            if accuracy > 55:
                body = f"Outperforming random baseline by {accuracy - 50:.0f} percentage points."
                ins_sentiment = "positive"
            elif accuracy > 45:
                body = f"Near the 50% baseline. {'Slightly above' if accuracy > 50 else 'Slightly below'} random."
                ins_sentiment = "neutral"
            else:
                body = "Below 50% baseline. Model underperforming in this period."
                ins_sentiment = "negative"

            period_label = f"last {days} days" if days else "all time"
            headline = (
                f"{accuracy:.0f}% accuracy ({total} predictions, {period_label})."
            )

            insights.append(
                {
                    "type": "system_pulse",
                    "headline": headline,
                    "body": body,
                    "assets": [],
                    "sentiment": ins_sentiment,
                    "timestamp": None,
                    "priority": 3,
                }
            )
    except Exception as e:
        logger.error(f"Error generating system_pulse insight: {e}")

    # ---- Insight 4: Most active asset (most predictions recently) ----
    try:
        date_filter_bare = ""
        if days is not None:
            date_filter_bare = "AND prediction_date >= :start_date"

        active_query = text(f"""
            SELECT
                symbol,
                COUNT(*) AS pred_count,
                ROUND(AVG(return_t7)::numeric, 2) AS avg_return
            FROM prediction_outcomes
            WHERE correct_t7 IS NOT NULL
                {date_filter_bare}
            GROUP BY symbol
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """)
        rows, columns = _base.execute_query(active_query, params)
        if rows and rows[0]:
            symbol = rows[0][0]
            count = rows[0][1]
            avg_ret = float(rows[0][2]) if rows[0][2] is not None else 0.0

            ret_comment = (
                f"averaging {avg_ret:+.2f}% per call"
                if avg_ret != 0
                else "averaging flat returns"
            )
            headline = f"{symbol} is our most-called asset ({count} predictions), {ret_comment}."
            body = (
                f"Most frequently referenced asset with {count} total mentions."
                if count > 10
                else "Recurring asset in recent analysis."
            )

            insights.append(
                {
                    "type": "hot_asset",
                    "headline": headline,
                    "body": body,
                    "assets": [symbol],
                    "sentiment": "positive"
                    if avg_ret > 0
                    else "negative"
                    if avg_ret < 0
                    else "neutral",
                    "timestamp": None,
                    "priority": 4,
                }
            )
    except Exception as e:
        logger.error(f"Error generating hot_asset insight: {e}")

    # ---- Insight 5: Recent high-confidence signal ----
    try:
        hot_signal_query = text("""
            SELECT
                po.symbol,
                po.prediction_sentiment,
                po.prediction_confidence,
                po.correct_t7,
                po.return_t7,
                tss.timestamp AS post_timestamp
            FROM prediction_outcomes po
            INNER JOIN predictions p ON po.prediction_id = p.id
            INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
            WHERE po.prediction_confidence >= 0.75
            ORDER BY tss.timestamp DESC
            LIMIT 1
        """)
        rows, columns = _base.execute_query(hot_signal_query)
        if rows and rows[0]:
            symbol = rows[0][0]
            sentiment = (rows[0][1] or "neutral").lower()
            confidence = float(rows[0][2]) if rows[0][2] is not None else 0.0
            correct = rows[0][3]
            return_t7 = float(rows[0][4]) if rows[0][4] is not None else None
            post_ts = rows[0][5]

            conf_pct = f"{confidence:.0%}"
            if correct is None:
                headline = f"High-confidence call: {sentiment.upper()} on {symbol} ({conf_pct}). Awaiting results."
                body = "Outcome pending -- check back after maturation."
                ins_sentiment = "neutral"
            elif correct:
                ret_str = f"{return_t7:+.2f}%" if return_t7 is not None else "N/A"
                headline = f"High-confidence call on {symbol} ({conf_pct}) was RIGHT. {ret_str} in 7d."
                body = "High-confidence signal validated."
                ins_sentiment = "positive"
            else:
                ret_str = f"{return_t7:+.2f}%" if return_t7 is not None else "N/A"
                headline = f"High-confidence call on {symbol} ({conf_pct}) was WRONG. {ret_str} in 7d."
                body = "High confidence did not translate to accuracy here."
                ins_sentiment = "negative"

            insights.append(
                {
                    "type": "hot_signal",
                    "headline": headline,
                    "body": body,
                    "assets": [symbol],
                    "sentiment": ins_sentiment,
                    "timestamp": post_ts,
                    "priority": 5,
                }
            )
    except Exception as e:
        logger.error(f"Error generating hot_signal insight: {e}")

    return insights
