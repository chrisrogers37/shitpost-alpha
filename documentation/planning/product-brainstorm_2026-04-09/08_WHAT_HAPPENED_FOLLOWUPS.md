# 08: "What Happened" Follow-Ups

**Feature**: After sending an alert, automatically send follow-up messages at T+1h, T+1d, and T+7d showing actual market moves vs the prediction.

**Status**: Design  
**Priority**: Medium-High  
**Estimated Effort**: 2-3 sessions  

---

## Overview

Today, Telegram subscribers receive an alert when a prediction is created ("TSLA bearish at 85% confidence"), but never hear what actually happened. Did TSLA drop? Was the prediction correct? Subscribers have no feedback loop. This feature closes that gap by automatically sending follow-up messages at three checkpoints:

- **T+1h**: Immediate reaction. "TSLA is down 0.8% since the post."
- **T+1d**: Next-day verdict. "TSLA closed down 1.2%. Prediction was CORRECT."
- **T+7d**: Medium-term outcome. "After 7 trading days, TSLA is down 3.1%. $1000 position would have gained $31."

The system already tracks all of this data:
- `prediction_outcomes` has `return_1h`, `return_same_day`, `return_t1`, `return_t7` with `correct_*` boolean flags and `pnl_*` simulation values.
- `notifications/alert_engine.py` already sends alerts to subscribers.
- `notifications/db.py` has all subscriber management.

What's missing: tracking which alerts have been sent, scheduling follow-ups, and formatting the follow-up messages.

---

## Motivation

1. **Closing the feedback loop**: Subscribers who see "TSLA bearish 85%" need to know if that call was right. Without follow-ups, the system feels like shouting into the void.
2. **Trust building**: Showing both correct and incorrect predictions builds credibility. "We told you TSLA would drop, and it did" is powerful. "We said bullish, but it dropped 2%" is honest.
3. **Engagement**: Follow-ups give 3 additional touchpoints per alert. Subscribers stay engaged with the product.
4. **Implicit accuracy reporting**: Over time, subscribers develop an intuitive sense of the system's accuracy from the follow-ups they receive, without needing to visit a dashboard.

---

## Follow-Up Schedule

### Timing Logic

| Checkpoint | Trigger Condition | Data Source | Typical Timing |
|------------|-------------------|-------------|----------------|
| **T+1h** | 1 hour after the original alert was sent | `prediction_outcomes.return_1h`, `price_1h_after` | 1 hour after alert |
| **T+1d** | Next market close after the post | `prediction_outcomes.return_t1`, `correct_t1`, `pnl_t1` | Next trading day close (4 PM ET) |
| **T+7d** | 7 trading days after the post | `prediction_outcomes.return_t7`, `correct_t7`, `pnl_t7` | ~1.5 calendar weeks later |

### When Data Becomes Available

The `OutcomeCalculator` populates these fields at different times:

- **`return_1h`**: Populated shortly after prediction creation (inline in analyzer via `_trigger_reactive_backfill`). Usually available within minutes.
- **`return_t1`**: Populated by `OutcomeCalculator.mature_outcomes()` cron job after the next trading day's close. Available ~T+1 trading day + cron delay.
- **`return_t7`**: Populated by outcome maturation after 7 trading days. Available ~T+7 trading days + cron delay.

The follow-up sender checks if the data is available. If not yet populated, it defers to the next check cycle.

---

## Data Model

### New Table: `alert_followups`

