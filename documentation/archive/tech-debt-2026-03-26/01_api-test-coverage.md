# Phase 01: API Test Coverage + CORS Hardening

**Status**: ✅ COMPLETE
**Started**: 2026-03-28
**Completed**: 2026-03-28

| Field | Value |
|---|---|
| **PR Title** | `feat: API test coverage + CORS hardening` |
| **Risk** | Low |
| **Effort** | Medium |
| **Files Created** | 7 (`shit_tests/api/__init__.py`, `shit_tests/api/conftest.py`, `shit_tests/api/test_feed_router.py`, `shit_tests/api/test_prices_router.py`, `shit_tests/api/test_telegram_router.py`, `shit_tests/api/test_feed_queries.py`, `shit_tests/api/test_price_queries.py`) |
| **Files Modified** | 1 (`api/main.py`) |
| **Files Deleted** | 0 |
| **Dependencies** | None |
| **Unlocks** | None |

---

## Context

The `api/` module serves production traffic as the FastAPI backend for the React frontend deployed at `https://shitpost-alpha-web-production.up.railway.app/`. Despite being a production-facing module, it has **zero tests** — the only untested module in the entire codebase (2,338+ tests across 110 test files). Additionally, the CORS middleware uses `allow_origins=["*"]` which is overly permissive for a production deployment.

This phase adds comprehensive test coverage for all API routes, query functions, and response schemas, plus hardens the CORS configuration to restrict origins in production while keeping the wildcard for local development.

---

## Dependencies

- **Depends on**: None — this is a standalone phase.
- **Unlocks**: None — no other phases depend on this.
- **Parallel safety**: This phase touches only `api/main.py` (one modification) and creates new files under `shit_tests/api/`. It is safe to run in parallel with any phase that does not modify `api/main.py`.

---

## Detailed Implementation Plan

### Step 1: Create `shit_tests/api/__init__.py`

Create an empty init file so pytest discovers the test package.

**Create file** `shit_tests/api/__init__.py`:

```python
```

(Empty file — just needs to exist for package discovery.)

---

### Step 2: Create `shit_tests/api/conftest.py`

This conftest provides:
1. A mock for `api.dependencies.execute_query` so no real database is needed
2. A FastAPI `TestClient` fixture
3. Sample data fixtures for feed responses, price data, and outcomes

**Create file** `shit_tests/api/conftest.py`:

```python
"""
Conftest for API tests.
Provides TestClient, mock execute_query, and sample data fixtures.
"""

import os
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock settings before any api module imports
_mock_settings = MagicMock()
_mock_settings.DATABASE_URL = "sqlite:///test.db"
_mock_settings.TELEGRAM_BOT_TOKEN = "test-bot-token-123"

sys.modules.setdefault("shit.config.shitpost_settings", MagicMock())
sys.modules["shit.config.shitpost_settings"].settings = _mock_settings

# Set DATABASE_URL env var as fallback
os.environ["DATABASE_URL"] = "sqlite:///test.db"


@pytest.fixture
def mock_execute_query():
    """Mock api.dependencies.execute_query to return controlled data.

    Usage in tests:
        def test_something(client, mock_execute_query):
            mock_execute_query.return_value = (rows, columns)
            response = client.get("/api/feed/latest")
    """
    with patch("api.dependencies.execute_query") as mock_eq:
        # Default: return empty results
        mock_eq.return_value = ([], [])
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
    ]
    row = (
        "post_abc123",  # shitpost_id
        "Big tariff announcement coming!",  # text
        "<p>Big tariff announcement coming!</p>",  # content_html
        datetime(2026, 3, 25, 14, 30, 0),  # timestamp
        "realDonaldTrump",  # username
        "https://truthsocial.com/@realDonaldTrump/post_abc123",  # url
        42,  # replies_count
        150,  # reblogs_count
        500,  # favourites_count
        300,  # upvotes_count
        10,  # downvotes_count
        101,  # prediction_id
        ["AAPL", "TSLA"],  # assets (already a list)
        {"AAPL": "bearish", "TSLA": "bullish"},  # market_impact (already a dict)
        0.85,  # confidence
        "Tariffs on China will hurt Apple supply chain but benefit Tesla domestic production.",  # thesis
        "completed",  # analysis_status
        0.7,  # engagement_score
        0.8,  # viral_score
        -0.3,  # sentiment_score
        0.9,  # urgency_score
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
        202,
        '["SPY", "DIA"]',  # assets as JSON string
        '{"SPY": "bullish", "DIA": "bullish"}',  # market_impact as JSON string
        0.72,
        "Trade deal boosts market indices.",
        "completed",
        0.5,
        0.6,
        0.4,
        0.3,
    )
    return ([row], columns)


@pytest.fixture
def sample_outcomes_rows() -> tuple[list[tuple], list[str]]:
    """Outcome rows as returned by get_outcomes_for_prediction's SQL."""
    columns = [
        "symbol",
        "prediction_sentiment",
        "prediction_confidence",
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
    ]
    row_aapl = (
        "AAPL",  # symbol
        "bearish",  # prediction_sentiment
        0.85,  # prediction_confidence
        178.50,  # price_at_prediction
        178.20,  # price_at_post
        177.80,  # price_at_next_close
        178.00,  # price_1h_after
        176.50,  # price_t1
        175.00,  # price_t3
        174.00,  # price_t7
        180.00,  # price_t30
        -1.12,  # return_t1
        -1.96,  # return_t3
        -2.52,  # return_t7
        0.84,  # return_t30
        -0.39,  # return_same_day
        -0.11,  # return_1h
        True,  # correct_t1
        True,  # correct_t3
        True,  # correct_t7
        False,  # correct_t30
        True,  # correct_same_day
        True,  # correct_1h
        11.20,  # pnl_t1
        19.60,  # pnl_t3
        25.20,  # pnl_t7
        -8.40,  # pnl_t30
        3.90,  # pnl_same_day
        1.10,  # pnl_1h
        True,  # is_complete
    )
    row_tsla = (
        "TSLA",
        "bullish",
        0.85,
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
    )
    return ([row_aapl, row_tsla], columns)


@pytest.fixture
def sample_total_count_row() -> tuple[list[tuple], list[str]]:
    """Total count row as returned by get_total_analyzed_posts."""
    return ([(42,)], ["total"])


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
```

---

### Step 3: Create `shit_tests/api/test_feed_router.py`

**Create file** `shit_tests/api/test_feed_router.py`:

