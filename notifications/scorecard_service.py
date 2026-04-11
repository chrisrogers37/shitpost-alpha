"""
Weekly Scorecard Service

Orchestrates data collection, formatting, and delivery of the weekly scorecard.
Called by Railway cron every Sunday at 7 PM ET.
"""

import json
from datetime import date, timedelta
from typing import Optional

from notifications.db import get_active_subscriptions
from notifications.scorecard_formatter import (
    format_weekly_scorecard,
    truncate_to_telegram_limit,
)
from notifications.scorecard_queries import (
    get_asset_breakdown,
    get_top_wins,
    get_weekly_accuracy,
    get_weekly_pnl,
    get_weekly_prediction_stats,
    get_weekly_streak,
    get_worst_misses,
)
from notifications.telegram_sender import send_telegram_message
from shit.logging import get_service_logger

logger = get_service_logger("scorecard_service")


def get_current_week_range() -> tuple[date, date]:
    """Get the Monday-Sunday range for the current week.

    Returns:
        Tuple of (monday, sunday) as date objects.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def generate_scorecard(
    week_start: Optional[date] = None,
    week_end: Optional[date] = None,
) -> str:
    """Generate the scorecard message for a given week.

    Args:
        week_start: Monday of the week. Defaults to current week.
        week_end: Sunday of the week. Defaults to current week.

    Returns:
        Formatted MarkdownV2 message string.
    """
    if week_start is None or week_end is None:
        week_start, week_end = get_current_week_range()

    logger.info(f"Generating scorecard for {week_start} to {week_end}")

    prediction_stats = get_weekly_prediction_stats(week_start, week_end)
    accuracy = get_weekly_accuracy(week_start, week_end, timeframe="t7")
    pnl = get_weekly_pnl(week_start, week_end, timeframe="t7")
    top_wins = get_top_wins(week_start, week_end, limit=3)
    worst_misses = get_worst_misses(week_start, week_end, limit=3)
    asset_breakdown = get_asset_breakdown(week_start, week_end)
    streak = get_weekly_streak()

    # Optional: conviction voting leaderboard (Feature 11)
    leaderboard = None
    llm_vs_crowd = None
    try:
        from notifications.vote_db import get_leaderboard, get_llm_vs_crowd_stats

        leaderboard = get_leaderboard(limit=5)
        llm_vs_crowd = get_llm_vs_crowd_stats()
    except ImportError:
        pass  # Feature 11 not yet implemented

    message = format_weekly_scorecard(
        week_start=week_start,
        week_end=week_end,
        prediction_stats=prediction_stats,
        accuracy=accuracy,
        pnl=pnl,
        top_wins=top_wins,
        worst_misses=worst_misses,
        asset_breakdown=asset_breakdown,
        leaderboard=leaderboard,
        llm_vs_crowd=llm_vs_crowd,
        streak_info=streak,
    )

    return truncate_to_telegram_limit(message)


def send_weekly_scorecard() -> dict:
    """Generate and send the weekly scorecard to all active subscribers.

    Returns:
        Stats dict with sent, failed, skipped counts.
    """
    stats = {"sent": 0, "failed": 0, "skipped": 0}

    message = generate_scorecard()

    # Check if there's enough data
    total = message.count("Total Predictions: 0")
    if total > 0:
        logger.info("No predictions this week, skipping scorecard")
        return stats

    subscriptions = get_active_subscriptions()
    for sub in subscriptions:
        chat_id = sub["chat_id"]

        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        if not prefs.get("scorecard_enabled", True):
            stats["skipped"] += 1
            continue

        success, error = send_telegram_message(chat_id, message)
        if success:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            logger.warning(f"Failed to send scorecard to {chat_id}: {error}")

    logger.info(
        f"Weekly scorecard: {stats['sent']} sent, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    return stats


def generate_and_send_scorecard(
    chat_id: str,
    preview: bool = False,
) -> None:
    """Generate and send a scorecard to a single chat (for /scorecard now).

    Args:
        chat_id: Telegram chat ID.
        preview: If True, add a "PREVIEW" header.
    """
    message = generate_scorecard()
    if preview:
        message = "*PREVIEW \\- Not final*\n\n" + message

    send_telegram_message(chat_id, message)
