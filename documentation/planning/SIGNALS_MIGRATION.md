# Signals Migration Plan

**Status**: Planning
**Created**: 2026-03-26
**Context**: Data model audit revealed `signals` table is 100% write-only. S3 Processor dual-writes every post to both `signals` and legacy `truth_social_shitposts`, but all 21+ downstream queries still read from the legacy table. This wastes write I/O and blocks the multi-source architecture.

---

## Vision

Transform Shitpost Alpha from a single-source Trump Truth Social monitor into a **multi-source, multi-provider, multi-input** financial signal analysis platform.

**Future sources**: Truth Social, Twitter/X, congressional filings, SEC EDGAR, executive orders, press briefings, Telegram channels, Reddit (r/wallstreetbets), and more.

The `signals` table was designed as the source-agnostic content model for this vision. Its `source` column and `platform_data` JSON field already support arbitrary platforms. The migration just needs to wire in the readers.

---

## Current State (as of 2026-03-26)

### What's Done
- `Signal` model defined in `shitvault/signal_models.py` with 26 universal columns
- `SignalOperations` CRUD in `shitvault/signal_operations.py` with backward-compat aliases
- `SignalTransformer` in `shit/db/signal_utils.py` converts S3 data → Signal format
- S3 Processor writes every post to `signals` table via `SignalOperations.store_signal()`
- `Prediction` model has dual-FK: `shitpost_id` (legacy) + `signal_id` (new)
- Event system emits `SIGNALS_STORED` events with signal IDs

### What's NOT Done
- **21 raw SQL queries** across 6 files still reference `truth_social_shitposts`
- **Analyzer** still imports/uses deprecated `ShitpostOperations`
- **No historical backfill**: signals table only has posts since dual-write was enabled (~Feb 2026)
- **No `migrate-to-signals` CLI** for backfilling historical data
- **Prediction.shitpost_id** is still the primary join key in all dashboard queries

### Current Architecture
```
S3 Data → S3 Processor → [signals table (WRITE ONLY)]
                        → [truth_social_shitposts (READ/WRITE)]
                        → Event: SIGNALS_STORED

All readers → truth_social_shitposts → predictions (via shitpost_id)
```

### Target Architecture
```
S3 Data → S3 Processor → [signals table (PRIMARY)]
                        → Event: SIGNALS_STORED

All readers → signals → predictions (via signal_id)
truth_social_shitposts → DEPRECATED / DROPPED
```

---

## Column Mapping: truth_social_shitposts → signals

Every column accessed by downstream queries has a Signal equivalent:

| Legacy Column | Signal Column | Notes |
|---|---|---|
| `shitpost_id` | `signal_id` | Unique content ID |
| `content` | `content_html` | HTML content |
| `text` | `text` | Plain text content |
| `timestamp` | `published_at` | Publication datetime |
| `username` | `author_username` | Author handle |
| `platform` | `source` | Platform identifier |
| `url` | `source_url` | Original URL |
| `replies_count` | `replies_count` | Same name |
| `reblogs_count` | `shares_count` | Normalized name |
| `favourites_count` | `likes_count` | Normalized name |
| `upvotes_count` | `platform_data->'upvotes_count'` | In JSON |
| `downvotes_count` | `platform_data->'downvotes_count'` | In JSON |
| `account_verified` | `author_verified` | Normalized name |
| `account_followers_count` | `author_followers` | Normalized name |
| `account_display_name` | `author_display_name` | Normalized name |
| `has_media` | `has_media` | Same name |
| `reblog` | `platform_data->'reblog'` | In JSON (repost indicator) |
| `mentions` | `platform_data->'mentions'` | In JSON |
| `tags` | `platform_data->'tags'` | In JSON |
| `raw_api_data` | `raw_api_data` | Same name |

**No query accesses a column that doesn't exist on Signal.** All 21 queries can be migrated.

---

## Query Migration Inventory

### Dashboard UI: `shitty_ui/data/signal_queries.py` — 11 references

