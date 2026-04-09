"""Tests for the feed service layer (api/services/feed_service.py).

Unit tests for static builder methods (pure functions, no DB mocking needed)
and orchestration tests for get_feed_response.
"""

from datetime import date, datetime
from unittest.mock import patch

from api.services.feed_service import FeedService


# ---------------------------------------------------------------------------
# build_link_preview
# ---------------------------------------------------------------------------


class TestBuildLinkPreview:
    def test_none_returns_none(self):
        assert FeedService.build_link_preview(None) is None

    def test_empty_dict_returns_none(self):
        assert FeedService.build_link_preview({}) is None

    def test_non_dict_returns_none(self):
        assert FeedService.build_link_preview("not a dict") is None

    def test_missing_title_returns_none(self):
        assert FeedService.build_link_preview({"description": "desc"}) is None

    def test_empty_title_returns_none(self):
        assert FeedService.build_link_preview({"title": ""}) is None

    def test_complete_card(self):
        card = {
            "title": "Article Title",
            "description": "Summary",
            "image": "https://example.com/img.jpg",
            "url": "https://example.com/article",
            "provider_name": "Example News",
        }
        result = FeedService.build_link_preview(card)
        assert result is not None
        assert result.title == "Article Title"
        assert result.description == "Summary"
        assert result.url == "https://example.com/article"
        assert result.provider_name == "Example News"

    def test_title_only(self):
        result = FeedService.build_link_preview({"title": "Just a title"})
        assert result is not None
        assert result.title == "Just a title"
        assert result.description is None


# ---------------------------------------------------------------------------
# build_reply_context
# ---------------------------------------------------------------------------


class TestBuildReplyContext:
    def test_none_returns_none(self):
        assert FeedService.build_reply_context(None) is None

    def test_empty_dict_returns_none(self):
        assert FeedService.build_reply_context({}) is None

    def test_non_dict_returns_none(self):
        assert FeedService.build_reply_context("not a dict") is None

    def test_no_username_no_text_returns_none(self):
        assert FeedService.build_reply_context({"account": {}}) is None

    def test_with_username(self):
        reply = {"account": {"username": "someone"}, "text": "original post"}
        result = FeedService.build_reply_context(reply)
        assert result is not None
        assert result.username == "someone"
        assert result.text == "original post"

    def test_acct_fallback(self):
        reply = {"account": {"acct": "user@server"}, "text": "post"}
        result = FeedService.build_reply_context(reply)
        assert result.username == "user@server"

    def test_text_truncated_to_200(self):
        reply = {"account": {"username": "user"}, "text": "x" * 300}
        result = FeedService.build_reply_context(reply)
        assert len(result.text) == 200

    def test_html_content_fallback(self):
        reply = {"account": {"username": "user"}, "content": "<p>HTML</p>"}
        result = FeedService.build_reply_context(reply)
        assert result.text == "<p>HTML</p>"


# ---------------------------------------------------------------------------
# build_navigation
# ---------------------------------------------------------------------------


class TestBuildNavigation:
    def test_at_newest(self):
        nav = FeedService.build_navigation(0, 42)
        assert nav.has_newer is False
        assert nav.has_older is True
        assert nav.current_offset == 0
        assert nav.total_posts == 42

    def test_at_oldest(self):
        nav = FeedService.build_navigation(41, 42)
        assert nav.has_newer is True
        assert nav.has_older is False

    def test_mid_range(self):
        nav = FeedService.build_navigation(5, 42)
        assert nav.has_newer is True
        assert nav.has_older is True

    def test_single_post(self):
        nav = FeedService.build_navigation(0, 1)
        assert nav.has_newer is False
        assert nav.has_older is False


# ---------------------------------------------------------------------------
# build_post
# ---------------------------------------------------------------------------


