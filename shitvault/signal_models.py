"""
Source-Agnostic Signal Model
SQLAlchemy model for signals from ANY social media or news source.
Platform-specific data is stored in a JSON blob.
"""

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
    Index,
)
from sqlalchemy.orm import relationship

from shit.db.data_models import Base, TimestampMixin, IDMixin, model_to_dict


class Signal(Base, IDMixin, TimestampMixin):
    """
    Source-agnostic signal model.

    Represents a content signal from ANY platform (Truth Social, Twitter/X,
    RSS, news feeds, etc.). Platform-specific fields are stored in the
    `platform_data` JSON column.

    Universal fields capture the data every downstream consumer needs:
    text, author, timestamp, source, and normalized engagement metrics.
    """

    __tablename__ = "signals"

    # --- Universal Identifiers ---
    signal_id = Column(String(255), unique=True, index=True, nullable=False)
    source = Column(String(50), nullable=False, index=True)
    source_url = Column(String(1000), nullable=True)

    # --- Universal Content ---
    text = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    language = Column(String(10), nullable=True)

    # --- Universal Author ---
    author_id = Column(String(255), nullable=True)
    author_username = Column(String(200), nullable=False)
    author_display_name = Column(String(200), nullable=True)
    author_verified = Column(Boolean, default=False)
    author_followers = Column(Integer, default=0)

    # --- Universal Timestamps ---
    published_at = Column(DateTime, nullable=False, index=True)

    # --- Normalized Engagement (source-agnostic names) ---
    likes_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    replies_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)

    # --- Content Flags ---
    has_media = Column(Boolean, default=False)
    is_repost = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)
    is_quote = Column(Boolean, default=False)

    # --- Platform-Specific Data (JSON blob) ---
    platform_data = Column(JSON, default=dict)

    # --- Raw API Response ---
    raw_api_data = Column(JSON, nullable=True)

    # --- Relationships ---
    predictions = relationship(
        "Prediction", back_populates="signal", foreign_keys="Prediction.signal_id"
    )

    # --- Indexes ---
    __table_args__ = (
        Index("ix_signals_source_published", "source", "published_at"),
        Index("ix_signals_author", "author_username"),
    )

    def __repr__(self):
        text_preview = (self.text or "")[:50]
        return f"<Signal(id={self.id}, source='{self.source}', author='{self.author_username}', text='{text_preview}...')>"

    @property
    def total_engagement(self) -> int:
        """Sum of all engagement metrics."""
        return (
            (self.likes_count or 0)
            + (self.shares_count or 0)
            + (self.replies_count or 0)
        )

    @property
    def engagement_rate(self) -> float:
        """Engagement rate relative to author followers."""
        if not self.author_followers or self.author_followers == 0:
            return 0.0
        return self.total_engagement / self.author_followers


def signal_to_dict(signal: Signal) -> Dict[str, Any]:
    """Convert Signal to dictionary."""
    return model_to_dict(signal)
