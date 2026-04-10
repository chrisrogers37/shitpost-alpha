"""
Domain-Specific Database Models
SQLAlchemy models for shitposts, predictions, and related data.
Uses generic Base class from shit/db/data_models.
Note: Field names match Truth Social API structure for direct mapping.
"""

from datetime import datetime
from typing import Dict, Any
from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    DateTime,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from shit.db.data_models import Base, TimestampMixin, IDMixin, model_to_dict


class TruthSocialShitpost(Base, IDMixin, TimestampMixin):
    """Model for Truth Social shitposts. Field names match API structure."""

    __tablename__ = "truth_social_shitposts"
    shitpost_id = Column(
        String(255), unique=True, index=True
    )  # Original Truth Social post ID
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    username = Column(String(100), nullable=False)
    platform = Column(String(50), default="truth_social")

    # Post metadata from API (keeping original field names)
    text = Column(Text, nullable=True)  # Plain text content
    language = Column(String(10), nullable=True)  # Language code (en, etc.)
    visibility = Column(String(20), default="public")  # public, private, etc.
    sensitive = Column(Boolean, default=False)
    spoiler_text = Column(String(500), nullable=True)
    uri = Column(String(500), nullable=True)  # Truth Social URI
    url = Column(String(500), nullable=True)  # Public URL

    # Engagement metrics (API field names)
    replies_count = Column(Integer, default=0)
    reblogs_count = Column(Integer, default=0)
    favourites_count = Column(Integer, default=0)
    upvotes_count = Column(Integer, default=0)
    downvotes_count = Column(Integer, default=0)

    # Account information (API field names)
    account_id = Column(String(255), nullable=True)  # Account ID from API
    account_display_name = Column(String(200), nullable=True)  # Display name
    account_followers_count = Column(Integer, default=0)
    account_following_count = Column(Integer, default=0)
    account_statuses_count = Column(Integer, default=0)
    account_verified = Column(Boolean, default=False)
    account_website = Column(String(500), nullable=True)

    # Media and attachments (API field names)
    has_media = Column(Boolean, default=False)
    media_attachments = Column(JSON, default=list)  # Full media attachment data
    mentions = Column(JSON, default=list)  # List of @mentions
    tags = Column(JSON, default=list)  # List of hashtags/tags

    # Additional API fields (keeping original names)
    in_reply_to_id = Column(String(255), nullable=True)
    quote_id = Column(String(255), nullable=True)
    in_reply_to_account_id = Column(String(255), nullable=True)
    card = Column(JSON, nullable=True)  # Link preview card data
    group = Column(JSON, nullable=True)  # Group data if applicable
    quote = Column(JSON, nullable=True)  # Quoted post data
    in_reply_to = Column(JSON, nullable=True)  # Reply data
    reblog = Column(JSON, nullable=True)  # Reblog data
    sponsored = Column(Boolean, default=False)
    reaction = Column(JSON, nullable=True)
    favourited = Column(Boolean, default=False)
    reblogged = Column(Boolean, default=False)
    muted = Column(Boolean, default=False)
    pinned = Column(Boolean, default=False)
    bookmarked = Column(Boolean, default=False)
    poll = Column(JSON, nullable=True)
    emojis = Column(JSON, default=list)
    votable = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)
    version = Column(String(10), nullable=True)
    editable = Column(Boolean, default=False)
    title = Column(String(500), nullable=True)

    # Raw API data for debugging/analysis
    raw_api_data = Column(JSON, nullable=True)  # Store complete API response

    # Relationships
    predictions = relationship("Prediction", back_populates="shitpost")

    def __repr__(self):
        return f"<TruthSocialShitpost(id={self.id}, username='{self.username}', content='{self.content[:50]}...')>"


