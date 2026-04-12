"""Tests for vote callback handling and new bot commands."""

from unittest.mock import patch

from notifications.telegram_bot import (
    handle_leaderboard_command,
    handle_mystats_command,
    handle_vote_callback,
    process_update,
)
from notifications.telegram_sender import (
    build_vote_keyboard,
    build_voted_keyboard,
)


class TestBuildVoteKeyboard:
    def test_keyboard_structure(self):
        kb = build_vote_keyboard(123)
        assert "inline_keyboard" in kb
        buttons = kb["inline_keyboard"][0]
        assert len(buttons) == 3
        assert buttons[0]["callback_data"] == "vote:123:bull"
        assert buttons[1]["callback_data"] == "vote:123:bear"
        assert buttons[2]["callback_data"] == "vote:123:skip"

    def test_button_labels(self):
        kb = build_vote_keyboard(456)
        buttons = kb["inline_keyboard"][0]
        assert "Bull" in buttons[0]["text"]
        assert "Bear" in buttons[1]["text"]
        assert "Skip" in buttons[2]["text"]


class TestBuildVotedKeyboard:
    def test_shows_tallies(self):
        tally = {"bull": 5, "bear": 3, "skip": 1}
        kb = build_voted_keyboard(123, tally)
        buttons = kb["inline_keyboard"][0]
        assert "(5)" in buttons[0]["text"]
        assert "(3)" in buttons[1]["text"]
        assert "(1)" in buttons[2]["text"]

    def test_zero_tallies(self):
        tally = {"bull": 0, "bear": 0, "skip": 0}
        kb = build_voted_keyboard(123, tally)
        buttons = kb["inline_keyboard"][0]
        assert "(0)" in buttons[0]["text"]


class TestHandleVoteCallback:
    def _make_callback(self, pred_id=123, chat_id="456", vote="bull"):
        return {
            "id": "callback_123",
            "data": f"vote:{pred_id}:{vote}",
            "from": {"id": chat_id, "username": "testuser"},
            "message": {
                "message_id": 789,
                "chat": {"id": chat_id},
            },
        }

    @patch("notifications.telegram_bot.edit_message_reply_markup")
    @patch("notifications.telegram_bot.answer_callback_query")
    def test_valid_bull_vote(self, mock_answer, mock_edit, mock_sync_session):
        with (
            patch("notifications.vote_db.is_prediction_evaluated", return_value=False),
            patch("notifications.vote_db.get_vote", return_value=None),
            patch(
                "notifications.vote_db.record_vote", return_value=True
            ) as mock_record,
            patch(
                "notifications.vote_db.get_vote_tally",
                return_value={"bull": 1, "bear": 0, "skip": 0, "total": 1},
            ),
        ):
            handle_vote_callback(self._make_callback())

            mock_record.assert_called_once_with(123, "456", "bull", username="testuser")
            mock_answer.assert_called_once()
            assert "Bull" in str(mock_answer.call_args) or "BULL" in str(
                mock_answer.call_args
            )

    @patch("notifications.telegram_bot.answer_callback_query")
    def test_voting_closed(self, mock_answer, mock_sync_session):
        with patch("notifications.vote_db.is_prediction_evaluated", return_value=True):
            handle_vote_callback(self._make_callback())

            mock_answer.assert_called_once()
            assert "closed" in str(mock_answer.call_args).lower()

    @patch("notifications.telegram_bot.answer_callback_query")
    def test_already_voted(self, mock_answer, mock_sync_session):
        with (
            patch("notifications.vote_db.is_prediction_evaluated", return_value=False),
            patch(
                "notifications.vote_db.get_vote",
                return_value={"vote": "bull"},
            ),
        ):
            handle_vote_callback(self._make_callback())

            mock_answer.assert_called_once()
            assert "Already voted" in str(mock_answer.call_args)

    @patch("notifications.telegram_bot.answer_callback_query")
    def test_invalid_callback_data(self, mock_answer, mock_sync_session):
        callback = {
            "id": "cb_1",
            "data": "invalid_data",
            "from": {"id": "456"},
            "message": {"message_id": 1, "chat": {"id": "456"}},
        }
        handle_vote_callback(callback)
        mock_answer.assert_called_once()
        assert "Invalid" in str(mock_answer.call_args)

    @patch("notifications.telegram_bot.answer_callback_query")
    def test_invalid_vote_value(self, mock_answer, mock_sync_session):
        callback = {
            "id": "cb_1",
            "data": "vote:123:maybe",
            "from": {"id": "456"},
            "message": {"message_id": 1, "chat": {"id": "456"}},
        }
        handle_vote_callback(callback)
        mock_answer.assert_called_once()
        assert "Invalid" in str(mock_answer.call_args)

    @patch("notifications.telegram_bot.answer_callback_query")
    def test_invalid_prediction_id(self, mock_answer, mock_sync_session):
        callback = {
            "id": "cb_1",
            "data": "vote:abc:bull",
            "from": {"id": "456"},
            "message": {"message_id": 1, "chat": {"id": "456"}},
        }
        handle_vote_callback(callback)
        mock_answer.assert_called_once()
        assert "Invalid" in str(mock_answer.call_args)


