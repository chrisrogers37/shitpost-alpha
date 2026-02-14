"""
Event Producer

Emits events to the PostgreSQL-backed queue with write-time fan-out.
Each call creates one row per consumer group defined in CONSUMER_GROUPS.
"""

import uuid
from typing import Optional

from shit.db.sync_session import get_session
from shit.events.models import Event
from shit.events.event_types import CONSUMER_GROUPS
from shit.logging import get_service_logger

logger = get_service_logger("event_producer")


def emit_event(
    event_type: str,
    payload: dict,
    source_service: str,
    correlation_id: Optional[str] = None,
    max_attempts: int = 3,
) -> list[int]:
    """Emit an event to all registered consumer groups.

    Creates one ``Event`` row per consumer group (write-time fan-out).
    Uses a synchronous session so producers don't need async context.

    Args:
        event_type: Event type constant from EventType.
        payload: Event-specific data dict.
        source_service: Name of the service emitting the event.
        correlation_id: Optional ID to link related events across the chain.
            If None, a new UUID is generated.
        max_attempts: Max retry attempts before dead-lettering (default 3).

    Returns:
        List of created event IDs.

    Raises:
        ValueError: If event_type has no registered consumer groups.
    """
    consumers = CONSUMER_GROUPS.get(event_type)
    if consumers is None:
        raise ValueError(
            f"Unknown event type: {event_type}. "
            f"Registered types: {list(CONSUMER_GROUPS.keys())}"
        )

    if not consumers:
        logger.debug(
            f"Event {event_type} has no consumers, skipping emission",
            extra={"event_type": event_type, "source": source_service},
        )
        return []

    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    event_ids: list[int] = []

    with get_session() as session:
        for consumer_group in consumers:
            event = Event(
                event_type=event_type,
                consumer_group=consumer_group,
                payload=payload,
                status="pending",
                source_service=source_service,
                correlation_id=correlation_id,
                max_attempts=max_attempts,
            )
            session.add(event)
            session.flush()  # Assign ID before commit
            event_ids.append(event.id)

        # Session commits on context manager exit

    logger.info(
        f"Emitted {event_type} to {len(consumers)} consumer(s): "
        f"{', '.join(consumers)}",
        extra={
            "event_type": event_type,
            "consumers": consumers,
            "correlation_id": correlation_id,
            "source": source_service,
            "event_ids": event_ids,
        },
    )

    return event_ids
