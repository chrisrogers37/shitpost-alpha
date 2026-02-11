"""
Tests for shitvault/signal_operations.py - Signal CRUD operations.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from shitvault.signal_operations import SignalOperations
from shitvault.signal_models import Signal


def _make_signal_data(**overrides):
    """Helper to create a signal data dict for testing."""
    data = {
        "signal_id": "sig_001",
        "source": "truth_social",
        "source_url": "https://truthsocial.com/@user/001",
        "text": "Market update!",
        "content_html": "<p>Market update!</p>",
        "title": "",
        "language": "en",
        "author_id": "acct_1",
        "author_username": "testuser",
        "author_display_name": "Test User",
        "author_verified": True,
        "author_followers": 5000,
        "published_at": datetime(2025, 6, 1, 12, 0, 0),
        "likes_count": 20,
        "shares_count": 5,
        "replies_count": 10,
        "views_count": 0,
        "has_media": False,
        "is_repost": False,
        "is_reply": False,
        "is_quote": False,
        "platform_data": {"upvotes_count": 3},
        "raw_api_data": {"id": "001"},
    }
    data.update(overrides)
    return data


class TestStoreSignal:
    """Tests for SignalOperations.store_signal."""

    @pytest.mark.asyncio
    async def test_store_signal_new(self):
        """Test storing a new signal succeeds."""
        mock_db_ops = AsyncMock()
        mock_db_ops.read_one = AsyncMock(return_value=None)

        # Mock session.add, commit, refresh
        mock_signal = MagicMock()
        mock_signal.id = 42
        mock_signal.signal_id = "sig_001"
        mock_signal.source = "truth_social"

        mock_db_ops.session = AsyncMock()
        mock_db_ops.session.add = MagicMock()
        mock_db_ops.session.commit = AsyncMock()
        mock_db_ops.session.refresh = AsyncMock()

        ops = SignalOperations(mock_db_ops)

        with patch("shitvault.signal_operations.Signal") as MockSignal:
            mock_instance = MagicMock()
            mock_instance.id = 42
            mock_instance.signal_id = "sig_001"
            mock_instance.source = "truth_social"
            MockSignal.return_value = mock_instance

            result = await ops.store_signal(_make_signal_data())

        assert result == "42"
        mock_db_ops.session.add.assert_called_once()
        mock_db_ops.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_signal_duplicate_returns_existing_id(self):
        """Test that storing a duplicate signal returns the existing ID."""
        existing = MagicMock()
        existing.id = 99

        mock_db_ops = AsyncMock()
        mock_db_ops.read_one = AsyncMock(return_value=existing)
        mock_db_ops.session = AsyncMock()

        ops = SignalOperations(mock_db_ops)
        result = await ops.store_signal(_make_signal_data())

        assert result == "99"
        # Should not attempt to add/commit
        mock_db_ops.session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_signal_integrity_error_returns_none(self):
        """Test that IntegrityError returns None."""
        from sqlalchemy.exc import IntegrityError

        mock_db_ops = AsyncMock()
        mock_db_ops.read_one = AsyncMock(return_value=None)
        mock_db_ops.session = AsyncMock()
        mock_db_ops.session.add = MagicMock()
        mock_db_ops.session.commit = AsyncMock(
            side_effect=IntegrityError("dup", {}, Exception())
        )
        mock_db_ops.session.rollback = AsyncMock()

        ops = SignalOperations(mock_db_ops)

        with patch("shitvault.signal_operations.Signal") as MockSignal:
            MockSignal.return_value = MagicMock()
            result = await ops.store_signal(_make_signal_data())

        assert result is None
        mock_db_ops.session.rollback.assert_awaited_once()


class TestGetUnprocessedSignals:
    """Tests for SignalOperations.get_unprocessed_signals."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_signals(self):
        """Test returns empty list when no unprocessed signals exist."""
        mock_db_ops = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_ops.session.execute = AsyncMock(return_value=mock_result)

        ops = SignalOperations(mock_db_ops)
        result = await ops.get_unprocessed_signals(launch_date="2025-01-01")

        assert result == []

    @pytest.mark.asyncio
    async def test_backward_compat_aliases(self):
        """Test that returned dicts include backward-compatible aliases."""
        mock_signal = MagicMock(spec=Signal)
        mock_signal.id = 1
        mock_signal.signal_id = "sig_100"
        mock_signal.source = "truth_social"
        mock_signal.source_url = "https://example.com"
        mock_signal.text = "Test content"
        mock_signal.content_html = "<p>Test content</p>"
        mock_signal.title = ""
        mock_signal.language = "en"
        mock_signal.author_id = "acct_1"
        mock_signal.author_username = "testuser"
        mock_signal.author_display_name = "Test"
        mock_signal.author_verified = True
        mock_signal.author_followers = 1000
        mock_signal.published_at = datetime(2025, 6, 1)
        mock_signal.likes_count = 10
        mock_signal.shares_count = 5
        mock_signal.replies_count = 3
        mock_signal.views_count = 0
        mock_signal.has_media = False
        mock_signal.is_repost = False
        mock_signal.is_reply = False
        mock_signal.is_quote = False
        mock_signal.platform_data = {"upvotes_count": 2, "downvotes_count": 0}
        mock_signal.raw_api_data = {}
        mock_signal.created_at = datetime(2025, 6, 1)
        mock_signal.updated_at = datetime(2025, 6, 1)

        mock_db_ops = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_signal]
        mock_db_ops.session.execute = AsyncMock(return_value=mock_result)

        ops = SignalOperations(mock_db_ops)
        results = await ops.get_unprocessed_signals(launch_date="2025-01-01")

        assert len(results) == 1
        d = results[0]

        # Universal fields
        assert d["signal_id"] == "sig_100"
        assert d["source"] == "truth_social"
        assert d["likes_count"] == 10
        assert d["shares_count"] == 5

        # Backward-compatible aliases
        assert d["shitpost_id"] == "sig_100"
        assert d["username"] == "testuser"
        assert d["platform"] == "truth_social"
        assert d["content"] == "<p>Test content</p>"
        assert d["reblogs_count"] == 5  # shares_count alias
        assert d["favourites_count"] == 10  # likes_count alias
        assert d["account_verified"] is True
        assert d["account_followers_count"] == 1000
        assert d["upvotes_count"] == 2

    @pytest.mark.asyncio
    async def test_error_propagates(self):
        """Test that unexpected errors are re-raised."""
        mock_db_ops = AsyncMock()
        mock_db_ops.session.execute = AsyncMock(side_effect=RuntimeError("DB down"))

        ops = SignalOperations(mock_db_ops)

        with pytest.raises(RuntimeError, match="DB down"):
            await ops.get_unprocessed_signals(launch_date="2025-01-01")
