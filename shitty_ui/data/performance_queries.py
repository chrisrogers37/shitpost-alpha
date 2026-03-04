"""
Performance and KPI query functions.

Handles dashboard KPIs, accuracy breakdowns, cumulative P&L, rolling metrics,
win/loss streaks, confidence calibration, backtesting simulation, and
aggregate statistics.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

import data.base as _base
from data.base import ttl_cache, logger, DATABASE_URL, _timeframe_for_period


@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes
def get_available_assets() -> List[str]:
    """Get list of all unique assets mentioned in completed predictions.

    Queries the predictions table's assets JSONB column to extract
    all distinct ticker symbols. Falls back to a static list on error.
    """
    if DATABASE_URL.startswith("sqlite"):
        # SQLite doesn't support jsonb_array_elements_text
        # Fall back to loading predictions and extracting in Python
        try:
            query = text("""
                SELECT assets
                FROM predictions
                WHERE analysis_status = 'completed'
                    AND assets IS NOT NULL
            """)
            rows, columns = _base.execute_query(query)
            assets_set: set = set()
            for row in rows:
                assets_val = row[0]
                if isinstance(assets_val, list):
                    assets_set.update(assets_val)
            return sorted(assets_set)
        except Exception as e:
            logger.error(f"Error loading available assets (sqlite): {e}")
            return []
    else:
        # PostgreSQL with JSONB support
        try:
            query = text("""
                SELECT DISTINCT asset
                FROM predictions p,
                     jsonb_array_elements_text(p.assets) AS asset
                WHERE p.analysis_status = 'completed'
                    AND p.assets IS NOT NULL
                    AND p.assets::jsonb <> '[]'::jsonb
                ORDER BY asset
            """)
            rows, columns = _base.execute_query(query)
            return [row[0] for row in rows if row[0]]
        except Exception as e:
            logger.error(f"Error loading available assets: {e}")
            return []


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_prediction_stats() -> Dict[str, Any]:
    """Get summary statistics for predictions."""
    if DATABASE_URL.startswith("sqlite"):
        # Simplified stats for SQLite
        query = text("""
            SELECT
                COUNT(*) as total_posts,
                COUNT(p.id) as analyzed_posts,
                COUNT(CASE WHEN p.analysis_status = 'completed' THEN 1 END) as completed_analyses,
                COUNT(CASE WHEN p.analysis_status = 'bypassed' THEN 1 END) as bypassed_posts,
                AVG(p.confidence) as avg_confidence,
                COUNT(CASE WHEN p.confidence >= 0.7 THEN 1 END) as high_confidence_predictions
            FROM truth_social_shitposts tss
            LEFT JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        """)
    else:
        # PostgreSQL with JSON support
        query = text("""
            SELECT
                COUNT(*) as total_posts,
                COUNT(p.id) as analyzed_posts,
                COUNT(CASE WHEN p.analysis_status = 'completed' THEN 1 END) as completed_analyses,
                COUNT(CASE WHEN p.analysis_status = 'bypassed' THEN 1 END) as bypassed_posts,
                AVG(p.confidence) as avg_confidence,
                COUNT(CASE WHEN p.confidence >= 0.7 THEN 1 END) as high_confidence_predictions
            FROM truth_social_shitposts tss
            LEFT JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        """)

    rows, columns = _base.execute_query(query)
    if rows:
        row = rows[0]
        return {
            "total_posts": row[0] or 0,
            "analyzed_posts": row[1] or 0,
            "completed_analyses": row[2] or 0,
            "bypassed_posts": row[3] or 0,
            "avg_confidence": float(row[4]) if row[4] else 0.0,
            "high_confidence_predictions": row[5] or 0,
        }
    return {
        "total_posts": 0,
        "analyzed_posts": 0,
        "completed_analyses": 0,
        "bypassed_posts": 0,
        "avg_confidence": 0.0,
        "high_confidence_predictions": 0,
    }


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
    """
    Get overall prediction performance metrics from prediction_outcomes table.

    Args:
        days: Number of days to look back (None = all time)
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "WHERE prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_t7,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect_t7,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_t7,
            AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl_t7,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        {date_filter}
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        if rows and rows[0]:
            row = rows[0]
            total = row[3] or 0  # evaluated_t7
            correct = row[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0

            return {
                "total_outcomes": row[0] or 0,
                "evaluated_predictions": total,
                "correct_predictions": correct,
                "incorrect_predictions": row[2] or 0,
                "accuracy_t7": round(accuracy, 1),
                "avg_return_t7": round(float(row[4]), 2) if row[4] else 0.0,
                "total_pnl_t7": round(float(row[5]), 2) if row[5] else 0.0,
                "avg_confidence": round(float(row[6]), 2) if row[6] else 0.0,
            }
    except Exception as e:
        logger.error(f"Error loading performance metrics: {e}")

    return {
        "total_outcomes": 0,
        "evaluated_predictions": 0,
        "correct_predictions": 0,
        "incorrect_predictions": 0,
        "accuracy_t7": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl_t7": 0.0,
        "avg_confidence": 0.0,
    }


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_dashboard_kpis(days: int = None) -> Dict[str, Any]:
    """Get the four key metrics for the main dashboard KPI cards.

    Returns only evaluated predictions (where the appropriate timeframe
    outcome is not NULL). Uses adaptive timeframe: T+1 for 7D, T+3 for
    30D, T+7 for 90D and all-time.

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        Dict with keys:
            total_signals: int - count of evaluated prediction-outcome rows
            accuracy_pct: float - percentage correct at chosen timeframe
            avg_return_t7: float - mean return at chosen timeframe (percentage)
            total_pnl: float - sum of P&L at chosen timeframe (dollar amount)
            timeframe: str - which timeframe was used ("t1", "t3", or "t7")
    """
    tf = _timeframe_for_period(days)

    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query_template = """
        SELECT
            COUNT(*) as total_signals,
            COUNT(CASE WHEN correct_{tf} = true THEN 1 END) as correct_count,
            AVG(return_{tf}) as avg_return,
            SUM(CASE WHEN pnl_{tf} IS NOT NULL THEN pnl_{tf} ELSE 0 END) as total_pnl
        FROM prediction_outcomes
        WHERE correct_{tf} IS NOT NULL
        {date_filter}
    """
    query = text(query_template.format(tf=tf, date_filter=date_filter))

    try:
        rows, columns = _base.execute_query(query, params)
        if rows and rows[0]:
            row = rows[0]
            total = row[0] or 0
            correct = row[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0.0

            return {
                "total_signals": total,
                "accuracy_pct": round(accuracy, 1),
                "avg_return_t7": round(float(row[2]), 2) if row[2] else 0.0,
                "total_pnl": round(float(row[3]), 2) if row[3] else 0.0,
                "timeframe": tf,
            }
    except Exception as e:
        logger.error(f"Error loading dashboard KPIs: {e}")

    return {
        "total_signals": 0,
        "accuracy_pct": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl": 0.0,
        "timeframe": tf,
    }


def get_dashboard_kpis_with_fallback(days: int | None = 90) -> dict:
    """Get dashboard KPIs with automatic fallback to all-time data.

    When the selected time period has no evaluated predictions (total_signals == 0),
    falls back to all-time data and marks the result so the UI can display a note.

    Args:
        days: Number of days to filter. None = all time.

    Returns:
        Dict with KPI values plus:
            is_fallback: bool - True if showing all-time data instead of requested period
            fallback_label: str - Display label (empty if not fallback)
            timeframe_label: str - Human-readable label for the active timeframe
    """
    kpis = get_dashboard_kpis(days=days)
    tf = kpis.get("timeframe", "t7")

    tf_labels = {"t1": "1-day", "t3": "3-day", "t7": "7-day"}
    kpis["timeframe_label"] = tf_labels.get(tf, "7-day")

    # If period has evaluated signals, return as-is
    if kpis["total_signals"] > 0 or days is None:
        kpis["is_fallback"] = False
        kpis["fallback_label"] = ""
        return kpis

    # Fall back to all-time
    kpis = get_dashboard_kpis(days=None)
    tf = kpis.get("timeframe", "t7")
    kpis["timeframe_label"] = tf_labels.get(tf, "7-day")
    kpis["is_fallback"] = True
    kpis["fallback_label"] = "Showing all-time data"
    return kpis


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_accuracy_by_confidence(days: int = None) -> pd.DataFrame:
    """
    Get prediction accuracy broken down by confidence level.

    Args:
        days: Number of days to look back (None = all time)
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            CASE
                WHEN prediction_confidence < 0.6 THEN 'Low (<60%)'
                WHEN prediction_confidence < 0.75 THEN 'Medium (60-75%)'
                ELSE 'High (>75%)'
            END as confidence_level,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(CASE WHEN return_t7 IS NOT NULL THEN return_t7 END)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        {date_filter}
        GROUP BY
            CASE
                WHEN prediction_confidence < 0.6 THEN 'Low (<60%)'
                WHEN prediction_confidence < 0.75 THEN 'Medium (60-75%)'
                ELSE 'High (>75%)'
            END
        ORDER BY
            CASE confidence_level
                WHEN 'Low (<60%)' THEN 1
                WHEN 'Medium (60-75%)' THEN 2
                WHEN 'High (>75%)' THEN 3
            END
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total"] * 100).round(1)
        return df
    except Exception as e:
        logger.error(f"Error loading accuracy by confidence: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_accuracy_by_asset(limit: int = 15, days: int = None) -> pd.DataFrame:
    """
    Get prediction accuracy broken down by asset.

    Args:
        limit: Maximum number of assets to return
        days: Number of days to look back (None = all time)
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {"limit": limit}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            symbol,
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(CASE WHEN return_t7 IS NOT NULL THEN return_t7 END)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        {date_filter}
        GROUP BY symbol
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
        return df
    except Exception as e:
        logger.error(f"Error loading accuracy by asset: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_sentiment_distribution(days: int = None) -> Dict[str, int]:
    """
    Get distribution of bullish/bearish/neutral predictions.

    Args:
        days: Number of days to look back (None = all time)
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_sentiment,
            COUNT(*) as count
        FROM prediction_outcomes
        WHERE prediction_sentiment IS NOT NULL
        {date_filter}
        GROUP BY prediction_sentiment
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        result = {"bullish": 0, "bearish": 0, "neutral": 0}
        for row in rows:
            sentiment = row[0].lower() if row[0] else "neutral"
            if sentiment in result:
                result[sentiment] = row[1]
        return result
    except Exception as e:
        logger.error(f"Error loading sentiment distribution: {e}")
        return {"bullish": 0, "bearish": 0, "neutral": 0}


@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes (changes less often)
def get_active_assets_from_db() -> List[str]:
    """
    Get list of assets that actually have predictions with outcomes.
    """
    query = text("""
        SELECT DISTINCT symbol
        FROM prediction_outcomes
        WHERE symbol IS NOT NULL
        ORDER BY symbol
    """)

    try:
        rows, columns = _base.execute_query(query)
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error loading active assets: {e}")
        return []


@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes (same as get_active_assets_from_db)
def get_top_predicted_asset() -> Optional[str]:
    """
    Get the asset with the most prediction outcomes.

    Used to auto-select a default asset on the /trends page.

    Returns:
        Ticker symbol string (e.g., 'TSLA'), or None if no assets exist.
    """
    query = text("""
        SELECT symbol, COUNT(*) as prediction_count
        FROM prediction_outcomes
        WHERE symbol IS NOT NULL
        GROUP BY symbol
        ORDER BY prediction_count DESC
        LIMIT 1
    """)

    try:
        rows, columns = _base.execute_query(query)
        if rows and rows[0]:
            return rows[0][0]
        return None
    except Exception as e:
        logger.error(f"Error loading top predicted asset: {e}")
        return None


def get_cumulative_pnl(days: int = None) -> pd.DataFrame:
    """
    Get cumulative P&L over time for equity curve visualization.

    Args:
        days: Number of days to look back (None = all time)

    Returns:
        DataFrame with columns: prediction_date, daily_pnl, predictions_count, cumulative_pnl
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_date,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as daily_pnl,
            COUNT(*) as predictions_count
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        {date_filter}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["cumulative_pnl"] = df["daily_pnl"].cumsum()
        return df
    except Exception as e:
        logger.error(f"Error loading cumulative P&L: {e}")
        return pd.DataFrame()


def get_rolling_accuracy(window: int = 30, days: int = None) -> pd.DataFrame:
    """
    Get rolling accuracy over time.

    Args:
        window: Rolling window size in days
        days: Total days to look back (None = all time)

    Returns:
        DataFrame with: prediction_date, correct, total, rolling_accuracy
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_date,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as total
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        {date_filter}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty and len(df) > 0:
            df["rolling_correct"] = (
                df["correct"].rolling(window=window, min_periods=1).sum()
            )
            df["rolling_total"] = (
                df["total"].rolling(window=window, min_periods=1).sum()
            )
            df["rolling_accuracy"] = (
                df["rolling_correct"] / df["rolling_total"] * 100
            ).round(1)
        return df
    except Exception as e:
        logger.error(f"Error loading rolling accuracy: {e}")
        return pd.DataFrame()


def get_win_loss_streaks() -> Dict[str, int]:
    """
    Calculate current and max win/loss streaks.

    Returns:
        Dict with:
            current_streak: positive for wins, negative for losses
            max_win_streak: longest consecutive correct predictions
            max_loss_streak: longest consecutive incorrect predictions
    """
    query = text("""
        SELECT
            prediction_date,
            correct_t7
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        ORDER BY prediction_date ASC, created_at ASC
    """)

    try:
        rows, columns = _base.execute_query(query)
        if not rows:
            return {"current_streak": 0, "max_win_streak": 0, "max_loss_streak": 0}

        outcomes = [row[1] for row in rows]  # List of True/False

        # Calculate streaks
        max_win = 0
        max_loss = 0
        current = 0

        for correct in outcomes:
            if correct:
                if current > 0:
                    current += 1
                else:
                    current = 1
                max_win = max(max_win, current)
            else:
                if current < 0:
                    current -= 1
                else:
                    current = -1
                max_loss = max(max_loss, abs(current))

        return {
            "current_streak": current,
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
        }
    except Exception as e:
        logger.error(f"Error loading win/loss streaks: {e}")
        return {"current_streak": 0, "max_win_streak": 0, "max_loss_streak": 0}


def get_confidence_calibration(buckets: int = 10) -> pd.DataFrame:
    """
    Get confidence calibration data (predicted confidence vs actual accuracy).

    Buckets predictions by confidence level and calculates actual
    accuracy for each bucket. A well-calibrated model should show
    predictions with 70% confidence being correct ~70% of the time.

    Args:
        buckets: Number of confidence buckets (default 10 = 0-10%, 10-20%, etc.)

    Returns:
        DataFrame with: bucket_start, total, correct, avg_confidence,
                        actual_accuracy, predicted_confidence, bucket_label
    """
    bucket_size = 1.0 / buckets

    query = text("""
        SELECT
            FLOOR(prediction_confidence / :bucket_size) * :bucket_size as bucket_start,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
            AND prediction_confidence IS NOT NULL
        GROUP BY FLOOR(prediction_confidence / :bucket_size)
        ORDER BY bucket_start ASC
    """)

    try:
        rows, columns = _base.execute_query(query, {"bucket_size": bucket_size})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["actual_accuracy"] = (df["correct"] / df["total"] * 100).round(1)
            df["predicted_confidence"] = (df["avg_confidence"] * 100).round(1)
            df["bucket_label"] = df["bucket_start"].apply(
                lambda x: f"{int(x * 100)}-{int((x + bucket_size) * 100)}%"
            )
        return df
    except Exception as e:
        logger.error(f"Error loading confidence calibration: {e}")
        return pd.DataFrame()


def get_monthly_performance(months: int = 12) -> pd.DataFrame:
    """
    Get monthly performance summary.

    Args:
        months: Number of months to look back

    Returns:
        DataFrame with: month, total_predictions, correct, incorrect,
                        avg_return, total_pnl, accuracy
    """
    query = text("""
        SELECT
            DATE_TRUNC('month', prediction_date) as month,
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(return_t7)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        GROUP BY DATE_TRUNC('month', prediction_date)
        ORDER BY month DESC
        LIMIT :months
    """)

    try:
        rows, columns = _base.execute_query(query, {"months": months})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
            df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m")
        return df
    except Exception as e:
        logger.error(f"Error loading monthly performance: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)
def get_high_confidence_metrics(days: int = None) -> Dict[str, Any]:
    """
    Get win rate and count for high-confidence predictions (>=0.75).

    Args:
        days: Number of days to look back (None = all time)

    Returns:
        Dict with win_rate, total, correct, incorrect
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect
        FROM prediction_outcomes
        WHERE prediction_confidence >= 0.75
            AND correct_t7 IS NOT NULL
            {date_filter}
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        if rows and rows[0]:
            total = rows[0][0] or 0
            correct = rows[0][1] or 0
            win_rate = (correct / total * 100) if total > 0 else 0
            return {
                "win_rate": round(win_rate, 1),
                "total": total,
                "correct": correct,
                "incorrect": rows[0][2] or 0,
            }
    except Exception as e:
        logger.error(f"Error loading high confidence metrics: {e}")

    return {"win_rate": 0.0, "total": 0, "correct": 0, "incorrect": 0}


@ttl_cache(ttl_seconds=300)
def get_empty_state_context() -> Dict[str, Any]:
    """Get contextual counts for smart empty state messages.

    Returns lightweight aggregate counts used by empty-state components
    to guide users toward timeframes and pages that have data.

    Returns:
        Dict with keys:
            total_evaluated: int -- all-time evaluated prediction outcomes
            total_pending: int -- outcomes awaiting maturation
            total_high_confidence: int -- all-time high-confidence signals (>=0.75)
    """
    query = text("""
        SELECT
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) AS total_evaluated,
            COUNT(CASE WHEN correct_t7 IS NULL THEN 1 END) AS total_pending,
            COUNT(CASE WHEN prediction_confidence >= 0.75 AND correct_t7 IS NOT NULL THEN 1 END) AS total_high_confidence
        FROM prediction_outcomes
    """)

    try:
        rows, columns = _base.execute_query(query)
        if rows and rows[0]:
            return {
                "total_evaluated": rows[0][0] or 0,
                "total_pending": rows[0][1] or 0,
                "total_high_confidence": rows[0][2] or 0,
            }
    except Exception as e:
        logger.error(f"Error loading empty state context: {e}")

    return {
        "total_evaluated": 0,
        "total_pending": 0,
        "total_high_confidence": 0,
    }


@ttl_cache(ttl_seconds=300)
def get_best_performing_asset(days: int = None) -> Dict[str, Any]:
    """
    Get the best performing asset by total P&L.

    Args:
        days: Number of days to look back (None = all time)

    Returns:
        Dict with symbol, total_pnl, accuracy, prediction_count
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            symbol,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl,
            COUNT(*) as prediction_count,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
            {date_filter}
        GROUP BY symbol
        HAVING COUNT(*) >= 2
        ORDER BY SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) DESC
        LIMIT 1
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        if rows and rows[0]:
            total = rows[0][2] or 0
            correct = rows[0][3] or 0
            return {
                "symbol": rows[0][0],
                "total_pnl": float(rows[0][1]) if rows[0][1] else 0.0,
                "prediction_count": total,
                "accuracy": round((correct / total * 100) if total > 0 else 0, 1),
            }
    except Exception as e:
        logger.error(f"Error loading best performing asset: {e}")

    return {"symbol": "N/A", "total_pnl": 0.0, "prediction_count": 0, "accuracy": 0.0}


def get_accuracy_over_time(days: int = None) -> pd.DataFrame:
    """
    Get prediction accuracy aggregated by week for line chart.

    Args:
        days: Number of days to look back (None = all time)

    Returns:
        DataFrame with columns: week, total, correct, accuracy
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            DATE_TRUNC('week', prediction_date) as week,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
            {date_filter}
        GROUP BY DATE_TRUNC('week', prediction_date)
        HAVING COUNT(*) >= 1
        ORDER BY week ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total"] * 100).round(1)
            df["week"] = pd.to_datetime(df["week"])
        return df
    except Exception as e:
        logger.error(f"Error loading accuracy over time: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)
def get_backtest_simulation(
    initial_capital: float = 10000,
    min_confidence: float = 0.75,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Simulate P&L if following high-confidence signals with a given capital.

    Assumes equal position sizing per trade based on initial capital.

    Args:
        initial_capital: Starting capital
        min_confidence: Minimum confidence threshold for trades
        days: Number of days to look back

    Returns:
        Dict with final_value, total_return_pct, trade_count, wins, losses, win_rate
    """
    date_filter = ""
    params: Dict[str, Any] = {"min_confidence": min_confidence}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            return_t7,
            correct_t7,
            pnl_t7
        FROM prediction_outcomes
        WHERE prediction_confidence >= :min_confidence
            AND correct_t7 IS NOT NULL
            AND return_t7 IS NOT NULL
            {date_filter}
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        if not rows:
            return {
                "initial_capital": initial_capital,
                "final_value": initial_capital,
                "total_return_pct": 0.0,
                "trade_count": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
            }

        # Simulate: each trade uses a fixed fraction of capital
        # Use $1000 per trade (matching existing pnl_t7 calculation)
        total_pnl = sum(float(r[2]) for r in rows if r[2] is not None)
        wins = sum(1 for r in rows if r[1] is True)
        losses = sum(1 for r in rows if r[1] is False)
        trade_count = wins + losses
        win_rate = (wins / trade_count * 100) if trade_count > 0 else 0

        final_value = initial_capital + total_pnl
        total_return_pct = (
            (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
        )

        return {
            "initial_capital": initial_capital,
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return_pct, 2),
            "trade_count": trade_count,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
        }
    except Exception as e:
        logger.error(f"Error running backtest simulation: {e}")
        return {
            "initial_capital": initial_capital,
            "final_value": initial_capital,
            "total_return_pct": 0.0,
            "trade_count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
        }


def get_sentiment_accuracy(days: int = None) -> pd.DataFrame:
    """
    Get accuracy breakdown by sentiment type with counts.

    Args:
        days: Number of days to look back (None = all time)

    Returns:
        DataFrame with columns: sentiment, total, correct, accuracy
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_sentiment as sentiment,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct
        FROM prediction_outcomes
        WHERE prediction_sentiment IS NOT NULL
            AND correct_t7 IS NOT NULL
            {date_filter}
        GROUP BY prediction_sentiment
        ORDER BY COUNT(*) DESC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total"] * 100).round(1)
        return df
    except Exception as e:
        logger.error(f"Error loading sentiment accuracy: {e}")
        return pd.DataFrame()
