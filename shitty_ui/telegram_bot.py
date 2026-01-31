"""
Telegram Bot Handler for Shitpost Alpha Alerts.

Multi-tenant architecture: One bot serves many users/groups.
Each subscription has its own alert preferences stored in the database.

Bot Commands:
    /start - Subscribe to alerts
    /stop - Unsubscribe from alerts
    /status - Check subscription status
    /settings - View/modify alert preferences
    /help - Show available commands
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Telegram API base URL
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def get_bot_token() -> Optional[str]:
    """Get Telegram bot token from settings."""
    try:
        from shit.config.shitpost_settings import settings

        return settings.TELEGRAM_BOT_TOKEN
    except ImportError:
        logger.error("Could not import settings for Telegram configuration")
        return None


# ============================================================
# Database Operations
# ============================================================


def get_subscription(chat_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a Telegram subscription by chat_id.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Subscription dict or None if not found
    """
    try:
        from data import execute_query

        query = text("""
            SELECT
                id, chat_id, chat_type, username, first_name, last_name,
                title, is_active, subscribed_at, unsubscribed_at,
                alert_preferences, last_alert_at, alerts_sent_count,
                last_interaction_at, consecutive_errors, last_error,
                created_at, updated_at
            FROM telegram_subscriptions
            WHERE chat_id = :chat_id
        """)
        rows, columns = execute_query(query, {"chat_id": str(chat_id)})
        if rows:
            return dict(zip(columns, rows[0]))
        return None
    except Exception as e:
        logger.error(f"Error getting subscription for chat_id {chat_id}: {e}")
        return None


def get_active_subscriptions() -> List[Dict[str, Any]]:
    """
    Get all active Telegram subscriptions.

    Returns:
        List of subscription dicts
    """
    try:
        from data import execute_query

        query = text("""
            SELECT
                id, chat_id, chat_type, username, first_name, last_name,
                title, is_active, subscribed_at, alert_preferences,
                last_alert_at, alerts_sent_count, consecutive_errors
            FROM telegram_subscriptions
            WHERE is_active = true
                AND consecutive_errors < 5
            ORDER BY subscribed_at ASC
        """)
        rows, columns = execute_query(query)
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error getting active subscriptions: {e}")
        return []


def create_subscription(
    chat_id: str,
    chat_type: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    title: Optional[str] = None,
) -> bool:
    """
    Create a new Telegram subscription.

    Args:
        chat_id: Telegram chat ID
        chat_type: Type of chat (private, group, supergroup, channel)
        username: Optional username
        first_name: Optional first name
        last_name: Optional last name
        title: Optional group/channel title

    Returns:
        True if created successfully
    """
    try:
        from data import execute_query

        # Check if subscription already exists
        existing = get_subscription(chat_id)
        if existing:
            # Reactivate if inactive
            if not existing.get("is_active"):
                return update_subscription(
                    chat_id, is_active=True, unsubscribed_at=None
                )
            return True  # Already active

        query = text("""
            INSERT INTO telegram_subscriptions (
                chat_id, chat_type, username, first_name, last_name, title,
                is_active, subscribed_at, alert_preferences,
                alerts_sent_count, consecutive_errors,
                created_at, updated_at
            ) VALUES (
                :chat_id, :chat_type, :username, :first_name, :last_name, :title,
                true, NOW(), :alert_preferences,
                0, 0,
                NOW(), NOW()
            )
        """)

        default_prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }

        import json

        execute_query(
            query,
            {
                "chat_id": str(chat_id),
                "chat_type": chat_type,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "alert_preferences": json.dumps(default_prefs),
            },
        )
        logger.info(f"Created Telegram subscription for chat_id {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating subscription for chat_id {chat_id}: {e}")
        return False


def update_subscription(chat_id: str, **kwargs) -> bool:
    """
    Update a Telegram subscription.

    Args:
        chat_id: Telegram chat ID
        **kwargs: Fields to update

    Returns:
        True if updated successfully
    """
    try:
        from data import execute_query

        if not kwargs:
            return True

        # Build dynamic UPDATE query
        set_clauses = []
        params = {"chat_id": str(chat_id)}

        for key, value in kwargs.items():
            if key == "alert_preferences" and isinstance(value, dict):
                import json

                value = json.dumps(value)
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        set_clauses.append("updated_at = NOW()")

        query = text(f"""
            UPDATE telegram_subscriptions
            SET {", ".join(set_clauses)}
            WHERE chat_id = :chat_id
        """)

        execute_query(query, params)
        logger.info(f"Updated Telegram subscription for chat_id {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating subscription for chat_id {chat_id}: {e}")
        return False


