"""
Signal and post query functions.

Handles loading, filtering, and paginating Truth Social posts and their
associated predictions. Includes the signal feed, unified feed, CSV export,
and price+signal combination queries.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

import data.base as _base
from data.base import logger


def load_recent_posts(limit: int = 100) -> pd.DataFrame:
    """
    Load recent posts with their predictions.

    Args:
        limit: Maximum number of posts to return

    Returns:
        DataFrame with posts and prediction data
    """
    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            tss.replies_count,
            tss.reblogs_count,
            tss.favourites_count,
            p.assets,
            p.market_impact,
            p.thesis,
            p.confidence,
            p.analysis_status,
            p.analysis_comment
        FROM truth_social_shitposts tss
        LEFT JOIN predictions p 
            ON tss.shitpost_id = p.shitpost_id
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    rows, columns = _base.execute_query(query, {"limit": limit})
    df = pd.DataFrame(rows, columns=columns)
    return df


def load_filtered_posts(
    limit: int = 100,
    has_prediction: Optional[bool] = None,
    assets_filter: Optional[List[str]] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load posts with advanced filtering options.

    Args:
        limit: Maximum number of posts to return
        has_prediction: Filter for posts with/without predictions
        assets_filter: List of asset tickers to filter by
        confidence_min: Minimum confidence score
        confidence_max: Maximum confidence score
        date_from: Start date (YYYY-MM-DD format)
        date_to: End date (YYYY-MM-DD format)

    Returns:
        Filtered DataFrame with posts and prediction data
    """
    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            tss.replies_count,
            tss.reblogs_count,
            tss.favourites_count,
            p.assets,
            p.market_impact,
            p.thesis,
            p.confidence,
            p.analysis_status,
            p.analysis_comment
        FROM truth_social_shitposts tss
        LEFT JOIN predictions p 
            ON tss.shitpost_id = p.shitpost_id
        WHERE 1=1
    """)

    params = {"limit": limit}

    # Add filters dynamically
    if has_prediction is not None:
        if has_prediction:
            query = text(
                str(query)
                + " AND p.assets IS NOT NULL AND p.assets::jsonb <> '[]'::jsonb"
            )
        else:
            query = text(
                str(query) + " AND (p.assets IS NULL OR p.assets::jsonb = '[]'::jsonb)"
            )

    if confidence_min is not None:
        query = text(str(query) + " AND p.confidence >= :confidence_min")
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        query = text(str(query) + " AND p.confidence <= :confidence_max")
        params["confidence_max"] = confidence_max

    if date_from:
        query = text(str(query) + " AND tss.timestamp >= :date_from")
        # Convert string date to datetime object
        from datetime import datetime

        if isinstance(date_from, str):
            params["date_from"] = datetime.strptime(date_from, "%Y-%m-%d")
        else:
            params["date_from"] = date_from

    if date_to:
        query = text(str(query) + " AND tss.timestamp < :date_to_plus_one")
        # Convert string date to datetime object and add one day to include the entire day
        from datetime import datetime, timedelta

        if isinstance(date_to, str):
            params["date_to_plus_one"] = datetime.strptime(
                date_to, "%Y-%m-%d"
            ) + timedelta(days=1)
        else:
            params["date_to_plus_one"] = date_to + timedelta(days=1)

    query = text(str(query) + " ORDER BY tss.timestamp DESC LIMIT :limit")

    rows, columns = _base.execute_query(query, params)
    df = pd.DataFrame(rows, columns=columns)

    # Post-process asset filtering (since it's JSON, easier to do in Python)
    if assets_filter and not df.empty:

        def has_asset(assets_json, target_assets):
            if pd.isna(assets_json) or not assets_json:
                return False
            try:
                assets = assets_json if isinstance(assets_json, list) else []
                return any(asset in assets for asset in target_assets)
            except (TypeError, ValueError):
                return False

        df = df[df["assets"].apply(lambda x: has_asset(x, assets_filter))]

    return df


def get_recent_signals(
    limit: int = 10, min_confidence: float = 0.5, days: int = None
) -> pd.DataFrame:
    """
    Get recent predictions with actionable signals (has assets and sentiment).
    Returns predictions with their outcomes if available.

    Args:
        limit: Maximum number of signals to return
        min_confidence: Minimum confidence threshold
        days: Number of days to look back (None = all time)
    """
    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {"limit": limit, "min_confidence": min_confidence}

    if days is not None:
        date_filter = "AND tss.timestamp >= :start_date"
        params["start_date"] = datetime.now() - timedelta(days=days)

    query = text(f"""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            po.symbol,
            po.prediction_sentiment,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            {date_filter}
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading recent signals: {e}")
        return pd.DataFrame()


