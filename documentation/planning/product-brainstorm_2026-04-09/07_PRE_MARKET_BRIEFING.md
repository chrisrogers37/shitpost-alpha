# 07: Pre-Market Briefing

**Feature**: Every trading day at 8:30 AM ET, send a Telegram digest summarizing overnight Trump activity, sentiment, and historical context.

**Status**: COMPLETE  
**Started**: 2026-04-11  
**Completed**: 2026-04-11  
**PR**: #137  
**Priority**: Medium  
**Estimated Effort**: 2 sessions  

---

## Overview

Subscribers currently receive individual alerts for each prediction as it's generated. This means a burst of 5 posts overnight results in 5 separate Telegram messages, none of which provide aggregate context. The pre-market briefing is a single daily digest sent at 8:30 AM ET on trading days that summarizes all overnight activity into a coherent morning brief.

The infrastructure is already in place:
- `notifications/telegram_sender.py` sends MarkdownV2 messages to subscribers.
- `notifications/db.py` has `get_active_subscriptions()` with preference filtering.
- `notifications/telegram_bot.py` handles bot commands (/start, /stop, /status, etc.).
- `shit/market_data/market_calendar.py` has `MarketCalendar.is_trading_day()` and `next_trading_day()`.
- `notifications/db.py` has `get_new_predictions_since()` for querying recent predictions.

What's missing: the briefing content assembly, scheduling logic, subscriber opt-in, and the Railway cron service.

---

## Motivation

1. **Context over noise**: Individual alerts lack context. A briefing saying "3 posts overnight, all bearish on auto sector, avg confidence 82%" is more actionable than 3 separate messages.
2. **Pre-market timing**: 8:30 AM ET is 30 minutes before NYSE opens (9:30 AM ET). This gives traders time to review and position before the opening bell.
3. **Quiet night handling**: When Trump doesn't post, a "quiet night" message confirms the system is working and that no activity occurred -- rather than silence that leaves subscribers wondering if the bot is broken.
4. **Engagement driver**: Daily touchpoint keeps subscribers engaged even on low-activity days.

---

## Content Design

### Message Sections

The briefing consists of 4 sections:

1. **Header** -- Date, market status, post count
2. **Activity Summary** -- Net sentiment, top assets, confidence range
3. **Per-Asset Breakdown** -- Each asset with aggregated sentiment and post count
4. **Footer** -- Disclaimer, opt-out instructions

### Example: Active Night (3+ predictions)

```
SHITPOST ALPHA | MORNING BRIEFING
Wednesday, April 9, 2026

OVERNIGHT ACTIVITY: 4 posts analyzed (8:00 PM - 8:30 AM ET)

NET SENTIMENT: BEARISH (3 bearish, 1 neutral)
AVG CONFIDENCE: 82% (range: 72-91%)

ASSET BREAKDOWN:
  TSLA - BEARISH (3 posts, avg conf 85%)
    "Electric vehicles are a scam" (91%)
    "Tesla stock is overvalued" (82%)
    "EVs destroying the auto industry" (83%)
  F - NEUTRAL (1 post, avg conf 72%)
    "Ford makes great trucks" (72%)

OVERNIGHT HIGHLIGHTS:
  Highest conviction: TSLA bearish at 91%
  Most mentioned: TSLA (3 posts)

This is NOT financial advice. For entertainment only.
Reply /briefing off to disable morning briefings.
```

### Example: Quiet Night (0 predictions)

```
SHITPOST ALPHA | MORNING BRIEFING
Wednesday, April 9, 2026

QUIET NIGHT - No market-relevant posts detected.

Last activity: 2 posts yesterday (April 8) - bullish SPY

Have a good trading day!
Reply /briefing off to disable morning briefings.
```

### Example: Light Activity (1-2 predictions)

```
SHITPOST ALPHA | MORNING BRIEFING
Wednesday, April 9, 2026

1 post analyzed overnight

TSLA - BEARISH (85% confidence)
"Tesla is failing, electric cars are a disaster"
Thesis: Direct negative sentiment likely to pressure TSLA at open

This is NOT financial advice. For entertainment only.
Reply /briefing off to disable morning briefings.
```

---

## Scheduling

### Railway Cron Configuration

New Railway service: `briefing-sender`

**Cron schedule**: `30 12 * * 1-5` (12:30 UTC = 8:30 AM ET during EDT)

**DST handling**: The cron runs in UTC. Eastern Time shifts between EDT (UTC-4) and EST (UTC-5):
- EDT (March-November): 8:30 AM ET = 12:30 UTC
- EST (November-March): 8:30 AM ET = 13:30 UTC

