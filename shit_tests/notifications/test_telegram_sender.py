"""
Tests for notifications/telegram_sender.py.
Covers message sending, alert formatting, and markdown escaping.
"""

from unittest.mock import MagicMock, patch

from notifications.telegram_sender import (
    escape_markdown,
    format_telegram_alert,
    send_telegram_message,
    set_webhook,
)


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

        success, error = send_telegram_message("123456", "Test message")
        assert success is False
        assert "Chat not found" in error

    @patch("notifications.telegram_sender.get_bot_token")
    def test_fails_without_token(self, mock_token):
        """Fails gracefully when token not configured."""
        mock_token.return_value = None

        success, error = send_telegram_message("123456", "Test message")
        assert success is False
        assert "not configured" in error.lower()

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_handles_timeout(self, mock_post, mock_token):
        """Handles request timeout."""
        import requests

        mock_token.return_value = "test_token"
        mock_post.side_effect = requests.exceptions.Timeout()

        success, error = send_telegram_message("123456", "Test")
        assert success is False
        assert "timeout" in error.lower()


class TestSetWebhook:
    """Test webhook registration."""

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_sets_webhook_successfully(self, mock_post, mock_token):
        """Sets webhook URL successfully."""
        mock_token.return_value = "test_token"
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": True, "description": "Webhook was set"}
        )

        success, error = set_webhook("https://example.com/webhook")
        assert success is True
        assert error is None

    @patch("notifications.telegram_sender.get_bot_token")
    def test_fails_without_token(self, mock_token):
        """Fails when token not configured."""
        mock_token.return_value = None

        success, error = set_webhook("https://example.com/webhook")
        assert success is False


class TestFormatTelegramAlert:
    """Test Telegram alert message formatting."""

    def test_formats_bullish_alert(self, sample_alert):
        """Formats a bullish alert with green emoji."""
        result = format_telegram_alert(sample_alert)
        assert "\U0001f7e2" in result
        assert "BULLISH" in result
        assert "85%" in result
        assert "AAPL" in result

    def test_formats_bearish_alert(self):
        """Formats a bearish alert with red emoji."""
        alert = {
            "sentiment": "bearish",
            "confidence": 0.75,
            "assets": ["SPY"],
            "text": "Market downturn coming.",
            "thesis": "Recession fears.",
        }
        result = format_telegram_alert(alert)
        assert "\U0001f534" in result
        assert "BEARISH" in result

    def test_formats_neutral_alert(self):
        """Formats a neutral alert with white emoji."""
        alert = {
            "sentiment": "neutral",
            "confidence": 0.6,
            "assets": [],
            "text": "Nothing significant.",
            "thesis": "Wait and see.",
        }
        result = format_telegram_alert(alert)
        assert "\u26aa" in result
        assert "NEUTRAL" in result

    def test_handles_empty_assets(self):
        """Handles empty assets list gracefully."""
        alert = {
            "sentiment": "bullish",
            "confidence": 0.8,
            "assets": [],
            "text": "General comment.",
            "thesis": "Optimistic.",
        }
        result = format_telegram_alert(alert)
        assert "None specified" in result

    def test_truncates_long_text(self):
        """Truncates long post text."""
        alert = {
            "sentiment": "bullish",
            "confidence": 0.8,
            "assets": ["AAPL"],
            "text": "A" * 500,
            "thesis": "B" * 300,
        }
        result = format_telegram_alert(alert)
        assert len(result) < 1500


class TestEscapeMarkdown:
    """Test Markdown escaping."""

    def test_escapes_asterisk(self):
        """Escapes asterisk characters."""
        result = escape_markdown("*bold*")
        assert "\\*" in result

    def test_escapes_underscore(self):
        """Escapes underscore characters."""
        result = escape_markdown("_italic_")
        assert "\\_" in result

    def test_handles_empty_string(self):
        """Handles empty string."""
        assert escape_markdown("") == ""

    def test_handles_none(self):
        """Handles None input."""
        assert escape_markdown(None) == ""