```sql
CREATE TABLE alert_followups (
    id SERIAL PRIMARY KEY,

    -- Link to the original prediction
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),

    -- Link to the subscriber who received the original alert
    chat_id VARCHAR(50) NOT NULL,

    -- Which follow-up horizons have been sent
    -- NULL = not yet due, FALSE = due but data not available, TRUE = sent
    sent_1h BOOLEAN DEFAULT NULL,
    sent_1h_at TIMESTAMP,
    sent_1d BOOLEAN DEFAULT NULL,
    sent_1d_at TIMESTAMP,
    sent_7d BOOLEAN DEFAULT NULL,
    sent_7d_at TIMESTAMP,

    -- Timing
    original_alert_sent_at TIMESTAMP NOT NULL,
    next_check_at TIMESTAMP NOT NULL,  -- When to next check for due follow-ups

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_alert_followup_pred_chat UNIQUE (prediction_id, chat_id)
);

CREATE INDEX idx_alert_followups_next_check
    ON alert_followups (next_check_at)
    WHERE sent_1h IS NOT TRUE OR sent_1d IS NOT TRUE OR sent_7d IS NOT TRUE;

CREATE INDEX idx_alert_followups_chat_id
    ON alert_followups (chat_id);

COMMENT ON TABLE alert_followups IS 'Tracks follow-up messages for sent alerts at T+1h, T+1d, T+7d';
```

### State Machine

Each follow-up row goes through this lifecycle:

```
Created (original alert sent)
    → next_check_at = original_alert_sent_at + 65 minutes
    → sent_1h = NULL, sent_1d = NULL, sent_7d = NULL

Check cycle runs:
    T+1h due?
        → Is return_1h available in prediction_outcomes?
            → Yes: Send message, set sent_1h = TRUE
            → No: Defer, next_check_at += 30 minutes

    T+1d due?
        → Is return_t1 available?
            → Yes: Send message, set sent_1d = TRUE
            → No: Defer

    T+7d due?
        → Is return_t7 available?
            → Yes: Send message, set sent_7d = TRUE
            → No: Defer

All three sent → Row is complete (no more checks needed)
```

### Row Creation

When the alert engine sends an alert to a subscriber, it also creates a follow-up tracking row:

```python
# In notifications/alert_engine.py, after successful send
def _create_followup_tracking(
    prediction_id: int,
    chat_id: str,
    alert_sent_at: datetime,
) -> bool:
    """Create follow-up tracking row for a sent alert."""
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
```

---

## Outcome Data Dependencies

### When outcome_maturation Has Run

For T+1d and T+7d follow-ups, the data comes from `prediction_outcomes`. The `outcome-maturation` cron job runs daily and incrementally fills in timeframe data as it matures.

**Query to check data availability:**

```python
def get_followup_data(prediction_id: int, symbol: str) -> dict | None:
    """Get outcome data for a follow-up message.

    Returns dict with available timeframe data, or None if no outcome exists.
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
            AND po.symbol = :symbol
        """,
        params={"prediction_id": prediction_id, "symbol": symbol},
        processor=_row_to_dict,
        default=None,
        context="get_followup_data",
    )
```

### When outcome_maturation Hasn't Run

If the outcome data isn't available yet (e.g., the maturation cron hasn't run since the timeframe elapsed), the follow-up is deferred:

```python
def _check_data_available(outcome: dict, horizon: str) -> bool:
    """Check if outcome data is available for a given horizon."""
    if horizon == "1h":
        return outcome.get("return_1h") is not None
    elif horizon == "1d":
        return outcome.get("return_t1") is not None
    elif horizon == "7d":
        return outcome.get("return_t7") is not None
    return False
```

The follow-up row's `next_check_at` is advanced by 30 minutes on each deferred check. After 48 hours of deferral for any horizon, mark it as `sent_Xd = FALSE` (data never became available) and stop retrying.

```python
MAX_DEFERRAL_HOURS = 48

def _should_abandon(followup: dict, horizon: str) -> bool:
    """Check if we've been deferring too long."""
    alert_time = followup["original_alert_sent_at"]
    expected_offsets = {"1h": 2, "1d": 48, "7d": 336}  # hours
    max_wait = expected_offsets[horizon] + MAX_DEFERRAL_HOURS
    return (datetime.utcnow() - alert_time).total_seconds() > max_wait * 3600
```