**Approach**: Run the cron at both 12:30 and 13:30 UTC year-round. The script checks whether it's currently 8:30 AM ET and exits early if not.

```python
# briefing_cron.py
"""Pre-market briefing sender. Runs twice daily to handle DST shifts."""

from datetime import datetime
from zoneinfo import ZoneInfo

from shit.market_data.market_calendar import MarketCalendar
from notifications.briefing import send_morning_briefing
from shit.logging import setup_cli_logging

ET = ZoneInfo("America/New_York")

def main():
    setup_cli_logging(verbose=True)

    now_et = datetime.now(ET)

    # Only send between 8:25-8:35 AM ET
    if not (8 <= now_et.hour <= 8 and 25 <= now_et.minute <= 35):
        print(f"Not briefing time (current ET: {now_et.strftime('%H:%M')}), exiting")
        return

    # Check if today is a trading day
    calendar = MarketCalendar()
    if not calendar.is_trading_day(now_et.date()):
        print(f"{now_et.date()} is not a trading day, skipping briefing")
        return

    # Send briefing
    result = send_morning_briefing()
    print(f"Briefing sent: {result}")


if __name__ == "__main__":
    main()
```

**Alternative approach**: Single cron at `30 12 * * 1-5` with an ENV var `BRIEFING_TARGET_HOUR_ET=8` that the script uses to compute the correct UTC time dynamically. This avoids running twice.

```python
# Cleaner: compute target time dynamically
target_et = datetime.now(ET).replace(hour=8, minute=30, second=0, microsecond=0)
target_utc = target_et.astimezone(ZoneInfo("UTC"))
# Set Railway cron to this computed UTC hour
```

**Recommendation**: Use the dual-cron approach for simplicity. The extra run exits in < 1 second and costs nothing.

### Market Calendar Integration

```python
from shit.market_data.market_calendar import MarketCalendar

calendar = MarketCalendar()

# Check if today is a trading day
if not calendar.is_trading_day(today):
    return  # Skip weekends and holidays

# Get previous market close time (for query window)
prev_trading_day = calendar.previous_trading_day(today)
# Market closes at 4:00 PM ET
previous_close = datetime.combine(
    prev_trading_day,
    time(16, 0),
    tzinfo=ET,
)
```

### Half-Day Handling

Some trading days close early (e.g., day before Thanksgiving at 1:00 PM ET). The `exchange_calendars` library tracks these. However, the briefing always sends at 8:30 AM ET regardless of close time -- the early close affects the query window for the *next* morning's briefing, not the current one.

---

## Data Queries

### Overnight Predictions Query

The "overnight" window is from the previous market close (4:00 PM ET) to the current briefing time (8:30 AM ET):

```python
def get_overnight_predictions(briefing_time: datetime) -> list[dict]:
    """Get predictions created since last market close.

    Args:
        briefing_time: Current briefing datetime (timezone-aware, ET).

    Returns:
        List of prediction dicts with post text and outcome data.
    """
    ET = ZoneInfo("America/New_York")
    calendar = MarketCalendar()

    # Previous market close = yesterday's trading day at 4:00 PM ET
    prev_trading_day = calendar.previous_trading_day(briefing_time.date())
    window_start = datetime.combine(
        prev_trading_day,
        time(16, 0),
        tzinfo=ET,
    )

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
            s.text as post_text
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
```

### Asset Aggregation

```python
def aggregate_by_asset(predictions: list[dict]) -> dict[str, dict]:
    """Aggregate predictions by asset symbol.

    Returns:
        Dict mapping symbol to:
        {
            "sentiment": "bearish",  # Majority vote
            "count": 3,
            "avg_confidence": 0.82,
            "predictions": [...]     # Individual prediction details
        }
    """
    from collections import Counter, defaultdict

    assets = defaultdict(lambda: {
        "sentiments": [],
        "confidences": [],
        "predictions": [],
    })

    for pred in predictions:
        impact = pred.get("market_impact", {})
        if isinstance(impact, str):
            import json
            impact = json.loads(impact)

        for symbol, sentiment in impact.items():
            assets[symbol]["sentiments"].append(sentiment)
            assets[symbol]["confidences"].append(pred.get("confidence", 0))
            text = pred.get("post_text", "")
            assets[symbol]["predictions"].append({
                "text": text[:80] if text else "",
                "confidence": pred.get("confidence", 0),
                "sentiment": sentiment,
            })

    result = {}
    for symbol, data in assets.items():
        counts = Counter(data["sentiments"])
        majority_sentiment = counts.most_common(1)[0][0]
        result[symbol] = {
            "sentiment": majority_sentiment,
            "count": len(data["sentiments"]),
            "avg_confidence": sum(data["confidences"]) / len(data["confidences"]),
            "min_confidence": min(data["confidences"]),
            "max_confidence": max(data["confidences"]),
            "predictions": data["predictions"],
        }

    return dict(sorted(result.items(), key=lambda x: x[1]["count"], reverse=True))
```

