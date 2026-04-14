# Signals Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the cutover from `truth_social_shitposts` to `signals` as the primary content table — backfill historical data, migrate all live readers, remove dual-write, and clean up legacy code.

**Architecture:** Big-bang cutover in a single PR. The `signals` table already exists with dual-write active. We backfill historical data, switch all readers (analyzer, API, notifications, echoes) from `truth_social_shitposts` to `signals`, remove the dual-write, and delete legacy code. No prediction replay — existing analyses stay as-is.

**Tech Stack:** Python 3.13, SQLAlchemy, PostgreSQL (Neon), FastAPI, React/TypeScript, pytest

**Spec:** `docs/superpowers/specs/2026-04-14-signals-migration-and-scraping-design.md`

---

## File Structure

### Files to Create
- `shitvault/migrate_to_signals.py` — CLI for historical backfill (shitposts → signals + prediction FK)

### Files to Modify
- `shitpost_ai/shitpost_analyzer.py` — Switch from ShitpostOperations to SignalOperations
- `api/queries/feed_queries.py` — SQL joins: `truth_social_shitposts` → `signals`
- `api/services/feed_service.py` — Field name updates for signal columns
- `api/schemas/feed.py` — Rename `shitpost_id` → `signal_id` on Post schema
- `frontend/src/types/api.ts` — Match renamed field
- `frontend/src/pages/FeedPage.tsx` — Match renamed field
- `notifications/briefing.py` — Remove legacy shitposts join
- `notifications/followups.py` — Remove legacy shitposts join
- `notifications/event_consumer.py` — Read `signal_id` from event payload
- `notifications/alert_engine.py` — Read `signal_id` from prediction
- `shitvault/s3_processor.py` — Remove dual-write, update `_get_most_recent_post_id()`
- `shitvault/shitpost_models.py` — Remove `shitpost_id` FK from Prediction model
- `shit/echoes/echo_service.py` — Pass `signal_id` instead of `shitpost_id` to embed_and_store
- `CLAUDE.md` — Update architecture docs

### Files to Delete
- `shitvault/shitpost_operations.py` — Deprecated, all consumers migrated
- `shitty_ui/` — Entire directory (dead Dash dashboard)

### Test Files to Modify
- Tests referencing `ShitpostOperations` or `shitpost_id` on predictions — update to `signal_id`

---

## Task 1: Historical Backfill CLI

**Files:**
- Create: `shitvault/migrate_to_signals.py`
- Read: `shit/db/signal_utils.py` (SignalTransformer)
- Read: `shitvault/signal_operations.py` (store_signal)
- Read: `shitvault/shitpost_models.py` (TruthSocialShitpost model)

- [ ] **Step 1: Write the migration script**