```python
"""Tests for the feed API router (api/routers/feed.py).

Covers:
- GET /api/feed/latest
- GET /api/feed/at?offset=N
- Navigation bounds
- JSON field parsing
- Error/edge cases
"""

from datetime import datetime
from unittest.mock import patch


# ---------------------------------------------------------------------------
# GET /api/feed/latest — happy path
# ---------------------------------------------------------------------------


def test_get_latest_post_happy_path(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows, sample_total_count_row
):
    """GET /api/feed/latest returns a complete FeedResponse with post, prediction, outcomes."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows
    count_rows, count_cols = sample_total_count_row

    # execute_query is called 3 times: post, total, outcomes
    mock_execute_query.side_effect = [
        (post_rows, post_cols),  # get_analyzed_post_at_offset(0)
        (count_rows, count_cols),  # get_total_analyzed_posts()
        (outcome_rows, outcome_cols),  # get_outcomes_for_prediction(101)
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["post"]["shitpost_id"] == "post_abc123"
    assert data["post"]["text"] == "Big tariff announcement coming!"
    assert data["post"]["username"] == "realDonaldTrump"
    assert data["post"]["engagement"]["replies"] == 42
    assert data["post"]["engagement"]["favourites"] == 500

    assert data["prediction"]["prediction_id"] == 101
    assert data["prediction"]["confidence"] == 0.85
    assert data["prediction"]["assets"] == ["AAPL", "TSLA"]
    assert data["prediction"]["market_impact"] == {"AAPL": "bearish", "TSLA": "bullish"}
    assert data["prediction"]["scores"]["urgency"] == 0.9

    assert len(data["outcomes"]) == 2
    assert data["outcomes"][0]["symbol"] == "AAPL"
    assert data["outcomes"][0]["returns"]["t1"] == -1.12
    assert data["outcomes"][0]["correct"]["t1"] is True
    assert data["outcomes"][0]["pnl"]["t1"] == 11.20
    assert data["outcomes"][1]["symbol"] == "TSLA"

    assert data["navigation"]["current_offset"] == 0
    assert data["navigation"]["total_posts"] == 42
    assert data["navigation"]["has_newer"] is False  # offset=0 is newest
    assert data["navigation"]["has_older"] is True


# ---------------------------------------------------------------------------
# GET /api/feed/latest — empty database
# ---------------------------------------------------------------------------


def test_get_latest_post_empty_database(client, mock_execute_query):
    """GET /api/feed/latest returns 404 when no analyzed posts exist."""
    mock_execute_query.return_value = ([], [])

    response = client.get("/api/feed/latest")
    assert response.status_code == 404
    assert "No post found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=0 — same as latest
# ---------------------------------------------------------------------------


def test_get_post_at_offset_zero(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows, sample_total_count_row
):
    """GET /api/feed/at?offset=0 behaves identically to /api/feed/latest."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at?offset=0")
    assert response.status_code == 200

    data = response.json()
    assert data["post"]["shitpost_id"] == "post_abc123"
    assert data["navigation"]["current_offset"] == 0


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=5 — returns 5th post
# ---------------------------------------------------------------------------


def test_get_post_at_offset_five(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows, sample_total_count_row
):
    """GET /api/feed/at?offset=5 returns the 5th most recent analyzed post."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at?offset=5")
    assert response.status_code == 200

    data = response.json()
    assert data["navigation"]["current_offset"] == 5
    assert data["navigation"]["has_newer"] is True  # offset > 0

    # Verify the query was called with offset=5
    first_call_params = mock_execute_query.call_args_list[0]
    assert first_call_params[0][1] == {"offset": 5}


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=9999 — out of range returns 404
# ---------------------------------------------------------------------------


def test_get_post_at_offset_out_of_range(client, mock_execute_query):
    """GET /api/feed/at?offset=9999 returns 404 when offset exceeds total posts."""
    mock_execute_query.return_value = ([], [])

    response = client.get("/api/feed/at?offset=9999")
    assert response.status_code == 404
    assert "No post found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=-1 — validation error (ge=0 constraint)
# ---------------------------------------------------------------------------


def test_get_post_at_negative_offset(client, mock_execute_query):
    """GET /api/feed/at?offset=-1 returns 422 validation error."""
    response = client.get("/api/feed/at?offset=-1")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Navigation bounds: has_newer=False when offset=0
# ---------------------------------------------------------------------------


def test_navigation_has_newer_false_at_offset_zero(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows
):
    """At offset=0, has_newer must be False (already at the newest post)."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([(10,)], ["total"]),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at?offset=0")
    assert response.status_code == 200
    assert response.json()["navigation"]["has_newer"] is False
    assert response.json()["navigation"]["has_older"] is True


# ---------------------------------------------------------------------------
# Navigation bounds: has_older=False when at last post
# ---------------------------------------------------------------------------


def test_navigation_has_older_false_at_last_post(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows
):
    """At offset = total - 1, has_older must be False (already at the oldest post)."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows

    # total = 10, offset = 9 (last post)
    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([(10,)], ["total"]),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at?offset=9")
    assert response.status_code == 200

    nav = response.json()["navigation"]
    assert nav["has_older"] is False
    assert nav["has_newer"] is True
    assert nav["total_posts"] == 10


# ---------------------------------------------------------------------------
# Navigation: mid-range has both directions
# ---------------------------------------------------------------------------


def test_navigation_mid_range_has_both_directions(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows
):
    """At a mid-range offset, both has_newer and has_older must be True."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([(10,)], ["total"]),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at?offset=5")
    assert response.status_code == 200

    nav = response.json()["navigation"]
    assert nav["has_newer"] is True
    assert nav["has_older"] is True


# ---------------------------------------------------------------------------
# JSON field parsing: assets as JSON string gets parsed to list
# ---------------------------------------------------------------------------


def test_assets_json_string_parsed_to_list(
    client, mock_execute_query, sample_post_row_json_strings, sample_total_count_row
):
    """When assets comes back as a JSON string from the DB, it gets parsed to a list."""
    post_rows, post_cols = sample_post_row_json_strings
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        ([], []),  # no outcomes
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["prediction"]["assets"] == ["SPY", "DIA"]
    assert isinstance(data["prediction"]["assets"], list)


# ---------------------------------------------------------------------------
# JSON field parsing: market_impact as JSON string gets parsed to dict
# ---------------------------------------------------------------------------


def test_market_impact_json_string_parsed_to_dict(
    client, mock_execute_query, sample_post_row_json_strings, sample_total_count_row
):
    """When market_impact comes back as a JSON string, it gets parsed to a dict."""
    post_rows, post_cols = sample_post_row_json_strings
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["prediction"]["market_impact"] == {"SPY": "bullish", "DIA": "bullish"}
    assert isinstance(data["prediction"]["market_impact"], dict)


# ---------------------------------------------------------------------------
# Post with None text gets default empty string
# ---------------------------------------------------------------------------


def test_post_with_none_text_defaults_to_empty_string(
    client, mock_execute_query, sample_total_count_row
):
    """When text is None in the DB row, the response should use an empty string."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_null_text", None, None, datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump", None, 0, 0, 0, 0, 0, 303,
        ["SPY"], {"SPY": "bullish"}, 0.6, "Some thesis",
        "completed", None, None, None, None,
    )
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        ([row], columns),
        (count_rows, count_cols),
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200
    assert response.json()["post"]["text"] == ""


# ---------------------------------------------------------------------------
# Post with None engagement fields default to 0
# ---------------------------------------------------------------------------


def test_post_with_none_engagement_defaults_to_zero(
    client, mock_execute_query, sample_total_count_row
):
    """When engagement counts are None, the response should default them to 0."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_none_eng", "Test post", None, datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump", None,
        None, None, None, None, None,  # all engagement counts are None
        404, ["AAPL"], {"AAPL": "bullish"}, 0.5, "Thesis",
        "completed", None, None, None, None,
    )
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        ([row], columns),
        (count_rows, count_cols),
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    eng = response.json()["post"]["engagement"]
    assert eng["replies"] == 0
    assert eng["reblogs"] == 0
    assert eng["favourites"] == 0
    assert eng["upvotes"] == 0
    assert eng["downvotes"] == 0


# ---------------------------------------------------------------------------
# Outcomes are empty list when prediction has no outcomes
# ---------------------------------------------------------------------------


def test_feed_response_with_no_outcomes(
    client, mock_execute_query, sample_post_row, sample_total_count_row
):
    """When there are no outcomes for a prediction, outcomes list is empty."""
    post_rows, post_cols = sample_post_row
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        ([], []),  # no outcomes
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200
    assert response.json()["outcomes"] == []


# ---------------------------------------------------------------------------
# Scores with None values are returned as null in JSON
# ---------------------------------------------------------------------------


def test_scores_with_none_values(
    client, mock_execute_query, sample_total_count_row
):
    """When score fields are None, they serialize as null in the JSON response."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_no_scores", "Test", None, datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump", None, 5, 10, 20, 15, 1, 505,
        ["AAPL"], {"AAPL": "bullish"}, 0.7, "Thesis",
        "completed", None, None, None, None,  # all scores None
    )
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        ([row], columns),
        (count_rows, count_cols),
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    scores = response.json()["prediction"]["scores"]
    assert scores["engagement"] is None
    assert scores["viral"] is None
    assert scores["sentiment"] is None
    assert scores["urgency"] is None


# ---------------------------------------------------------------------------
# Default offset for /at endpoint is 0
# ---------------------------------------------------------------------------


def test_at_endpoint_default_offset_is_zero(
    client, mock_execute_query, sample_post_row, sample_outcomes_rows, sample_total_count_row
):
    """GET /api/feed/at without offset param defaults to offset=0."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        (outcome_rows, outcome_cols),
    ]

    response = client.get("/api/feed/at")
    assert response.status_code == 200
    assert response.json()["navigation"]["current_offset"] == 0


# ---------------------------------------------------------------------------
# Timestamp is serialized as ISO string
# ---------------------------------------------------------------------------


def test_timestamp_serialized_as_iso_string(
    client, mock_execute_query, sample_post_row, sample_total_count_row
):
    """The post timestamp should be an ISO-format string in the response."""
    post_rows, post_cols = sample_post_row
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    ts = response.json()["post"]["timestamp"]
    assert "2026" in ts
    assert "T" in ts or "-" in ts  # ISO format contains these
```

