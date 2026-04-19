"""Tests for the feed API router (api/routers/feed.py).

Covers:
- GET /api/feed/latest
- GET /api/feed/at?offset=N
- Navigation bounds
- JSON field parsing
- Error/edge cases
- GET /api/health
"""

from conftest import make_outcome_rows, make_post_row


# ---------------------------------------------------------------------------
# GET /api/feed/latest — happy path
# ---------------------------------------------------------------------------


def test_get_latest_post_happy_path(client, mock_execute_query):
    """GET /api/feed/latest returns a complete FeedResponse with post, prediction, outcomes."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {
            "symbol": "AAPL",
            "prediction_sentiment": "bearish",
        },
        {
            "symbol": "TSLA",
            "prediction_sentiment": "bullish",
            "price_at_prediction": 245.00,
            "price_at_post": 244.80,
            "price_at_next_close": 246.50,
            "price_1h_after": 245.50,
            "price_t1": 248.00,
            "price_t3": 252.00,
            "price_t7": 260.00,
            "price_t30": 240.00,
            "return_t1": 1.22,
            "return_t3": 2.86,
            "return_t7": 6.12,
            "return_t30": -2.04,
            "return_same_day": 0.69,
            "return_1h": 0.20,
            "correct_t1": True,
            "correct_t3": True,
            "correct_t7": True,
            "correct_t30": False,
            "correct_same_day": True,
            "correct_1h": True,
            "pnl_t1": 12.20,
            "pnl_t3": 28.60,
            "pnl_t7": 61.20,
            "pnl_t30": -20.40,
            "pnl_same_day": 6.90,
            "pnl_1h": 2.00,
            "company_name": "Tesla Inc.",
            "asset_type": "stock",
            "exchange": "NASDAQ",
            "sector": "Automotive",
            "industry": "Auto Manufacturers",
            "market_cap": 812000000000,
            "pe_ratio": 68.4,
            "forward_pe": 42.1,
            "beta": 2.05,
            "dividend_yield": None,
        },
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["post"]["signal_id"] == "post_abc123"
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
    assert data["navigation"]["has_newer"] is False
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


def test_get_post_at_offset_zero(client, mock_execute_query):
    """GET /api/feed/at?offset=0 behaves identically to /api/feed/latest."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/at?offset=0")
    assert response.status_code == 200
    assert response.json()["post"]["signal_id"] == "post_abc123"
    assert response.json()["navigation"]["current_offset"] == 0


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=5 — returns 5th post
# ---------------------------------------------------------------------------


def test_get_post_at_offset_five(client, mock_execute_query):
    """GET /api/feed/at?offset=5 returns the 5th most recent analyzed post."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/at?offset=5")
    assert response.status_code == 200
    assert response.json()["navigation"]["current_offset"] == 5
    assert response.json()["navigation"]["has_newer"] is True

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


def test_navigation_has_newer_false_at_offset_zero(client, mock_execute_query):
    """At offset=0, has_newer must be False (already at the newest post)."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/at?offset=0")
    assert response.status_code == 200
    assert response.json()["navigation"]["has_newer"] is False
    assert response.json()["navigation"]["has_older"] is True


# ---------------------------------------------------------------------------
# Navigation bounds: has_older=False when at last post
# ---------------------------------------------------------------------------


def test_navigation_has_older_false_at_last_post(client, mock_execute_query):
    """At offset = total - 1, has_older must be False (already at the oldest post)."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    # total_count is 42 in make_post_row defaults, so offset=41 is the last post
    response = client.get("/api/feed/at?offset=41")
    assert response.status_code == 200

    nav = response.json()["navigation"]
    assert nav["has_older"] is False
    assert nav["has_newer"] is True
    assert nav["total_posts"] == 42


# ---------------------------------------------------------------------------
# Navigation: mid-range has both directions
# ---------------------------------------------------------------------------


def test_navigation_mid_range_has_both_directions(client, mock_execute_query):
    """At a mid-range offset, both has_newer and has_older must be True."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/at?offset=5")
    assert response.status_code == 200

    nav = response.json()["navigation"]
    assert nav["has_newer"] is True
    assert nav["has_older"] is True


