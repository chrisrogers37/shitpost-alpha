"""Tests for weekly scorecard (Feature 12)."""

from datetime import date
from unittest.mock import patch

from notifications.scorecard_formatter import (
    format_weekly_scorecard,
    truncate_to_telegram_limit,
)
from notifications.scorecard_service import (
    generate_scorecard,
    get_current_week_range,
    send_weekly_scorecard,
)
from notifications.telegram_bot import handle_scorecard_command, process_update


# ============================================================
# Formatter Tests
# ============================================================


class TestScorecardFormatter:
    """Test format_weekly_scorecard()."""

    def _make_scorecard(self, **overrides):
        """Build a scorecard with sensible defaults."""
        defaults = {
            "week_start": date(2026, 4, 7),
            "week_end": date(2026, 4, 13),
            "prediction_stats": {
                "total_predictions": 15,
                "completed": 12,
                "bypassed": 3,
                "errors": 0,
                "avg_confidence": 0.77,
            },
            "accuracy": {
                "correct": 8,
                "incorrect": 3,
                "pending": 1,
                "bullish_correct": 5,
                "bullish_total": 7,
                "bearish_correct": 3,
                "bearish_total": 4,
            },
            "pnl": {
                "total_pnl": 187.5,
                "best_pnl": 42.0,
                "worst_pnl": -12.0,
                "trade_count": 11,
            },
            "top_wins": [
                {
                    "symbol": "TSLA",
                    "sentiment": "bullish",
                    "confidence": 0.92,
                    "return_pct": 4.2,
                    "pnl": 42.0,
                },
            ],
            "worst_misses": [
                {
                    "symbol": "F",
                    "sentiment": "bearish",
                    "confidence": 0.81,
                    "return_pct": 1.2,
                    "pnl": -12.0,
                },
            ],
            "asset_breakdown": [
                {
                    "symbol": "TSLA",
                    "signal_count": 5,
                    "accuracy_pct": 80.0,
                    "total_pnl": 67.5,
                },
            ],
        }
        defaults.update(overrides)
        return format_weekly_scorecard(**defaults)

    def test_includes_header(self):
        message = self._make_scorecard()
        assert "WEEKLY SCORECARD" in message
        assert "Apr" in message

    def test_includes_signals_section(self):
        message = self._make_scorecard()
        assert "SIGNALS" in message
        assert "15" in message  # total
        assert "12" in message  # completed

    def test_includes_accuracy(self):
        message = self._make_scorecard()
        assert "ACCURACY" in message
        assert "73%" in message  # 8/11 = 72.7%

    def test_includes_pnl(self):
        message = self._make_scorecard()
        assert "P&L" in message
        assert "187" in message

    def test_includes_top_wins(self):
        message = self._make_scorecard()
        assert "TOP WINS" in message
        assert "TSLA" in message

    def test_includes_misses(self):
        message = self._make_scorecard()
        assert "BIGGEST MISSES" in message
        assert "F" in message

    def test_includes_asset_breakdown(self):
        message = self._make_scorecard()
        assert "TOP ASSETS" in message
        assert "5 signals" in message

    def test_no_misses_when_all_positive(self):
        message = self._make_scorecard(worst_misses=[{"symbol": "TSLA", "pnl": 5.0}])
        assert "BIGGEST MISSES" not in message

    def test_footer_present(self):
        message = self._make_scorecard()
        assert "NOT financial advice" in message
        assert "/scorecard off" in message

    def test_with_leaderboard(self):
        message = self._make_scorecard(
            leaderboard=[
                {
                    "display_name": "TraderJoe",
                    "accuracy_pct": 78,
                    "correct": 7,
                    "evaluated": 9,
                },
            ],
        )
        assert "LEADERBOARD" in message
        assert "TraderJoe" in message

    def test_without_leaderboard(self):
        message = self._make_scorecard(leaderboard=None)
        assert "LEADERBOARD" not in message

    def test_with_streak(self):
        message = self._make_scorecard(
            streak_info={"streak_type": "winning", "streak_length": 3}
        )
        assert "3 winning weeks" in message

    def test_no_streak(self):
        message = self._make_scorecard(
            streak_info={"streak_type": None, "streak_length": 0}
        )
        assert "Streak" not in message

    def test_pending_shown(self):
        message = self._make_scorecard()
        assert "Pending" in message

    def test_no_pending_when_zero(self):
        accuracy = {
            "correct": 8,
            "incorrect": 3,
            "pending": 0,
            "bullish_correct": 5,
            "bullish_total": 7,
            "bearish_correct": 3,
            "bearish_total": 4,
        }
        message = self._make_scorecard(accuracy=accuracy)
        assert "Pending" not in message

    def test_under_telegram_limit(self):
        message = self._make_scorecard()
        assert len(message) <= 4096

    def test_empty_week(self):
        message = self._make_scorecard(
            prediction_stats={
                "total_predictions": 0,
                "completed": 0,
                "bypassed": 0,
                "avg_confidence": 0,
            },
            accuracy={
                "correct": 0,
                "incorrect": 0,
                "pending": 0,
                "bullish_correct": 0,
                "bullish_total": 0,
                "bearish_correct": 0,
                "bearish_total": 0,
            },
            pnl={"total_pnl": 0, "best_pnl": 0, "worst_pnl": 0, "trade_count": 0},
            top_wins=[],
            worst_misses=[],
            asset_breakdown=[],
        )
        assert "WEEKLY SCORECARD" in message
        assert "N/A" in message


