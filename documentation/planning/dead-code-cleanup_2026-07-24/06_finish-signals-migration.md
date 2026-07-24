---
title: "Phase 6 — Finish signals migration"
session: dead-code-cleanup_2026-07-24
status: READY
issues: [224, 229]
code_area: shitvault, shitpost_ai, shitposts, shit/content
risk: medium
---

# Phase 6 — Finish signals migration

## Summary
This is the heaviest, riskiest phase in the cluster. It finishes the `truth_social_shitposts` → `signals` cutover that PR #140 started but did not complete. Most of the work is non-behavioral cleanup (removing read-time `shitpost_id` aliasing, deleting dead multi-source scaffolding, tightening a bypass check, implementing a stubbed stats method). **One sub-part is genuinely behavioral: `shitvault/statistics.py` still counts the frozen `truth_social_shitposts` table, so migrating it to `signals` will change the numbers the `stats` CLI reports in production.** Because of that, the recommendation below is to **split M23 into its own PR** so the identity/dead-code cleanup can land risk-free first. The CHANGELOG already claims "Signals Migration Complete," which the statistics code currently contradicts — this phase makes the claim true.

## Findings

### #224 M22 — Dual identity shitpost_id ↔ signal_id (app code)
- **Locations (verified against current code):**
  - `shitvault/signal_operations.py:160-161` — CONFIRMED. Line 160 is the comment `# Backward-compatible aliases (for analyzer, bypass service, etc.)`; line 161 is `"shitpost_id": sig.signal_id,`. This is the single injection point of the `shitpost_id` alias. (The same dict, lines 162-195, also injects other legacy aliases — `timestamp`, `username`, `platform`, `content`, `reblog`, `mentions`, `tags`, `reblogs_count`, `favourites_count`, `upvotes_count`, `account_*` — those are a *separate* field-name-vocabulary concern and are **out of scope** for M22; see note below.)
  - `shitpost_ai/shitpost_analyzer.py:386-394` — CONFIRMED. Line 386 `shitpost_id = shitpost.get("shitpost_id")`; line 394 `if await self.prediction_ops.check_prediction_exists(shitpost_id, use_signal=True):`.
  - `shitpost_ai/shitpost_analyzer.py:603-604` — CONFIRMED. Line 603 `"shitpost_id": None,`; line 604 `"signal_id": shitpost_id,` (inside the `PREDICTION_CREATED` event payload).
  - **Additional live sites found (drift — not in the original finding, must be fixed for a clean cutover):**
    - `shitpost_ai/shitpost_analyzer.py:462` — `shitpost_id = shitpost.get("shitpost_id")` (second read, in `_analyze_shitpost`).
    - `shitpost_ai/shitpost_analyzer.py:438` and `:662` — `shitpost.get('shitpost_id', 'unknown')` in error logs.
    - `shitpost_ai/shitpost_analyzer.py:478, 565` — pass `use_signal=True` to `handle_no_text_prediction` / `store_analysis`.
    - `shitvault/prediction_operations.py:49, 57, 157, 167, 226, 238` — `use_signal: bool = True` params, each documented `"Deprecated, ignored. Always ... signal_id."` These are no-ops and should be removed.
    - `shit/events/event_types.py:67` — `PREDICTION_CREATED` schema doc still lists `"shitpost_id": "str|None - shitpost ID if available"`.
