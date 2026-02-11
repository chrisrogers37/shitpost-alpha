"""
Telegram Bot command handlers for Shitpost Alpha.

Handles /start, /stop, /status, /settings, /stats, /latest, /help commands
and routes incoming webhook updates to the appropriate handler.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from notifications.db import (
    create_subscription,
    deactivate_subscription,
    get_latest_predictions,
    get_prediction_stats,
    get_subscription,
    update_subscription,
)
from notifications.telegram_sender import send_telegram_message
from shit.logging import get_service_logger

logger = get_service_logger("telegram_bot")


# ============================================================
# Command Handlers
# ============================================================


def handle_start_command(chat_id: str, chat_type: str, user_info: Dict) -> str:
    """
    Handle /start command - Subscribe to alerts.

    Args:
        chat_id: Telegram chat ID.
        chat_type: Type of chat.
        user_info: User/chat info from Telegram.

    Returns:
        Response message.
    """
    username = user_info.get("username")
    first_name = user_info.get("first_name")
    last_name = user_info.get("last_name")
    title = user_info.get("title")

    success = create_subscription(
        chat_id=chat_id,
        chat_type=chat_type,
        username=username,
        first_name=first_name,
        last_name=last_name,
        title=title,
    )

    if success:
        name = first_name or username or "there"
        return f"""
\U0001f389 *Welcome to Shitpost Alpha Alerts, {name}\\!*

You're now subscribed to receive real\\-time prediction alerts\\.

*Default settings:*
\u2022 Minimum confidence: 70%
\u2022 Assets: All
\u2022 Sentiment: All

*Commands:*
/settings \\- View/change your preferences
/status \\- Check subscription status
/stats \\- View prediction accuracy
/latest \\- Show recent predictions
/stop \\- Unsubscribe from alerts
/help \\- Show all commands

_Alerts will be sent when new high\\-confidence predictions are detected\\._
"""
    else:
        return "\u274c Failed to subscribe. Please try again later."


def handle_stop_command(chat_id: str) -> str:
    """Handle /stop command - Unsubscribe from alerts."""
    success = deactivate_subscription(chat_id)

    if success:
        return """
\U0001f44b *You've been unsubscribed from Shitpost Alpha Alerts\\.*

You will no longer receive prediction alerts\\.

To resubscribe, send /start anytime\\.
"""
    else:
        return "\u274c Failed to unsubscribe. Please try again later."


def handle_status_command(chat_id: str) -> str:
    """Handle /status command - Check subscription status."""
    sub = get_subscription(chat_id)

    if not sub:
        return """
\u2753 *You're not subscribed to alerts\\.*

Send /start to subscribe\\.
"""

    is_active = sub.get("is_active", False)
    alerts_sent = sub.get("alerts_sent_count", 0)
    subscribed_at = sub.get("subscribed_at")
    last_alert = sub.get("last_alert_at")
    prefs = sub.get("alert_preferences", {})

    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    status_emoji = "\u2705" if is_active else "\u274c"
    status_text = "Active" if is_active else "Inactive"

    sub_date = subscribed_at.strftime("%Y-%m-%d") if subscribed_at else "Unknown"
    last_alert_str = last_alert.strftime("%Y-%m-%d %H:%M") if last_alert else "Never"

    min_conf = prefs.get("min_confidence", 0.7)
    assets = prefs.get("assets_of_interest", [])
    assets_str = ", ".join(assets) if assets else "All"
    sentiment = prefs.get("sentiment_filter", "all").capitalize()

    return f"""
\U0001f4ca *Subscription Status*

{status_emoji} *Status:* {status_text}
\U0001f4c5 *Subscribed:* {sub_date}
\U0001f4ec *Alerts received:* {alerts_sent}
\U0001f550 *Last alert:* {last_alert_str}

*Your Preferences:*
\u2022 Min confidence: {min_conf:.0%}
\u2022 Assets: {assets_str}
\u2022 Sentiment: {sentiment}

