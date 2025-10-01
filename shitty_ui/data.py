"""
Database access layer for Shitty UI Dashboard
Handles database connections and query functions for posts and predictions.
Integrates with the global Shitpost Alpha settings system.
"""

import sys
import os
import asyncio
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
            except:
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