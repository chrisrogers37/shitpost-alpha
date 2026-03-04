"""
Asset query functions.

Handles asset screener data, sparkline price loading, per-asset predictions,
asset statistics, price history, related assets, and predictions with outcomes.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Dict, Any, Optional

import data.base as _base
from data.base import ttl_cache, logger
from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME


@ttl_cache(ttl_seconds=300)
def get_asset_screener_data(
    days: int = None, timeframe: str = DEFAULT_TIMEFRAME
) -> pd.DataFrame:
    """Get combined asset screener data for the dashboard table.

    Joins per-asset accuracy metrics with the latest prediction sentiment
    for each asset, plus average confidence.

    Args:
        days: Number of days to look back (None = all time).
        timeframe: Outcome timeframe key ("t1", "t3", "t7", "t30").

    Returns:
        DataFrame with columns: symbol, total_predictions, correct,
        incorrect, avg_return, total_pnl, accuracy, latest_sentiment,
        avg_confidence, timeframe. Sorted by total_predictions descending.
    """
    # Validate timeframe key; use raw key for column interpolation
    get_tf_columns(timeframe)
    tf = timeframe

    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query_template = """
        WITH asset_metrics AS (
            SELECT
                po.symbol,
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN po.correct_{tf} = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_{tf} = false THEN 1 END) as incorrect,
                ROUND(AVG(CASE WHEN po.return_{tf} IS NOT NULL
                    THEN po.return_{tf} END)::numeric, 2) as avg_return,
                ROUND(SUM(CASE WHEN po.pnl_{tf} IS NOT NULL
                    THEN po.pnl_{tf} ELSE 0 END)::numeric, 2) as total_pnl,
                ROUND(AVG(po.prediction_confidence)::numeric, 2) as avg_confidence
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {date_filter}
            GROUP BY po.symbol
            HAVING COUNT(*) >= 2
        ),
        latest_sentiment AS (
            SELECT DISTINCT ON (po.symbol)
                po.symbol,
                po.prediction_sentiment
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {date_filter}
            ORDER BY po.symbol, po.prediction_date DESC
        )
        SELECT
            am.symbol,
            am.total_predictions,
            am.correct,
            am.incorrect,
            am.avg_return,
            am.total_pnl,
            am.avg_confidence,
            ls.prediction_sentiment as latest_sentiment
        FROM asset_metrics am
        LEFT JOIN latest_sentiment ls ON am.symbol = ls.symbol
        ORDER BY am.total_predictions DESC
    """
    query = text(query_template.format(tf=tf, date_filter=date_filter))

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
            df["timeframe"] = tf
        return df
    except Exception as e:
        logger.error(f"Error loading asset screener data: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)
def get_screener_sparkline_prices(symbols: tuple) -> Dict[str, pd.DataFrame]:
    """Batch-fetch 30-day trailing price data for screener sparklines.

    Unlike get_sparkline_prices() which centers on a prediction date,
    this fetches the most recent 30 calendar days of prices for each symbol.

    Args:
        symbols: Tuple of ticker symbols (tuple for cache hashability).

    Returns:
        Dict mapping symbol -> DataFrame with columns [date, close].
    """
    if not symbols:
        return {}

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=45)

    query = text("""
        SELECT symbol, date, close
        FROM market_prices
        WHERE symbol = ANY(:symbols)
            AND date >= :start_date
            AND date <= :end_date
        ORDER BY symbol, date ASC
    """)

    params = {
        "symbols": list(symbols),
        "start_date": start_date,
        "end_date": end_date,
    }

    try:
        rows, columns = _base.execute_query(query, params)
        if not rows:
            return {}

        df = pd.DataFrame(rows, columns=columns)
        df["date"] = pd.to_datetime(df["date"])

        result: Dict[str, pd.DataFrame] = {}
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol][["date", "close"]].reset_index(
                drop=True
            )
            if len(symbol_df) >= 2:
                result[symbol] = symbol_df

        return result
    except Exception as e:
        logger.error(f"Error loading screener sparkline prices: {e}")
        return {}


def get_similar_predictions(
    asset: str = None,
    limit: int = 10,
    days: int = None,
    timeframe: str = DEFAULT_TIMEFRAME,
) -> pd.DataFrame:
    """
    Get predictions for a specific asset with their outcomes.
    Shows historical performance for similar predictions.

    Args:
        asset: Asset symbol to filter by
        limit: Maximum number of predictions to return
        days: Number of days to look back (None = all time)
        timeframe: Outcome timeframe key ("t1", "t3", "t7", "t30").
    """
    if not asset:
        return pd.DataFrame()

    tf = get_tf_columns(timeframe)
    correct_col = tf["correct_col"]
    return_col = tf["return_col"]
    pnl_col = tf["pnl_col"]
    price_col = tf["price_col"]

    # Build date filter
    date_filter = ""
    params: Dict[str, Any] = {"asset": asset, "limit": limit}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.confidence,
            p.market_impact,
            p.thesis,
            po.prediction_sentiment,
            po.return_t1,
            po.return_t3,
            po.{return_col},
            po.{correct_col},
            po.{pnl_col},
            po.price_at_prediction,
            po.{price_col}
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :asset
            AND po.{correct_col} IS NOT NULL
            {date_filter}
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading similar predictions: {e}")
        return pd.DataFrame()


def get_predictions_with_outcomes(
    limit: int = 50,
    days: int = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get recent predictions with their validated outcomes.
    This is for the main data table showing prediction results.

    Args:
        limit: Maximum number of predictions to return
        days: Number of days to look back (None = all time)
        confidence_min: Minimum confidence threshold (0.0-1.0)
        confidence_max: Maximum confidence threshold (0.0-1.0)
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
    """
    # Build filters
    filters = []
    params: Dict[str, Any] = {"limit": limit}

    if days is not None and start_date is None:
        filters.append("AND tss.timestamp >= :start_date")
        params["start_date"] = datetime.now() - timedelta(days=days)

    if confidence_min is not None:
        filters.append("AND p.confidence >= :confidence_min")
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        filters.append("AND p.confidence <= :confidence_max")
        params["confidence_max"] = confidence_max

    if start_date is not None:
        filters.append("AND tss.timestamp >= :date_start")
        if isinstance(start_date, str):
            params["date_start"] = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            params["date_start"] = start_date

    if end_date is not None:
        filters.append("AND tss.timestamp < :date_end_plus_one")
        if isinstance(end_date, str):
            params["date_end_plus_one"] = datetime.strptime(
                end_date, "%Y-%m-%d"
            ) + timedelta(days=1)
        else:
            params["date_end_plus_one"] = end_date + timedelta(days=1)

    filter_clause = "\n        ".join(filters)

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
            p.analysis_comment,
            po.symbol as outcome_symbol,
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
        {filter_clause}
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading predictions with outcomes: {e}")
        return pd.DataFrame()


