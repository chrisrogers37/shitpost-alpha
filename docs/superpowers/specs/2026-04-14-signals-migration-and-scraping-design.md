# Signals Migration & Direct Scraping Design

**Status**: Approved
**Created**: 2026-04-14
**Approach**: Big-bang cutover (single PR) for signals migration; design-only for scraping

---

## Scope

**Workstream 1 — Signals Migration (Implement Now):**
Complete the cutover from `truth_social_shitposts` to `signals` as the primary content table. Backfill historical data, migrate all live readers (analyzer, API, notifications, echoes), remove dual-write, and clean up legacy code.

**Workstream 2 — Direct Truth Social Scraping (Design Only):**
Document the approach for replacing ScrapeCreators API with direct Truth Social access to enable near-real-time post detection. No implementation this session.

---

## Workstream 1: Signals Migration

### Context

The `signals` table was built as a source-agnostic replacement for `truth_social_shitposts` during the system-evolution session (Feb 2026). S3 Processor dual-writes every post to both tables, but all downstream readers still use the legacy table. This wastes write I/O and blocks multi-source support.

### Current Architecture

```
S3 Data -> S3 Processor -> [signals table (WRITE ONLY)]
                         -> [truth_social_shitposts (READ/WRITE)]
                         -> Event: SIGNALS_STORED

All readers -> truth_social_shitposts -> predictions (via shitpost_id)
```

### Target Architecture

```
S3 Data -> S3 Processor -> [signals table (PRIMARY)]
                         -> Event: SIGNALS_STORED

All readers -> signals -> predictions (via signal_id)
truth_social_shitposts -> ARCHIVED (no new writes, table retained)
```

### Design Decisions

- **Big-bang cutover**: All changes ship in a single PR. No phased rollout — fix forward if anything breaks. No active users on the system right now.
- **No prediction replay**: Existing predictions keep their current analysis. The `signal_id` backfill is a data-only operation (`UPDATE predictions SET signal_id = shitpost_id WHERE signal_id IS NULL`). Ensemble consensus runs on new posts going forward.
- **Delete `shitty_ui/`**: Old Dash dashboard is dead code. Analytics queries there are tightly coupled to Dash and the legacy schema. If analytics features are needed later, rebuild as proper API services.
- **Keep `truth_social_shitposts` table**: Don't DROP the table — historical data stays for reference. Just stop writing to it.

---

### Section 1: Historical Backfill

**Goal**: Ensure `signals` table has all historical data and all predictions have `signal_id`.

**Implementation:**

1. CLI command `python -m shitvault migrate-to-signals`:
   - Read all `truth_social_shitposts` rows
   - Transform each via `SignalTransformer.transform_truth_social()`
   - Upsert into `signals` (skip if `signal_id` already exists from dual-write era)
   - Batch processing with progress logging

2. Backfill predictions FK:
   ```sql
   UPDATE predictions
   SET signal_id = shitpost_id
   WHERE signal_id IS NULL AND shitpost_id IS NOT NULL;
   ```

3. Verification:
   - Assert row count: `signals` >= `truth_social_shitposts`
   - Assert all predictions have `signal_id` set
   - Spot-check field mapping on a sample of rows

**No schema changes** — both tables and FKs already exist.

---

### Section 2: Analyzer Migration

**Goal**: Analyzer reads from `signals` and writes `signal_id` on predictions.

**Files changed:**
- `shitpost_ai/shitpost_analyzer.py`

**Changes:**
- Replace `ShitpostOperations` import with `SignalOperations`
- Swap `get_unprocessed_shitposts()` -> `get_unprocessed_signals()`
- `SignalOperations.get_unprocessed_signals()` already returns backward-compat aliases (`shitpost_id`, `timestamp`, `username`, `content`, etc.), so `_prepare_enhanced_content()` works without field name changes
- Call `prediction_operations.store_analysis()` with `use_signal=True` so new predictions write `signal_id` instead of `shitpost_id`
- `PREDICTION_CREATED` event payload: populate `signal_id` field, leave `shitpost_id` as None

**What stays the same:** LLM prompts, bypass logic, ensemble orchestration, price snapshot capture.

---

### Section 3: API, Notifications & Echo Service Migration

**Goal**: All live read queries join on `signals` instead of `truth_social_shitposts`.

#### Feed Queries (`api/queries/feed_queries.py`) — 2 SQL statements

Table/join changes:
- `FROM truth_social_shitposts tss` -> `FROM signals s`
- `ON tss.shitpost_id = p.shitpost_id` -> `ON s.signal_id = p.signal_id`

Column renames:
| Legacy | Signal |
|--------|--------|
| `tss.timestamp` | `s.published_at` |
| `tss.content` | `s.content_html` |
| `tss.username` | `s.author_username` |
| `tss.url` | `s.source_url` |
| `tss.reblogs_count` | `s.shares_count` |
| `tss.favourites_count` | `s.likes_count` |
| `tss.upvotes_count` | `(s.platform_data->>'upvotes_count')::int` |
| `tss.downvotes_count` | `(s.platform_data->>'downvotes_count')::int` |

#### Feed Service / Schemas (`api/services/feed_service.py`, `api/schemas/`)

Update field mappings to match new column names. The frontend consumes the API schema, not raw column names — keep the API response shape stable so no frontend changes are needed.

#### Notifications (`notifications/db.py`, `briefing.py`, `followups.py`)

