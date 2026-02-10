"""
Tests for notifications/__main__.py CLI entry points.
"""

import argparse
from unittest.mock import patch

from notifications.__main__ import (
    cmd_check_alerts,
    cmd_list_subscribers,
    cmd_set_webhook,
    cmd_stats,
    cmd_test_alert,
    main,
)


class TestCmdCheckAlerts:
    """Test the check-alerts CLI command."""

    @patch("notifications.alert_engine.check_and_dispatch")
    def test_runs_check_and_dispatch(self, mock_dispatch):
        """Runs the alert check and returns 0."""
        mock_dispatch.return_value = {
            "predictions_found": 2,
            "alerts_sent": 1,
            "alerts_failed": 0,
            "filtered": 1,
        }

        args = argparse.Namespace()
        result = cmd_check_alerts(args)
        assert result == 0
        mock_dispatch.assert_called_once()


class TestCmdSetWebhook:
    """Test the set-webhook CLI command."""

    @patch("notifications.telegram_sender.set_webhook")
    def test_sets_webhook_successfully(self, mock_set):
        """Sets webhook and returns 0."""
        mock_set.return_value = (True, None)

        args = argparse.Namespace(url="https://example.com/webhook")
        result = cmd_set_webhook(args)
        assert result == 0

    @patch("notifications.telegram_sender.set_webhook")
    def test_returns_1_on_failure(self, mock_set):
        """Returns 1 when webhook fails."""
        mock_set.return_value = (False, "Token not configured")

        args = argparse.Namespace(url="https://example.com/webhook")
        result = cmd_set_webhook(args)
        assert result == 1


class TestCmdTestAlert:
    """Test the test-alert CLI command."""

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    def test_sends_test_alert(self, mock_format, mock_send):
        """Sends test alert and returns 0."""
        mock_format.return_value = "Test message"
        mock_send.return_value = (True, None)

        args = argparse.Namespace(chat_id="123456")
        result = cmd_test_alert(args)
        assert result == 0

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    def test_returns_1_on_send_failure(self, mock_format, mock_send):
        """Returns 1 when send fails."""
        mock_format.return_value = "Test message"
        mock_send.return_value = (False, "Chat not found")

        args = argparse.Namespace(chat_id="123456")
        result = cmd_test_alert(args)
        assert result == 1


class TestCmdListSubscribers:
    """Test the list-subscribers CLI command."""

    @patch("notifications.db.get_active_subscriptions")
    def test_lists_subscribers(self, mock_subs):
        """Lists active subscribers."""
        mock_subs.return_value = [
            {
                "chat_id": "123",
                "chat_type": "private",
                "username": "testuser",
                "first_name": "Test",
                "title": None,
                "alerts_sent_count": 5,
                "consecutive_errors": 0,
            }
        ]

        args = argparse.Namespace()
        result = cmd_list_subscribers(args)
        assert result == 0

    @patch("notifications.db.get_active_subscriptions")
    def test_handles_no_subscribers(self, mock_subs):
        """Handles empty subscriber list."""
        mock_subs.return_value = []

        args = argparse.Namespace()
        result = cmd_list_subscribers(args)
        assert result == 0


class TestCmdStats:
    """Test the stats CLI command."""

    @patch("notifications.db.get_subscription_stats")
    def test_shows_stats(self, mock_stats):
        """Shows subscription statistics."""
        mock_stats.return_value = {
            "total": 10,
            "active": 8,
            "private_chats": 6,
            "groups": 2,
            "channels": 0,
            "total_alerts_sent": 150,
        }

        args = argparse.Namespace()
        result = cmd_stats(args)
        assert result == 0


class TestMain:
    """Test the main CLI entry point."""

    def test_no_command_returns_1(self):
        """Returns 1 when no command given."""
        with patch("sys.argv", ["notifications"]):
            result = main()
            assert result == 1