def deactivate_subscription(chat_id: str) -> bool:
    """Deactivate (unsubscribe) a Telegram subscription."""
    return update_subscription(
        chat_id, is_active=False, unsubscribed_at=datetime.utcnow()
    )


def record_alert_sent(chat_id: str) -> bool:
    """Record that an alert was sent to this subscription."""
    try:
        from data import execute_query

        query = text("""
            UPDATE telegram_subscriptions
            SET last_alert_at = NOW(),
                alerts_sent_count = alerts_sent_count + 1,
                consecutive_errors = 0,
                updated_at = NOW()
            WHERE chat_id = :chat_id
        """)
        execute_query(query, {"chat_id": str(chat_id)})
        return True
    except Exception as e:
        logger.error(f"Error recording alert sent for chat_id {chat_id}: {e}")
        return False


def record_error(chat_id: str, error_message: str) -> bool:
    """Record an error for this subscription."""
    try:
        from data import execute_query

        query = text("""
            UPDATE telegram_subscriptions
            SET consecutive_errors = consecutive_errors + 1,
                last_error = :error_message,
                updated_at = NOW()
            WHERE chat_id = :chat_id
        """)
        execute_query(query, {"chat_id": str(chat_id), "error_message": error_message})
        return True
    except Exception as e:
        logger.error(f"Error recording error for chat_id {chat_id}: {e}")
        return False