---

## User Preferences

### /briefing Command

Add to `notifications/telegram_bot.py`:

```python
def handle_briefing_command(chat_id: str, args: str) -> str:
    """Handle /briefing command - toggle morning briefing.

    Args:
        chat_id: Telegram chat ID.
        args: Command arguments ("on", "off", or empty for status).

    Returns:
        Response message.
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "You're not subscribed. Send /start first."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        import json
        prefs = json.loads(prefs)

    current = prefs.get("briefing_enabled", True)  # Default: enabled

    if args.strip().lower() == "off":
        prefs["briefing_enabled"] = False
        update_subscription(chat_id, alert_preferences=prefs)
        return "Morning briefings disabled. Send /briefing on to re-enable."
    elif args.strip().lower() == "on":
        prefs["briefing_enabled"] = True
        update_subscription(chat_id, alert_preferences=prefs)
        return "Morning briefings enabled! You'll receive a digest at 8:30 AM ET on trading days."
    else:
        status = "enabled" if current else "disabled"
        return f"Morning briefings are currently {status}.\n\nSend /briefing on or /briefing off to change."
```

### Configurable Delivery Time (Future)

For v1, all briefings send at 8:30 AM ET. Future enhancement: allow subscribers to choose their preferred time:

```python
# Future: in alert_preferences
{
    "briefing_enabled": True,
    "briefing_time": "08:30",  # HH:MM in ET
    "briefing_timezone": "America/New_York"
}
```

This requires changing the cron to run every 5 minutes and checking each subscriber's preferred time. Deferred to v2.

---

## Integration with Other Features

### Historical Echoes (Feature 04)

If the Historical Echoes feature is implemented, the briefing can include a "Similar Past Activity" section:

```
HISTORICAL CONTEXT:
  Similar bearish TSLA posts in the past:
  - Jan 15, 2026: TSLA dropped 3.2% in 7 days
  - Dec 3, 2025: TSLA dropped 1.8% in 7 days
  Average outcome: -2.5% at T+7
```

**Integration point**: After querying overnight predictions, look up similar historical predictions using the echoes API. This is optional -- the briefing works fine without it.

```python
# Optional historical context
if settings.HISTORICAL_ECHOES_ENABLED:
    for symbol, data in asset_summary.items():
        echoes = get_historical_echoes(symbol, data["sentiment"])
        if echoes:
            data["historical_context"] = echoes
```

### Calibration Data (Feature 06)

If confidence calibration is active, show calibrated confidence in the briefing:

```
AVG CONFIDENCE: 82% raw / 71% calibrated (range: 72-91%)
```

**Integration point**: Read `calibrated_confidence` from the prediction records. If not null, show both raw and calibrated.

---

## Edge Cases

### Holidays

`MarketCalendar.is_trading_day()` returns `False` for holidays. No briefing is sent. The next briefing picks up from the last market close.

Example: Good Friday (market closed). Thursday's close is 4:00 PM ET. Monday's briefing covers Thursday 4:00 PM through Monday 8:30 AM -- a 4-day window catching any weekend/holiday posts.

### Half-Days

The market closes early on some days (e.g., 1:00 PM ET on day before Thanksgiving). The briefing still sends at 8:30 AM ET. The query window adjusts:

```python
# For half-days, the previous close time needs to respect early close
# exchange_calendars provides this:
prev_session = calendar._cal.previous_session(pd.Timestamp(today))
close_time = calendar._cal.session_close(prev_session)
# close_time is a pd.Timestamp with the actual close time
```

For v1, use 4:00 PM ET as the universal close time. This is slightly inaccurate for half-days (misses the 1:00-4:00 PM window) but is simpler and covers > 99% of cases.

### Weekend Posts

Posts created on Saturday/Sunday are captured in Monday's briefing. The query window from Friday 4:00 PM to Monday 8:30 AM covers the full weekend.

### Multiple Posts About the Same Asset

Aggregation handles this naturally. If 3 posts mention TSLA, the asset summary shows "TSLA (3 posts, avg confidence 85%)".

### No Active Subscribers

If `get_active_subscriptions()` returns empty (all unsubscribed), the briefing exits early. No messages sent, no errors.

### ScrapeCreators API Outage

If the harvester didn't run overnight (API down), there are no new predictions. The briefing sends the "quiet night" message. This is correct behavior -- the briefing reports on analyzed predictions, not raw posts.

