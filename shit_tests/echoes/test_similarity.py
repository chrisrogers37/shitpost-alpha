"""
Tests for EchoService similarity search (find_similar_posts).

Since pgvector queries require PostgreSQL, these tests mock the raw SQL
execution to verify query construction and result mapping.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import patch, MagicMock
from datetime import datetime

from shit.echoes.echo_service import EchoService

_SESSION_PATCH = "shit.echoes.echo_service.get_session"


def _mock_embedding_client():
    mock = MagicMock()
    mock.model = "text-embedding-3-small"
    return mock


def _make_similarity_rows(rows):
    """Create mock fetchall() result rows.

    Each row: (prediction_id, shitpost_id, signal_id, similarity,
               assets, market_impact, confidence, thesis, post_timestamp)
    """
    return rows


class TestFindSimilarPosts:
    def test_returns_matches_in_order(self):
        mock_rows = [
            (
                10,
                "post_a",
                None,
                0.92,
                ["XLE"],
                {"XLE": "bullish"},
                0.85,
                "Energy thesis",
                datetime(2025, 11, 15),
            ),
            (
                20,
                "post_b",
                None,
                0.78,
                ["TSLA"],
                {"TSLA": "bearish"},
                0.70,
                "Tesla thesis",
                datetime(2025, 12, 1),
            ),
        ]
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = mock_rows
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.find_similar_posts(
                embedding=[0.1] * 1536, limit=5, exclude_prediction_id=99
            )

        assert len(result) == 2
        assert result[0]["prediction_id"] == 10
        assert result[0]["similarity"] == 0.92
        assert result[0]["assets"] == ["XLE"]
        assert result[1]["prediction_id"] == 20

    def test_empty_db_returns_empty(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.find_similar_posts(embedding=[0.1] * 1536)

        assert result == []

    def test_exclude_prediction_id_passed_to_query(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            service.find_similar_posts(embedding=[0.1] * 1536, exclude_prediction_id=42)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]  # Second positional arg is the params dict
        assert params["exclude_id"] == 42

    def test_min_similarity_converted_to_max_distance(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            service.find_similar_posts(embedding=[0.1] * 1536, min_similarity=0.80)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert abs(params["max_dist"] - 0.20) < 0.001