---

### Step 4: Create `shit_tests/api/test_prices_router.py`

**Create file** `shit_tests/api/test_prices_router.py`:

```python
"""Tests for the prices API router (api/routers/prices.py).

Covers:
- GET /api/prices/{symbol}
- Days parameter validation
- post_timestamp handling
- yfinance fallback to DB
- TTL cache behavior
- Edge cases
"""

from datetime import date
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL — happy path
# ---------------------------------------------------------------------------


def test_get_prices_happy_path(client, mock_execute_query):
    """GET /api/prices/AAPL returns PriceResponse with candles from yfinance."""
    mock_record = MagicMock()
    mock_record.date = date(2026, 3, 25)
    mock_record.open = 180.0
    mock_record.high = 182.0
    mock_record.low = 179.0
    mock_record.close = 181.5
    mock_record.volume = 50000000

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {
                    "date": "2026-03-25",
                    "open": 180.0,
                    "high": 182.0,
                    "low": 179.0,
                    "close": 181.5,
                    "volume": 50000000,
                }
            ]

            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert len(data["candles"]) == 1
    assert data["candles"][0]["close"] == 181.5
    assert data["post_date_index"] is None  # no post_timestamp given
    assert data["post_timestamp"] is None


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=7 — respects days param
# ---------------------------------------------------------------------------


def test_get_prices_respects_days_param(client, mock_execute_query):
    """GET /api/prices/AAPL?days=7 passes days=7 to get_price_data."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {"date": "2026-03-24", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
            ]

            response = client.get("/api/prices/AAPL?days=7")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=0 — validation error (ge=1)
# ---------------------------------------------------------------------------


def test_get_prices_days_zero_validation_error(client, mock_execute_query):
    """GET /api/prices/AAPL?days=0 returns 422 (days must be >= 1)."""
    response = client.get("/api/prices/AAPL?days=0")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?days=999 — validation error (le=365)
# ---------------------------------------------------------------------------


def test_get_prices_days_too_large_validation_error(client, mock_execute_query):
    """GET /api/prices/AAPL?days=999 returns 422 (days must be <= 365)."""
    response = client.get("/api/prices/AAPL?days=999")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?post_timestamp=... — finds correct post_date_index
# ---------------------------------------------------------------------------


def test_get_prices_with_post_timestamp(client, mock_execute_query):
    """post_timestamp locates the correct candle index in the response."""
    candles = [
        {"date": "2026-03-20", "open": 175, "high": 178, "low": 174, "close": 177, "volume": 50000000},
        {"date": "2026-03-21", "open": 177, "high": 179, "low": 176, "close": 178, "volume": 45000000},
        {"date": "2026-03-24", "open": 178, "high": 180, "low": 177, "close": 179, "volume": 55000000},
        {"date": "2026-03-25", "open": 179, "high": 181, "low": 178, "close": 180, "volume": 60000000},
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles
            response = client.get("/api/prices/AAPL?post_timestamp=2026-03-21T14:30:00Z")

    assert response.status_code == 200
    data = response.json()
    assert data["post_date_index"] == 1  # index of 2026-03-21
    assert data["post_timestamp"] == "2026-03-21T14:30:00Z"


# ---------------------------------------------------------------------------
# GET /api/prices/AAPL?post_timestamp=invalid — gracefully handles bad timestamp
# ---------------------------------------------------------------------------


def test_get_prices_invalid_post_timestamp(client, mock_execute_query):
    """An invalid post_timestamp is silently ignored; post_date_index is None."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = [
                {"date": "2026-03-25", "open": 179, "high": 181, "low": 178, "close": 180, "volume": 60000000},
            ]
            response = client.get("/api/prices/AAPL?post_timestamp=not-a-date")

    assert response.status_code == 200
    data = response.json()
    assert data["post_date_index"] is None


# ---------------------------------------------------------------------------
# Empty candles returned (yfinance + DB both fail)
# ---------------------------------------------------------------------------


def test_get_prices_both_sources_fail_returns_empty_candles(client, mock_execute_query):
    """When yfinance returns [] and DB fallback also returns [], candles is empty."""
    # mock_execute_query already returns ([], []) by default (DB fallback)
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []  # yfinance fails
            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["candles"] == []


# ---------------------------------------------------------------------------
# Cache hit: second request returns cached data
# ---------------------------------------------------------------------------


def test_get_prices_cache_hit(client, mock_execute_query):
    """Second request within TTL returns cached data without re-fetching."""
    candles = [
        {"date": "2026-03-25", "open": 179, "high": 181, "low": 178, "close": 180, "volume": 60000000},
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles

            # First request — populates cache
            response1 = client.get("/api/prices/AAPL?days=30")
            assert response1.status_code == 200
            assert mock_yf.call_count == 1

            # Second request — should hit cache
            response2 = client.get("/api/prices/AAPL?days=30")
            assert response2.status_code == 200
            assert mock_yf.call_count == 1  # NOT called again

    assert response2.json()["candles"] == response1.json()["candles"]


# ---------------------------------------------------------------------------
# Symbol is uppercased in response
# ---------------------------------------------------------------------------


def test_get_prices_symbol_uppercased(client, mock_execute_query):
    """Symbol is uppercased in the response regardless of input casing."""
    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []
            response = client.get("/api/prices/aapl")

    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# yfinance fails, DB fallback succeeds
# ---------------------------------------------------------------------------


def test_get_prices_yfinance_fails_db_fallback(client, mock_execute_query, sample_candle_rows):
    """When yfinance returns empty, falls back to database and returns those candles."""
    db_rows, db_cols = sample_candle_rows

    # mock_execute_query handles the DB fallback query
    mock_execute_query.return_value = (db_rows, db_cols)

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = []  # yfinance returns nothing
            response = client.get("/api/prices/AAPL")

    assert response.status_code == 200
    data = response.json()
    assert len(data["candles"]) == 4
    assert data["candles"][0]["date"] == "2026-03-20"


# ---------------------------------------------------------------------------
# post_timestamp between two candle dates picks the earlier one
# ---------------------------------------------------------------------------


def test_post_timestamp_between_dates_picks_earlier(client, mock_execute_query):
    """When post_timestamp falls between two candle dates, the index of the earlier candle is used."""
    candles = [
        {"date": "2026-03-20", "open": 175, "high": 178, "low": 174, "close": 177, "volume": 50000000},
        {"date": "2026-03-24", "open": 178, "high": 180, "low": 177, "close": 179, "volume": 55000000},
    ]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            mock_yf.return_value = candles
            # March 22 is between Mar 20 and Mar 24
            response = client.get("/api/prices/AAPL?post_timestamp=2026-03-22T12:00:00Z")

    assert response.status_code == 200
    data = response.json()
    assert data["post_date_index"] == 0  # picks the earlier candle (Mar 20)
```