class TestProcessUpdateCallbackQuery:
    @patch("notifications.telegram_bot.handle_vote_callback")
    def test_callback_query_routed(self, mock_handler, mock_sync_session):
        update = {
            "callback_query": {
                "id": "cb_1",
                "data": "vote:123:bull",
                "from": {"id": "456"},
                "message": {"message_id": 1, "chat": {"id": "456"}},
            }
        }
        result = process_update(update)
        assert result is None
        mock_handler.assert_called_once()

    @patch("notifications.telegram_bot.send_telegram_message")
    def test_message_still_works(self, mock_send, mock_sync_session):
        """Regular messages still route to command handlers."""
        update = {
            "message": {
                "chat": {"id": "456", "type": "private"},
                "text": "/help",
                "from": {"username": "test"},
            }
        }
        result = process_update(update)
        assert result is not None
        assert "Commands" in result or "commands" in result.lower()


class TestHandleMystatsCommand:
    def test_no_votes(self, mock_sync_session):
        with patch(
            "notifications.vote_db.get_user_stats",
            return_value={"total_votes": 0},
        ):
            result = handle_mystats_command("456")
            assert "haven't voted" in result

    def test_with_stats(self, mock_sync_session):
        with (
            patch(
                "notifications.vote_db.get_user_stats",
                return_value={
                    "total_votes": 20,
                    "correct": 12,
                    "incorrect": 5,
                    "pending": 3,
                    "skipped": 0,
                    "accuracy_pct": 70.6,
                    "bull_accuracy": 75.0,
                    "bear_accuracy": 60.0,
                },
            ),
            patch(
                "notifications.vote_db.get_user_streak",
                return_value={"streak_type": "win", "streak_length": 4},
            ),
        ):
            result = handle_mystats_command("456")
            assert "70.6%" in result
            assert "12" in result
            assert "5" in result
            assert "win" in result.lower()
            assert "4" in result

    def test_with_losing_streak(self, mock_sync_session):
        with (
            patch(
                "notifications.vote_db.get_user_stats",
                return_value={
                    "total_votes": 10,
                    "correct": 3,
                    "incorrect": 7,
                    "pending": 0,
                    "skipped": 0,
                    "accuracy_pct": 30.0,
                    "bull_accuracy": 25.0,
                    "bear_accuracy": 40.0,
                },
            ),
            patch(
                "notifications.vote_db.get_user_streak",
                return_value={"streak_type": "loss", "streak_length": 3},
            ),
        ):
            result = handle_mystats_command("456")
            assert "30.0%" in result
            assert "loss" in result.lower()


class TestHandleLeaderboardCommand:
    def test_no_data(self, mock_sync_session):
        with patch("notifications.vote_db.get_leaderboard", return_value=[]):
            result = handle_leaderboard_command("456")
            assert "Not enough data" in result

    def test_with_leaders(self, mock_sync_session):
        with (
            patch(
                "notifications.vote_db.get_leaderboard",
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
            ),
            patch(
                "notifications.vote_db.get_llm_vs_crowd_stats",
                return_value={"total_evaluated": 0},
            ),
        ):
            result = handle_leaderboard_command("456")
            assert "TraderJoe" in result
            assert "CryptoKing" in result
            assert "80" in result

    def test_with_llm_comparison(self, mock_sync_session):
        with (
            patch(
                "notifications.vote_db.get_leaderboard",
                return_value=[
                    {
                        "chat_id": "1",
                        "display_name": "User1",
                        "correct": 8,
                        "evaluated": 10,
                        "accuracy_pct": 80.0,
                    },
                ],
            ),
            patch(
                "notifications.vote_db.get_llm_vs_crowd_stats",
                return_value={
                    "total_evaluated": 10,
                    "llm_accuracy": 65.0,
                    "crowd_accuracy": 70.0,
                    "agreement_rate": 75.0,
                },
            ),
        ):
            result = handle_leaderboard_command("456")
            assert "LLM" in result
            assert "Crowd" in result
            assert "65" in result
            assert "70" in result


class TestMystatsAndLeaderboardRouting:
    @patch("notifications.telegram_bot.send_telegram_message")
    def test_mystats_routed(self, mock_send, mock_sync_session):
        with patch(
            "notifications.vote_db.get_user_stats",
            return_value={"total_votes": 0},
        ):
            update = {
                "message": {
                    "chat": {"id": "456", "type": "private"},
                    "text": "/mystats",
                    "from": {"username": "test"},
                }
            }
            result = process_update(update)
            assert result is not None
            assert "haven't voted" in result

    @patch("notifications.telegram_bot.send_telegram_message")
    def test_leaderboard_routed(self, mock_send, mock_sync_session):
        with patch("notifications.vote_db.get_leaderboard", return_value=[]):
            update = {
                "message": {
                    "chat": {"id": "456", "type": "private"},
                    "text": "/leaderboard",
                    "from": {"username": "test"},
                }
            }
            result = process_update(update)
            assert result is not None
            assert "Not enough data" in result
