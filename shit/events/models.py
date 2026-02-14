"""
Event Queue Model

SQLAlchemy model for the PostgreSQL-backed event queue.
Supports fan-out (write-time duplication), claim-based processing,
exponential backoff retry, and dead-letter handling.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Index

from shit.db.data_models import Base, IDMixin, TimestampMixin


class Event(Base, IDMixin, TimestampMixin):
    """A single event in the queue.

    Fan-out strategy: ``emit_event()`` writes one row per consumer group.
    Each consumer only sees rows matching its ``consumer_group``.

    Lifecycle::

        pending -> claimed -> completed
                           -> failed -> (retry as pending)
                                     -> dead_letter (after max_attempts)
    """

    __tablename__ = "events"

    # Event identity
    event_type = Column(String(100), nullable=False, index=True)
    consumer_group = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)

    # Processing state
    status = Column(String(20), nullable=False, default="pending", index=True)
    claimed_by = Column(String(100), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Retry
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime, nullable=True)

    # Provenance
    source_service = Column(String(100), nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)

    __table_args__ = (
        # Primary query path: claim pending events for a consumer group
        Index(
            "ix_events_claimable",
            "consumer_group",
            "status",
            "next_retry_at",
        ),
        # Debugging: find events by type + status
        Index("ix_events_type_status", "event_type", "status"),
        # Cleanup: prune old completed events
        Index("ix_events_completed_at", "completed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, type='{self.event_type}', "
            f"consumer='{self.consumer_group}', status='{self.status}')>"
        )

    def mark_claimed(self, worker_id: str) -> None:
        """Mark this event as claimed by a worker."""
        self.status = "claimed"
        self.claimed_by = worker_id
        self.claimed_at = datetime.now(timezone.utc)
        self.attempt += 1

    def mark_completed(self, result: dict | None = None) -> None:
        """Mark this event as successfully processed."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        self.result = result

    def mark_failed(self, error_message: str) -> None:
        """Mark this event as failed and schedule retry or dead-letter."""
        if self.attempt >= self.max_attempts:
            self.status = "dead_letter"
            self.error = error_message
        else:
            self.status = "pending"
            self.error = error_message
            # Exponential backoff: 30s * 2^attempt, capped at 1 hour
            backoff_seconds = min(30 * (2 ** self.attempt), 3600)
            self.next_retry_at = datetime.now(timezone.utc).__class__.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + backoff_seconds,
                tz=timezone.utc,
            )