| Function | Lines | Join Pattern | Migration |
|---|---|---|---|
| `load_recent_posts()` | ~42 | `FROM tss LEFT JOIN predictions p ON tss.shitpost_id = p.shitpost_id` | Change to `FROM signals s LEFT JOIN predictions p ON s.signal_id = p.signal_id` |
| `load_filtered_posts()` | ~92 | Same pattern | Same change + update asset filter to use `p.signal_id` |
| `get_unfiltered_posts()` | ~200 | `FROM tss` | Change to `FROM signals s` |
| `get_posts_for_asset()` | ~257 | `FROM tss JOIN predictions` | Same pattern change |
| Various feed/timeline queries | ~365-846 | Various JOINs on `shitpost_id` | Change join key to `signal_id` |

### Dashboard UI: `shitty_ui/data/asset_queries.py` — 3 references

| Lines | Pattern | Migration |
|---|---|---|
| ~208, ~301, ~486 | `INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id` | Change to `INNER JOIN signals s ON p.signal_id = s.signal_id` |

### Dashboard UI: `shitty_ui/data/performance_queries.py` — 2 references

| Lines | Pattern | Migration |
|---|---|---|
| ~78, ~91 | `FROM truth_social_shitposts tss LEFT JOIN predictions` | Change table and join key |

### Dashboard UI: `shitty_ui/data/insight_queries.py` — 2 references

| Lines | Pattern | Migration |
|---|---|---|
| ~70, ~288 | `INNER JOIN truth_social_shitposts tss` accessing `tss.timestamp` | Change to `signals s` using `s.published_at` |

### FastAPI: `api/queries/feed_queries.py` — 2 references

| Lines | Pattern | Migration |
|---|---|---|
| ~45, ~126 | `FROM truth_social_shitposts tss LEFT JOIN predictions` | Change table, join key, and column names |

### Notifications: `notifications/db.py` — 1 reference

| Line | Pattern | Migration |
|---|---|---|
| ~328 | `INNER JOIN truth_social_shitposts tss ON tss.shitpost_id = p.shitpost_id` | Change to signals join |

---

## Migration Strategy: Phased Cutover

### Phase 0: Historical Backfill (Pre-requisite)
**Goal**: Ensure `signals` table has all historical data, not just posts since dual-write started.

1. Write `migrate-to-signals` CLI command that:
   - Reads all `truth_social_shitposts` rows
   - Transforms each to Signal format using `SignalTransformer`
   - Upserts into `signals` table (skip if `signal_id` already exists)
2. Backfill `predictions.signal_id` for all rows that only have `shitpost_id`:
   ```sql
   UPDATE predictions p
   SET signal_id = p.shitpost_id
   WHERE p.signal_id IS NULL AND p.shitpost_id IS NOT NULL;
   ```
3. Verify row counts match between tables

### Phase 1: Migrate Analyzer to SignalOperations
**Goal**: Stop reading from legacy table in the pipeline write path.

1. Replace `ShitpostOperations` import with `SignalOperations` in `shitpost_ai/shitpost_analyzer.py`
2. Replace `self.shitpost_ops` with `self.signal_ops`
3. Call `get_unprocessed_signals()` instead of `get_unprocessed_shitposts()`
4. No field name changes needed — SignalOperations already returns backward-compat aliases

### Phase 2: Migrate All Read Queries
**Goal**: Point all 21 raw SQL queries at `signals` table.

For each query file, apply this systematic transformation:
```
OLD: FROM truth_social_shitposts tss
NEW: FROM signals s

OLD: ON tss.shitpost_id = p.shitpost_id
NEW: ON s.signal_id = p.signal_id

OLD: tss.timestamp
NEW: s.published_at

OLD: tss.username
NEW: s.author_username

OLD: tss.reblogs_count
NEW: s.shares_count

OLD: tss.favourites_count
NEW: s.likes_count

OLD: tss.content
NEW: s.content_html

OLD: tss.url
NEW: s.source_url
```

For columns in `platform_data` JSON:
```
OLD: tss.upvotes_count
NEW: (s.platform_data->>'upvotes_count')::int

OLD: tss.downvotes_count
NEW: (s.platform_data->>'downvotes_count')::int
```

