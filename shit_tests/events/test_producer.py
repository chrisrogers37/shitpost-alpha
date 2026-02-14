"""Tests for the event producer (emit_event)."""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from shit.events.models import Event
from shit.events.event_types import EventType, ConsumerGroup, CONSUMER_GROUPS
from shit.events.producer import emit_event


class TestEmitEvent:
    """Tests for the emit_event function."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch get_session to use the test database."""
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(event_engine, expire_on_commit=False)

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

        self._TestSession = TestSession
        with patch("shit.events.producer.get_session", mock_get_session):
            yield

    def test_emit_posts_harvested(self):
        """Test emitting a posts_harvested event creates one row for s3_processor."""
        payload = {
            "s3_keys": ["key1.json"],
            "source": "truth_social",
            "count": 1,
            "mode": "incremental",
        }

        event_ids = emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload=payload,
            source_service="harvester",
        )

        assert len(event_ids) == 1

        # Verify in DB
        session = self._TestSession()
        event = session.query(Event).get(event_ids[0])
        assert event.event_type == EventType.POSTS_HARVESTED
        assert event.consumer_group == ConsumerGroup.S3_PROCESSOR
        assert event.status == "pending"
        assert event.payload == payload
        assert event.source_service == "harvester"
        assert event.correlation_id is not None
        session.close()

    def test_emit_prediction_created_fan_out(self):
        """Test that prediction_created fans out to market_data and notifications."""
        payload = {
            "prediction_id": 42,
            "assets": ["TSLA"],
            "confidence": 0.85,
            "analysis_status": "completed",
        }

        event_ids = emit_event(
            event_type=EventType.PREDICTION_CREATED,
            payload=payload,
            source_service="analyzer",
        )

        # Should create 2 rows (market_data + notifications)
        assert len(event_ids) == 2

        session = self._TestSession()
        events = session.query(Event).filter(Event.id.in_(event_ids)).all()
        consumer_groups = {e.consumer_group for e in events}
        assert consumer_groups == {ConsumerGroup.MARKET_DATA, ConsumerGroup.NOTIFICATIONS}

        # Both should share the same correlation_id
        correlation_ids = {e.correlation_id for e in events}
        assert len(correlation_ids) == 1

        # Both should have the same payload
        for e in events:
            assert e.payload == payload
        session.close()

    def test_emit_signals_stored(self):
        """Test emitting signals_stored event creates one row for analyzer."""
        event_ids = emit_event(
            event_type=EventType.SIGNALS_STORED,
            payload={"signal_ids": ["sig_1", "sig_2"], "source": "truth_social", "count": 2},
            source_service="s3_processor",
        )

        assert len(event_ids) == 1

        session = self._TestSession()
        event = session.query(Event).get(event_ids[0])
        assert event.consumer_group == ConsumerGroup.ANALYZER
        session.close()

    def test_emit_prices_backfilled_no_consumers(self):
        """Test that terminal events with no consumers produce no rows."""
        event_ids = emit_event(
            event_type=EventType.PRICES_BACKFILLED,
            payload={"symbols": ["TSLA"], "prediction_id": 1},
            source_service="market_data",
        )

        assert event_ids == []

    def test_emit_unknown_event_type_raises(self):
        """Test that an unknown event type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown event type"):
            emit_event(
                event_type="nonexistent_event",
                payload={},
                source_service="test",
            )

    def test_custom_correlation_id(self):
        """Test passing a custom correlation_id."""
        event_ids = emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload={"s3_keys": [], "source": "test", "count": 0},
            source_service="harvester",
            correlation_id="my-custom-corr-id",
        )

        session = self._TestSession()
        event = session.query(Event).get(event_ids[0])
        assert event.correlation_id == "my-custom-corr-id"
        session.close()

    def test_custom_max_attempts(self):
        """Test passing a custom max_attempts."""
        event_ids = emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload={"s3_keys": [], "source": "test", "count": 0},
            source_service="harvester",
            max_attempts=5,
        )

        session = self._TestSession()
        event = session.query(Event).get(event_ids[0])
        assert event.max_attempts == 5
        session.close()

    def test_emit_multiple_events_independence(self):
        """Test that multiple emissions create independent events."""
        ids_1 = emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload={"s3_keys": ["a.json"], "source": "ts", "count": 1},
            source_service="harvester",
        )
        ids_2 = emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload={"s3_keys": ["b.json"], "source": "ts", "count": 1},
            source_service="harvester",
        )

        session = self._TestSession()
        e1 = session.query(Event).get(ids_1[0])
        e2 = session.query(Event).get(ids_2[0])

        assert e1.payload["s3_keys"] == ["a.json"]
        assert e2.payload["s3_keys"] == ["b.json"]
        # Different correlation IDs
        assert e1.correlation_id != e2.correlation_id
        session.close()