---

### Step 5: Create `shit_tests/api/test_telegram_router.py`

**Create file** `shit_tests/api/test_telegram_router.py`:

```python
"""Tests for the Telegram webhook router (api/routers/telegram.py).

Covers:
- POST /telegram/webhook
- GET /telegram/health
- Error handling
"""

from unittest.mock import patch, MagicMock
from datetime import datetime


# ---------------------------------------------------------------------------
# POST /telegram/webhook — valid update returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_valid_update(client, mock_execute_query):
    """POST /telegram/webhook with a valid Telegram update returns 200 {"ok": true}."""
    update_payload = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {"id": 789, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 789, "type": "private"},
            "date": 1711000000,
            "text": "/start",
        },
    }

    with patch("api.routers.telegram.process_update") as mock_process:
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_process.assert_called_once_with(update_payload)


# ---------------------------------------------------------------------------
# POST /telegram/webhook — invalid JSON returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_invalid_json(client, mock_execute_query):
    """POST /telegram/webhook with invalid JSON returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "Invalid JSON" in response.json()["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — process_update exception still returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_process_update_exception_returns_200(client, mock_execute_query):
    """Even if process_update raises, the webhook returns 200 to prevent Telegram retries."""
    update_payload = {"update_id": 999, "message": {"text": "/crash"}}

    with patch("api.routers.telegram.process_update", side_effect=RuntimeError("boom")):
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# GET /telegram/health — returns health info
# ---------------------------------------------------------------------------


def test_telegram_health_happy_path(client, mock_execute_query):
    """GET /telegram/health returns full health info when everything works."""
    mock_stats = {"total": 50, "active": 45, "total_alerts_sent": 1200}
    mock_last_check = datetime(2026, 3, 25, 14, 0, 0)

    with patch("api.routers.telegram.get_subscription_stats", return_value=mock_stats):
        with patch("api.routers.telegram.get_last_alert_check", return_value=mock_last_check):
            with patch("api.routers.telegram.get_bot_token", return_value="valid-token"):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "telegram_alerts"
    assert data["bot_configured"] is True
    assert data["subscribers"]["total"] == 50
    assert data["subscribers"]["active"] == 45
    assert data["total_alerts_sent"] == 1200
    assert data["last_alert_check"] is not None


# ---------------------------------------------------------------------------
# GET /telegram/health — with missing bot token
# ---------------------------------------------------------------------------


def test_telegram_health_missing_bot_token(client, mock_execute_query):
    """GET /telegram/health reports bot_configured=False when token is missing."""
    mock_stats = {"total": 10, "active": 8, "total_alerts_sent": 50}

    with patch("api.routers.telegram.get_subscription_stats", return_value=mock_stats):
        with patch("api.routers.telegram.get_last_alert_check", return_value=None):
            with patch("api.routers.telegram.get_bot_token", return_value=None):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["bot_configured"] is False
    assert data["last_alert_check"] is None


# ---------------------------------------------------------------------------
# GET /telegram/health — when DB stats fail returns 503
# ---------------------------------------------------------------------------


def test_telegram_health_db_failure_returns_503(client, mock_execute_query):
    """GET /telegram/health returns 503 when database calls raise."""
    with patch(
        "api.routers.telegram.get_subscription_stats",
        side_effect=ConnectionError("DB unavailable"),
    ):
        response = client.get("/telegram/health")

    assert response.status_code == 503
    data = response.json()
    assert data["ok"] is False
    assert "error" in data
    assert "DB unavailable" in data["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — empty body returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_empty_body(client, mock_execute_query):
    """POST /telegram/webhook with empty body returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /telegram/health — last_alert_check is None when no alerts sent
# ---------------------------------------------------------------------------


def test_telegram_health_no_alerts_sent(client, mock_execute_query):
    """GET /telegram/health handles the case where no alerts have ever been sent."""
    mock_stats = {"total": 1, "active": 1, "total_alerts_sent": 0}

    with patch("api.routers.telegram.get_subscription_stats", return_value=mock_stats):
        with patch("api.routers.telegram.get_last_alert_check", return_value=None):
            with patch("api.routers.telegram.get_bot_token", return_value="tok"):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["last_alert_check"] is None
    assert data["total_alerts_sent"] == 0
```

