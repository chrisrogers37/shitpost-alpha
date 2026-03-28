"""Tests for feed query functions (api/queries/feed_queries.py).

Unit tests for the query layer, mocking execute_query at the
api.dependencies level.
"""

from datetime import datetime
from unittest.mock import patch


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — returns dict on success
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_returns_dict():
    """get_analyzed_post_at_offset returns a dict with all expected keys."""
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
        "post_1",
        "Hello",
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "user",
        None,
        1,
        2,
        3,
        4,
        5,
        100,
        ["AAPL"],
        {"AAPL": "bullish"},
        0.9,
        "Thesis",
        "completed",
        0.5,
        0.6,
        0.7,
        0.8,
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
        "post_json",
        "Text",
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "user",
        None,
        0,
        0,
        0,
        0,
        0,
        200,
        '["TSLA", "NVDA"]',
        '{"TSLA": "bullish"}',
        0.8,
        "Thesis",
        "completed",
        None,
        None,
        None,
        None,
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
        "post_native",
        "Text",
        None,
        datetime(2026, 3, 25, 12, 0, 0),
        "user",
        None,
        0,
        0,
        0,
        0,
        0,
        300,
        ["AAPL"],
        {"AAPL": "bearish"},
        0.7,
        "Thesis",
        "completed",
        None,
        None,
        None,
        None,
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
    row = (
        "AAPL",
        "bearish",
        0.85,
        178.5,
        178.2,
        177.8,
        178.0,
        176.5,
        175.0,
        174.0,
        180.0,
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
        11.2,
        19.6,
        25.2,
        -8.4,
        3.9,
        1.1,
        True,
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
    with patch(
        "api.queries.feed_queries.execute_query", return_value=([(42,)], ["total"])
    ):
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
