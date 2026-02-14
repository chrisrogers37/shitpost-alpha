"""Tests for the Event model."""

import pytest
from datetime import datetime, timezone

from shit.events.models import Event


class TestEventModel:
    """Tests for the Event SQLAlchemy model."""

    def test_create_event(self, event_session):
        """Test basic event creation and persistence."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={"s3_keys": ["key1.json"], "count": 1},
            source_service="harvester",
            correlation_id="corr-001",
        )
        event_session.add(event)
        event_session.commit()

        assert event.id is not None
        assert event.status == "pending"
        assert event.attempt == 0
        assert event.max_attempts == 3
        assert event.payload["count"] == 1

    def test_default_values(self, event_session):
        """Test that default values are set correctly."""
        event = Event(
            event_type="signals_stored",
            consumer_group="analyzer",
            payload={},
        )
        event_session.add(event)
        event_session.commit()

        assert event.status == "pending"
        assert event.attempt == 0
        assert event.max_attempts == 3
        assert event.claimed_by is None
        assert event.claimed_at is None
        assert event.completed_at is None
        assert event.result is None
        assert event.error is None
        assert event.next_retry_at is None

    def test_mark_claimed(self, event_session):
        """Test marking an event as claimed."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
        )
        event_session.add(event)
        event_session.commit()

        event.mark_claimed("worker-abc123")
        event_session.commit()

        assert event.status == "claimed"
        assert event.claimed_by == "worker-abc123"
        assert event.claimed_at is not None
        assert event.attempt == 1

    def test_mark_completed(self, event_session):
        """Test marking an event as completed."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
        )
        event_session.add(event)
        event_session.commit()

        event.mark_claimed("worker-abc")
        event.mark_completed({"processed": True})
        event_session.commit()

        assert event.status == "completed"
        assert event.completed_at is not None
        assert event.result == {"processed": True}

    def test_mark_completed_no_result(self, event_session):
        """Test marking completed without a result dict."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
        )
        event_session.add(event)
        event_session.commit()

        event.mark_claimed("worker-abc")
        event.mark_completed()
        event_session.commit()

        assert event.status == "completed"
        assert event.result is None

    def test_mark_failed_retries(self, event_session):
        """Test that failed events are re-queued with backoff when under max_attempts."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
            max_attempts=3,
        )
        event_session.add(event)
        event_session.commit()

        # First attempt fails
        event.mark_claimed("worker-abc")
        event.mark_failed("connection error")
        event_session.commit()

        assert event.status == "pending"  # Re-queued
        assert event.error == "connection error"
        assert event.next_retry_at is not None
        assert event.attempt == 1

    def test_mark_failed_dead_letter(self, event_session):
        """Test that events go to dead_letter after max_attempts."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
            max_attempts=2,
        )
        event_session.add(event)
        event_session.commit()

        # Exhaust retries
        event.mark_claimed("worker-abc")  # attempt 1
        event.mark_failed("error 1")      # still under max
        event.mark_claimed("worker-abc")  # attempt 2
        event.mark_failed("error 2")      # now at max
        event_session.commit()

        assert event.status == "dead_letter"
        assert event.error == "error 2"
        assert event.attempt == 2

    def test_repr(self):
        """Test event string representation."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
        )
        event.id = 42
        event.status = "pending"
        assert "42" in repr(event)
        assert "posts_harvested" in repr(event)
        assert "s3_processor" in repr(event)
        assert "pending" in repr(event)

    def test_json_payload(self, event_session):
        """Test that complex JSON payloads are stored and retrieved correctly."""
        payload = {
            "s3_keys": ["key1.json", "key2.json"],
            "source": "truth_social",
            "count": 2,
            "nested": {"a": [1, 2, 3]},
        }
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload=payload,
        )
        event_session.add(event)
        event_session.commit()

        # Re-query
        fetched = event_session.query(Event).get(event.id)
        assert fetched.payload == payload
        assert fetched.payload["nested"]["a"] == [1, 2, 3]

    def test_exponential_backoff_timing(self, event_session):
        """Test that backoff increases exponentially."""
        event = Event(
            event_type="posts_harvested",
            consumer_group="s3_processor",
            payload={},
            max_attempts=5,
        )
        event_session.add(event)
        event_session.commit()

        # Track retry times
        retry_times = []
        for _ in range(3):
            event.mark_claimed("worker-abc")
            before = datetime.now(timezone.utc)
            event.mark_failed("error")
            if event.next_retry_at:
                delta = (event.next_retry_at - before).total_seconds()
                retry_times.append(delta)

        # Each retry should be longer than the previous
        # (allowing some tolerance for timing)
        assert len(retry_times) == 3
        assert retry_times[1] > retry_times[0]
        assert retry_times[2] > retry_times[1]