def get_active_signals(min_confidence: float = 0.75, hours: int = 48) -> pd.DataFrame:
    """
    Get recent high-confidence signals for the hero section, deduplicated by post.

    Each post produces one card, regardless of how many tickers it mentions.
    Outcome data is aggregated across all ticker outcomes for the prediction.

    Args:
        min_confidence: Minimum confidence threshold
        hours: How many hours back to look

    Returns:
        DataFrame with one row per unique post, with aggregated outcome data
    """
    params: Dict[str, Any] = {
        "min_confidence": min_confidence,
        "since": datetime.now() - timedelta(hours=hours),
    }

    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            COUNT(po.id) AS outcome_count,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) AS correct_count,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) AS incorrect_count,
            AVG(po.return_t7) AS avg_return_t7,
            SUM(po.pnl_t7) AS total_pnl_t7,
            BOOL_AND(po.is_complete) AS is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp >= :since
        GROUP BY tss.timestamp, tss.text, tss.shitpost_id,
                 p.id, p.assets, p.market_impact, p.confidence, p.thesis
        ORDER BY tss.timestamp DESC
        LIMIT 5
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading active signals: {e}")
        return pd.DataFrame()


def get_active_signals_with_fallback() -> tuple:
    """Get hero signals with progressive fallback for wider time windows.

    Tries these strategies in order:
    1. High confidence (>=0.75) in last 72 hours
    2. High confidence (>=0.75) in last 7 days
    3. High confidence (>=0.75) in last 30 days
    4. Medium confidence (>=0.60) in last 30 days

    Returns:
        Tuple of (DataFrame, label_str) where label_str describes the data shown.
    """
    # Strategy 1: Last 72 hours, high confidence
    df = get_active_signals(min_confidence=0.75, hours=72)
    if not df.empty:
        return df, "High confidence predictions in last 72h"

    # Strategy 2: Last 7 days, high confidence
    df = get_active_signals(min_confidence=0.75, hours=168)
    if not df.empty:
        return df, "Top signals this week"

    # Strategy 3: Last 30 days, high confidence
    df = get_active_signals(min_confidence=0.75, hours=720)
    if not df.empty:
        return df, "Top signals this month"

    # Strategy 4: Last 30 days, medium confidence
    df = get_active_signals(min_confidence=0.60, hours=720)
    if not df.empty:
        return df, "Recent signals (30d, confidence >= 60%)"

    # Nothing at all
    return pd.DataFrame(), ""