---

## Message Design

### T+1h Follow-Up

Short, immediate reaction. Focus on price movement since the post.

**Correct prediction:**

```
UPDATE: TSLA 1 hour later

Price: $245.50 -> $243.20 (-0.9%)
Prediction: BEARISH @ 85% confidence
Result: ON TRACK

The market is moving in the predicted direction.
```

**Incorrect prediction:**

```
UPDATE: TSLA 1 hour later

Price: $245.50 -> $247.10 (+0.7%)
Prediction: BEARISH @ 85% confidence
Result: AGAINST

Early movement is against the prediction. T+1d and T+7d follow-ups will show the fuller picture.
```

**No significant movement:**

```
UPDATE: TSLA 1 hour later

Price: $245.50 -> $245.80 (+0.1%)
Prediction: BEARISH @ 85% confidence
Result: FLAT (within 0.5% threshold)

No significant movement yet.
```

### T+1d Follow-Up

Next-day verdict. Include P&L simulation.

**Correct:**

```
VERDICT: TSLA after 1 trading day

Price: $245.50 -> $241.30 (-1.7%)
Prediction: BEARISH @ 85%
Result: CORRECT

P&L: $1,000 position would have gained $17.10

T+7d follow-up coming in ~6 trading days.
```

**Incorrect:**

```
VERDICT: TSLA after 1 trading day

Price: $245.50 -> $249.80 (+1.8%)
Prediction: BEARISH @ 85%
Result: INCORRECT

P&L: $1,000 position would have lost $17.50

Markets don't always follow sentiment immediately. T+7d will show the medium-term picture.
```

### T+7d Follow-Up

Final verdict. Include cumulative P&L and accuracy context.

**Correct:**

```
FINAL RESULT: TSLA after 7 trading days

Price: $245.50 -> $237.20 (-3.4%)
Prediction: BEARISH @ 85%
FINAL VERDICT: CORRECT

P&L: $1,000 position would have gained $33.80

This prediction was part of the 68% of bearish calls that were correct at T+7.
```

**Incorrect:**

```
FINAL RESULT: TSLA after 7 trading days

Price: $245.50 -> $252.10 (+2.7%)
Prediction: BEARISH @ 85%
FINAL VERDICT: INCORRECT

P&L: $1,000 position would have lost $26.90

Not every call lands. Overall accuracy at T+7: 65% correct.
```

### Multi-Asset Predictions

When a prediction covers multiple assets (e.g., TSLA, F, GM), send one follow-up per prediction (not per asset). Summarize all assets in one message:

```
VERDICT: 3 assets after 1 trading day

TSLA: $245.50 -> $241.30 (-1.7%) CORRECT
F:    $12.80 -> $12.65 (-1.2%) CORRECT
GM:   $45.20 -> $45.50 (+0.7%) INCORRECT

Overall: 2/3 correct
Net P&L: +$17.10 + $11.70 - $6.60 = +$22.20 on $3,000 across 3 positions
```

### Telegram MarkdownV2 Template

