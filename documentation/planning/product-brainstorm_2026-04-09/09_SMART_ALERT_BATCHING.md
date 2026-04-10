# Feature 09: Smart Alert Batching

**Status:** Planning
**Date:** 2026-04-09
**Priority:** High -- directly addresses alert fatigue, the #1 user experience problem

---

## Overview

When Trump posts a rapid-fire burst of 5-10 posts in 20 minutes (a "rage-tweet storm"), subscribers currently receive 5-10 individual Telegram alerts in rapid succession. This is noisy, overwhelming, and causes users to mute or unsubscribe.

Smart Alert Batching groups related posts within a configurable time window (default: 30 minutes) and sends a single consolidated alert with a burst summary. An urgency override mechanism ensures that exceptionally high-confidence predictions break out of the batch and fire immediately.

---

## Motivation

### The Problem

Trump frequently posts in bursts. Historical data shows clusters of 3-8 posts within 15-30 minute windows. Each post triggers an independent `PREDICTION_CREATED` event, which flows through the notifications worker and fires a separate Telegram alert. Users receive a wall of nearly identical alerts:

```
[12:01] BULLISH ALERT - TSLA (82% confidence)
[12:03] BEARISH ALERT - F (75% confidence)
[12:05] BULLISH ALERT - TSLA (78% confidence)
[12:08] NEUTRAL ALERT - SPY (71% confidence)
[12:12] BULLISH ALERT - XLE (80% confidence)
```

This causes:
1. **Alert fatigue** -- users stop reading alerts
2. **Unsubscribes** -- users mute or /stop the bot
3. **Missed signals** -- the truly important alert gets lost in the noise
4. **Redundancy** -- multiple posts about the same topic (TSLA) produce near-duplicate alerts

### The Solution

Instead of firing immediately, the notifications worker holds alerts in a batch buffer. When the batch window closes (30 minutes of silence, or a hard cap), it sends one consolidated message:

```
SHITPOST ALPHA - BURST ALERT (5 posts in 14 minutes)

Dominant Theme: Auto industry and energy policy
Top Signal: BULLISH on TSLA (82% confidence)

Assets Mentioned: TSLA (3x), F (1x), XLE (1x), SPY (1x)
Average Confidence: 77%

Key Thesis: Multiple posts attacking traditional automakers
while praising Tesla and domestic energy. Strong bullish
signal for TSLA and XLE.

[View all 5 posts on dashboard]
```

---

## Burst Detection Algorithm

### Time-Window Approach

The batching system uses a **sliding time window** with two closing conditions:

1. **Silence timeout** -- no new prediction arrives within `BATCH_WINDOW_SECONDS` (default: 1800 = 30 min) of the last prediction in the batch
2. **Hard cap** -- the batch has been open for `MAX_BATCH_DURATION_SECONDS` (default: 3600 = 60 min)

```
Timeline:
  T=0    Post A arrives → start batch, set timer for 30 min
  T=3    Post B arrives → reset timer to 30 min from now
  T=8    Post C arrives → reset timer to 30 min from now
  T=45   No new posts   → timer expires, flush batch (A + B + C)
```

### Configuration

```python
# notifications/batch_config.py

from dataclasses import dataclass

@dataclass
class BatchConfig:
    """Configuration for alert batching behavior."""

    # Time window: how long to wait for more posts before flushing
    batch_window_seconds: int = 1800  # 30 minutes

    # Hard cap: maximum time a batch can stay open
    max_batch_duration_seconds: int = 3600  # 60 minutes

    # Minimum posts to trigger batch mode (1 = always batch, 2+ = only batch bursts)
    min_batch_size: int = 2

    # Urgency override: confidence threshold for immediate send
    urgency_confidence_threshold: float = 0.85

    # Urgency override: urgency_score threshold for immediate send
    urgency_score_threshold: float = 0.85

    # Whether to use LLM for burst summarization (vs rule-based)
    use_llm_summary: bool = False

    # Maximum LLM summary cost per burst (in tokens)
    max_summary_tokens: int = 500
```

### Post Rate Detection

To identify bursts vs. isolated posts, the system tracks recent prediction timestamps:

