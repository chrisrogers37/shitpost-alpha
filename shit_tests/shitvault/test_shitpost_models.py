"""
Tests for shitvault/shitpost_models.py - Domain-specific database models.
"""

import pytest
import json
from datetime import datetime
from sqlalchemy import inspect

from shitvault.shitpost_models import (
    TruthSocialShitpost,
    Prediction,
    shitpost_to_dict,
    prediction_to_dict,
)
from shitvault.signal_models import Signal  # noqa: F401 — needed for Prediction.signal relationship
from shit.db.data_models import Base


class TestTruthSocialShitpost:
    """Test cases for TruthSocialShitpost model."""

    def test_model_creation(self):
        """Test creating a TruthSocialShitpost instance."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123456789",
            content="<p>Tesla stock is going up!</p>",
            text="Tesla stock is going up!",
            timestamp=datetime(2024, 1, 15, 12, 0, 0),
            username="realDonaldTrump",
            platform="truth_social"
        )
        
        assert shitpost.shitpost_id == "123456789"
        assert shitpost.content == "<p>Tesla stock is going up!</p>"
        assert shitpost.text == "Tesla stock is going up!"
        assert shitpost.username == "realDonaldTrump"
        assert shitpost.platform == "truth_social"

    def test_model_with_defaults(self):
        """Test model with explicitly set default values."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test content",
            username="testuser",
            platform="truth_social",
            replies_count=0,
            reblogs_count=0,
            favourites_count=0,
            upvotes_count=0,
            downvotes_count=0
        )
        
        # SQLAlchemy defaults don't apply until persisted, so we test explicitly set values
        assert shitpost.shitpost_id == "123"
        assert shitpost.content == "Test content"
        assert shitpost.username == "testuser"
        assert shitpost.platform == "truth_social"
        assert shitpost.replies_count == 0

    def test_model_with_engagement_metrics(self):
        """Test model with engagement metrics."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            replies_count=100,
            reblogs_count=200,
            favourites_count=300,
            upvotes_count=250,
            downvotes_count=25
        )
        
        assert shitpost.replies_count == 100
        assert shitpost.reblogs_count == 200
        assert shitpost.favourites_count == 300
        assert shitpost.upvotes_count == 250
        assert shitpost.downvotes_count == 25

    def test_model_with_account_info(self):
        """Test model with account information."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            account_id="987654321",
            account_display_name="Test User",
            account_followers_count=5000000,
            account_following_count=50,
            account_statuses_count=10000,
            account_verified=True,
            account_website="https://example.com"
        )
        
        assert shitpost.account_id == "987654321"
        assert shitpost.account_display_name == "Test User"
        assert shitpost.account_followers_count == 5000000
        assert shitpost.account_following_count == 50
        assert shitpost.account_statuses_count == 10000
        assert shitpost.account_verified is True
        assert shitpost.account_website == "https://example.com"

    def test_model_with_media(self):
        """Test model with media attachments."""
        media_data = [
            {"id": "1", "type": "image", "url": "https://example.com/image.jpg"}
        ]
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            has_media=True,
            media_attachments=media_data
        )
        
        assert shitpost.has_media is True
        assert shitpost.media_attachments == media_data

    def test_model_with_json_fields(self):
        """Test model with JSON fields."""
        mentions = [{"username": "elonmusk", "id": "111"}]
        tags = [{"name": "TSLA", "url": "https://example.com/tags/TSLA"}]
        emojis = [{"shortcode": "fire", "url": "https://example.com/emoji/fire.png"}]
        
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            mentions=mentions,
            tags=tags,
            emojis=emojis
        )
        
        assert shitpost.mentions == mentions
        assert shitpost.tags == tags
        assert shitpost.emojis == emojis

    def test_model_with_reply_data(self):
        """Test model with reply information."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            in_reply_to_id="999",
            in_reply_to_account_id="888"
        )
        
        assert shitpost.in_reply_to_id == "999"
        assert shitpost.in_reply_to_account_id == "888"

    def test_model_with_timestamps(self):
        """Test model with various timestamps."""
        created = datetime(2024, 1, 15, 12, 0, 0)
        edited = datetime(2024, 1, 15, 13, 0, 0)
        
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test",
            username="testuser",
            timestamp=created,
            edited_at=edited
        )
        
        assert shitpost.timestamp == created
        assert shitpost.edited_at == edited

    def test_model_repr(self):
        """Test model string representation."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="This is a long post that should be truncated in the repr",
            username="testuser"
        )
        
        repr_str = repr(shitpost)
        assert "TruthSocialShitpost" in repr_str
        assert "testuser" in repr_str

    def test_table_name(self):
        """Test correct table name."""
        assert TruthSocialShitpost.__tablename__ == "truth_social_shitposts"

    def test_shitpost_id_unique_constraint(self):
        """Test that shitpost_id has unique constraint."""
        mapper = inspect(TruthSocialShitpost)
        shitpost_id_col = mapper.columns['shitpost_id']
        assert shitpost_id_col.unique is True
        assert shitpost_id_col.index is True


