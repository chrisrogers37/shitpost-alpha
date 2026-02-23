"""Test fixtures for the event system."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shit.db.data_models import Base


@pytest.fixture
def event_engine(tmp_path):
    """Create a temporary SQLite engine with event tables."""
    db_path = tmp_path / "test_events.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def event_session(event_engine):
    """Provide a transactional session for event tests."""
    Session = sessionmaker(event_engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "event_type": "posts_harvested",
        "consumer_group": "s3_processor",
        "payload": {
            "s3_keys": ["truth_social/raw/2024/01/15/post_123.json"],
            "source": "truth_social",
            "count": 1,
            "mode": "incremental",
        },
        "source_service": "harvester",
        "correlation_id": "test-corr-001",
    }


@pytest.fixture
def sample_prediction_event_data():
    """Sample prediction_created event data."""
    return {
        "event_type": "prediction_created",
        "consumer_group": "market_data",
        "payload": {
            "prediction_id": 42,
            "shitpost_id": "post_123",
            "assets": ["TSLA", "AAPL"],
            "confidence": 0.85,
            "analysis_status": "completed",
        },
        "source_service": "analyzer",
        "correlation_id": "test-corr-002",
    }


@pytest.fixture
def sample_signals_stored_data():
    """Sample signals_stored event data for analyzer consumer tests."""
    return {
        "event_type": "signals_stored",
        "consumer_group": "analyzer",
        "payload": {
            "signal_ids": ["sig_001", "sig_002", "sig_003"],
            "source": "truth_social",
            "count": 3,
        },
        "source_service": "s3_processor",
        "correlation_id": "test-corr-003",
    }


@pytest.fixture
def sample_notification_event_data():
    """Sample prediction_created event data for notifications consumer tests."""
    return {
        "event_type": "prediction_created",
        "consumer_group": "notifications",
        "payload": {
            "prediction_id": 99,
            "shitpost_id": "post_456",
            "assets": ["SPY", "QQQ"],
            "confidence": 0.72,
            "analysis_status": "completed",
        },
        "source_service": "analyzer",
        "correlation_id": "test-corr-004",
    }


@pytest.fixture
def patched_worker_session(event_engine):
    """Patch SessionLocal and get_session for worker tests.

    Returns a tuple of (TestSession, cleanup) where cleanup is a
    context manager that patches the worker module's session access.

    Usage in tests:
        def test_something(self, patched_worker_session):
            TestSession, patch_ctx = patched_worker_session
            with patch_ctx:
                worker = MyWorker()
                worker.run_once()
    """
    from contextlib import contextmanager
    from unittest.mock import patch

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

    patch_ctx = patch("shit.events.worker.SessionLocal", TestSession)
    patch_ctx2 = patch("shit.events.worker.get_session", mock_get_session)

    class PatchContext:
        def __enter__(self_inner):
            patch_ctx.__enter__()
            patch_ctx2.__enter__()
            return self_inner

        def __exit__(self_inner, *args):
            patch_ctx2.__exit__(*args)
            patch_ctx.__exit__(*args)

    return TestSession, PatchContext()