def get_asset_price_history(symbol: str, days: int = 180) -> pd.DataFrame:
    """
    Get historical price data for a specific asset.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL', 'TSLA')
        days: Number of days of history to fetch (default 180)

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, adjusted_close
        Sorted by date ascending (oldest first).
        Returns empty DataFrame on error.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    query = text("""
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

    try:
        rows, columns = _base.execute_query(
            query, {"symbol": symbol.upper(), "start_date": start_date}
        )
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        logger.error(f"Error loading price history for {symbol}: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)
def get_sparkline_prices(
    symbols: tuple,
    center_date: str,
    days_before: int = 3,
    days_after: int = 10,
) -> Dict[str, pd.DataFrame]:
    """Batch-fetch price data for sparkline rendering across multiple symbols.

    Fetches closing prices in a narrow window around the prediction date for
    each symbol. Returns a dict keyed by symbol, where each value is a small
    DataFrame of (date, close) rows -- typically 10-15 rows per symbol.

    Uses a single SQL query for ALL symbols to avoid N+1 query patterns.

    Args:
        symbols: Tuple of ticker symbols (tuple for cache hashability).
        center_date: ISO date string (YYYY-MM-DD) for the prediction date.
            The window extends days_before before and days_after after this date.
        days_before: Trading days before center_date to include.
        days_after: Trading days after center_date to include.

    Returns:
        Dict mapping symbol -> DataFrame with columns [date, close].
        Missing symbols are absent from the dict (not empty DataFrames).
    """
    if not symbols:
        return {}

    # Expand the calendar window to account for weekends/holidays
    # 3 trading days ~ 6 calendar days; 10 trading days ~ 18 calendar days
    calendar_before = int(days_before * 2.0)
    calendar_after = int(days_after * 1.8)

    from datetime import datetime as dt

    center_dt = (
        dt.strptime(center_date, "%Y-%m-%d").date()
        if isinstance(center_date, str)
        else center_date
    )
    start = center_dt - timedelta(days=calendar_before)
    end = center_dt + timedelta(days=calendar_after)

    query = text("""
        SELECT symbol, date, close
        FROM market_prices
        WHERE symbol = ANY(:symbols)
            AND date >= :start_date
            AND date <= :end_date
        ORDER BY symbol, date ASC
    """)

    params = {
        "symbols": list(symbols),
        "start_date": start,
        "end_date": end,
    }

    try:
        rows, columns = _base.execute_query(query, params)
        if not rows:
            return {}

        df = pd.DataFrame(rows, columns=columns)
        df["date"] = pd.to_datetime(df["date"])

        # Split into per-symbol DataFrames
        result: Dict[str, pd.DataFrame] = {}
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol][["date", "close"]].reset_index(
                drop=True
            )
            if len(symbol_df) >= 2:  # Need at least 2 points for a line
                result[symbol] = symbol_df

        return result
    except Exception as e:
        logger.error(f"Error loading sparkline prices: {e}")
        return {}


