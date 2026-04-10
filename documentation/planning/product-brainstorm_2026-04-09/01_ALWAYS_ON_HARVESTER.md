# 01: Always-On Harvester

**Feature**: Replace the 5-minute cron harvester with a persistent always-on service that polls Truth Social every 15-30 seconds.

**Status**: Planning
**Date**: 2026-04-09
**Estimated Effort**: Medium (2-3 sessions)

---

## Overview

The harvester currently runs as a Railway cron job every 5 minutes (`python -m shitposts --mode incremental`). Each invocation spins up a fresh process, initializes an aiohttp session and S3 client, fetches new posts, stores them to S3, emits a `POSTS_HARVESTED` event, and exits. This means post detection latency ranges from 0 to 5 minutes depending on when a post is published relative to the cron tick.

This design converts the harvester into a persistent always-on Railway service that polls the ScrapeCreators API every 15-30 seconds, cutting worst-case detection latency by 10-20x. The change is surgical -- the `TruthSocialS3Harvester` and `SignalHarvester` base class remain intact; we add a new polling loop wrapper that reuses the existing `_fetch_batch` and S3 write path.

---

## Motivation: Latency Analysis

### Current Pipeline Latency (Worst Case)

| Stage | Latency | Source |
|-------|---------|--------|
| Post published -> Harvester runs | 0-300s | Railway cron (5min interval) |
| API fetch + S3 write | 2-5s | ScrapeCreators API + S3 PutObject |
| Event emission + S3 Processor | 2-10s | PostgreSQL event queue + worker poll |
| LLM analysis | 3-10s | Claude/GPT-4 API |
| Notification dispatch | 2-5s | Telegram API |
| **Total worst case** | **~330s** | |

### Proposed Pipeline Latency (Worst Case)

| Stage | Latency | Source |
|-------|---------|--------|
| Post published -> Harvester detects | 0-30s | Always-on polling (30s interval) |
| API fetch + S3 write | 2-5s | Same |
| Event emission + downstream | 2-10s | Same |
| LLM analysis | 3-10s | Same |
| Notification dispatch | 2-5s | Same |
| **Total worst case** | **~60s** | |

Worst-case detection latency drops from 300s to 30s. Combined with the existing event-driven pipeline, end-to-end time from post to Telegram alert drops from ~5.5 minutes to ~1 minute.

### Why Not WebSockets / Server-Sent Events?

ScrapeCreators does not offer a streaming API. The only interface is `GET /v1/truthsocial/user/posts?user_id=...&limit=N`. Polling is the only option. The 15-30 second interval balances latency with API rate limits.

---

## Architecture

### Polling Loop Design

The always-on harvester wraps `TruthSocialS3Harvester` in a persistent loop. Each poll cycle calls `_fetch_batch(cursor=None)` with `limit=20` (the API default) to get the most recent posts, then compares against known post IDs to identify new ones.

```
                  ┌──────────────────────────────┐
                  │   AlwaysOnHarvester          │
                  │                              │
                  │  ┌─────────────┐             │
          ┌───────│──│ Poll Timer  │◄──── 30s ───│──── asyncio.sleep(interval)
          │       │  └──────┬──────┘             │
          │       │         │                    │
          │       │  ┌──────▼──────┐             │
          │       │  │ _fetch_batch│ (limit=20)  │
          │       │  └──────┬──────┘             │
          │       │         │                    │
          │       │  ┌──────▼──────────────┐     │
          │       │  │ Dedup (shitpost_id  │     │
          │       │  │ seen_ids set +      │     │
          │       │  │ S3 existence check) │     │
          │       │  └──────┬──────────────┘     │
          │       │         │ new posts only     │
          │       │  ┌──────▼──────┐             │
          │       │  │ S3 Write    │             │
          │       │  └──────┬──────┘             │
          │       │         │                    │
          │       │  ┌──────▼──────┐             │
          │       │  │ Emit Event  │ (immediate) │
          │       │  └─────────────┘             │
          │       └──────────────────────────────┘
          │
          └──────────── repeat ─────────────────
```

