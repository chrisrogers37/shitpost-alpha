"""
CLI entry point for the notifications module.

Usage:
    python -m notifications check-alerts          # Run alert check (Railway cron)
    python -m notifications set-webhook <url>     # Register webhook URL with Telegram
    python -m notifications test-alert --chat-id 123  # Send test alert
    python -m notifications list-subscribers      # Show active subscribers
    python -m notifications stats                 # Show subscription statistics
"""

import argparse
import logging
import sys

from shit.logging import setup_cli_logging

setup_cli_logging(service_name="notifications")
logger = logging.getLogger(__name__)


def cmd_check_alerts(args: argparse.Namespace) -> int:
    """Run the alert check-and-dispatch cycle."""
    from notifications.alert_engine import check_and_dispatch

    logger.info("Starting alert check...")
    results = check_and_dispatch()

    print(f"Predictions found: {results['predictions_found']}")
    print(f"Alerts sent:       {results['alerts_sent']}")
    print(f"Alerts failed:     {results['alerts_failed']}")
    print(f"Filtered out:      {results['filtered']}")

    return 0


def cmd_set_webhook(args: argparse.Namespace) -> int:
    """Register a webhook URL with the Telegram Bot API."""
    from notifications.telegram_sender import set_webhook

    url = args.url
    if not url:
        print("Error: webhook URL is required")
        return 1

    success, error = set_webhook(url)
    if success:
        print(f"Webhook set successfully: {url}")
        return 0
    else:
        print(f"Failed to set webhook: {error}")
        return 1


def cmd_test_alert(args: argparse.Namespace) -> int:
    """Send a test alert to a specific chat ID."""
    from notifications.telegram_sender import (
        format_telegram_alert,
        send_telegram_message,
    )

    chat_id = args.chat_id
    if not chat_id:
        print("Error: --chat-id is required")
        return 1

    test_alert = {
        "sentiment": "bullish",
        "confidence": 0.85,
        "assets": ["TEST"],
        "text": "This is a test alert from Shitpost Alpha.",
        "thesis": "Testing the notification system.",
    }

    message = format_telegram_alert(test_alert)
    success, error = send_telegram_message(chat_id, message)

    if success:
        print(f"Test alert sent to chat_id {chat_id}")
        return 0
    else:
        print(f"Failed to send test alert: {error}")
        return 1


def cmd_list_subscribers(args: argparse.Namespace) -> int:
    """List all active subscribers."""
    from notifications.db import get_active_subscriptions

    subs = get_active_subscriptions()

    if not subs:
        print("No active subscribers.")
        return 0

    print(f"Active subscribers: {len(subs)}\n")
    print(f"{'Chat ID':<15} {'Type':<12} {'Name':<20} {'Alerts Sent':<12} {'Errors'}")
    print("-" * 75)

    for sub in subs:
        chat_id = sub.get("chat_id", "")
        chat_type = sub.get("chat_type", "")
        name = sub.get("username") or sub.get("first_name") or sub.get("title") or "-"
        alerts = sub.get("alerts_sent_count", 0)
        errors = sub.get("consecutive_errors", 0)
        print(f"{chat_id:<15} {chat_type:<12} {name:<20} {alerts:<12} {errors}")

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show subscription statistics."""
    from notifications.db import get_subscription_stats

    stats = get_subscription_stats()

    if not stats:
        print("No subscription data available.")
        return 0

    print("Subscription Statistics")
    print("-" * 30)
    print(f"Total subscriptions: {stats.get('total', 0)}")
    print(f"Active:              {stats.get('active', 0)}")
    print(f"Private chats:       {stats.get('private_chats', 0)}")
    print(f"Groups:              {stats.get('groups', 0)}")
    print(f"Channels:            {stats.get('channels', 0)}")
    print(f"Total alerts sent:   {stats.get('total_alerts_sent', 0)}")

    return 0


def main() -> int:
    """Parse arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(
        prog="python -m notifications",
        description="Shitpost Alpha Notification Service",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check-alerts
    subparsers.add_parser(
        "check-alerts",
        help="Check for new predictions and dispatch alerts",
    )

    # set-webhook
    webhook_parser = subparsers.add_parser(
        "set-webhook",
        help="Register webhook URL with Telegram API",
    )
    webhook_parser.add_argument("url", help="The HTTPS webhook URL")

    # test-alert
    test_parser = subparsers.add_parser(
        "test-alert",
        help="Send a test alert to a specific chat",
    )
    test_parser.add_argument(
        "--chat-id", required=True, help="Telegram chat ID to send test alert to"
    )

    # list-subscribers
    subparsers.add_parser(
        "list-subscribers",
        help="List all active subscribers",
    )

    # stats
    subparsers.add_parser(
        "stats",
        help="Show subscription statistics",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "check-alerts": cmd_check_alerts,
        "set-webhook": cmd_set_webhook,
        "test-alert": cmd_test_alert,
        "list-subscribers": cmd_list_subscribers,
        "stats": cmd_stats,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