Same join pattern change. Event consumers read `signal_id` from `PREDICTION_CREATED` payload with fallback to `shitpost_id` for in-flight events during deploy.

#### Echo Service (`shit/echoes/`)

Embedding storage/queries switch FK reference from `shitpost_id` to `signal_id`. Same values, just the column name changes.

---

### Section 4: Remove Dual-Write & Legacy Cleanup

**Goal**: Stop writing to legacy table, remove dead code.

#### S3 Processor (`shitvault/s3_processor.py`)
- Remove legacy write: delete `DatabaseUtils.transform_s3_data_to_shitpost()` call and `shitpost_ops.store_shitpost()`
- Remove `ShitpostOperations` import
- Update `_get_most_recent_post_id()` to query `Signal` table instead of `TruthSocialShitpost`

#### Delete `shitty_ui/`
Entire directory removed. Old Dash dashboard code with 11+ legacy queries.

#### Remove `ShitpostOperations`
Delete `shitvault/shitpost_operations.py` — class is deprecated, all consumers migrated.

#### Prediction Model Cleanup (`shitvault/shitpost_models.py`)
- Remove `shitpost_id` column from `Prediction` SQLAlchemy model (Python code only — the database column stays for now; a future ALTER TABLE DROP COLUMN can run after production is stable)
- Update CHECK constraint in model: `signal_id IS NOT NULL` (drop the OR clause). Corresponding database constraint update is a production SQL migration.
- Remove `shitpost` relationship
- Keep `TruthSocialShitpost` model — table stays for historical reference

#### Update CLAUDE.md
Reflect new architecture: `signals` as primary content table, `truth_social_shitposts` as archived.

---

## Workstream 2: Direct Truth Social Scraping (Design Only)

### Context

ScrapeCreators API costs ~$17-20/month at current 5-minute polling. The cost is trivial, but it caps detection latency at 5+ minutes (Railway cron minimum) and adds ScrapeCreators' own scraping latency on top.

For near-real-time detection (sub-30s), a direct approach eliminates per-call costs and latency overhead, enabling persistent polling or streaming.

### Exploration Findings

**Truth Social's Mastodon API is NOT publicly accessible:**
- All REST endpoints (`/api/v1/accounts/.../statuses`, `/api/v1/timelines/...`, account lookup) return Cloudflare 403 block pages
- RSS endpoints (`.rss`) return SPA HTML, not actual RSS
- ActivityPub endpoints return 401
- ScrapeCreators handles proxy rotation, Cloudflare bypass, and detection evasion — not a simple API proxy

**Alternative approaches investigated:**

| Option | Mechanism | Viability |
|--------|-----------|-----------|
| Direct Mastodon API | `GET /api/v1/accounts/{id}/statuses` | Blocked by Cloudflare (403) |
| truthbrush (Stanford) | Authenticated API client | Requires TS account; open Cloudflare issues |
| Mastodon Streaming API | WebSocket `/api/v1/streaming` with auth | Untested; could provide push-based real-time |
| Headless browser | Playwright + stealth plugins | High maintenance; Cloudflare cat-and-mouse |
| Alternative proxy | ScrapingBee, Bright Data, etc. | Similar or higher cost than ScrapeCreators |

### Recommended Future Approach

**Phase 1 — Validate access (investigation session):**
1. Create a Truth Social account
2. Test authenticated Mastodon API access from a Railway server IP (Cloudflare may treat differently than local)
3. Test truthbrush library with the account credentials
4. Test streaming API endpoint for push-based delivery

**Phase 2 — Build persistent poller (if auth works):**
1. Replace `_fetch_batch()` in `TruthSocialS3Harvester` with authenticated direct API call
2. Remove `SCRAPECREATORS_API_KEY` dependency
3. Switch Railway service from cron to persistent process
4. Poll every 10-30 seconds (or use streaming WebSocket if available)

**Phase 3 — Always-on harvester (if streaming works):**
1. WebSocket connection to `/api/v1/streaming/user` or `/api/v1/streaming/public`
2. Reconnection logic with exponential backoff
3. Heartbeat monitoring
4. Near-instant detection (<5s from post to S3)

### Architecture Impact

Minimal. The `SignalHarvester` base class abstracts the data source:
- Only `_fetch_batch()` and `_test_connection()` change
- S3 storage, event emission, incremental dedup — all unchanged
- The signals migration makes this even cleaner since everything downstream reads from `signals` regardless of harvest source

### Cost Comparison

| Approach | Latency | Monthly cost | Maintenance |
|----------|---------|-------------|-------------|
| ScrapeCreators 5min | ~5-7 min | ~$20 | None |
| ScrapeCreators 1min | ~1-2 min | ~$86 | None |
| Direct auth polling 30s | ~30s | $0 | Low (account mgmt) |
| Streaming WebSocket | ~instant | $0 | Medium (reconnection) |
| Headless browser | ~30s | $0 | High (Cloudflare updates) |

---

## Test Strategy

- Existing test suite (2600+ tests) validates each component
- Add migration verification tests: row counts, FK integrity, sample data comparison
- Update existing tests that reference `shitpost_id` to use `signal_id` where applicable
- Feed query tests updated with new column names
- Run full suite before and after migration

## Rollback Plan

Since this is a big-bang cutover: `git revert` the PR. Historical backfill data in `signals` is harmless (dual-write already puts data there). The only irreversible step is dropping `shitpost_id` from the Prediction model — but since the column data is identical to `signal_id`, no information is lost.
