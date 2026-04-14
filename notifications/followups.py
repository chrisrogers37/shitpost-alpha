"""
"What Happened" follow-up messages for Telegram subscribers.

After an alert is sent, tracks the prediction and sends follow-up messages
at T+1h, T+1d, and T+7d showing actual market moves vs the prediction.
"""

import json
import time as time_module
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from notifications.db import (
    _execute_read,
    _execute_write,
    _extract_scalar,
)
from notifications.telegram_sender import escape_markdown, send_telegram_message
from shit.logging import get_service_logger

logger = get_service_logger("followups")

MAX_FOLLOWUPS_PER_DAY = 15
MAX_DEFERRAL_HOURS = 48
HORIZONS = ("1h", "1d", "7d")

# Expected time offsets (hours) from alert time for each horizon
EXPECTED_OFFSETS = {"1h": 2, "1d": 48, "7d": 336}

# DB column mappings per horizon
RETURN_COL = {"1h": "return_1h", "1d": "return_t1", "7d": "return_t7"}
CORRECT_COL = {"1h": "correct_1h", "1d": "correct_t1", "7d": "correct_t7"}
PNL_COL = {"1h": "pnl_1h", "1d": "pnl_t1", "7d": "pnl_t7"}
PRICE_COL = {"1h": "price_1h_after", "1d": "price_t1", "7d": "price_t7"}
SENT_COL = {"1h": "sent_1h", "1d": "sent_1d", "7d": "sent_7d"}
SENT_AT_COL = {"1h": "sent_1h_at", "1d": "sent_1d_at", "7d": "sent_7d_at"}


# ============================================================
# Follow-up Tracking Creation
# ============================================================


def create_followup_tracking(
    prediction_id: int,
    chat_id: str,
    alert_sent_at: datetime,
) -> bool:
    """Create a follow-up tracking row for a sent alert.

    Args:
        prediction_id: ID of the prediction that triggered the alert.
        chat_id: Telegram chat ID of the subscriber.
        alert_sent_at: When the original alert was sent.

    Returns:
        True if created (or already exists), False on error.
    """
    first_check = alert_sent_at + timedelta(minutes=65)  # 1h + 5min buffer

    return _execute_write(
        """
        INSERT INTO alert_followups (
            prediction_id, chat_id, original_alert_sent_at, next_check_at,
            created_at, updated_at
        ) VALUES (
            :prediction_id, :chat_id, :alert_sent_at, :next_check_at,
            NOW(), NOW()
        )
        ON CONFLICT (prediction_id, chat_id) DO NOTHING
        """,
        params={
            "prediction_id": prediction_id,
            "chat_id": chat_id,
            "alert_sent_at": alert_sent_at,
            "next_check_at": first_check,
        },
        context="create_followup_tracking",
    )


# ============================================================
# Due Follow-up Detection
# ============================================================


def get_due_followups() -> List[Dict[str, Any]]:
    """Get follow-up rows that are due for processing.

    Returns rows where next_check_at <= now and at least one horizon
    is not yet sent (True).
    """
    return _execute_read(
        """
        SELECT
            af.id,
            af.prediction_id,
            af.chat_id,
            af.sent_1h, af.sent_1d, af.sent_7d,
            af.sent_1h_at, af.sent_1d_at, af.sent_7d_at,
            af.original_alert_sent_at,
            af.next_check_at,
            p.assets,
            p.market_impact,
            p.confidence,
            p.calibrated_confidence,
            s.text as post_text
        FROM alert_followups af
        JOIN predictions p ON p.id = af.prediction_id
        LEFT JOIN signals s ON s.signal_id = p.signal_id
        JOIN telegram_subscriptions tsub ON tsub.chat_id = af.chat_id
            AND tsub.is_active = true
        WHERE af.next_check_at <= NOW()
            AND (af.sent_1h IS NOT TRUE OR af.sent_1d IS NOT TRUE OR af.sent_7d IS NOT TRUE)
        ORDER BY af.original_alert_sent_at ASC
        """,
        default=[],
        context="get_due_followups",
    )


