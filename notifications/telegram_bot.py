"""
Telegram Bot command handlers for Shitpost Alpha.

Handles /start, /stop, /status, /settings, /watchlist, /briefing, /followups, /stats, /latest, /help
commands and routes incoming webhook updates to the appropriate handler.
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
from notifications.telegram_sender import escape_markdown, send_telegram_message
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
/watchlist \\- Set which tickers you want alerts for
/briefing \\- Morning briefing settings
/followups \\- Follow\\-up message settings
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
/watchlist \\- Manage your ticker watchlist
/briefing \\- Toggle morning briefing \\(8:30 AM ET\\)
/followups \\- Toggle prediction follow\\-up messages
/stats \\- View prediction accuracy stats
/latest \\- Show recent predictions
/help \\- Show this help message

*Watchlist Examples:*
`/watchlist add TSLA NVDA`
`/watchlist remove NVDA`
`/watchlist clear`

*Settings Examples:*
`/settings confidence 80`
`/settings sentiment bullish`

*About:*
This bot sends alerts when our LLM detects high\\-confidence trading signals from Trump's Truth Social posts\\.

\u26a0\ufe0f _Not financial advice\\. For entertainment only\\._
"""


# ============================================================
# Briefing Command Handler
# ============================================================


def handle_briefing_command(chat_id: str, args: str = "") -> str:
    """Handle /briefing command — toggle morning briefing.

    Args:
        chat_id: Telegram chat ID.
        args: Command arguments ("on", "off", or empty for status).

    Returns:
        Response message.
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "You're not subscribed\\. Send /start first\\."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    current = prefs.get("briefing_enabled", True)
    arg = args.strip().lower()

    if arg == "off":
        prefs["briefing_enabled"] = False
        update_subscription(chat_id, alert_preferences=prefs)
        return "Morning briefings disabled\\. Send /briefing on to re\\-enable\\."
    elif arg == "on":
        prefs["briefing_enabled"] = True
        update_subscription(chat_id, alert_preferences=prefs)
        return (
            "Morning briefings enabled\\! "
            "You'll receive a digest at 8:30 AM ET on trading days\\."
        )
    else:
        status = "enabled" if current else "disabled"
        return (
            f"Morning briefings are currently *{status}*\\.\n\n"
            "Send /briefing on or /briefing off to change\\."
        )


# ============================================================
# Follow-ups Command Handler
# ============================================================


def handle_followups_command(chat_id: str, args: str = "") -> str:
    """Handle /followups command — toggle follow-up messages.

    Args:
        chat_id: Telegram chat ID.
        args: "on", "off", or empty for status. Also "1h,1d" for selective.

    Returns:
        Response message.
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "You're not subscribed\\. Send /start first\\."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    current = prefs.get("followups_enabled", True)
    current_horizons = prefs.get("followup_horizons", ["1h", "1d", "7d"])
    arg = args.strip().lower()

    if arg == "off":
        prefs["followups_enabled"] = False
        update_subscription(chat_id, alert_preferences=prefs)
        return "Follow\\-up messages disabled\\. Send /followups on to re\\-enable\\."
    elif arg == "on":
        prefs["followups_enabled"] = True
        update_subscription(chat_id, alert_preferences=prefs)
        h_str = ", ".join(current_horizons)
        return escape_markdown(f"Follow-up messages enabled for: {h_str}")
    elif all(h in ("1h", "1d", "7d") for h in arg.replace(" ", "").split(",")):
        horizons = [
            h.strip() for h in arg.split(",") if h.strip() in ("1h", "1d", "7d")
        ]
        if horizons:
            prefs["followup_horizons"] = horizons
            prefs["followups_enabled"] = True
            update_subscription(chat_id, alert_preferences=prefs)
            return escape_markdown(f"Follow-ups set to: {', '.join(horizons)}")
    # Default: show status
    status = "enabled" if current else "disabled"
    h_str = ", ".join(current_horizons)
    return (
        f"Follow\\-ups are currently *{status}*\\.\n"
        f"Active horizons: {escape_markdown(h_str)}\n\n"
        "*Commands:*\n"
        "/followups on \\- Enable all follow\\-ups\n"
        "/followups off \\- Disable follow\\-ups\n"
        "`/followups 1h,7d` \\- Only get 1h and 7d follow\\-ups"
    )


# ============================================================
# Watchlist Command Handlers
# ============================================================