- **Verification of the coupling:** `get_unprocessed_signals` is the ONLY producer of the `shitpost_id` dict key (signal_operations.py:161), and `ShitpostAnalyzer` is the ONLY consumer (`shitpost.get("shitpost_id")`). `prediction_operations.py` does **not** read `shitpost_id` from any dict (confirmed by grep — it receives the id positionally). So the alias and its readers can be cut together with no other app-code impact.
- **Problem / Fix:** The app speaks `shitpost_id` and relies on `signal_operations` injecting `shitpost_id = signal_id` at read time. Standardize on `signal_id` end-to-end: (1) analyzer reads `shitpost.get("signal_id")` (rename the local to `signal_id` for clarity); (2) delete the `"shitpost_id": sig.signal_id` alias at signal_operations.py:161; (3) drop the no-op `use_signal=True` kwargs and their params; (4) drop `"shitpost_id": None` from the event payload and the matching line in the event schema doc. **Keep DB-column compatibility only** — `predictions.shitpost_id` is a nullable DB column for historical rows and is NOT touched (the Python `Prediction` model already has no `shitpost_id` attribute per PR #140). No schema change.
- **Out of scope (explicit):** The other legacy aliases in the signal_operations dict (`timestamp`/`username`/`reblog`/`mentions`/`tags`/engagement counts) stay — they are still consumed by `_prepare_enhanced_content`, `_enhance_analysis_with_shitpost_data`, and `BypassService._is_retruth`. Full field-name unification is a larger, separate effort; M22 is scoped to the *identity* alias only.

### #224 M23 — Legacy table drives stats  (BEHAVIOR CHANGE)
- **Locations (verified):** `shitvault/statistics.py:12` imports `TruthSocialShitpost`; two methods query it:
  - `get_analysis_stats()` lines 27-62 — counts `TruthSocialShitpost.id` (line 32). **This method has NO live callers** (the `stats` CLI calls `get_database_stats`, not this; only tests reference it). It is effectively dead.
  - `get_database_stats()` lines 64-125 — the LIVE method behind `python -m shitvault stats` (cli.py:191). Query 1 (lines 68-72) counts `TruthSocialShitpost.id` and takes `min/max(TruthSocialShitpost.timestamp)`.
- **Current query** (`get_database_stats`, Query 1, statistics.py:68-72):
  ```python
  stats_stmt = select(
      func.count(TruthSocialShitpost.id).label("shitpost_count"),
      func.min(TruthSocialShitpost.timestamp).label("min_date"),
      func.max(TruthSocialShitpost.timestamp).label("max_date"),
  )
  ```
- **Proposed query** (signals-based equivalent; `from shitvault.signal_models import Signal`):
  ```python
  stats_stmt = select(
      func.count(Signal.id).label("shitpost_count"),
      func.min(Signal.published_at).label("min_date"),
      func.max(Signal.published_at).label("max_date"),
  )
  ```
  Column mapping: `TruthSocialShitpost.id → Signal.id`, `TruthSocialShitpost.timestamp → Signal.published_at`. Output dict keys stay identical (`total_shitposts`, `earliest_post`, `latest_post`, `analysis_rate`) — only the source table changes, so the CLI/consumer contract is unchanged.
- **Impact (numbers WILL change):** `truth_social_shitposts` is write-archived and frozen; `signals` was backfilled from it at 100% coverage (CHANGELOG line 222) and is the **live, growing** table (~32,881 rows at migration, higher now). Therefore `total_shitposts` increases, `earliest_post`/`latest_post` extend to the live edge, and `analysis_rate = total_analyses / total_shitposts` shifts. This is a production-visible change to the `stats` command output.
- **CHANGELOG contradiction (noted):** `[Unreleased]` line 31 states *"Signals Migration Complete — All readers now use `signals` table instead of legacy `truth_social_shitposts`."* That is false while `statistics.py` reads the legacy table. This phase makes it true; the `[Unreleased]` entry must be reconciled to record that statistics was the final straggler.
- **`get_analysis_stats` decision:** it is dead (no app/CLI caller). Recommendation: **delete it** (and its ~6 mock tests / integration assertions) to remove the second legacy-table reader. Conservative alternative: migrate it to `Signal` too (its tests are table-agnostic mocks and would still pass). Either way, after this phase `statistics.py` imports `Signal`, not `TruthSocialShitpost`.

### #224 M24 — Multi-source dead code
- **Recommendation: REMOVE** `shitposts/harvester_registry.py` and `shitposts/twitter_harvester.py` (plus their tests), and drop `HarvesterRegistry` / `create_default_registry` from `shitposts/__init__.py` `__all__`.
- **Evidence (grep):**
  - Live harvest dispatch does NOT use the registry. `shitposts/__main__.py` calls `truth_social_s3_harvester.main()` directly, which builds a `TruthSocialS3Harvester` via `create_harvester_parser` (cli.py). `create_default_registry` / `create_all_enabled` / `create_harvester` have **zero** non-test, non-self callers — the only non-test reference to the registry is the re-export in `shitposts/__init__.py:7,12-13`.
  - `TwitterHarvester` has **zero** live importers. Its only non-test references are a docstring example (`harvester_registry.py:21`) and a comment (`harvester_registry.py:178`). The class body raises `NotImplementedError` in `_test_connection`/`_fetch_batch` — it is an explicit skeleton.
  - Tests to delete alongside: `shit_tests/shitposts/test_harvester_registry.py`, `shit_tests/shitposts/test_twitter_harvester.py`.
  - **Not dead (keep):** `shitposts/base_harvester.py` (`SignalHarvester` — live base class of `TruthSocialS3Harvester`) and `shitposts/harvester_models.py` (`HarvestResult`/`HarvestSummary` used by the live harvester; `HarvesterConfig` only used by the registry — it can go with the registry or stay harmlessly). Also trim the aspirational `--source twitter` line in `shitposts/__main__.py`'s docstring, since the live path does not switch sources.
- **Per the downgrade rule:** the registry is NOT referenced by live dispatch (only re-exported), so "remove" stands — no downgrade to a #193 flag is needed. Reintroducing multi-source wiring belongs with harvester issues #193/#211 in a separate cluster; the registry pattern remains recoverable from git history.
- **Archived `TruthSocialShitpost` ORM model — decision: KEEP + document (do NOT delete).** After M23 the model has no query-driving reader. Remaining references are benign: `shit/db/sync_session.py:73` (metadata/table registration) and `shit/echoes/backfill.py:38` (a raw-SQL `LEFT JOIN truth_social_shitposts`, not the ORM class). The DB table still holds historical rows. This matches CLAUDE.md ("Archived — no new writes, retained for historical reference"). Removing the class is a separate schema-adjacent call, out of scope here.
- **`shitvault/README.md` — align to signals-only reality (doc-only).** It is stale: references dual-write (line 13), the deleted `ShitpostOperations` (lines 140, 297, 308), `truth_social_shitposts` as the primary table (line 55), and `predictions.shitpost_id` as the FK (lines 84, 381). Rewrite to: `SignalOperations` primary, `signals` primary table, `predictions.signal_id` FK, `s3_processor` signals-only (no dual-write), `truth_social_shitposts` archived.

### #229 L13 — Bypass phrases too aggressive
- **DRIFT — the finding's premise is largely incorrect for current code.** `BypassService._is_test_content` (bypass_service.py:159-160) is:
  ```python
  text_lower = text_content.lower().strip()
  return text_lower in self.TEST_PHRASES
  ```
  This is already a **whole-post exact match** (membership in a set), NOT a substring match. A legitimate short post such as `"Hello everyone, big $TSLA news today"` does not match any phrase and is not bypassed by this check.
- **Second observation:** every configured phrase in `TEST_PHRASES` (bypass_service.py:60) — `'test'` (4), `'testing'` (7), `'hello'` (5), `'hi'` (2), `'test post'` (9) — is shorter than `MIN_TEXT_LENGTH = 10`. So Check 3 (`TEXT_TOO_SHORT`) fires first and Check 5 (`_is_test_content`) is **effectively unreachable** for its own phrase set. Bare greetings are already bypassed, just under the `TEXT_TOO_SHORT` reason (the existing test `test_bypass_test_content` even notes "Some may be caught by earlier checks").
- **Current rule:** exact match of the full, stripped, lowercased post against `{'test','testing','hello','hi','test post'}` — but unreachable in practice because all phrases are below the length floor.
- **Proposed rule (precise, conservative):** keep exact whole-post matching; never substring. Normalize with `.strip().lower()` and strip trailing punctuation, then require the ENTIRE post to equal a known marker. Narrow `TEST_PHRASES` to unambiguous testing markers — `{'test', 'testing', 'test post'}` — dropping the bare greetings `'hello'`/`'hi'` (they are redundant with `TEXT_TOO_SHORT` and are the only genuinely ambiguous entries; this also stays safe if `MIN_TEXT_LENGTH` is ever lowered). Net effect on real posts: unchanged (they were never bypassed by this check). The real deliverable is a **regression test** locking the safe behavior plus removal of a misleading, unreachable branch. (Optional stricter variant: delete Check 5 / `TEST_PHRASES` entirely, since it is unreachable today — but keeping a narrowed, documented exact-match check is the lower-surprise choice.)

### #229 L14 — get_s3_processing_stats stub
- **Location (verified, minor drift):** `shitvault/s3_processor.py` — method `get_s3_processing_stats` spans **lines 226-250**; the stubbed return dict is **lines 238-246** (finding said 236-245). The stub hardcodes `'db_stats': {}`, `'db_records': 0`, `'processing_ratio': 0.0`; only `s3_stats` is real. It is reached by `python -m shitvault processing-stats` (cli.py:199-217, `get_processing_stats`).
- **Recommendation: IMPLEMENT MINIMALLY** (do not remove the CLI). Rationale: the S3 half already works; only the DB half is stubbed; and the `stats` command already demonstrates the exact pattern for a live `signals` count. Wire `db_records` from `func.count(Signal.signal_id)` (consistent with M23), compute `processing_ratio = db_records / s3_files` (guard divide-by-zero), and optionally populate `db_stats` by delegating to `Statistics.get_database_stats()`. This is read-only and cheap. Removing the command is defensible but discards a working S3-side report.
- **Interaction with Phase 5 (#191 `process_keys`):** orthogonal — `get_s3_processing_stats` does not touch the processing path. But both phases edit `S3Processor`, so sequence Phase 6's minimal stats impl to rebase cleanly on Phase 5. If Phase 5 introduces a shared `signals`-count helper, reuse it rather than duplicating the query.
- **Test impact:** `shit_tests/shitvault/test_s3_processor.py:309` (`test_get_s3_processing_stats_success`) and `:330` (`..._error`) currently assert the stub shape and must be updated to the real counts.

## Implementation Plan

### Steps
1. **(M22) Standardize identity in the analyzer.** In `shitpost_ai/shitpost_analyzer.py`, replace both `shitpost.get("shitpost_id")` reads (lines 386, 462) and the two `shitpost.get('shitpost_id', 'unknown')` log reads (438, 662) with `signal_id`; rename the local variable `shitpost_id → signal_id` throughout `_analyze_batch`/`_analyze_shitpost` for clarity. Remove `use_signal=True` from the `check_prediction_exists` (394), `handle_no_text_prediction` (478), and `store_analysis` (565) calls. In the event payload (601-610) drop `"shitpost_id": None` and keep `"signal_id"`.
2. **(M22) Drop the alias and dead params.** Delete `shitvault/signal_operations.py:161` (`"shitpost_id": sig.signal_id,`) and its comment scope note. Remove the `use_signal` params (and their docstring lines) from `shitvault/prediction_operations.py` (43-57, 151-167, 222-238). Remove the `"shitpost_id"` line from the `PREDICTION_CREATED` schema in `shit/events/event_types.py:67`.
3. **(M22) Verify** the return-key alias for the bypass path: the bypassed-analysis dict at analyzer:481-485 returns `"shitpost_id": shitpost_id` — rename that key to `"signal_id"` and confirm no caller reads `["shitpost_id"]` off the return (grep: only the batch loop inspects `analysis_status`, so safe).
4. **(M24) Delete dead multi-source scaffolding.** Remove `shitposts/harvester_registry.py`, `shitposts/twitter_harvester.py`, `shit_tests/shitposts/test_harvester_registry.py`, `shit_tests/shitposts/test_twitter_harvester.py`. Edit `shitposts/__init__.py` to drop the `harvester_registry` import and the `HarvesterRegistry` / `create_default_registry` entries from `__all__`. Trim the `--source twitter` line from `shitposts/__main__.py`'s docstring.
5. **(M24) Docs.** Rewrite `shitvault/README.md` to the signals-only reality (SignalOperations primary; `signals` primary table; `predictions.signal_id` FK; s3_processor single-write; `truth_social_shitposts`/`TruthSocialShitpost` archived-retained). Keep the `TruthSocialShitpost` model.
6. **(L13) Tighten + lock the bypass rule.** In `shit/content/bypass_service.py`, narrow `TEST_PHRASES` (line 60) to `{'test', 'testing', 'test post'}`; keep exact whole-post matching in `_is_test_content` (159-160) and add trailing-punctuation normalization. Add regression tests (below).
7. **(L14) Implement the stats method.** In `shitvault/s3_processor.py:226-250`, replace the stub `db_records`/`processing_ratio` with a real `signals` count and computed ratio (guard zero); update `shit_tests/shitvault/test_s3_processor.py` accordingly.
8. **(M23 — SEPARATE PR, see split rec)** Swap `get_database_stats` Query 1 to `Signal` (statistics.py:68-72), update the `import` at line 12, delete (or migrate) the dead `get_analysis_stats`, add a pinning test, and reconcile the CHANGELOG "Signals Migration Complete" entry.
9. Run `pytest shit_tests/shitvault/ shit_tests/shitpost_ai/ shit_tests/content/ shit_tests/shitposts/`, then `ruff check .` / `ruff format .`. Update `CHANGELOG.md` `[Unreleased]`.

## Acceptance Criteria
- [ ] App code references `signal_id` (no read-time `shitpost_id` aliasing); DB column retained.
- [ ] Stats computed from `signals`; a test pins the new counts; CHANGELOG reconciled.
- [ ] Multi-source dead code removed (or explicitly deferred with a tracking note).
- [ ] Bypass rule tightened; a test proves a legitimate short post is no longer bypassed while true greetings still are.
- [ ] `processing-stats` CLI works or is removed.
- [ ] `pytest shit_tests/shitvault/ shit_tests/shitpost_ai/ shit_tests/content/` green.
- [ ] `ruff check .` / `ruff format .` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` updated (reconcile the "Signals Migration Complete" claim).

## Test Plan
- **M22 (identity):** covered by existing analyzer tests (`shit_tests/shitpost_ai/`) — they exercise `_analyze_batch`/`_analyze_shitpost` and will fail if the `signal_id` read breaks. Add/adjust a `signal_operations` test asserting the returned dict no longer contains a `shitpost_id` key (the migration's end state). Confirm `prediction_operations` tests still pass after `use_signal` param removal (params were no-ops).
- **M23 (stats, behavioral):** the current `test_statistics.py` tests are pure mocks (they inject `scalar`/`one()` values and never assert which table is queried) — they will NOT catch a regression to the legacy table. Add a **pinning test** that compiles the `get_database_stats` statement and asserts `"signals"` appears in the FROM clause and `"truth_social_shitposts"` does not (e.g. `str(stmt.compile())`). Optionally add an integration test seeding `signals` + `predictions` in a test DB and asserting `total_shitposts`/`analysis_rate` against known fixture counts (before/after: legacy-frozen count vs live signals count).
- **L13 (bypass):** add unit tests — (a) `"Hello everyone, huge $TSLA news today"` → `should_bypass is False` (greeting as a prefix of a real post is not bypassed); (b) bare `"hello"` → still bypassed (as `TEXT_TOO_SHORT`); (c) `"test"` / `"testing"` / `"test post"` exact → bypassed; (d) `"testing the new $AAPL rollout in Q3"` → NOT bypassed (greeting/marker substring inside a real post). Update `test_threshold_configuration` / `test_bypass_test_content` for the narrowed set.
- **L14 (stub):** update `test_get_s3_processing_stats_success` to assert real `db_records`/`processing_ratio` from a mocked `signals` count; keep the error-path test.

## Rollback
- `git revert` of the PR. No schema change (the `predictions.shitpost_id` and `truth_social_shitposts` DB columns/tables are retained). On revert of the M23 PR, the `stats` command reverts to legacy `truth_social_shitposts` counts — no data migration to undo.

## Notes / Risks
- **Split recommendation (strong): two PRs.**
  - **PR-A (non-behavioral):** M22 identity cleanup + M24 dead-code removal + L13 bypass tightening + L14 stub impl + README/CHANGELOG docs. Nothing here changes a production-visible number; it can land and deploy with low review risk.
  - **PR-B (behavioral, isolated):** M23 statistics source swap + pinning test + CHANGELOG reconciliation. Isolating it means the one change that shifts `stats`/`analysis_rate` output is reviewed and deployed on its own, with eyes on the dashboard, and is trivially revertable without dragging the cleanup back.
- If a single PR is preferred for velocity, land M23 as a clearly-labeled standalone commit so it can be cherry-reverted.
- **L13 is a verify-and-lock, not a bug fix** — flag in the PR description that the reported substring risk does not exist in current code (matching is already exact) and that the real value delivered is a regression test plus removal of an unreachable branch. Avoid the temptation to "fix" it by switching to substring matching — that would introduce the very bug the finding feared.
- **M24 model decision:** keep `TruthSocialShitpost`; only its statistics reader is removed. Do not let the dead-code sweep delete the ORM class or the DB table — historical rows and the echoes raw-SQL join still depend on the table existing.
- **Sequencing with Phase 5 (#191):** both phases edit `S3Processor`; land/rebase so L14's minimal stats impl and Phase 5's `process_keys` don't collide.
