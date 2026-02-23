"""Tests for the EventWorker base class."""

import pytest
from unittest.mock import patch
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.worker import EventWorker


class DummyWorker(EventWorker):
    """Concrete worker for testing."""

    consumer_group = "test_consumer"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.processed_events = []
        self.fail_on_types = set()

    def process_event(self, event_type: str, payload: dict) -> dict:
        if event_type in self.fail_on_types:
            raise RuntimeError(f"Simulated failure for {event_type}")
        self.processed_events.append((event_type, payload))
        return {"ok": True}


class TestEventWorker:
    """Tests for the EventWorker base class."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch SessionLocal and get_session to use the test database."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession
        self._engine = event_engine

        @contextmanager
        def mock_get_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with (
            patch("shit.events.worker.SessionLocal", TestSession),
            patch("shit.events.worker.get_session", mock_get_session),
        ):
            yield

    def _seed_events(
        self, count: int = 3, consumer_group: str = "test_consumer"
    ) -> list[int]:
        """Seed pending events into the test database."""
        session = self._TestSession()
        ids = []
        for i in range(count):
            event = Event(
                event_type=f"test_event_{i}",
                consumer_group=consumer_group,
                payload={"index": i},
                source_service="test",
            )
            session.add(event)
            session.flush()
            ids.append(event.id)
        session.commit()
        session.close()
        return ids

    def test_consumer_group_required(self):
        """Test that consumer_group must be set."""

        class BadWorker(EventWorker):
            consumer_group = ""

            def process_event(self, event_type, payload):
                pass

        with pytest.raises(ValueError, match="consumer_group must be set"):
            BadWorker()

    def test_run_once_processes_all_pending(self):
        """Test that run_once drains all pending events."""
        self._seed_events(3)
        worker = DummyWorker(batch_size=10)

        total = worker.run_once()

        assert total == 3
        assert len(worker.processed_events) == 3

        # All events should be completed
        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "completed"
        session.close()

    def test_run_once_returns_zero_on_empty_queue(self):
        """Test that run_once returns 0 when no events are pending."""
        worker = DummyWorker()
        total = worker.run_once()
        assert total == 0

    def test_run_once_only_processes_own_consumer_group(self):
        """Test that worker only processes events for its own consumer group."""
        self._seed_events(2, consumer_group="test_consumer")
        self._seed_events(2, consumer_group="other_consumer")

        worker = DummyWorker()
        total = worker.run_once()

        assert total == 2  # Only test_consumer events

    def test_failed_event_retries(self):
        """Test that a failed event is re-queued for retry."""
        self._seed_events(1)
        worker = DummyWorker()
        worker.fail_on_types = {"test_event_0"}

        # First pass: event fails
        total = worker.run_once()
        assert total == 1

        session = self._TestSession()
        event = session.query(Event).first()
        assert event.status == "pending"  # Re-queued
        assert event.attempt == 1
        assert event.error == "Simulated failure for test_event_0"
        session.close()

    def test_dead_letter_after_max_attempts(self):
        """Test that events are dead-lettered after max_attempts."""
        session = self._TestSession()
        event = Event(
            event_type="test_event",
            consumer_group="test_consumer",
            payload={"index": 0},
            source_service="test",
            max_attempts=1,
        )
        session.add(event)
        session.commit()
        session.close()

        worker = DummyWorker()
        worker.fail_on_types = {"test_event"}

        # Single attempt, should go to dead_letter
        worker.run_once()

        session = self._TestSession()
        event = session.query(Event).first()
        assert event.status == "dead_letter"
        assert event.attempt == 1
        session.close()

    def test_batch_size_respected(self):
        """Test that batch_size limits events per poll cycle."""
        self._seed_events(5)
        worker = DummyWorker(batch_size=2)

        # run_once drains all, but in batches
        total = worker.run_once()
        assert total == 5  # All processed across multiple batches

    def test_result_stored_on_success(self):
        """Test that process_event return value is stored as result."""
        self._seed_events(1)
        worker = DummyWorker()
        worker.run_once()

        session = self._TestSession()
        event = session.query(Event).first()
        assert event.result == {"ok": True}
        session.close()

    def test_worker_id_auto_generated(self):
        """Test that worker_id is auto-generated when not provided."""
        worker = DummyWorker()
        assert worker.worker_id.startswith("test_consumer-")
        assert len(worker.worker_id) > len("test_consumer-")

    def test_worker_id_custom(self):
        """Test that custom worker_id is used."""
        worker = DummyWorker(worker_id="my-worker-01")
        assert worker.worker_id == "my-worker-01"

    def test_events_with_future_retry_not_claimed(self):
        """Test that events with next_retry_at in the future are skipped."""
        from datetime import datetime, timezone, timedelta

        session = self._TestSession()
        # Event with retry in the future
        event = Event(
            event_type="test_event",
            consumer_group="test_consumer",
            payload={},
            source_service="test",
            next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(event)
        session.commit()
        session.close()

        worker = DummyWorker()
        total = worker.run_once()

        assert total == 0  # Not yet ready for retry

    # --- New tests for signal handlers and run() ---

    def test_signal_handler_sets_shutdown_flag(self):
        """Test that receiving SIGTERM sets the _shutdown flag."""
        import os
        import signal as sig_mod

        worker = DummyWorker()
        assert worker._shutdown is False

        orig_term = sig_mod.getsignal(sig_mod.SIGTERM)
        orig_int = sig_mod.getsignal(sig_mod.SIGINT)

        try:
            worker._setup_signal_handlers()
            os.kill(os.getpid(), sig_mod.SIGTERM)
            assert worker._shutdown is True
        finally:
            sig_mod.signal(sig_mod.SIGTERM, orig_term)
            sig_mod.signal(sig_mod.SIGINT, orig_int)

    def test_signal_handler_sigint_sets_shutdown_flag(self):
        """Test that SIGINT also sets the _shutdown flag."""
        import os
        import signal as sig_mod

        worker = DummyWorker()

        orig_term = sig_mod.getsignal(sig_mod.SIGTERM)
        orig_int = sig_mod.getsignal(sig_mod.SIGINT)

        try:
            worker._setup_signal_handlers()
            os.kill(os.getpid(), sig_mod.SIGINT)
            assert worker._shutdown is True
        finally:
            sig_mod.signal(sig_mod.SIGTERM, orig_term)
            sig_mod.signal(sig_mod.SIGINT, orig_int)

    def test_run_exits_on_shutdown_flag(self):
        """Test that run() exits its loop when _shutdown becomes True."""
        worker = DummyWorker(poll_interval=0.1)

        call_count = 0

        def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            worker._shutdown = True

        with (
            patch("shit.events.worker.time.sleep", side_effect=fake_sleep),
            patch("shit.events.worker.signal.signal"),
        ):
            worker.run()

        assert call_count >= 1

    def test_run_processes_events_before_shutdown(self):
        """Test that run() processes events before checking shutdown."""
        self._seed_events(2)
        worker = DummyWorker(poll_interval=0.01)

        def shutdown_on_sleep(seconds):
            worker._shutdown = True

        with (
            patch("shit.events.worker.time.sleep", side_effect=shutdown_on_sleep),
            patch("shit.events.worker.signal.signal"),
        ):
            worker.run()

        assert len(worker.processed_events) == 2

        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "completed"
        session.close()

    def test_run_handles_poll_exception_gracefully(self):
        """Test that run() catches exceptions in _poll_and_process and continues."""
        worker = DummyWorker(poll_interval=0.01)
        poll_count = 0

        def failing_poll():
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                raise RuntimeError("Unexpected DB error")
            return 0

        worker._poll_and_process = failing_poll

        def shutdown_on_sleep(seconds):
            worker._shutdown = True

        with (
            patch("shit.events.worker.time.sleep", side_effect=shutdown_on_sleep),
            patch("shit.events.worker.signal.signal"),
        ):
            worker.run()

        assert poll_count >= 1

    def test_run_skips_sleep_when_events_processed(self):
        """Test that run() does NOT sleep when events were just processed."""
        self._seed_events(1)
        worker = DummyWorker(poll_interval=0.1)

        sleep_calls = []

        def tracking_sleep(seconds):
            sleep_calls.append(seconds)
            worker._shutdown = True

        with (
            patch("shit.events.worker.time.sleep", side_effect=tracking_sleep),
            patch("shit.events.worker.signal.signal"),
        ):
            worker.run()

        assert len(sleep_calls) == 1
        assert len(worker.processed_events) == 1
