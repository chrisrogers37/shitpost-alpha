"""
Tests for notifications/telegram_bot.py.
Covers command handlers, update routing, and /stats, /latest commands.
"""

from datetime import datetime
from unittest.mock import patch

from notifications.telegram_bot import (
    handle_help_command,
    handle_latest_command,
    handle_settings_command,
    handle_start_command,
    handle_stats_command,
    handle_status_command,
    handle_stop_command,
    process_update,
)


class TestHandleStartCommand:
    """Test /start command handler."""

    @patch("notifications.telegram_bot.create_subscription")
    def test_returns_welcome_message(self, mock_create):
        """Returns welcome message on successful subscription."""
        mock_create.return_value = True

        result = handle_start_command(
            chat_id="123456",
            chat_type="private",
            user_info={"first_name": "John", "username": "johndoe"},
        )
        assert "Welcome" in result
        assert "John" in result
        mock_create.assert_called_once()

    @patch("notifications.telegram_bot.create_subscription")
    def test_returns_error_on_failure(self, mock_create):
        """Returns error message on subscription failure."""
        mock_create.return_value = False

        result = handle_start_command(
            chat_id="123456",
            chat_type="private",
            user_info={},
        )
        assert "Failed" in result or "\u274c" in result


class TestHandleStopCommand:
    """Test /stop command handler."""

    @patch("notifications.telegram_bot.deactivate_subscription")
    def test_returns_unsubscribe_message(self, mock_deactivate):
        """Returns unsubscribe confirmation."""
        mock_deactivate.return_value = True

        result = handle_stop_command("123456")
        assert "unsubscribed" in result.lower() or "\U0001f44b" in result


class TestHandleStatusCommand:
    """Test /status command handler."""

    @patch("notifications.telegram_bot.get_subscription")
    def test_shows_active_status(self, mock_get):
        """Shows active subscription status."""
        mock_get.return_value = {
            "is_active": True,
            "alerts_sent_count": 42,
            "subscribed_at": datetime(2024, 1, 15),
            "last_alert_at": datetime(2024, 1, 20, 10, 30),
            "alert_preferences": {
                "min_confidence": 0.8,
                "assets_of_interest": ["AAPL"],
                "sentiment_filter": "bullish",
            },
        }

        result = handle_status_command("123456")
        assert "Active" in result
        assert "42" in result
        assert "80%" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_shows_not_subscribed(self, mock_get):
        """Shows not subscribed message for unknown user."""
        mock_get.return_value = None

        result = handle_status_command("123456")
        assert "not subscribed" in result.lower() or "/start" in result


class TestHandleSettingsCommand:
    """Test /settings command handler."""

    @patch("notifications.telegram_bot.get_subscription")
    def test_shows_current_settings(self, mock_get):
        """Shows current settings when no args provided."""
        mock_get.return_value = {
            "alert_preferences": {
                "min_confidence": 0.7,
                "assets_of_interest": [],
                "sentiment_filter": "all",
                "quiet_hours_enabled": False,
            }
        }

        result = handle_settings_command("123456", "")
        assert "Settings" in result
        assert "70%" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_updates_confidence(self, mock_get, mock_update):
        """Updates confidence setting."""
        mock_get.return_value = {
            "alert_preferences": {
                "min_confidence": 0.7,
                "assets_of_interest": [],
                "sentiment_filter": "all",
            }
        }
        mock_update.return_value = True

        result = handle_settings_command("123456", "confidence 80")
        assert "80%" in result
        mock_update.assert_called_once()

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_updates_assets(self, mock_get, mock_update):
        """Updates asset filter."""
        mock_get.return_value = {
            "alert_preferences": {
                "min_confidence": 0.7,
                "assets_of_interest": [],
                "sentiment_filter": "all",
            }
        }
        mock_update.return_value = True

        result = handle_settings_command("123456", "assets AAPL TSLA")
        assert "AAPL" in result
        assert "TSLA" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed_error(self, mock_get):
        """Returns error for unsubscribed user."""
        mock_get.return_value = None

        result = handle_settings_command("123456", "")
        assert "not subscribed" in result.lower() or "/start" in result


class TestHandleHelpCommand:
    """Test /help command handler."""

    def test_returns_help_text(self):
        """Returns help text with all commands."""
        result = handle_help_command()
        assert "/start" in result
        assert "/stop" in result
        assert "/status" in result
        assert "/settings" in result
        assert "/stats" in result
        assert "/latest" in result