```python
"""CLI to migrate truth_social_shitposts → signals and backfill predictions.signal_id."""

import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select, text, func

from shit.config.shitpost_settings import settings
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shit.db.signal_utils import SignalTransformer
from shit.logging import setup_cli_logging, get_service_logger
from shitvault.shitpost_models import TruthSocialShitpost
from shitvault.signal_operations import SignalOperations

logger = get_service_logger("migrate_to_signals")

BATCH_SIZE = 500


async def migrate_shitposts_to_signals() -> dict:
    """Copy all truth_social_shitposts rows into signals table.

    Skips rows where signal_id already exists (from dual-write era).
    Returns stats dict with counts.
    """
    db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
    db_client = DatabaseClient(db_config)
    await db_client.initialize()
    session = db_client.get_session()
    db_ops = DatabaseOperations(session)
    signal_ops = SignalOperations(db_ops)

    stats = {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    try:
        # Count total shitposts
        result = await session.execute(select(func.count()).select_from(TruthSocialShitpost))
        total = result.scalar()
        stats["total"] = total
        logger.info(f"Found {total} shitposts to migrate")

        # Process in batches
        offset = 0
        while offset < total:
            result = await session.execute(
                select(TruthSocialShitpost)
                .order_by(TruthSocialShitpost.timestamp)
                .offset(offset)
                .limit(BATCH_SIZE)
            )
            rows = result.scalars().all()
            if not rows:
                break

            for row in rows:
                try:
                    # Build S3-like dict that SignalTransformer expects
                    s3_data = _shitpost_row_to_s3_data(row)
                    signal_data = SignalTransformer.transform_truth_social(s3_data)
                    stored = await signal_ops.store_signal(signal_data)
                    if stored:
                        stats["migrated"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(f"Error migrating shitpost {row.shitpost_id}: {e}")

            offset += BATCH_SIZE
            logger.info(
                f"Progress: {offset}/{total} "
                f"(migrated={stats['migrated']}, skipped={stats['skipped']}, errors={stats['errors']})"
            )

        return stats

    finally:
        await db_client.close()


def _shitpost_row_to_s3_data(row: TruthSocialShitpost) -> dict:
    """Convert a TruthSocialShitpost SQLAlchemy row to the S3-data dict format
    that SignalTransformer.transform_truth_social() expects.

    The transformer expects a dict with a 'raw_api_data' key containing
    the original API response fields.
    """
    # If the row has raw_api_data stored, use it directly
    if row.raw_api_data:
        return {"raw_api_data": row.raw_api_data}

    # Otherwise, reconstruct a minimal raw_api_data dict from row columns
    raw = {
        "id": row.shitpost_id,
        "content": row.content,
        "created_at": row.timestamp.isoformat() if row.timestamp else None,
        "account": {
            "id": getattr(row, "account_id", None),
            "username": row.username,
            "display_name": getattr(row, "account_display_name", None),
            "verified": getattr(row, "account_verified", False),
            "followers_count": getattr(row, "account_followers_count", 0),
        },
        "replies_count": row.replies_count or 0,
        "reblogs_count": row.reblogs_count or 0,
        "favourites_count": row.favourites_count or 0,
        "upvotes_count": getattr(row, "upvotes_count", 0) or 0,
        "downvotes_count": getattr(row, "downvotes_count", 0) or 0,
        "media_attachments": getattr(row, "media_attachments", []) or [],
        "mentions": getattr(row, "mentions", []) or [],
        "tags": getattr(row, "tags", []) or [],
        "reblog": getattr(row, "reblog", None),
        "url": getattr(row, "url", None),
        "in_reply_to_id": getattr(row, "in_reply_to_id", None),
        "card": getattr(row, "card", None),
    }
    return {"raw_api_data": raw}


async def backfill_prediction_signal_ids() -> int:
    """Set predictions.signal_id = shitpost_id where signal_id is NULL.

    Returns count of updated rows.
    """
    db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
    db_client = DatabaseClient(db_config)
    await db_client.initialize()
    session = db_client.get_session()

    try:
        result = await session.execute(
            text("""
                UPDATE predictions
                SET signal_id = shitpost_id
                WHERE signal_id IS NULL AND shitpost_id IS NOT NULL
            """)
        )
        await session.commit()
        count = result.rowcount
        logger.info(f"Backfilled signal_id on {count} predictions")
        return count
    finally:
        await db_client.close()


async def verify_migration() -> dict:
    """Verify the migration succeeded.

    Returns verification results dict.
    """
    db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
    db_client = DatabaseClient(db_config)
    await db_client.initialize()
    session = db_client.get_session()

    try:
        checks = {}

        # Count shitposts
        result = await session.execute(text("SELECT COUNT(*) FROM truth_social_shitposts"))
        checks["shitposts_count"] = result.scalar()

        # Count signals
        result = await session.execute(text("SELECT COUNT(*) FROM signals"))
        checks["signals_count"] = result.scalar()

        # Count predictions missing signal_id
        result = await session.execute(
            text("SELECT COUNT(*) FROM predictions WHERE signal_id IS NULL AND shitpost_id IS NOT NULL")
        )
        checks["predictions_missing_signal_id"] = result.scalar()

        # Count predictions with signal_id
        result = await session.execute(
            text("SELECT COUNT(*) FROM predictions WHERE signal_id IS NOT NULL")
        )
        checks["predictions_with_signal_id"] = result.scalar()

        checks["signals_covers_shitposts"] = checks["signals_count"] >= checks["shitposts_count"]
        checks["all_predictions_have_signal_id"] = checks["predictions_missing_signal_id"] == 0

        return checks
    finally:
        await db_client.close()


async def main():
    setup_cli_logging(verbose=True)

    print("=" * 60)
    print("SIGNALS MIGRATION")
    print("=" * 60)

    # Step 1: Migrate shitposts to signals
    print("\n--- Step 1: Migrating shitposts → signals ---")
    stats = await migrate_shitposts_to_signals()
    print(f"Migration: {stats}")

    # Step 2: Backfill prediction signal_ids
    print("\n--- Step 2: Backfilling predictions.signal_id ---")
    count = await backfill_prediction_signal_ids()
    print(f"Updated {count} predictions")

    # Step 3: Verify
    print("\n--- Step 3: Verification ---")
    checks = await verify_migration()
    for k, v in checks.items():
        status = "PASS" if v not in (False, None) else "FAIL"
        print(f"  {k}: {v} [{status}]")

    if not checks["signals_covers_shitposts"]:
        print("\nWARNING: signals count is less than shitposts count!")
        sys.exit(1)
    if not checks["all_predictions_have_signal_id"]:
        print("\nWARNING: Some predictions still missing signal_id!")
        sys.exit(1)

    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run against production database**

Run: `source venv/bin/activate && python -m shitvault.migrate_to_signals`

Expected: Migration stats showing ~32,700 shitposts migrated or skipped, all verification checks PASS.

- [ ] **Step 3: Commit**

```bash
git add shitvault/migrate_to_signals.py
git commit -m "feat: add migrate-to-signals CLI for historical backfill"
```

---

## Task 2: Analyzer Migration (ShitpostOperations → SignalOperations)

**Files:**
- Modify: `shitpost_ai/shitpost_analyzer.py`

- [ ] **Step 1: Update imports (line 14)**

Replace:
```python
from shitvault.shitpost_operations import ShitpostOperations
```
With:
```python
from shitvault.signal_operations import SignalOperations
```

- [ ] **Step 2: Update __init__ attribute (line 62)**

Replace:
```python
        self.shitpost_ops = None  # Will be initialized in initialize()
