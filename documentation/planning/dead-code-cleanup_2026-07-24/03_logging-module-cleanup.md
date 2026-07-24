---
title: "Phase 3 — Logging module cleanup"
session: dead-code-cleanup_2026-07-24
status: READY
issues: [196, 197]
code_area: shit/logging
risk: low
---

# Phase 3 — Logging module cleanup

## Summary
Two mechanical, behavior-preserving fixes inside `shit/logging/`. **#196**: the name
`get_cli_logger` is defined twice with divergent contracts and is listed in
`__init__.py`'s `__all__` without ever being imported, so `from shit.logging import *`
raises `AttributeError` and `from shit.logging import get_cli_logger` raises
`ImportError` — the export is simply broken. We keep the `CLILogger`-factory definition
(matching the `get_s3_logger`/`get_database_logger`/`get_llm_logger` sibling pattern),
delete the plain-`logging.Logger` one, and wire the survivor into `__init__.py`.
**#197**: the four service-logger classes (`S3Logger`, `DatabaseLogger`, `LLMLogger`,
`CLILogger`) each re-implement the same "optional ` (suffix)` + `self.logger.<level>(msg,
extra={...})`" scaffolding; we introduce a shared private base with one `_emit` helper and
route every method through it **without changing any public class name, method name, or
signature**. Both fixes are provably safe because `shit_tests/shit/logging/` already pins
the exact message text and full `extra` dict for every method.

## Findings

### #196 — get_cli_logger double-def + broken __all__ export  (≡ #230 L12)

- **Location:**
  - `shit/logging/service_loggers.py:436` — `def get_cli_logger(module_name: Optional[str] = None) -> CLILogger:` → `return CLILogger(module_name)` (the wrapper factory).
  - `shit/logging/cli_logging.py:197` — `def get_cli_logger(module_name: str):` → `return logging.getLogger(module_name)` (a plain `logging.Logger`; **required** positional arg, no default).
  - `shit/logging/__init__.py:88` — `'get_cli_logger',` appears in `__all__`, but the name is **not** imported anywhere in `__init__.py`. The `service_loggers` import block (lines 31–40) pulls in `get_s3_logger`/`get_database_logger`/`get_llm_logger` but **omits** `get_cli_logger`; the `cli_logging` import block (lines 42–47) omits it too.

- **Problem:** Because `__all__` (line 88) references a name that is absent from the
  `shit.logging` namespace:
  - `from shit.logging import *` → `AttributeError: module 'shit.logging' has no attribute 'get_cli_logger'` (CPython validates every `__all__` entry during `import *`).
  - `from shit.logging import get_cli_logger` → `ImportError: cannot import name 'get_cli_logger' from 'shit.logging'`.
  - Separately, the same identifier means two different things depending on which sibling module you import it from — a latent trap even for callers who bypass the package root.

- **Verified against `main`:** All four line numbers are current (read 2026-07-24).
  Repo-wide `rg 'get_cli_logger'` shows **no production caller** of either definition —
  the only references are the two defs, the `__all__` string, two test modules (each
  testing its own sibling's version), and the session's `00_OVERVIEW.md`. The three
  sibling factories are the intended pattern and are wired correctly:
  `get_s3_logger`@`service_loggers.py:400` → `S3Logger`, `get_database_logger`@412 →
  `DatabaseLogger`, `get_llm_logger`@424 → `LLMLogger`, all imported at
  `__init__.py:37–39` and listed in `__all__` at lines 85–87.

- **Fix — keep the `service_loggers.py` (`CLILogger`) definition, delete the
  `cli_logging.py` (plain-Logger) one.** Rationale: (1) it completes the
  `get_<service>_logger → <Service>Logger` family; (2) it shares the sibling signature
  `module_name: Optional[str] = None` (the `cli_logging.py` version makes `module_name`
  mandatory); (3) the `cli_logging.py` version is a trivial one-line pass-through to
  `logging.getLogger` that adds no value over calling the stdlib directly. Then:
  1. Add `get_cli_logger` to the `service_loggers` import block in `__init__.py` (append after `get_llm_logger`, line ~39) so the `__all__` entry at line 88 becomes valid — **no** change to `__all__` itself is needed for this name.
  2. Delete `get_cli_logger` (lines 197–206) from `cli_logging.py`.
  3. Update `shit_tests/shit/logging/test_cli_logging.py`: remove `get_cli_logger` from its import (line 16) and delete the three tests that exercise the plain-Logger contract — `TestGetCLILogger.test_get_cli_logger` (378) and `TestGetCLILogger.test_get_cli_logger_without_module` (389) (the whole `TestGetCLILogger` class, lines 375–398), plus `TestCLILoggingEdgeCases.test_get_cli_logger_with_special_characters` (504–513).
  4. `shit_tests/shit/logging/test_service_loggers.py` needs **no** change: it already imports `get_cli_logger` from `shit.logging.service_loggers` (line 20) and its `test_get_cli_logger` (475–483) asserts `CLILogger` is constructed — i.e. it already tests the definition we keep.

### #197 — DRY four service-logger classes

- **Location:** `shit/logging/service_loggers.py:57–396`
  - `S3Logger` — lines 57–163
  - `DatabaseLogger` — lines 166–240
  - `LLMLogger` — lines 243–318
  - `CLILogger` — lines 321–396
  - **They do NOT currently share a base class** — each is a standalone `class X:` whose `__init__` independently calls `get_service_logger("<service>", module_name)` and stores `self.logger`. A base class must be **introduced**.

- **Problem:** Copy-pasted scaffolding repeated across every method: build a message, optionally append a ` (<suffix>)` when a value is present, then call `self.logger.<level>(msg, extra={'service': ..., 'operation': ..., <fields>, **kwargs})`. The five methods that carry the optional suffix are:
  - `S3Logger.uploaded` (82–99) — ` ({size})` when `if size:`
  - `S3Logger.downloaded` (115–132) — ` ({size})` when `if size:`
  - `DatabaseLogger.query_result` (191–208) — ` ({rows} rows)` when `rows is not None`
  - `LLMLogger.api_call_success` (268–285) — ` ({tokens} tokens)` when `tokens is not None`
  - `LLMLogger.analysis_complete` (301–318) — ` (confidence: {confidence:.1%})` when `confidence is not None`

  The remaining methods (starts/completions, `S3Logger.exists`'s conditional *prefix*, `CLILogger.progress`'s two-branch message) share the same `extra`-dict merge even though they carry no suffix.

- **Public API to preserve (every public method + exact signature — the refactor must
  not touch any of these; call sites and tests depend on them verbatim):**

  - `S3Logger`
    - `__init__(self, module_name: Optional[str] = None)`
    - `uploading(self, key: str, **kwargs)`
    - `uploaded(self, key: str, size: Optional[str] = None, **kwargs)`
    - `downloading(self, key: str, **kwargs)`
    - `downloaded(self, key: str, size: Optional[str] = None, **kwargs)`
    - `checking_exists(self, key: str, **kwargs)`
    - `exists(self, key: str, exists: bool, **kwargs)`
  - `DatabaseLogger`
    - `__init__(self, module_name: Optional[str] = None)`
    - `executing_query(self, query_type: str, **kwargs)`
    - `query_result(self, query_type: str, rows: Optional[int] = None, **kwargs)`
    - `inserting(self, table: str, count: int = 1, **kwargs)`
    - `inserted(self, table: str, count: int = 1, **kwargs)`
  - `LLMLogger`
    - `__init__(self, module_name: Optional[str] = None)`
    - `api_call_start(self, model: str, **kwargs)`
    - `api_call_success(self, model: str, tokens: Optional[int] = None, **kwargs)`
    - `analyzing(self, item: str, **kwargs)`
    - `analysis_complete(self, item: str, confidence: Optional[float] = None, **kwargs)`
  - `CLILogger`
    - `__init__(self, module_name: Optional[str] = None)`
    - `operation_start(self, operation: str, **kwargs)`
    - `operation_complete(self, operation: str, **kwargs)`
    - `operation_error(self, operation: str, error: str, **kwargs)`
    - `progress(self, current: int, total: Optional[int] = None, **kwargs)`
  - Module-level factories (unchanged): `get_service_logger`, `get_s3_logger`, `get_database_logger`, `get_llm_logger`, `get_cli_logger`.
  - **Also preserve the instance attribute `self.logger`** — `test_service_loggers.py` patches `s3_logger.logger`, `db_logger.logger`, etc., and asserts on `self.logger.<level>.assert_called_once()`.

- **Fix — introduce ONE private base class carrying a single `_emit` helper:**
  ```python
  class _BaseServiceLogger:
      def __init__(self, service: str, module_name: Optional[str] = None):
          self.service = service
          self.logger = get_service_logger(service, module_name)

      def _emit(self, level: str, msg: str, operation: str,
                suffix: Optional[str] = None, **fields) -> None:
          if suffix:
              msg = f"{msg} ({suffix})"
          getattr(self.logger, level)(
              msg,
              extra={'service': self.service, 'operation': operation, **fields},
          )
  ```
  Each of the four classes subclasses `_BaseServiceLogger`, calls
  `super().__init__("<service>", module_name)`, and rewrites each method as a one-line
  `self._emit(...)` call. **Behavior-preservation rules:**
  - The **caller** computes the suffix string using its own original condition and passes
    `suffix=None` when absent (e.g. `suffix=size if size else None`;
    `suffix=f"{rows} rows" if rows is not None else None`;
    `suffix=f"{tokens} tokens" if tokens is not None else None`;
    `suffix=f"confidence: {confidence:.1%}" if confidence is not None else None`). The
    helper only wraps ` ({suffix})` when truthy — so no trailing ` (...)` ever appears when
    absent, exactly as today.
  - The **raw field** is still passed through `**fields` (e.g. `size=size`, `rows=rows`,
    `tokens=tokens`, `confidence=confidence`) so the `extra` dict is byte-for-byte
    identical — including `'size': None` etc. when the value is absent (pinned by
    `test_uploaded_without_size`).
  - Non-suffix methods route through `_emit` with `suffix=None` and a pre-built message:
    `S3Logger.exists` passes the conditional-prefix message; `CLILogger.progress` passes
    its already-composed two-branch message. `CLILogger` methods pass
    `operation=<the user arg>` (or the literal `'progress'`) plus `status=...` as a field.
  - Keep the base class private (`_` prefix) and **out of `__all__`**; do not export it.

## Implementation Plan

> Land after / rebase on **Phase 1** — it edits the same `shit/logging/__init__.py` (see
> Notes / Dedup).

### Steps
1. **`service_loggers.py` — add base + refactor (#197).**
   - Add `_BaseServiceLogger` with `__init__(service, module_name=None)` and the `_emit` helper.
   - Change each class header to inherit `_BaseServiceLogger`; replace each `__init__` body with `super().__init__("<service>", module_name)` (`s3`/`database`/`llm`/`cli`).
   - Rewrite every method body to a single `self._emit(...)` call, moving the suffix computation into the caller per the rules above. Leave all method signatures and docstrings intact.
2. **`cli_logging.py` — delete the duplicate (#196).** Remove `get_cli_logger` (lines 197–206). Confirm no other symbol in the file references it (it does not).
3. **`__init__.py` — wire the survivor (#196).** Add `get_cli_logger` to the `.service_loggers` import block (append after `get_llm_logger`). The `__all__` entry at line 88 is now satisfied; leave it in place. **Do not** re-add or touch the `progress_tracker` lines — those are Phase 1's to remove; if Phase 1 has already landed they will be gone, and the final `__all__` must contain only importable names.
4. **Tests — #196.** In `test_cli_logging.py`: drop `get_cli_logger` from the import (line 16); delete the `TestGetCLILogger` class (375–398) and `TestCLILoggingEdgeCases.test_get_cli_logger_with_special_characters` (504–513). Leave `test_service_loggers.py` untouched.
5. **Tests — #197.** Run `pytest shit_tests/shit/logging/` — `test_service_loggers.py` (message text + `extra` + level, per method) must pass **unmodified**; it is the behavior harness.
6. **Import smoke test.** Add (or run ad hoc) a tiny test asserting `from shit.logging import *` succeeds and that `get_cli_logger` is importable from the package root and returns a `CLILogger`.
7. **Lint/format + CHANGELOG.** `ruff check .`, `ruff format .`, and add an `[Unreleased]` entry.

## Acceptance Criteria
- [ ] `from shit.logging import get_cli_logger` works AND `from shit.logging import *` does not raise.
- [ ] Only one `get_cli_logger` definition remains (in `service_loggers.py`, returning `CLILogger`).
- [ ] All four service loggers delegate to `_emit` on a shared base; every public method name and signature is unchanged, and `self.logger` still exists as an instance attribute.
- [ ] `pytest shit_tests/shit/logging/` green (`test_service_loggers.py` unmodified; `test_cli_logging.py` only loses the three plain-Logger `get_cli_logger` tests).
- [ ] `ruff check .` / `ruff format .` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` updated (closes #196 ≡ #230 L12, and #197).

## Test Plan
- **Existing harness (must stay green, unmodified):** `shit_tests/shit/logging/test_service_loggers.py` asserts, for every method, the exact message string — including the suffix forms `"...(1KB)"`, `"...(5 rows)"`, `"...(150 tokens)"`, `"...(confidence: 85.0%)"` and the *no-suffix* forms `"✅ Uploaded to S3: test-key"`, `"✅ Query completed: INSERT"`, `"✅ LLM API call completed: gpt-4"` — plus the full `extra` dict (`service`, `operation`, and each field, e.g. `extra['size'] is None` in `test_uploaded_without_size`) and the log level (`.info`/`.debug`/`.error`). Passing this harness after the refactor is the proof of behavior preservation.
- **Import smoke test (new, small):** assert `import shit.logging as L; exec("from shit.logging import *")` does not raise, and `from shit.logging import get_cli_logger; assert isinstance(get_cli_logger("x"), CLILogger)`.
- **Per-class spot check:** for one method per class (`S3Logger.uploaded`, `DatabaseLogger.query_result`, `LLMLogger.analysis_complete`, `CLILogger.progress`), confirm message text and `extra` dict are identical pre/post refactor (already covered by the harness).
- **Suite guard:** `pytest shit_tests/shit/logging/` and a full `pytest` run to confirm no importer elsewhere trips on the `__init__.py` change.

## Rollback
- `git revert` of the PR. Pure code refactor + export fix — no data, schema, or config impact; no runtime state to reconcile.

## Notes / Dedup
- **#196 ≡ #230 (L12)** — same fix filed in Wave A and Wave B; the closing PR references both, and #230 stays open until its other findings (owned by Phases 4/5) also land.
- **Cross-phase dependency (shared file `shit/logging/__init__.py`):** Phase 1 (`01_dead-code-deletions.md`, #194) removes the `progress_tracker` **import block** (`__init__.py:49–53`) and its `__all__` entries `'ProgressTracker'`/`'track_progress'`/`'simple_progress'` (`__init__.py:97–99`), and deletes `shit/logging/progress_tracker.py` (+ `test_progress_tracker.py`). Phase 3 edits the **same file** (adds the `get_cli_logger` import; the `__all__` entry already exists at line 88). **Land Phase 3 after / rebased on Phase 1** (per `00_OVERVIEW.md` §Dependencies) to avoid churn in the import section and `__all__`. **Post-both invariant:** `__all__` must contain only names actually importable from the package namespace — after Phase 1 removes the three progress names and Phase 3 wires in `get_cli_logger`, the list is internally consistent.
