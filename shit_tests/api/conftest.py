"""
Conftest for API tests.
Provides TestClient, mock execute_query, and row factory functions.
"""

import os
import sys
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set DATABASE_URL env var so sync_session module can import
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")


# ---------------------------------------------------------------------------
# Row factory functions
# ---------------------------------------------------------------------------


def make_post_row(**overrides) -> tuple[list[tuple], list[str]]:
    """Build a post row as returned by get_analyzed_post_at_offset's SQL.

    Column order matches the SQL query in api/queries/feed_queries.py.
    Returns (rows, columns) matching execute_query() return format.

    Usage:
        rows, cols = make_post_row()                          # all defaults
        rows, cols = make_post_row(text=None)                 # override one field
        rows, cols = make_post_row(assets='["SPY"]')          # JSON string variant
    """
    defaults = {
        "shitpost_id": "post_abc123",
        "text": "Big tariff announcement coming!",
        "content_html": "<p>Big tariff announcement coming!</p>",
        "timestamp": datetime(2026, 3, 25, 14, 30, 0),
        "username": "realDonaldTrump",
        "url": "https://truthsocial.com/@realDonaldTrump/post_abc123",
        "replies_count": 42,
        "reblogs_count": 150,
        "favourites_count": 500,
        "upvotes_count": 300,
        "downvotes_count": 10,
        "account_verified": True,
        "account_followers_count": 8200000,
        "card": None,
        "media_attachments": [],
        "in_reply_to_id": None,
        "in_reply_to": None,
        "reblog": None,
        "prediction_id": 101,
        "assets": ["AAPL", "TSLA"],
        "market_impact": {"AAPL": "bearish", "TSLA": "bullish"},
        "confidence": 0.85,
        "thesis": "Tariffs on China will hurt Apple supply chain but benefit Tesla domestic production.",
        "analysis_status": "completed",
        "engagement_score": 0.7,
        "viral_score": 0.8,
        "sentiment_score": -0.3,
        "urgency_score": 0.9,
        "total_count": 42,
    }
    defaults.update(overrides)
    columns = list(defaults.keys())
    row = tuple(defaults.values())
    return ([row], columns)


def make_outcome_row(**overrides) -> tuple[list[tuple], list[str]]:
    """Build an outcome row as returned by get_outcomes_for_prediction's SQL.

    Column order matches the SQL query in api/queries/feed_queries.py.
    Returns (rows, columns) matching execute_query() return format.

    Usage:
        rows, cols = make_outcome_row()                              # AAPL defaults
        rows, cols = make_outcome_row(symbol="TSLA", prediction_sentiment="bullish")
    """
    defaults = {
        "symbol": "AAPL",
        "prediction_sentiment": "bearish",
        "prediction_confidence": 0.85,
        "prediction_date": date(2026, 3, 25),
        "price_at_prediction": 178.50,
        "price_at_post": 178.20,
        "price_at_next_close": 177.80,
        "price_1h_after": 178.00,
        "price_t1": 176.50,
        "price_t3": 175.00,
        "price_t7": 174.00,
        "price_t30": 180.00,
        "return_t1": -1.12,
        "return_t3": -1.96,
        "return_t7": -2.52,
        "return_t30": 0.84,
        "return_same_day": -0.39,
        "return_1h": -0.11,
        "correct_t1": True,
        "correct_t3": True,
        "correct_t7": True,
        "correct_t30": False,
        "correct_same_day": True,
        "correct_1h": True,
        "pnl_t1": 11.20,
        "pnl_t3": 19.60,
        "pnl_t7": 25.20,
        "pnl_t30": -8.40,
        "pnl_same_day": 3.90,
        "pnl_1h": 1.10,
        "is_complete": True,
        "company_name": "Apple Inc.",
        "asset_type": "stock",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 2800000000000,
        "pe_ratio": 28.5,
        "forward_pe": 26.1,
        "beta": 1.2,
        "dividend_yield": 0.005,
    }
    defaults.update(overrides)
    columns = list(defaults.keys())
    row = tuple(defaults.values())
    return ([row], columns)


def make_outcome_rows(*rows_overrides: dict) -> tuple[list[tuple], list[str]]:
    """Build multiple outcome rows sharing the same column list.

    Usage:
        rows, cols = make_outcome_rows(
            {"symbol": "AAPL"},
            {"symbol": "TSLA", "prediction_sentiment": "bullish"},
        )
    """
    if not rows_overrides:
        return make_outcome_row()

    first_rows, columns = make_outcome_row(**rows_overrides[0])
    all_rows = list(first_rows)
    for ov in rows_overrides[1:]:
        more_rows, _ = make_outcome_row(**ov)
        all_rows.extend(more_rows)
    return (all_rows, columns)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_execute_query():
    """Mock execute_query at all usage sites to return controlled data.

    feed_queries and price_queries both do `from api.dependencies import execute_query`
    at module level, creating separate name bindings. We share a single MagicMock
    across both patch sites so side_effect/return_value set once works everywhere.

    Usage in tests:
        def test_something(client, mock_execute_query):
            mock_execute_query.return_value = (rows, columns)
            response = client.get("/api/feed/latest")
    """
    mock_eq = MagicMock()
    mock_eq.return_value = ([], [])
    with patch("api.queries.feed_queries.execute_query", mock_eq):
        with patch("api.queries.price_queries.execute_query", mock_eq):
            yield mock_eq


@pytest.fixture
def client(mock_execute_query):
    """FastAPI TestClient with mocked database.

    The mock_execute_query fixture is automatically active.
    Access it via the mock_execute_query fixture if you need to
    configure return values.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_snapshot_rows() -> tuple[list[tuple], list[str]]:
    """Empty snapshot rows (no snapshots captured yet)."""
    return ([], [])


@pytest.fixture
def sample_candle_rows() -> tuple[list[tuple], list[str]]:
    """Price candle rows as returned from the database fallback query."""
    columns = ["date", "open", "high", "low", "close", "volume"]
    rows = [
        (date(2026, 3, 20), 175.0, 178.0, 174.5, 177.0, 50000000),
        (date(2026, 3, 21), 177.0, 179.5, 176.0, 178.5, 45000000),
        (date(2026, 3, 24), 178.5, 180.0, 177.0, 179.0, 55000000),
        (date(2026, 3, 25), 179.0, 181.0, 178.0, 180.5, 60000000),
    ]
    return (rows, columns)