```
With:
```python
        self.signal_ops = None  # Will be initialized in initialize()
```

- [ ] **Step 3: Update initialize() (line 103)**

Replace:
```python
        self.shitpost_ops = ShitpostOperations(self.db_ops)
```
With:
```python
        self.signal_ops = SignalOperations(self.db_ops)
```

- [ ] **Step 4: Update _analyze_backfill (line 180-182)**

Replace:
```python
                shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                    launch_date=self.launch_date, limit=self.batch_size
                )
```
With:
```python
                shitposts = await self.signal_ops.get_unprocessed_signals(
                    launch_date=self.launch_date, limit=self.batch_size
                )
```

- [ ] **Step 5: Update _analyze_date_range (line 249-251)**

Replace:
```python
                shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                    launch_date=self.launch_date, limit=self.batch_size
                )
```
With:
```python
                shitposts = await self.signal_ops.get_unprocessed_signals(
                    launch_date=self.launch_date, limit=self.batch_size
                )
```

- [ ] **Step 6: Update _analyze_incremental (line 338-340)**

Replace:
```python
            shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                launch_date=self.launch_date, limit=self.batch_size
            )
```
With:
```python
            shitposts = await self.signal_ops.get_unprocessed_signals(
                launch_date=self.launch_date, limit=self.batch_size
            )