### New File: `shitposts/always_on.py`

```python
"""
Always-On Harvester
Persistent polling loop that wraps TruthSocialS3Harvester for low-latency detection.
"""

import asyncio
import signal
from datetime import datetime, timezone
from typing import Optional, Set

from shit.config.shitpost_settings import settings
from shit.events.producer import emit_event
from shit.events.event_types import EventType
from shit.logging import get_service_logger
from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester

logger = get_service_logger("always_on_harvester")

# Defaults
DEFAULT_POLL_INTERVAL = 30  # seconds
MIN_POLL_INTERVAL = 10      # floor to avoid API abuse
MAX_POLL_INTERVAL = 120     # ceiling for backoff
BACKOFF_MULTIPLIER = 2.0
BACKOFF_RESET_AFTER = 5     # successful polls before resetting to base interval
SEEN_IDS_MAX_SIZE = 500     # rolling window of recently seen post IDs
HEALTH_STALE_SECONDS = 180  # consider unhealthy if no poll in 3 min


class AlwaysOnHarvester:
    """Persistent polling loop for Truth Social harvesting.

    Wraps TruthSocialS3Harvester and calls _fetch_batch in a loop,
    deduplicating via an in-memory seen_ids set plus S3 existence checks.
    Emits POSTS_HARVESTED events immediately on each poll that finds new posts.
    """

    def __init__(
        self,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_interval: float = MAX_POLL_INTERVAL,
    ):
        self.base_interval = max(poll_interval, MIN_POLL_INTERVAL)
        self.current_interval = self.base_interval
        self.max_interval = max_interval
        self._shutdown = False
        self._consecutive_successes = 0
        self._consecutive_errors = 0
        self._last_poll_at: Optional[datetime] = None
        self._polls_total = 0
        self._posts_found_total = 0

        # Rolling dedup set — prevents re-processing within a session
        self._seen_ids: Set[str] = set()

        # Underlying harvester (reused across polls)
        self._harvester: Optional[TruthSocialS3Harvester] = None

    async def initialize(self) -> None:
        """Initialize the underlying harvester (API + S3 connections)."""
        self._harvester = TruthSocialS3Harvester(mode="incremental")
        await self._harvester.initialize(dry_run=False)
        logger.info(
            f"Always-on harvester initialized. "
            f"Poll interval: {self.base_interval}s"
        )

    async def run(self) -> None:
        """Main polling loop. Runs until SIGTERM/SIGINT."""
        self._setup_signal_handlers()
        logger.info("Always-on harvester starting persistent loop")

        while not self._shutdown:
            try:
                new_count = await self._poll_once()
                self._update_backoff(success=True, found_posts=new_count > 0)
            except Exception:
                logger.error("Poll cycle failed", exc_info=True)
                self._update_backoff(success=False)

            if not self._shutdown:
                await asyncio.sleep(self.current_interval)

        await self._cleanup()
        logger.info("Always-on harvester shut down gracefully")

    async def _poll_once(self) -> int:
        """Execute a single poll cycle.

        Returns:
            Number of new posts found and stored.
        """
        self._polls_total += 1
        self._last_poll_at = datetime.now(timezone.utc)

        # Fetch latest batch (most recent 20 posts)
        posts, _ = await self._harvester._fetch_batch(cursor=None)

        if not posts:
            return 0

        # Identify truly new posts
        new_posts = []
        for post in posts:
            post_id = self._harvester._extract_item_id(post)
            if not post_id:
                continue
            if post_id in self._seen_ids:
                continue  # Already processed this session
            new_posts.append((post_id, post))

        if not new_posts:
            return 0

        # Store each new post to S3 and track it
        stored_keys = []
        for post_id, post in new_posts:
            try:
                s3_key = await self._harvester.s3_data_lake.store_raw_data(post)
                stored_keys.append(s3_key)
                self._seen_ids.add(post_id)
                logger.info(f"New post detected: {post_id} -> {s3_key}")
            except Exception as e:
                logger.error(f"Failed to store post {post_id}: {e}")

        # Trim seen_ids to prevent unbounded growth
        if len(self._seen_ids) > SEEN_IDS_MAX_SIZE:
            excess = len(self._seen_ids) - SEEN_IDS_MAX_SIZE
            # Remove oldest entries (set has no order, but for dedup this is fine)
            for _ in range(excess):
                self._seen_ids.pop()

        # Emit event immediately for each batch of new posts
        if stored_keys:
            self._posts_found_total += len(stored_keys)
            try:
                emit_event(
                    event_type=EventType.POSTS_HARVESTED,
                    payload={
                        "s3_keys": stored_keys,
                        "source": self._harvester.get_source_name(),
                        "count": len(stored_keys),
                        "mode": "always_on",
                    },
                    source_service="always_on_harvester",
                )
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")

        return len(stored_keys)

    def _update_backoff(self, success: bool, found_posts: bool = False) -> None:
        """Adjust polling interval based on success/failure."""
        if success:
            self._consecutive_errors = 0
            self._consecutive_successes += 1
            if self._consecutive_successes >= BACKOFF_RESET_AFTER:
                self.current_interval = self.base_interval
        else:
            self._consecutive_successes = 0
            self._consecutive_errors += 1
            self.current_interval = min(
                self.current_interval * BACKOFF_MULTIPLIER,
                self.max_interval,
            )
            logger.warning(
                f"Backing off to {self.current_interval}s "
                f"({self._consecutive_errors} consecutive errors)"
            )

    def get_health(self) -> dict:
        """Return health check data for /healthz endpoint."""
        now = datetime.now(timezone.utc)
        last_poll_age = (
            (now - self._last_poll_at).total_seconds()
            if self._last_poll_at
            else None
        )
        return {
            "status": "healthy" if (
                last_poll_age is not None
                and last_poll_age < HEALTH_STALE_SECONDS
            ) else "unhealthy",
            "last_poll_at": self._last_poll_at.isoformat() if self._last_poll_at else None,
            "last_poll_age_seconds": last_poll_age,
            "polls_total": self._polls_total,
            "posts_found_total": self._posts_found_total,
            "current_interval": self.current_interval,
            "consecutive_errors": self._consecutive_errors,
        }

    def _setup_signal_handlers(self) -> None:
        """Register SIGTERM/SIGINT for graceful shutdown."""
        def _handle(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._shutdown = True
        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)

    async def _cleanup(self) -> None:
        """Clean up harvester resources."""
        if self._harvester:
            await self._harvester.cleanup()
```