class TestTruncation:
    """Test truncate_to_telegram_limit."""

    def test_short_message_unchanged(self):
        msg = "Short message"
        assert truncate_to_telegram_limit(msg) == msg

    def test_long_message_truncated(self):
        msg = "Line\n" * 2000
        result = truncate_to_telegram_limit(msg)
        assert len(result) <= 4096
        assert "truncated" in result


# ============================================================
# Service Tests
# ============================================================


class TestScorecardService:
    """Test scorecard service."""

    def test_get_current_week_range(self):
        monday, sunday = get_current_week_range()
        assert monday.weekday() == 0  # Monday
        assert sunday.weekday() == 6  # Sunday
        assert (sunday - monday).days == 6

    @patch("notifications.scorecard_service.send_telegram_message")
    @patch("notifications.scorecard_service.get_active_subscriptions")
    @patch("notifications.scorecard_service.get_weekly_streak")
    @patch("notifications.scorecard_service.get_asset_breakdown")
    @patch("notifications.scorecard_service.get_worst_misses")
    @patch("notifications.scorecard_service.get_top_wins")
    @patch("notifications.scorecard_service.get_weekly_pnl")
    @patch("notifications.scorecard_service.get_weekly_accuracy")
    @patch("notifications.scorecard_service.get_weekly_prediction_stats")
    def test_sends_to_opted_in(
        self,
        mock_stats,
        mock_acc,
        mock_pnl,
        mock_wins,
        mock_misses,
        mock_assets,
        mock_streak,
        mock_subs,
        mock_send,
    ):
        mock_stats.return_value = {
            "total_predictions": 10,
            "completed": 8,
            "bypassed": 2,
            "avg_confidence": 0.8,
        }
        mock_acc.return_value = {
            "correct": 5,
            "incorrect": 3,
            "pending": 0,
            "bullish_correct": 3,
            "bullish_total": 5,
            "bearish_correct": 2,
            "bearish_total": 3,
        }
        mock_pnl.return_value = {
            "total_pnl": 100.0,
            "best_pnl": 30.0,
            "worst_pnl": -10.0,
            "trade_count": 8,
        }
        mock_wins.return_value = []
        mock_misses.return_value = []
        mock_assets.return_value = []
        mock_streak.return_value = {"streak_type": None, "streak_length": 0}
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {"scorecard_enabled": True}},
            {"chat_id": "222", "alert_preferences": {"scorecard_enabled": False}},
        ]
        mock_send.return_value = (True, None)

        stats = send_weekly_scorecard()
        assert stats["sent"] == 1
        assert stats["skipped"] == 1

    @patch("notifications.scorecard_service.get_weekly_streak")
    @patch("notifications.scorecard_service.get_asset_breakdown")
    @patch("notifications.scorecard_service.get_worst_misses")
    @patch("notifications.scorecard_service.get_top_wins")
    @patch("notifications.scorecard_service.get_weekly_pnl")
    @patch("notifications.scorecard_service.get_weekly_accuracy")
    @patch("notifications.scorecard_service.get_weekly_prediction_stats")
    def test_generate_scorecard_returns_string(
        self,
        mock_stats,
        mock_acc,
        mock_pnl,
        mock_wins,
        mock_misses,
        mock_assets,
        mock_streak,
    ):
        mock_stats.return_value = {
            "total_predictions": 5,
            "completed": 5,
            "bypassed": 0,
            "avg_confidence": 0.75,
        }
        mock_acc.return_value = {
            "correct": 3,
            "incorrect": 2,
            "pending": 0,
            "bullish_correct": 2,
            "bullish_total": 3,
            "bearish_correct": 1,
            "bearish_total": 2,
        }
        mock_pnl.return_value = {
            "total_pnl": 50.0,
            "best_pnl": 20.0,
            "worst_pnl": -5.0,
            "trade_count": 5,
        }
        mock_wins.return_value = []
        mock_misses.return_value = []
        mock_assets.return_value = []
        mock_streak.return_value = {"streak_type": None, "streak_length": 0}

        result = generate_scorecard(date(2026, 4, 7), date(2026, 4, 13))
        assert isinstance(result, str)
        assert "WEEKLY SCORECARD" in result


# ============================================================
# Bot Command Tests
# ============================================================


class TestScorecardCommand:
    """Test /scorecard bot command."""

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed(self, mock_get_sub):
        mock_get_sub.return_value = None
        result = handle_scorecard_command("123")
        assert "not subscribed" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_scorecard_off(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"scorecard_enabled": True}}
        mock_update.return_value = True
        result = handle_scorecard_command("123", "off")
        assert "disabled" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_scorecard_on(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"scorecard_enabled": False}}
        mock_update.return_value = True
        result = handle_scorecard_command("123", "on")
        assert "enabled" in result
        assert "Sunday" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_scorecard_status(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {"scorecard_enabled": True}}
        result = handle_scorecard_command("123")
        assert "enabled" in result
        assert "Sunday" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_default_enabled(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {}}
        result = handle_scorecard_command("123")
        assert "enabled" in result


# ============================================================
# Process Update Routing
# ============================================================


class TestProcessUpdateScorecard:
    """Test /scorecard routing through process_update."""

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.get_subscription")
    def test_routes_to_scorecard_handler(self, mock_get_sub, mock_send):
        mock_get_sub.return_value = {"alert_preferences": {"scorecard_enabled": True}}
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"username": "testuser"},
                "text": "/scorecard",
            }
        }
        result = process_update(update)
        assert result is not None
        assert "enabled" in result