Use /settings to change preferences\\.
"""


def handle_settings_command(chat_id: str, args: str = "") -> str:
    """
    Handle /settings command - View/modify preferences.

    Supports:
        /settings - Show current settings
        /settings confidence 80 - Set min confidence to 80%
        /settings assets AAPL TSLA - Set assets filter
        /settings assets all - Remove assets filter
        /settings sentiment bullish - Set sentiment filter
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "\u2753 You're not subscribed. Send /start first."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    args = args.strip().lower()

    if not args:
        min_conf = prefs.get("min_confidence", 0.7)
        assets = prefs.get("assets_of_interest", [])
        assets_str = ", ".join(assets) if assets else "All"
        sentiment = prefs.get("sentiment_filter", "all").capitalize()
        quiet = prefs.get("quiet_hours_enabled", False)
        quiet_str = "Enabled" if quiet else "Disabled"

        return f"""
\u2699\ufe0f *Your Alert Settings*

*Confidence:* {min_conf:.0%}
*Assets:* {assets_str}
*Sentiment:* {sentiment}
*Quiet hours:* {quiet_str}

*To change settings:*
`/settings confidence 80` \\- Set to 80%
`/settings assets AAPL TSLA` \\- Filter to specific assets
`/settings assets all` \\- All assets
`/settings sentiment bullish` \\- bullish/bearish/neutral/all
"""

    parts = args.split()
    setting_type = parts[0]
    values = parts[1:] if len(parts) > 1 else []

    if setting_type == "confidence":
        if not values:
            return "Usage: `/settings confidence 80`"
        try:
            conf = int(values[0])
            if conf < 0 or conf > 100:
                return "Confidence must be between 0 and 100"
            prefs["min_confidence"] = conf / 100.0
            update_subscription(chat_id, alert_preferences=prefs)
            return f"\u2705 Minimum confidence set to {conf}%"
        except ValueError:
            return "Invalid confidence value. Use a number 0-100."

    elif setting_type == "assets":
        if not values:
            return "Usage: `/settings assets AAPL TSLA` or `/settings assets all`"
        if values[0] == "all":
            prefs["assets_of_interest"] = []
            update_subscription(chat_id, alert_preferences=prefs)
            return "\u2705 Asset filter removed. You'll receive alerts for all assets."
        else:
            asset_list = [v.upper() for v in values]
            prefs["assets_of_interest"] = asset_list
            update_subscription(chat_id, alert_preferences=prefs)
            return f"\u2705 Asset filter set to: {', '.join(asset_list)}"

    elif setting_type == "sentiment":
        if not values:
            return "Usage: `/settings sentiment bullish`"
        sentiment = values[0].lower()
        if sentiment not in ["all", "bullish", "bearish", "neutral"]:
            return "Sentiment must be: all, bullish, bearish, or neutral"
        prefs["sentiment_filter"] = sentiment
        update_subscription(chat_id, alert_preferences=prefs)
        return f"\u2705 Sentiment filter set to: {sentiment.capitalize()}"

    else:
        return "Unknown setting. Use: confidence, assets, or sentiment"


def handle_stats_command(chat_id: str) -> str:
    """
    Handle /stats command - Show prediction accuracy statistics.

    Queries prediction_outcomes for overall accuracy, win rate, and total P&L.
    """
    stats = get_prediction_stats()

    if not stats or stats.get("total_predictions", 0) == 0:
        return """
\U0001f4ca *Prediction Statistics*

No prediction data available yet\\.
Check back once predictions have been evaluated\\.
"""

    total = stats.get("total_predictions", 0)
    evaluated = stats.get("evaluated", 0)
    correct = stats.get("correct", 0)
    win_rate = stats.get("win_rate", 0.0)
    total_return = stats.get("total_return_pct", 0.0)

    return_emoji = "\U0001f4c8" if total_return >= 0 else "\U0001f4c9"

    return f"""
\U0001f4ca *Shitpost Alpha \\- Prediction Stats*

\U0001f3af *Total Predictions:* {total}
\u2705 *Evaluated:* {evaluated}
\U0001f3c6 *Correct:* {correct}
\U0001f4af *Win Rate:* {win_rate}%
{return_emoji} *Total Return:* {total_return:+.2f}%

_Stats based on 7\\-day outcome window\\._
"""


