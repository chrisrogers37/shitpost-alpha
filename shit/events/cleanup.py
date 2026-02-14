"""
Event Cleanup

Prune old completed and dead-letter events from the queue.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import and_

from shit.db.sync_session import get_session
from shit.events.models import Event
from shit.logging import get_service_logger

logger = get_service_logger("event_cleanup")


def cleanup_completed_events(older_than_days: int = 7) -> int:
    """Delete completed events older than the given threshold.

    Args:
        older_than_days: Delete events completed more than this many days ago.

    Returns:
        Number of events deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    with get_session() as session:
        count = (
            session.query(Event)
            .filter(
                and_(
                    Event.status == "completed",
                    Event.completed_at < cutoff,
                )
            )
            .delete(synchronize_session="fetch")
        )

    logger.info(
        f"Cleaned up {count} completed events older than {older_than_days} days",
        extra={"deleted": count, "cutoff_days": older_than_days},
    )
    return count


def cleanup_dead_letter_events(older_than_days: int = 30) -> int:
    """Delete dead-letter events older than the given threshold.

    Dead-letter events are kept longer for debugging purposes.

    Args:
        older_than_days: Delete events dead-lettered more than this many days ago.

    Returns:
        Number of events deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    with get_session() as session:
        count = (
            session.query(Event)
            .filter(
                and_(
                    Event.status == "dead_letter",
                    Event.updated_at < cutoff,
                )
            )
            .delete(synchronize_session="fetch")
        )

    logger.info(
        f"Cleaned up {count} dead-letter events older than {older_than_days} days",
        extra={"deleted": count, "cutoff_days": older_than_days},
    )
    return count


def retry_dead_letter_events(
    event_type: str | None = None,
    consumer_group: str | None = None,
    max_events: int = 100,
) -> int:
    """Re-queue dead-letter events for retry.

    Resets status to 'pending', clears error/claim fields, and resets
    attempt counter. Useful for manual recovery after fixing a bug.

    Args:
        event_type: Only retry events of this type (None = all).
        consumer_group: Only retry events for this consumer (None = all).
        max_events: Maximum number of events to retry.

    Returns:
        Number of events re-queued.
    """
    with get_session() as session:
        query = session.query(Event).filter(Event.status == "dead_letter")

        if event_type:
            query = query.filter(Event.event_type == event_type)
        if consumer_group:
            query = query.filter(Event.consumer_group == consumer_group)

        events = query.limit(max_events).all()

        for event in events:
            event.status = "pending"
            event.attempt = 0
            event.error = None
            event.claimed_by = None
            event.claimed_at = None
            event.next_retry_at = None

        count = len(events)

    logger.info(
        f"Re-queued {count} dead-letter events for retry",
        extra={
            "count": count,
            "event_type": event_type,
            "consumer_group": consumer_group,
        },
    )
    return count