### New File: `shitposts/always_on_cli.py`

```python
"""CLI entry point for always-on harvester."""

import argparse
import asyncio

from shit.logging import setup_cli_logging


def main():
    setup_cli_logging(service_name="always_on_harvester")

    parser = argparse.ArgumentParser(
        description="Always-on Truth Social harvester (persistent polling)"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=30.0,
        help="Seconds between polls (default: 30, min: 10)",
    )
    parser.add_argument(
        "--max-interval",
        type=float,
        default=120.0,
        help="Maximum backoff interval in seconds (default: 120)",
    )
    args = parser.parse_args()

    async def _run():
        from shitposts.always_on import AlwaysOnHarvester
        harvester = AlwaysOnHarvester(
            poll_interval=args.poll_interval,
            max_interval=args.max_interval,
        )
        await harvester.initialize()
        await harvester.run()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

### Deduplication Strategy

Three layers of dedup prevent the same post from being stored/processed twice:

1. **In-memory `_seen_ids` set** (session-scoped): O(1) lookup for posts already seen in the current process lifetime. Rolling window of 500 IDs to bound memory.

2. **S3 existence check** (removed in always-on mode): The current incremental harvester checks `s3_data_lake.check_object_exists(key)` before writing. In always-on mode, the in-memory set makes this redundant for the steady state. On cold start (restart/deploy), the first poll may re-fetch up to 20 posts that are already in S3 -- the S3 `store_raw_data` call uses `PUT` which is idempotent (overwrites with identical content).

3. **Database-level uniqueness**: Downstream `shitpost_id` uniqueness constraints in `truth_social_shitposts` and `signals` tables prevent duplicate DB entries regardless of S3 duplicates.

### Cold Start Behavior

On process restart, `_seen_ids` is empty. The first `_fetch_batch()` returns the 20 most recent posts. Some or all of these may already be in S3. This is acceptable because:

- S3 PUT is idempotent -- re-uploading the same JSON is a no-op from a data perspective.
- The `POSTS_HARVESTED` event will be emitted, but the S3 processor's downstream dedup (DB uniqueness on `shitpost_id`) will skip already-stored posts.
- Cost is negligible (20 small JSON PUTs to S3 on each deploy).

To optimize cold starts, we could pre-seed `_seen_ids` by listing recent S3 keys, but this adds complexity for minimal benefit.

---

## Railway Configuration

### Current Setup (Cron)

- **Service**: `harvester`
- **Start command**: `python -m shitposts --mode incremental`
- **Schedule**: `*/5 * * * *` (every 5 minutes)
- **Type**: Cron job

### Proposed Setup (Always-On)

- **Service**: `harvester` (same service, reconfigured)
- **Start command**: `python -m shitposts.always_on_cli --poll-interval 30`
- **Schedule**: None (always-on)
- **Type**: Worker (persistent process)
- **Health check**: HTTP endpoint on port 8080 (see below)

### Cost Delta

Railway pricing for always-on vs cron:

| Mode | Compute Hours/Day | Estimated Cost |
|------|-------------------|---------------|
| Cron (5min, ~10s/run) | 0.048 hrs | ~$0.01/day |
| Always-on (idle process) | 24 hrs | ~$0.50/day |

The always-on service costs roughly $15/month more. This is the price of sub-30-second latency. The process is mostly sleeping and uses minimal memory (~50MB RSS).

### Health Check Endpoint

Add a minimal HTTP health check so Railway can monitor the service:

```python
# In always_on.py, add a tiny HTTP server for health checks
from aiohttp import web