**Important note about the telegram router**: The `process_update`, `get_subscription_stats`, `get_last_alert_check`, and `get_bot_token` functions are imported *inside* the endpoint functions (lazy imports). The `with patch(...)` targets must match the import path *as resolved at call time*. Since the imports happen inside the function body using `from notifications.telegram_bot import process_update`, the mock target is `api.routers.telegram.process_update` only if the function was previously imported at module level. Looking at the source code more carefully:

- `process_update` is imported lazily inside `telegram_webhook()` — so the mock target is `notifications.telegram_bot.process_update`
- `get_subscription_stats`, `get_last_alert_check`, `get_bot_token` are imported lazily inside `telegram_health()` — so mock targets are `notifications.db.get_subscription_stats`, `notifications.telegram_sender.get_bot_token`, etc.

**However**, since these are lazy imports that happen on every call, patching the source module works. The tests above patch `api.routers.telegram.process_update` which will NOT work because the name is not at module scope. Here is the corrected approach — we need to patch at the import source:

**CORRECTION**: Replace all `api.routers.telegram.process_update` patches with `notifications.telegram_bot.process_update`, and similarly for the health check imports. The corrected test file is shown in Step 5 above — but let me provide the exact corrected mock targets below in a dedicated section.

---

### Step 5 (CORRECTED): Telegram mock targets

Because the telegram router uses lazy imports (imports inside the function body), the mock targets must be the *source module* where the functions are defined:

| Function | Source module | Mock target |
|---|---|---|
| `process_update` | `notifications.telegram_bot` | `notifications.telegram_bot.process_update` |
| `get_subscription_stats` | `notifications.db` | `notifications.db.get_subscription_stats` |
| `get_last_alert_check` | `notifications.db` | `notifications.db.get_last_alert_check` |
| `get_bot_token` | `notifications.telegram_sender` | `notifications.telegram_sender.get_bot_token` |

**Updated `shit_tests/api/test_telegram_router.py`** (full corrected version):

```python
"""Tests for the Telegram webhook router (api/routers/telegram.py).

Covers:
- POST /telegram/webhook
- GET /telegram/health
- Error handling

NOTE: The telegram router uses lazy imports (inside function bodies), so
mock targets point to the source modules, not api.routers.telegram.
"""

from unittest.mock import patch
from datetime import datetime


# ---------------------------------------------------------------------------
# POST /telegram/webhook — valid update returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_valid_update(client, mock_execute_query):
    """POST /telegram/webhook with a valid Telegram update returns 200 {"ok": true}."""
    update_payload = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {"id": 789, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 789, "type": "private"},
            "date": 1711000000,
            "text": "/start",
        },
    }

    with patch("notifications.telegram_bot.process_update") as mock_process:
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_process.assert_called_once_with(update_payload)


# ---------------------------------------------------------------------------
# POST /telegram/webhook — invalid JSON returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_invalid_json(client, mock_execute_query):
    """POST /telegram/webhook with invalid JSON returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "Invalid JSON" in response.json()["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — process_update exception still returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_process_update_exception_returns_200(client, mock_execute_query):
    """Even if process_update raises, the webhook returns 200 to prevent Telegram retries."""
    update_payload = {"update_id": 999, "message": {"text": "/crash"}}

    with patch(
        "notifications.telegram_bot.process_update",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# GET /telegram/health — returns health info
# ---------------------------------------------------------------------------


def test_telegram_health_happy_path(client, mock_execute_query):
    """GET /telegram/health returns full health info when everything works."""
    mock_stats = {"total": 50, "active": 45, "total_alerts_sent": 1200}
    mock_last_check = datetime(2026, 3, 25, 14, 0, 0)

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch("notifications.db.get_last_alert_check", return_value=mock_last_check):
            with patch("notifications.telegram_sender.get_bot_token", return_value="valid-token"):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "telegram_alerts"
    assert data["bot_configured"] is True
    assert data["subscribers"]["total"] == 50
    assert data["subscribers"]["active"] == 45
    assert data["total_alerts_sent"] == 1200
    assert data["last_alert_check"] is not None


# ---------------------------------------------------------------------------
# GET /telegram/health — with missing bot token
# ---------------------------------------------------------------------------


def test_telegram_health_missing_bot_token(client, mock_execute_query):
    """GET /telegram/health reports bot_configured=False when token is missing."""
    mock_stats = {"total": 10, "active": 8, "total_alerts_sent": 50}

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch("notifications.db.get_last_alert_check", return_value=None):
            with patch("notifications.telegram_sender.get_bot_token", return_value=None):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["bot_configured"] is False
    assert data["last_alert_check"] is None


# ---------------------------------------------------------------------------
# GET /telegram/health — when DB stats fail returns 503
# ---------------------------------------------------------------------------


def test_telegram_health_db_failure_returns_503(client, mock_execute_query):
    """GET /telegram/health returns 503 when database calls raise."""
    with patch(
        "notifications.db.get_subscription_stats",
        side_effect=ConnectionError("DB unavailable"),
    ):
        response = client.get("/telegram/health")

    assert response.status_code == 503
    data = response.json()
    assert data["ok"] is False
    assert "error" in data
    assert "DB unavailable" in data["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — empty body returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_empty_body(client, mock_execute_query):
    """POST /telegram/webhook with empty body returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /telegram/health — last_alert_check is None when no alerts sent
# ---------------------------------------------------------------------------


def test_telegram_health_no_alerts_sent(client, mock_execute_query):
    """GET /telegram/health handles the case where no alerts have ever been sent."""
    mock_stats = {"total": 1, "active": 1, "total_alerts_sent": 0}

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch("notifications.db.get_last_alert_check", return_value=None):
            with patch("notifications.telegram_sender.get_bot_token", return_value="tok"):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["last_alert_check"] is None
    assert data["total_alerts_sent"] == 0
```

---

### Step 6: Create `shit_tests/api/test_feed_queries.py`

**Create file** `shit_tests/api/test_feed_queries.py`:

