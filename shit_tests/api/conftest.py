"""
Conftest for API tests.
Provides TestClient, mock execute_query, and sample data fixtures.
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set DATABASE_URL env var so sync_session module can import
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")


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
def sample_post_row() -> tuple[list[tuple], list[str]]:
    """A single analyzed post row as returned by execute_query.

    Returns (rows, columns) matching get_analyzed_post_at_offset's SQL.
    Includes total_count from COUNT(*) OVER().
    """
    columns = [
        "shitpost_id",
        "text",
        "content_html",
        "timestamp",
        "username",
        "url",
        "replies_count",
        "reblogs_count",
        "favourites_count",
        "upvotes_count",
        "downvotes_count",
        "account_verified",
        "account_followers_count",
        "card",
        "media_attachments",
        "in_reply_to_id",
        "in_reply_to",
        "reblog",
        "prediction_id",
        "assets",
        "market_impact",
        "confidence",
        "thesis",
        "analysis_status",
        "engagement_score",
        "viral_score",
        "sentiment_score",
        "urgency_score",
        "total_count",
    ]
    row = (
        "post_abc123",
        "Big tariff announcement coming!",
        "<p>Big tariff announcement coming!</p>",
        datetime(2026, 3, 25, 14, 30, 0),
        "realDonaldTrump",
        "https://truthsocial.com/@realDonaldTrump/post_abc123",
        42,
        150,
        500,
        300,
        10,
        True,
        8200000,
        None,
        [],
        None,
        None,
        None,
        101,
        ["AAPL", "TSLA"],
        {"AAPL": "bearish", "TSLA": "bullish"},
        0.85,
        "Tariffs on China will hurt Apple supply chain but benefit Tesla domestic production.",
        "completed",
        0.7,
        0.8,
        -0.3,
        0.9,
        42,
    )
    return ([row], columns)


@pytest.fixture
def sample_post_row_json_strings() -> tuple[list[tuple], list[str]]:
    """A post row where assets and market_impact are JSON strings (not parsed).

    This simulates what some database drivers return.
    """
    columns = [
        "shitpost_id",
        "text",
        "content_html",
        "timestamp",
        "username",
        "url",
        "replies_count",
        "reblogs_count",
        "favourites_count",
        "upvotes_count",
        "downvotes_count",
        "account_verified",
        "account_followers_count",
        "card",
        "media_attachments",
        "in_reply_to_id",
        "in_reply_to",
        "reblog",
        "prediction_id",
        "assets",
        "market_impact",
        "confidence",
        "thesis",
        "analysis_status",
        "engagement_score",
        "viral_score",
        "sentiment_score",
        "urgency_score",
        "total_count",
    ]
    row = (
        "post_json456",
        "Trade deal signed!",
        "<p>Trade deal signed!</p>",
        datetime(2026, 3, 24, 10, 0, 0),
        "realDonaldTrump",
        None,
        10,
        50,
        200,
        100,
        5,
        False,
        None,
        None,
        None,
        None,
        None,
        None,
        202,
        '["SPY", "DIA"]',
        '{"SPY": "bullish", "DIA": "bullish"}',
        0.72,
        "Trade deal boosts market indices.",
        "completed",
        0.5,
        0.6,
        0.4,
        0.3,
        42,
    )
    return ([row], columns)


@pytest.fixture
def sample_outcomes_rows() -> tuple[list[tuple], list[str]]:
    """Outcome rows as returned by get_outcomes_for_prediction's SQL."""
    from datetime import date

    columns = [
        "symbol",
        "prediction_sentiment",
        "prediction_confidence",
        "prediction_date",
        "price_at_prediction",
        "price_at_post",
        "price_at_next_close",
        "price_1h_after",
        "price_t1",
        "price_t3",
        "price_t7",
        "price_t30",
        "return_t1",
        "return_t3",
        "return_t7",
        "return_t30",
        "return_same_day",
        "return_1h",
        "correct_t1",
        "correct_t3",
        "correct_t7",
        "correct_t30",
        "correct_same_day",
        "correct_1h",
        "pnl_t1",
        "pnl_t3",
        "pnl_t7",
        "pnl_t30",
        "pnl_same_day",
        "pnl_1h",
        "is_complete",
        "company_name",
        "asset_type",
        "exchange",
        "sector",
        "industry",
        "market_cap",
        "pe_ratio",
        "forward_pe",
        "beta",
        "dividend_yield",
    ]
    row_aapl = (
        "AAPL",
        "bearish",
        0.85,
        date(2026, 3, 25),
        178.50,
        178.20,
        177.80,
        178.00,
        176.50,
        175.00,
        174.00,
        180.00,
        -1.12,
        -1.96,
        -2.52,
        0.84,
        -0.39,
        -0.11,
        True,
        True,
        True,
        False,
        True,
        True,
        11.20,
        19.60,
        25.20,
        -8.40,
        3.90,
        1.10,
        True,
        "Apple Inc.",
        "stock",
        "NASDAQ",
        "Technology",
        "Consumer Electronics",
        2800000000000,
        28.5,
        26.1,
        1.2,
        0.005,
    )
    row_tsla = (
        "TSLA",
        "bullish",
        0.85,
        date(2026, 3, 25),
        245.00,
        244.80,
        246.50,
        245.50,
        248.00,
        252.00,
        260.00,
        240.00,
        1.22,
        2.86,
        6.12,
        -2.04,
        0.69,
        0.20,
        True,
        True,
        True,
        False,
        True,
        True,
        12.20,
        28.60,
        61.20,
        -20.40,
        6.90,
        2.00,
        True,
        "Tesla Inc.",
        "stock",
        "NASDAQ",
        "Automotive",
        "Auto Manufacturers",
        812000000000,
        68.4,
        42.1,
        2.05,
        None,
    )
    return ([row_aapl, row_tsla], columns)


@pytest.fixture
def sample_snapshot_rows() -> tuple[list[tuple], list[str]]:
    """Empty snapshot rows (no snapshots captured yet)."""
    return ([], [])


@pytest.fixture
def sample_candle_rows() -> tuple[list[tuple], list[str]]:
    """Price candle rows as returned from the database fallback query."""
    from datetime import date

    columns = ["date", "open", "high", "low", "close", "volume"]
    rows = [
        (date(2026, 3, 20), 175.0, 178.0, 174.5, 177.0, 50000000),
        (date(2026, 3, 21), 177.0, 179.5, 176.0, 178.5, 45000000),
        (date(2026, 3, 24), 178.5, 180.0, 177.0, 179.0, 55000000),
        (date(2026, 3, 25), 179.0, 181.0, 178.0, 180.5, 60000000),
    ]
    return (rows, columns)
