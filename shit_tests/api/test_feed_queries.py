"""Tests for feed query functions (api/queries/feed_queries.py).

Unit tests for the query layer, mocking execute_query at the
api.dependencies level.
"""

from unittest.mock import patch

from conftest import make_outcome_row, make_post_row


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — returns dict on success
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_returns_dict():
    """get_analyzed_post_at_offset returns (dict, total) tuple."""
    rows, columns = make_post_row(
        shitpost_id="post_1",
        text="Hello",
        content_html=None,
        username="user",
        url=None,
        replies_count=1,
        reblogs_count=2,
        favourites_count=3,
        upvotes_count=4,
        downvotes_count=5,
        account_verified=False,
        account_followers_count=None,
        prediction_id=100,
        assets=["AAPL"],
        market_impact={"AAPL": "bullish"},
        confidence=0.9,
        thesis="Thesis",
        engagement_score=0.5,
        viral_score=0.6,
        sentiment_score=0.7,
        urgency_score=0.8,
        total_count=10,
    )

    with patch("api.queries.feed_queries.execute_query", return_value=(rows, columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    assert result is not None
    row, total = result
    assert row["shitpost_id"] == "post_1"
    assert row["prediction_id"] == 100
    assert row["confidence"] == 0.9
    assert total == 10


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
    rows, columns = make_post_row(
        shitpost_id="post_json",
        assets='["TSLA", "NVDA"]',
        market_impact='{"TSLA": "bullish"}',
    )

    with patch("api.queries.feed_queries.execute_query", return_value=(rows, columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    row, _ = result
    assert row["assets"] == ["TSLA", "NVDA"]
    assert isinstance(row["assets"], list)
    assert row["market_impact"] == {"TSLA": "bullish"}
    assert isinstance(row["market_impact"], dict)


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — leaves list/dict assets as-is
# ---------------------------------------------------------------------------


def test_get_analyzed_post_at_offset_leaves_native_types():
    """When assets is already a list and market_impact a dict, they are not re-parsed."""
    rows, columns = make_post_row(
        shitpost_id="post_native",
        assets=["AAPL"],
        market_impact={"AAPL": "bearish"},
    )

    with patch("api.queries.feed_queries.execute_query", return_value=(rows, columns)):
        from api.queries.feed_queries import get_analyzed_post_at_offset

        result = get_analyzed_post_at_offset(0)

    row, _ = result
    assert row["assets"] == ["AAPL"]
    assert row["market_impact"] == {"AAPL": "bearish"}


# ---------------------------------------------------------------------------
# get_outcomes_for_prediction — returns list of dicts
# ---------------------------------------------------------------------------


def test_get_outcomes_for_prediction_returns_list():
    """get_outcomes_for_prediction returns a list of outcome dicts."""
    rows, columns = make_outcome_row()

    with patch("api.queries.feed_queries.execute_query", return_value=(rows, columns)):
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