MAX_WATCHLIST_SIZE = 50


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return "".join(f"\\{c}" if c in r"_*[]()~`>#+-=|{}.!" else c for c in text)


def _normalize_ticker(symbol: str) -> tuple:
    """Normalize a ticker symbol via alias remapping.

    Returns:
        (normalized_symbol, warning) — warning is set if delisted.
    """
    from shit.market_data.ticker_validator import TickerValidator

    symbol = symbol.strip().upper()
    if symbol in TickerValidator.ALIASES:
        replacement = TickerValidator.ALIASES[symbol]
        if replacement is None:
            return symbol, f"{symbol} is no longer publicly traded"
        return replacement, None
    return symbol, None


def _validate_watchlist_tickers(symbols: list) -> tuple:
    """Validate tickers against the ticker_registry.

    Returns:
        (valid_symbols, invalid_symbols)
    """
    from shit.db.sync_session import get_session
    from shit.market_data.models import TickerRegistry

    if not symbols:
        return [], []

    try:
        with get_session() as session:
            known = (
                session.query(TickerRegistry.symbol)
                .filter(
                    TickerRegistry.symbol.in_(symbols),
                    TickerRegistry.status == "active",
                )
                .all()
            )
            known_set = {r.symbol for r in known}

        valid = [s for s in symbols if s in known_set]
        invalid = [s for s in symbols if s not in known_set]
        return valid, invalid
    except Exception:
        # If DB is unavailable, accept all tickers (fail-open)
        return symbols, []


def _get_ticker_names(symbols: list) -> dict:
    """Look up company names for a list of symbols from ticker_registry."""
    if not symbols:
        return {}
    from shit.db.sync_session import get_session
    from shit.market_data.models import TickerRegistry

    try:
        with get_session() as session:
            rows = (
                session.query(
                    TickerRegistry.symbol,
                    TickerRegistry.company_name,
                    TickerRegistry.sector,
                )
                .filter(TickerRegistry.symbol.in_(symbols))
                .all()
            )
            return {
                row.symbol: (
                    f"{row.company_name}" + (f" ({row.sector})" if row.sector else "")
                )
                for row in rows
                if row.company_name
            }
    except Exception:
        return {}


def _format_watchlist_display(watchlist: list) -> str:
    """Format watchlist for display with company names."""
    if not watchlist:
        return (
            "\U0001f4cb *Your Watchlist*\n\n"
            "Your watchlist is empty \\- you're receiving alerts for ALL tickers\\.\n\n"
            "To focus on specific tickers, use:\n"
            "`/watchlist add TSLA NVDA AAPL`"
        )

    names = _get_ticker_names(watchlist)
    lines = ["\U0001f4cb *Your Watchlist*\n"]
    lines.append(f"You're tracking {len(watchlist)} tickers:")
    for symbol in sorted(watchlist):
        name = names.get(symbol, "")
        if name:
            lines.append(f"\u2022 {symbol} \\- {_escape_md(name)}")
        else:
            lines.append(f"\u2022 {symbol}")
    lines.append(
        "\nYou'll only receive alerts when these tickers appear in a prediction\\."
    )
    lines.append(
        "\n_Use /watchlist add TICKER or /watchlist remove TICKER to modify\\._"
    )
    return "\n".join(lines)


def _format_watchlist_summary(watchlist: list) -> str:
    """Format a compact watchlist summary for add/remove responses."""
    if not watchlist:
        return ""
    names = _get_ticker_names(watchlist)
    lines = [f"\nYour watchlist \\({len(watchlist)} tickers\\):"]
    for symbol in sorted(watchlist):
        name = names.get(symbol, "")
        if name:
            lines.append(f"\u2022 {symbol} \\- {_escape_md(name)}")
        else:
            lines.append(f"\u2022 {symbol}")
    return "\n".join(lines)


