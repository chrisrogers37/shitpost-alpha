"""
Event Worker Base Class

Provides a polling loop that claims and processes events from the queue.
Consumers subclass this and implement ``process_event()``.

Supports two modes:
- ``run()``: Persistent polling loop with graceful shutdown (SIGTERM/SIGINT).
- ``run_once()``: Drain all pending events and exit (for Railway cron).
"""

import abc
import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_

from shit.db.sync_session import get_session, SessionLocal
from shit.events.models import Event
from shit.logging import get_service_logger


class EventWorker(abc.ABC):
    """Base class for event consumers.

    Subclasses must implement:
        - ``consumer_group``: property returning the consumer group name.
        - ``process_event(event_type, payload)``: process a single event.

    Usage::

        class MyWorker(EventWorker):
            consumer_group = "my_service"

            def process_event(self, event_type, payload):
                # do work
                return {"processed": True}

        worker = MyWorker()
        worker.run_once()  # for cron
        # or
        worker.run()  # for persistent
    """

    #: Consumer group name — set in subclass
    consumer_group: str = ""

    def __init__(
        self,
        poll_interval: float = 2.0,
        batch_size: int = 10,
        worker_id: Optional[str] = None,
    ):
        """Initialize the worker.

        Args:
            poll_interval: Seconds between poll cycles in persistent mode.
            batch_size: Max events to claim per poll cycle.
            worker_id: Unique worker identifier. Auto-generated if None.
        """
        if not self.consumer_group:
            raise ValueError("consumer_group must be set in subclass")

        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.worker_id = worker_id or f"{self.consumer_group}-{uuid.uuid4().hex[:8]}"
        self._shutdown = False
        self.logger = get_service_logger(f"worker.{self.consumer_group}")

    @abc.abstractmethod
    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a single event.

        Args:
            event_type: The event type string.
            payload: The event payload dict.

        Returns:
            Result dict to store on the event (can be empty).

        Raises:
            Exception: Any exception marks the event as failed.
        """
        ...

    def run(self) -> None:
        """Run the persistent polling loop. Handles SIGTERM/SIGINT."""
        self._setup_signal_handlers()
        self.logger.info(
            f"Worker {self.worker_id} starting persistent loop "
            f"(group={self.consumer_group}, interval={self.poll_interval}s)"
        )

        while not self._shutdown:
            try:
                processed = self._poll_and_process()
                if processed == 0:
                    time.sleep(self.poll_interval)
            except Exception:
                self.logger.error("Unexpected error in poll loop", exc_info=True)
                time.sleep(self.poll_interval)

        self.logger.info(f"Worker {self.worker_id} shut down gracefully")

    def run_once(self) -> int:
        """Drain all pending events and exit.

        Returns:
            Total number of events processed.
        """
        self.logger.info(
            f"Worker {self.worker_id} draining queue "
            f"(group={self.consumer_group})"
        )

        total = 0
        while True:
            processed = self._poll_and_process()
            total += processed
            if processed == 0:
                break

        self.logger.info(
            f"Worker {self.worker_id} drained {total} events",
            extra={"total_processed": total},
        )
        return total

    def _poll_and_process(self) -> int:
        """Claim and process one batch of events.

        Returns:
            Number of events processed in this batch.
        """
        now = datetime.now(timezone.utc)
        processed = 0

        session = SessionLocal()
        try:
            # Claim events with SELECT ... FOR UPDATE SKIP LOCKED
            claimable = (
                session.query(Event)
                .filter(
                    and_(
                        Event.consumer_group == self.consumer_group,
                        Event.status == "pending",
                        or_(
                            Event.next_retry_at.is_(None),
                            Event.next_retry_at <= now,
                        ),
                    )
                )
                .with_for_update(skip_locked=True)
                .limit(self.batch_size)
                .all()
            )

            if not claimable:
                session.commit()
                return 0

            # Mark claimed
            for event in claimable:
                event.mark_claimed(self.worker_id)
            session.commit()

        except Exception:
            session.rollback()
            self.logger.error("Failed to claim events", exc_info=True)
            return 0
        finally:
            session.close()

        # Process each event in its own transaction
        for event in claimable:
            self._process_single(event)
            processed += 1

        return processed

    def _process_single(self, event: Event) -> None:
        """Process a single claimed event in its own transaction."""
        session = SessionLocal()
        try:
            # Re-attach event to this session
            db_event = session.get(Event, event.id)
            if db_event is None or db_event.status != "claimed":
                session.commit()
                return

            try:
                result = self.process_event(db_event.event_type, db_event.payload)
                db_event.mark_completed(result)
                self.logger.debug(
                    f"Completed event {db_event.id} ({db_event.event_type})",
                    extra={
                        "event_id": db_event.id,
                        "event_type": db_event.event_type,
                        "attempt": db_event.attempt,
                    },
                )
            except Exception as exc:
                db_event.mark_failed(str(exc))
                self.logger.warning(
                    f"Event {db_event.id} failed (attempt {db_event.attempt}/"
                    f"{db_event.max_attempts}): {exc}",
                    extra={
                        "event_id": db_event.id,
                        "event_type": db_event.event_type,
                        "attempt": db_event.attempt,
                        "error": str(exc),
                    },
                )

            session.commit()

        except Exception:
            session.rollback()
            self.logger.error(
                f"Transaction failed for event {event.id}", exc_info=True
            )
        finally:
            session.close()

    def _setup_signal_handlers(self) -> None:
        """Register SIGTERM/SIGINT handlers for graceful shutdown."""
        def _handle_signal(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self._shutdown = True

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