```python
def format_followup_message(
    horizon: str,              # "1h", "1d", "7d"
    prediction: dict,          # Original prediction data
    outcomes: list[dict],      # Per-asset outcome data
) -> str:
    """Format a follow-up message for Telegram.

    Args:
        horizon: Which follow-up horizon.
        prediction: Original prediction with assets, sentiment, confidence.
        outcomes: List of outcome dicts (one per asset).

    Returns:
        MarkdownV2 formatted message.
    """
    lines = []

    # Header
    horizon_labels = {
        "1h": "1 hour later",
        "1d": "after 1 trading day",
        "7d": "after 7 trading days",
    }
    header_prefix = {
        "1h": "UPDATE",
        "1d": "VERDICT",
        "7d": "FINAL RESULT",
    }

    if len(outcomes) == 1:
        symbol = outcomes[0]["symbol"]
        lines.append(escape_markdown(f"{header_prefix[horizon]}: {symbol} {horizon_labels[horizon]}"))
    else:
        n = len(outcomes)
        lines.append(escape_markdown(f"{header_prefix[horizon]}: {n} assets {horizon_labels[horizon]}"))

    lines.append("")

    # Per-asset results
    return_key = {"1h": "return_1h", "1d": "return_t1", "7d": "return_t7"}[horizon]
    correct_key = {"1h": "correct_1h", "1d": "correct_t1", "7d": "correct_t7"}[horizon]
    pnl_key = {"1h": "pnl_1h", "1d": "pnl_t1", "7d": "pnl_t7"}[horizon]
    price_key = {"1h": "price_1h_after", "1d": "price_t1", "7d": "price_t7"}[horizon]

    total_correct = 0
    total_pnl = 0.0

    for outcome in outcomes:
        symbol = outcome["symbol"]
        base_price = outcome.get("price_at_post") or outcome.get("price_at_prediction")
        end_price = outcome.get(price_key)
        ret = outcome.get(return_key)
        correct = outcome.get(correct_key)
        pnl = outcome.get(pnl_key, 0) or 0

        if ret is not None:
            sign = "+" if ret >= 0 else ""
            ret_str = f"{sign}{ret:.1f}%"
        else:
            ret_str = "N/A"

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

        sentiment = outcome.get("prediction_sentiment", "").upper()
        conf = outcome.get("prediction_confidence", 0)

        if len(outcomes) == 1:
            lines.append(escape_markdown(f"Price: {price_str}({ret_str})"))
            lines.append(escape_markdown(f"Prediction: {sentiment} @ {conf:.0%} confidence"))
            emoji = "\\u2705" if correct else "\\u274c" if correct is False else "\\u2796"
            lines.append(f"Result: {escape_markdown(result_str)}")
        else:
            emoji = "\\u2705" if correct else "\\u274c" if correct is False else "\\u2796"
            lines.append(escape_markdown(f"  {symbol}: {price_str}({ret_str}) {result_str}"))

        total_pnl += pnl

    lines.append("")

    # P&L summary
    if horizon in ("1d", "7d"):
        pnl_sign = "+" if total_pnl >= 0 else ""
        if len(outcomes) == 1:
            lines.append(escape_markdown(
                f"P&L: $1,000 position would have "
                f"{'gained' if total_pnl >= 0 else 'lost'} ${abs(total_pnl):.2f}"
            ))
        else:
            lines.append(escape_markdown(f"Overall: {total_correct}/{len(outcomes)} correct"))
            total_position = len(outcomes) * 1000
            lines.append(escape_markdown(
                f"Net P&L: {pnl_sign}${total_pnl:.2f} on ${total_position:,} across {len(outcomes)} positions"
            ))

    # Footer
    lines.append("")
    lines.append(escape_markdown("Reply /followups off to disable follow-up messages."))

    return "\n".join(lines)
```

---

## Batching

### Multiple Follow-Ups Due at Same Time

