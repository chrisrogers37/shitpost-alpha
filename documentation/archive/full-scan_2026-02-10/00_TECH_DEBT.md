# Tech Debt Inventory — Full Scan 2026-02-10

**Scan Date**: 2026-02-10
**Scanned By**: Claude Code (automated + manual deep review)
**Codebase Version**: v0.18.0+ (commit `bfddb75` on `main`)

---

## Executive Summary

This scan identified **20 findings** across the Shitpost Alpha codebase:
- **6 HIGH** severity (security vulnerabilities, missing initialization, zero test coverage on critical paths)
- **10 MEDIUM** severity (code duplication, bare exceptions, architectural misalignment)
- **4 LOW** severity (style inconsistencies, dead code patterns)

**Estimated Total Effort**: 8-12 engineering days across 7 remediation plans

---

## Severity Definitions

| Level | Meaning | SLA |
|-------|---------|-----|
| **HIGH** | Security vulnerability, data loss risk, or production crash path | Fix within 1 sprint |
| **MEDIUM** | Maintainability drag, code smell, or reliability concern | Fix within 2 sprints |
| **LOW** | Style issue, minor duplication, or cosmetic inconsistency | Fix opportunistically |

---

## Master Finding Index

| # | Severity | Category | Finding | File(s) | Plan |
|---|----------|----------|---------|---------|------|
| 1 | **HIGH** | Security | SQL injection in `update_subscription()` | `notifications/db.py:177-180` | [01](./01_security-hardening.md) |
| 2 | **HIGH** | Security | HTML injection in email alerts | `notifications/dispatcher.py:400-427` | [01](./01_security-hardening.md) |
| 3 | **HIGH** | Architecture | `ShitpostAnalyzer.initialize()` never sets `db_ops`, `shitpost_ops`, `prediction_ops` | `shitpost_ai/shitpost_analyzer.py:38-40,63-79` | [05](./05_architecture-fixes.md) |
| 4 | **HIGH** | Testing | Zero test coverage on `outcome_calculator.py` (production critical) | `shit/market_data/outcome_calculator.py` | [02](./02_critical-test-coverage.md) |
| 5 | **HIGH** | Testing | Zero test coverage on `market_data/client.py` (production critical) | `shit/market_data/client.py` | [02](./02_critical-test-coverage.md) |
| 6 | **HIGH** | Testing | Zero test coverage on `sync_session.py` (used by all sync DB access) | `shit/db/sync_session.py` | [02](./02_critical-test-coverage.md) |
| 7 | **MEDIUM** | Security | Bare `except:` clauses swallow all errors | `shit/llm/llm_client.py:207`, `shit/s3/s3_models.py:77,88`, `shit/market_data/cli.py:99` | [01](./01_security-hardening.md) |
| 8 | **MEDIUM** | Security | Database URL printed to stdout at import time | `shitty_ui/data.py:65,88` | [01](./01_security-hardening.md) |
| 9 | **MEDIUM** | Architecture | Sync Anthropic client used in async context | `shit/llm/llm_client.py:44-45,156-169` | [05](./05_architecture-fixes.md) |
| 10 | **MEDIUM** | Architecture | `sys.path.insert(0, ...)` hack in dashboard data layer | `shitty_ui/data.py:59` | [05](./05_architecture-fixes.md) |
| 11 | **MEDIUM** | Architecture | Three separate database connection pools | `shitty_ui/data.py:78-118`, `shit/db/sync_session.py:14-32`, `shit/db/database_client.py` | [03](./03_database-session-consolidation.md) |
| 12 | **MEDIUM** | Duplication | Three near-identical subprocess execution functions | `shitpost_alpha.py:20-68,71-119,122-172` | [04](./04_code-deduplication.md) |
| 13 | **MEDIUM** | Duplication | `get_new_predictions_since()` duplicated across modules | `notifications/db.py:275`, `shitty_ui/data.py:1701` | [04](./04_code-deduplication.md) |
| 14 | **MEDIUM** | Duplication | `dict(zip(columns, row))` pattern repeated ~10 times | `notifications/db.py` (throughout) | [04](./04_code-deduplication.md) |
| 15 | **MEDIUM** | Architecture | Error handling inconsistency (print vs logger vs handle_exceptions) | Multiple files | [05](./05_architecture-fixes.md) |
| 16 | **MEDIUM** | Maintainability | `shitty_ui/layout.py` is 5,066 lines (god file) | `shitty_ui/layout.py` | [06](./06_layout-decomposition.md) |
| 17 | **LOW** | Duplication | CLI argument parsing duplicated in dry-run path | `shitpost_alpha.py:259-311` | [04](./04_code-deduplication.md) |
| 18 | **LOW** | Architecture | Private module imports at function level (inconsistent) | Multiple files | [05](./05_architecture-fixes.md) |
| 19 | **LOW** | Logging | 6 of 8 logging migration phases still pending | See `LOGGING_MIGRATION_PLAN.md` | [07](./07_logging-migration.md) |
| 20 | **LOW** | Architecture | `notifications/db.py` uses raw SQL everywhere instead of ORM | `notifications/db.py` (all functions) | [03](./03_database-session-consolidation.md) |

