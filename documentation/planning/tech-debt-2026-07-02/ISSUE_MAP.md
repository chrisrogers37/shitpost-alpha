# Issue Map — 2026-07-02 System Review

Crosswalk from review finding IDs (see [`00_TECH_DEBT.md`](00_TECH_DEBT.md)) to the GitHub issues filed in `chrisrogers37/shitpost-alpha`.

**Filing policy** (per request): **P0 (CRITICAL)** and **P1 (HIGH)** findings are filed as **individual** issues; **P2 (MEDIUM)** and **P3/P4/nice-to-have (LOW)** findings are filed as **clustered** issues grouped by workstream/theme.

**Priority mapping:** P0 = CRITICAL · P1 = HIGH · P2 = MEDIUM · P3/P4/nice-to-have = LOW.

> Labeling note: the GitHub token available to the filing agent can create issues but **not** labels, so a dedicated `priority: critical` / `system-review` label could not be added. P0 and P1 both carry the existing `priority: high` label and are disambiguated by the `[P0]`/`[P1]` title prefix. P2 → `priority: medium`, P3/P4 → `priority: low`. Each issue body links back to its tracker file and finding ID.

---

## P0 — CRITICAL (individual)

| Finding | Issue | Title | Workstream |
|---------|-------|-------|-----------|
| C1 | [#198](https://github.com/chrisrogers37/shitpost-alpha/issues/198) | Production Telegram alerts sent with hardcoded neutral sentiment and empty thesis/text | 01 |
| C2 | [#199](https://github.com/chrisrogers37/shitpost-alpha/issues/199) | Analyzer range-mode can infinite-loop when unprocessed posts are newer than the range | 03 |
| C3 | [#200](https://github.com/chrisrogers37/shitpost-alpha/issues/200) | Dual execution model can double-process and double-spend LLM | 02 |
| C4 | [#201](https://github.com/chrisrogers37/shitpost-alpha/issues/201) | Event queue has no stale-claim recovery; worker crash orphans claimed events | 04 |
| C5 | [#202](https://github.com/chrisrogers37/shitpost-alpha/issues/202) | No alert-delivery idempotency; retries/overlapping cron can re-send predictions | 01 |

## P1 — HIGH (individual)

| Finding | Issue | Title | Workstream |
|---------|-------|-------|-----------|
| H1 | [#203](https://github.com/chrisrogers37/shitpost-alpha/issues/203) | Dual DB session mechanisms create pool pressure and nested-session bugs | 05 |
| H2 | [#204](https://github.com/chrisrogers37/shitpost-alpha/issues/204) | get_session() misused as async context manager; unreliable cleanup | 05 |
| H3 | [#205](https://github.com/chrisrogers37/shitpost-alpha/issues/205) | create_all() runs on every async DB init (schema-drift/migration race) | 05 |
| H4 | [#206](https://github.com/chrisrogers37/shitpost-alpha/issues/206) | No session.rollback() on prediction write failure poisons the batch | 06 |
| H5 | [#207](https://github.com/chrisrogers37/shitpost-alpha/issues/207) | Failed LLM analysis leaves no DB footprint; signal retried forever | 06 |
| H6 | [#208](https://github.com/chrisrogers37/shitpost-alpha/issues/208) | check_prediction_exists fails open on DB error (duplicate analysis) | 06 |
| H7 | [#209](https://github.com/chrisrogers37/shitpost-alpha/issues/209) | Incremental S3 processing reprocesses everything when last signal_id absent | 09 |
| H8 | [#210](https://github.com/chrisrogers37/shitpost-alpha/issues/210) | list_raw_data() ignores end_date; range mode loads out-of-window files | 09 |
| H9 | [#211](https://github.com/chrisrogers37/shitpost-alpha/issues/211) | --max-id and --source CLI args are dead | 12 |
| H10 | [#212](https://github.com/chrisrogers37/shitpost-alpha/issues/212) | API is fully open when API_KEY is unset | 07 |
| H11 | [#213](https://github.com/chrisrogers37/shitpost-alpha/issues/213) | COUNT(*) OVER() on every feed request scans the full filtered set | 07 |
| H12 | [#214](https://github.com/chrisrogers37/shitpost-alpha/issues/214) | PriceKPIs violates the Rules of Hooks (early return before hooks) | 08 |
| H13 | [#215](https://github.com/chrisrogers37/shitpost-alpha/issues/215) | Vote maturation is never scheduled; /mystats, /leaderboard never work | 01 |
| H14 | [#216](https://github.com/chrisrogers37/shitpost-alpha/issues/216) | Re-subscribe via /start never resets consecutive_errors | 01 |
| H15 | [#217](https://github.com/chrisrogers37/shitpost-alpha/issues/217) | analyze_ensemble() silently drops prompt_func/kwargs | 11 |
| H16 | [#218](https://github.com/chrisrogers37/shitpost-alpha/issues/218) | Manual JSON fallback fabricates junk predictions on parse failure | 11 |

## P2 — MEDIUM (clustered)

| Issue | Title | Findings | Workstream |
|-------|-------|----------|-----------|
| [#219](https://github.com/chrisrogers37/shitpost-alpha/issues/219) | Market data / outcome calculator: correctness fixes + decomposition | M1, M2, M3, M4, M5 | 10 |
| [#220](https://github.com/chrisrogers37/shitpost-alpha/issues/220) | LLM robustness: prompt-injection, rate limiting, dead resilience utils | M6, M7, M8 | 11 |
| [#221](https://github.com/chrisrogers37/shitpost-alpha/issues/221) | Event system reliability & targeting | M9, M10, M11, M12 | 04/02/03 |
| [#222](https://github.com/chrisrogers37/shitpost-alpha/issues/222) | API performance & security hardening | M13, M14, M15, M16, M17, M29 | 07 |
| [#223](https://github.com/chrisrogers37/shitpost-alpha/issues/223) | Notifications correctness & structure | M18, M19, M20, M21, M30, M31 | 01/13 |
| [#224](https://github.com/chrisrogers37/shitpost-alpha/issues/224) | Finish signals migration & remove multi-source dead code | M22, M23, M24 | 12 |
| [#225](https://github.com/chrisrogers37/shitpost-alpha/issues/225) | Harvest/S3 correctness: fake-async boto3 + naive-UTC timestamps | M25, M26 | 09 |
| [#226](https://github.com/chrisrogers37/shitpost-alpha/issues/226) | Config validation & environment/bucket single-source-of-truth | M27, M28 | 14 |

## P3 / P4 / nice-to-have — LOW (clustered)

| Issue | Title | Findings | Workstream |
|-------|-------|----------|-----------|
| [#227](https://github.com/chrisrogers37/shitpost-alpha/issues/227) | [P3] Notifications low-severity bugs & security | L1, L2, L17, L19 | 01/13 |
| [#228](https://github.com/chrisrogers37/shitpost-alpha/issues/228) | [P3] Frontend robustness | L5, L6, L7, L8, L9, L10 | 08 |
| [#229](https://github.com/chrisrogers37/shitpost-alpha/issues/229) | [P4] Migration & legacy dead-code cleanup | L11, L13, L14, L15 | 12 |
| [#230](https://github.com/chrisrogers37/shitpost-alpha/issues/230) | [P4] Config/logging/consistency cleanup | L3, L4, L12 | 14 |
| [#231](https://github.com/chrisrogers37/shitpost-alpha/issues/231) | [P4] API/web cleanup + echo embed idempotency | L16, L18 | 06/07 |

---

## Coverage check

- **P0/CRITICAL:** C1–C5 → 5 individual issues (#198–#202). ✅ complete
- **P1/HIGH:** H1–H16 → 16 individual issues (#203–#218). ✅ complete
- **P2/MEDIUM:** M1–M31 → 8 clustered issues (#219–#226). ✅ complete
- **P3/P4/LOW:** L1–L19 → 5 clustered issues (#227–#231). ✅ complete

**Total: 34 GitHub issues (#198–#231)** covering all 71 findings in the review.
