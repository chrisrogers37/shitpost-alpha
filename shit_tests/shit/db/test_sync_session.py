"""Tests for synchronous session management (shit/db/sync_session.py)."""

import pytest
from unittest.mock import patch, MagicMock, call


class TestGetSession:
    """Test the get_session() context manager."""

    @patch("shit.db.sync_session.SessionLocal")
    def test_yields_session(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with get_session() as session:
            assert session is mock_session

    @patch("shit.db.sync_session.SessionLocal")
    def test_commits_on_success(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with get_session() as session:
            pass  # No error

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch("shit.db.sync_session.SessionLocal")
    def test_rolls_back_on_exception(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with pytest.raises(ValueError):
            with get_session() as session:
                raise ValueError("test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    @patch("shit.db.sync_session.SessionLocal")
    def test_closes_session_on_success(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with get_session() as session:
            pass

        mock_session.close.assert_called_once()

    @patch("shit.db.sync_session.SessionLocal")
    def test_closes_session_on_exception(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with pytest.raises(ValueError):
            with get_session() as session:
                raise ValueError("test error")

        mock_session.close.assert_called_once()

    @patch("shit.db.sync_session.SessionLocal")
    def test_reraises_exception(self, mock_factory):
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session

        with pytest.raises(RuntimeError, match="specific error"):
            with get_session() as session:
                raise RuntimeError("specific error")

    @patch("shit.db.sync_session.SessionLocal")
    def test_operation_order_on_success(self, mock_factory):
        """Verify commit happens before close."""
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session
        call_order = []
        mock_session.commit.side_effect = lambda: call_order.append("commit")
        mock_session.close.side_effect = lambda: call_order.append("close")

        with get_session() as session:
            pass

        assert call_order == ["commit", "close"]

    @patch("shit.db.sync_session.SessionLocal")
    def test_operation_order_on_error(self, mock_factory):
        """Verify rollback happens before close on error."""
        from shit.db.sync_session import get_session

        mock_session = MagicMock()
        mock_factory.return_value = mock_session
        call_order = []
        mock_session.rollback.side_effect = lambda: call_order.append("rollback")
        mock_session.close.side_effect = lambda: call_order.append("close")

        with pytest.raises(ValueError):
            with get_session() as session:
                raise ValueError("boom")

        assert call_order == ["rollback", "close"]


class TestCreateTables:
    """Test create_tables() function."""

    @patch("shit.db.sync_session.engine")
    def test_calls_create_all(self, mock_engine):
        from shit.db.data_models import Base
        from shit.db.sync_session import create_tables

        with patch.object(Base.metadata, "create_all") as mock_create:
            create_tables()
            mock_create.assert_called_once_with(mock_engine)
