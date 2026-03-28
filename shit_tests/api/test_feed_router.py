"""Tests for the feed API router (api/routers/feed.py).

Covers:
- GET /api/feed/latest
- GET /api/feed/at?offset=N
- Navigation bounds
- JSON field parsing
- Error/edge cases
- GET /api/health
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# GET /api/feed/latest — happy path
# ---------------------------------------------------------------------------


def test_get_latest_post_happy_path(
    client,
    mock_execute_query,
    sample_post_row,
    sample_outcomes_rows,
    sample_total_count_row,
):
    """GET /api/feed/latest returns a complete FeedResponse with post, prediction, outcomes."""
    post_rows, post_cols = sample_post_row
    outcome_rows, outcome_cols = sample_outcomes_rows
    count_rows, count_cols = sample_total_count_row

    mock_execute_query.side_effect = [
        (post_rows, post_cols),
        (count_rows, count_cols),
        (outcome_rows, outcome_cols),
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


def test_get_post_at_offset_zero(
    client,
    mock_execute_query,
    sample_post_row,
    sample_outcomes_rows,
    sample_total_count_row,
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
    assert response.json()["post"]["shitpost_id"] == "post_abc123"
    assert response.json()["navigation"]["current_offset"] == 0


# ---------------------------------------------------------------------------
# GET /api/feed/at?offset=5 — returns 5th post
# ---------------------------------------------------------------------------


def test_get_post_at_offset_five(
    client,
    mock_execute_query,
    sample_post_row,
    sample_outcomes_rows,
    sample_total_count_row,
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
        ([], []),
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
        "post_null_text",
        None,
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump",
        None,
        0,
        0,
        0,
        0,
        0,
        303,
        ["SPY"],
        {"SPY": "bullish"},
        0.6,
        "Some thesis",
        "completed",
        None,
        None,
        None,
        None,
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
        "post_none_eng",
        "Test post",
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump",
        None,
        None,
        None,
        None,
        None,
        None,
        404,
        ["AAPL"],
        {"AAPL": "bullish"},
        0.5,
        "Thesis",
        "completed",
        None,
        None,
        None,
        None,
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
        ([], []),
    ]

    response = client.get("/api/feed/latest")
    assert response.status_code == 200
    assert response.json()["outcomes"] == []


# ---------------------------------------------------------------------------
# Scores with None values are returned as null in JSON
# ---------------------------------------------------------------------------


def test_scores_with_none_values(client, mock_execute_query, sample_total_count_row):
    """When score fields are None, they serialize as null in the JSON response."""
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
        "post_no_scores",
        "Test",
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "realDonaldTrump",
        None,
        5,
        10,
        20,
        15,
        1,
        505,
        ["AAPL"],
        {"AAPL": "bullish"},
        0.7,
        "Thesis",
        "completed",
        None,
        None,
        None,
        None,
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
    client,
    mock_execute_query,
    sample_post_row,
    sample_outcomes_rows,
    sample_total_count_row,
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
