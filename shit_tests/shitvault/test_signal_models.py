"""
Tests for shitvault/signal_models.py - Source-agnostic Signal model.
"""

import pytest
from datetime import datetime

from shitvault.signal_models import Signal, signal_to_dict
from shit.db.data_models import Base


class TestSignalModel:
    """Test cases for the Signal model."""

    def test_signal_creation_minimal(self):
        """Test creating a Signal with only required fields."""
        signal = Signal(
            signal_id="post_123",
            source="truth_social",
            author_username="testuser",
            published_at=datetime(2025, 1, 15, 12, 0, 0),
        )

        assert signal.signal_id == "post_123"
        assert signal.source == "truth_social"
        assert signal.author_username == "testuser"
        assert signal.published_at == datetime(2025, 1, 15, 12, 0, 0)

    def test_signal_creation_all_fields(self):
        """Test creating a Signal with all fields populated."""
        now = datetime(2025, 6, 1, 10, 0, 0)
        signal = Signal(
            signal_id="post_456",
            source="twitter",
            source_url="https://twitter.com/user/status/456",
            text="Market is moving!",
            content_html="<p>Market is moving!</p>",
            title="Breaking News",
            language="en",
            author_id="acct_789",
            author_username="trader",
            author_display_name="Top Trader",
            author_verified=True,
            author_followers=50000,
            published_at=now,
            likes_count=100,
            shares_count=50,
            replies_count=25,
            views_count=10000,
            has_media=True,
            is_repost=False,
            is_reply=False,
            is_quote=True,
            platform_data={"quote_id": "111"},
            raw_api_data={"id": "456", "full_text": "Market is moving!"},
        )

        assert signal.signal_id == "post_456"
        assert signal.source == "twitter"
        assert signal.source_url == "https://twitter.com/user/status/456"
        assert signal.text == "Market is moving!"
        assert signal.content_html == "<p>Market is moving!</p>"
        assert signal.title == "Breaking News"
        assert signal.language == "en"
        assert signal.author_id == "acct_789"
        assert signal.author_display_name == "Top Trader"
        assert signal.author_verified is True
        assert signal.author_followers == 50000
        assert signal.likes_count == 100
        assert signal.shares_count == 50
        assert signal.replies_count == 25
        assert signal.views_count == 10000
        assert signal.has_media is True
        assert signal.is_repost is False
        assert signal.is_reply is False
        assert signal.is_quote is True
        assert signal.platform_data == {"quote_id": "111"}

    def test_signal_default_values(self):
        """Test that defaults are applied for optional numeric fields."""
        signal = Signal(
            signal_id="post_999",
            source="rss",
            author_username="feed",
            published_at=datetime(2025, 1, 1),
            likes_count=0,
            shares_count=0,
            replies_count=0,
            views_count=0,
            has_media=False,
            is_repost=False,
            is_reply=False,
            is_quote=False,
        )

        assert signal.likes_count == 0
        assert signal.shares_count == 0
        assert signal.replies_count == 0
        assert signal.views_count == 0
        assert signal.has_media is False
        assert signal.is_repost is False

    def test_signal_total_engagement(self):
        """Test total_engagement property sums likes + shares + replies."""
        signal = Signal(
            signal_id="eng_1",
            source="truth_social",
            author_username="user",
            published_at=datetime(2025, 1, 1),
            likes_count=100,
            shares_count=50,
            replies_count=25,
        )

        assert signal.total_engagement == 175

    def test_signal_total_engagement_with_none(self):
        """Test total_engagement handles None values gracefully."""
        signal = Signal(
            signal_id="eng_2",
            source="truth_social",
            author_username="user",
            published_at=datetime(2025, 1, 1),
            likes_count=None,
            shares_count=50,
            replies_count=None,
        )

        assert signal.total_engagement == 50

    def test_signal_engagement_rate(self):
        """Test engagement_rate returns ratio to followers."""
        signal = Signal(
            signal_id="rate_1",
            source="truth_social",
            author_username="influencer",
            published_at=datetime(2025, 1, 1),
            author_followers=1000,
            likes_count=50,
            shares_count=30,
            replies_count=20,
        )

        # total_engagement = 100, followers = 1000
        assert signal.engagement_rate == 0.1

    def test_signal_engagement_rate_zero_followers(self):
        """Test engagement_rate returns 0.0 when author has no followers."""
        signal = Signal(
            signal_id="rate_2",
            source="truth_social",
            author_username="newuser",
            published_at=datetime(2025, 1, 1),
            author_followers=0,
            likes_count=10,
            shares_count=5,
            replies_count=2,
        )

        assert signal.engagement_rate == 0.0

    def test_signal_repr(self):
        """Test __repr__ output."""
        signal = Signal(
            signal_id="repr_1",
            source="truth_social",
            author_username="testuser",
            published_at=datetime(2025, 1, 1),
            text="Short text",
        )

        repr_str = repr(signal)
        assert "Signal" in repr_str
        assert "truth_social" in repr_str
        assert "testuser" in repr_str

    def test_signal_table_name(self):
        """Test the model's __tablename__."""
        assert Signal.__tablename__ == "signals"

    def test_signal_platform_data_json(self):
        """Test that platform_data stores complex JSON structures."""
        platform_data = {
            "upvotes_count": 42,
            "downvotes_count": 3,
            "mentions": [{"id": "1", "username": "foo"}],
            "tags": [{"name": "stocks"}],
            "visibility": "public",
            "card": {"title": "Link Preview", "url": "https://example.com"},
        }

        signal = Signal(
            signal_id="json_1",
            source="truth_social",
            author_username="user",
            published_at=datetime(2025, 1, 1),
            platform_data=platform_data,
        )

        assert signal.platform_data["upvotes_count"] == 42
        assert len(signal.platform_data["mentions"]) == 1
        assert signal.platform_data["card"]["title"] == "Link Preview"