---

## Dependency Matrix

Remediation plans should be executed in this order:

```
01_security-hardening  ──┐
                         ├──→ 04_code-deduplication ──→ 06_layout-decomposition
02_critical-test-coverage┤
                         ├──→ 05_architecture-fixes
03_database-session-consolidation
                               07_logging-migration (independent, can run anytime)
```

**Key dependencies**:
- Plan 03 (session consolidation) should be done **before** Plan 04 (deduplication), because deduplicating `get_new_predictions_since` requires knowing which session provider to use
- Plan 01 (security) and 02 (tests) have **no dependencies** and can start immediately
- Plan 06 (layout decomposition) is best done **last** as it's the largest refactor
- Plan 07 (logging migration) is **fully independent** and can be done in parallel with anything

---

## Remediation Plan Index

| Plan | Title | Findings | Effort | Risk | Status |
|------|-------|----------|--------|------|--------|
| [01](./01_security-hardening.md) | Security Hardening | #1, #2, #7, #8 | 1-2 days | Medium | ✅ COMPLETE (PR #42) |
| [02](./02_critical-test-coverage.md) | Critical Test Coverage | #4, #5, #6 | 2-3 days | Low | ✅ COMPLETE (PR #43) |
| [03](./03_database-session-consolidation.md) | Database Session Consolidation | #11, #20 | 1-2 days | High | ✅ COMPLETE (PR #44) |
| [04](./04_code-deduplication.md) | Code Deduplication | #12, #13, #14, #17 | 1-2 days | Low | ✅ COMPLETE (PR #45) |
| [05](./05_architecture-fixes.md) | Architecture Fixes | #3, #9, #10, #15, #18 | 1-2 days | Medium | ✅ COMPLETE (PR #46) |
| [06](./06_layout-decomposition.md) | Layout Decomposition | #16 | 2-3 days | High | ✅ COMPLETE (PR #47) |
| [07](./07_logging-migration.md) | Logging Migration | #19 | 1-2 days | Low | ✅ COMPLETE (PR #48) |

---

## What NOT To Do

1. **Do NOT attempt to fix all findings in a single PR.** Each plan is scoped to be one PR.
2. **Do NOT change database schema** as part of any tech debt fix. Schema changes require separate migration planning.
3. **Do NOT refactor and add features simultaneously.** Tech debt PRs should be pure refactors with zero behavior change.
4. **Do NOT skip the verification checklist** in each plan. Every plan has a "How to verify" section — run it.
5. **Do NOT reorder the dependency chain** unless you understand why the dependencies exist (see matrix above).
