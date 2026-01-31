"""
Domain-Specific Database Models
SQLAlchemy models for shitposts, predictions, and related data.
Uses generic Base class from shit/db/data_models.
Note: Field names match Truth Social API structure for direct mapping.
"""

from datetime import datetime
from typing import Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    JSON,
    ForeignKey,
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
    shitpost_id = Column(
        String(255), ForeignKey("truth_social_shitposts.shitpost_id"), nullable=False
    )  # Foreign key to TruthSocialShitpost.shitpost_id

    # Analysis results
    assets = Column(JSON, default=list)  # List of asset tickers
    market_impact = Column(JSON, default=dict)  # Dict of asset -> sentiment
    confidence = Column(
        Float, nullable=True
    )  # Confidence score 0.0-1.0 (nullable for bypassed posts)
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
    market_movements = relationship("MarketMovement", back_populates="prediction")

    def __repr__(self):
        return f"<Prediction(id={self.id}, confidence={self.confidence}, assets={self.assets})>"


class MarketMovement(Base, IDMixin, TimestampMixin):
    """Model for tracking actual market movements after shitpost predictions."""

    __tablename__ = "market_movements"
    prediction_id = Column(
        Integer, ForeignKey("predictions.id"), nullable=False
    )  # Foreign key to Prediction

    # Market data
    asset = Column(String(20), nullable=False)  # Ticker symbol
    price_at_prediction = Column(Float, nullable=True)  # Price when prediction was made
    price_after_24h = Column(Float, nullable=True)  # Price 24 hours later
    price_after_72h = Column(Float, nullable=True)  # Price 72 hours later

    # Movement calculations
    movement_24h = Column(Float, nullable=True)  # Percentage change
    movement_72h = Column(Float, nullable=True)  # Percentage change

    # Prediction accuracy
    prediction_correct_24h = Column(Boolean, nullable=True)  # Was prediction correct?
    prediction_correct_72h = Column(Boolean, nullable=True)  # Was prediction correct?

    # Relationships
    prediction = relationship("Prediction", back_populates="market_movements")

    def __repr__(self):
        return f"<MarketMovement(id={self.id}, asset='{self.asset}', movement_24h={self.movement_24h}%)>"


class Subscriber(Base, IDMixin, TimestampMixin):
    """Model for SMS alert subscribers."""

    __tablename__ = "subscribers"
    phone_number = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # Preferences
    is_active = Column(Boolean, default=True)
    confidence_threshold = Column(Float, default=0.7)  # Minimum confidence for alerts
    alert_frequency = Column(
        String(20), default="all"
    )  # all, high_confidence, daily_summary

    # Rate limiting
    last_alert_sent = Column(DateTime, nullable=True)
    alerts_sent_today = Column(Integer, default=0)

    def __repr__(self):
        return f"<Subscriber(id={self.id}, phone='{self.phone_number}', active={self.is_active})>"


class LLMFeedback(Base, IDMixin, TimestampMixin):
    """Model for storing LLM performance feedback on shitpost analysis."""

    __tablename__ = "llm_feedback"
    prediction_id = Column(
        Integer, ForeignKey("predictions.id"), nullable=False
    )  # Foreign key to Prediction

    # Feedback data
    feedback_type = Column(
        String(50), nullable=False
    )  # accuracy, relevance, confidence
    feedback_score = Column(Float, nullable=False)  # 0.0-1.0 score
    feedback_notes = Column(Text, nullable=True)  # Human feedback notes

    # Metadata
    feedback_source = Column(String(50), default="system")  # system, human, automated
    feedback_timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LLMFeedback(id={self.id}, type='{self.feedback_type}', score={self.feedback_score})>"


class TelegramSubscription(Base, IDMixin, TimestampMixin):
    """
    Model for Telegram alert subscriptions.

    Supports multi-tenant architecture where one bot serves many users/groups.
    Each subscription has its own alert preferences.
    """

    __tablename__ = "telegram_subscriptions"

    # Telegram identifiers
    chat_id = Column(
        String(50), unique=True, nullable=False, index=True
    )  # Telegram chat ID
    chat_type = Column(
        String(20), nullable=False, default="private"
    )  # private, group, supergroup, channel

    # User/group info (captured from Telegram API)
    username = Column(String(100), nullable=True)  # @username (optional)
    first_name = Column(String(100), nullable=True)  # User's first name
    last_name = Column(String(100), nullable=True)  # User's last name
    title = Column(
        String(200), nullable=True
    )  # Group/channel title (for non-private chats)

    # Subscription status
    is_active = Column(Boolean, default=True, index=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    unsubscribed_at = Column(DateTime, nullable=True)

    # Alert preferences (stored as JSON for flexibility)
    alert_preferences = Column(
        JSON,
        default=lambda: {
            "min_confidence": 0.7,
            "assets_of_interest": [],  # Empty = all assets
            "sentiment_filter": "all",  # all, bullish, bearish, neutral
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    )

    # Rate limiting and tracking
    last_alert_at = Column(DateTime, nullable=True)
    alerts_sent_count = Column(Integer, default=0)
    last_interaction_at = Column(
        DateTime, default=datetime.utcnow
    )  # Last command received

    # Error tracking
    consecutive_errors = Column(Integer, default=0)  # For auto-disabling broken chats
    last_error = Column(Text, nullable=True)

    def __repr__(self):
        name = self.username or self.first_name or self.title or self.chat_id
        return f"<TelegramSubscription(chat_id={self.chat_id}, name='{name}', active={self.is_active})>"

    def get_display_name(self) -> str:
        """Get a human-readable name for this subscription."""
        if self.chat_type == "private":
            if self.username:
                return f"@{self.username}"
            return self.first_name or f"User {self.chat_id}"
        return self.title or f"Chat {self.chat_id}"


# Domain-specific utility functions (using generic model_to_dict)
def shitpost_to_dict(shitpost: TruthSocialShitpost) -> Dict[str, Any]:
    """Convert TruthSocialShitpost to dictionary."""
    return model_to_dict(shitpost)


def prediction_to_dict(prediction: Prediction) -> Dict[str, Any]:
    """Convert Prediction to dictionary."""
    return model_to_dict(prediction)


def market_movement_to_dict(movement: MarketMovement) -> Dict[str, Any]:
    """Convert MarketMovement to dictionary."""
    return model_to_dict(movement)