---

## Telegram Formatting

### MarkdownV2 Message Template

```python
def format_briefing_message(
    date_str: str,
    predictions: list[dict],
    asset_summary: dict[str, dict],
) -> str:
    """Format the morning briefing as a Telegram MarkdownV2 message.

    Args:
        date_str: Formatted date string (e.g., "Wednesday, April 9, 2026").
        predictions: List of overnight prediction dicts.
        asset_summary: Aggregated per-asset data.

    Returns:
        MarkdownV2 formatted string.
    """
    lines = []

    # Header
    lines.append("*SHITPOST ALPHA \\| MORNING BRIEFING*")
    lines.append(escape_markdown(date_str))
    lines.append("")

    if not predictions:
        # Quiet night
        lines.append("*QUIET NIGHT* \\- No market\\-relevant posts detected\\.")
        lines.append("")
        lines.append(escape_markdown("Have a good trading day!"))
    else:
        n = len(predictions)
        lines.append(escape_markdown(f"OVERNIGHT ACTIVITY: {n} post{'s' if n != 1 else ''} analyzed"))
        lines.append("")

        # Net sentiment
        all_sentiments = []
        all_confidences = []
        for data in asset_summary.values():
            for p in data["predictions"]:
                all_sentiments.append(p["sentiment"])
                all_confidences.append(p["confidence"])

        from collections import Counter
        sentiment_counts = Counter(all_sentiments)
        dominant = sentiment_counts.most_common(1)[0][0].upper()
        counts_str = ", ".join(f"{c} {s}" for s, c in sentiment_counts.items())

        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        min_conf = min(all_confidences) if all_confidences else 0
        max_conf = max(all_confidences) if all_confidences else 0

        lines.append(escape_markdown(f"NET SENTIMENT: {dominant} ({counts_str})"))
        lines.append(escape_markdown(f"AVG CONFIDENCE: {avg_conf:.0%} (range: {min_conf:.0%}-{max_conf:.0%})"))
        lines.append("")

        # Per-asset breakdown
        lines.append("*ASSET BREAKDOWN:*")
        for symbol, data in asset_summary.items():
            sentiment = data["sentiment"].upper()
            count = data["count"]
            avg = data["avg_confidence"]
            lines.append(escape_markdown(f"  {symbol} - {sentiment} ({count} post{'s' if count != 1 else ''}, avg conf {avg:.0%})"))

            # Show up to 3 posts per asset
            for p in data["predictions"][:3]:
                text_preview = p["text"][:60] + "..." if len(p["text"]) > 60 else p["text"]
                conf_pct = f"{p['confidence']:.0%}"
                lines.append(escape_markdown(f'    "{text_preview}" ({conf_pct})'))

        lines.append("")

    # Footer
    lines.append(escape_markdown("This is NOT financial advice. For entertainment only."))
    lines.append(escape_markdown("Reply /briefing off to disable morning briefings."))

    return "\n".join(lines)
```

### Character Limit

Telegram messages have a 4096 character limit. If the briefing exceeds this (many assets, many posts), truncate:

```python
MAX_TELEGRAM_LENGTH = 4096

message = format_briefing_message(date_str, predictions, asset_summary)
if len(message) > MAX_TELEGRAM_LENGTH:
    # Truncate per-asset breakdown to top 5 assets
    # Reduce post previews to 1 per asset
    # Add "... and N more assets" footer
    message = format_briefing_message_compact(date_str, predictions, asset_summary)
```

---

## Main Briefing Function

### `notifications/briefing.py` (New File)