class TestBuildPost:
    def test_basic_post(self):
        row = {
            "shitpost_id": "post_1",
            "text": "Hello",
            "content_html": "<p>Hello</p>",
            "timestamp": datetime(2026, 3, 25, 14, 30, 0),
            "username": "user",
            "url": "https://example.com",
            "replies_count": 10,
            "reblogs_count": 20,
            "favourites_count": 30,
            "upvotes_count": 40,
            "downvotes_count": 5,
            "account_verified": True,
            "account_followers_count": 1000,
            "card": None,
            "media_attachments": [],
            "in_reply_to": None,
            "reblog": None,
        }
        post = FeedService.build_post(row, "market_open", "0m")
        assert post.shitpost_id == "post_1"
        assert post.text == "Hello"
        assert post.engagement.replies == 10
        assert post.verified is True
        assert post.market_timing == "market_open"
        assert post.is_repost is False

    def test_none_text_defaults_to_empty(self):
        row = {
            "shitpost_id": "p",
            "text": None,
            "timestamp": datetime(2026, 1, 1),
            "username": "u",
            "replies_count": 0,
            "reblogs_count": 0,
            "favourites_count": 0,
            "upvotes_count": 0,
            "downvotes_count": 0,
        }
        post = FeedService.build_post(row, "", "")
        assert post.text == ""

    def test_reblog_sets_is_repost(self):
        row = {
            "shitpost_id": "p",
            "text": "rt",
            "timestamp": datetime(2026, 1, 1),
            "username": "u",
            "reblog": {"id": "orig"},
            "replies_count": 0,
            "reblogs_count": 0,
            "favourites_count": 0,
            "upvotes_count": 0,
            "downvotes_count": 0,
        }
        post = FeedService.build_post(row, "", "")
        assert post.is_repost is True


# ---------------------------------------------------------------------------
# build_prediction
# ---------------------------------------------------------------------------


class TestBuildPrediction:
    def test_basic_prediction(self):
        row = {
            "prediction_id": 101,
            "confidence": 0.85,
            "thesis": "Bull case",
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "engagement_score": 0.7,
            "viral_score": 0.8,
            "sentiment_score": 0.5,
            "urgency_score": 0.9,
        }
        pred = FeedService.build_prediction(row)
        assert pred.prediction_id == 101
        assert pred.assets == ["AAPL"]
        assert pred.scores.urgency == 0.9

    def test_none_assets_defaults_to_empty_list(self):
        row = {
            "prediction_id": 1,
            "assets": None,
            "market_impact": None,
        }
        pred = FeedService.build_prediction(row)
        assert pred.assets == []
        assert pred.market_impact == {}


# ---------------------------------------------------------------------------
# build_outcome
# ---------------------------------------------------------------------------