# ---------------------------------------------------------------------------
# JSON field parsing: assets as JSON string gets parsed to list
# ---------------------------------------------------------------------------


def test_assets_json_string_parsed_to_list(client, mock_execute_query):
    """When assets comes back as a JSON string from the DB, it gets parsed to a list."""
    post_rows, post_cols = make_post_row(
        assets='["SPY", "DIA"]',
        market_impact='{"SPY": "bullish", "DIA": "bullish"}',
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["prediction"]["assets"] == ["SPY", "DIA"]
    assert isinstance(data["prediction"]["assets"], list)


# ---------------------------------------------------------------------------
# JSON field parsing: market_impact as JSON string gets parsed to dict
# ---------------------------------------------------------------------------


def test_market_impact_json_string_parsed_to_dict(client, mock_execute_query):
    """When market_impact comes back as a JSON string, it gets parsed to a dict."""
    post_rows, post_cols = make_post_row(
        assets='["SPY", "DIA"]',
        market_impact='{"SPY": "bullish", "DIA": "bullish"}',
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    data = response.json()
    assert data["prediction"]["market_impact"] == {"SPY": "bullish", "DIA": "bullish"}
    assert isinstance(data["prediction"]["market_impact"], dict)


# ---------------------------------------------------------------------------
# Post with None text gets default empty string
# ---------------------------------------------------------------------------


def test_post_with_none_text_defaults_to_empty_string(client, mock_execute_query):
    """When text is None in the DB row, the response should use an empty string."""
    post_rows, post_cols = make_post_row(
        signal_id="post_null_text",
        text=None,
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200
    assert response.json()["post"]["text"] == ""


# ---------------------------------------------------------------------------
# Post with None engagement fields default to 0
# ---------------------------------------------------------------------------


def test_post_with_none_engagement_defaults_to_zero(client, mock_execute_query):
    """When engagement counts are None, the response should default them to 0."""
    post_rows, post_cols = make_post_row(
        signal_id="post_none_eng",
        text="Test post",
        replies_count=None,
        reblogs_count=None,
        favourites_count=None,
        upvotes_count=None,
        downvotes_count=None,
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
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


def test_feed_response_with_no_outcomes(client, mock_execute_query):
    """When there are no outcomes for a prediction, outcomes list is empty."""
    post_rows, post_cols = make_post_row()

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200
    assert response.json()["outcomes"] == []


# ---------------------------------------------------------------------------
# Scores with None values are returned as null in JSON
# ---------------------------------------------------------------------------


def test_scores_with_none_values(client, mock_execute_query):
    """When score fields are None, they serialize as null in the JSON response."""
    post_rows, post_cols = make_post_row(
        signal_id="post_no_scores",
        replies_count=5,
        reblogs_count=10,
        favourites_count=20,
        upvotes_count=15,
        downvotes_count=1,
        prediction_id=505,
        confidence=0.7,
        engagement_score=None,
        viral_score=None,
        sentiment_score=None,
        urgency_score=None,
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
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


def test_at_endpoint_default_offset_is_zero(client, mock_execute_query):
    """GET /api/feed/at without offset param defaults to offset=0."""
    post_rows, post_cols = make_post_row()
    outcome_rows, outcome_cols = make_outcome_rows(
        {"symbol": "AAPL"}, {"symbol": "TSLA"}
    )

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (outcome_rows, outcome_cols),
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/at")
    assert response.status_code == 200
    assert response.json()["navigation"]["current_offset"] == 0


# ---------------------------------------------------------------------------
# Timestamp is serialized as ISO string
# ---------------------------------------------------------------------------


def test_timestamp_serialized_as_iso_string(client, mock_execute_query):
    """The post timestamp should be an ISO-format string in the response."""
    post_rows, post_cols = make_post_row()

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        ([], []),  # outcomes
        ([], []),  # snapshots
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200

    ts = response.json()["post"]["timestamp"]
    assert "2026" in ts
    assert "T" in ts or "-" in ts


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
