"""
Event System Package

PostgreSQL-backed event queue for decoupling pipeline services.
Each service produces and consumes events independently, enabling
fan-out, retry with backoff, and dead-letter handling.
"""

from shit.events.models import Event
from shit.events.event_types import EventType, CONSUMER_GROUPS
from shit.events.producer import emit_event
from shit.events.worker import EventWorker

__all__ = [
    "Event",
    "EventType",
    "CONSUMER_GROUPS",
    "emit_event",
    "EventWorker",
]