def get_asset_predictions(symbol: str, limit: int = 50) -> pd.DataFrame:
    """
    Get all predictions for a specific asset with their outcomes and tweet text.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        limit: Maximum number of predictions to return

    Returns:
        DataFrame with columns: prediction_date, timestamp, text, shitpost_id,
        prediction_id, prediction_sentiment, prediction_confidence,
        price_at_prediction, price_t7, return_t1, return_t3, return_t7,
        return_t30, correct_t7, pnl_t7, is_complete, confidence, thesis
        Sorted by prediction_date descending (newest first).
        Returns empty DataFrame on error.
    """
    query = text("""
        SELECT
            po.prediction_date,
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id AS prediction_id,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.price_t7,
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
            p.confidence,
            p.thesis
        FROM prediction_outcomes po
        INNER JOIN predictions p
            ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss
            ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :symbol
        ORDER BY po.prediction_date DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(
            query, {"symbol": symbol.upper(), "limit": limit}
        )
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["prediction_date"] = pd.to_datetime(df["prediction_date"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        logger.error(f"Error loading predictions for {symbol}: {e}")
        return pd.DataFrame()


@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_asset_stats(
    symbol: str, timeframe: str = DEFAULT_TIMEFRAME
) -> Dict[str, Any]:
    """
    Get aggregate performance statistics for a specific asset,
    alongside overall system averages for comparison.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        timeframe: Outcome timeframe key ("t1", "t3", "t7", "t30").

    Returns:
        Dictionary with generic keys (no _t7 suffix):
          accuracy, avg_return, total_pnl, best_return, worst_return,
          overall_accuracy, overall_avg_return, etc.
        Returns zeroed dict on error.
    """
    tf = get_tf_columns(timeframe)
    correct_col = tf["correct_col"]
    return_col = tf["return_col"]
    pnl_col = tf["pnl_col"]

    query = text(f"""
        WITH asset_stats AS (
            SELECT
                COUNT(*) AS total_predictions,
                COUNT(CASE WHEN {correct_col} = true THEN 1 END) AS correct,
                COUNT(CASE WHEN {correct_col} = false THEN 1 END) AS incorrect,
                COUNT(CASE WHEN {correct_col} IS NOT NULL THEN 1 END) AS evaluated,
                AVG(CASE WHEN {correct_col} IS NOT NULL THEN {return_col} END) AS avg_return,
                SUM(CASE WHEN {pnl_col} IS NOT NULL THEN {pnl_col} ELSE 0 END) AS total_pnl,
                AVG(prediction_confidence) AS avg_confidence,
                COUNT(CASE WHEN prediction_sentiment = 'bullish' THEN 1 END) AS bullish_count,
                COUNT(CASE WHEN prediction_sentiment = 'bearish' THEN 1 END) AS bearish_count,
                COUNT(CASE WHEN prediction_sentiment = 'neutral' THEN 1 END) AS neutral_count,
                MAX({return_col}) AS best_return,
                MIN({return_col}) AS worst_return
            FROM prediction_outcomes
            WHERE symbol = :symbol
        ),
        overall_stats AS (
            SELECT
                COUNT(CASE WHEN {correct_col} IS NOT NULL THEN 1 END) AS overall_evaluated,
                COUNT(CASE WHEN {correct_col} = true THEN 1 END) AS overall_correct,
                AVG(CASE WHEN {correct_col} IS NOT NULL THEN {return_col} END) AS overall_avg_return
            FROM prediction_outcomes
        )
        SELECT
            a.total_predictions,
            a.correct,
            a.incorrect,
            a.evaluated,
            a.avg_return,
            a.total_pnl,
            a.avg_confidence,
            a.bullish_count,
            a.bearish_count,
            a.neutral_count,
            a.best_return,
            a.worst_return,
            o.overall_evaluated,
            o.overall_correct,
            o.overall_avg_return
        FROM asset_stats a, overall_stats o
    """)

    try:
        rows, columns = _base.execute_query(query, {"symbol": symbol.upper()})
        if rows and rows[0]:
            row = rows[0]
            evaluated = row[3] or 0
            correct = row[1] or 0
            accuracy = (correct / evaluated * 100) if evaluated > 0 else 0.0

            overall_evaluated = row[12] or 0
            overall_correct = row[13] or 0
            overall_accuracy = (
                (overall_correct / overall_evaluated * 100)
                if overall_evaluated > 0
                else 0.0
            )

            return {
                "total_predictions": row[0] or 0,
                "correct_predictions": correct,
                "incorrect_predictions": row[2] or 0,
                "accuracy": round(accuracy, 1),
                "avg_return": round(float(row[4]), 2) if row[4] else 0.0,
                "total_pnl": round(float(row[5]), 2) if row[5] else 0.0,
                "avg_confidence": round(float(row[6]), 2) if row[6] else 0.0,
                "bullish_count": row[7] or 0,
                "bearish_count": row[8] or 0,
                "neutral_count": row[9] or 0,
                "best_return": round(float(row[10]), 2) if row[10] else None,
                "worst_return": round(float(row[11]), 2) if row[11] else None,
                "overall_accuracy": round(overall_accuracy, 1),
                "overall_avg_return": (round(float(row[14]), 2) if row[14] else 0.0),
            }
    except Exception as e:
        logger.error(f"Error loading asset stats for {symbol}: {e}")

    return {
        "total_predictions": 0,
        "correct_predictions": 0,
        "incorrect_predictions": 0,
        "accuracy": 0.0,
        "avg_return": 0.0,
        "total_pnl": 0.0,
        "avg_confidence": 0.0,
        "bullish_count": 0,
        "bearish_count": 0,
        "neutral_count": 0,
        "best_return": None,
        "worst_return": None,
        "overall_accuracy": 0.0,
        "overall_avg_return": 0.0,
    }


def get_related_assets(
    symbol: str, limit: int = 8, timeframe: str = DEFAULT_TIMEFRAME
) -> pd.DataFrame:
    """
    Get assets that frequently appear in the same predictions as the given symbol.

    Logic: Find all predictions that mention `symbol`, extract all other assets
    from those predictions, and count co-occurrences.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        limit: Maximum number of related assets to return

    Returns:
        DataFrame with columns: related_symbol, co_occurrence_count, avg_return
        Sorted by co_occurrence_count descending.
        Returns empty DataFrame on error.
    """
    tf = get_tf_columns(timeframe)
    return_col = tf["return_col"]

    query = text(f"""
        WITH target_predictions AS (
            -- Find all prediction IDs that mention this symbol
            SELECT p.id AS prediction_id
            FROM predictions p
            WHERE p.assets::jsonb ? :symbol
                AND p.analysis_status = 'completed'
        ),
        co_occurring_assets AS (
            -- Find all OTHER assets in those same predictions
            SELECT
                po.symbol AS related_symbol,
                COUNT(DISTINCT po.prediction_id) AS co_occurrence_count,
                AVG(po.{return_col}) AS avg_return
            FROM prediction_outcomes po
            INNER JOIN target_predictions tp
                ON po.prediction_id = tp.prediction_id
            WHERE po.symbol != :symbol
                AND po.symbol IS NOT NULL
            GROUP BY po.symbol
        )
        SELECT
            related_symbol,
            co_occurrence_count,
            ROUND(avg_return::numeric, 2) AS avg_return
        FROM co_occurring_assets
        ORDER BY co_occurrence_count DESC
        LIMIT :limit
    """)

    try:
        rows, columns = _base.execute_query(
            query, {"symbol": symbol.upper(), "limit": limit}
        )
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading related assets for {symbol}: {e}")
        return pd.DataFrame()
