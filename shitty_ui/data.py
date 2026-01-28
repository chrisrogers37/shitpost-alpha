"""
Database access layer for Shitty UI Dashboard
Handles database connections and query functions for posts and predictions.
Integrates with the global Shitpost Alpha settings system.
"""

import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Any, Optional

# Add parent directory to path to import global settings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from shit.config.shitpost_settings import settings
    DATABASE_URL = settings.DATABASE_URL
    print(f"🔍 Dashboard using settings DATABASE_URL: {DATABASE_URL[:50]}...")
except ImportError as e:
    # Fallback to environment variable if settings can't be imported
    DATABASE_URL = os.environ.get("DATABASE_URL")
    print(f"🔍 Dashboard using environment DATABASE_URL: {DATABASE_URL[:50] if DATABASE_URL else 'None'}...")
    if not DATABASE_URL:
        raise ValueError(f"Could not load database URL from settings: {e}. Please set DATABASE_URL environment variable.")

# Create engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite - use synchronous SQLAlchemy
    engine = create_engine(DATABASE_URL, echo=False, future=True)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
else:
    # PostgreSQL - use synchronous engine for dashboard
    # Convert async URL to sync for dashboard use
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    # Remove SSL parameters that might cause issues
    sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")
    print(f"🔍 Using PostgreSQL sync URL: {sync_url[:50]}...")
    
    # Create synchronous engine for dashboard with explicit driver
    try:
        # Try psycopg2 first (more common)
        engine = create_engine(sync_url, echo=False, future=True)
        SessionLocal = sessionmaker(engine, expire_on_commit=False)
    except Exception as e:
        print(f"⚠️ Failed to create engine with default driver: {e}")
        # Fallback: try to use psycopg2 explicitly
        try:
            sync_url_with_driver = sync_url.replace("postgresql://", "postgresql+psycopg2://")
            engine = create_engine(sync_url_with_driver, echo=False, future=True)
            SessionLocal = sessionmaker(engine, expire_on_commit=False)
            print("✅ Successfully created engine with psycopg2 driver")
        except Exception as e2:
            print(f"❌ Failed to create engine with psycopg2: {e2}")
            raise

def execute_query(query, params=None):
    """Execute query using appropriate session type."""
    try:
        with SessionLocal() as session:
            result = session.execute(query, params or {})
            return result.fetchall(), result.keys()
    except Exception as e:
        print(f"❌ Database query error: {e}")
        print(f"🔍 DATABASE_URL: {DATABASE_URL[:50]}...")
        raise

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
    
    rows, columns = execute_query(query, {"limit": limit})
    df = pd.DataFrame(rows, columns=columns)
    return df

def load_filtered_posts(
    limit: int = 100,
    has_prediction: Optional[bool] = None,
    assets_filter: Optional[List[str]] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
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
            query = text(str(query) + " AND p.assets IS NOT NULL AND p.assets::jsonb <> '[]'::jsonb")
        else:
            query = text(str(query) + " AND (p.assets IS NULL OR p.assets::jsonb = '[]'::jsonb)")
    
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
            params["date_to_plus_one"] = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        else:
            params["date_to_plus_one"] = date_to + timedelta(days=1)
    
    query = text(str(query) + " ORDER BY tss.timestamp DESC LIMIT :limit")
    
    rows, columns = execute_query(query, params)
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
        
        df = df[df['assets'].apply(lambda x: has_asset(x, assets_filter))]
    
    return df

def get_available_assets() -> List[str]:
    """Get list of all unique assets mentioned in predictions."""
    # For now, return a hardcoded list of common assets
    # This avoids the JSON parsing complexity
    common_assets = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 
        'AMD', 'INTC', 'CRM', 'ORCL', 'ADBE', 'PYPL', 'UBER', 'LYFT',
        'SPY', 'QQQ', 'IWM', 'GLD', 'SLV', 'TLT', 'HYG', 'LQD',
        'RTN', 'LMT', 'NOC', 'BA', 'GD', 'HII', 'LHX', 'TDY'
    ]
    return common_assets

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

    rows, columns = execute_query(query)
    if rows:
        row = rows[0]
        return {
            "total_posts": row[0] or 0,
            "analyzed_posts": row[1] or 0,
            "completed_analyses": row[2] or 0,
            "bypassed_posts": row[3] or 0,
            "avg_confidence": float(row[4]) if row[4] else 0.0,
            "high_confidence_predictions": row[5] or 0
        }
    return {
        "total_posts": 0,
        "analyzed_posts": 0,
        "completed_analyses": 0,
        "bypassed_posts": 0,
        "avg_confidence": 0.0,
        "high_confidence_predictions": 0
    }