```python
"""Tests for feed query functions (api/queries/feed_queries.py).

Unit tests for the query layer, mocking execute_query at the
api.dependencies level.
"""

import json
from datetime import datetime
from unittest.mock import patch


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — returns dict on success
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_returns_dict():
    """get_analyzed_post_at_offset returns a dict with all expected keys."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_1", "Hello", None, datetime(2026, 3, 25, 12, 0, 0),
        "user", None, 1, 2, 3, 4, 5, 100,
        ["AAPL"], {"AAPL": "bullish"}, 0.9, "Thesis",
        "completed", 0.5, 0.6, 0.7, 0.8,
    )

    with patch("api.queries.feed_queries.execute_query", return_value=([row], columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    assert result is not None
    assert result["shitpost_id"] == "post_1"
    assert result["prediction_id"] == 100
    assert result["confidence"] == 0.9


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — returns None when empty
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_returns_none_when_empty():
    """get_analyzed_post_at_offset returns None when no rows match."""
    with patch("api.queries.feed_queries.execute_query", return_value=([], [])):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(9999)

    assert result is None


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — parses JSON string assets
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_parses_json_string_assets():
    """When assets is a JSON string, it gets parsed to a list."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_json", "Text", None, datetime(2026, 3, 25, 12, 0, 0),
        "user", None, 0, 0, 0, 0, 0, 200,
        '["TSLA", "NVDA"]',  # JSON string
        '{"TSLA": "bullish"}',  # JSON string
        0.8, "Thesis", "completed", None, None, None, None,
    )

    with patch("api.queries.feed_queries.execute_query", return_value=([row], columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    assert result["assets"] == ["TSLA", "NVDA"]
    assert isinstance(result["assets"], list)
    assert result["market_impact"] == {"TSLA": "bullish"}
    assert isinstance(result["market_impact"], dict)


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — leaves list/dict assets as-is
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_leaves_native_types():
    """When assets is already a list and market_impact a dict, they are not re-parsed."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp", "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count", "prediction_id",
        "assets", "market_impact", "confidence", "thesis",
        "analysis_status", "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
    ]
    row = (
        "post_native", "Text", None, datetime(2026, 3, 25, 12, 0, 0),
        "user", None, 0, 0, 0, 0, 0, 300,
        ["AAPL"],  # already a list
        {"AAPL": "bearish"},  # already a dict
        0.7, "Thesis", "completed", None, None, None, None,
    )

    with patch("api.queries.feed_queries.execute_query", return_value=([row], columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    assert result["assets"] == ["AAPL"]
    assert result["market_impact"] == {"AAPL": "bearish"}


# ---------------------------------------------------------------------------
# get_outcomes_for_prediction — returns list of dicts
# ---------------------------------------------------------------------------


def test_get_outcomes_for_prediction_returns_list():
    """get_outcomes_for_prediction returns a list of outcome dicts."""
    columns = [
        "symbol", "prediction_sentiment", "prediction_confidence",
        "price_at_prediction", "price_at_post", "price_at_next_close",
        "price_1h_after", "price_t1", "price_t3", "price_t7", "price_t30",
        "return_t1", "return_t3", "return_t7", "return_t30",
        "return_same_day", "return_1h",
        "correct_t1", "correct_t3", "correct_t7", "correct_t30",
        "correct_same_day", "correct_1h",
        "pnl_t1", "pnl_t3", "pnl_t7", "pnl_t30",
        "pnl_same_day", "pnl_1h", "is_complete",
    ]
    row = (
        "AAPL", "bearish", 0.85, 178.5, 178.2, 177.8, 178.0,
        176.5, 175.0, 174.0, 180.0,
        -1.12, -1.96, -2.52, 0.84, -0.39, -0.11,
        True, True, True, False, True, True,
        11.2, 19.6, 25.2, -8.4, 3.9, 1.1, True,
    )

    with patch("api.queries.feed_queries.execute_query", return_value=([row], columns)):
        from api.queries.feed_queries import get_outcomes_for_prediction

        result = get_outcomes_for_prediction(101)

    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["return_t1"] == -1.12
    assert result[0]["is_complete"] is True


# ---------------------------------------------------------------------------
# get_outcomes_for_prediction — empty results
# ---------------------------------------------------------------------------


def test_get_outcomes_for_prediction_empty():
    """get_outcomes_for_prediction returns empty list when no outcomes exist."""
    with patch("api.queries.feed_queries.execute_query", return_value=([], [])):
        from api.queries.feed_queries import get_outcomes_for_prediction

        result = get_outcomes_for_prediction(9999)

    assert result == []


# ---------------------------------------------------------------------------
# get_total_analyzed_posts — returns integer count
# ---------------------------------------------------------------------------


def test_get_total_analyzed_posts_returns_count():
    """get_total_analyzed_posts returns the integer count."""
    with patch("api.queries.feed_queries.execute_query", return_value=([(42,)], ["total"])):
        from api.queries.feed_queries import get_total_analyzed_posts

        result = get_total_analyzed_posts()

    assert result == 42


# ---------------------------------------------------------------------------
# get_total_analyzed_posts — empty result returns 0
# ---------------------------------------------------------------------------


def test_get_total_analyzed_posts_empty_returns_zero():
    """get_total_analyzed_posts returns 0 when query returns no rows."""
    with patch("api.queries.feed_queries.execute_query", return_value=([], [])):
        from api.queries.feed_queries import get_total_analyzed_posts

        result = get_total_analyzed_posts()

    assert result == 0
```

---

### Step 7: Create `shit_tests/api/test_price_queries.py`

**Create file** `shit_tests/api/test_price_queries.py`:

```python
"""Tests for price query functions (api/queries/price_queries.py).

Unit tests for the query/cache layer, mocking yfinance and execute_query.
"""

import time
from datetime import date, datetime
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — happy path
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_happy_path():
    """_fetch_from_yfinance returns formatted candle dicts from YFinanceProvider."""
    mock_record = MagicMock()
    mock_record.date = date(2026, 3, 25)
    mock_record.open = 180.0
    mock_record.high = 182.0
    mock_record.low = 179.0
    mock_record.close = 181.5
    mock_record.volume = 50000000

    mock_provider = MagicMock()
    mock_provider.fetch_prices.return_value = [mock_record]

    with patch("api.queries.price_queries.YFinanceProvider", return_value=mock_provider):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("AAPL", date(2026, 3, 20), date(2026, 3, 25))

    assert len(result) == 1
    assert result[0]["date"] == "2026-03-25"
    assert result[0]["close"] == 181.5
    assert result[0]["volume"] == 50000000


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — ProviderError returns empty
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_provider_error():
    """_fetch_from_yfinance returns empty list when YFinanceProvider raises ProviderError."""
    from shit.market_data.price_provider import ProviderError

    mock_provider = MagicMock()
    mock_provider.fetch_prices.side_effect = ProviderError("No data")

    with patch("api.queries.price_queries.YFinanceProvider", return_value=mock_provider):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("INVALID", date(2026, 3, 20), date(2026, 3, 25))

    assert result == []


# ---------------------------------------------------------------------------
# _fetch_from_yfinance — None values default to 0
# ---------------------------------------------------------------------------


def test_fetch_from_yfinance_none_values_default():
    """_fetch_from_yfinance converts None OHLCV values to 0."""
    mock_record = MagicMock()
    mock_record.date = date(2026, 3, 25)
    mock_record.open = None
    mock_record.high = None
    mock_record.low = None
    mock_record.close = None
    mock_record.volume = None

    mock_provider = MagicMock()
    mock_provider.fetch_prices.return_value = [mock_record]

    with patch("api.queries.price_queries.YFinanceProvider", return_value=mock_provider):
        from api.queries.price_queries import _fetch_from_yfinance

        result = _fetch_from_yfinance("AAPL", date(2026, 3, 20), date(2026, 3, 25))

    assert result[0]["open"] == 0
    assert result[0]["close"] == 0
    assert result[0]["volume"] == 0


# ---------------------------------------------------------------------------
# _fetch_from_database — happy path
# ---------------------------------------------------------------------------


def test_fetch_from_database_happy_path():
    """_fetch_from_database returns formatted candle dicts from DB rows."""
    columns = ["date", "open", "high", "low", "close", "volume"]
    rows = [
        (date(2026, 3, 25), 180.0, 182.0, 179.0, 181.5, 50000000),
    ]

    with patch("api.queries.price_queries.execute_query", return_value=(rows, columns)):
        from api.queries.price_queries import _fetch_from_database

        result = _fetch_from_database("AAPL", date(2026, 3, 20))

    assert len(result) == 1
    assert result[0]["date"] == "2026-03-25"
    assert result[0]["close"] == 181.5


# ---------------------------------------------------------------------------
# _fetch_from_database — empty results
# ---------------------------------------------------------------------------


def test_fetch_from_database_empty():
    """_fetch_from_database returns empty list when no rows found."""
    with patch("api.queries.price_queries.execute_query", return_value=([], [])):
        from api.queries.price_queries import _fetch_from_database

        result = _fetch_from_database("FAKE", date(2026, 3, 20))

    assert result == []


# ---------------------------------------------------------------------------
# _get_candles — cache miss fetches from yfinance
# ---------------------------------------------------------------------------


def test_get_candles_cache_miss():
    """_get_candles fetches from yfinance on cache miss."""
    candles = [{"date": "2026-03-25", "open": 180, "high": 182, "low": 179, "close": 181, "volume": 50000000}]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance", return_value=candles):
            from api.queries.price_queries import _get_candles

            result = _get_candles("AAPL", 30)

    assert result == candles


# ---------------------------------------------------------------------------
# _get_candles — cache hit returns cached data
# ---------------------------------------------------------------------------


def test_get_candles_cache_hit():
    """_get_candles returns cached data without re-fetching when TTL is fresh."""
    cached_candles = [{"date": "2026-03-25", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 100}]
    cache = {("AAPL", 30): (cached_candles, time.time())}  # fresh cache entry

    with patch("api.queries.price_queries._price_cache", cache):
        with patch("api.queries.price_queries._fetch_from_yfinance") as mock_yf:
            from api.queries.price_queries import _get_candles

            result = _get_candles("AAPL", 30)

    mock_yf.assert_not_called()
    assert result == cached_candles


# ---------------------------------------------------------------------------
# get_price_data — complete response structure
# ---------------------------------------------------------------------------


def test_get_price_data_response_structure():
    """get_price_data returns dict with symbol, post_timestamp, candles, post_date_index."""
    candles = [{"date": "2026-03-25", "open": 180, "high": 182, "low": 179, "close": 181, "volume": 50000000}]

    with patch("api.queries.price_queries._price_cache", {}):
        with patch("api.queries.price_queries._fetch_from_yfinance", return_value=candles):
            from api.queries.price_queries import get_price_data

            result = get_price_data("aapl", 30, None)

    assert result["symbol"] == "AAPL"
    assert result["post_timestamp"] is None
    assert result["candles"] == candles
    assert result["post_date_index"] is None
```

---

### Step 8: Modify `api/main.py` — CORS Hardening

**File**: `api/main.py`

**Before** (lines 1-37):

```python
"""FastAPI application for Shitpost Alpha.

Serves the React frontend and JSON API for the single-post feed experience.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import feed, prices, telegram


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    yield


app = FastAPI(
    title="Shitpost Alpha API",
    description="Weaponizing Shitposts for American Profit",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for local development (Vite on :5173, API on :8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**After** (lines 1-47):

```python
"""FastAPI application for Shitpost Alpha.

Serves the React frontend and JSON API for the single-post feed experience.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import feed, prices, telegram


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    yield


app = FastAPI(
    title="Shitpost Alpha API",
    description="Weaponizing Shitposts for American Profit",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production, allow all in development
_default_origins = "https://shitpost-alpha-web-production.up.railway.app"
_allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", _default_origins)
_environment = os.environ.get("ENVIRONMENT", "production")

if _environment == "development":
    _allowed_origins = ["*"]
else:
    _allowed_origins = [o.strip() for o in _allowed_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**What changed**:
1. Removed hardcoded `allow_origins=["*"]`
2. Added `ALLOWED_ORIGINS` env var support (comma-separated list of origins)
3. Added `ENVIRONMENT` env var check — only `development` gets wildcard `*`
4. Default production origin is the Railway deployment URL
5. The rest of `api/main.py` (lines 39-73 becoming lines 49-73) stays unchanged

**Railway configuration note**: No env var changes are needed on Railway — the default (`https://shitpost-alpha-web-production.up.railway.app`) is correct for production. For local development, set `ENVIRONMENT=development` in `.env`.

---

### Step 9: Add health check test to `shit_tests/api/test_feed_router.py`

Rather than a separate file for 2 health check tests, add them at the bottom of `test_feed_router.py` since the health endpoint is defined in `api/main.py` and uses the same `client` fixture.

**Append to `shit_tests/api/test_feed_router.py`** (after the last test):

```python
# ---------------------------------------------------------------------------
# GET /api/health — returns ok
# ---------------------------------------------------------------------------


def test_health_check(client, mock_execute_query):
    """GET /api/health returns {"ok": true, "service": "shitpost-alpha-api"}."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "shitpost-alpha-api"


# ---------------------------------------------------------------------------
# GET /api/health — does not require database
# ---------------------------------------------------------------------------