```

- [ ] **Step 7: Update prediction_ops calls to use signal FK**

In `_analyze_shitpost`, update `check_prediction_exists` (line 394):
```python
                if await self.prediction_ops.check_prediction_exists(shitpost_id, use_signal=True):
```

Update `handle_no_text_prediction` (line 477-479):
```python
                    await self.prediction_ops.handle_no_text_prediction(
                        shitpost_id, shitpost, bypass_reason, use_signal=True
                    )
```

Update `store_analysis` (line 564-566):
```python
                analysis_id = await self.prediction_ops.store_analysis(
                    shitpost_id, enhanced_analysis, shitpost, use_signal=True
                )
```

Note: The variable is still called `shitpost_id` because `get_unprocessed_signals()` returns a backward-compat alias `shitpost_id` → `signal_id`. The `use_signal=True` flag tells prediction_ops to write it as `Prediction.signal_id`.

- [ ] **Step 8: Update PREDICTION_CREATED event payload (lines 601-604)**

Replace:
```python
                        event_payload = {
                            "prediction_id": int(analysis_id),
                            "shitpost_id": shitpost_id,
                            "signal_id": None,
```
With:
```python
                        event_payload = {
                            "prediction_id": int(analysis_id),
                            "shitpost_id": None,
                            "signal_id": shitpost_id,
```

- [ ] **Step 9: Update _embed_prediction call (lines 628-633)**

Replace:
```python
                            await asyncio.to_thread(
                                self._embed_prediction,
                                int(analysis_id),
                                post_text,
                                shitpost_id,
                            )
```
With:
```python
                            await asyncio.to_thread(
                                self._embed_prediction,
                                int(analysis_id),
                                post_text,
                                signal_id=shitpost_id,
                            )
```

- [ ] **Step 10: Update _embed_prediction method signature (line 877-888)**

Replace:
```python
    def _embed_prediction(
        prediction_id: int, text: str, shitpost_id: str | None = None
    ) -> None:
        """Generate and store embedding for a prediction (sync, for asyncio.to_thread)."""
        from shit.echoes.echo_service import EchoService

        service = EchoService()
        service.embed_and_store(
            prediction_id=prediction_id,
            text=text,
            shitpost_id=shitpost_id,
        )
```
With:
```python
    def _embed_prediction(
        prediction_id: int, text: str, signal_id: str | None = None
    ) -> None:
        """Generate and store embedding for a prediction (sync, for asyncio.to_thread)."""
        from shit.echoes.echo_service import EchoService

        service = EchoService()
        service.embed_and_store(
            prediction_id=prediction_id,
            text=text,
            signal_id=signal_id,
        )
```

- [ ] **Step 11: Run tests**

Run: `source venv/bin/activate && pytest shit_tests/shitpost_ai/ -v`

- [ ] **Step 12: Commit**

```bash
git add shitpost_ai/shitpost_analyzer.py
git commit -m "refactor: analyzer reads from signals table instead of shitposts"
```

---

## Task 3: API Feed Queries Migration

**Files:**
- Modify: `api/queries/feed_queries.py`
- Modify: `api/services/feed_service.py`
- Modify: `api/schemas/feed.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/pages/FeedPage.tsx`

- [ ] **Step 1: Update feed query SQL (lines 26-70)**

Replace the full query in `get_analyzed_post_at_offset()`:
```python
    query = """
        SELECT
            s.signal_id,
            s.text,
            s.content_html,
            s.published_at AS timestamp,
            s.author_username AS username,
            s.source_url AS url,
            s.replies_count,
            s.shares_count AS reblogs_count,
            s.likes_count AS favourites_count,
            (s.platform_data->>'upvotes_count')::int AS upvotes_count,
            (s.platform_data->>'downvotes_count')::int AS downvotes_count,
            s.author_verified AS account_verified,
            s.author_followers AS account_followers_count,
            s.platform_data->'card' AS card,
            s.platform_data->'media_attachments' AS media_attachments,
            s.platform_data->>'in_reply_to_id' AS in_reply_to_id,
            s.platform_data->'in_reply_to' AS in_reply_to,
            s.platform_data->'reblog' AS reblog,
            p.id AS prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.calibrated_confidence,
            p.thesis,
            p.analysis_status,
            p.engagement_score,
            p.viral_score,
            p.sentiment_score,
            p.urgency_score,
            p.ensemble_results,
            p.ensemble_metadata,
            COUNT(*) OVER() AS total_count
        FROM signals s
        INNER JOIN predictions p ON s.signal_id = p.signal_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::text <> '[]'
            AND p.assets::text <> 'null'
        ORDER BY s.published_at DESC
        OFFSET :offset
        LIMIT 1
    """
```

Note: Column aliases (`AS reblogs_count`, `AS favourites_count`, `AS username`, etc.) preserve the existing dict key names so `feed_service.py` field access mostly stays the same.

- [ ] **Step 2: Update JSON parsing keys (line 76-91)**

Replace `row = dict(zip(columns, rows[0]))` dict key `shitpost_id` usage. The query now returns `signal_id`. Update the `json_keys` tuple — `card`, `media_attachments`, `in_reply_to`, and `reblog` are now extracted from `platform_data` JSON and may already be parsed. Update to handle both:

```python
    row = dict(zip(columns, rows[0]))
    total = row.pop("total_count", 0)

    # Parse JSON fields — platform_data extractions may already be dicts
    json_keys = (
        "assets",
        "market_impact",
        "card",
        "media_attachments",
        "in_reply_to",
        "reblog",
    )
    for key in json_keys:
        val = row.get(key)
        if isinstance(val, str):
            row[key] = json.loads(val)
```

- [ ] **Step 3: Update Post schema (api/schemas/feed.py line 29)**

Replace:
```python
class Post(BaseModel):
    shitpost_id: str
```
With:
```python
class Post(BaseModel):
    signal_id: str
```

- [ ] **Step 4: Update feed_service.py build_post (line 84-86)**

Replace:
```python
        ts = row["timestamp"]
        return Post(
            shitpost_id=row["shitpost_id"],
```
With:
```python
        ts = row["timestamp"]
        return Post(
            signal_id=row["signal_id"],
```

- [ ] **Step 5: Update frontend TypeScript type (frontend/src/types/api.ts line 25)**

Replace:
```typescript
  shitpost_id: string;
```
With:
```typescript
  signal_id: string;
```

- [ ] **Step 6: Update frontend FeedPage.tsx (line 151)**

Replace:
```tsx
            key={data.post.shitpost_id}
```
With:
```tsx
            key={data.post.signal_id}
```

- [ ] **Step 7: Rebuild frontend**

Run: `cd /Users/chris/Projects/shitpost-alpha/frontend && npm run build`

- [ ] **Step 8: Run API tests**

Run: `source venv/bin/activate && pytest shit_tests/api/ -v`

- [ ] **Step 9: Commit**

```bash
git add api/queries/feed_queries.py api/services/feed_service.py api/schemas/feed.py frontend/
git commit -m "refactor: feed queries join on signals table instead of shitposts"
```

---

## Task 4: Notifications Migration

**Files:**
- Modify: `notifications/briefing.py`
- Modify: `notifications/followups.py`
- Modify: `notifications/event_consumer.py`
- Modify: `notifications/alert_engine.py`

- [ ] **Step 1: Update briefing.py query (lines 55-58)**

Replace:
```python
            COALESCE(s.text, ts.text) as post_text
        FROM predictions p
        LEFT JOIN signals s ON s.signal_id = p.signal_id
        LEFT JOIN truth_social_shitposts ts ON ts.shitpost_id = p.shitpost_id
```
With:
```python
            s.text as post_text
        FROM predictions p
        LEFT JOIN signals s ON s.signal_id = p.signal_id
```

Also remove `p.shitpost_id,` from the SELECT list (line 47).

- [ ] **Step 2: Update followups.py query (lines 108-112)**

Replace:
```python
            COALESCE(s.text, ts.text) as post_text
        FROM alert_followups af
        JOIN predictions p ON p.id = af.prediction_id
        LEFT JOIN signals s ON s.signal_id = p.signal_id
        LEFT JOIN truth_social_shitposts ts ON ts.shitpost_id = p.shitpost_id
```
With:
```python
            s.text as post_text
        FROM alert_followups af
        JOIN predictions p ON p.id = af.prediction_id
        LEFT JOIN signals s ON s.signal_id = p.signal_id
```

- [ ] **Step 3: Update notifications/event_consumer.py (line 59)**

Replace:
```python
            "shitpost_id": payload.get("shitpost_id"),
```
With:
```python
            "signal_id": payload.get("signal_id"),
```

- [ ] **Step 4: Update notifications/alert_engine.py (line 69)**

Replace:
```python
            "shitpost_id": pred.get("shitpost_id"),
```
With:
```python
            "signal_id": pred.get("signal_id"),
```

- [ ] **Step 5: Update notifications/db.py query (line 373)**

Replace:
```python
            p.shitpost_id,
```
With:
```python
            p.signal_id,
```

- [ ] **Step 6: Run notifications tests**

Run: `source venv/bin/activate && pytest shit_tests/notifications/ -v`

- [ ] **Step 7: Commit**

```bash
git add notifications/
git commit -m "refactor: notifications queries use signals table, remove shitposts joins"
```

---

## Task 5: S3 Processor — Remove Dual-Write

**Files:**
- Modify: `shitvault/s3_processor.py`

- [ ] **Step 1: Remove ShitpostOperations import (line 14)**

Replace:
```python
from shitvault.shitpost_operations import ShitpostOperations
```
Remove this line entirely.

Also remove the `TruthSocialShitpost` import (line 16):
```python
from shitvault.shitpost_models import TruthSocialShitpost
```

- [ ] **Step 2: Remove shitpost_ops from __init__ (line 34)**

Replace:
```python
        self.shitpost_ops = ShitpostOperations(db_ops)  # Keep for backward compat
```
Remove this line entirely.

- [ ] **Step 3: Remove dual-write from _process_single_s3_data (lines 216-221)**

Remove these lines:
```python
                # Dual-write to legacy truth_social_shitposts table.
                # This stays until api/queries/feed_queries.py migrates reads
                # to the signals table. Tracked in:
                # documentation/planning/SIGNALS_MIGRATION.md
                legacy_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
                await self.shitpost_ops.store_shitpost(legacy_data)
```

Also remove the `DatabaseUtils` import (line 12) — only usage was the dual-write:
```python
from shit.db.database_utils import DatabaseUtils
```

- [ ] **Step 4: Update _get_most_recent_post_id (lines 152-174)**

Replace:
```python
    async def _get_most_recent_post_id(self) -> Optional[str]:
        """Get the most recent processed post ID from the database.
        
        Returns:
            The most recent post ID, or None if no posts exist
        """
        try:
            # Query for the most recent post by timestamp
            from sqlalchemy import select, desc
            stmt = select(TruthSocialShitpost.shitpost_id).order_by(desc(TruthSocialShitpost.timestamp)).limit(1)
            result = await self.db_ops.session.execute(stmt)
            most_recent_id = result.scalar()
            
            if most_recent_id:
                logger.debug(f"Found most recent post ID in database: {most_recent_id}")
                return most_recent_id
            else:
                logger.debug("No posts found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting most recent post ID: {e}")
            return None
```
With:
```python
    async def _get_most_recent_post_id(self) -> Optional[str]:
        """Get the most recent processed signal ID from the database.
        
        Returns:
            The most recent signal ID, or None if no signals exist.
        """
        try:
            from sqlalchemy import select, desc
            from shitvault.signal_models import Signal

            stmt = select(Signal.signal_id).order_by(desc(Signal.published_at)).limit(1)
            result = await self.db_ops.session.execute(stmt)
            most_recent_id = result.scalar()
            
            if most_recent_id:
                logger.debug(f"Found most recent signal ID in database: {most_recent_id}")
                return most_recent_id
            else:
                logger.debug("No signals found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting most recent signal ID: {e}")
            return None
```

- [ ] **Step 5: Run S3 processor tests**

Run: `source venv/bin/activate && pytest shit_tests/shitvault/ -v`

- [ ] **Step 6: Commit**

```bash
git add shitvault/s3_processor.py
git commit -m "refactor: remove dual-write from S3 processor, query signals for most recent"
```

---

## Task 6: Prediction Model Cleanup

**Files:**
- Modify: `shitvault/shitpost_models.py`

- [ ] **Step 1: Remove shitpost_id FK from Prediction model (lines 126-128)**

Remove:
```python
    # Legacy FK -- nullable now, will be removed after full migration
    shitpost_id = Column(
        String(255), ForeignKey("truth_social_shitposts.shitpost_id"), nullable=True
    )
```

- [ ] **Step 2: Make signal_id required (line 130)**

Replace:
```python
    # New FK -- points to the source-agnostic signals table
    signal_id = Column(String(255), ForeignKey("signals.signal_id"), nullable=True)
```
With:
```python
    # FK to source-agnostic signals table
    signal_id = Column(String(255), ForeignKey("signals.signal_id"), nullable=False)
```

- [ ] **Step 3: Update CHECK constraint (lines 111-122)**

Replace the table_args CHECK constraint:
```python
    __table_args__ = (
        CheckConstraint(
            "shitpost_id IS NOT NULL OR signal_id IS NOT NULL",
            name="ck_predictions_has_content_ref",
        ),
    )
```
With:
```python
    __table_args__ = ()
```

The nullable=False on signal_id enforces the constraint at the ORM level. The database-level CHECK constraint will be updated via a production SQL migration separately.

- [ ] **Step 4: Remove shitpost relationship (line 186)**

Remove:
```python
    shitpost = relationship("TruthSocialShitpost", back_populates="predictions")
```

- [ ] **Step 5: Update signal relationship (lines 187-189)**

Replace:
```python
    signal = relationship(
        "Signal", back_populates="predictions", foreign_keys=[signal_id]
    )
```
With:
```python
    signal = relationship("Signal", back_populates="predictions")
```

- [ ] **Step 6: Update content_id property**

Replace:
```python
    @property
    def content_id(self) -> str:
        """Return the signal or shitpost ID, whichever is set."""
        return self.signal_id or self.shitpost_id
```
With:
```python
    @property
    def content_id(self) -> str:
        """Return the signal ID."""
        return self.signal_id
```

- [ ] **Step 7: Remove shitpost_id index**

Find and remove the index on `shitpost_id` from the model if defined (line ~217):
```python
Index("idx_predictions_shitpost_id", "shitpost_id"),
```

- [ ] **Step 8: Run all model tests**

Run: `source venv/bin/activate && pytest shit_tests/shitvault/ -v`

- [ ] **Step 9: Commit**

```bash
git add shitvault/shitpost_models.py
git commit -m "refactor: remove shitpost_id FK from Prediction model, signal_id is now required"
```

---

## Task 7: Delete Legacy Code

**Files:**
- Delete: `shitvault/shitpost_operations.py`
- Delete: `shitty_ui/` (entire directory)

- [ ] **Step 1: Delete ShitpostOperations**

```bash
rm shitvault/shitpost_operations.py
```

- [ ] **Step 2: Delete shitty_ui directory**

```bash
rm -rf shitty_ui/
```

- [ ] **Step 3: Remove any remaining imports of ShitpostOperations**

Search and fix:
```bash
source venv/bin/activate && grep -rn "ShitpostOperations" --include="*.py" .
```

Any remaining references (likely in tests) should be updated or removed.

- [ ] **Step 4: Run full test suite**

Run: `source venv/bin/activate && pytest -v`

Fix any test failures caused by:
- Tests importing `ShitpostOperations`
- Tests referencing `shitpost_id` on Prediction model
- Tests using `shitty_ui` fixtures

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: delete ShitpostOperations and shitty_ui legacy code"
```

---

## Task 8: Update Tests

**Files:**
- Modify: Various test files in `shit_tests/`

- [ ] **Step 1: Find all test files referencing removed code**

```bash
source venv/bin/activate && grep -rn "shitpost_ops\|ShitpostOperations\|shitpost_id.*Prediction\|from shitvault.shitpost_operations" shit_tests/ --include="*.py"
```

- [ ] **Step 2: Update analyzer tests**

In `shit_tests/shitpost_ai/` — update mocks to use `signal_ops` instead of `shitpost_ops`, `get_unprocessed_signals` instead of `get_unprocessed_shitposts`.

- [ ] **Step 3: Update prediction operation tests**

In `shit_tests/shitvault/` — update tests that create Prediction objects to use `signal_id` instead of `shitpost_id`.

- [ ] **Step 4: Update S3 processor tests**

In `shit_tests/shitvault/` — remove tests for dual-write behavior, update mocks to not include `ShitpostOperations`.

- [ ] **Step 5: Update API/feed tests**

In `shit_tests/api/` — update expected query results to use `signal_id` field name.

- [ ] **Step 6: Run full suite and iterate**

Run: `source venv/bin/activate && pytest -v`

Fix any remaining failures. Iterate until all tests pass.

- [ ] **Step 7: Commit**

```bash
git add shit_tests/
git commit -m "test: update test suite for signals migration"
```

---

## Task 9: Update CLAUDE.md and Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `documentation/planning/SIGNALS_MIGRATION.md`

- [ ] **Step 1: Update CLAUDE.md architecture section**

Update the database tables section to:
- Mark `truth_social_shitposts` as archived (no new writes)
- Remove `shitpost_id` from the Prediction table description
- Mark `signal_id` as the primary content FK
- Update the architecture diagram

- [ ] **Step 2: Update SIGNALS_MIGRATION.md status**

Change status from "Planning" to "Complete". Add completion date and summary.

- [ ] **Step 3: Run linting**

Run: `source venv/bin/activate && ruff check . && ruff format .`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md documentation/
git commit -m "docs: update architecture docs for signals migration completion"
```

---

## Task 10: Final Verification and PR

- [ ] **Step 1: Run full test suite**

Run: `source venv/bin/activate && pytest -v`

Expected: All tests pass.

- [ ] **Step 2: Run linting**

Run: `source venv/bin/activate && ruff check . && ruff format .`

- [ ] **Step 3: Update CHANGELOG.md**

Add entry under `## [Unreleased]`:

```markdown
### Changed
- **Signals Migration Complete** - All readers now use `signals` table instead of legacy `truth_social_shitposts`
  - Analyzer reads from `SignalOperations.get_unprocessed_signals()`
  - Predictions now write `signal_id` FK (was `shitpost_id`)
  - Feed API queries join on `signals` table
  - Notifications queries use `signals` for post text
  - S3 Processor dual-write removed — signals-only path

### Removed
- **ShitpostOperations** — deprecated class deleted, replaced by `SignalOperations`
- **shitty_ui/** — dead Dash dashboard code removed
- **Prediction.shitpost_id** — legacy FK removed from model (database column retained)
```

- [ ] **Step 4: Create PR**

```bash
git push -u origin main
```

Or if working on a branch:
```bash
gh pr create --title "Complete signals migration — cut over from truth_social_shitposts" --body "..."
```
