"""Tests for event cleanup operations."""

import pytest
from unittest.mock import patch
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.cleanup import (
    cleanup_completed_events,
    cleanup_dead_letter_events,
    retry_dead_letter_events,
)


class TestEventCleanup:
    """Tests for event cleanup and retry operations."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session to use the test database."""
        TestSession = sessionmaker(event_engine, expire_on_commit=False)
        self._TestSession = TestSession

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

        with patch("shit.events.cleanup.get_session", mock_get_session):
            yield

    def _seed_completed_events(self, count: int, days_ago: int) -> None:
        """Seed completed events with a specific age."""
        session = self._TestSession()
        for i in range(count):
            event = Event(
                event_type="test_event",
                consumer_group="test_consumer",
                payload={},
                status="completed",
                completed_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
                source_service="test",
            )
            session.add(event)
        session.commit()
        session.close()

    def _seed_dead_letter_events(
        self, count: int, days_ago: int, event_type: str = "test_event",
        consumer_group: str = "test_consumer"
    ) -> None:
        """Seed dead-letter events with a specific age."""
        session = self._TestSession()
        for i in range(count):
            event = Event(
                event_type=event_type,
                consumer_group=consumer_group,
                payload={},
                status="dead_letter",
                error="test error",
                attempt=3,
                max_attempts=3,
                source_service="test",
            )
            session.add(event)
            session.flush()
            # Manually set updated_at to simulate age
            event.updated_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        session.commit()
        session.close()

    def test_cleanup_completed_removes_old_events(self):
        """Test that old completed events are deleted."""
        self._seed_completed_events(3, days_ago=10)
        self._seed_completed_events(2, days_ago=3)

        deleted = cleanup_completed_events(older_than_days=7)

        assert deleted == 3

        session = self._TestSession()
        remaining = session.query(Event).count()
        assert remaining == 2
        session.close()

    def test_cleanup_completed_preserves_recent(self):
        """Test that recent completed events are preserved."""
        self._seed_completed_events(5, days_ago=1)

        deleted = cleanup_completed_events(older_than_days=7)

        assert deleted == 0

    def test_cleanup_dead_letter_removes_old(self):
        """Test that old dead-letter events are deleted."""
        self._seed_dead_letter_events(2, days_ago=60)
        self._seed_dead_letter_events(3, days_ago=10)

        deleted = cleanup_dead_letter_events(older_than_days=30)

        assert deleted == 2

    def test_cleanup_dead_letter_preserves_recent(self):
        """Test that recent dead-letter events are preserved."""
        self._seed_dead_letter_events(3, days_ago=5)

        deleted = cleanup_dead_letter_events(older_than_days=30)

        assert deleted == 0

    def test_retry_dead_letter_requeues_events(self):
        """Test that dead-letter events are re-queued as pending."""
        self._seed_dead_letter_events(3, days_ago=1)

        count = retry_dead_letter_events()

        assert count == 3

        session = self._TestSession()
        events = session.query(Event).all()
        for e in events:
            assert e.status == "pending"
            assert e.attempt == 0
            assert e.error is None
            assert e.claimed_by is None
            assert e.next_retry_at is None
        session.close()

    def test_retry_dead_letter_filter_by_event_type(self):
        """Test filtering retries by event_type."""
        self._seed_dead_letter_events(2, days_ago=1, event_type="type_a")
        self._seed_dead_letter_events(3, days_ago=1, event_type="type_b")

        count = retry_dead_letter_events(event_type="type_a")

        assert count == 2

        session = self._TestSession()
        pending = session.query(Event).filter(Event.status == "pending").all()
        dead = session.query(Event).filter(Event.status == "dead_letter").all()
        assert len(pending) == 2
        assert len(dead) == 3
        session.close()

    def test_retry_dead_letter_filter_by_consumer_group(self):
        """Test filtering retries by consumer_group."""
        self._seed_dead_letter_events(2, days_ago=1, consumer_group="group_a")
        self._seed_dead_letter_events(3, days_ago=1, consumer_group="group_b")

        count = retry_dead_letter_events(consumer_group="group_a")

        assert count == 2

    def test_retry_dead_letter_limit(self):
        """Test that max_events limits retries."""
        self._seed_dead_letter_events(5, days_ago=1)

        count = retry_dead_letter_events(max_events=2)

        assert count == 2

    def test_retry_dead_letter_empty(self):
        """Test that retry with no dead-letter events returns 0."""
        count = retry_dead_letter_events()
        assert count == 0