```python
def is_burst_starting(self, current_prediction_time: datetime) -> bool:
    """Determine if a new prediction is part of a burst.

    A burst is detected when 2+ predictions arrive within
    BURST_DETECTION_WINDOW (default 10 minutes).
    """
    if not self._recent_predictions:
        return False

    last_prediction_time = self._recent_predictions[-1].timestamp
    gap = (current_prediction_time - last_prediction_time).total_seconds()
    return gap <= self.config.batch_window_seconds
```

---

## Urgency Override

### When to Break the Batch

Some predictions are too important to hold. The batch is flushed immediately -- and the triggering prediction is sent as a standalone alert -- when ANY of these conditions are met:

1. **High confidence**: `prediction.confidence >= 0.85`
2. **High urgency score**: `prediction.urgency_score >= 0.85` (from LLM analysis)
3. **Manual flag**: A future admin command could force-flush

### Override Logic

```python
# notifications/batch_manager.py

def should_send_immediately(self, alert: dict) -> bool:
    """Check if an alert should bypass batching and send immediately.

    Args:
        alert: Alert dict with confidence, urgency_score, etc.

    Returns:
        True if the alert should be sent immediately.
    """
    confidence = alert.get("confidence", 0) or 0
    urgency = alert.get("urgency_score", 0) or 0

    if confidence >= self.config.urgency_confidence_threshold:
        return True
    if urgency >= self.config.urgency_score_threshold:
        return True

    return False
```

### Behavior When Override Fires

When an override occurs mid-batch:

1. The urgent alert is sent **immediately** as a standalone message (standard format)
2. The remaining batch continues accumulating
3. When the batch window closes, the consolidated alert is sent **without** the urgent post (it was already sent)
4. The consolidated alert references the urgent post: "Note: 1 high-priority alert was sent separately"

---

## Summarization Strategy

### Option A: Rule-Based Merging (Default)

No LLM call. Aggregate the batch using structured data from existing predictions:

```python
# notifications/batch_summarizer.py

def summarize_batch_rule_based(alerts: list[dict]) -> dict:
    """Generate a burst summary from structured prediction data.

    Args:
        alerts: List of alert dicts from the batch.

    Returns:
        Summary dict with theme, top_signal, assets, avg_confidence.
    """
    # Collect all assets across the batch
    all_assets: dict[str, int] = {}
    for alert in alerts:
        for asset in alert.get("assets", []):
            all_assets[asset] = all_assets.get(asset, 0) + 1

    # Sort by frequency
    sorted_assets = sorted(all_assets.items(), key=lambda x: -x[1])

    # Find the highest-confidence prediction
    top_alert = max(alerts, key=lambda a: a.get("confidence", 0) or 0)

    # Determine dominant sentiment
    sentiments = [a.get("sentiment", "neutral") for a in alerts]
    sentiment_counts = {}
    for s in sentiments:
        sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
    dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)

    # Average confidence
    confidences = [a.get("confidence", 0) for a in alerts if a.get("confidence")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Build asset string: "TSLA (3x), F (1x), XLE (1x)"
    asset_str = ", ".join(
        f"{sym} ({count}x)" if count > 1 else sym
        for sym, count in sorted_assets[:6]
    )

    return {
        "post_count": len(alerts),
        "dominant_sentiment": dominant_sentiment,
        "top_signal": top_alert,
        "assets_summary": asset_str,
        "sorted_assets": sorted_assets,
        "avg_confidence": avg_confidence,
        "sentiments": sentiment_counts,
    }
```

**Pros:** Zero cost, zero latency, deterministic.
**Cons:** Cannot synthesize a narrative thesis across posts.

### Option B: LLM Burst Summary (Opt-in)

Use the existing `LLMClient` to generate a narrative summary from the batch:

```python
async def summarize_batch_llm(alerts: list[dict]) -> str:
    """Generate an LLM-powered narrative summary of a post burst.

    Uses the existing LLMClient with a burst-specific prompt.
    Cost: ~500 tokens per burst (~$0.015 with GPT-4).

    Args:
        alerts: List of alert dicts from the batch.

    Returns:
        Narrative summary string (max 200 chars).
    """
    from shit.llm import LLMClient

    # Build compact context from batch
    post_summaries = []
    for i, alert in enumerate(alerts, 1):
        text = alert.get("text", "")[:100]
        assets = ", ".join(alert.get("assets", []))
        sentiment = alert.get("sentiment", "neutral")
        conf = alert.get("confidence", 0)
        post_summaries.append(
            f"Post {i}: [{sentiment}, {conf:.0%}] {assets} - {text}"
        )

    prompt = f"""Summarize this burst of {len(alerts)} social media posts into a single 1-2 sentence market thesis. Focus on the dominant financial signal.

Posts:
{chr(10).join(post_summaries)}

Summary (max 200 characters):"""

    client = LLMClient()
    await client.initialize()
    response = await client.raw_completion(
        prompt=prompt,
        max_tokens=100,
        temperature=0.3,
    )
    return response.strip()[:200]
```

**Pros:** Produces a coherent narrative ("Trump is on a tear against automakers -- strongly bullish TSLA, bearish legacy auto").
**Cons:** ~$0.015 per burst, adds 2-5s latency, requires async context.

### Recommendation

Start with **Option A (rule-based)** as default. Add Option B behind the `use_llm_summary` config flag. The rule-based approach handles 90% of cases well enough, and the LLM summary can be enabled for premium subscribers or high-value bursts (5+ posts).

---

## State Management

### Approach: Database Table

Worker memory is lost on restart (Railway cron mode uses `--once`). State must be persisted in the database.

#### New Table: `alert_batches`

```sql
CREATE TABLE alert_batches (
    id SERIAL PRIMARY KEY,

    -- Batch identification
    batch_id VARCHAR(50) UNIQUE NOT NULL,       -- UUID for this batch
    status VARCHAR(20) NOT NULL DEFAULT 'open', -- open, flushed, expired

    -- Timing
    opened_at TIMESTAMP NOT NULL,               -- When first alert entered batch
    last_alert_at TIMESTAMP NOT NULL,           -- When last alert was added
    flushed_at TIMESTAMP,                       -- When batch was sent
    expires_at TIMESTAMP NOT NULL,              -- Hard cap deadline

    -- Content
    alert_count INTEGER NOT NULL DEFAULT 0,     -- Number of alerts in batch
    alert_data JSONB NOT NULL DEFAULT '[]',     -- Array of alert dicts
    summary JSONB,                              -- Computed summary (after flush)

    -- Metrics
    urgent_bypasses INTEGER DEFAULT 0,          -- Alerts that bypassed this batch
    avg_confidence FLOAT,                       -- Computed at flush

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alert_batches_status ON alert_batches (status);
CREATE INDEX idx_alert_batches_expires_at ON alert_batches (expires_at) WHERE status = 'open';
```

#### SQLAlchemy Model

```python
# notifications/models.py (add to existing file)

class AlertBatch(Base, IDMixin, TimestampMixin):
    """Tracks open and closed alert batches for burst grouping."""

    __tablename__ = "alert_batches"

    batch_id = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open")  # open, flushed, expired

    opened_at = Column(DateTime, nullable=False)
    last_alert_at = Column(DateTime, nullable=False)
    flushed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)

    alert_count = Column(Integer, nullable=False, default=0)
    alert_data = Column(JSON, nullable=False, default=list)  # Array of alert dicts
    summary = Column(JSON, nullable=True)

    urgent_bypasses = Column(Integer, default=0)
    avg_confidence = Column(Float, nullable=True)
```

### Handling Worker Restarts

The notifications worker runs on Railway cron (`--once` mode, every 5 minutes). On each invocation:

1. **Check for open batches** -- query `alert_batches WHERE status = 'open'`
2. **Check if any open batch should be flushed:**
   - `last_alert_at + batch_window_seconds < NOW()` (silence timeout)
   - `expires_at < NOW()` (hard cap)
3. **Flush expired batches** -- send consolidated alerts, mark `status = 'flushed'`
4. **Process new events** -- for each `PREDICTION_CREATED` event:
   - Check urgency override -> send immediately if triggered
   - Otherwise, add to open batch (or create new batch)