class Prediction(Base, IDMixin, TimestampMixin):
    """Model for LLM predictions/analysis of shitposts."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "analysis_status IN ('completed', 'bypassed', 'error', 'pending')",
            name="ck_predictions_analysis_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_predictions_confidence_range",
        ),
        CheckConstraint(
            "shitpost_id IS NOT NULL OR signal_id IS NOT NULL",
            name="ck_predictions_has_content_ref",
        ),
    )

    # Legacy FK -- nullable now, will be removed after full migration
    shitpost_id = Column(
        String(255), ForeignKey("truth_social_shitposts.shitpost_id"), nullable=True
    )
    # New FK -- points to the source-agnostic signals table
    signal_id = Column(
        String(255), ForeignKey("signals.signal_id"), nullable=True
    )

    # Denormalized source post timestamp (avoids N+1 loading shitpost/signal)
    post_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Analysis results
    assets = Column(JSON, default=list)  # List of asset tickers
    market_impact = Column(JSON, default=dict)  # Dict of asset -> sentiment
    confidence = Column(
        Float, nullable=True
    )  # Confidence score 0.0-1.0 (nullable for bypassed posts)
    calibrated_confidence = Column(
        Float, nullable=True
    )  # Empirically calibrated confidence from calibration curve
    thesis = Column(Text, nullable=True)  # Investment thesis

    # Analysis metadata
    analysis_status = Column(
        String(50), nullable=False, default="pending"
    )  # 'completed', 'bypassed', 'error'
    analysis_comment = Column(String(255), nullable=True)  # Reason for bypass/error

    # Enhanced analysis using Truth Social data
    engagement_score = Column(
        Float, nullable=True
    )  # Calculated from engagement metrics
    viral_score = Column(
        Float, nullable=True
    )  # Calculated from reblogs/favourites ratio
    sentiment_score = Column(Float, nullable=True)  # Sentiment analysis score
    urgency_score = Column(
        Float, nullable=True
    )  # Urgency indicator from content analysis

    # Content analysis
    has_media = Column(Boolean, default=False)  # Whether shitpost has media
    mentions_count = Column(Integer, default=0)  # Number of @mentions
    hashtags_count = Column(Integer, default=0)  # Number of hashtags
    content_length = Column(Integer, default=0)  # Content length

    # Engagement metrics at analysis time
    replies_at_analysis = Column(Integer, default=0)
    reblogs_at_analysis = Column(Integer, default=0)
    favourites_at_analysis = Column(Integer, default=0)
    upvotes_at_analysis = Column(Integer, default=0)

    # LLM metadata
    llm_provider = Column(String(50), nullable=True)  # openai, anthropic, etc.
    llm_model = Column(String(100), nullable=True)  # gpt-4, claude-3, etc.
    analysis_timestamp = Column(DateTime, nullable=True)

    # Relationships
    shitpost = relationship("TruthSocialShitpost", back_populates="predictions")
    signal = relationship("Signal", back_populates="predictions", foreign_keys=[signal_id])
    @property
    def content_id(self) -> str:
        """Return the signal or shitpost ID, whichever is set."""
        return self.signal_id or self.shitpost_id

    def __repr__(self):
        return f"<Prediction(id={self.id}, confidence={self.confidence}, assets={self.assets})>"


# TelegramSubscription moved to notifications/models.py — re-export for compatibility
from notifications.models import TelegramSubscription  # noqa: F401


# Domain-specific utility functions (using generic model_to_dict)
def shitpost_to_dict(shitpost: TruthSocialShitpost) -> Dict[str, Any]:
    """Convert TruthSocialShitpost to dictionary."""
    return model_to_dict(shitpost)


def prediction_to_dict(prediction: Prediction) -> Dict[str, Any]:
    """Convert Prediction to dictionary."""
    return model_to_dict(prediction)


# Indexes for efficient querying on predictions table
# PostgreSQL does NOT auto-index FK columns — only the referenced key gets one
Index("idx_predictions_shitpost_id", Prediction.shitpost_id)
Index("idx_predictions_signal_id", Prediction.signal_id)
Index("idx_predictions_analysis_status", Prediction.analysis_status)
Index("idx_predictions_created_at", Prediction.created_at)


