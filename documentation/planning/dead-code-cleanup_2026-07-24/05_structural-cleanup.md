---
title: "Phase 5 — Structural cleanup + small correctness"
session: dead-code-cleanup_2026-07-24
status: READY
issues: [191, 231]
code_area: shitvault, shit/db, shit/content, api
risk: low-medium
---

# Phase 5 — Structural cleanup + small correctness

## Summary
Consolidate the duplicated S3-key processing + `SIGNALS_STORED` emission that lives in
both `S3ProcessorWorker` and `S3Processor` behind a single public `process_keys()` method
(#191, pure refactor), and land the API/web cleanup of #231 L18 (remove dead `get_db()`,
remove the frontend-unused `/latest` feed endpoint, bound the unbounded `_price_cache`,
drop the empty `lifespan`). **This phase carries two genuine behavior changes:** echo-embed
idempotency (#231 L16 — `INSERT … ON CONFLICT DO NOTHING` closes a cross-session TOCTOU race)
and a bounded price cache (evicts instead of growing forever). Both are additive/safe and
require no migration. Note the `/latest` removal is product-safe (the React app calls only
`/at`) but forces a test-suite repoint — see Notes/Risks.

## Findings

### #191 — Consolidate S3-key processing + SIGNALS_STORED emission
- **Locations (verified):**
  - `shitvault/event_consumer.py:22-86` — `S3ProcessorWorker.process_event`; the inner `async def _process()` is **47-86**: stats dict **53-59**, key loop **61-67** (reaches into the private `processor._process_single_s3_data` at **65-67**), `SIGNALS_STORED` emission **69-82**.
  - `shitvault/s3_processor.py:84-90` — stats dict; **93-99** — incremental-branch key loop (`if incremental and most_recent_post_id and 's3_keys' in locals():` → `get_raw_data` → `_process_single_s3_data`); **123-140** — `SIGNALS_STORED` emission block; **196-224** — the private `_process_single_s3_data`.
- **Problem:** `event_consumer.py:53-82` is a near-verbatim copy of `s3_processor.py:84-99` + `123-140`. The worker rebuilds the identical stats dict, re-runs the same `get_raw_data`→`_process_single_s3_data` loop, and re-emits the same `SIGNALS_STORED` event — while reaching into a **private** method (`_process_single_s3_data`) across a module boundary. Two copies drift independently (the worker's emit has **no** `try/except`; the processor's does — `126`/`139`). Both stats dicts are the **identical** shape: `total_processed, successful, failed, skipped, signal_ids` (signal_ids popped before return in both paths), so a shared method returns the same keys. Downstream consumers already use defensive access — `shitvault/cli.py:168-171` reads `stats.get('total_processed', 0)` etc., and the worker just stores the dict via `db_event.mark_completed(result)` (`shit/events/worker.py:196`) — so no consumer breaks on shape.
- **Fix:** Add a **public** `S3Processor.process_keys(s3_keys: list[str], dry_run: bool = False) -> Dict[str, int]` that builds the stats dict, runs the `get_raw_data`→`_process_single_s3_data` loop once, and emits `SIGNALS_STORED` once. Extract the emission itself into a private `_emit_signals_stored(signal_ids, dry_run)` helper (with the existing `try/except`) so there is exactly **one** emission block. Then:
  - `process_s3_to_database` incremental branch (93-99) delegates: `stats = await self.process_keys(s3_keys, dry_run)` and returns it.
  - `process_s3_to_database` streaming branch keeps its own stream loop but replaces its inline emission (123-140) with a call to `self._emit_signals_stored(...)`.
  - `S3ProcessorWorker.process_event` delegates: `return asyncio.run(processor.process_keys(s3_keys, dry_run=False))` (keep the empty-`s3_keys` early guard at `event_consumer.py:43-45`; `process_keys` also handles empty lists gracefully).
  - Harmonization bonus: the worker's emission becomes best-effort (`try/except`) like the processor's — a strict improvement.

### #231 L16 — Echo embed TOCTOU
- **Location:** `shit/echoes/echo_service.py` — `embed_and_store` **def at 39-81** (task said 56-78; that range is the TOCTOU body, not the signature). Existence check in **session 1** at **56-64**, `self.embedding_client.embed(text)` at **66**, insert in **session 2** at **68-78**. Session lifecycle is `shit/db/sync_session.py:45-65` `get_session()` — commits on `__exit__`, rolls back on exception.
- **Unique constraint (for ON CONFLICT):** column **`prediction_id`** on table **`post_embeddings`**. The model declares it column-level `unique=True` (`shit/echoes/models.py:18-24`); the design DDL names it **`uq_post_embeddings_prediction`** (`documentation/planning/product-brainstorm_2026-04-09/04_HISTORICAL_ECHOES.md:276`). If the production table was instead created via SQLAlchemy `create_all` the auto-name is **`post_embeddings_prediction_id_key`**. **Use column inference — `ON CONFLICT (prediction_id) DO NOTHING` — which is name-agnostic** and works against whichever unique index/constraint covers `(prediction_id)`, so the plan does not depend on resolving which name is live.
- **Problem:** The check (session 1, 56-64) and the insert (session 2, 68-78) span two separate sessions with an OpenAI `embed()` call in between. Under concurrency (the caller is `ShitpostAnalyzer._embed_prediction`, `shitpost_ai/shitpost_analyzer.py:876-888`, invoked via `asyncio.to_thread`; concurrent/retried analyzer runs or a reactive backfill can process the same `prediction_id` twice) two workers both pass the existence check, both embed, and the second insert hits the unique constraint → unhandled `IntegrityError`, event marked failed and retried.
- **Fix:** Keep the pre-check as a cost optimization (it still short-circuits the expensive `embed()` call in the common already-present case, preserving the current "already exists → `False`" fast path and its test). Replace the ORM `session.add(record)` (68-78) with a PostgreSQL dialect insert: `from sqlalchemy.dialects.postgresql import insert as pg_insert` → `pg_insert(PostEmbedding).values(...).on_conflict_do_nothing(index_elements=["prediction_id"])`, executed on the session. Inspect `result.rowcount`: `1` = inserted (return `True`), `0` = a concurrent writer won the race → **treat the conflict as success, return `True`** (the desired end-state — an embedding for that prediction — holds; no unhandled unique violation). pgvector's `Vector(1536)` column binds fine through a Core insert.

### #231 L18 — API/web cleanup
- **Locations (verified against current code post-#162/#163):**
  - **Dead `get_db()`** — `api/dependencies.py:35-37`. Leak pattern (`return SessionLocal()` — session never closed). **Zero callers** anywhere in the repo (`grep -rn "get_db\b"` returns only the definition; every endpoint uses `execute_query` or `SessionLocal()` directly). Line numbers are **accurate** (not drifted by #162/#163, which added `verify_api_key`/`hmac` above it).
  - **Duplicate `/latest`** — `api/routers/feed.py:13-20` (`get_latest_post`), which is `_service.get_feed_response(0)` — functionally identical to `/at?offset=0` (`feed.py:23-30`). **Frontend evidence:** the React app calls **only** `/at` — `frontend/src/api/client.ts:21` → `` fetchJson(`/api/feed/at?offset=${offset}`) `` (wrapped by `useFeedPost` in `frontend/src/api/hooks.ts:7`, used in `frontend/src/pages/FeedPage.tsx:71`). **No `/latest` reference exists anywhere under `frontend/src/`.** → safe to **remove** the endpoint. (Caveat: the api test suite still targets `/api/feed/latest` — see Notes/Risks; those tests must be repointed to `/at?offset=0`.)
  - **Unbounded `_price_cache`** — `api/queries/price_queries.py:14` (module-level dict), populated at `89`, read at `72-74`. It is only TTL-**checked** on read (never pruned or capped); every distinct `(symbol, days)` key lives forever → unbounded memory growth.
  - **Empty `lifespan`** — `api/main.py:22-25` (`async def lifespan` whose body is a bare `yield`), wired at `main.py:32`. Line numbers **accurate** despite #162/#163 adding rate-limit/security-header/CORS setup below it.
- **Fix:**
  - Delete `get_db()` (`dependencies.py:35-37`) — dead, and it models a leak future code shouldn't copy.
  - Remove `get_latest_post` + its `@router.get("/latest")` decorator (`feed.py:13-20`); keep `/at`. Repoint the api tests (below).
  - Bound `_price_cache`: cap entries (e.g. `max ~256`) with simple LRU eviction (or evict-oldest / opportunistic prune of TTL-expired keys on insert), keeping the existing 5-min `_CACHE_TTL`. A tiny `OrderedDict`-backed helper (`move_to_end` on hit, `popitem(last=False)` past cap) is sufficient — no new dependency.
  - Remove the empty `lifespan` (delete the function + `lifespan=lifespan` at `main.py:32`, and the now-unused `asynccontextmanager` import), **or** give it a real body (e.g. warm/close the DB pool). Prefer removal — there is no real startup/shutdown work today.

## Implementation Plan

### Steps
1. **#191 – shared `process_keys`.** In `shitvault/s3_processor.py`: add private `_emit_signals_stored(self, signal_ids, dry_run)` wrapping the existing 123-140 emit (guard `if not signal_ids or dry_run: return`, `try/except` best-effort). Add public `async def process_keys(self, s3_keys, dry_run=False) -> Dict[str,int]` that builds the stats dict, loops `get_raw_data`→`_process_single_s3_data`, pops `signal_ids`, calls `_emit_signals_stored`, returns stats. Rewire the incremental branch (93-99) to `return await self.process_keys(s3_keys, dry_run)` and replace the streaming branch's inline emit (123-140) with `self._emit_signals_stored(signal_ids, dry_run)`.
2. **#191 – worker delegates.** In `shitvault/event_consumer.py`, collapse the `_process()` body (53-82) to construct the processor and `return await processor.process_keys(s3_keys, dry_run=False)`. Keep the empty-keys early guard (43-45).
3. **#231 L16 – echo idempotency.** In `shit/echoes/echo_service.py:embed_and_store`, swap the ORM add (68-78) for `pg_insert(PostEmbedding).values(...).on_conflict_do_nothing(index_elements=["prediction_id"])`; branch on `result.rowcount` (`0` = conflict → `return True`). Keep the pre-check. Add the `from sqlalchemy.dialects.postgresql import insert as pg_insert` import.
4. **#231 L18 – dead `get_db`.** Delete `api/dependencies.py:35-37`.
5. **#231 L18 – `/latest`.** Remove `get_latest_post` (`api/routers/feed.py:13-20`); repoint the api tests that hit `/api/feed/latest` to `/api/feed/at?offset=0` (`shit_tests/api/conftest.py:175`, `shit_tests/api/test_feed_router.py`, `shit_tests/api/test_api_auth.py`).
6. **#231 L18 – bound cache.** Add LRU/max-entries eviction to `_price_cache` in `api/queries/price_queries.py` (keep TTL).
7. **#231 L18 – lifespan.** Remove the empty `lifespan` + `lifespan=lifespan` + `asynccontextmanager` import from `api/main.py`.
8. Update the echo test doubles (they assert `mock_session.add.called`) to assert on `mock_session.execute` (see Test Plan). Run `pytest shit_tests/shitvault/ shit_tests/api/ shit_tests/echoes/ shit_tests/`, then `ruff check .` / `ruff format .`.
9. Add a `CHANGELOG.md` `[Unreleased]` entry (Changed: S3 processing consolidation, bounded price cache; Fixed: echo TOCTOU; Removed: dead `get_db`, duplicate `/latest`, empty `lifespan`).

## Acceptance Criteria
- [ ] Event consumer and incremental S3 path both call `S3Processor.process_keys`; no duplicated emission block (single `_emit_signals_stored` helper).
- [ ] Concurrent `embed_and_store` for the same key is idempotent (no dup rows, no unhandled unique violation).
- [ ] Dead `get_db()` removed; `/latest` removed (per frontend evidence) with api tests repointed to `/at`; `_price_cache` bounded; `lifespan` removed (or given a real body).
- [ ] `pytest shit_tests/shitvault/ shit_tests/api/ shit_tests/echoes/ shit_tests/` green.
- [ ] `ruff check .` / `ruff format .` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` updated.

## Test Plan
- **#231 L16 (conflict path):** New test in `shit_tests/echoes/test_echo_service.py` — mock the session so the `on_conflict_do_nothing` execute returns `rowcount == 0`; assert `embed_and_store` returns `True` and raises nothing (idempotent conflict = success). Existing `test_stores_new_embedding` / `test_skips_duplicate` must be updated: they currently assert `mock_session.add.called` (line 57) — repoint to `mock_session.execute` and simulate `rowcount == 1`. Empty/None-text fast paths (75-82) are unchanged.
- **#191 (shared stats shape):** Test that `S3Processor.process_keys([...])` returns a dict containing `total_processed/successful/failed/skipped` and that `signal_ids` is popped (not in the returned dict); add/adjust a `S3ProcessorWorker.process_event` test asserting it now delegates to `process_keys` and returns the same shape. Confirm the `SIGNALS_STORED` emit fires once (patch `emit_event`, assert `call_count == 1`).
- **#231 L18 (cache eviction):** Unit test the bounded cache — insert > cap distinct `(symbol, days)` keys and assert oldest is evicted and size stays ≤ cap; assert a fresh hit within TTL still returns cached candles. Extend `shit_tests/api/test_price_queries.py`.
- **api suite exists** — no smoke-test bootstrap needed. `shit_tests/api/` already covers feed/prices/auth (`test_feed_router.py`, `test_prices_router.py`, `test_api_auth.py`, `test_feed_service.py`, `test_feed_queries.py`, `test_price_queries.py`, `test_telegram_router.py`, `test_webhook_secret.py`). The `/latest` removal's main test cost is repointing those files (they use `/api/feed/latest` as the canonical protected path).

## Rollback
- `git revert` of the PR. The `ON CONFLICT` change is additive/safe; **no migration required** — the unique constraint on `post_embeddings(prediction_id)` already exists. The `process_keys` extraction and API removals are pure code; reverting restores prior behavior with no data implications.

## Notes / Risks
- **api/ line-drift check:** #162 (API-key auth + `hmac`) and #163 (rate limiting + `SecurityHeadersMiddleware`) touched `api/main.py` and `api/dependencies.py`, but the four #231 L18 refs verified **accurate** against current code — `get_db` at `dependencies.py:35-37`, empty `lifespan` at `main.py:22-25`, `/latest` at `feed.py:13-20`, `_price_cache` at `price_queries.py:14`. No drift to correct; `feed.py`/`price_queries.py` were untouched by those commits.
- **`/latest` — safe to remove, but test-coupled.** The frontend uses only `/at` (`client.ts:21`), so production is unaffected. **However** the api test suite treats `/api/feed/latest` as its canonical endpoint: `shit_tests/api/conftest.py:175`, most of `shit_tests/api/test_feed_router.py` (incl. `test_get_latest_post_happy_path`, `test_get_latest_post_empty_database`, and ~9 more at lines 291-478), and the auth tests in `shit_tests/api/test_api_auth.py` (34-150). Removal is **not** a one-line change — it requires repointing those tests to `/api/feed/at?offset=0` (there is already a `test_feed_router.py:125` test asserting the two behave identically; it becomes redundant and should be dropped or repurposed). If the reviewer prefers to avoid the test churn, the fallback is to **consolidate** — keep `/latest` as a thin alias delegating to the same service call — but given zero frontend usage and identical semantics, **removal + test repoint is recommended.** The Telegram `/latest` references in `shit_tests/notifications/test_telegram_bot.py` are an unrelated bot command, not this endpoint.
- **ON CONFLICT constraint name:** using column inference (`ON CONFLICT (prediction_id)`) sidesteps the ambiguity between the design-doc name `uq_post_embeddings_prediction` and a possible SQLAlchemy auto-name `post_embeddings_prediction_id_key`. If a reviewer insists on `ON CONSTRAINT <name>`, confirm the live name on Neon first (`\d post_embeddings`).
- **Streaming branch coupling (#191):** the non-incremental branch of `process_s3_to_database` streams via `stream_raw_data` and cannot itself call `process_keys` (no key list), so it retains its own loop — but it shares the single `_emit_signals_stored` helper, satisfying "no duplicated emission block."
- **Echo pre-check retained on purpose:** dropping it entirely would send every already-embedded prediction through a needless OpenAI `embed()` call before the no-op insert; keeping it preserves the cost optimization while ON CONFLICT closes the race.
