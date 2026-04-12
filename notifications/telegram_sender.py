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
    parse_mode: str = "MarkdownV2",
    disable_notification: bool = False,
    reply_markup: Optional[Dict] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID.
        text: Message text (supports Markdown).
        parse_mode: "MarkdownV2", "Markdown", or "HTML".
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
    calibrated = alert.get("calibrated_confidence")
    if calibrated is not None and confidence:
        confidence_pct = escape_markdown(
            f"{confidence:.0%} raw / {calibrated:.0%} calibrated"
        )
    elif confidence:
        confidence_pct = escape_markdown(f"{confidence:.0%}")
    else:
        confidence_pct = "N/A"
    assets = alert.get("assets", [])
    assets_str = escape_markdown(", ".join(assets[:5])) if assets else "None specified"
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

*Sentiment:* {sentiment} \\({confidence_pct} confidence\\)
*Assets:* {assets_str}

\U0001f4dd *Post:*
_{escape_markdown(text)}_

\U0001f4a1 *Thesis:*
{escape_markdown(thesis)}

{_format_echo_section(alert)}{_format_ensemble_section(alert)}\u26a0\ufe0f _This is NOT financial advice\\. For entertainment only\\._
"""
    return message.strip()


def _format_echo_section(alert: Dict[str, Any]) -> str:
    """Format the Historical Echoes section for a Telegram alert.

    Returns an empty string if no echoes are available.
    """
    echoes = alert.get("echoes")
    if not echoes or echoes.get("count", 0) == 0:
        return ""

    lines = [f"\U0001f4ca *Historical Echoes* \\({echoes['count']} similar posts\\):"]

    if echoes.get("avg_return") is not None:
        val = escape_markdown(f"{echoes['avg_return']:+.1f}%")
        lines.append(f"\u2022 Avg T\\+7 return: {val}")

    if echoes.get("win_rate") is not None:
        wr = echoes["win_rate"] * 100
        c, ic = echoes.get("correct", 0), echoes.get("incorrect", 0)
        lines.append(
            f"\u2022 Win rate: {c}/{c + ic} \\({escape_markdown(f'{wr:.0f}%')}\\)"
        )

    if echoes.get("avg_pnl") is not None:
        val = escape_markdown(f"${echoes['avg_pnl']:+.0f}")
        lines.append(f"\u2022 Avg P&L \\($1k\\): {val}")

    pending = echoes.get("pending", 0)
    if pending > 0 and echoes.get("correct", 0) + echoes.get("incorrect", 0) == 0:
        lines = [
            lines[0],
            f"\u2022 Outcomes: {pending} pending \\(too recent to evaluate\\)",
        ]

    return "\n".join(lines) + "\n\n"


def _format_ensemble_section(alert: Dict[str, Any]) -> str:
    """Format the ensemble consensus section for a Telegram alert.

    Returns an empty string if no ensemble metadata is available.
    """
    metadata = alert.get("ensemble_metadata")
    if not metadata:
        return ""

    level = metadata.get("agreement_level", "single")
    n_succeeded = metadata.get("providers_succeeded", 1)
    n_queried = metadata.get("providers_queried", 1)

    if level == "single":
        return ""

    level_labels = {
        "unanimous": "all agree",
        "majority": "majority agree",
        "split": "split decision",
    }
    label = level_labels.get(level, level)

    line = escape_markdown(f"[{n_succeeded}/{n_queried} models, {label}]")

    # Show confidence range if available
    spread = metadata.get("confidence_spread", 0)
    if spread > 0:
        line += f" \\| spread: {escape_markdown(f'{spread:.0%}')}"

    # Note dissenting views
    dissents = metadata.get("dissenting_views", [])
    if dissents:
        notes = []
        for d in dissents[:2]:  # Max 2 dissent notes
            asset = d.get("asset", "")
            sents = d.get("sentiments", {})
            parts = [
                f"{escape_markdown(p)}: {escape_markdown(s)}" for p, s in sents.items()
            ]
            notes.append(f"{escape_markdown(asset)} \\({', '.join(parts)}\\)")
        line += "\n_Dissent: " + "; ".join(notes) + "_"

    return f"\U0001f916 {line}\n\n"


def build_vote_keyboard(prediction_id: int) -> dict:
    """Build inline keyboard with voting buttons.

    Args:
        prediction_id: ID to embed in callback_data.

    Returns:
        reply_markup dict for Telegram API.
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": "\U0001f7e2 Bull",
                    "callback_data": f"vote:{prediction_id}:bull",
                },
                {
                    "text": "\U0001f534 Bear",
                    "callback_data": f"vote:{prediction_id}:bear",
                },
                {
                    "text": "\u23ed Skip",
                    "callback_data": f"vote:{prediction_id}:skip",
                },
            ]
        ]
    }


def build_voted_keyboard(prediction_id: int, tally: dict) -> dict:
    """Build keyboard showing current vote tallies.

    Args:
        prediction_id: Prediction ID.
        tally: Dict with bull, bear, skip counts.

    Returns:
        reply_markup dict.
    """
    bull_count = tally.get("bull", 0)
    bear_count = tally.get("bear", 0)
    skip_count = tally.get("skip", 0)

    return {
        "inline_keyboard": [
            [
                {
                    "text": f"\U0001f7e2 Bull ({bull_count})",
                    "callback_data": f"vote:{prediction_id}:bull",
                },
                {
                    "text": f"\U0001f534 Bear ({bear_count})",
                    "callback_data": f"vote:{prediction_id}:bear",
                },
                {
                    "text": f"\u23ed Skip ({skip_count})",
                    "callback_data": f"vote:{prediction_id}:skip",
                },
            ]
        ]
    }


def answer_callback_query(
    callback_query_id: str,
    text: str,
    show_alert: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Answer a callback query (toast notification to the user).

    Args:
        callback_query_id: The callback query ID from Telegram.
        text: Text to show in the toast.
        show_alert: If True, show as a popup instead of a toast.

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="answerCallbackQuery")
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        return (True, None) if data.get("ok") else (False, data.get("description"))
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")
        return False, str(e)


def edit_message_reply_markup(
    chat_id: str,
    message_id: int,
    reply_markup: Optional[dict] = None,
) -> Tuple[bool, Optional[str]]:
    """Edit the inline keyboard of an existing message.

    Args:
        chat_id: Chat where the message lives.
        message_id: ID of the message to edit.
        reply_markup: New inline keyboard markup (or None to remove).

    Returns:
        Tuple of (success, error_message).
    """
    bot_token = get_bot_token()
    if not bot_token:
        return False, "Bot token not configured"

    url = TELEGRAM_API_BASE.format(token=bot_token, method="editMessageReplyMarkup")
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        return (True, None) if data.get("ok") else (False, data.get("description"))
    except Exception as e:
        logger.error(f"Error editing message reply markup: {e}")
        return False, str(e)


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
