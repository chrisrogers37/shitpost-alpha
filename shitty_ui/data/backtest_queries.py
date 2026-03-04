"""Backtest simulation queries returning time-series data for charts.

Supplements the summary-only get_backtest_simulation() in performance_queries
with a date-ordered DataFrame suitable for plotting equity curves.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import text

import data.base as _base
from data.base import ttl_cache, logger


@ttl_cache(ttl_seconds=300)
def get_backtest_equity_curve(
    initial_capital: float = 10000,
    min_confidence: float = 0.75,
    days: int = None,
) -> pd.DataFrame:
    """Get date-ordered equity curve for backtest simulation chart.

    Returns the same trade-by-trade P&L data as get_backtest_simulation()
    but includes prediction_date so it can be plotted as a time series.

    Args:
        initial_capital: Starting capital in dollars.
        min_confidence: Minimum prediction confidence threshold to include.
        days: Number of days to look back (None = all time).

    Returns:
        DataFrame with columns:
            prediction_date, daily_pnl, trade_count, cumulative_pnl, equity
        Where equity = initial_capital + cumulative_pnl.
        Empty DataFrame if no data.
    """
    date_filter = ""
    params: Dict[str, Any] = {"min_confidence": min_confidence}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            prediction_date,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as daily_pnl,
            COUNT(*) as trade_count
        FROM prediction_outcomes
        WHERE prediction_confidence >= :min_confidence
            AND correct_t7 IS NOT NULL
            AND return_t7 IS NOT NULL
            {date_filter}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["cumulative_pnl"] = df["daily_pnl"].cumsum()
            df["equity"] = initial_capital + df["cumulative_pnl"]
        return df
    except Exception as e:
        logger.error(f"Error loading backtest equity curve: {e}")
        return pd.DataFrame()
