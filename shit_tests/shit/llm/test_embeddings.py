"""
Tests for shit/llm/embeddings.py — EmbeddingClient.

Covers: single embedding, batch embedding, text truncation.
"""

from unittest.mock import patch, MagicMock

from shit.llm.embeddings import EmbeddingClient


def _make_mock_response(embeddings: list[list[float]]) -> MagicMock:
    """Create a mock OpenAI embeddings.create() response."""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=e) for e in embeddings]
    return mock_resp


class TestEmbedSingle:
    def test_returns_embedding_vector(self):
        expected = [0.1] * 1536
        with patch("shit.llm.embeddings.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = _make_mock_response([expected])
            mock_cls.return_value = mock_client

            client = EmbeddingClient()
            result = client.embed("Hello world")

        assert result == expected
        mock_client.embeddings.create.assert_called_once()
        call_kwargs = mock_client.embeddings.create.call_args
        assert call_kwargs.kwargs["model"] == "text-embedding-3-small"
        assert call_kwargs.kwargs["input"] == "Hello world"

    def test_truncates_long_text(self):
        long_text = "x" * 10000
        with patch("shit.llm.embeddings.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = _make_mock_response(
                [[0.1] * 1536]
            )
            mock_cls.return_value = mock_client

            client = EmbeddingClient()
            client.embed(long_text)

        call_kwargs = mock_client.embeddings.create.call_args
        assert len(call_kwargs.kwargs["input"]) == 8000


class TestEmbedBatch:
    def test_returns_multiple_embeddings(self):
        expected = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        with patch("shit.llm.embeddings.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = _make_mock_response(expected)
            mock_cls.return_value = mock_client

            client = EmbeddingClient()
            result = client.embed_batch(["a", "b", "c"])

        assert len(result) == 3
        assert result[0] == expected[0]

    def test_empty_input_returns_empty(self):
        with patch("shit.llm.embeddings.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = EmbeddingClient()
            assert client.embed_batch([]) == []

    def test_truncates_each_text(self):
        with patch("shit.llm.embeddings.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = _make_mock_response(
                [[0.1] * 1536, [0.2] * 1536]
            )
            mock_cls.return_value = mock_client

            client = EmbeddingClient()
            client.embed_batch(["x" * 10000, "y" * 10000])

        call_kwargs = mock_client.embeddings.create.call_args
        for text in call_kwargs.kwargs["input"]:
            assert len(text) == 8000