def _handle_watchlist_add(
    chat_id: str,
    prefs: Dict[str, Any],
    current_watchlist: list,
    tickers_raw: list,
) -> str:
    """Handle /watchlist add <tickers>."""
    if not tickers_raw:
        return "Usage: `/watchlist add TSLA NVDA AAPL`"

    # Normalize via alias remapping and check for delisted
    normalized = []
    delisted_warnings = []
    for t in tickers_raw:
        symbol, warning = _normalize_ticker(t)
        if warning:
            delisted_warnings.append(warning)
        else:
            normalized.append(symbol)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for s in normalized:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    normalized = deduped

    # Check max size
    new_count = len(set(current_watchlist) | set(normalized))
    if new_count > MAX_WATCHLIST_SIZE:
        return (
            f"Watchlist is limited to {MAX_WATCHLIST_SIZE} tickers\\. "
            f"You have {len(current_watchlist)}\\."
        )

    # Validate against registry
    valid, invalid = _validate_watchlist_tickers(normalized)

    # Separate already-present from truly new
    already_present = [s for s in valid if s in current_watchlist]
    new_additions = [s for s in valid if s not in current_watchlist]

    # Update watchlist if there are new additions
    if new_additions:
        updated = current_watchlist + new_additions
        prefs["assets_of_interest"] = updated
        update_subscription(chat_id, alert_preferences=prefs)
        current_watchlist = updated

    # Build response
    lines = []
    if new_additions:
        lines.append(f"\u2705 Added to watchlist: {', '.join(new_additions)}")
    if already_present:
        lines.append(f"\u2139\ufe0f Already on watchlist: {', '.join(already_present)}")
    if invalid:
        lines.append(
            f"\u26a0\ufe0f Unknown tickers \\(not in our registry\\): "
            f"{', '.join(invalid)}"
        )
    if delisted_warnings:
        for w in delisted_warnings:
            lines.append(f"\u26a0\ufe0f {_escape_md(w)}")

    if not lines:
        lines.append("No valid tickers to add\\.")

    # Append watchlist summary
    summary = _format_watchlist_summary(current_watchlist)
    if summary:
        lines.append(summary)

    return "\n".join(lines)


def _handle_watchlist_remove(
    chat_id: str,
    prefs: Dict[str, Any],
    current_watchlist: list,
    tickers_raw: list,
) -> str:
    """Handle /watchlist remove <tickers>."""
    if not tickers_raw:
        return "Usage: `/watchlist remove TSLA NVDA`"

    symbols = [s.strip().upper() for s in tickers_raw if s.strip()]

    present = [s for s in symbols if s in current_watchlist]
    absent = [s for s in symbols if s not in current_watchlist]

    lines = []
    if present:
        updated = [s for s in current_watchlist if s not in present]
        prefs["assets_of_interest"] = updated
        update_subscription(chat_id, alert_preferences=prefs)
        lines.append(f"\u2705 Removed from watchlist: {', '.join(present)}")
        current_watchlist = updated
    if absent:
        lines.append(f"\u2139\ufe0f Not on your watchlist: {', '.join(absent)}")

    if current_watchlist:
        summary = _format_watchlist_summary(current_watchlist)
        if summary:
            lines.append(summary)
    else:
        lines.append(
            "\nYour watchlist is now empty \\- you'll receive alerts for ALL tickers\\."
        )

    return "\n".join(lines)


def _handle_watchlist_clear(chat_id: str, prefs: Dict[str, Any]) -> str:
    """Handle /watchlist clear."""
    prefs["assets_of_interest"] = []
    update_subscription(chat_id, alert_preferences=prefs)
    return "\u2705 Watchlist cleared\\. You'll now receive alerts for ALL tickers\\."


def handle_watchlist_command(chat_id: str, args: str = "") -> str:
    """Handle /watchlist command — view/modify ticker watchlist.

    Supports:
        /watchlist              — Show current watchlist
        /watchlist show         — Same as above
        /watchlist add TSLA     — Add tickers
        /watchlist remove TSLA  — Remove tickers
        /watchlist clear        — Clear watchlist (receive all alerts)
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

    current_watchlist = prefs.get("assets_of_interest", [])
    args = args.strip()

    if not args or args.lower() == "show":
        return _format_watchlist_display(current_watchlist)

    parts = args.split()
    action = parts[0].lower()
    tickers_raw = parts[1:] if len(parts) > 1 else []

    if action == "add":
        return _handle_watchlist_add(chat_id, prefs, current_watchlist, tickers_raw)
    elif action == "remove":
        return _handle_watchlist_remove(chat_id, prefs, current_watchlist, tickers_raw)
    elif action == "clear":
        return _handle_watchlist_clear(chat_id, prefs)
    else:
        return (
            "Unknown action\\. Use `/watchlist add TSLA`, "
            "`/watchlist remove TSLA`, or `/watchlist show`\\."
        )


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
    elif command == "/watchlist":
        response = handle_watchlist_command(chat_id, args)
    elif command == "/briefing":
        response = handle_briefing_command(chat_id, args)
    elif command == "/followups":
        response = handle_followups_command(chat_id, args)
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
