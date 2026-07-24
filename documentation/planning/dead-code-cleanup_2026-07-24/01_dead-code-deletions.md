---
title: "Phase 1 — Dead-code deletions"
session: dead-code-cleanup_2026-07-24
status: COMPLETE
started: 2026-07-24
completed: 2026-07-24
pr: 234
issues: [187, 189, 192, 194]
code_area: shitvault, shit/db, shit/utils, shit/logging
risk: very low
---

# Phase 1 — Dead-code deletions

## Summary
Four pure deletions with no behavior change: a completed one-shot migration script
(#187), a dead S3→shitpost transform method superseded by `SignalTransformer` (#189), the
unused resilience machinery in `error_handling.py` — retry decorators, `CircuitBreaker`,
`RateLimiter`, module-global instances, and debug log helpers (#192) — and the dead
`progress_tracker` module plus its `Icons.PROGRESS` monkeypatch (#194). All four have zero
live callers; the only references are their own tests, archived planning docs, and the
CHANGELOG. Net effect is ~1,000+ LOC removed (source + tests) with the live code paths
(`SignalTransformer.transform_truth_social`, `handle_exceptions`, `parse_timestamp`)
untouched.

## Findings

### #187 — Delete the completed `migrate_to_signals.py` one-shot script
- **Location:** `shitvault/migrate_to_signals.py` (351 LOC; self-contained script with its own `build_parser()` at :288, `main()` at :310, and `if __name__ == "__main__"` at :350).
- **Problem:** One-time historical backfill (`truth_social_shitposts` → `signals` + prediction FK). Migration is complete — PR #140 merged, run on production (32,881 rows, 5,566 predictions backfilled per session memory). No production call-site; invoked only manually as `python -m shitvault.migrate_to_signals`.
- **Verified against `main`:** CONFIRMED — file exists at 351 LOC; `shitvault/__main__.py` routes only to `cli.main` (`from shitvault.cli import main` → `asyncio.run(main())`), with no reference to the migration module; `shitvault/cli.py` has no `migrate` reference.
- **Deadness evidence:** `rg "migrate_to_signals"` (excl. venv) returns only: the file itself, archived/planning docs (`docs/superpowers/plans/2026-04-14-signals-migration.md`, `documentation/archive/system-evolution_2026-02-11/02_source-agnostic-data-model.md`), and `CHANGELOG.md:37`. No live `import`/`from ... import` anywhere in source.
- **Fix:** `git rm shitvault/migrate_to_signals.py`. No test file exists for it (nothing to remove). Leave archived docs and the historical CHANGELOG line as-is.

### #189 — Delete dead `DatabaseUtils.transform_s3_data_to_shitpost`  (≡ Wave B #229 L11)
- **Location:** `shit/db/database_utils.py:48-134` (`@staticmethod` at :48, `def transform_s3_data_to_shitpost` at :49, body ends :134).
- **Problem:** Legacy transform that built the archived `truth_social_shitposts` row shape. The live S3→DB path uses `SignalTransformer.transform_truth_social`; this method is dead since the signals cutover (PR #140).
- **Verified against `main`:** CONFIRMED at `shit/db/database_utils.py:48-134`. The sibling live method `parse_timestamp` (`:22-46`) STAYS — it is used by `shitvault/prediction_operations.py` (:87,:132,:180), `shit/db/signal_utils.py` (:95), and internally. The enclosing `DatabaseUtils` class STAYS (only the one method is removed).
- **Deadness evidence:** `rg "transform_s3_data_to_shitpost"` (excl. venv) shows the only invocations are in `shit_tests/shit/db/test_database_utils.py` (13 call-sites). All other hits are archived docs/specs (`documentation/archive/...`, `docs/superpowers/...`) — no live caller.
- **Fix:** Remove the method (`database_utils.py:48-134`). Drop the 13 `test_transform_s3_data*` test methods **and** the now-orphaned `sample_s3_data` fixture (`test_database_utils.py:17-74`, consumed only by those tests). Remove imports orphaned by the deletion — `import json` and `from typing import Dict, Any, Optional` (both used only by the removed method) — keeping `from datetime import datetime` (needed by `parse_timestamp`). Let `ruff check` confirm no unused imports remain.
- **Dedup:** This is identical to Wave B finding **#229 (L11)**. The closing PR should reference both #189 and #229 (#229 is a multi-finding cluster issue — check off L11, do not close).

### #192 — Reduce `error_handling.py` to only `handle_exceptions()`  (deletion portion of Wave B #220 M8)
- **Location:** `shit/utils/error_handling.py`. Keep `handle_exceptions` (`:17-28`). Delete everything after it (`:31-251`): `async_retry` (:31-62), `sync_retry` (:65-97), `CircuitBreaker` (:100-157), `RateLimiter` (:159-184), the four module globals `truth_social_circuit_breaker`/`llm_circuit_breaker`/`truth_social_rate_limiter`/`llm_rate_limiter` (:187-201), `log_function_call` (:204-209), `log_function_result` (:212-219), and the `test_error_handling` self-test + `__main__` block (:222-251).
- **Problem:** Resilience/logging machinery that was never wired into any live path. Retries, circuit-breaking, and rate-limiting are all dead scaffolding.
- **Verified against `main`:** CONFIRMED — `handle_exceptions` at `:17-28`; dead symbols span `:31-251`. Live importers all import **only** `handle_exceptions`: `shit/llm/llm_client.py:13`, `shitpost_ai/shitpost_analyzer.py:16`, `shitvault/cli.py:12`. A targeted grep confirms none of these files reference any other `error_handling` symbol.
- **Deadness evidence:** `rg` for `async_retry|sync_retry|CircuitBreaker|RateLimiter|log_function_call|log_function_result|*_circuit_breaker|*_rate_limiter` (excl. venv) returns only definitions in `error_handling.py`, references inside its own unit test `shit_tests/shit/utils/test_error_handling.py`, and archived docs. Zero live application references.
- **Fix:** Delete `:31-251`. Trim the module imports to what `handle_exceptions` actually needs — keep `import logging`, `import traceback`, and `from shit.logging import get_service_logger`; **remove the now-unused `import asyncio`, `from typing import Optional, Callable, Any`, and `from functools import wraps`** (ruff F401 otherwise). In `test_error_handling.py`, keep the `TestHandleExceptions` class (`:28-91`) and delete the other eight classes (`TestAsyncRetry` :95, `TestSyncRetry` :222, `TestCircuitBreaker` :341, `TestRateLimiter` :543, `TestGlobalInstances` :636, `TestLoggingFunctions` :662, `TestTestErrorHandling` :747, `TestEdgeCases` :776); trim the top import block (`:12-25`) to import only `handle_exceptions` and drop `import shit.utils.error_handling as error_handling_module` (used only by the removed `TestTestErrorHandling`).
- **Scope note / Dedup:** This overlaps Wave B **#220 (M8)**, but #220 is a broader **P2 LLM-robustness** issue (it argues for *adding* real retry/backoff around LLM calls). Phase 1 performs **only the dead-utils deletion** — it does not add resilience. The PR should reference #220 M8 as "dead-code portion addressed"; the robustness redesign stays in its P2 cluster and #220 remains open.

### #194 — Delete the dead `progress_tracker` module and its `Icons.PROGRESS` monkeypatch
- **Location:** `shit/logging/progress_tracker.py` (212 LOC): `ProgressTracker` (:13), `track_progress` (:159), `simple_progress` (:184), and the import-time mutation `Icons.PROGRESS = "📊"` (:210-212). Re-exports live in `shit/logging/__init__.py` at `:49-53` (import block) and `:97-99` (`__all__` entries).
- **Problem:** Progress-display helpers with no live consumers. The module mutates the shared `Icons` class at import (`Icons.PROGRESS = "📊"`) purely to serve its own dead `update()`/`simple_progress()` output — a side effect on shared state that exists only for dead code.
- **Verified against `main`:** CONFIRMED — file is 212 LOC; the `Icons.PROGRESS` mutation is at `:210-212`; `__init__.py` import block is at `:49-53` and `__all__` entries at `:97-99`. **No live caller needs `PROGRESS`:** `Icons` in `shit/logging/formatters.py:48` defines `ERROR`/`SUCCESS`/etc. but **not** `PROGRESS`, and `rg "Icons.PROGRESS"` finds references only inside `progress_tracker.py` (:90, :204, :211, :212). Therefore adding `PROGRESS` to `Icons` in `formatters.py` is **NOT needed** — nothing outside the deleted module reads it.
- **Deadness evidence:** `rg "progress_tracker|ProgressTracker|track_progress|simple_progress"` (excl. venv) returns only: the module itself, the `__init__.py` re-export, its own test `shit_tests/shit/logging/test_progress_tracker.py`, and doc/CHANGELOG mentions. No application import of any of the three public symbols.
- **Fix:** `git rm shit/logging/progress_tracker.py` and `git rm shit_tests/shit/logging/test_progress_tracker.py` (524 LOC, all `ProgressTracker` tests). In `shit/logging/__init__.py`, remove the `from .progress_tracker import (...)` block (`:49-53`) and the three `__all__` entries (`:97-99`). Do **not** add `PROGRESS` to `Icons`.
- **Cross-phase note:** Phase 3 (`03_logging-module-cleanup.md`) also edits `shit/logging/__init__.py`. Phase 1 removes the `progress_tracker` import block and `__all__` entries there, so **Phase 3 should rebase on / land after Phase 1** to avoid conflicts in that file (also called out in `00_OVERVIEW.md`).

## Implementation Plan
### Steps
1. **#187** — `git rm shitvault/migrate_to_signals.py`. Confirm nothing else imports it (already verified). No test to remove.
2. **#189** — In `shit/db/database_utils.py`: delete `transform_s3_data_to_shitpost` (`:48-134`); remove the now-unused `import json` (:10) and `from typing import Dict, Any, Optional` (:9); keep `from datetime import datetime`, the `DatabaseUtils` class, and `parse_timestamp`.
3. **#189 (tests)** — In `shit_tests/shit/db/test_database_utils.py`: delete the 13 `test_transform_s3_data*` methods (:117, :129, :160, :173, :185, :197, :221, :231, :241, :250, :266, :278, :289) and the orphaned `sample_s3_data` fixture (:17-74). Keep the six `test_parse_timestamp*` tests.
4. **#192** — In `shit/utils/error_handling.py`: delete `:31-251` (all symbols after `handle_exceptions`); trim imports to `import logging`, `import traceback`, `from shit.logging import get_service_logger`; remove `import asyncio`, `from typing import Optional, Callable, Any`, `from functools import wraps`.
5. **#192 (tests)** — In `shit_tests/shit/utils/test_error_handling.py`: keep `TestHandleExceptions` (:28-91); delete the other eight test classes (:95, :222, :341, :543, :636, :662, :747, :776); trim the import block (:12-25) to only `handle_exceptions` and drop `import shit.utils.error_handling as error_handling_module`.
6. **#194** — `git rm shit/logging/progress_tracker.py` and `git rm shit_tests/shit/logging/test_progress_tracker.py`.
7. **#194 (init)** — In `shit/logging/__init__.py`: remove the `from .progress_tracker import (...)` block (:49-53) and the `'ProgressTracker'`, `'track_progress'`, `'simple_progress'` entries from `__all__` (:97-99). Do not touch the `Icons` import or `formatters.py`.
8. Run `ruff check .`, `ruff format .`, then `pytest shit_tests/`. Update `CHANGELOG.md` `[Unreleased]` → `### Removed`.

## Acceptance Criteria
- [ ] `shitvault/migrate_to_signals.py` deleted; `rg migrate_to_signals` returns only docs/CHANGELOG.
- [ ] `shit/db/database_utils.py` retains `DatabaseUtils` + `parse_timestamp` only; `transform_s3_data_to_shitpost` gone; no unused `json`/`typing` imports.
- [ ] `shit/utils/error_handling.py` contains only `handle_exceptions` + its needed imports (`logging`, `traceback`, `get_service_logger`); all retry/circuit-breaker/rate-limiter/log-helper/self-test code removed.
- [ ] `shit/logging/progress_tracker.py` deleted; `shit/logging/__init__.py` no longer imports or exports `ProgressTracker`/`track_progress`/`simple_progress`; `Icons` unchanged (no `PROGRESS` added).
- [ ] `pytest shit_tests/` green — specifically `shit_tests/shit/db/test_database_utils.py` (parse_timestamp tests only), `shit_tests/shit/utils/test_error_handling.py` (`TestHandleExceptions` only); `shit_tests/shit/logging/test_progress_tracker.py` deleted.
- [ ] `ruff check .` and `ruff format .` clean (confirms no orphaned imports).
- [ ] `CHANGELOG.md` `[Unreleased]` updated under `### Removed`.

## Test Plan
- Run `pytest shit_tests/shit/db/test_database_utils.py shit_tests/shit/utils/test_error_handling.py shit_tests/shit/logging/ -q` after edits, then the full `pytest shit_tests/`.
- Deleted test blocks: 13 transform tests + `sample_s3_data` fixture (test_database_utils.py); 8 test classes (test_error_handling.py); the entire test_progress_tracker.py (524 LOC).
- Deadness re-proof (should all return only docs/tests, no live source) —
  - `rg "migrate_to_signals" --glob '!venv/**'`
  - `rg "transform_s3_data_to_shitpost" --glob '!venv/**'`
  - `rg "async_retry|sync_retry|CircuitBreaker|RateLimiter|log_function_call|log_function_result" --glob '!venv/**' --glob '!*.md'`
  - `rg "progress_tracker|ProgressTracker|track_progress|simple_progress|Icons\.PROGRESS" --glob '!venv/**' --glob '!*.md'`
- Import smoke check: `./venv/bin/python -c "import shit.logging, shit.utils.error_handling, shit.db.database_utils"` must succeed (proves `__init__.py` and trimmed imports are consistent).

## Rollback
- Pure `git revert` of the PR; no data/schema impact (migration already completed; no runtime behavior touched).

## Notes / Dedup
- #189 ≡ Wave B **#229 (L11)**; #192 overlaps Wave B **#220 (M8)** — deletion portion only (the P2 LLM-robustness redesign in #220 is out of scope here). Reference both parent issues in the PR; the multi-finding cluster issues (#229, #220) stay open with only their L11 / M8 portions checked off.
- Cross-phase: Phase 3 also edits `shit/logging/__init__.py` — Phase 1 removes the `progress_tracker` import/`__all__` lines first, so Phase 3 should rebase on or land after Phase 1 (per `00_OVERVIEW.md` dependency note).