def test_health_check_no_db_dependency(client, mock_execute_query):
    """GET /api/health returns 200 even if execute_query would fail."""
    mock_execute_query.side_effect = ConnectionError("DB down")

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
```

---

## Test Plan

### New tests to write

| File | Test count | What it covers |
|---|---|---|
| `shit_tests/api/test_feed_router.py` | 17 | Feed endpoints, navigation, JSON parsing, engagement defaults, health check |
| `shit_tests/api/test_prices_router.py` | 11 | Price endpoints, validation, cache, yfinance fallback, post_timestamp |
| `shit_tests/api/test_telegram_router.py` | 8 | Webhook processing, error resilience, health check |
| `shit_tests/api/test_feed_queries.py` | 8 | Query layer: offset, JSON parsing, outcomes, total count |
| `shit_tests/api/test_price_queries.py` | 8 | yfinance provider, DB fallback, cache TTL, response structure |
| **Total** | **52** | |

### Existing tests to modify

None. All tests are new.

### Coverage expectations

- `api/routers/feed.py` — 100% line coverage
- `api/routers/prices.py` — 100% line coverage
- `api/routers/telegram.py` — 100% line coverage
- `api/queries/feed_queries.py` — 100% line coverage
- `api/queries/price_queries.py` — ~95% line coverage (lazy import branches)
- `api/main.py` — ~70% line coverage (SPA serving branch depends on filesystem state)
- `api/dependencies.py` — covered transitively via mocking (not directly unit-tested since it is the mock boundary)

### Manual verification steps

1. Run `source venv/bin/activate && pytest shit_tests/api/ -v` — all 52 tests pass
2. Run `source venv/bin/activate && pytest -v` — full suite passes (no regressions)
3. Run `ruff check api/ shit_tests/api/` — no lint errors
4. Run `ruff format api/ shit_tests/api/` — files formatted
5. Verify CORS behavior locally:
   - Without `ENVIRONMENT=development`: CORS only allows Railway origin
   - With `ENVIRONMENT=development`: CORS allows all origins

---

## Documentation Updates

### CLAUDE.md

No changes needed. The test structure section in CLAUDE.md says "mirrors source structure under `shit_tests/`" — adding `shit_tests/api/` follows this convention.

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **API test coverage** — 52 tests for all FastAPI endpoints, query functions, and response schemas
  - Feed router: navigation bounds, JSON parsing, engagement defaults, error cases
  - Price router: yfinance/DB fallback, cache TTL, post_timestamp indexing, validation
  - Telegram router: webhook processing, error resilience, health check
  - Query layer: offset logic, JSON string parsing, empty results

### Security
- **CORS hardening** — Restrict `allow_origins` to Railway domain in production
  - Added `ALLOWED_ORIGINS` env var (comma-separated, defaults to Railway URL)
  - Wildcard `*` only used when `ENVIRONMENT=development`
```

---

## Stress Testing & Edge Cases

### Edge cases handled by the test suite

1. **Empty database** — `test_get_latest_post_empty_database`, `test_get_post_at_offset_out_of_range`
2. **None/null values** — `test_post_with_none_text_defaults_to_empty_string`, `test_post_with_none_engagement_defaults_to_zero`, `test_scores_with_none_values`, `test_fetch_from_yfinance_none_values_default`
3. **JSON string vs native type** — `test_assets_json_string_parsed_to_list`, `test_market_impact_json_string_parsed_to_dict`, `test_get_analyzed_post_at_offset_parses_json_string_assets`, `test_get_analyzed_post_at_offset_leaves_native_types`
4. **Validation boundaries** — `test_get_post_at_negative_offset`, `test_get_prices_days_zero_validation_error`, `test_get_prices_days_too_large_validation_error`
5. **Service failures** — `test_telegram_health_db_failure_returns_503`, `test_telegram_webhook_process_update_exception_returns_200`, `test_get_prices_both_sources_fail_returns_empty_candles`
6. **Cache behavior** — `test_get_prices_cache_hit`, `test_get_candles_cache_hit`, `test_get_candles_cache_miss`
7. **Navigation boundaries** — offset=0 (newest), offset=total-1 (oldest), mid-range, out-of-range
8. **Invalid input** — bad JSON body, invalid timestamp, negative offset

### Not covered (acceptable gaps)

- **SPA serving** (`serve_spa` function in `api/main.py`) — depends on `frontend/dist/` directory existing. Testing would require building the frontend or mocking the filesystem extensively. Low value since it is a thin static file server.
- **Database connection failures in `execute_query`** — `api/dependencies.py` is the mock boundary. Testing the actual SQLAlchemy session is an integration test concern.

---

## Verification Checklist

- [ ] `shit_tests/api/__init__.py` exists (empty file)
- [ ] `shit_tests/api/conftest.py` exists with `client`, `mock_execute_query`, and all sample data fixtures
- [ ] `shit_tests/api/test_feed_router.py` has 17 tests including 2 health check tests
- [ ] `shit_tests/api/test_prices_router.py` has 11 tests
- [ ] `shit_tests/api/test_telegram_router.py` has 8 tests
- [ ] `shit_tests/api/test_feed_queries.py` has 8 tests
- [ ] `shit_tests/api/test_price_queries.py` has 8 tests
- [ ] `api/main.py` CORS changed from `["*"]` to environment-aware origins
- [ ] `ruff check api/ shit_tests/api/` passes
- [ ] `ruff format api/ shit_tests/api/` passes
- [ ] `pytest shit_tests/api/ -v` — all 52 tests pass
- [ ] `pytest -v` — full test suite passes (no regressions)
- [ ] CHANGELOG.md updated

---

## What NOT To Do

### 1. Do NOT patch `api.routers.telegram.process_update`

The telegram router uses lazy imports inside function bodies:

```python
# Inside telegram_webhook():
from notifications.telegram_bot import process_update
```

This means `process_update` is **never** a module-level attribute of `api.routers.telegram`. Patching `api.routers.telegram.process_update` will raise `AttributeError`. You must patch at the source: `notifications.telegram_bot.process_update`.

The same applies to `get_subscription_stats`, `get_last_alert_check`, and `get_bot_token` in the health endpoint.

### 2. Do NOT use `httpx.AsyncClient` for these tests

The API endpoints are synchronous (`def`, not `async def`). Using `httpx.AsyncClient` would require `pytest-asyncio` and `async` test functions for no benefit. Use `fastapi.testclient.TestClient` (which wraps `httpx` synchronously).

### 3. Do NOT import from `api.main` at module level in conftest

The `client` fixture imports `from api.main import app` inside the fixture function, not at file level. This is intentional — it ensures the mock for `execute_query` is active before the app is constructed. If you import at file level, the app may initialize before mocks are in place.

### 4. Do NOT mock `SessionLocal` directly

The test boundary is `api.dependencies.execute_query`. Mocking `SessionLocal` or `get_db` is unnecessary and fragile — it would couple tests to the database implementation. All API routes use `execute_query`, so mocking that one function covers all database access.

### 5. Do NOT forget to clear `_price_cache` between price tests

The `_price_cache` module-level dict in `api/queries/price_queries.py` persists across tests. Every price test must either:
- Use `with patch("api.queries.price_queries._price_cache", {})` to start fresh, or
- Explicitly clear the cache

Failing to do this will cause flaky tests where order matters.

### 6. Do NOT set `ENVIRONMENT=development` in the `.env` committed to git

The CORS hardening defaults to production behavior. For local development, add `ENVIRONMENT=development` to your local `.env` file (which is gitignored). Never commit this setting.

### 7. Do NOT add `ALLOWED_ORIGINS` to Railway env vars

The default value (`https://shitpost-alpha-web-production.up.railway.app`) is correct for the current Railway deployment. Only add the env var if additional origins are needed (e.g., a staging domain).

### 8. Do NOT create a separate `test_health.py` file

The health check endpoint is just 3 lines in `api/main.py`. Two tests at the bottom of `test_feed_router.py` is cleaner than a separate file with two tests and its own imports. Keep the test file count manageable.