def get_followup_outcomes(prediction_id: int) -> List[Dict[str, Any]]:
    """Get outcome data for all assets in a prediction.

    Args:
        prediction_id: The prediction ID.

    Returns:
        List of outcome dicts, one per asset.
    """
    return _execute_read(
        """
        SELECT
            po.symbol,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.price_at_post,
            po.price_1h_after,
            po.return_1h,
            po.correct_1h,
            po.pnl_1h,
            po.price_t1,
            po.return_t1,
            po.correct_t1,
            po.pnl_t1,
            po.price_t7,
            po.return_t7,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete
        FROM prediction_outcomes po
        WHERE po.prediction_id = :prediction_id
        """,
        params={"prediction_id": prediction_id},
        default=[],
        context="get_followup_outcomes",
    )


# ============================================================
# Data Availability Checks
# ============================================================


def _is_data_available(outcome: Dict, horizon: str) -> bool:
    """Check if outcome data is available for a given horizon."""
    return outcome.get(RETURN_COL[horizon]) is not None


def _should_abandon(followup: Dict, horizon: str) -> bool:
    """Check if we've been deferring too long for this horizon."""
    alert_time = followup["original_alert_sent_at"]
    if isinstance(alert_time, str):
        alert_time = datetime.fromisoformat(alert_time)

    max_wait_hours = EXPECTED_OFFSETS[horizon] + MAX_DEFERRAL_HOURS
    elapsed = (
        datetime.now(timezone.utc) - alert_time.replace(tzinfo=timezone.utc)
    ).total_seconds()
    return elapsed > max_wait_hours * 3600


# ============================================================
# Message Formatting
# ============================================================


def format_followup_message(
    horizon: str,
    outcomes: List[Dict[str, Any]],
) -> str:
    """Format a follow-up message for Telegram.

    Args:
        horizon: "1h", "1d", or "7d".
        outcomes: List of outcome dicts (one per asset).

    Returns:
        MarkdownV2 formatted message.
    """
    lines = []

    horizon_labels = {
        "1h": "1 hour later",
        "1d": "after 1 trading day",
        "7d": "after 7 trading days",
    }
    header_prefix = {"1h": "UPDATE", "1d": "VERDICT", "7d": "FINAL RESULT"}

    return_key = RETURN_COL[horizon]
    correct_key = CORRECT_COL[horizon]
    pnl_key = PNL_COL[horizon]
    price_key = PRICE_COL[horizon]

    # Header
    if len(outcomes) == 1:
        symbol = outcomes[0]["symbol"]
        lines.append(
            escape_markdown(
                f"{header_prefix[horizon]}: {symbol} {horizon_labels[horizon]}"
            )
        )
    else:
        lines.append(
            escape_markdown(
                f"{header_prefix[horizon]}: {len(outcomes)} assets {horizon_labels[horizon]}"
            )
        )
    lines.append("")

    total_correct = 0
    total_pnl = 0.0

    for outcome in outcomes:
        symbol = outcome["symbol"]
        base_price = outcome.get("price_at_post") or outcome.get("price_at_prediction")
        end_price = outcome.get(price_key)
        ret = outcome.get(return_key)
        correct = outcome.get(correct_key)
        pnl = outcome.get(pnl_key, 0) or 0

        ret_str = f"{ret:+.1f}%" if ret is not None else "N/A"

        if correct is True:
            result_str = "CORRECT"
            total_correct += 1
        elif correct is False:
            result_str = "INCORRECT"
        else:
            result_str = "FLAT"

        price_str = ""
        if base_price and end_price:
            price_str = f"${base_price:.2f} -> ${end_price:.2f} "

        sentiment = (outcome.get("prediction_sentiment") or "neutral").upper()
        conf = outcome.get("prediction_confidence", 0) or 0

        if len(outcomes) == 1:
            lines.append(escape_markdown(f"Price: {price_str}({ret_str})"))
            lines.append(
                escape_markdown(f"Prediction: {sentiment} @ {conf:.0%} confidence")
            )
            lines.append(escape_markdown(f"Result: {result_str}"))
        else:
            lines.append(
                escape_markdown(f"  {symbol}: {price_str}({ret_str}) {result_str}")
            )

        total_pnl += pnl

    lines.append("")

    # P&L summary for 1d and 7d
    if horizon in ("1d", "7d"):
        if len(outcomes) == 1:
            verb = "gained" if total_pnl >= 0 else "lost"
            lines.append(
                escape_markdown(
                    f"P&L: $1,000 position would have {verb} ${abs(total_pnl):.2f}"
                )
            )
        else:
            lines.append(
                escape_markdown(f"Overall: {total_correct}/{len(outcomes)} correct")
            )
            total_position = len(outcomes) * 1000
            lines.append(
                escape_markdown(
                    f"Net P&L: ${total_pnl:+,.2f} on ${total_position:,} across {len(outcomes)} positions"
                )
            )

    # Footer
    lines.append("")
    lines.append(escape_markdown("Reply /followups off to disable follow-up messages."))

    return "\n".join(lines)