5. **Exit** -- batch remains open in DB for next invocation

This means a batch might span multiple worker invocations. The 5-minute Railway cron interval naturally provides the polling mechanism.

---

## Batch Manager: Core Implementation

```python
# notifications/batch_manager.py

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from notifications.batch_config import BatchConfig
from notifications.batch_summarizer import summarize_batch_rule_based
from notifications.db import _execute_read, _execute_write, _row_to_dict, _rows_to_dicts
from shit.logging import get_service_logger

logger = get_service_logger("batch_manager")


class BatchManager:
    """Manages alert batching lifecycle: open, accumulate, flush.

    Designed to work across Railway cron invocations by persisting
    batch state in the alert_batches table.
    """

    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()

    def get_open_batch(self) -> Optional[dict]:
        """Get the currently open batch, if any.

        Returns:
            Batch dict or None.
        """
        return _execute_read(
            """
            SELECT * FROM alert_batches
            WHERE status = 'open'
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            processor=_row_to_dict,
            default=None,
            context="get_open_batch",
        )

    def should_flush(self, batch: dict) -> bool:
        """Determine if an open batch should be flushed.

        Args:
            batch: Batch dict from database.

        Returns:
            True if the batch should be flushed now.
        """
        now = datetime.now(timezone.utc)
        last_alert_at = batch["last_alert_at"]
        expires_at = batch["expires_at"]

        # Silence timeout: no new alerts within window
        silence_deadline = last_alert_at + timedelta(
            seconds=self.config.batch_window_seconds
        )
        if now >= silence_deadline:
            return True

        # Hard cap: batch has been open too long
        if now >= expires_at:
            return True

        return False

    def add_to_batch(self, alert: dict) -> str:
        """Add an alert to the current open batch, or create a new one.

        Args:
            alert: Alert dict with prediction data.

        Returns:
            batch_id of the batch the alert was added to.
        """
        batch = self.get_open_batch()
        now = datetime.now(timezone.utc)

        if batch is None:
            # Create new batch
            batch_id = str(uuid.uuid4())[:12]
            expires_at = now + timedelta(
                seconds=self.config.max_batch_duration_seconds
            )
            _execute_write(
                """
                INSERT INTO alert_batches
                    (batch_id, status, opened_at, last_alert_at, expires_at,
                     alert_count, alert_data)
                VALUES
                    (:batch_id, 'open', :now, :now, :expires_at, 1, :alert_data)
                """,
                params={
                    "batch_id": batch_id,
                    "now": now,
                    "expires_at": expires_at,
                    "alert_data": json.dumps([alert]),
                },
                context="create_batch",
            )
            return batch_id
        else:
            # Append to existing batch
            batch_id = batch["batch_id"]
            existing_alerts = batch.get("alert_data", [])
            if isinstance(existing_alerts, str):
                existing_alerts = json.loads(existing_alerts)
            existing_alerts.append(alert)

            _execute_write(
                """
                UPDATE alert_batches
                SET alert_data = :alert_data,
                    alert_count = :count,
                    last_alert_at = :now,
                    updated_at = :now
                WHERE batch_id = :batch_id AND status = 'open'
                """,
                params={
                    "alert_data": json.dumps(existing_alerts),
                    "count": len(existing_alerts),
                    "now": now,
                    "batch_id": batch_id,
                },
                context="add_to_batch",
            )
            return batch_id

    def flush_batch(self, batch_id: str) -> dict:
        """Flush a batch: generate summary and mark as flushed.

        Args:
            batch_id: ID of the batch to flush.

        Returns:
            Summary dict for message formatting.
        """
        batch = _execute_read(
            "SELECT * FROM alert_batches WHERE batch_id = :batch_id",
            params={"batch_id": batch_id},
            processor=_row_to_dict,
            default=None,
            context="get_batch_for_flush",
        )

        if not batch:
            return {}

        alerts = batch.get("alert_data", [])
        if isinstance(alerts, str):
            alerts = json.loads(alerts)

        summary = summarize_batch_rule_based(alerts)
        now = datetime.now(timezone.utc)

        _execute_write(
            """
            UPDATE alert_batches
            SET status = 'flushed',
                flushed_at = :now,
                summary = :summary,
                avg_confidence = :avg_conf,
                updated_at = :now
            WHERE batch_id = :batch_id
            """,
            params={
                "now": now,
                "summary": json.dumps(summary),
                "avg_conf": summary.get("avg_confidence"),
                "batch_id": batch_id,
            },
            context="flush_batch",
        )

        return summary
```