def get_subscription_stats() -> Dict[str, Any]:
    """Get statistics about Telegram subscriptions."""
    try:
        from data import execute_query

        query = text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active,
                COUNT(CASE WHEN chat_type = 'private' THEN 1 END) as private_chats,
                COUNT(CASE WHEN chat_type IN ('group', 'supergroup') THEN 1 END) as groups,
                COUNT(CASE WHEN chat_type = 'channel' THEN 1 END) as channels,
                SUM(alerts_sent_count) as total_alerts_sent
            FROM telegram_subscriptions
        """)
        rows, columns = execute_query(query)
        if rows:
            return dict(zip(columns, rows[0]))
        return {}
    except Exception as e:
        logger.error(f"Error getting subscription stats: {e}")
        return {}


# ============================================================
# Telegram API Calls
# ============================================================


def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    disable_notification: bool = False,
    reply_markup: Optional[Dict] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID
        text: Message text (supports Markdown)
        parse_mode: "Markdown" or "HTML"
        disable_notification: Send silently
        reply_markup: Optional inline keyboard

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Telegram bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="sendMessage")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }

    if reply_markup:
        import json

        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        if data.get("ok"):
            return True, None
        else:
            error = data.get("description", "Unknown error")
            logger.error(f"Telegram API error for chat_id {chat_id}: {error}")
            return False, error

    except requests.exceptions.Timeout:
        logger.error(f"Telegram API timeout for chat_id {chat_id}")
        return False, "Request timeout"
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API request error for chat_id {chat_id}: {e}")
        return False, str(e)
    except Exception as e:
        logger.error(f"Unexpected error sending to chat_id {chat_id}: {e}")
        return False, str(e)


def send_alert_to_subscriber(
    subscription: Dict[str, Any],
    alert: Dict[str, Any],
) -> bool:
    """
    Send an alert to a specific subscriber.

    Args:
        subscription: Subscription dict from database
        alert: Alert dict with prediction data

    Returns:
        True if sent successfully
    """
    chat_id = subscription["chat_id"]

    # Format the alert message
    message = format_telegram_alert(alert)

    success, error = send_telegram_message(chat_id, message)

    if success:
        record_alert_sent(chat_id)
        return True
    else:
        record_error(chat_id, error or "Unknown error")
        return False


def broadcast_alert(alert: Dict[str, Any]) -> Dict[str, int]:
    """
    Broadcast an alert to all active subscribers whose preferences match.

    Args:
        alert: Alert dict with prediction data

    Returns:
        Dict with counts: {"sent": N, "failed": N, "filtered": N}
    """
    from alerts import filter_predictions_by_preferences, is_in_quiet_hours

    subscriptions = get_active_subscriptions()
    results = {"sent": 0, "failed": 0, "filtered": 0}

    for sub in subscriptions:
        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            import json

            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        # Check quiet hours
        if is_in_quiet_hours(prefs):
            results["filtered"] += 1
            continue

        # Check if alert matches preferences
        # Wrap alert in list for filter function
        matched = filter_predictions_by_preferences([alert], prefs)
        if not matched:
            results["filtered"] += 1
            continue

        # Send the alert
        if send_alert_to_subscriber(sub, alert):
            results["sent"] += 1
        else:
            results["failed"] += 1

    logger.info(
        f"Telegram broadcast complete: {results['sent']} sent, "
        f"{results['failed']} failed, {results['filtered']} filtered"
    )
    return results


def format_telegram_alert(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into a Telegram message with Markdown.

    Args:
        alert: Alert dict

    Returns:
        Formatted message string
    """
    sentiment = alert.get("sentiment", "neutral").upper()
    confidence = alert.get("confidence", 0)
    confidence_pct = f"{confidence:.0%}" if confidence else "N/A"
    assets = alert.get("assets", [])
    assets_str = ", ".join(assets[:5]) if assets else "None specified"
    text = alert.get("text", "")[:300]
    thesis = alert.get("thesis", "")[:200]

    # Sentiment emoji
    if sentiment == "BULLISH":
        emoji = "🟢"
    elif sentiment == "BEARISH":
        emoji = "🔴"
    else:
        emoji = "⚪"

    message = f"""
{emoji} *SHITPOST ALPHA ALERT*

*Sentiment:* {sentiment} ({confidence_pct} confidence)
*Assets:* {assets_str}

📝 *Post:*
_{escape_markdown(text)}_

💡 *Thesis:*
{escape_markdown(thesis)}

⚠️ _This is NOT financial advice. For entertainment only._
"""
    return message.strip()


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters."""
    if not text:
        return ""
    # Escape special characters for Telegram Markdown
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


# ============================================================
# Bot Command Handlers
# ============================================================


def handle_start_command(chat_id: str, chat_type: str, user_info: Dict) -> str:
    """
    Handle /start command - Subscribe to alerts.

    Args:
        chat_id: Telegram chat ID
        chat_type: Type of chat
        user_info: User/chat info from Telegram

    Returns:
        Response message
    """
    username = user_info.get("username")
    first_name = user_info.get("first_name")
    last_name = user_info.get("last_name")
    title = user_info.get("title")  # For groups/channels

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
🎉 *Welcome to Shitpost Alpha Alerts, {name}\\!*

You're now subscribed to receive real\\-time prediction alerts\\.

*Default settings:*
• Minimum confidence: 70%
• Assets: All
• Sentiment: All

*Commands:*
/settings \\- View/change your preferences
/status \\- Check subscription status
/stop \\- Unsubscribe from alerts
/help \\- Show all commands

_Alerts will be sent when new high\\-confidence predictions are detected\\._
"""
    else:
        return "❌ Failed to subscribe. Please try again later."


def handle_stop_command(chat_id: str) -> str:
    """Handle /stop command - Unsubscribe from alerts."""
    success = deactivate_subscription(chat_id)

    if success:
        return """
👋 *You've been unsubscribed from Shitpost Alpha Alerts\\.*

You will no longer receive prediction alerts\\.

To resubscribe, send /start anytime\\.
"""
    else:
        return "❌ Failed to unsubscribe. Please try again later."