def handle_latest_command(chat_id: str) -> str:
    """
    Handle /latest command - Show recent completed predictions.

    Returns 3-5 most recent predictions with sentiment, confidence, assets,
    and outcome status.
    """
    predictions = get_latest_predictions(limit=5)

    if not predictions:
        return """
\U0001f4cb *Latest Predictions*

No predictions available yet\\.
"""

    lines = ["\U0001f4cb *Latest Predictions*\n"]
    for pred in predictions:
        sentiment = ""
        market_impact = pred.get("market_impact")
        if isinstance(market_impact, dict) and market_impact:
            sentiment = next(iter(market_impact.values()), "neutral")
        elif isinstance(market_impact, str):
            try:
                mi = json.loads(market_impact)
                if isinstance(mi, dict) and mi:
                    sentiment = next(iter(mi.values()), "neutral")
            except (json.JSONDecodeError, TypeError):
                sentiment = "neutral"
        sentiment = sentiment or "neutral"

        pred_sentiment = pred.get("prediction_sentiment") or sentiment
        conf = pred.get("confidence", 0)
        conf_str = f"{conf:.0%}" if conf else "N/A"

        assets = pred.get("assets", [])
        if isinstance(assets, str):
            try:
                assets = json.loads(assets)
            except (json.JSONDecodeError, TypeError):
                assets = []
        assets_str = ", ".join(assets[:3]) if assets else "\\-"

        correct = pred.get("correct_t7")
        ret = pred.get("return_t7")
        if correct is True:
            outcome = f"\u2705 {ret:+.1%}" if ret is not None else "\u2705"
        elif correct is False:
            outcome = f"\u274c {ret:+.1%}" if ret is not None else "\u274c"
        else:
            outcome = "\u23f3 Pending"

        emoji = (
            "\U0001f7e2"
            if pred_sentiment == "bullish"
            else ("\U0001f534" if pred_sentiment == "bearish" else "\u26aa")
        )

        lines.append(
            f"{emoji} *{pred_sentiment.upper()}* \\| {conf_str} \\| {assets_str}"
        )
        lines.append(f"   Outcome: {outcome}")
        lines.append("")

    lines.append("_Use /stats for overall accuracy\\._")
    return "\n".join(lines)


def handle_help_command() -> str:
    """Handle /help command."""
    return """
\U0001f916 *Shitpost Alpha Bot Commands*

/start \\- Subscribe to alerts
/stop \\- Unsubscribe from alerts
/status \\- Check your subscription status
/settings \\- View/change alert preferences
/stats \\- View prediction accuracy stats
/latest \\- Show recent predictions
/help \\- Show this help message

*Settings Examples:*
`/settings confidence 80`
`/settings assets AAPL TSLA`
`/settings sentiment bullish`

*About:*
This bot sends alerts when our LLM detects high\\-confidence trading signals from Trump's Truth Social posts\\.

\u26a0\ufe0f _Not financial advice\\. For entertainment only\\._
"""


# ============================================================
# Update Router
# ============================================================


def process_update(update: Dict[str, Any]) -> Optional[str]:
    """
    Process an incoming Telegram update (webhook or polling).

    Routes the message to the appropriate command handler and sends
    the response back to the chat.

    Args:
        update: Telegram update object.

    Returns:
        Response message, or None if no response needed.
    """
    message = update.get("message", {})
    if not message:
        return None

    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    chat_type = chat.get("type", "private")
    text = message.get("text", "")
    from_user = message.get("from", {})

    # Update last interaction
    update_subscription(chat_id, last_interaction_at=datetime.utcnow())

    if not text.startswith("/"):
        return None

    parts = text.split(maxsplit=1)
    command = parts[0].lower().split("@")[0]
    args = parts[1] if len(parts) > 1 else ""

    user_info = {
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "title": chat.get("title"),
    }

    response = None

    if command == "/start":
        response = handle_start_command(chat_id, chat_type, user_info)
    elif command == "/stop":
        response = handle_stop_command(chat_id)
    elif command == "/status":
        response = handle_status_command(chat_id)
    elif command == "/settings":
        response = handle_settings_command(chat_id, args)
    elif command == "/stats":
        response = handle_stats_command(chat_id)
    elif command == "/latest":
        response = handle_latest_command(chat_id)
    elif command == "/help":
        response = handle_help_command()

    # Send the response back to the user
    if response:
        send_telegram_message(chat_id, response)

    return response