---

## Message Design: Consolidated Alert Format

### Telegram MarkdownV2 Template

```python
# notifications/telegram_sender.py (add new function)

def format_batch_alert(summary: dict, batch: dict) -> str:
    """Format a batch of alerts into a consolidated Telegram message.

    Args:
        summary: Summary dict from summarize_batch_rule_based().
        batch: Batch dict from alert_batches table.

    Returns:
        Formatted MarkdownV2 string.
    """
    post_count = summary["post_count"]
    top = summary["top_signal"]
    top_sentiment = top.get("sentiment", "neutral").upper()
    top_conf = top.get("confidence", 0)
    top_assets = ", ".join(top.get("assets", [])[:3])
    avg_conf = summary["avg_confidence"]
    assets_summary = summary["assets_summary"]
    dominant = summary["dominant_sentiment"].upper()

    # Duration
    opened = batch["opened_at"]
    last = batch["last_alert_at"]
    if isinstance(opened, str):
        opened = datetime.fromisoformat(opened)
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    duration_min = int((last - opened).total_seconds() / 60)

    # Sentiment emoji for dominant sentiment
    emoji = {"BULLISH": "\U0001f7e2", "BEARISH": "\U0001f534"}.get(
        dominant, "\u26aa"
    )

    # Sentiment breakdown line
    sentiments = summary.get("sentiments", {})
    sent_parts = []
    for s, count in sorted(sentiments.items(), key=lambda x: -x[1]):
        sent_parts.append(f"{s.capitalize()}: {count}")
    sentiment_line = " | ".join(sent_parts)

    urgent_note = ""
    bypasses = batch.get("urgent_bypasses", 0)
    if bypasses:
        urgent_note = (
            f"\n_Note: {bypasses} high\\-priority "
            f"alert{'s' if bypasses != 1 else ''} sent separately\\._"
        )

    return f"""{emoji} *SHITPOST ALPHA \\- BURST ALERT*
_{escape_markdown(f"{post_count} posts in {duration_min} minutes")}_

*Dominant Sentiment:* {escape_markdown(dominant)}
*Top Signal:* {escape_markdown(top_sentiment)} on {escape_markdown(top_assets)} \\({escape_markdown(f"{top_conf:.0%}")} confidence\\)

*Assets Mentioned:* {escape_markdown(assets_summary)}
*Average Confidence:* {escape_markdown(f"{avg_conf:.0%}")}
*Sentiment Breakdown:* {escape_markdown(sentiment_line)}

\U0001f4a1 *Top Thesis:*
{escape_markdown(top.get("thesis", "")[:200])}{urgent_note}

\u26a0\ufe0f _This is NOT financial advice\\. For entertainment only\\._"""
```

---

## Integration with Notifications Worker

### Modified Event Consumer

The `NotificationsWorker.process_event()` method is the integration point. Instead of immediately dispatching alerts, it routes through the batch manager:

```python
# notifications/event_consumer.py (modified process_event)

class NotificationsWorker(EventWorker):
    """Processes prediction_created events with optional batching."""

    consumer_group = ConsumerGroup.NOTIFICATIONS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._batch_manager = None  # Lazy init

    @property
    def batch_manager(self):
        if self._batch_manager is None:
            from notifications.batch_manager import BatchManager
            self._batch_manager = BatchManager()
        return self._batch_manager

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a prediction_created event with batching support."""
        from notifications.alert_engine import filter_predictions_by_preferences
        from notifications.db import get_active_subscriptions, record_alert_sent, record_error
        from notifications.telegram_sender import (
            format_telegram_alert, format_batch_alert,
            send_telegram_message,
        )

        analysis_status = payload.get("analysis_status", "")
        if analysis_status != "completed":
            return {"skipped": True, "reason": f"status={analysis_status}"}

        # Build alert from event payload
        alert = self._build_alert(payload)

        # Check urgency override
        if self.batch_manager.should_send_immediately(alert):
            # Send immediately (bypass batch)
            results = self._dispatch_alert_to_subscribers(alert)
            # Record bypass on open batch if one exists
            self.batch_manager.record_urgent_bypass()
            return {**results, "batched": False, "urgent": True}

        # Add to batch
        batch_id = self.batch_manager.add_to_batch(alert)
        return {"batched": True, "batch_id": batch_id}

    def run_once(self) -> int:
        """Extended run_once that also flushes expired batches."""
        # First, flush any expired batches
        self._flush_expired_batches()

        # Then process new events normally
        total = super().run_once()

        # Check again after processing (new alerts may have closed a batch)
        self._flush_expired_batches()

        return total

    def _flush_expired_batches(self) -> int:
        """Flush all batches that have hit their timeout or hard cap."""
        flushed = 0
        batch = self.batch_manager.get_open_batch()
        while batch and self.batch_manager.should_flush(batch):
            summary = self.batch_manager.flush_batch(batch["batch_id"])
            if summary and summary.get("post_count", 0) > 0:
                self._dispatch_batch_to_subscribers(summary, batch)
                flushed += 1
            batch = self.batch_manager.get_open_batch()
        return flushed
```

### Single-Post Passthrough

When `min_batch_size = 2` (default) and only 1 post arrives before the window closes, the system sends it as a standard individual alert (not a "burst of 1"). The `flush_batch` method detects single-alert batches and falls back to the standard `format_telegram_alert` format.

---

## User Preferences: Opt-Out of Batching

### New Preference Key

Add to `alert_preferences` JSON:

```python
{
    "min_confidence": 0.7,
    "assets_of_interest": [],
    "sentiment_filter": "all",
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "batching_enabled": True,          # NEW -- default True
}
```

### Telegram Command

```
/settings batching on   -> Enable burst batching (default)
/settings batching off  -> Disable batching, receive all alerts individually
```

### Implementation in Dispatcher

When dispatching a flushed batch, check each subscriber's `batching_enabled` preference:
- If `True` (default): send the consolidated batch alert
- If `False`: send each alert individually (fall back to current behavior)

This means the batch is still accumulated and summarized centrally, but per-subscriber dispatch respects the preference.

---

## Integration with Always-On Harvester

### Current Architecture

The harvester runs on Railway cron every 5 minutes. Posts arrive in batches corresponding to the cron interval:

```
[5-min cron] Harvest 0-N posts → POSTS_HARVESTED event
  → S3 processor → SIGNALS_STORED event
  → Analyzer → PREDICTION_CREATED event (one per post)
  → Notifications worker → Alert
```

### Implication for Batching

Since the harvester already batches posts by 5-minute intervals, a burst of 10 posts may all arrive at the analyzer within the same cron cycle. The `PREDICTION_CREATED` events will fire in rapid succession (seconds apart). The batch manager will:

1. Receive first event, create batch (or add to existing open batch)
2. Receive remaining events, add to same batch
3. On the next cron invocation (5 min later), check if the batch should flush
4. If silence timeout (30 min) hasn't elapsed, the batch stays open
5. If no new posts arrive for 30 minutes, the next cron run flushes it

**Worst case latency:** 30 minutes (silence timeout) + 5 minutes (cron interval) = **35 minutes** from last post to consolidated alert. This is acceptable for a "digest" experience, and the urgency override ensures critical signals are never delayed.

### Future: Streaming Mode

If the notifications worker switches to persistent mode (`worker.run()` instead of `--once`), the batch manager works identically -- the poll interval (2s) simply checks `should_flush()` more frequently, reducing flush latency from 5 minutes to seconds.

---

## Testing Strategy

### Unit Tests