class TestBuildOutcome:
    def test_basic_outcome(self):
        o = {
            "symbol": "AAPL",
            "prediction_sentiment": "bearish",
            "prediction_confidence": 0.85,
            "prediction_date": date(2026, 3, 25),
            "price_at_prediction": 178.50,
            "price_at_post": 178.20,
            "return_same_day": -0.39,
            "return_1h": -0.11,
            "return_t1": -1.12,
            "return_t3": -1.96,
            "return_t7": -2.52,
            "return_t30": 0.84,
            "correct_same_day": True,
            "correct_1h": True,
            "correct_t1": True,
            "correct_t3": True,
            "correct_t7": True,
            "correct_t30": False,
            "pnl_same_day": 3.90,
            "pnl_1h": 1.10,
            "pnl_t1": 11.20,
            "pnl_t3": 19.60,
            "pnl_t7": 25.20,
            "pnl_t30": -8.40,
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
        outcome = FeedService.build_outcome(o, None)
        assert outcome.symbol == "AAPL"
        assert outcome.returns.t1 == -1.12
        assert outcome.correct.t1 is True
        assert outcome.pnl.t1 == 11.20
        assert outcome.fundamentals is not None
        assert outcome.fundamentals.company_name == "Apple Inc."
        assert outcome.price_snapshot is None
        assert outcome.prediction_date == "2026-03-25"

    def test_without_fundamentals(self):
        o = {
            "symbol": "XYZ",
            "company_name": None,
            "prediction_date": None,
            "is_complete": False,
        }
        outcome = FeedService.build_outcome(o, None)
        assert outcome.fundamentals is None
        assert outcome.prediction_date is None

    def test_with_price_snapshot(self):
        o = {
            "symbol": "AAPL",
            "company_name": None,
            "prediction_date": None,
            "is_complete": True,
        }
        snap = {
            "price": 178.50,
            "captured_at": "2026-03-25T14:30:00",
            "market_status": "open",
            "previous_close": 177.00,
            "day_high": 179.00,
            "day_low": 176.50,
        }
        outcome = FeedService.build_outcome(o, snap)
        assert outcome.price_snapshot is not None
        assert outcome.price_snapshot.price == 178.50
        assert outcome.price_snapshot.market_status == "open"


# ---------------------------------------------------------------------------
# get_feed_response — orchestration
# ---------------------------------------------------------------------------


class TestGetFeedResponse:
    def test_returns_none_when_no_post(self):
        with patch(
            "api.services.feed_service.get_analyzed_post_at_offset", return_value=None
        ):
            service = FeedService()
            result = service.get_feed_response(0)
        assert result is None

    def test_happy_path(self):
        row = {
            "shitpost_id": "post_1",
            "text": "Test",
            "content_html": None,
            "timestamp": datetime(2026, 3, 25, 14, 30, 0),
            "username": "user",
            "url": None,
            "replies_count": 0,
            "reblogs_count": 0,
            "favourites_count": 0,
            "upvotes_count": 0,
            "downvotes_count": 0,
            "account_verified": False,
            "account_followers_count": None,
            "card": None,
            "media_attachments": None,
            "in_reply_to": None,
            "reblog": None,
            "prediction_id": 1,
            "assets": ["SPY"],
            "market_impact": {"SPY": "bullish"},
            "confidence": 0.5,
            "thesis": "Thesis",
            "analysis_status": "completed",
            "engagement_score": None,
            "viral_score": None,
            "sentiment_score": None,
            "urgency_score": None,
        }

        with (
            patch(
                "api.services.feed_service.get_analyzed_post_at_offset",
                return_value=(row, 10),
            ),
            patch(
                "api.services.feed_service.get_outcomes_for_prediction", return_value=[]
            ),
        ):
            service = FeedService()
            result = service.get_feed_response(0)

        assert result is not None
        assert result.post.shitpost_id == "post_1"
        assert result.prediction.assets == ["SPY"]
        assert result.outcomes == []
        assert result.navigation.total_posts == 10

    def test_filters_invalid_tickers_from_assets(self):
        """Assets in prediction that have no outcome (filtered by SQL) should be removed."""
        row = {
            "shitpost_id": "post_2",
            "text": "Defense and stocks",
            "content_html": None,
            "timestamp": datetime(2026, 3, 25, 14, 30, 0),
            "username": "user",
            "url": None,
            "replies_count": 0,
            "reblogs_count": 0,
            "favourites_count": 0,
            "upvotes_count": 0,
            "downvotes_count": 0,
            "account_verified": False,
            "account_followers_count": None,
            "card": None,
            "media_attachments": None,
            "in_reply_to": None,
            "reblog": None,
            "prediction_id": 2,
            "assets": ["RTX", "RTN", "DEFENSE"],
            "market_impact": {"RTX": "bullish", "RTN": "bullish", "DEFENSE": "bullish"},
            "confidence": 0.7,
            "thesis": "Defense spending",
            "analysis_status": "completed",
            "engagement_score": None,
            "viral_score": None,
            "sentiment_score": None,
            "urgency_score": None,
        }

        # Only RTX has an outcome (RTN and DEFENSE filtered by SQL)
        outcomes_raw = [
            {
                "symbol": "RTX",
                "prediction_sentiment": "bullish",
                "prediction_confidence": 0.7,
                "prediction_date": date(2026, 3, 25),
                "price_at_prediction": 120.0,
                "price_at_post": None,
                "return_same_day": None,
                "return_1h": None,
                "return_t1": 1.5,
                "return_t3": None,
                "return_t7": None,
                "return_t30": None,
                "correct_same_day": None,
                "correct_1h": None,
                "correct_t1": True,
                "correct_t3": None,
                "correct_t7": None,
                "correct_t30": None,
                "pnl_same_day": None,
                "pnl_1h": None,
                "pnl_t1": 15.0,
                "pnl_t3": None,
                "pnl_t7": None,
                "pnl_t30": None,
                "is_complete": False,
                "company_name": "RTX Corporation",
                "asset_type": "stock",
                "exchange": "NYSE",
                "sector": "Industrials",
                "industry": "Aerospace & Defense",
                "market_cap": 150000000000,
                "pe_ratio": 22.0,
                "forward_pe": 20.0,
                "beta": 0.9,
                "dividend_yield": 0.02,
                "snapshot_price": None,
                "snapshot_captured_at": None,
                "snapshot_market_status": None,
                "snapshot_previous_close": None,
                "snapshot_day_high": None,
                "snapshot_day_low": None,
            }
        ]

        with (
            patch(
                "api.services.feed_service.get_analyzed_post_at_offset",
                return_value=(row, 5),
            ),
            patch(
                "api.services.feed_service.get_outcomes_for_prediction",
                return_value=outcomes_raw,
            ),
        ):
            service = FeedService()
            result = service.get_feed_response(0)

        assert result is not None
        # Only RTX should remain in assets (RTN and DEFENSE filtered)
        assert result.prediction.assets == ["RTX"]
        assert result.prediction.market_impact == {"RTX": "bullish"}
        assert len(result.outcomes) == 1
        assert result.outcomes[0].symbol == "RTX"
