"""Test fixtures for the event system."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shit.db.data_models import Base
from shit.events.models import Event


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