```python
# shit_tests/notifications/test_batch_manager.py

class TestBatchManager:
    """Tests for alert batching logic."""

    def test_create_batch_on_first_alert(self, mock_sync_session):
        """First alert creates a new batch."""
        manager = BatchManager()
        alert = make_alert(confidence=0.75, assets=["TSLA"])
        batch_id = manager.add_to_batch(alert)
        assert batch_id is not None

    def test_add_to_existing_batch(self, mock_sync_session):
        """Second alert joins existing open batch."""
        manager = BatchManager()
        alert1 = make_alert(confidence=0.75, assets=["TSLA"])
        alert2 = make_alert(confidence=0.80, assets=["F"])
        id1 = manager.add_to_batch(alert1)
        id2 = manager.add_to_batch(alert2)
        assert id1 == id2

    def test_urgency_override_high_confidence(self):
        """Alert with confidence >= 0.85 bypasses batch."""
        manager = BatchManager()
        alert = make_alert(confidence=0.90, assets=["TSLA"])
        assert manager.should_send_immediately(alert) is True

    def test_urgency_override_below_threshold(self):
        """Alert with confidence < 0.85 enters batch."""
        manager = BatchManager()
        alert = make_alert(confidence=0.80, assets=["TSLA"])
        assert manager.should_send_immediately(alert) is False

    def test_silence_timeout_flush(self, mock_sync_session, freezer):
        """Batch flushes after silence timeout."""
        manager = BatchManager(config=BatchConfig(batch_window_seconds=300))
        alert = make_alert(confidence=0.75)
        manager.add_to_batch(alert)

        # Move time forward past the silence window
        freezer.move_to(timedelta(seconds=301))
        batch = manager.get_open_batch()
        assert manager.should_flush(batch) is True

    def test_hard_cap_flush(self, mock_sync_session, freezer):
        """Batch flushes at hard cap even with recent alerts."""
        manager = BatchManager(
            config=BatchConfig(max_batch_duration_seconds=600)
        )
        # Add alerts over 10+ minutes
        for i in range(5):
            freezer.move_to(timedelta(seconds=i * 120))
            manager.add_to_batch(make_alert(confidence=0.75))

        batch = manager.get_open_batch()
        assert manager.should_flush(batch) is True

    def test_single_post_passthrough(self, mock_sync_session, freezer):
        """Single-post batch sends as individual alert, not burst."""
        manager = BatchManager(config=BatchConfig(min_batch_size=2))
        alert = make_alert(confidence=0.75)
        manager.add_to_batch(alert)

        freezer.move_to(timedelta(seconds=1801))
        batch = manager.get_open_batch()
        summary = manager.flush_batch(batch["batch_id"])
        assert summary["post_count"] == 1
        # Caller should detect post_count < min_batch_size and use individual format


class TestBatchSummarizer:
    """Tests for burst summarization."""

    def test_rule_based_summary_assets(self):
        """Assets are counted and sorted by frequency."""
        alerts = [
            make_alert(assets=["TSLA", "F"]),
            make_alert(assets=["TSLA"]),
            make_alert(assets=["TSLA", "XLE"]),
        ]
        summary = summarize_batch_rule_based(alerts)
        assert summary["sorted_assets"][0] == ("TSLA", 3)

    def test_rule_based_summary_sentiment(self):
        """Dominant sentiment is correctly identified."""
        alerts = [
            make_alert(sentiment="bullish"),
            make_alert(sentiment="bullish"),
            make_alert(sentiment="bearish"),
        ]
        summary = summarize_batch_rule_based(alerts)
        assert summary["dominant_sentiment"] == "bullish"

    def test_rule_based_summary_top_signal(self):
        """Top signal is the highest confidence alert."""
        alerts = [
            make_alert(confidence=0.75),
            make_alert(confidence=0.85),
            make_alert(confidence=0.70),
        ]
        summary = summarize_batch_rule_based(alerts)
        assert summary["top_signal"]["confidence"] == 0.85


class TestBatchMessageFormat:
    """Tests for consolidated alert message formatting."""

    def test_batch_alert_contains_post_count(self):
        summary = {"post_count": 5, ...}
        message = format_batch_alert(summary, batch)
        assert "5 posts" in message

    def test_batch_alert_contains_top_signal(self):
        ...

    def test_batch_alert_mentions_urgent_bypasses(self):
        batch = {"urgent_bypasses": 2, ...}
        message = format_batch_alert(summary, batch)
        assert "2 high-priority" in message
```