class TestHandleStatsCommand:
    """Test /stats command handler."""

    @patch("notifications.telegram_bot.get_prediction_stats")
    def test_returns_stats_with_data(self, mock_stats):
        """Returns formatted stats when data is available."""
        mock_stats.return_value = {
            "total_predictions": 100,
            "evaluated": 80,
            "correct": 56,
            "win_rate": 70.0,
            "total_return_pct": 12.5,
        }

        result = handle_stats_command("123456")
        assert "100" in result
        assert "70.0%" in result
        assert "12.50%" in result

    @patch("notifications.telegram_bot.get_prediction_stats")
    def test_returns_no_data_message(self, mock_stats):
        """Returns appropriate message when no data."""
        mock_stats.return_value = {"total_predictions": 0}

        result = handle_stats_command("123456")
        assert "No prediction data" in result


class TestHandleLatestCommand:
    """Test /latest command handler."""

    @patch("notifications.telegram_bot.get_latest_predictions")
    def test_returns_predictions(self, mock_latest):
        """Returns formatted recent predictions."""
        mock_latest.return_value = [
            {
                "prediction_id": 1,
                "assets": ["AAPL"],
                "confidence": 0.85,
                "market_impact": {"AAPL": "bullish"},
                "thesis": "Strong earnings",
                "created_at": "2024-01-15T10:00:00",
                "prediction_sentiment": "bullish",
                "correct_t7": True,
                "return_t7": 0.032,
                "symbol": "AAPL",
            }
        ]

        result = handle_latest_command("123456")
        assert "AAPL" in result
        assert "BULLISH" in result
        assert "\u2705" in result

    @patch("notifications.telegram_bot.get_latest_predictions")
    def test_returns_no_data_message(self, mock_latest):
        """Returns appropriate message when no predictions."""
        mock_latest.return_value = []

        result = handle_latest_command("123456")
        assert "No predictions" in result

    @patch("notifications.telegram_bot.get_latest_predictions")
    def test_handles_pending_outcome(self, mock_latest):
        """Shows pending for predictions without outcomes."""
        mock_latest.return_value = [
            {
                "prediction_id": 2,
                "assets": ["TSLA"],
                "confidence": 0.75,
                "market_impact": {"TSLA": "bearish"},
                "thesis": "Overvalued",
                "created_at": "2024-01-20T10:00:00",
                "prediction_sentiment": None,
                "correct_t7": None,
                "return_t7": None,
                "symbol": "TSLA",
            }
        ]

        result = handle_latest_command("123456")
        assert "Pending" in result


class TestProcessUpdate:
    """Test update routing."""

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.handle_start_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_start_command(self, mock_update, mock_start, mock_send):
        """Routes /start command correctly."""
        mock_start.return_value = "Welcome!"
        mock_update.return_value = True

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/start",
                "from": {"first_name": "John"},
            }
        }
        result = process_update(update)
        assert result == "Welcome!"
        mock_start.assert_called_once()

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.handle_help_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_help_command(self, mock_update, mock_help, mock_send):
        """Routes /help command correctly."""
        mock_help.return_value = "Help text"
        mock_update.return_value = True

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/help",
                "from": {},
            }
        }
        result = process_update(update)
        assert result == "Help text"

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.handle_stats_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_stats_command(self, mock_update, mock_stats, mock_send):
        """Routes /stats command correctly."""
        mock_stats.return_value = "Stats data"
        mock_update.return_value = True

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/stats",
                "from": {},
            }
        }
        result = process_update(update)
        assert result == "Stats data"

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.handle_latest_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_latest_command(self, mock_update, mock_latest, mock_send):
        """Routes /latest command correctly."""
        mock_latest.return_value = "Latest data"
        mock_update.return_value = True

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/latest",
                "from": {},
            }
        }
        result = process_update(update)
        assert result == "Latest data"

    @patch("notifications.telegram_bot.update_subscription")
    def test_ignores_non_command(self, mock_update):
        """Ignores non-command messages."""
        mock_update.return_value = True

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "Hello bot!",
                "from": {},
            }
        }
        result = process_update(update)
        assert result is None

    def test_ignores_empty_update(self):
        """Ignores updates without messages."""
        result = process_update({})
        assert result is None
