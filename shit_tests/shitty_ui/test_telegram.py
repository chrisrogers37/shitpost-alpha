"""
Tests for the Telegram bot handler module.
Covers subscription management, message formatting, and command handling.
"""

import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add the shitty_ui directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


# ============================================================
# Test: Message Formatting
# ============================================================


class TestFormatTelegramAlert:
    """Test Telegram alert message formatting."""

    def test_formats_bullish_alert(self):
        """Formats a bullish alert with green emoji."""
        from telegram_bot import format_telegram_alert

        alert = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["AAPL", "TSLA"],
            "text": "Great news for tech!",
            "thesis": "Strong earnings expected.",
        }
        result = format_telegram_alert(alert)
        assert "🟢" in result
        assert "BULLISH" in result
        assert "85%" in result
        assert "AAPL" in result
        assert "TSLA" in result

    def test_formats_bearish_alert(self):
        """Formats a bearish alert with red emoji."""
        from telegram_bot import format_telegram_alert

        alert = {
            "sentiment": "bearish",
            "confidence": 0.75,
            "assets": ["SPY"],
            "text": "Market downturn coming.",
            "thesis": "Recession fears.",
        }
        result = format_telegram_alert(alert)
        assert "🔴" in result
        assert "BEARISH" in result

    def test_formats_neutral_alert(self):
        """Formats a neutral alert with white emoji."""
        from telegram_bot import format_telegram_alert

        alert = {
            "sentiment": "neutral",
            "confidence": 0.6,
            "assets": [],
            "text": "Nothing significant.",
            "thesis": "Wait and see.",
        }
        result = format_telegram_alert(alert)
        assert "⚪" in result
        assert "NEUTRAL" in result

    def test_handles_empty_assets(self):
        """Handles empty assets list gracefully."""
        from telegram_bot import format_telegram_alert

        alert = {
            "sentiment": "bullish",
            "confidence": 0.8,
            "assets": [],
            "text": "General market comment.",
            "thesis": "Optimistic outlook.",
        }
        result = format_telegram_alert(alert)
        assert "None specified" in result

    def test_truncates_long_text(self):
        """Truncates long post text."""
        from telegram_bot import format_telegram_alert

        alert = {
            "sentiment": "bullish",
            "confidence": 0.8,
            "assets": ["AAPL"],
            "text": "A" * 500,
            "thesis": "B" * 300,
        }
        result = format_telegram_alert(alert)
        # Should have truncated the text
        assert len(result) < 1500


class TestEscapeMarkdown:
    """Test Markdown escaping."""

    def test_escapes_asterisk(self):
        """Escapes asterisk characters."""
        from telegram_bot import escape_markdown

        result = escape_markdown("*bold*")
        assert "\\*" in result

    def test_escapes_underscore(self):
        """Escapes underscore characters."""
        from telegram_bot import escape_markdown

        result = escape_markdown("_italic_")
        assert "\\_" in result

    def test_handles_empty_string(self):
        """Handles empty string."""
        from telegram_bot import escape_markdown

        result = escape_markdown("")
        assert result == ""

    def test_handles_none(self):
        """Handles None input."""
        from telegram_bot import escape_markdown

        result = escape_markdown(None)
        assert result == ""


# ============================================================
# Test: Command Handlers
# ============================================================


class TestHandleStartCommand:
    """Test /start command handler."""

    @patch("notifications.telegram_bot.create_subscription")
    def test_returns_welcome_message(self, mock_create):
        """Returns welcome message on successful subscription."""
        mock_create.return_value = True

        from telegram_bot import handle_start_command

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

        from telegram_bot import handle_start_command

        result = handle_start_command(
            chat_id="123456",
            chat_type="private",
            user_info={},
        )
        assert "Failed" in result or "❌" in result


class TestHandleStopCommand:
    """Test /stop command handler."""

    @patch("notifications.telegram_bot.deactivate_subscription")
    def test_returns_unsubscribe_message(self, mock_deactivate):
        """Returns unsubscribe confirmation."""
        mock_deactivate.return_value = True

        from telegram_bot import handle_stop_command

        result = handle_stop_command("123456")
        assert "unsubscribed" in result.lower() or "👋" in result


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

        from telegram_bot import handle_status_command

        result = handle_status_command("123456")
        assert "Active" in result
        assert "42" in result
        assert "80%" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_shows_not_subscribed(self, mock_get):
        """Shows not subscribed message for unknown user."""
        mock_get.return_value = None

        from telegram_bot import handle_status_command

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

        from telegram_bot import handle_settings_command

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

        from telegram_bot import handle_settings_command

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

        from telegram_bot import handle_settings_command

        result = handle_settings_command("123456", "assets AAPL TSLA")
        assert "AAPL" in result
        assert "TSLA" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed_error(self, mock_get):
        """Returns error for unsubscribed user."""
        mock_get.return_value = None

        from telegram_bot import handle_settings_command

        result = handle_settings_command("123456", "")
        assert "not subscribed" in result.lower() or "/start" in result


class TestHandleHelpCommand:
    """Test /help command handler."""

    def test_returns_help_text(self):
        """Returns help text with all commands."""
        from telegram_bot import handle_help_command

        result = handle_help_command()
        assert "/start" in result
        assert "/stop" in result
        assert "/status" in result
        assert "/settings" in result


# ============================================================
# Test: Process Update
# ============================================================