```python
"""
Pre-market morning briefing for Telegram subscribers.

Sends a daily digest at 8:30 AM ET on trading days summarizing overnight
Trump activity, aggregated sentiment, and per-asset breakdown.
"""

from datetime import datetime, time
from typing import Any, Dict
from zoneinfo import ZoneInfo

from notifications.db import get_active_subscriptions
from notifications.telegram_sender import send_telegram_message, escape_markdown
from shit.logging import get_service_logger

logger = get_service_logger("briefing")

ET = ZoneInfo("America/New_York")


def send_morning_briefing() -> Dict[str, Any]:
    """Send morning briefing to all opted-in subscribers.

    Returns:
        Summary dict: {sent, failed, skipped, total_subscribers}
    """
    results = {"sent": 0, "failed": 0, "skipped": 0, "total_subscribers": 0}

    now_et = datetime.now(ET)

    # Query overnight predictions
    predictions = get_overnight_predictions(now_et)
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
            import json
            prefs = json.loads(prefs)

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
        f"{results['failed']} failed, {results['skipped']} skipped"
    )
    return results
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `notifications/briefing.py` | **NEW** - `send_morning_briefing()`, `get_overnight_predictions()`, `aggregate_by_asset()`, `format_briefing_message()` |
| `notifications/telegram_bot.py` | Add `/briefing` command handler |
| `notifications/db.py` | Add `get_overnight_predictions()` query |
| `briefing_cron.py` | **NEW** - Railway cron entry point |
| `shit_tests/notifications/test_briefing.py` | **NEW** - Unit tests |

---

## Testing Strategy

### Unit Tests (`shit_tests/notifications/test_briefing.py`)

1. **Aggregation tests**:
   - `test_aggregate_single_asset`: One asset mentioned across multiple predictions
   - `test_aggregate_multiple_assets`: Multiple assets, sorted by frequency
   - `test_aggregate_empty_predictions`: No predictions returns empty dict
   - `test_aggregate_mixed_sentiments`: Same asset with conflicting sentiments, majority wins
   - `test_aggregate_json_string_market_impact`: Handle market_impact stored as string vs dict

2. **Formatting tests**:
   - `test_format_active_night`: 3+ predictions, verify all sections present
   - `test_format_quiet_night`: 0 predictions, verify quiet message
   - `test_format_single_prediction`: 1 prediction, simplified format
   - `test_format_respects_character_limit`: Long briefing truncated under 4096 chars
   - `test_format_escapes_markdown`: Special characters properly escaped

3. **Scheduling tests**:
   - `test_skip_non_trading_day`: Saturday/Sunday/holiday skips briefing
   - `test_skip_wrong_time`: Running at 3 PM ET exits early
   - `test_trading_day_sends`: Monday 8:30 AM ET proceeds
   - `test_dst_handling_edt`: March-November, 12:30 UTC = 8:30 AM EDT
   - `test_dst_handling_est`: November-March, 13:30 UTC = 8:30 AM EST

4. **Subscriber preference tests**:
   - `test_briefing_enabled_default`: New subscribers get briefings by default
   - `test_briefing_disabled_skipped`: Opted-out subscribers are skipped
   - `test_briefing_command_on`: `/briefing on` enables briefings
   - `test_briefing_command_off`: `/briefing off` disables briefings
   - `test_briefing_command_status`: `/briefing` (no args) shows current state

5. **Query window tests**:
   - `test_overnight_window_weekday`: Friday 4 PM to Monday 8:30 AM for Monday briefing
   - `test_overnight_window_normal`: Previous day 4 PM to today 8:30 AM
   - `test_overnight_window_holiday`: Spans holiday gap correctly

### Mock Strategy

Mock `get_session()` and `send_telegram_message()`. Use fixed datetime for reproducible scheduling tests:

```python
@pytest.fixture
def mock_trading_day(monkeypatch):
    """Fix datetime to a known trading day (Wednesday 8:30 AM ET)."""
    fixed_time = datetime(2026, 4, 8, 8, 30, tzinfo=ZoneInfo("America/New_York"))
    monkeypatch.setattr("notifications.briefing.datetime", MockDatetime(fixed_time))
```

---

## Open Questions

1. **Should the quiet night message include the last prediction's summary?** Current design shows "Last activity: 2 posts yesterday." This requires an extra query. Keep it simple for v1 -- just say "quiet night."

2. **Should the briefing include price data?** For example, "TSLA closed at $245.50 yesterday." This requires a live price fetch at 8:30 AM. Deferred -- adds latency and complexity for marginal value.

3. **Should we batch with other morning communications?** If Feature 08 (What Happened Follow-ups) sends T+1d follow-ups in the morning, should they be combined into the briefing? Probably not -- follow-ups are about specific past predictions, while the briefing is about new activity. Keep them separate.

4. **Group chat support**: The bot is in some Telegram groups. Should groups receive briefings? Yes, using the same `get_active_subscriptions()` query (groups are subscriptions too). But consider adding a group-specific preference.

5. **Rate limiting for high subscriber count**: With 10 subscribers, sequential sending takes ~10 seconds. With 1000, it takes ~17 minutes. For v1, sequential is fine. Future: use `asyncio.gather` with a semaphore (max 30 concurrent sends per Telegram rate limits).

---

## Implementation Order

1. **Phase 1**: Create `notifications/briefing.py` with query, aggregation, and formatting. Full unit tests.
2. **Phase 2**: Add `/briefing` bot command. Update subscriber preferences.
3. **Phase 3**: Create `briefing_cron.py` entry point with scheduling logic. Deploy to Railway.
4. **Phase 4**: Monitor for a week, adjust formatting based on real data.
