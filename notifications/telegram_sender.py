"""
Low-level Telegram API calls for Shitpost Alpha.

Handles sending messages, formatting alerts, and escaping Markdown.
Uses the project's settings for bot token configuration.
"""

import json
from typing import Any, Dict, Optional, Tuple

import requests

from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("telegram_sender")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def get_bot_token() -> Optional[str]:
    """Get Telegram bot token from settings."""
    return settings.TELEGRAM_BOT_TOKEN


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
        chat_id: Telegram chat ID.
        text: Message text (supports Markdown).
        parse_mode: "Markdown" or "HTML".
        disable_notification: Send silently.
        reply_markup: Optional inline keyboard.

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Telegram bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="sendMessage")

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }

    if reply_markup:
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


def set_webhook(webhook_url: str) -> Tuple[bool, Optional[str]]:
    """
    Register a webhook URL with the Telegram Bot API.

    Args:
        webhook_url: The HTTPS URL to receive updates.

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Telegram bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="setWebhook")

    try:
        response = requests.post(url, json={"url": webhook_url}, timeout=10)
        data = response.json()

        if data.get("ok"):
            logger.info(f"Webhook set to {webhook_url}")
            return True, None
        else:
            error = data.get("description", "Unknown error")
            logger.error(f"Failed to set webhook: {error}")
            return False, error
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return False, str(e)


def format_telegram_alert(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into a Telegram message with Markdown.

    Args:
        alert: Alert dict with prediction data.

    Returns:
        Formatted message string.
    """
    sentiment = alert.get("sentiment", "neutral").upper()
    confidence = alert.get("confidence", 0)
    confidence_pct = f"{confidence:.0%}" if confidence else "N/A"
    assets = alert.get("assets", [])
    assets_str = ", ".join(assets[:5]) if assets else "None specified"
    text = alert.get("text", "")[:300]
    thesis = alert.get("thesis", "")[:200]

    if sentiment == "BULLISH":
        emoji = "\U0001f7e2"
    elif sentiment == "BEARISH":
        emoji = "\U0001f534"
    else:
        emoji = "\u26aa"

    message = f"""
{emoji} *SHITPOST ALPHA ALERT*

*Sentiment:* {sentiment} ({confidence_pct} confidence)
*Assets:* {assets_str}

\U0001f4dd *Post:*
_{escape_markdown(text)}_

\U0001f4a1 *Thesis:*
{escape_markdown(thesis)}

\u26a0\ufe0f _This is NOT financial advice. For entertainment only._
"""
    return message.strip()


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters for Telegram."""
    if not text:
        return ""
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
