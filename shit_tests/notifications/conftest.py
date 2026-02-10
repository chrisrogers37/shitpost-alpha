"""
Conftest for notifications tests.
Mocks database and settings imports so tests run without real connections.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_sync_session():
    """Mock the sync session to avoid real database connections."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    with patch("notifications.db.get_session", return_value=mock_session):
        yield mock_session


@pytest.fixture
def sample_alert():
    """Sample alert dict for testing."""
    return {
        "prediction_id": "pred_123",
        "shitpost_id": "post_456",
        "text": "Great news for tech stocks!",
        "confidence": 0.85,
        "assets": ["AAPL", "TSLA"],
        "sentiment": "bullish",
        "thesis": "Strong earnings expected.",
        "timestamp": "2024-01-15T10:00:00",
    }


@pytest.fixture
def sample_subscription():
    """Sample subscription dict for testing."""
    return {
        "id": 1,
        "chat_id": "123456",
        "chat_type": "private",
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "title": None,
        "is_active": True,
        "subscribed_at": None,
        "alert_preferences": {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
        "last_alert_at": None,
        "alerts_sent_count": 5,
        "consecutive_errors": 0,
    }


@pytest.fixture
def sample_preferences():
    """Sample subscriber preferences dict."""
    return {
        "min_confidence": 0.7,
        "assets_of_interest": [],
        "sentiment_filter": "all",
        "quiet_hours_enabled": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