### Phase 3: Remove Dual-Write
**Goal**: Stop writing to `truth_social_shitposts`.

1. Remove the legacy write from `shitvault/s3_processor.py:218-219`
2. Remove `ShitpostOperations` import from s3_processor
3. Update `_get_most_recent_post_id()` to query `Signal` table instead of `TruthSocialShitpost`
4. Deploy and verify pipeline still works end-to-end

### Phase 4: Remove Legacy FK and Cleanup
**Goal**: Clean up the dual-FK architecture.

1. Remove `Prediction.shitpost_id` column (after verifying all rows have `signal_id`)
2. Drop `truth_social_shitposts` table (or archive to S3 first)
3. Remove `TruthSocialShitpost` model from `shitvault/shitpost_models.py`
4. Remove `ShitpostOperations` class from `shitvault/shitpost_operations.py`
5. Remove backward-compat aliases from `SignalOperations.get_unprocessed_signals()`
6. Update CLAUDE.md to reflect new architecture
7. Remove the `ck_predictions_has_content_ref` CHECK constraint (or update to require signal_id only)

---

## Multi-Source Architecture (Future)

Once the migration is complete, adding new sources becomes straightforward:

### Adding a New Source (e.g., Twitter)

1. **Harvester**: Write `TwitterHarvester` that fetches tweets → S3 (same pattern as Truth Social)
2. **Transformer**: Add `twitter` case to `SignalTransformer.get_transformer()` that maps Twitter API fields → Signal columns
3. **Platform data**: Twitter-specific fields go in `platform_data` JSON:
   ```python
   platform_data = {
       "retweet_count": int,
       "bookmark_count": int,
       "impression_count": int,
       "quoted_tweet": dict,
       ...
   }
   ```
4. **Everything else is automatic**: S3 Processor already uses `source` field to select transformer, analyzer already processes signals generically, dashboard queries work on any source

### Schema Considerations for Multi-Source

The current `signals` schema handles multi-source well:
- `source` column identifies the platform
- `signal_id` is platform-specific (prefixed or namespaced as needed)
- `platform_data` JSON absorbs platform-specific fields
- Normalized engagement columns (`likes_count`, `shares_count`, `replies_count`) enable cross-platform comparison

**Potential additions for multi-source**:
- `source_category` (social_media, government, financial_filing) for grouping
- `credibility_score` (per-source weighting for analysis confidence)
- `language_detected` (for non-English sources)
- Indexes on `(source, published_at)` for per-platform queries

---

## Effort Estimate

| Phase | Scope | Files Changed | Estimated Effort |
|---|---|---|---|
| 0 | Historical backfill CLI | 1-2 new files | 2-3 hours |
| 1 | Analyzer migration | 1 file | 30 minutes |
| 2 | Query migration (21 queries) | 6 files | 3-4 hours |
| 3 | Remove dual-write | 1 file | 30 minutes |
| 4 | Legacy cleanup | 4-5 files | 1-2 hours |
| **Total** | | **~14 files** | **~8-10 hours** |

**Risk assessment**: LOW to MEDIUM. The column mapping is 100% covered. The main risk is query regressions from column name changes — mitigated by the existing test suite (2500+ tests).

---

## Rollback Plan

Each phase is independently reversible:
- **Phase 0**: Backfilled data can coexist; no reads change
- **Phase 1**: Revert analyzer import to ShitpostOperations
- **Phase 2**: Revert SQL queries to use `truth_social_shitposts` (git revert)
- **Phase 3**: Re-enable dual-write in S3 Processor
- **Phase 4**: NOT easily reversible — do not proceed until Phases 0-3 are stable

**Recommendation**: Deploy each phase separately with a monitoring period before proceeding.

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-02-11 | Created signals table + dual-write | System evolution session, Phase 02 |
| 2026-03-26 | Data model audit flagged signals as 100% write-only | All 21 readers still on legacy table |
| 2026-03-26 | Documented multi-source vision | User wants multi-source, multi-provider, multi-input |
