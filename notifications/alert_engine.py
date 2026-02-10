"""
Core alert engine for Shitpost Alpha.

Queries for new predictions, matches them to subscriber preferences,
and dispatches alerts via Telegram. Designed to run via Railway cron
every 2 minutes, completely decoupled from the dashboard.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from notifications.db import (
    get_active_subscriptions,
    get_last_alert_check,
    get_new_predictions_since,
    record_alert_sent,
    record_error,
)
from notifications.telegram_sender import format_telegram_alert, send_telegram_message

logger = logging.getLogger(__name__)


def check_and_dispatch() -> Dict[str, Any]:
    """
    Main alert function called by cron.

    Queries for new predictions since the last check, filters per subscriber
    preferences, and dispatches via Telegram.

    Returns:
        Dict with summary: predictions_found, alerts_sent, alerts_failed, filtered.
    """
    results = {
        "predictions_found": 0,
        "alerts_sent": 0,
        "alerts_failed": 0,
        "filtered": 0,
    }

    # Determine the time window
    last_check = get_last_alert_check()
    if last_check is None:
        since = datetime.utcnow() - timedelta(minutes=5)
    else:
        since = last_check

    # Query for new predictions
    new_predictions = get_new_predictions_since(since)
    results["predictions_found"] = len(new_predictions)

    if not new_predictions:
        logger.info("No new predictions found since last check")
        return results

    logger.info(f"Found {len(new_predictions)} new predictions")

    # Build alert objects
    alerts = []
    for pred in new_predictions:
        alert = {
            "prediction_id": pred.get("prediction_id"),
            "shitpost_id": pred.get("shitpost_id"),
            "text": pred.get("text", "")[:200],
            "confidence": pred.get("confidence"),
            "assets": pred.get("assets", []),
            "sentiment": _extract_sentiment(pred.get("market_impact", {})),
            "thesis": pred.get("thesis", ""),
            "timestamp": pred.get("timestamp"),
        }
        alerts.append(alert)

    # Get active subscribers
    subscriptions = get_active_subscriptions()
    if not subscriptions:
        logger.info("No active subscribers to notify")
        return results

    # Dispatch alerts to each subscriber
    for sub in subscriptions:
        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        # Check quiet hours
        if is_in_quiet_hours(prefs):
            results["filtered"] += 1
            continue

        # Filter predictions by subscriber preferences
        matched = filter_predictions_by_preferences(alerts, prefs)
        if not matched:
            results["filtered"] += 1
            continue

        # Send each matched alert
        chat_id = sub["chat_id"]
        for alert in matched:
            message = format_telegram_alert(alert)
            success, error = send_telegram_message(chat_id, message)

            if success:
                record_alert_sent(chat_id)
                results["alerts_sent"] += 1
            else:
                record_error(chat_id, error or "Unknown error")
                results["alerts_failed"] += 1

    logger.info(
        f"Alert dispatch complete: {results['alerts_sent']} sent, "
        f"{results['alerts_failed']} failed, {results['filtered']} filtered"
    )
    return results


def filter_predictions_by_preferences(
    predictions: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Filter a list of prediction/alert dicts against subscriber preferences.

    Args:
        predictions: List of prediction/alert dicts.
        preferences: Subscriber's alert preferences dict.

    Returns:
        Filtered list of predictions that match all preference criteria.
    """
    min_confidence = preferences.get("min_confidence", 0.7)
    assets_of_interest = preferences.get("assets_of_interest", [])
    sentiment_filter = preferences.get("sentiment_filter", "all")

    matched = []
    for pred in predictions:
        # Check confidence threshold
        confidence = pred.get("confidence")
        if confidence is None or confidence < min_confidence:
            continue

        # Check asset filter (empty list = match all)
        if assets_of_interest:
            pred_assets = pred.get("assets", [])
            if not isinstance(pred_assets, list):
                pred_assets = []
            if not any(asset in assets_of_interest for asset in pred_assets):
                continue

        # Check sentiment filter
        if sentiment_filter != "all":
            pred_sentiment = pred.get("sentiment", "neutral")
            if pred_sentiment != sentiment_filter:
                continue

        matched.append(pred)

    return matched


def is_in_quiet_hours(preferences: Dict[str, Any]) -> bool:
    """
    Check if the current time falls within the subscriber's quiet hours.

    Args:
        preferences: Subscriber's alert preferences dict.

    Returns:
        True if currently in quiet hours and quiet hours are enabled.
    """
    if not preferences.get("quiet_hours_enabled", False):
        return False

    now = datetime.now()
    current_time = now.strftime("%H:%M")

    start = preferences.get("quiet_hours_start", "22:00")
    end = preferences.get("quiet_hours_end", "08:00")

    # Handle overnight quiet hours (e.g., 22:00 - 08:00)
    if start > end:
        return current_time >= start or current_time < end
    else:
        return start <= current_time < end


def _extract_sentiment(market_impact: Any) -> str:
    """
    Extract the primary sentiment from a market_impact field.

    The market_impact field is a dict mapping asset symbols to sentiment strings.

    Args:
        market_impact: Dict like {"AAPL": "bullish"} or a JSON string.

    Returns:
        Sentiment string, defaulting to "neutral".
    """
    if isinstance(market_impact, str):
        try:
            market_impact = json.loads(market_impact)
        except (json.JSONDecodeError, TypeError):
            return "neutral"

    if not isinstance(market_impact, dict) or not market_impact:
        return "neutral"

    first_value = next(iter(market_impact.values()), "neutral")
    if isinstance(first_value, str):
        return first_value.lower()
    return "neutral"
