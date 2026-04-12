"""Tests for vote maturation — evaluating conviction votes against outcomes."""

from unittest.mock import patch

from notifications.vote_maturation import (
    evaluate_votes_for_prediction,
    mature_all_votes,
)


class TestEvaluateVotesForPrediction:
    def test_bull_majority_outcomes(self, mock_sync_session):
        """When majority of assets went up, bull votes are correct."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[
                    {"symbol": "TSLA", "return_t7": 2.5},
                    {"symbol": "AAPL", "return_t7": 1.3},
                    {"symbol": "F", "return_t7": -0.2},  # Flat (within threshold)
                ],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            # Check the direction parameter
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "bull"

    def test_bear_majority_outcomes(self, mock_sync_session):
        """When majority of assets went down, bear votes are correct."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[
                    {"symbol": "TSLA", "return_t7": -3.0},
                    {"symbol": "AAPL", "return_t7": -1.5},
                    {"symbol": "F", "return_t7": 0.1},
                ],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "bear"

    def test_flat_market(self, mock_sync_session):
        """When all assets are flat, all non-skip votes are incorrect."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[
                    {"symbol": "TSLA", "return_t7": 0.1},
                    {"symbol": "AAPL", "return_t7": -0.3},
                ],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "flat"

    def test_tied_directions(self, mock_sync_session):
        """When equal bull and bear assets, treat as flat."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[
                    {"symbol": "TSLA", "return_t7": 2.0},
                    {"symbol": "AAPL", "return_t7": -2.0},
                ],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "flat"

    def test_no_outcomes(self, mock_sync_session):
        """No outcomes yet — nothing to evaluate."""
        with patch("notifications.vote_maturation._execute_read", return_value=[]):
            result = evaluate_votes_for_prediction(123)
            assert result is False

    def test_single_asset_bullish(self, mock_sync_session):
        """Single asset prediction with positive return."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[{"symbol": "TSLA", "return_t7": 5.0}],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "bull"

    def test_single_asset_bearish(self, mock_sync_session):
        """Single asset prediction with negative return."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[{"symbol": "TSLA", "return_t7": -3.0}],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "bear"

    def test_none_return_treated_as_zero(self, mock_sync_session):
        """None return_t7 values treated as 0 (flat)."""
        with (
            patch(
                "notifications.vote_maturation._execute_read",
                return_value=[{"symbol": "TSLA", "return_t7": None}],
            ),
            patch(
                "notifications.vote_maturation._execute_write", return_value=True
            ) as mock_write,
        ):
            result = evaluate_votes_for_prediction(123)
            assert result is True
            call_args = mock_write.call_args
            assert call_args[1]["params"]["direction"] == "flat"


class TestMatureAllVotes:
    def test_processes_pending_predictions(self, mock_sync_session):
        """Finds and processes predictions with pending votes."""
        call_count = 0

        def mock_read(query_str, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # find_votes_to_mature query
                return [{"prediction_id": 100}, {"prediction_id": 200}]
            else:
                # get_outcomes_for_vote_eval query
                return [{"symbol": "TSLA", "return_t7": 2.0}]

        with (
            patch("notifications.vote_maturation._execute_read", side_effect=mock_read),
            patch("notifications.vote_maturation._execute_write", return_value=True),
        ):
            stats = mature_all_votes()
            assert stats["predictions_processed"] == 2

    def test_no_pending_votes(self, mock_sync_session):
        """Nothing to process — returns zero."""
        with patch("notifications.vote_maturation._execute_read", return_value=[]):
            stats = mature_all_votes()
            assert stats["predictions_processed"] == 0

    def test_partial_failure(self, mock_sync_session):
        """Some predictions succeed, others fail."""
        call_count = 0

        def mock_read(query_str, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"prediction_id": 100}, {"prediction_id": 200}]
            elif call_count == 2:
                return [{"symbol": "TSLA", "return_t7": 2.0}]
            else:
                return []  # No outcomes for second prediction

        with (
            patch("notifications.vote_maturation._execute_read", side_effect=mock_read),
            patch("notifications.vote_maturation._execute_write", return_value=True),
        ):
            stats = mature_all_votes()
            assert stats["predictions_processed"] == 1
