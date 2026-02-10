"""
Telegram Bot Handler for Shitty UI Dashboard.

Thin wrapper that delegates to the standalone notifications/ module.
Kept for backward compatibility with existing dashboard imports.
"""

import json

import requests  # noqa: F401 - kept for test mocking compatibility

from notifications.telegram_sender import (
    escape_markdown,
    format_telegram_alert,
    get_bot_token,
    send_telegram_message,
)
from notifications.db import (
    create_subscription,
    deactivate_subscription,
    get_active_subscriptions,
    get_subscription,
    get_subscription_stats,
    record_alert_sent,
    record_error,
    update_subscription,
)
from notifications.telegram_bot import (
    handle_help_command,
    handle_settings_command,
    handle_start_command,
    handle_status_command,
    handle_stop_command,
    process_update,
)


def send_alert_to_subscriber(subscription, alert):
    """Send an alert to a specific subscriber."""
    chat_id = subscription["chat_id"]
    message = format_telegram_alert(alert)
    success, error = send_telegram_message(chat_id, message)
    if success:
        record_alert_sent(chat_id)
        return True
    else:
        record_error(chat_id, error or "Unknown error")
        return False


def broadcast_alert(alert):
    """Broadcast an alert to all active subscribers whose preferences match."""
    from notifications.alert_engine import (
        filter_predictions_by_preferences,
        is_in_quiet_hours,
    )

    subscriptions = get_active_subscriptions()
    results = {"sent": 0, "failed": 0, "filtered": 0}

    for sub in subscriptions:
        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        if is_in_quiet_hours(prefs):
            results["filtered"] += 1
            continue

        matched = filter_predictions_by_preferences([alert], prefs)
        if not matched:
            results["filtered"] += 1
            continue

        if send_alert_to_subscriber(sub, alert):
            results["sent"] += 1
        else:
            results["failed"] += 1

    return results


__all__ = [
    "escape_markdown",
    "format_telegram_alert",
    "get_bot_token",
    "send_telegram_message",
    "create_subscription",
    "deactivate_subscription",
    "get_active_subscriptions",
    "get_subscription",
    "get_subscription_stats",
    "record_alert_sent",
    "record_error",
    "update_subscription",
    "handle_help_command",
    "handle_settings_command",
    "handle_start_command",
    "handle_status_command",
    "handle_stop_command",
    "process_update",
    "send_alert_to_subscriber",
    "broadcast_alert",
]