# ============================================================
# Follow-up Processing
# ============================================================


def _check_daily_limit(chat_id: str) -> bool:
    """Check if subscriber has hit daily follow-up limit.

    Returns True if under the limit (can send more).
    """
    count = _execute_read(
        """
        SELECT COUNT(*) as sent_today
        FROM alert_followups
        WHERE chat_id = :chat_id
            AND (
                (sent_1h = true AND sent_1h_at >= CURRENT_DATE)
                OR (sent_1d = true AND sent_1d_at >= CURRENT_DATE)
                OR (sent_7d = true AND sent_7d_at >= CURRENT_DATE)
            )
        """,
        params={"chat_id": chat_id},
        processor=_extract_scalar,
        default=0,
        context="check_daily_followup_limit",
    )
    return (count or 0) < MAX_FOLLOWUPS_PER_DAY


def _get_subscriber_prefs(chat_id: str) -> Optional[Dict]:
    """Get subscriber preferences for follow-up filtering."""
    row = _execute_read(
        """
        SELECT alert_preferences
        FROM telegram_subscriptions
        WHERE chat_id = :chat_id AND is_active = true
        """,
        params={"chat_id": chat_id},
        processor=_extract_scalar,
        default=None,
        context="get_subscriber_prefs_for_followup",
    )
    if row is None:
        return None
    if isinstance(row, str):
        try:
            return json.loads(row)
        except json.JSONDecodeError:
            return {}
    return row if isinstance(row, dict) else {}


def _update_followup_sent(followup_id: int, horizon: str) -> bool:
    """Mark a horizon as sent."""
    sent_col = SENT_COL[horizon]
    sent_at_col = SENT_AT_COL[horizon]
    return _execute_write(
        f"""
        UPDATE alert_followups
        SET {sent_col} = true, {sent_at_col} = NOW(), updated_at = NOW()
        WHERE id = :id
        """,
        params={"id": followup_id},
        context=f"update_followup_sent_{horizon}",
    )


def _update_followup_abandoned(followup_id: int, horizon: str) -> bool:
    """Mark a horizon as abandoned (data never became available)."""
    sent_col = SENT_COL[horizon]
    return _execute_write(
        f"""
        UPDATE alert_followups
        SET {sent_col} = false, updated_at = NOW()
        WHERE id = :id
        """,
        params={"id": followup_id},
        context=f"update_followup_abandoned_{horizon}",
    )


def _defer_followup(followup_id: int) -> bool:
    """Push next_check_at forward by 30 minutes."""
    return _execute_write(
        """
        UPDATE alert_followups
        SET next_check_at = next_check_at + INTERVAL '30 minutes', updated_at = NOW()
        WHERE id = :id
        """,
        params={"id": followup_id},
        context="defer_followup",
    )