def get_unified_feed(
    limit: int = 15,
    days: int | None = 90,
    min_confidence: float = 0.5,
) -> pd.DataFrame:
    """Get a unified prediction feed for the dashboard.

    Combines the deduplication logic of get_active_signals() (one row per post,
    aggregated outcomes) with the time-period filtering of get_recent_signals().

    Sort order: evaluated predictions first (correct/incorrect), then pending,
    within each group ordered by timestamp descending.

    Args:
        limit: Maximum number of predictions to return.
        days: Number of days to look back (None = all time).
        min_confidence: Minimum confidence threshold.

    Returns:
        DataFrame with one row per unique post, with aggregated outcome data.
    """
    date_filter = ""
    params: Dict[str, Any] = {
        "limit": limit,
        "min_confidence": min_confidence,
    }

    if days is not None:
        date_filter = "AND tss.timestamp >= :start_date"
        params["start_date"] = datetime.now() - timedelta(days=days)

    query = text(f"""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            COUNT(po.id) AS outcome_count,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) AS correct_count,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) AS incorrect_count,
            AVG(po.return_t7) AS avg_return_t7,
            SUM(po.pnl_t7) AS total_pnl_t7,
            BOOL_AND(po.is_complete) AS is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            {date_filter}
        GROUP BY tss.timestamp, tss.text, tss.shitpost_id,
                 p.id, p.assets, p.market_impact, p.confidence,
                 p.thesis, p.analysis_status
        ORDER BY
            CASE
                WHEN COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) > 0
                THEN 0
                ELSE 1
            END,
            tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading unified feed: {e}")
        return pd.DataFrame()


def get_weekly_signal_count() -> int:
    """Get count of completed predictions this week."""
    params: Dict[str, Any] = {
        "week_start": (datetime.now() - timedelta(days=7)),
    }

    query = text("""
        SELECT COUNT(*)
        FROM predictions p
        INNER JOIN truth_social_shitposts tss ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp >= :week_start
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        return rows[0][0] if rows else 0
    except Exception as e:
        logger.error(f"Error loading weekly signal count: {e}")
        return 0


def _build_signal_feed_filters(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    Build shared WHERE clause fragments for signal feed queries.

    Constructs the dynamic filter portion of the WHERE clause used by both
    get_signal_feed() and get_signal_feed_count(). The returned SQL string
    is meant to be appended to a base query that already includes the standard
    completed-prediction filters (analysis_status, confidence IS NOT NULL, etc.).

    Args:
        sentiment_filter: 'bullish', 'bearish', or None.
        confidence_min: Minimum confidence (0.0-1.0).
        confidence_max: Maximum confidence (0.0-1.0).
        asset_filter: Specific ticker symbol (e.g. 'AAPL').
        outcome_filter: 'correct', 'incorrect', 'evaluated', 'pending', or None.

    Returns:
        Tuple of (where_clause_str, params_dict) where where_clause_str contains
        zero or more ' AND ...' fragments and params_dict contains the corresponding
        bind parameters.
    """
    clauses = ""
    params: Dict[str, Any] = {}

    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        clauses += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    if confidence_min is not None:
        clauses += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        clauses += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    if asset_filter:
        clauses += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    if outcome_filter == "correct":
        clauses += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        clauses += " AND po.correct_t7 = false"
    elif outcome_filter == "evaluated":
        clauses += " AND po.correct_t7 IS NOT NULL"
    elif outcome_filter == "pending":
        clauses += " AND po.correct_t7 IS NULL"

    return clauses, params


def get_signal_feed(
    limit: int = 20,
    offset: int = 0,
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load signal feed data with filtering and pagination.

    Returns predictions joined with source posts and validation outcomes,
    ordered by timestamp descending (newest first).

    Args:
        limit: Maximum signals per page.
        offset: Number of signals to skip (for load-more pagination).
        sentiment_filter: 'bullish', 'bearish', or None.
        confidence_min: Minimum confidence (0.0-1.0).
        confidence_max: Maximum confidence (0.0-1.0).
        asset_filter: Specific ticker symbol (e.g. 'AAPL').
        outcome_filter: 'correct', 'incorrect', 'pending', or None.

    Returns:
        DataFrame with signal feed columns. Empty DataFrame on error.
    """
    base_query = """
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            po.symbol,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
    """

    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    # Apply shared signal feed filters
    filter_clauses, filter_params = _build_signal_feed_filters(
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )
    base_query += filter_clauses
    params.update(filter_params)

    base_query += """
        ORDER BY
            CASE WHEN po.correct_t7 IS NOT NULL THEN 0 ELSE 1 END,
            tss.timestamp DESC
        LIMIT :limit OFFSET :offset
    """

    try:
        rows, columns = _base.execute_query(text(base_query), params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading signal feed: {e}")
        return pd.DataFrame()


def get_signal_feed_count(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> int:
    """
    Count total signals matching current filters.

    Uses the same filter logic as get_signal_feed but returns only the count.

    Returns:
        Integer count of matching signals. Returns 0 on error.
    """
    base_query = """
        SELECT COUNT(*) as total
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
    """

    # Apply shared signal feed filters
    filter_clauses, filter_params = _build_signal_feed_filters(
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )
    base_query += filter_clauses
    params = filter_params

    try:
        rows, columns = _base.execute_query(text(base_query), params)
        if rows and rows[0]:
            return rows[0][0] or 0
        return 0
    except Exception as e:
        logger.error(f"Error counting signal feed: {e}")
        return 0


def get_new_signals_since(since_timestamp: str) -> int:
    """
    Count new completed predictions since a given ISO timestamp.

    Used by the 'new signals since you last checked' indicator.

    Args:
        since_timestamp: ISO-format timestamp string.

    Returns:
        Integer count. Returns 0 on error or if since_timestamp is None/empty.
    """
    if not since_timestamp:
        return 0

    query = text("""
        SELECT COUNT(*) as new_count
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp > :since_timestamp
    """)

    try:
        rows, columns = _base.execute_query(query, {"since_timestamp": since_timestamp})
        if rows and rows[0]:
            return rows[0][0] or 0
        return 0
    except Exception as e:
        logger.error(f"Error counting new signals: {e}")
        return 0


def get_signal_feed_csv(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get full signal feed data formatted for CSV export.

    Same filtering as get_signal_feed but without pagination and with
    human-readable column names.

    Returns:
        DataFrame with export columns. Empty DataFrame on error.
    """
    df = get_signal_feed(
        limit=10000,
        offset=0,
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )

    if df.empty:
        return pd.DataFrame()

    export_df = pd.DataFrame()
    export_df["Timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    export_df["Post Text"] = df["text"].fillna("")
    export_df["Asset"] = df["symbol"].fillna(
        df["assets"].apply(
            lambda x: (
                ", ".join(x)
                if isinstance(x, list)
                else (str(x) if pd.notna(x) else "N/A")
            )
        )
    )
    export_df["Sentiment"] = df["prediction_sentiment"].fillna("N/A")
    export_df["Confidence"] = df["confidence"].apply(
        lambda x: f"{x:.0%}" if pd.notna(x) else "N/A"
    )
    export_df["Thesis"] = df["thesis"].fillna("")
    export_df["Return (1d)"] = df["return_t1"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Return (3d)"] = df["return_t3"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Return (7d)"] = df["return_t7"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Outcome"] = df["correct_t7"].apply(
        lambda x: "Correct" if x is True else ("Incorrect" if x is False else "Pending")
    )
    export_df["P&L (7d)"] = df["pnl_t7"].apply(
        lambda x: f"${x:,.2f}" if pd.notna(x) else ""
    )

    return export_df


def get_price_with_signals(
    symbol: str,
    days: int = 90,
) -> Dict[str, pd.DataFrame]:
    """
    Get combined price history and prediction signals for a symbol.

    Returns two DataFrames in a dict:
    - 'prices': OHLCV data from market_prices table
    - 'signals': Prediction signals with sentiment, confidence, thesis, outcomes

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        days: Number of days of history

    Returns:
        Dict with 'prices' and 'signals' DataFrames.
        Both may be empty if no data exists.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    price_query = text("""
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume,
            adjusted_close
        FROM market_prices
        WHERE symbol = :symbol
            AND date >= :start_date
        ORDER BY date ASC
    """)

    signal_query = text("""
        SELECT
            po.prediction_date,
            tss.timestamp AS post_timestamp,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.return_t30,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.correct_t30,
            po.pnl_t7,
            po.is_complete,
            p.thesis,
            p.assets,
            tss.text AS post_text
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :symbol
            AND po.prediction_date >= :start_date
        ORDER BY po.prediction_date ASC
    """)

    params = {"symbol": symbol.upper(), "start_date": start_date}

    result: Dict[str, pd.DataFrame] = {
        "prices": pd.DataFrame(),
        "signals": pd.DataFrame(),
    }

    try:
        rows, columns = _base.execute_query(price_query, params)
        price_df = pd.DataFrame(rows, columns=columns)
        if not price_df.empty:
            price_df["date"] = pd.to_datetime(price_df["date"])
        result["prices"] = price_df
    except Exception as e:
        logger.error(f"Error loading prices for {symbol}: {e}")

    try:
        rows, columns = _base.execute_query(signal_query, params)
        signal_df = pd.DataFrame(rows, columns=columns)
        if not signal_df.empty:
            signal_df["prediction_date"] = pd.to_datetime(signal_df["prediction_date"])
            signal_df["post_timestamp"] = pd.to_datetime(signal_df["post_timestamp"])
        result["signals"] = signal_df
    except Exception as e:
        logger.error(f"Error loading signals for {symbol}: {e}")

    return result


def get_multi_asset_signals(
    days: int = 90,
    limit: int = 200,
) -> pd.DataFrame:
    """
    Get recent prediction signals across all assets for the trend overview.

    Args:
        days: Number of days to look back
        limit: Maximum signals to return

    Returns:
        DataFrame with signal data, or empty DataFrame on error.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    query = text("""
        SELECT
            po.symbol,
            po.prediction_date,
            tss.timestamp AS post_timestamp,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.return_t7,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete,
            p.thesis,
            tss.text AS post_text
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.prediction_date >= :start_date
        ORDER BY po.prediction_date DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(
            query, {"start_date": start_date, "limit": limit}
        )
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["prediction_date"] = pd.to_datetime(df["prediction_date"])
        return df
    except Exception as e:
        logger.error(f"Error loading multi-asset signals: {e}")
        return pd.DataFrame()
