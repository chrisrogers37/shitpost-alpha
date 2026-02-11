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


class TestParseMode:
    """Test that the default parse_mode is MarkdownV2."""

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_default_parse_mode_is_markdownv2(self, mock_post, mock_token):
        """Default parse_mode should be MarkdownV2."""
        mock_token.return_value = "test_token"
        mock_post.return_value = MagicMock(json=lambda: {"ok": True})

        send_telegram_message("123456", "Test")
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["parse_mode"] == "MarkdownV2"

    @patch("notifications.telegram_sender.get_bot_token")
    @patch("notifications.telegram_sender.requests.post")
    def test_explicit_markdown_v1_override(self, mock_post, mock_token):
        """Can explicitly override to Markdown v1."""
        mock_token.return_value = "test_token"
        mock_post.return_value = MagicMock(json=lambda: {"ok": True})

        send_telegram_message("123456", "Test", parse_mode="Markdown")
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["parse_mode"] == "Markdown"


class TestFormatAlertMarkdownV2:
    """Test that format_telegram_alert produces valid MarkdownV2."""

    def test_escapes_parentheses(self):
        """Parentheses in the template are escaped for MarkdownV2."""
        alert = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["AAPL"],
            "text": "Test post.",
            "thesis": "Test thesis.",
        }
        message = format_telegram_alert(alert)
        assert "\\(" in message
        assert "\\)" in message

    def test_escapes_dots_in_disclaimer(self):
        """Dots in the disclaimer are escaped for MarkdownV2."""
        alert = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["AAPL"],
            "text": "Test.",
            "thesis": "Test.",
        }
        message = format_telegram_alert(alert)
        assert "advice\\." in message
        assert "only\\." in message

    def test_escapes_special_chars_in_assets(self):
        """Asset strings with special chars are escaped."""
        alert = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["BTC-USD"],
            "text": "Test.",
            "thesis": "Test.",
        }
        message = format_telegram_alert(alert)
        assert "BTC\\-USD" in message


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
