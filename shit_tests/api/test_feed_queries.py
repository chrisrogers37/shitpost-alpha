"""Tests for feed query functions (api/queries/feed_queries.py).

Unit tests for the query layer, mocking execute_query at the
api.dependencies level.
"""

from datetime import datetime
from unittest.mock import patch


# ---------------------------------------------------------------------------
# get_analyzed_post_at_offset — returns dict on success
# ---------------------------------------------------------------------------


def _make_query_row(overrides=None):
    """Build a sample post query row with columns + total_count."""
    columns = [
        "shitpost_id", "text", "content_html", "timestamp",
        "username", "url",
        "replies_count", "reblogs_count", "favourites_count",
        "upvotes_count", "downvotes_count",
        "account_verified", "account_followers_count",
        "card", "media_attachments",
        "in_reply_to_id", "in_reply_to", "reblog",
        "prediction_id", "assets", "market_impact",
        "confidence", "thesis", "analysis_status",
        "engagement_score", "viral_score",
        "sentiment_score", "urgency_score",
        "total_count",
    ]
    defaults = (
        "post_1", "Hello", None,
        datetime(2026, 3, 25, 12, 0, 0),
        "user", None,
        1, 2, 3, 4, 5,
        False, None, None, None, None, None, None,
        100, ["AAPL"], {"AAPL": "bullish"},
        0.9, "Thesis", "completed",
        0.5, 0.6, 0.7, 0.8,
        10,
    )
    if overrides:
        vals = dict(zip(columns, defaults))
        vals.update(overrides)
        return ([tuple(vals.values())], list(vals.keys()))
    return ([defaults], columns)


def test_get_analyzed_post_at_offset_returns_dict():
    """get_analyzed_post_at_offset returns (dict, total) tuple."""
    rows, columns = _make_query_row()

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
    rows, columns = _make_query_row({
        "shitpost_id": "post_json",
        "assets": '["TSLA", "NVDA"]',
        "market_impact": '{"TSLA": "bullish"}',
    })

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
    rows, columns = _make_query_row({
        "shitpost_id": "post_native",
        "assets": ["AAPL"],
        "market_impact": {"AAPL": "bearish"},
    })

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
    from datetime import date

    columns = [
        "symbol", "prediction_sentiment", "prediction_confidence",
        "prediction_date",
        "price_at_prediction", "price_at_post",
        "price_at_next_close", "price_1h_after",
        "price_t1", "price_t3", "price_t7", "price_t30",
        "return_t1", "return_t3", "return_t7", "return_t30",
        "return_same_day", "return_1h",
        "correct_t1", "correct_t3", "correct_t7", "correct_t30",
        "correct_same_day", "correct_1h",
        "pnl_t1", "pnl_t3", "pnl_t7", "pnl_t30",
        "pnl_same_day", "pnl_1h",
        "is_complete",
        "company_name", "asset_type", "exchange", "sector", "industry",
        "market_cap", "pe_ratio", "forward_pe", "beta", "dividend_yield",
    ]
    row = (
        "AAPL", "bearish", 0.85,
        date(2026, 3, 25),
        178.5, 178.2, 177.8, 178.0,
        176.5, 175.0, 174.0, 180.0,
        -1.12, -1.96, -2.52, 0.84, -0.39, -0.11,
        True, True, True, False, True, True,
        11.2, 19.6, 25.2, -8.4, 3.9, 1.1,
        True,
        "Apple Inc.", "stock", "NASDAQ", "Technology",
        "Consumer Electronics", 2800000000000,
        28.5, 26.1, 1.2, 0.005,
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