class TestSignalToDict:
    """Test the signal_to_dict utility function."""

    def test_signal_to_dict_basic(self):
        """Test converting a signal to dict includes key fields."""
        signal = Signal(
            signal_id="dict_1",
            source="truth_social",
            author_username="user",
            published_at=datetime(2025, 1, 1),
            text="Test content",
        )

        result = signal_to_dict(signal)
        assert isinstance(result, dict)
        assert result["signal_id"] == "dict_1"
        assert result["source"] == "truth_social"
        assert result["text"] == "Test content"


class TestPredictionDualFK:
    """Test the dual-FK (shitpost_id + signal_id) on Prediction."""

    def test_prediction_with_shitpost_id(self):
        """Test creating a Prediction with legacy shitpost_id."""
        from shitvault.shitpost_models import Prediction

        pred = Prediction(
            shitpost_id="legacy_123",
            signal_id=None,
            confidence=0.8,
            thesis="Bullish",
            assets=["TSLA"],
            market_impact={"TSLA": "bullish"},
            analysis_status="completed",
        )

        assert pred.shitpost_id == "legacy_123"
        assert pred.signal_id is None
        assert pred.content_id == "legacy_123"

    def test_prediction_with_signal_id(self):
        """Test creating a Prediction with new signal_id."""
        from shitvault.shitpost_models import Prediction

        pred = Prediction(
            shitpost_id=None,
            signal_id="signal_456",
            confidence=0.9,
            thesis="Bearish",
            assets=["AAPL"],
            market_impact={"AAPL": "bearish"},
            analysis_status="completed",
        )

        assert pred.shitpost_id is None
        assert pred.signal_id == "signal_456"
        assert pred.content_id == "signal_456"

    def test_prediction_content_id_prefers_signal(self):
        """Test that content_id prefers signal_id when both are set."""
        from shitvault.shitpost_models import Prediction

        pred = Prediction(
            shitpost_id="legacy_123",
            signal_id="signal_456",
            analysis_status="completed",
        )

        assert pred.content_id == "signal_456"
