"""Tests for conviction voting database operations."""

from unittest.mock import MagicMock, patch

from notifications.vote_db import (
    get_leaderboard,
    get_llm_vs_crowd_stats,
    get_user_stats,
    get_user_streak,
    get_vote,
    get_vote_tally,
    is_prediction_evaluated,
    record_vote,
)


class TestRecordVote:
    def test_record_vote_success(self, mock_sync_session):
        mock_sync_session.execute = MagicMock()
        result = record_vote(123, "456", "bull", username="testuser")
        assert result is True

    def test_record_vote_with_username(self, mock_sync_session):
        mock_sync_session.execute = MagicMock()
        result = record_vote(123, "456", "bull", username="trader1")
        assert result is True
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["username"] == "trader1"

    def test_record_vote_db_error(self, mock_sync_session):
        mock_sync_session.execute = MagicMock(side_effect=Exception("DB error"))
        result = record_vote(123, "456", "bull")
        assert result is False


class TestGetVote:
    def test_get_vote_found(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1, 123, "456", "bull", None, None, None)]
        mock_result.keys.return_value = [
            "id",
            "prediction_id",
            "chat_id",
            "vote",
            "voted_at",
            "vote_correct",
            "evaluated_at",
        ]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        vote = get_vote(123, "456")
        assert vote is not None
        assert vote["vote"] == "bull"
        assert vote["prediction_id"] == 123

    def test_get_vote_not_found(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = []
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        vote = get_vote(999, "456")
        assert vote is None


class TestIsPredictionEvaluated:
    def test_evaluated(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (3,)
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        assert is_prediction_evaluated(123) is True

    def test_not_evaluated(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        assert is_prediction_evaluated(123) is False

    def test_no_votes(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        assert is_prediction_evaluated(999) is False


class TestGetVoteTally:
    def test_tally_with_votes(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("bull", 5),
            ("bear", 3),
            ("skip", 1),
        ]
        mock_result.keys.return_value = ["vote", "count"]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        tally = get_vote_tally(123)
        assert tally == {"bull": 5, "bear": 3, "skip": 1, "total": 9}

    def test_tally_empty(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = ["vote", "count"]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        tally = get_vote_tally(999)
        assert tally == {"bull": 0, "bear": 0, "skip": 0, "total": 0}

    def test_tally_only_bulls(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("bull", 7)]
        mock_result.keys.return_value = ["vote", "count"]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        tally = get_vote_tally(123)
        assert tally == {"bull": 7, "bear": 0, "skip": 0, "total": 7}


class TestGetUserStats:
    def test_user_with_stats(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(20, 8, 5, 5, 2, 6, 10, 2, 3)]
        mock_result.keys.return_value = [
            "total_votes",
            "correct",
            "incorrect",
            "pending",
            "skipped",
            "bull_correct",
            "bull_total",
            "bear_correct",
            "bear_total",
        ]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        stats = get_user_stats("456")
        assert stats["total_votes"] == 20
        assert stats["correct"] == 8
        assert stats["incorrect"] == 5
        assert stats["pending"] == 5
        assert stats["skipped"] == 2
        assert stats["accuracy_pct"] == 61.5  # 8/13 * 100
        assert stats["bull_accuracy"] == 60.0  # 6/10 * 100
        assert stats["bear_accuracy"] == 66.7  # 2/3 * 100

    def test_user_no_votes(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = []
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        stats = get_user_stats("nonexistent")
        assert stats == {"total_votes": 0}

    def test_user_zero_evaluated(self, mock_sync_session):
        """All votes pending — accuracy should be 0."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(5, 0, 0, 5, 0, 0, 0, 0, 0)]
        mock_result.keys.return_value = [
            "total_votes",
            "correct",
            "incorrect",
            "pending",
            "skipped",
            "bull_correct",
            "bull_total",
            "bear_correct",
            "bear_total",
        ]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        stats = get_user_stats("456")
        assert stats["accuracy_pct"] == 0.0


class TestGetUserStreak:
    def test_winning_streak(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (True,),
            (True,),
            (True,),
            (False,),
        ]
        mock_result.keys.return_value = ["vote_correct"]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        # _rows_to_dicts will create dicts
        with patch(
            "notifications.vote_db._execute_read",
            return_value=[
                {"vote_correct": True},
                {"vote_correct": True},
                {"vote_correct": True},
                {"vote_correct": False},
            ],
        ):
            streak = get_user_streak("456")
            assert streak["streak_type"] == "win"
            assert streak["streak_length"] == 3

    def test_losing_streak(self, mock_sync_session):
        with patch(
            "notifications.vote_db._execute_read",
            return_value=[
                {"vote_correct": False},
                {"vote_correct": False},
                {"vote_correct": True},
            ],
        ):
            streak = get_user_streak("456")
            assert streak["streak_type"] == "loss"
            assert streak["streak_length"] == 2

    def test_no_evaluated_votes(self, mock_sync_session):
        with patch("notifications.vote_db._execute_read", return_value=[]):
            streak = get_user_streak("456")
            assert streak["streak_type"] is None
            assert streak["streak_length"] == 0


class TestGetLeaderboard:
    def test_leaderboard_returns_data(self, mock_sync_session):
        with patch(
            "notifications.vote_db._execute_read",
            return_value=[
                {
                    "chat_id": "1",
                    "display_name": "TraderJoe",
                    "correct": 8,
                    "evaluated": 10,
                    "accuracy_pct": 80.0,
                },
                {
                    "chat_id": "2",
                    "display_name": "CryptoKing",
                    "correct": 6,
                    "evaluated": 10,
                    "accuracy_pct": 60.0,
                },
            ],
        ):
            leaders = get_leaderboard(limit=10)
            assert len(leaders) == 2
            assert leaders[0]["display_name"] == "TraderJoe"
            assert leaders[0]["accuracy_pct"] == 80.0

    def test_leaderboard_empty(self, mock_sync_session):
        with patch("notifications.vote_db._execute_read", return_value=[]):
            leaders = get_leaderboard()
            assert leaders == []


class TestGetLLMVsCrowdStats:
    def test_with_data(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(10, 6, 7, 8)]
        mock_result.keys.return_value = [
            "total_evaluated",
            "llm_correct_count",
            "crowd_correct_count",
            "agreement_count",
        ]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        stats = get_llm_vs_crowd_stats()
        assert stats["total_evaluated"] == 10
        assert stats["llm_accuracy"] == 60.0
        assert stats["crowd_accuracy"] == 70.0
        assert stats["agreement_rate"] == 80.0

    def test_no_data(self, mock_sync_session):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(0, 0, 0, 0)]
        mock_result.keys.return_value = [
            "total_evaluated",
            "llm_correct_count",
            "crowd_correct_count",
            "agreement_count",
        ]
        mock_sync_session.execute = MagicMock(return_value=mock_result)

        stats = get_llm_vs_crowd_stats()
        assert stats == {"total_evaluated": 0}
