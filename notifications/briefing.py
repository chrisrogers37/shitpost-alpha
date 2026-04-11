"""
Pre-market morning briefing for Telegram subscribers.

Sends a daily digest at 8:30 AM ET on trading days summarizing overnight
Trump activity, aggregated sentiment, and per-asset breakdown.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from notifications.db import (
    _execute_read,
    get_active_subscriptions,
)
from notifications.telegram_sender import escape_markdown, send_telegram_message
from shit.logging import get_service_logger
from shit.market_data.market_calendar import MarketCalendar

logger = get_service_logger("briefing")

ET = ZoneInfo("America/New_York")
MAX_TELEGRAM_LENGTH = 4096
BRIEFING_HOUR = 8
BRIEFING_MINUTE = 30


def get_overnight_predictions(briefing_time: datetime) -> List[Dict[str, Any]]:
    """Get predictions created since last market close.

    Args:
        briefing_time: Current briefing datetime (timezone-aware, ET).

    Returns:
        List of prediction dicts with post text and outcome data.
    """
    calendar = MarketCalendar()
    prev_trading_day = calendar.previous_trading_day(briefing_time.date())
    window_start = datetime.combine(prev_trading_day, time(16, 0), tzinfo=ET)

    return _execute_read(
        """
        SELECT
            p.id as prediction_id,
            p.shitpost_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.calibrated_confidence,
            p.thesis,
            p.post_timestamp,
            p.created_at,
            COALESCE(s.text, ts.text) as post_text
        FROM predictions p
        LEFT JOIN signals s ON s.signal_id = p.signal_id
        LEFT JOIN truth_social_shitposts ts ON ts.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND p.created_at >= :window_start
            AND p.created_at < :window_end
        ORDER BY p.created_at DESC
        """,
        params={
            "window_start": window_start,
            "window_end": briefing_time,
        },
        default=[],
        context="get_overnight_predictions",
    )


def aggregate_by_asset(predictions: List[Dict[str, Any]]) -> Dict[str, Dict]:
    """Aggregate predictions by asset symbol.

    Returns:
        Dict mapping symbol to sentiment, count, avg_confidence, predictions.
        Sorted by count descending.
    """
    assets: Dict[str, Dict[str, list]] = defaultdict(
        lambda: {"sentiments": [], "confidences": [], "predictions": []}
    )

    for pred in predictions:
        impact = pred.get("market_impact", {})
        if isinstance(impact, str):
            impact = json.loads(impact)
        if not isinstance(impact, dict):
            continue

        for symbol, sentiment in impact.items():
            assets[symbol]["sentiments"].append(sentiment)
            assets[symbol]["confidences"].append(pred.get("confidence", 0))
            text = pred.get("post_text", "") or ""
            assets[symbol]["predictions"].append(
                {
                    "text": text[:80] if text else "",
                    "confidence": pred.get("confidence", 0),
                    "calibrated_confidence": pred.get("calibrated_confidence"),
                    "sentiment": sentiment,
                }
            )

    result = {}
    for symbol, data in assets.items():
        counts = Counter(data["sentiments"])
        majority_sentiment = counts.most_common(1)[0][0]
        confidences = data["confidences"]
        result[symbol] = {
            "sentiment": majority_sentiment,
            "count": len(data["sentiments"]),
            "avg_confidence": sum(confidences) / len(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "predictions": data["predictions"],
        }

    return dict(sorted(result.items(), key=lambda x: x[1]["count"], reverse=True))


def format_briefing_message(
    date_str: str,
    predictions: List[Dict[str, Any]],
    asset_summary: Dict[str, Dict],
) -> str:
    """Format the morning briefing as a Telegram MarkdownV2 message.

    Args:
        date_str: Formatted date string (e.g., "Wednesday, April 9, 2026").
        predictions: List of overnight prediction dicts.
        asset_summary: Aggregated per-asset data from aggregate_by_asset().

    Returns:
        MarkdownV2 formatted string.
    """
    lines = []

    # Header
    lines.append("*SHITPOST ALPHA \\| MORNING BRIEFING*")
    lines.append(escape_markdown(date_str))
    lines.append("")

    if not predictions:
        lines.append("*QUIET NIGHT* \\- No market\\-relevant posts detected\\.")
        lines.append("")
        lines.append(escape_markdown("Have a good trading day!"))
    else:
        n = len(predictions)
        post_word = "post" if n == 1 else "posts"
        lines.append(escape_markdown(f"OVERNIGHT ACTIVITY: {n} {post_word} analyzed"))
        lines.append("")

        # Net sentiment
        all_sentiments = []
        all_confidences = []
        for data in asset_summary.values():
            for p in data["predictions"]:
                all_sentiments.append(p["sentiment"])
                all_confidences.append(p["confidence"])

        sentiment_counts = Counter(all_sentiments)
        dominant = sentiment_counts.most_common(1)[0][0].upper()
        counts_str = ", ".join(f"{c} {s}" for s, c in sentiment_counts.most_common())

        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        min_conf = min(all_confidences) if all_confidences else 0
        max_conf = max(all_confidences) if all_confidences else 0

        lines.append(escape_markdown(f"NET SENTIMENT: {dominant} ({counts_str})"))
        lines.append(
            escape_markdown(
                f"AVG CONFIDENCE: {avg_conf:.0%} (range: {min_conf:.0%}-{max_conf:.0%})"
            )
        )
        lines.append("")

        # Per-asset breakdown
        lines.append("*ASSET BREAKDOWN:*")
        for symbol, data in asset_summary.items():
            sentiment = data["sentiment"].upper()
            count = data["count"]
            avg = data["avg_confidence"]
            post_word = "post" if count == 1 else "posts"
            lines.append(
                escape_markdown(
                    f"  {symbol} - {sentiment} ({count} {post_word}, avg conf {avg:.0%})"
                )
            )
            # Show up to 3 posts per asset
            for p in data["predictions"][:3]:
                text_preview = p["text"]
                if len(text_preview) > 60:
                    text_preview = text_preview[:60] + "..."
                conf_pct = f"{p['confidence']:.0%}"
                lines.append(escape_markdown(f'    "{text_preview}" ({conf_pct})'))
        lines.append("")

    # Footer
    lines.append(
        escape_markdown("This is NOT financial advice. For entertainment only.")
    )
    lines.append(escape_markdown("Reply /briefing off to disable morning briefings."))

    message = "\n".join(lines)

    # Truncate if over Telegram limit
    if len(message) > MAX_TELEGRAM_LENGTH:
        message = _format_compact(date_str, predictions, asset_summary)

    return message


def _format_compact(
    date_str: str,
    predictions: List[Dict[str, Any]],
    asset_summary: Dict[str, Dict],
) -> str:
    """Format a compact briefing when the full version exceeds Telegram limits."""
    lines = []
    lines.append("*SHITPOST ALPHA \\| MORNING BRIEFING*")
    lines.append(escape_markdown(date_str))
    lines.append("")

    n = len(predictions)
    lines.append(escape_markdown(f"OVERNIGHT ACTIVITY: {n} posts analyzed"))
    lines.append("")

    # Top 5 assets, 1 line each, no post previews
    lines.append("*ASSET BREAKDOWN:*")
    for symbol, data in list(asset_summary.items())[:5]:
        sentiment = data["sentiment"].upper()
        count = data["count"]
        avg = data["avg_confidence"]
        lines.append(
            escape_markdown(
                f"  {symbol} - {sentiment} ({count} posts, avg conf {avg:.0%})"
            )
        )

    remaining = len(asset_summary) - 5
    if remaining > 0:
        lines.append(escape_markdown(f"  ... and {remaining} more assets"))

    lines.append("")
    lines.append(
        escape_markdown("This is NOT financial advice. For entertainment only.")
    )
    lines.append(escape_markdown("Reply /briefing off to disable morning briefings."))

    return "\n".join(lines)


def send_morning_briefing() -> Dict[str, Any]:
    """Send morning briefing to all opted-in subscribers.

    Returns:
        Summary dict: {sent, failed, skipped, total_subscribers, predictions_count}
    """
    results = {
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "total_subscribers": 0,
        "predictions_count": 0,
    }

    now_et = datetime.now(ET)

    # Query overnight predictions
    predictions = get_overnight_predictions(now_et)
    results["predictions_count"] = len(predictions)
    asset_summary = aggregate_by_asset(predictions) if predictions else {}

    # Format briefing message
    date_str = now_et.strftime("%A, %B %-d, %Y")
    message = format_briefing_message(date_str, predictions, asset_summary)

    # Get subscribers who have briefings enabled
    subscriptions = get_active_subscriptions()
    results["total_subscribers"] = len(subscriptions)

    for sub in subscriptions:
        prefs = sub.get("alert_preferences", {})
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except json.JSONDecodeError:
                prefs = {}

        if not prefs.get("briefing_enabled", True):
            results["skipped"] += 1
            continue

        chat_id = sub["chat_id"]
        success, error = send_telegram_message(chat_id, message)

        if success:
            results["sent"] += 1
        else:
            results["failed"] += 1
            logger.error(f"Failed to send briefing to {chat_id}: {error}")

    logger.info(
        f"Briefing complete: {results['sent']} sent, "
        f"{results['failed']} failed, {results['skipped']} skipped, "
        f"{results['predictions_count']} predictions"
    )
    return results


def is_briefing_time(now_et: Optional[datetime] = None) -> bool:
    """Check if now is within the briefing send window (8:25-8:35 AM ET).

    Args:
        now_et: Current time in ET. Defaults to now.

    Returns:
        True if within the 10-minute send window.
    """
    if now_et is None:
        now_et = datetime.now(ET)
    return now_et.hour == BRIEFING_HOUR and 25 <= now_et.minute <= 35


def is_briefing_day(now_et: Optional[datetime] = None) -> bool:
    """Check if today is a trading day.

    Args:
        now_et: Current time in ET. Defaults to now.

    Returns:
        True if today is a NYSE trading day.
    """
    if now_et is None:
        now_et = datetime.now(ET)
    calendar = MarketCalendar()
    return calendar.is_trading_day(now_et.date())
