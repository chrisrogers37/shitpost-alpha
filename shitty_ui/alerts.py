"""
Alert checking and dispatch logic for Shitty UI Dashboard.

Thin wrapper that delegates to the standalone notifications/ module.
Kept for backward compatibility with existing dashboard imports.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from notifications.alert_engine import (
    filter_predictions_by_preferences,  # noqa: F401
    is_in_quiet_hours,  # noqa: F401
    _extract_sentiment,
)
from notifications.dispatcher import (
    _validate_email,  # noqa: F401
    _validate_phone_number,  # noqa: F401
    _check_email_rate_limit,  # noqa: F401
    _check_sms_rate_limit,  # noqa: F401
    _email_sent_timestamps,  # noqa: F401
    _sms_sent_timestamps,  # noqa: F401
    _EMAIL_RATE_LIMIT,  # noqa: F401
    _SMS_RATE_LIMIT,  # noqa: F401
    _EMAIL_RATE_WINDOW,  # noqa: F401
    _SMS_RATE_WINDOW,  # noqa: F401
    send_email_alert as _send_email_alert,
    send_sms_alert as _send_sms_alert,
    _send_via_smtp,  # noqa: F401
    _send_via_sendgrid,  # noqa: F401
    _record_email_sent,  # noqa: F401
    _record_sms_sent,  # noqa: F401
    format_alert_message,
    format_alert_message_html,
)

logger = logging.getLogger(__name__)

# Default alert preferences - used when no localStorage data exists
DEFAULT_ALERT_PREFERENCES = {
    "enabled": False,
    "min_confidence": 0.7,
    "assets_of_interest": [],
    "sentiment_filter": "all",
    "browser_notifications": True,
    "email_enabled": False,
    "email_address": "",
    "sms_enabled": False,
    "sms_phone_number": "",
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "max_alerts_per_hour": 10,
}


def check_for_new_alerts(
    preferences: Dict[str, Any],
    last_check: Optional[str],
) -> Dict[str, Any]:
    """
    Check the database for new predictions that match the user's alert preferences.

    Args:
        preferences: User's alert preferences dict (from localStorage).
        last_check: ISO timestamp of the last check, or None if first check.

    Returns:
        Dict with keys:
            - "matched_alerts": list of alert dicts that matched preferences
            - "last_check": updated ISO timestamp string
            - "total_new": total new predictions found (before filtering)
    """
    from notifications.db import get_new_predictions_since

    if last_check:
        try:
            since = datetime.fromisoformat(last_check.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            since = datetime.utcnow() - timedelta(minutes=5)
    else:
        since = datetime.utcnow() - timedelta(minutes=5)

    new_predictions = get_new_predictions_since(since)
    total_new = len(new_predictions)

    if total_new == 0:
        return {
            "matched_alerts": [],
            "last_check": datetime.utcnow().isoformat(),
            "total_new": 0,
        }

    matched = filter_predictions_by_preferences(new_predictions, preferences)

    matched_alerts = []
    for pred in matched:
        alert = {
            "prediction_id": pred.get("prediction_id"),
            "shitpost_id": pred.get("shitpost_id"),
            "text": pred.get("text", "")[:200],
            "confidence": pred.get("confidence"),
            "assets": pred.get("assets", []),
            "sentiment": _extract_sentiment(pred.get("market_impact", {})),
            "thesis": pred.get("thesis", ""),
            "timestamp": pred.get("timestamp"),
            "alert_triggered_at": datetime.utcnow().isoformat(),
        }
        matched_alerts.append(alert)

    logger.info(
        f"Alert check complete: {total_new} new predictions, "
        f"{len(matched_alerts)} matched preferences"
    )

    return {
        "matched_alerts": matched_alerts,
        "last_check": datetime.utcnow().isoformat(),
        "total_new": total_new,
    }


def broadcast_telegram_alert(alert: Dict[str, Any]) -> Dict[str, int]:
    """Broadcast an alert to all active Telegram subscribers."""
    try:
        from telegram_bot import broadcast_alert

        return broadcast_alert(alert)
    except ImportError:
        logger.warning("Telegram bot module not available")
        return {"sent": 0, "failed": 0, "filtered": 0}
    except Exception as e:
        logger.error(f"Error broadcasting Telegram alert: {e}")
        return {"sent": 0, "failed": 0, "filtered": 0}


def dispatch_server_notifications(
    alert: Dict[str, Any],
    preferences: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Dispatch email, SMS, and Telegram notifications for a matched alert.

    Args:
        alert: The matched alert dict.
        preferences: User preferences dict (for email/SMS).

    Returns:
        Dict with dispatch results for each channel.
    """
    results = {
        "email_sent": False,
        "sms_sent": False,
        "telegram": {"sent": 0, "failed": 0, "filtered": 0},
    }

    if preferences.get("email_enabled") and preferences.get("email_address"):
        try:
            results["email_sent"] = _send_email_alert(
                to_email=preferences["email_address"],
                subject=f"Shitpost Alpha: {alert.get('sentiment', 'NEW').upper()} Alert",
                html_body=format_alert_message_html(alert),
                text_body=format_alert_message(alert),
            )
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    if preferences.get("sms_enabled") and preferences.get("sms_phone_number"):
        try:
            results["sms_sent"] = _send_sms_alert(
                to_phone=preferences["sms_phone_number"],
                message=format_alert_message(alert),
            )
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")

    try:
        results["telegram"] = broadcast_telegram_alert(alert)
    except Exception as e:
        logger.error(f"Failed to broadcast Telegram alert: {e}")

    return results
