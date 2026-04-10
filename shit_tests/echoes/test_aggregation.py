"""
Tests for EchoService.aggregate_echoes — outcome aggregation.

Covers: full outcomes, no outcomes, partial outcomes, empty matches.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import patch, MagicMock

from shit.echoes.echo_service import EchoService

_SESSION_PATCH = "shit.echoes.echo_service.get_session"


def _mock_embedding_client():
    mock = MagicMock()
    mock.model = "text-embedding-3-small"
    return mock


def _make_outcome(prediction_id, symbol, return_t7=None, correct_t7=None, pnl_t7=None):
    """Create a mock PredictionOutcome."""
    o = MagicMock()
    o.prediction_id = prediction_id
    o.symbol = symbol
    o.return_t7 = return_t7
    o.correct_t7 = correct_t7
    o.pnl_t7 = pnl_t7
    return o


def _mock_outcomes_session(outcomes):
    """Create a mock session that returns given outcomes from query."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = outcomes
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


class TestAggregateEchoes:
    def test_empty_matches(self):
        service = EchoService(embedding_client=_mock_embedding_client())
        result = service.aggregate_echoes([], timeframe="t7")
        assert result["count"] == 0
        assert result["matches"] == []

    def test_with_outcomes(self):
        matches = [
            {
                "prediction_id": 10,
                "similarity": 0.90,
                "assets": ["XLE"],
                "thesis": "Energy",
                "post_timestamp": None,
            },
            {
                "prediction_id": 20,
                "similarity": 0.80,
                "assets": ["OXY"],
                "thesis": "Oil",
                "post_timestamp": None,
            },
        ]
        outcomes = [
            _make_outcome(10, "XLE", return_t7=3.2, correct_t7=True, pnl_t7=32.0),
            _make_outcome(20, "OXY", return_t7=-1.0, correct_t7=False, pnl_t7=-10.0),
        ]
        mock_ctx = _mock_outcomes_session(outcomes)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.aggregate_echoes(matches, timeframe="t7")

        assert result["count"] == 2
        assert result["timeframe"] == "t7"
        assert result["avg_return"] == round((3.2 + -1.0) / 2, 4)
        assert result["win_rate"] == round(1 / 2, 4)
        assert result["correct"] == 1
        assert result["incorrect"] == 1
        assert result["avg_pnl"] == round((32.0 + -10.0) / 2, 2)

    def test_no_outcomes_yet(self):
        """Matches exist but no prediction_outcomes recorded."""
        matches = [
            {
                "prediction_id": 10,
                "similarity": 0.85,
                "assets": ["XLE"],
                "thesis": "Energy",
                "post_timestamp": None,
            },
        ]
        mock_ctx = _mock_outcomes_session([])

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.aggregate_echoes(matches, timeframe="t7")

        assert result["count"] == 1
        assert result["avg_return"] is None
        assert result["win_rate"] is None
        assert result["pending"] == 1

    def test_partial_outcomes(self):
        """Some matches have outcomes, some don't."""
        matches = [
            {
                "prediction_id": 10,
                "similarity": 0.90,
                "assets": ["XLE"],
                "thesis": "A",
                "post_timestamp": None,
            },
            {
                "prediction_id": 20,
                "similarity": 0.80,
                "assets": ["OXY"],
                "thesis": "B",
                "post_timestamp": None,
            },
            {
                "prediction_id": 30,
                "similarity": 0.70,
                "assets": ["CVX"],
                "thesis": "C",
                "post_timestamp": None,
            },
        ]
        outcomes = [
            _make_outcome(10, "XLE", return_t7=2.0, correct_t7=True, pnl_t7=20.0),
            # prediction 20 and 30 have no outcomes
        ]
        mock_ctx = _mock_outcomes_session(outcomes)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.aggregate_echoes(matches, timeframe="t7")

        assert result["count"] == 3
        assert result["correct"] == 1
        assert result["incorrect"] == 0
        assert result["pending"] == 2
        assert result["avg_return"] == 2.0

    def test_match_details_included(self):
        matches = [
            {
                "prediction_id": 10,
                "similarity": 0.90,
                "assets": ["XLE"],
                "thesis": "Drill baby drill",
                "post_timestamp": "2025-11-15",
            },
        ]
        outcomes = [
            _make_outcome(10, "XLE", return_t7=3.2, correct_t7=True, pnl_t7=32.0),
        ]
        mock_ctx = _mock_outcomes_session(outcomes)

        service = EchoService(embedding_client=_mock_embedding_client())
        with patch(_SESSION_PATCH, return_value=mock_ctx):
            result = service.aggregate_echoes(matches, timeframe="t7")

        assert len(result["matches"]) == 1
        detail = result["matches"][0]
        assert detail["prediction_id"] == 10
        assert detail["similarity"] == 0.90
        assert detail["thesis"] == "Drill baby drill"
        assert len(detail["outcomes"]) == 1
        assert detail["outcomes"][0]["symbol"] == "XLE"
