"""
Tests for shit/echoes/echo_service.py — EchoService core operations.

Covers: embed_and_store, get_embedding, duplicate detection, empty text handling.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import patch, MagicMock

from shit.echoes.echo_service import EchoService

_SESSION_PATCH = "shit.echoes.echo_service.get_session"


def _mock_embedding_client(vector=None):
    """Create a mock EmbeddingClient that returns a fixed vector."""
    if vector is None:
        vector = [0.1] * 1536
    mock = MagicMock()
    mock.embed.return_value = vector
    mock.embed_batch.return_value = [vector]
    mock.model = "text-embedding-3-small"
    return mock


def _mock_session_ctx(query_results=None):
    """Create a mock get_session context manager."""
    mock_session = MagicMock()
    if query_results is not None:
        mock_session.query.return_value.filter.return_value.first.return_value = (
            query_results
        )
    else:
        mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx, mock_session


class TestEmbedAndStore:
    def test_stores_new_embedding(self):
        mock_client = _mock_embedding_client()
        mock_ctx, mock_session = _mock_session_ctx(query_results=None)

        service = EchoService(embedding_client=mock_client)
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.embed_and_store(
                prediction_id=1, text="Drill baby drill!", shitpost_id="abc123"
            )

        assert result is True
        mock_client.embed.assert_called_once_with("Drill baby drill!")
        assert mock_session.add.called

    def test_skips_duplicate(self):
        mock_client = _mock_embedding_client()
        existing = MagicMock()  # Simulate existing record
        mock_ctx, mock_session = _mock_session_ctx(query_results=existing)

        service = EchoService(embedding_client=mock_client)
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.embed_and_store(prediction_id=1, text="Some text")

        assert result is False
        mock_client.embed.assert_not_called()

    def test_empty_text_returns_false(self):
        mock_client = _mock_embedding_client()
        service = EchoService(embedding_client=mock_client)

        assert service.embed_and_store(prediction_id=1, text="") is False
        assert service.embed_and_store(prediction_id=2, text="   ") is False
        mock_client.embed.assert_not_called()

    def test_none_text_returns_false(self):
        mock_client = _mock_embedding_client()
        service = EchoService(embedding_client=mock_client)
        assert service.embed_and_store(prediction_id=1, text=None) is False


class TestGetEmbedding:
    def test_returns_embedding_when_exists(self):
        mock_record = MagicMock()
        mock_record.embedding = [0.5] * 1536
        mock_ctx, _ = _mock_session_ctx(query_results=mock_record)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.get_embedding(prediction_id=1)

        assert result == [0.5] * 1536

    def test_returns_none_when_not_found(self):
        mock_ctx, _ = _mock_session_ctx(query_results=None)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.get_embedding(prediction_id=999)

        assert result is None
