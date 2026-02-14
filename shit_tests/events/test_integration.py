"""Integration tests for the event system end-to-end flow."""

import pytest
from unittest.mock import patch
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

from shit.events.models import Event
from shit.events.event_types import EventType, ConsumerGroup
from shit.events.producer import emit_event
from shit.events.worker import EventWorker


class S3ProcessorWorker(EventWorker):
    """Test S3 processor worker that emits signals_stored."""

    consumer_group = ConsumerGroup.S3_PROCESSOR

    def __init__(self, emit_fn=None, **kwargs):
        super().__init__(**kwargs)
        self._emit_fn = emit_fn
        self.processed = []

    def process_event(self, event_type: str, payload: dict) -> dict:
        self.processed.append(payload)
        # Simulate processing and emit downstream event
        if self._emit_fn:
            self._emit_fn(
                event_type=EventType.SIGNALS_STORED,
                payload={
                    "signal_ids": ["sig_1", "sig_2"],
                    "source": payload.get("source", "truth_social"),
                    "count": 2,
                },
                source_service="s3_processor",
                correlation_id=None,
            )
        return {"signals_stored": 2}


class AnalyzerWorker(EventWorker):
    """Test analyzer worker."""

    consumer_group = ConsumerGroup.ANALYZER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.processed = []

    def process_event(self, event_type: str, payload: dict) -> dict:
        self.processed.append(payload)
        return {"predictions_created": len(payload.get("signal_ids", []))}


class TestEventChain:
    """Test the full event chain: harvest -> s3_process -> analyze."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, event_engine):
        """Patch all session access to use the test database."""
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

        with patch("shit.events.producer.get_session", mock_get_session), \
             patch("shit.events.worker.SessionLocal", TestSession), \
             patch("shit.events.worker.get_session", mock_get_session):
            yield

    def test_full_chain_harvest_to_analyze(self):
        """Test event chain: posts_harvested -> signals_stored -> analyzer receives."""
        # Step 1: Harvester emits posts_harvested
        emit_event(
            event_type=EventType.POSTS_HARVESTED,
            payload={
                "s3_keys": ["key1.json", "key2.json"],
                "source": "truth_social",
                "count": 2,
                "mode": "incremental",
            },
            source_service="harvester",
            correlation_id="chain-001",
        )

        # Verify: 1 event for s3_processor
        session = self._TestSession()
        events = session.query(Event).all()
        assert len(events) == 1
        assert events[0].consumer_group == ConsumerGroup.S3_PROCESSOR
        session.close()

        # Step 2: S3 Processor worker consumes and emits signals_stored
        s3_worker = S3ProcessorWorker(emit_fn=emit_event)
        s3_worker.run_once()

        assert len(s3_worker.processed) == 1

        # Verify: original event completed, new event for analyzer
        session = self._TestSession()
        all_events = session.query(Event).order_by(Event.id).all()
        assert len(all_events) == 2

        assert all_events[0].status == "completed"
        assert all_events[0].consumer_group == ConsumerGroup.S3_PROCESSOR

        assert all_events[1].status == "pending"
        assert all_events[1].consumer_group == ConsumerGroup.ANALYZER
        assert all_events[1].event_type == EventType.SIGNALS_STORED
        session.close()

        # Step 3: Analyzer worker consumes signals_stored
        analyzer_worker = AnalyzerWorker()
        analyzer_worker.run_once()

        assert len(analyzer_worker.processed) == 1
        assert analyzer_worker.processed[0]["signal_ids"] == ["sig_1", "sig_2"]

        # Verify: all events completed
        session = self._TestSession()
        all_events = session.query(Event).all()
        for e in all_events:
            assert e.status == "completed"
        session.close()

    def test_prediction_created_fan_out(self):
        """Test that prediction_created fans out to both market_data and notifications."""
        emit_event(
            event_type=EventType.PREDICTION_CREATED,
            payload={
                "prediction_id": 42,
                "shitpost_id": "post_123",
                "assets": ["TSLA", "AAPL"],
                "confidence": 0.85,
                "analysis_status": "completed",
            },
            source_service="analyzer",
        )

        session = self._TestSession()
        events = session.query(Event).all()
        assert len(events) == 2

        groups = {e.consumer_group for e in events}
        assert groups == {ConsumerGroup.MARKET_DATA, ConsumerGroup.NOTIFICATIONS}

        # Both share the same correlation_id
        corr_ids = {e.correlation_id for e in events}
        assert len(corr_ids) == 1
        session.close()

    def test_concurrent_workers_no_double_processing(self):
        """Test that two workers for the same group don't double-process.

        Note: SQLite doesn't support FOR UPDATE SKIP LOCKED, so this test
        verifies the logic works in a single-worker scenario. True concurrency
        testing requires PostgreSQL.
        """
        # Seed 5 events
        for i in range(5):
            emit_event(
                event_type=EventType.POSTS_HARVESTED,
                payload={"s3_keys": [f"key_{i}.json"], "source": "ts", "count": 1},
                source_service="harvester",
            )

        # Two workers, same consumer group
        worker_a = S3ProcessorWorker(worker_id="worker-a")
        worker_b = S3ProcessorWorker(worker_id="worker-b")

        # Run sequentially (SQLite limitation)
        total_a = worker_a.run_once()
        total_b = worker_b.run_once()

        # All events should be processed exactly once
        assert total_a + total_b == 5

        session = self._TestSession()
        completed = session.query(Event).filter(Event.status == "completed").count()
        assert completed == 5
        session.close()