def _is_horizon_due(followup: Dict, horizon: str) -> bool:
    """Check if a specific horizon is due for processing.

    A horizon is due if:
    - It hasn't been sent yet (not True)
    - Enough time has elapsed since the alert
    """
    sent_val = followup.get(SENT_COL[horizon])
    if sent_val is True:
        return False  # Already sent
    if sent_val is False:
        return False  # Abandoned

    alert_time = followup["original_alert_sent_at"]
    if isinstance(alert_time, str):
        alert_time = datetime.fromisoformat(alert_time)

    # Minimum elapsed times
    min_elapsed = {
        "1h": timedelta(hours=1),
        "1d": timedelta(hours=20),
        "7d": timedelta(days=9),
    }
    now = datetime.now(timezone.utc)
    elapsed = now - alert_time.replace(tzinfo=timezone.utc)

    return elapsed >= min_elapsed[horizon]


def _process_single_followup(followup: Dict) -> str:
    """Process a single follow-up row.

    Returns one of: "sent", "deferred", "abandoned", "skipped".
    """
    followup_id = followup["id"]
    prediction_id = followup["prediction_id"]
    chat_id = followup["chat_id"]

    # Check subscriber preferences
    prefs = _get_subscriber_prefs(chat_id)
    if prefs is None:
        return "skipped"

    if not prefs.get("followups_enabled", True):
        return "skipped"

    enabled_horizons = set(prefs.get("followup_horizons", ["1h", "1d", "7d"]))

    # Get outcomes for this prediction
    outcomes = get_followup_outcomes(prediction_id)
    if not outcomes:
        # No outcomes yet — check if we should abandon
        for horizon in HORIZONS:
            if followup.get(SENT_COL[horizon]) is None and _should_abandon(
                followup, horizon
            ):
                _update_followup_abandoned(followup_id, horizon)
        _defer_followup(followup_id)
        return "deferred"

    sent_any = False
    deferred_any = False

    for horizon in HORIZONS:
        if horizon not in enabled_horizons:
            continue
        if not _is_horizon_due(followup, horizon):
            continue

        # Check if data is available for ALL outcomes at this horizon
        all_available = all(_is_data_available(o, horizon) for o in outcomes)

        if all_available:
            # Format and send
            message = format_followup_message(horizon, outcomes)
            success, error = send_telegram_message(chat_id, message)
            if success:
                _update_followup_sent(followup_id, horizon)
                sent_any = True
            else:
                logger.warning(
                    f"Failed to send {horizon} follow-up to {chat_id}: {error}"
                )
                deferred_any = True
        elif _should_abandon(followup, horizon):
            _update_followup_abandoned(followup_id, horizon)
        else:
            deferred_any = True

    if deferred_any:
        _defer_followup(followup_id)

    if sent_any:
        return "sent"
    elif deferred_any:
        return "deferred"
    return "skipped"


def process_due_followups() -> Dict[str, int]:
    """Process all due follow-up messages.

    Groups by subscriber, processes chronologically, respects daily limits.

    Returns:
        Summary dict: {checked, sent, deferred, abandoned, skipped}
    """
    results = {"checked": 0, "sent": 0, "deferred": 0, "abandoned": 0, "skipped": 0}

    due_followups = get_due_followups()
    results["checked"] = len(due_followups)

    if not due_followups:
        return results

    # Group by chat_id for batching
    by_chat: Dict[str, List[Dict]] = defaultdict(list)
    for fu in due_followups:
        by_chat[fu["chat_id"]].append(fu)

    for chat_id, followups in by_chat.items():
        # Check daily limit
        if not _check_daily_limit(chat_id):
            results["skipped"] += len(followups)
            continue

        # Sort by original alert time (oldest first)
        followups.sort(key=lambda f: f["original_alert_sent_at"])

        for fu in followups:
            result = _process_single_followup(fu)
            results[result] += 1

            # Rate limiting between messages to same chat
            if result == "sent":
                time_module.sleep(0.1)

    logger.info(
        f"Follow-ups: {results['checked']} checked, {results['sent']} sent, "
        f"{results['deferred']} deferred, {results['abandoned']} abandoned, "
        f"{results['skipped']} skipped"
    )
    return results