class TestProcessUpdate:
    """Test processing Telegram updates."""

    @patch("notifications.telegram_bot.handle_start_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_start_command(self, mock_update, mock_start):
        """Routes /start command correctly."""
        mock_start.return_value = "Welcome!"
        mock_update.return_value = True

        from telegram_bot import process_update

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

    @patch("notifications.telegram_bot.handle_help_command")
    @patch("notifications.telegram_bot.update_subscription")
    def test_routes_help_command(self, mock_update, mock_help):
        """Routes /help command correctly."""
        mock_help.return_value = "Help text"
        mock_update.return_value = True

        from telegram_bot import process_update

        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "text": "/help",
                "from": {},
            }
        }
        result = process_update(update)
        assert result == "Help text"

    @patch("notifications.telegram_bot.update_subscription")
    def test_ignores_non_command(self, mock_update):
        """Ignores non-command messages."""
        mock_update.return_value = True

        from telegram_bot import process_update

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
        from telegram_bot import process_update

        result = process_update({})
        assert result is None


# ============================================================
# Test: Telegram API Calls
# ============================================================


class TestSendTelegramMessage:
    """Test sending Telegram messages."""

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_sends_message_successfully(self, mock_post, mock_token):
        """Sends message and returns success."""
        mock_token.return_value = "test_token"
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": True, "result": {"message_id": 123}}
        )

        from telegram_bot import send_telegram_message

        success, error = send_telegram_message("123456", "Test message")
        assert success is True
        assert error is None

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_handles_api_error(self, mock_post, mock_token):
        """Handles Telegram API error response."""
        mock_token.return_value = "test_token"
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": False, "description": "Chat not found"}
        )

        from telegram_bot import send_telegram_message

        success, error = send_telegram_message("123456", "Test message")
        assert success is False
        assert "Chat not found" in error

    @patch("notifications.telegram_sender.get_bot_token")
    def test_fails_without_token(self, mock_token):
        """Fails gracefully when token not configured."""
        mock_token.return_value = None

        from telegram_bot import send_telegram_message

        success, error = send_telegram_message("123456", "Test message")
        assert success is False
        assert "not configured" in error.lower()


# ============================================================
# Test: Database Model
# ============================================================


class TestTelegramSubscriptionModel:
    """Test TelegramSubscription database model."""

    def test_model_has_required_fields(self):
        """Model has all required fields."""
        from shitvault.shitpost_models import TelegramSubscription

        # Check that the model has the expected columns
        columns = [c.name for c in TelegramSubscription.__table__.columns]

        required = [
            "id",
            "chat_id",
            "chat_type",
            "username",
            "first_name",
            "is_active",
            "alert_preferences",
            "last_alert_at",
            "alerts_sent_count",
            "consecutive_errors",
        ]

        for field in required:
            assert field in columns, f"Missing field: {field}"

    def test_get_display_name_private(self):
        """get_display_name returns username for private chats."""
        from shitvault.shitpost_models import TelegramSubscription

        sub = TelegramSubscription(
            chat_id="123",
            chat_type="private",
            username="johndoe",
            first_name="John",
        )
        assert sub.get_display_name() == "@johndoe"

    def test_get_display_name_group(self):
        """get_display_name returns title for groups."""
        from shitvault.shitpost_models import TelegramSubscription

        sub = TelegramSubscription(
            chat_id="-123",
            chat_type="group",
            title="Trading Signals",
        )
        assert sub.get_display_name() == "Trading Signals"

    def test_get_display_name_fallback(self):
        """get_display_name falls back to first_name then chat_id."""
        from shitvault.shitpost_models import TelegramSubscription

        sub = TelegramSubscription(
            chat_id="123",
            chat_type="private",
            first_name="John",
        )
        assert sub.get_display_name() == "John"

        sub2 = TelegramSubscription(
            chat_id="456",
            chat_type="private",
        )
        assert "456" in sub2.get_display_name()


# ============================================================
# Test: Broadcast Alert
# ============================================================


class TestBroadcastAlert:
    """Test broadcasting alerts to subscribers."""

    @patch("telegram_bot.send_alert_to_subscriber", create=True)
    @patch("notifications.alert_engine.filter_predictions_by_preferences")
    @patch("notifications.alert_engine.is_in_quiet_hours")
    @patch("telegram_bot.get_active_subscriptions")
    def test_broadcasts_to_matching_subscribers(
        self, mock_get_subs, mock_quiet, mock_filter, mock_send
    ):
        """Broadcasts to subscribers whose preferences match."""
        mock_get_subs.return_value = [
            {
                "chat_id": "123",
                "alert_preferences": {"min_confidence": 0.7},
            }
        ]
        mock_quiet.return_value = False
        mock_filter.return_value = [{"prediction_id": 1}]  # Matched
        mock_send.return_value = True

        from telegram_bot import broadcast_alert

        alert = {"confidence": 0.85, "assets": ["AAPL"]}
        result = broadcast_alert(alert)

        assert result["sent"] == 1
        assert result["failed"] == 0

    @patch("notifications.alert_engine.is_in_quiet_hours")
    @patch("telegram_bot.get_active_subscriptions")
    def test_respects_quiet_hours(self, mock_get_subs, mock_quiet):
        """Filters out subscribers in quiet hours."""
        mock_get_subs.return_value = [
            {
                "chat_id": "123",
                "alert_preferences": {"quiet_hours_enabled": True},
            }
        ]
        mock_quiet.return_value = True

        from telegram_bot import broadcast_alert

        alert = {"confidence": 0.85}
        result = broadcast_alert(alert)

        assert result["filtered"] == 1
        assert result["sent"] == 0
