"""
Notification Models
SQLAlchemy models for the notifications subsystem.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from shit.db.data_models import Base, TimestampMixin, IDMixin


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


class AlertFollowup(Base, IDMixin, TimestampMixin):
    """Tracks follow-up messages for sent alerts at T+1h, T+1d, T+7d.

    Each row tracks one (prediction, subscriber) pair. The follow-up
    checker runs every 5 minutes and processes rows where next_check_at <= now.
    """

    __tablename__ = "alert_followups"
    __table_args__ = (
        UniqueConstraint(
            "prediction_id", "chat_id", name="uq_alert_followup_pred_chat"
        ),
    )

    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    chat_id = Column(String(50), nullable=False, index=True)

    # Follow-up state: None = not yet due, False = abandoned, True = sent
    sent_1h = Column(Boolean, nullable=True, default=None)
    sent_1h_at = Column(DateTime, nullable=True)
    sent_1d = Column(Boolean, nullable=True, default=None)
    sent_1d_at = Column(DateTime, nullable=True)
    sent_7d = Column(Boolean, nullable=True, default=None)
    sent_7d_at = Column(DateTime, nullable=True)

    # Timing
    original_alert_sent_at = Column(DateTime, nullable=False)
    next_check_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return (
            f"<AlertFollowup(prediction_id={self.prediction_id}, "
            f"chat_id={self.chat_id}, "
            f"1h={self.sent_1h}, 1d={self.sent_1d}, 7d={self.sent_7d})>"
        )