def get_recent_signals(limit: int = 10, min_confidence: float = 0.5) -> pd.DataFrame:
    """
    Get recent predictions with actionable signals (has assets and sentiment).
    Returns predictions with their outcomes if available.
    """
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
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, {"limit": limit, "min_confidence": min_confidence})
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading recent signals: {e}")
        return pd.DataFrame()


def get_performance_metrics() -> Dict[str, Any]:
    """
    Get overall prediction performance metrics from prediction_outcomes table.
    """
    query = text("""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_t7,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect_t7,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_t7,
            AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl_t7,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
    """)

    try:
        rows, columns = execute_query(query)
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
                "avg_confidence": round(float(row[6]), 2) if row[6] else 0.0
            }
    except Exception as e:
        print(f"Error loading performance metrics: {e}")

    return {
        "total_outcomes": 0,
        "evaluated_predictions": 0,
        "correct_predictions": 0,
        "incorrect_predictions": 0,
        "accuracy_t7": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl_t7": 0.0,
        "avg_confidence": 0.0
    }


def get_accuracy_by_confidence() -> pd.DataFrame:
    """
    Get prediction accuracy broken down by confidence level.
    """
    query = text("""
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
        rows, columns = execute_query(query)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['accuracy'] = (df['correct'] / df['total'] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading accuracy by confidence: {e}")
        return pd.DataFrame()


def get_accuracy_by_asset(limit: int = 15) -> pd.DataFrame:
    """
    Get prediction accuracy broken down by asset.
    """
    query = text("""
        SELECT
            symbol,
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(CASE WHEN return_t7 IS NOT NULL THEN return_t7 END)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, {"limit": limit})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['accuracy'] = (df['correct'] / df['total_predictions'] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading accuracy by asset: {e}")
        return pd.DataFrame()


def get_similar_predictions(asset: str = None, limit: int = 10) -> pd.DataFrame:
    """
    Get predictions for a specific asset with their outcomes.
    Shows historical performance for similar predictions.
    """
    if not asset:
        return pd.DataFrame()

    query = text("""
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
            po.return_t7,
            po.correct_t7,
            po.pnl_t7,
            po.price_at_prediction,
            po.price_t7
        FROM prediction_outcomes po
        INNER JOIN predictions p ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :asset
            AND po.correct_t7 IS NOT NULL
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, {"asset": asset, "limit": limit})
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading similar predictions: {e}")
        return pd.DataFrame()


def get_predictions_with_outcomes(limit: int = 50) -> pd.DataFrame:
    """
    Get recent predictions with their validated outcomes.
    This is for the main data table showing prediction results.
    """
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
        ORDER BY tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, {"limit": limit})
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading predictions with outcomes: {e}")
        return pd.DataFrame()


def get_sentiment_distribution() -> Dict[str, int]:
    """
    Get distribution of bullish/bearish/neutral predictions.
    """
    query = text("""
        SELECT
            prediction_sentiment,
            COUNT(*) as count
        FROM prediction_outcomes
        WHERE prediction_sentiment IS NOT NULL
        GROUP BY prediction_sentiment
    """)

    try:
        rows, columns = execute_query(query)
        result = {"bullish": 0, "bearish": 0, "neutral": 0}
        for row in rows:
            sentiment = row[0].lower() if row[0] else "neutral"
            if sentiment in result:
                result[sentiment] = row[1]
        return result
    except Exception as e:
        print(f"Error loading sentiment distribution: {e}")
        return {"bullish": 0, "bearish": 0, "neutral": 0}


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
        rows, columns = execute_query(query)
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        print(f"Error loading active assets: {e}")
        return []