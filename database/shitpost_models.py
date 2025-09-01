"""
Shitpost Database Models
SQLAlchemy models for shitposts, predictions, and related data.
Note: Field names match Truth Social API structure for direct mapping.
"""

from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TruthSocialShitpost(Base):
    """Model for Truth Social shitposts. Field names match API structure."""
    
    __tablename__ = "truth_social_shitposts"
    
    id = Column(Integer, primary_key=True, index=True)
    shitpost_id = Column(String(255), unique=True, index=True)  # Original Truth Social post ID
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
    
    # Content metadata (legacy fields)
    original_length = Column(Integer, default=0)
    cleaned_length = Column(Integer, default=0)
    hashtags = Column(JSON, default=list)  # Legacy field for backward compatibility
    
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    predictions = relationship("Prediction", back_populates="shitpost")
    
    def __repr__(self):
        return f"<TruthSocialShitpost(id={self.id}, username='{self.username}', content='{self.content[:50]}...')>"


class Prediction(Base):
    """Model for LLM predictions/analysis of shitposts."""
    
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("truth_social_shitposts.id"), nullable=False)  # Foreign key to TruthSocialShitpost
    
    # Analysis results
    assets = Column(JSON, default=list)  # List of asset tickers
    market_impact = Column(JSON, default=dict)  # Dict of asset -> sentiment
    confidence = Column(Float, nullable=False)  # Confidence score 0.0-1.0
    thesis = Column(Text, nullable=True)  # Investment thesis
    
    # Enhanced analysis using Truth Social data
    engagement_score = Column(Float, nullable=True)  # Calculated from engagement metrics
    viral_score = Column(Float, nullable=True)  # Calculated from reblogs/favourites ratio
    sentiment_score = Column(Float, nullable=True)  # Sentiment analysis score
    urgency_score = Column(Float, nullable=True)  # Urgency indicator from content analysis
    
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shitpost = relationship("TruthSocialShitpost", back_populates="predictions")
    market_movements = relationship("MarketMovement", back_populates="prediction")
    
    def __repr__(self):
        return f"<Prediction(id={self.id}, confidence={self.confidence}, assets={self.assets})>"


class MarketMovement(Base):
    """Model for tracking actual market movements after shitpost predictions."""
    
    __tablename__ = "market_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)  # Foreign key to Prediction
    
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    prediction = relationship("Prediction", back_populates="market_movements")
    
    def __repr__(self):
        return f"<MarketMovement(id={self.id}, asset='{self.asset}', movement_24h={self.movement_24h}%)>"


class Subscriber(Base):
    """Model for SMS alert subscribers."""
    
    __tablename__ = "subscribers"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Preferences
    is_active = Column(Boolean, default=True)
    confidence_threshold = Column(Float, default=0.7)  # Minimum confidence for alerts
    alert_frequency = Column(String(20), default="all")  # all, high_confidence, daily_summary
    
    # Rate limiting
    last_alert_sent = Column(DateTime, nullable=True)
    alerts_sent_today = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Subscriber(id={self.id}, phone='{self.phone_number}', active={self.is_active})>"


class LLMFeedback(Base):
    """Model for storing LLM performance feedback on shitpost analysis."""
    
    __tablename__ = "llm_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)  # Foreign key to Prediction
    
    # Feedback data
    feedback_type = Column(String(50), nullable=False)  # accuracy, relevance, confidence
    feedback_score = Column(Float, nullable=False)  # 0.0-1.0 score
    feedback_notes = Column(Text, nullable=True)  # Human feedback notes
    
    # Metadata
    feedback_source = Column(String(50), default="system")  # system, human, automated
    feedback_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<LLMFeedback(id={self.id}, type='{self.feedback_type}', score={self.feedback_score})>"


# Utility functions for working with models
def shitpost_to_dict(shitpost: TruthSocialShitpost) -> Dict[str, Any]:
    """Convert TruthSocialShitpost to dictionary."""
    return {
        'id': shitpost.id,
        'shitpost_id': shitpost.shitpost_id,
        'content': shitpost.content,
        'timestamp': shitpost.timestamp.isoformat() if shitpost.timestamp else None,
        'username': shitpost.username,
        'platform': shitpost.platform,
        'original_length': shitpost.original_length,
        'cleaned_length': shitpost.cleaned_length,
        'has_media': shitpost.has_media,
        'mentions': shitpost.mentions,
        'hashtags': shitpost.hashtags,
        'created_at': shitpost.created_at.isoformat() if shitpost.created_at else None
    }


def prediction_to_dict(prediction: Prediction) -> Dict[str, Any]:
    """Convert Prediction to dictionary."""
    return {
        'id': prediction.id,
        'post_id': prediction.post_id,
        'assets': prediction.assets,
        'market_impact': prediction.market_impact,
        'confidence': prediction.confidence,
        'thesis': prediction.thesis,
        'llm_provider': prediction.llm_provider,
        'llm_model': prediction.llm_model,
        'analysis_timestamp': prediction.analysis_timestamp.isoformat() if prediction.analysis_timestamp else None,
        'created_at': prediction.created_at.isoformat() if prediction.created_at else None
    }


def market_movement_to_dict(movement: MarketMovement) -> Dict[str, Any]:
    """Convert MarketMovement to dictionary."""
    return {
        'id': movement.id,
        'prediction_id': movement.prediction_id,
        'asset': movement.asset,
        'price_at_prediction': movement.price_at_prediction,
        'price_after_24h': movement.price_after_24h,
        'price_after_72h': movement.price_after_72h,
        'movement_24h': movement.movement_24h,
        'movement_72h': movement.movement_72h,
        'prediction_correct_24h': movement.prediction_correct_24h,
        'prediction_correct_72h': movement.prediction_correct_72h,
        'created_at': movement.created_at.isoformat() if movement.created_at else None
    }