### Integration Tests

```python
# shit_tests/notifications/test_batch_integration.py

class TestBatchingIntegration:
    """End-to-end batching through the notifications worker."""

    def test_burst_of_three_produces_single_alert(self, mock_sync_session, mock_telegram):
        """Three rapid predictions produce one consolidated Telegram message."""
        worker = NotificationsWorker()

        # Simulate 3 rapid events
        for i in range(3):
            worker.process_event("prediction_created", make_payload(i))

        # Force flush
        worker._flush_expired_batches()

        # Should have sent 1 message (not 3)
        assert mock_telegram.send_count == 1
        assert "BURST ALERT" in mock_telegram.last_message

    def test_urgent_alert_bypasses_batch(self, mock_sync_session, mock_telegram):
        """High-confidence alert sends immediately + batch continues."""
        worker = NotificationsWorker()

        worker.process_event("prediction_created", make_payload(confidence=0.75))
        worker.process_event("prediction_created", make_payload(confidence=0.92))
        worker.process_event("prediction_created", make_payload(confidence=0.78))

        # Urgent alert should have fired immediately
        assert mock_telegram.send_count == 1  # Just the urgent one

        # Flush the batch
        worker._flush_expired_batches()
        assert mock_telegram.send_count == 2  # Batch + urgent
```

---

## Migration Plan

### Database Migration

```sql
-- Migration: Add alert_batches table
CREATE TABLE alert_batches (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    opened_at TIMESTAMP NOT NULL,
    last_alert_at TIMESTAMP NOT NULL,
    flushed_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    alert_count INTEGER NOT NULL DEFAULT 0,
    alert_data JSONB NOT NULL DEFAULT '[]',
    summary JSONB,
    urgent_bypasses INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alert_batches_status ON alert_batches (status);
CREATE INDEX idx_alert_batches_expires_at ON alert_batches (expires_at)
    WHERE status = 'open';
```

### Rollback Plan

Batching can be disabled by setting `ALERT_BATCHING_ENABLED=false` in Railway environment variables. The notifications worker falls back to the existing immediate-dispatch behavior.

---

## Files to Create/Modify

### New Files
- `notifications/batch_config.py` -- BatchConfig dataclass
- `notifications/batch_manager.py` -- BatchManager class (core logic)
- `notifications/batch_summarizer.py` -- Rule-based and LLM summarization
- `shit_tests/notifications/test_batch_manager.py` -- Unit tests
- `shit_tests/notifications/test_batch_summarizer.py` -- Summarizer tests
- `shit_tests/notifications/test_batch_integration.py` -- Integration tests

### Modified Files
- `notifications/models.py` -- Add AlertBatch model
- `notifications/event_consumer.py` -- Integrate BatchManager into process_event
- `notifications/telegram_sender.py` -- Add `format_batch_alert()` function
- `notifications/telegram_bot.py` -- Add `/settings batching on|off` handler
- `notifications/db.py` -- Add batch-related query helpers if needed
- `shit/config/shitpost_settings.py` -- Add `ALERT_BATCHING_ENABLED` setting

---

## Open Questions

1. **Window duration** -- Is 30 minutes the right default? Should we analyze historical burst patterns to calibrate?
2. **LLM cost ceiling** -- If LLM summarization is enabled, should there be a daily budget cap?
3. **Group chats** -- Do group chats get the same batching as private chats, or should groups always get individual alerts (for discussion threading)?
4. **Batch persistence** -- Should we keep flushed batches indefinitely for analytics, or clean up after 30 days?
5. **Subscriber-specific batching** -- Should batching be per-subscriber (each subscriber has their own batch window) or global (one batch for all)? Global is simpler; per-subscriber handles timezone-based preferences better.
6. **Dashboard integration** -- Should the React frontend show batch history? Would add complexity but provide transparency.