class TestPrediction:
    """Test cases for Prediction model."""

    def test_model_creation(self):
        """Test creating a Prediction instance."""
        prediction = Prediction(
            shitpost_id="123456789",
            assets=["TSLA", "AAPL"],
            market_impact={"TSLA": "bullish", "AAPL": "neutral"},
            confidence=0.85,
            thesis="Positive sentiment about Tesla",
            analysis_status="completed"
        )
        
        assert prediction.shitpost_id == "123456789"
        assert prediction.assets == ["TSLA", "AAPL"]
        assert prediction.market_impact == {"TSLA": "bullish", "AAPL": "neutral"}
        assert prediction.confidence == 0.85
        assert prediction.thesis == "Positive sentiment about Tesla"
        assert prediction.analysis_status == "completed"

    def test_model_with_default_status(self):
        """Test model with default status."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="pending",
            has_media=False,
            mentions_count=0,
            hashtags_count=0
        )
        
        # SQLAlchemy defaults don't apply until persisted
        assert prediction.shitpost_id == "123"
        assert prediction.analysis_status == "pending"
        assert prediction.has_media is False
        assert prediction.mentions_count == 0

    def test_model_with_analysis_scores(self):
        """Test model with enhanced analysis scores."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="completed",
            engagement_score=0.75,
            viral_score=0.82,
            sentiment_score=0.65,
            urgency_score=0.90
        )
        
        assert prediction.engagement_score == 0.75
        assert prediction.viral_score == 0.82
        assert prediction.sentiment_score == 0.65
        assert prediction.urgency_score == 0.90

    def test_model_with_content_analysis(self):
        """Test model with content analysis data."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="completed",
            has_media=True,
            mentions_count=3,
            hashtags_count=2,
            content_length=280
        )
        
        assert prediction.has_media is True
        assert prediction.mentions_count == 3
        assert prediction.hashtags_count == 2
        assert prediction.content_length == 280

    def test_model_with_engagement_at_analysis(self):
        """Test model with engagement metrics at analysis time."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="completed",
            replies_at_analysis=100,
            reblogs_at_analysis=500,
            favourites_at_analysis=1000,
            upvotes_at_analysis=800
        )
        
        assert prediction.replies_at_analysis == 100
        assert prediction.reblogs_at_analysis == 500
        assert prediction.favourites_at_analysis == 1000
        assert prediction.upvotes_at_analysis == 800

    def test_model_with_llm_metadata(self):
        """Test model with LLM provider metadata."""
        analysis_time = datetime(2024, 1, 15, 12, 0, 0)
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="completed",
            llm_provider="openai",
            llm_model="gpt-4",
            analysis_timestamp=analysis_time
        )
        
        assert prediction.llm_provider == "openai"
        assert prediction.llm_model == "gpt-4"
        assert prediction.analysis_timestamp == analysis_time

    def test_model_bypassed_status(self):
        """Test model with bypassed analysis status."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="bypassed",
            analysis_comment="No text content",
            confidence=None  # Nullable for bypassed posts
        )
        
        assert prediction.analysis_status == "bypassed"
        assert prediction.analysis_comment == "No text content"
        assert prediction.confidence is None

    def test_model_error_status(self):
        """Test model with error status."""
        prediction = Prediction(
            shitpost_id="123",
            analysis_status="error",
            analysis_comment="API timeout"
        )
        
        assert prediction.analysis_status == "error"
        assert prediction.analysis_comment == "API timeout"

    def test_model_repr(self):
        """Test model string representation."""
        prediction = Prediction(
            shitpost_id="123",
            assets=["TSLA"],
            confidence=0.85,
            analysis_status="completed"
        )
        
        repr_str = repr(prediction)
        assert "Prediction" in repr_str
        assert "0.85" in repr_str or "confidence" in repr_str.lower()

    def test_table_name(self):
        """Test correct table name."""
        assert Prediction.__tablename__ == "predictions"

    def test_foreign_key_constraint(self):
        """Test that shitpost_id has foreign key constraint."""
        mapper = inspect(Prediction)
        shitpost_id_col = mapper.columns['shitpost_id']
        assert shitpost_id_col.foreign_keys is not None
        assert len(shitpost_id_col.foreign_keys) > 0


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_shitpost_to_dict(self):
        """Test converting TruthSocialShitpost to dictionary."""
        shitpost = TruthSocialShitpost(
            shitpost_id="123",
            content="Test content",
            username="testuser",
            timestamp=datetime(2024, 1, 15, 12, 0, 0)
        )
        
        result = shitpost_to_dict(shitpost)
        
        assert isinstance(result, dict)
        assert result['shitpost_id'] == "123"
        assert result['content'] == "Test content"
        assert result['username'] == "testuser"

    def test_prediction_to_dict(self):
        """Test converting Prediction to dictionary."""
        prediction = Prediction(
            shitpost_id="123",
            assets=["TSLA"],
            confidence=0.85,
            analysis_status="completed"
        )
        
        result = prediction_to_dict(prediction)
        
        assert isinstance(result, dict)
        assert result['shitpost_id'] == "123"
        assert result['assets'] == ["TSLA"]
        assert result['confidence'] == 0.85
        assert result['analysis_status'] == "completed"



class TestModelRelationships:
    """Test model relationships."""

    def test_truth_social_shitpost_has_predictions_relationship(self):
        """Test TruthSocialShitpost has predictions relationship."""
        mapper = inspect(TruthSocialShitpost)
        relationships = mapper.relationships
        assert 'predictions' in relationships.keys()

    def test_prediction_has_shitpost_relationship(self):
        """Test Prediction has shitpost relationship."""
        mapper = inspect(Prediction)
        relationships = mapper.relationships
        assert 'shitpost' in relationships.keys()



class TestModelInheritance:
    """Test model inheritance from base classes."""

    def test_truth_social_shitpost_inherits_mixins(self):
        """Test TruthSocialShitpost inherits from Base, IDMixin, TimestampMixin."""
        assert issubclass(TruthSocialShitpost, Base)
        # Check for IDMixin fields
        mapper = inspect(TruthSocialShitpost)
        assert 'id' in mapper.columns.keys()
        # Check for TimestampMixin fields
        assert 'created_at' in mapper.columns.keys()
        assert 'updated_at' in mapper.columns.keys()

    def test_prediction_inherits_mixins(self):
        """Test Prediction inherits from Base, IDMixin, TimestampMixin."""
        assert issubclass(Prediction, Base)
        mapper = inspect(Prediction)
        assert 'id' in mapper.columns.keys()
        assert 'created_at' in mapper.columns.keys()
        assert 'updated_at' in mapper.columns.keys()