def handle_status_command(chat_id: str) -> str:
    """Handle /status command - Check subscription status."""
    sub = get_subscription(chat_id)

    if not sub:
        return """
❓ *You're not subscribed to alerts\\.*

Send /start to subscribe\\.
"""

    is_active = sub.get("is_active", False)
    alerts_sent = sub.get("alerts_sent_count", 0)
    subscribed_at = sub.get("subscribed_at")
    last_alert = sub.get("last_alert_at")
    prefs = sub.get("alert_preferences", {})

    if isinstance(prefs, str):
        import json

        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    status_emoji = "✅" if is_active else "❌"
    status_text = "Active" if is_active else "Inactive"

    # Format dates
    sub_date = subscribed_at.strftime("%Y-%m-%d") if subscribed_at else "Unknown"
    last_alert_str = last_alert.strftime("%Y-%m-%d %H:%M") if last_alert else "Never"

    # Format preferences
    min_conf = prefs.get("min_confidence", 0.7)
    assets = prefs.get("assets_of_interest", [])
    assets_str = ", ".join(assets) if assets else "All"
    sentiment = prefs.get("sentiment_filter", "all").capitalize()

    return f"""
📊 *Subscription Status*

{status_emoji} *Status:* {status_text}
📅 *Subscribed:* {sub_date}
📬 *Alerts received:* {alerts_sent}
🕐 *Last alert:* {last_alert_str}

*Your Preferences:*
• Min confidence: {min_conf:.0%}
• Assets: {assets_str}
• Sentiment: {sentiment}

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
        return "❓ You're not subscribed. Send /start first."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        import json

        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    args = args.strip().lower()

    if not args:
        # Show current settings
        min_conf = prefs.get("min_confidence", 0.7)
        assets = prefs.get("assets_of_interest", [])
        assets_str = ", ".join(assets) if assets else "All"
        sentiment = prefs.get("sentiment_filter", "all").capitalize()
        quiet = prefs.get("quiet_hours_enabled", False)
        quiet_str = "Enabled" if quiet else "Disabled"

        return f"""
⚙️ *Your Alert Settings*

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
            return f"✅ Minimum confidence set to {conf}%"
        except ValueError:
            return "Invalid confidence value. Use a number 0-100."

    elif setting_type == "assets":
        if not values:
            return "Usage: `/settings assets AAPL TSLA` or `/settings assets all`"
        if values[0] == "all":
            prefs["assets_of_interest"] = []
            update_subscription(chat_id, alert_preferences=prefs)
            return "✅ Asset filter removed. You'll receive alerts for all assets."
        else:
            assets = [v.upper() for v in values]
            prefs["assets_of_interest"] = assets
            update_subscription(chat_id, alert_preferences=prefs)
            return f"✅ Asset filter set to: {', '.join(assets)}"

    elif setting_type == "sentiment":
        if not values:
            return "Usage: `/settings sentiment bullish`"
        sentiment = values[0].lower()
        if sentiment not in ["all", "bullish", "bearish", "neutral"]:
            return "Sentiment must be: all, bullish, bearish, or neutral"
        prefs["sentiment_filter"] = sentiment
        update_subscription(chat_id, alert_preferences=prefs)
        return f"✅ Sentiment filter set to: {sentiment.capitalize()}"

    else:
        return "Unknown setting. Use: confidence, assets, or sentiment"


def handle_help_command() -> str:
    """Handle /help command."""
    return """
🤖 *Shitpost Alpha Bot Commands*

/start \\- Subscribe to alerts
/stop \\- Unsubscribe from alerts
/status \\- Check your subscription status
/settings \\- View/change alert preferences
/help \\- Show this help message

*Settings Examples:*
`/settings confidence 80`
`/settings assets AAPL TSLA`
`/settings sentiment bullish`

*About:*
This bot sends alerts when our LLM detects high\\-confidence trading signals from Trump's Truth Social posts\\.

⚠️ _Not financial advice\\. For entertainment only\\._
"""


def process_update(update: Dict[str, Any]) -> Optional[str]:
    """
    Process an incoming Telegram update (webhook or polling).

    Args:
        update: Telegram update object

    Returns:
        Response message to send, or None if no response needed
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

    # Parse command
    if not text.startswith("/"):
        return None

    parts = text.split(maxsplit=1)
    command = parts[0].lower().split("@")[0]  # Remove @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    user_info = {
        "username": from_user.get("username"),
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "title": chat.get("title"),  # For groups
    }

    if command == "/start":
        return handle_start_command(chat_id, chat_type, user_info)
    elif command == "/stop":
        return handle_stop_command(chat_id)
    elif command == "/status":
        return handle_status_command(chat_id)
    elif command == "/settings":
        return handle_settings_command(chat_id, args)
    elif command == "/help":
        return handle_help_command()
    else:
        return None  # Ignore unknown commands
