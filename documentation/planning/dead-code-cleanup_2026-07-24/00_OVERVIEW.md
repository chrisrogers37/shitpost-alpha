# Cluster 7 — Dead-Code & Consistency Cleanup

**Session:** `dead-code-cleanup_2026-07-24`
**Status:** READY (plans authored, implementation not started)
**Owner:** chrisrogers37
**Driver:** Batched GitHub-issue remediation — momentum-first cluster chosen to clear dead code and resolve the Wave A/Wave B overlap before the P0/P1 correctness work.

---

## Context

Thirty open issues exist across three "waves":

- **Wave A — Auto-audit tech-debt** (#184–#197): dead code, magic strings, consistency drift. Labeled, mostly Medium/Low, mechanical.
- **Wave B — Full-system review** (#198–#231, from PR #165): a P0→P4 priority ladder with file:line refs, proposed fixes, and acceptance criteria. Upstream tracker docs live in PR #165 under `documentation/planning/tech-debt-2026-07-02/` (unmerged).
- **Wave C — Security audit** (#232–#233): newest (2026-07-23).

This cluster (Cluster 7) is the **low-risk, high-mechanical** slice: pure dead-code deletion, dead-parameter/config removal, logging cleanup, consistency fixes, and finishing the signals migration. It deliberately excludes the P0/P1 correctness and security clusters (see **Excluded Work** below).

---

## Critical dedup — work each finding ONCE

Wave A and Wave B overlap. These are the **same fix filed twice**; each is worked once and closes both:

| Wave A issue | Wave B finding | What |
|---|---|---|
| #189 | #229 (L11) | Dead `DatabaseUtils.transform_s3_data_to_shitpost` |
| #188 | #229 (L15) | Dead `use_signal` deprecated-ignored param |
| #196 | #230 (L12) | `get_cli_logger` double-def + broken `__all__` export |
| #192 | #220 (M8) | Dead resilience machinery (CircuitBreaker/RateLimiter/retry) |

Each phase doc that touches an overlapping finding notes the crosswalk so both issues are referenced in the closing PR.

---

## Phases (each = one PR, ordered safest-first)

| Phase | Doc | Issues | Code area | Risk |
|---|---|---|---|---|
| **1** | `01_dead-code-deletions.md` | #187, #189 (≡#229 L11), #192 (≡#220 M8), #194 | `shitvault`, `shit/db`, `shit/utils`, `shit/logging` | Very low |
| **2** | `02_dead-params-and-config.md` | #188 (≡#229 L15), #195 | `shitvault`, `shitpost_ai`, `shitposts`, `shit/config` | Low |
| **3** | `03_logging-module-cleanup.md` | #196 (≡#230 L12), #197 | `shit/logging` | Low |
| **4** | `04_consistency.md` | #190, #230 (L3, L4) | `shit/events`, `notifications`, `shit/market_data`, `railway.json` | Low |
| **5** | `05_structural-cleanup.md` | #191, #231 (L16, L18) | `shitvault`, `shit/db`, `api` | Low-medium |
| **6** | `06_finish-signals-migration.md` | #224 (M22–M24), #229 (L13, L14) | `shitvault`, `shit/content` | Medium |

**Ordering rationale:** Phases 1–3 are pure removals and mechanical refactors with no behavior change — fast, satisfying, ~1,000+ LOC deleted. Phase 4 is tz/consistency hygiene. Phase 5 mixes structural consolidation with two small correctness fixes (echo idempotency, bounded price cache). Phase 6 is the heaviest (stats now computed from the legacy table; a behavioral change) and is deliberately last and fully separable — the cluster delivers value even if Phase 6 is deferred to its own follow-up.

**Dependencies:** Phases are independent and could run in parallel worktrees, with two soft orderings — do Phase 1's `progress_tracker` deletion before Phase 3 touches `shit/logging/__init__.py`, and land Phase 2's `use_signal` removal before Phase 6 restandardizes `signal_id` call-sites — to avoid merge churn in the same files.

## Adjustments discovered during plan drafting (per-phase ref verification)

Each phase doc was verified against current `main` before being written. Material changes from the raw issues:

- **Phase 6 splits into two PRs.** #224 M23 (compute stats from `signals` instead of the frozen `truth_social_shitposts`) is the cluster's *only* behavioral change and directly contradicts the CHANGELOG's "Signals Migration Complete" line. It becomes **PR-6b** (stats change + a count-pinning test + CHANGELOG reconcile), split from **PR-6a** (M22 identity, M24 dead multi-source removal, L13, L14 — all non-behavioral).
- **#229 L13 premise is invalid.** The bypass matcher is *already* an exact whole-post match (not substring), and every `TEST_PHRASES` entry is shorter than `MIN_TEXT_LENGTH`, making the greeting check effectively unreachable. Reframed from "tighten" to **verify-and-lock with a regression test**.
- **#195 chooses honest config over resolution.** Recommendation is to **delete** the loaded-but-ignored `TRUTH_SOCIAL_USERNAME` and add explicit `SCRAPECREATORS_BASE_URL` + `TRUTH_SOCIAL_USER_ID` settings (username→id resolution would add machinery belonging to the #193/#211 dispatch cluster).
- **Test-tree paths corrected.** `events`/`content`/`notifications`/`api` tests are top-level under `shit_tests/`, not under `shit_tests/shit/`. Phase docs use the verified paths.
- **ruff cleanup is in-scope for deletions.** Phases 1–2 leave several imports unused after removals (`asyncio`, `wraps`, typing symbols, `json`) plus an orphaned `sample_s3_data` fixture and a dangling `*,` marker — each phase doc lists them so the PR passes `ruff check`.

---

## Full issue → phase crosswalk

- **Phase 1:** #187, #189, #192, #194 (closes #229 L11 portion, #220 M8 portion)
- **Phase 2:** #188, #195 (closes #229 L15 portion)
- **Phase 3:** #196, #197 (closes #230 L12 portion)
- **Phase 4:** #190, #230 (L3, L4)
- **Phase 5:** #191, #231 (L16, L18)
- **Phase 6:** #224, #229 (L13, L14)

> #229, #230, #231, #220 are multi-finding cluster issues; they stay open until every constituent finding across the phases is landed, then close.

---

## Excluded work (other clusters — NOT in this session)

- **P0 correctness** (#198–#202): broken alert path, analyzer loop, dual execution, event stale-claims, alert idempotency.
- **P1 DB/sessions** (#203–#208), **harvest/S3** (#209–#211), **API/frontend** (#212–#214), **LLM** (#217–#218), **notifications features** (#215–#216).
- **P2 clusters** (#219–#223, #225, #226) beyond the dead-code portions pulled forward here.
- **Security** (#232, #233) — the Telegram webhook secret (#227 L1 / #232) and API-key fail-open (#233) belong to the security cluster.
- **Frontend/API auto-audit** (#184, #185, #186) and **#193** (forked harvester dispatch) belong to their code-area clusters.

---

## Cluster acceptance criteria

- [ ] Every finding in the crosswalk is implemented, verified, and its issue closed (or, for multi-finding issues, its portion checked off).
- [ ] `pytest` green after each phase; `ruff check .` and `ruff format .` clean.
- [ ] Net LOC reduced (dead code removed, not relocated).
- [ ] Each phase PR updates `CHANGELOG.md` under `[Unreleased]`.
- [ ] No behavior change in Phases 1–4; Phase 5/6 behavior changes are covered by tests. **(Amended: Phase 4 (PR #238) includes one intended behavior fix — widening `is_briefing_time()` to stop the morning briefing going dark every winter (EST); the #230 L3 cron item turned out to hide a real bug rather than a doc tweak. Covered by tests.)**

---

## How to run

```
/claudna:implement-plan documentation/planning/dead-code-cleanup_2026-07-24/
```

Path C queues the selected phases; each runs through challenge → implement → verify → PR. Run `/compact` between phases.