When the checker runs, multiple follow-ups may be due (e.g., three different predictions' T+1d follow-ups). These should be:

1. **Batched per subscriber**: One subscriber gets all their due follow-ups in sequence, not interleaved with other subscribers.
2. **Rate-limited**: Telegram rate limits are ~30 messages/second per bot. Send with a 100ms delay between messages.
3. **Ordered chronologically**: Oldest predictions' follow-ups first.

```python
def process_due_followups() -> dict:
    """Process all due follow-up messages.

    Returns:
        Summary dict: {checked, sent, deferred, abandoned}
    """
    results = {"checked": 0, "sent": 0, "deferred": 0, "abandoned": 0}

    # Get all follow-ups where next_check_at <= now
    due_followups = get_due_followups()
    results["checked"] = len(due_followups)

    # Group by chat_id for batching
    from collections import defaultdict
    by_chat = defaultdict(list)
    for fu in due_followups:
        by_chat[fu["chat_id"]].append(fu)

    for chat_id, followups in by_chat.items():
        # Sort by original_alert_sent_at (oldest first)
        followups.sort(key=lambda f: f["original_alert_sent_at"])

        for fu in followups:
            result = _process_single_followup(fu)
            results[result] += 1

            # Rate limiting between messages to same chat
            if result == "sent":
                import time
                time.sleep(0.1)

    return results
```

### Same Prediction, Multiple Horizons Due

It's possible (after an outage or delay) that both T+1h and T+1d are due for the same prediction. Process them in order: send T+1h first, then T+1d. The subscriber sees the chronological sequence.

---

## User Preferences

### /followups Command

Add to `notifications/telegram_bot.py`:

```python
def handle_followups_command(chat_id: str, args: str) -> str:
    """Handle /followups command - toggle follow-up messages.

    Args:
        chat_id: Telegram chat ID.
        args: "on", "off", or empty for status. Can also be "1h,1d" for selective horizons.
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "You're not subscribed. Send /start first."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        import json
        prefs = json.loads(prefs)

    current = prefs.get("followups_enabled", True)
    current_horizons = prefs.get("followup_horizons", ["1h", "1d", "7d"])

    arg = args.strip().lower()

    if arg == "off":
        prefs["followups_enabled"] = False
        update_subscription(chat_id, alert_preferences=prefs)
        return "Follow-up messages disabled. Send /followups on to re-enable."
    elif arg == "on":
        prefs["followups_enabled"] = True
        update_subscription(chat_id, alert_preferences=prefs)
        horizons_str = ", ".join(current_horizons)
        return f"Follow-up messages enabled for: {horizons_str}"
    elif arg in ("1h", "1d", "7d", "1h,1d", "1h,7d", "1d,7d", "1h,1d,7d"):
        # Selective horizons
        horizons = [h.strip() for h in arg.split(",")]
        prefs["followup_horizons"] = horizons
        prefs["followups_enabled"] = True
        update_subscription(chat_id, alert_preferences=prefs)
        return f"Follow-ups set to: {', '.join(horizons)}"
    else:
        status = "enabled" if current else "disabled"
        horizons_str = ", ".join(current_horizons)
        return (
            f"Follow-ups are currently {status}.\n"
            f"Active horizons: {horizons_str}\n\n"
            f"Commands:\n"
            f"/followups on - Enable all follow-ups\n"
            f"/followups off - Disable follow-ups\n"
            f"/followups 1h,7d - Only get 1h and 7d follow-ups"
        )
```

### Default Preferences Update

Add to the default `alert_preferences` in `notifications/db.py`:

```python
default_prefs = {
    "min_confidence": 0.7,
    "assets_of_interest": [],
    "sentiment_filter": "all",
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "briefing_enabled": True,       # Feature 07
    "followups_enabled": True,      # NEW
    "followup_horizons": ["1h", "1d", "7d"],  # NEW
}
```

---

## Spam Prevention

### Max Follow-Ups Per Day

To prevent message overload on high-activity days:

```python
MAX_FOLLOWUPS_PER_DAY = 15  # Per subscriber per day

def _check_daily_limit(chat_id: str) -> bool:
    """Check if subscriber has hit daily follow-up limit."""
    result = _execute_read(
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
    return (result or 0) < MAX_FOLLOWUPS_PER_DAY
```

### Quiet Hours Respect

Follow-ups respect the same quiet hours as regular alerts:

```python
if is_in_quiet_hours(subscriber_prefs):
    # Defer to next check outside quiet hours
    followup.next_check_at = calculate_next_check_after_quiet_hours(subscriber_prefs)
    return "deferred"
```

### Deduplication

The unique constraint `(prediction_id, chat_id)` prevents duplicate follow-up rows. The `sent_1h`/`sent_1d`/`sent_7d` flags prevent re-sending the same horizon.

---

## Railway Service

### Cron Configuration

New Railway service: `followup-sender`

**Cron schedule**: `*/5 * * * *` (every 5 minutes)

This matches the existing worker frequency pattern.

### Entry Point

```python
# followup_cron.py
"""Follow-up message sender. Runs every 5 minutes."""

from notifications.followups import process_due_followups
from shit.logging import setup_cli_logging


def main():
    setup_cli_logging(verbose=True)
    result = process_due_followups()
    print(
        f"Follow-ups: {result['checked']} checked, {result['sent']} sent, "
        f"{result['deferred']} deferred, {result['abandoned']} abandoned"
    )


if __name__ == "__main__":
    main()
```

### Worker Design

The follow-up sender is a simple cron job, not an event consumer. This is intentional:

- Follow-ups are not time-critical (minutes of delay are acceptable).
- The polling approach is simpler and more resilient than event-driven.
- The `next_check_at` column naturally handles scheduling without events.

If the cron misses a cycle (Railway downtime), the next run catches up all due follow-ups.

---

## Integration with Alert Engine

### Creating Follow-Up Rows

In `notifications/alert_engine.py`, after successfully sending an alert:

```python
# In check_and_dispatch(), after successful send:
for alert in matched:
    message = format_telegram_alert(alert)
    success, error = send_telegram_message(chat_id, message)

    if success:
        record_alert_sent(chat_id)
        results["alerts_sent"] += 1

        # Create follow-up tracking
        from notifications.followups import create_followup_tracking
        prediction_id = alert.get("prediction_id")
        if prediction_id:
            create_followup_tracking(
                prediction_id=prediction_id,
                chat_id=chat_id,
                alert_sent_at=datetime.utcnow(),
            )
```

### Event Consumer Integration

The `notifications/event_consumer.py` also sends alerts. Add follow-up creation there too:

```python
# In NotificationsWorker.process_event(), after successful send:
if prediction_id:
    create_followup_tracking(
        prediction_id=prediction_id,
        chat_id=chat_id,
        alert_sent_at=datetime.utcnow(),
    )
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `notifications/followups.py` | **NEW** - `create_followup_tracking()`, `process_due_followups()`, `format_followup_message()`, queries |
| `notifications/alert_engine.py` | Add follow-up row creation after successful alert send |
| `notifications/event_consumer.py` | Add follow-up row creation after successful alert send |
| `notifications/telegram_bot.py` | Add `/followups` command handler |
| `notifications/db.py` | Add `followups_enabled` and `followup_horizons` to default preferences |
| `followup_cron.py` | **NEW** - Railway cron entry point |
| `shit_tests/notifications/test_followups.py` | **NEW** - Unit tests |

---

## Testing Strategy

### Unit Tests (`shit_tests/notifications/test_followups.py`)

1. **Follow-up creation**:
   - `test_create_followup_tracking`: Row created with correct initial state
   - `test_create_followup_idempotent`: Duplicate insert is a no-op (ON CONFLICT DO NOTHING)
   - `test_followup_next_check_at`: First check scheduled at alert_time + 65 minutes

2. **Due follow-up detection**:
   - `test_get_due_followups`: Returns rows where next_check_at <= now
   - `test_get_due_followups_excludes_complete`: Rows with all three sent are not returned
   - `test_get_due_followups_respects_subscriber_active`: Inactive subscribers excluded

3. **Data availability checks**:
   - `test_1h_data_available`: return_1h is not null
   - `test_1d_data_not_available_yet`: return_t1 is null, deferred
   - `test_7d_data_available`: return_t7 is not null
   - `test_abandon_after_max_deferral`: 48 hours past expected, marked abandoned

4. **Message formatting**:
   - `test_format_1h_correct`: Price moved in predicted direction
   - `test_format_1h_incorrect`: Price moved against prediction
   - `test_format_1h_flat`: Within 0.5% threshold
   - `test_format_1d_with_pnl`: Includes P&L simulation
   - `test_format_7d_final_verdict`: Includes accuracy context
   - `test_format_multi_asset`: Multiple assets in one message
   - `test_format_respects_markdown_escaping`: Special characters escaped

5. **Batching and rate limiting**:
   - `test_batch_per_subscriber`: Messages grouped by chat_id
   - `test_chronological_order`: Oldest prediction's follow-ups first
   - `test_daily_limit_respected`: No more than 15 follow-ups per day

6. **User preferences**:
   - `test_followups_disabled_skipped`: Opted-out subscribers not checked
   - `test_selective_horizons`: Only configured horizons are sent
   - `test_followups_command_on_off`: Toggle works correctly
   - `test_followups_command_selective`: `/followups 1h,7d` sets correct horizons

7. **Quiet hours**:
   - `test_followup_deferred_during_quiet_hours`: Not sent, next_check_at advanced
   - `test_followup_sent_after_quiet_hours`: Sent when quiet hours end

### Integration Tests

1. `test_alert_creates_followup_row`: Sending an alert via alert_engine creates tracking row
2. `test_event_consumer_creates_followup_row`: Event-based alert also creates tracking row
3. `test_end_to_end_followup_lifecycle`: Create alert, populate outcome, run checker, verify message sent

### Mock Strategy

Mock `send_telegram_message`, `get_session()`, and `datetime.utcnow()` for deterministic timing tests. Use the existing `mock_sync_session` pattern from `shit_tests/notifications/conftest.py`.

---

## Open Questions

1. **Should T+1h follow-ups use intraday data or daily close?** Currently `return_1h` comes from `IntradayPriceSnapshot` captured at analysis time. If not captured (market closed when post was made), the follow-up defers until the data is available -- which may never happen for after-hours posts. Consider: only send T+1h follow-ups for posts made during market hours.

2. **Should follow-ups reference the original alert message ID?** Telegram supports `reply_to_message_id` to thread a follow-up as a reply to the original alert. This would visually link them in the chat. However, we don't currently store the Telegram `message_id` of sent alerts. Adding this requires modifying `send_telegram_message` to return the message_id and storing it. Recommended for v2.

3. **How to handle corporate actions?** If a stock splits between the prediction and T+7d, the return calculation may be wrong. The `prediction_outcomes` table has a `notes` field for this. For v1, trust the outcome calculator's math (which uses adjusted prices). If `notes` contains "split" or "dividend", add a footnote to the follow-up message.

4. **Should we aggregate follow-ups with the morning briefing?** Feature 07 (Pre-Market Briefing) sends at 8:30 AM ET. If T+1d follow-ups are also due in the morning, should they be combined? Recommendation: keep them separate. The briefing is about new activity; follow-ups are about past predictions. Different purposes, different messages.

5. **What about predictions with no outcomes?** If `prediction_outcomes` has no rows for a prediction (e.g., ticker was invalid, backfill failed), the follow-up has no data to report. After 48 hours of deferral, abandon the follow-up silently. Consider sending a "data unavailable" message instead.

6. **Storage growth**: With ~15 predictions/day and ~5 subscribers, that's ~75 follow-up rows/day. After a year, ~27,000 rows. Trivial for PostgreSQL. Add a cleanup job to delete completed rows older than 90 days if desired.

---

## Implementation Order

1. **Phase 1**: Create `alert_followups` table. Create `notifications/followups.py` with tracking creation, due detection, and message formatting. Full unit tests.
2. **Phase 2**: Integrate follow-up creation into `alert_engine.py` and `event_consumer.py`. Add `/followups` bot command.
3. **Phase 3**: Create `followup_cron.py` entry point. Deploy to Railway as `followup-sender` service.
4. **Phase 4**: Monitor for a week. Tune timing, message format, and daily limits based on real data.