async def _run_health_server(harvester: AlwaysOnHarvester, port: int = 8080):
    """Run a minimal HTTP health check server alongside the polling loop."""
    async def health_handler(request):
        data = harvester.get_health()
        status_code = 200 if data["status"] == "healthy" else 503
        return web.json_response(data, status=status_code)

    app = web.Application()
    app.router.add_get("/healthz", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
```

The health check returns 503 if no poll has completed in the last 180 seconds, which Railway will use to restart the service.

---

## Event Integration: Immediate Emit

### Current Behavior (Cron)

Events are emitted in a single batch at the end of the harvest run. The `main()` function in `truth_social_s3_harvester.py` collects all S3 keys into `collected_s3_keys`, then emits one `POSTS_HARVESTED` event with all keys.

### Proposed Behavior (Always-On)

Events are emitted immediately after each poll cycle that finds new posts. Each event contains only the S3 keys from that specific poll (typically 1-5 new posts, not 20).

This means downstream consumers (S3 processor, analyzer) can start processing immediately rather than waiting for the full cron cycle. Combined with the event workers' 2-second poll interval, new posts flow through the entire pipeline within seconds.

### Event Payload (unchanged schema)

```python
{
    "s3_keys": ["truth-social/raw/2026/04/09/114858915682735686.json"],
    "source": "truth_social",
    "count": 1,
    "mode": "always_on",  # New mode identifier for observability
}
```

---

## Error Handling

### Circuit Breaker Pattern

The backoff strategy serves as a simple circuit breaker:

```
Normal operation (30s interval)
        │
        ├── API error ──► Backoff: 60s
        │                    │
        │                    ├── Another error ──► 120s (max)
        │                    │
        │                    └── 5 successes ──► Reset to 30s
        │
        └── API success ──► Stay at 30s
```

| Condition | Behavior |
|-----------|----------|
| Single API error | Double interval (30s -> 60s) |
| Consecutive errors | Keep doubling up to max_interval (120s) |
| 5 consecutive successes after errors | Reset to base interval |
| API returns HTTP 402/403 | Log error, backoff applies. Manual intervention needed for billing issues. |
| Network timeout | Treated as error, backoff applies |
| S3 write failure | Post is skipped (logged), next poll retries naturally |

### API Rate Limits

ScrapeCreators API does not publish explicit rate limits, but based on production experience:

- **Current load**: 1 request per 5 minutes = 288 requests/day
- **Proposed load**: 1 request per 30 seconds = 2,880 requests/day (10x increase)

If the API starts returning 429 (Too Many Requests), the backoff will automatically reduce frequency. We should also respect `Retry-After` headers if present:

```python
async def _fetch_batch_with_rate_limit(self, cursor=None):
    """Wrapper that respects rate limit headers."""
    posts, next_cursor = await self._harvester._fetch_batch(cursor)
    # If the underlying method could expose response headers,
    # check for Retry-After and sleep accordingly.
    # For now, rely on the exponential backoff.
    return posts, next_cursor
```

### Graceful Shutdown

On SIGTERM (Railway deploy/restart), the handler sets `self._shutdown = True`. The current poll cycle completes, any in-flight S3 writes finish, and the process exits cleanly. No data loss because:

- Posts already written to S3 are durable.
- Events already emitted are in PostgreSQL.
- Posts not yet fetched will be picked up on the next process start.

---

## Migration Plan: Cron to Always-On

### Phase 1: Deploy Always-On Alongside Cron

1. Create a new Railway service `harvester-always-on` with the always-on configuration.
2. Both services run simultaneously. Dedup at the DB level ensures no duplicate posts.
3. Monitor for 24-48 hours to confirm the always-on harvester is detecting posts faster.
4. Compare S3 key counts, event emission times, and end-to-end latency.

### Phase 2: Disable Cron Harvester

1. Set the cron harvester service to sleep mode on Railway.
2. Monitor the always-on harvester for another 48 hours to confirm reliability.
3. Verify no gaps in post coverage by comparing Truth Social post IDs against S3 keys.

### Phase 3: Remove Cron Configuration

1. Delete the `harvester` cron service from Railway.
2. Rename `harvester-always-on` to `harvester`.
3. Archive the cron-specific code path (the `main()` function in `truth_social_s3_harvester.py` stays for manual CLI use).

### Rollback

If the always-on harvester has issues, re-enable the cron service on Railway. Both can coexist safely due to dedup.

---

## Downstream Impact: Should Workers Go Always-On?

### Current Worker Architecture

All event consumers (`s3-processor-worker`, `analyzer-worker`, `market-data-worker`, `notifications-worker`) run as Railway crons on `*/5` schedule with `--once` flag. They drain the event queue and exit.

### Impact of Faster Harvesting

With 30-second polling, events arrive more frequently but in smaller batches (1-5 posts vs 0-20 per cron). The `--once` workers will still drain correctly, but they now wake up to 1-5 pending events instead of 0-20, and the events sit in the queue for up to 5 minutes before being claimed.

### Recommendation: Keep Workers as Cron (For Now)

The bottleneck after this change shifts from harvesting latency (300s) to worker poll latency (300s). However:

1. **Cost**: Making all 4 workers always-on adds ~$60/month. The harvester alone adds ~$15/month.
2. **Priority**: The biggest win is harvesting latency. Worker latency is a separate optimization.
3. **Future**: If sub-minute end-to-end latency is needed, convert the notifications worker to always-on first (it's the user-facing one), then others as needed.

The notifications worker is the highest-priority candidate for always-on conversion because it directly affects user-perceived latency. The others (S3 processor, analyzer, market data) could remain as crons since their latency doesn't directly affect alert timing -- the analyzer already runs reactively in the event flow.

---

## Testing Strategy

### Unit Tests

**File**: `shit_tests/shitposts/test_always_on.py`

1. **`test_poll_once_no_new_posts`**: Mock `_fetch_batch` returning 20 posts all in `_seen_ids`. Assert 0 returned, no S3 writes, no events emitted.

2. **`test_poll_once_new_posts`**: Mock `_fetch_batch` with 3 new posts and 17 seen. Assert 3 S3 writes, 1 event with 3 keys.

3. **`test_dedup_across_polls`**: Call `_poll_once` twice with the same batch. Assert second call returns 0 new posts.

4. **`test_seen_ids_rolling_window`**: Add 600 IDs to `_seen_ids`, verify size is trimmed to `SEEN_IDS_MAX_SIZE`.

5. **`test_backoff_on_error`**: Simulate API errors, verify `current_interval` doubles up to `max_interval`.

6. **`test_backoff_reset_on_success`**: After errors, simulate 5 successes, verify interval resets to `base_interval`.

7. **`test_health_check_healthy`**: Set `_last_poll_at` to 10 seconds ago, verify health status is "healthy".

8. **`test_health_check_unhealthy`**: Set `_last_poll_at` to 200 seconds ago, verify health status is "unhealthy".

9. **`test_graceful_shutdown`**: Set `_shutdown = True` during poll, verify loop exits cleanly.

10. **`test_cold_start_idempotent`**: With empty `_seen_ids`, mock `_fetch_batch` returning posts that already exist in S3. Verify S3 PUT is called (idempotent) and event is emitted.

### Integration Tests

**File**: `shit_tests/integration/test_always_on_integration.py`

1. **`test_end_to_end_poll_to_event`**: Start `AlwaysOnHarvester` with mock S3, run one poll, verify event appears in events table.

2. **`test_restart_recovery`**: Simulate a restart by creating a new `AlwaysOnHarvester` instance, verify it handles duplicate S3 writes gracefully.

### Manual Testing

```bash
# Local test with dry run (no S3, no events)
# Requires SCRAPECREATORS_API_KEY in .env
python -m shitposts.always_on_cli --poll-interval 10
# Ctrl+C to stop, verify graceful shutdown

# Monitor health endpoint
curl http://localhost:8080/healthz
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `shitposts/always_on.py` | Create | `AlwaysOnHarvester` class with polling loop |
| `shitposts/always_on_cli.py` | Create | CLI entry point for always-on mode |
| `shit_tests/shitposts/test_always_on.py` | Create | Unit tests |
| `shit_tests/integration/test_always_on_integration.py` | Create | Integration tests |
| `shitposts/__main__.py` | No change | Existing CLI for manual/cron use stays |
| `shitposts/truth_social_s3_harvester.py` | No change | Reused via composition |
| `shitposts/base_harvester.py` | No change | Reused via composition |

---

## Open Questions

1. **ScrapeCreators rate limits**: What are the actual rate limits? 2,880 requests/day should be fine, but we should confirm with the API provider or watch for 429s in the first week.

2. **S3 costs**: At 2,880 PUT requests/day (mostly no-ops due to dedup), S3 costs are negligible (~$0.01/day). But should we add a check to skip the S3 write if the post is already in `_seen_ids`? (Currently yes -- we skip seen posts entirely before the S3 write.)

3. **Multi-instance safety**: If Railway scales the always-on service to 2+ instances, both would poll and potentially write the same posts. S3 PUT is idempotent and DB dedup protects against duplicates, but we'd double the API call volume. Should we add a distributed lock (e.g., PostgreSQL advisory lock)? Probably not needed at current scale.

4. **Adaptive polling**: Should the interval decrease when the market is open (higher post frequency) and increase overnight? Trump posts at all hours, so a fixed 30s interval is probably simplest.

5. **Health check port**: Railway supports health check URLs for web services. Does it support them for worker services? If not, we may need to configure this as a "web" type service that also serves health checks.

6. **Metric emission**: Should the always-on harvester emit metrics (polls/minute, posts/hour, error rate) to a monitoring service? Or is the `get_health()` endpoint sufficient for now?
