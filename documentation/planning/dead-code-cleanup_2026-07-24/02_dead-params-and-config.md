---
title: "Phase 2 — Dead params & config"
session: dead-code-cleanup_2026-07-24
status: COMPLETE
started: 2026-07-28
completed: 2026-07-28
pr: 235
issues: [188, 195]
code_area: shitvault, shitpost_ai, shitposts, shit/config
risk: low
---

# Phase 2 — Dead params & config

## Summary
Two independent no-behavior-change cleanups. **#188** removes the keyword-only
`use_signal` param — documented "Deprecated, ignored" — from three
`PredictionOperations` methods, their three analyzer call-sites, and one test
assertion; it is a pure backwards-compat shim (the code always stores/checks
`signal_id`). **#195** hoists the Truth Social harvester's hardcoded identity
(`base_url`, numeric account `user_id`) into `shit/config/shitpost_settings.py`
and deletes the genuinely-dead `TRUTH_SOCIAL_USERNAME` setting (assigned to
`self.username` but never read anywhere), so config reflects what actually
selects the account. Both are low-risk and were verified line-by-line against
`main` — every referenced line number is CONFIRMED with no drift.

## Findings

### #188 — Remove use_signal deprecated-ignored param  (≡ #229 L15)

- **Location** (all sites, verified against `main`):
  - Param declarations + docstrings in `shitvault/prediction_operations.py`:
    - `store_analysis` — param `use_signal: bool = True,` at **:49** (after bare `*,` at :48); docstring line at **:57**
    - `handle_no_text_prediction` — param at **:157** (after bare `*,` at :156); docstring line at **:167**
    - `check_prediction_exists` — param at **:226** (after `*,` at :225, which is *also* followed by `llm_provider`/`llm_model` at :227–:228); docstring line at **:238**
  - Call-sites in `shitpost_ai/shitpost_analyzer.py`:
    - `check_prediction_exists(shitpost_id, use_signal=True)` at **:394**
    - `handle_no_text_prediction(shitpost_id, shitpost, bypass_reason, use_signal=True)` at **:478** (call spans :477–:479)
    - `store_analysis(shitpost_id, enhanced_analysis, shitpost, use_signal=True)` at **:565** (call spans :564–:566)
  - Test assertion in `shit_tests/shitpost_ai/test_shitpost_analyzer.py`:
    - `mock_check.assert_called_once_with(sample_shitpost_data['shitpost_id'], use_signal=True)` at **:352**
- **Problem:** `use_signal` is a pure no-op shim from the signals migration (PR #140). Every method body unconditionally writes/queries `Prediction.signal_id` regardless of the flag; the docstrings literally read "Deprecated, ignored. Always stores/checks as signal_id." Removing it changes no behavior.
- **Verified against `main`:** all ten Python sites CONFIRMED at the exact lines above (issue estimates of ~49/~157/~226, ~394/~478/~565, and :352 all match — **no drift**).
- **Fix:** Delete the three `use_signal` params + their three docstring lines, delete the three `use_signal=True` arguments at the call-sites, and drop `use_signal=True` from the one test assertion. Cut cleanly — no alias, no deprecation cycle.
  - **Critical syntax nuance:** in `store_analysis` and `handle_no_text_prediction`, `use_signal` is the *only* keyword-only param, so its `*,` marker (lines :48 and :156) becomes a dangling bare `*,` with nothing after it — a `SyntaxError`. **Delete the `*,` line too** in those two methods. In `check_prediction_exists`, **keep** the `*,` at :225 because `llm_provider`/`llm_model` remain keyword-only.
- **No other callers:** `rg` over source+tests shows the only production callers are the three analyzer sites above. The many `store_analysis(...)` / `handle_no_text_prediction(...)` / `check_prediction_exists(...)` calls in `shit_tests/shitvault/test_prediction_operations.py` do **not** pass `use_signal` (grep-confirmed), so they are unaffected by the removal.

**Grep evidence — every `use_signal` occurrence in the repo (22 total across 8 files):**

| Kind | Location | Action |
|------|----------|--------|
| param | `shitvault/prediction_operations.py:49` | delete (+ `*,` at :48) |
| docstring | `shitvault/prediction_operations.py:57` | delete |
| param | `shitvault/prediction_operations.py:157` | delete (+ `*,` at :156) |
| docstring | `shitvault/prediction_operations.py:167` | delete |
| param | `shitvault/prediction_operations.py:226` | delete (keep `*,` at :225) |
| docstring | `shitvault/prediction_operations.py:238` | delete |
| call-site | `shitpost_ai/shitpost_analyzer.py:394` | drop `use_signal=True` |
| call-site | `shitpost_ai/shitpost_analyzer.py:478` | drop `use_signal=True` |
| call-site | `shitpost_ai/shitpost_analyzer.py:565` | drop `use_signal=True` |
| test | `shit_tests/shitpost_ai/test_shitpost_analyzer.py:352` | drop `use_signal=True` |
| doc (historical) | `CHANGELOG.md:598` | **leave** (append-only history) |
| doc (historical) | `docs/superpowers/specs/2026-04-14-signals-migration-and-scraping-design.md:93` | leave |
| doc (historical) | `docs/superpowers/plans/2026-04-14-signals-migration.md:383,389,396,400` | leave |
| doc (archive) | `documentation/archive/system-evolution_2026-02-11/02_source-agnostic-data-model.md:635,651,652,959` | leave |
| doc (this session) | `documentation/planning/dead-code-cleanup_2026-07-24/00_OVERVIEW.md:29,50` | leave |

→ **10 Python-code occurrences** to change; **12 doc/changelog occurrences** are historical/planning record and are intentionally retained.

### #195 — Hoist hardcoded Truth Social identity to settings

- **Location** (verified against `main`):
  - `shitposts/truth_social_s3_harvester.py` `__init__`:
    - `self.username = settings.TRUTH_SOCIAL_USERNAME` at **:41**  ← dead (assigned, never read)
    - `self.api_key = settings.SCRAPECREATORS_API_KEY` at **:43** (already from settings; leave)
    - `self.base_url = "https://api.scrapecreators.com/v1"` at **:44**  ← hardcoded literal
    - `self.user_id = "107780257626128497"  # Trump's Truth Social user ID` at **:45**  ← hardcoded literal
  - Interpolation sites (must keep working after the hoist):
    - `url = f"{self.base_url}/truthsocial/user/posts?user_id={self.user_id}&limit=1"` at **:73** (`_test_connection`)
    - `url = f"{self.base_url}/truthsocial/user/posts"` at **:95** and `params = {'user_id': self.user_id, 'limit': 20}` at **:96** (`_fetch_batch`)
  - The setting: `TRUTH_SOCIAL_USERNAME: str = Field(default="realDonaldTrump")` at `shit/config/shitpost_settings.py:**53**`
- **Problem:** The ScrapeCreators API selects the account purely by numeric `user_id` (plus the base URL host). Those two values are hardcoded string literals in `__init__`. Meanwhile `TRUTH_SOCIAL_USERNAME` is loaded from settings into `self.username` and then **never read by any code path** — config advertises a knob that does nothing, and the real selector is invisible to config.
- **Verified against `main`:**
  - Line numbers :41/:43/:44/:45/:73/:95/:96 and settings :53 all CONFIRMED — **no drift** (issue estimates ~41/~44/~45/~73/~95–96/:53 match).
  - `self.username` **unused CONFIRMED**: `rg '\.username\b'` (source only) shows the harvester's sole occurrence is the :41 assignment; all other `.username` hits are unrelated classes (`notifications/models.py`, `shitvault/shitpost_models.py` `TruthSocialShitpost.__repr__`, `shitvault/migrate_to_signals.py`, frontend `.tsx`). `shitposts/base_harvester.py` references none of `username`/`user_id`/`base_url`, so the base class never reads it either.
  - `self.user_id` **is** read externally by a test: `shit_tests/shitposts/test_truth_social_s3_harvester.py:84` asserts `harvester.user_id == "107780257626128497"` — so `self.user_id` must remain an instance attribute (now sourced from settings).
- **Fix — recommended option: DELETE `TRUTH_SOCIAL_USERNAME`; add two honest settings.** In `shit/config/shitpost_settings.py`:
  ```python
  # ScrapeCreators API Configuration
  SCRAPECREATORS_API_KEY: Optional[str] = Field(default=None)
  SCRAPECREATORS_BASE_URL: str = Field(default="https://api.scrapecreators.com/v1")
  TRUTH_SOCIAL_USER_ID: str = Field(default="107780257626128497")  # Trump's Truth Social account id
  ```
  Remove the `TRUTH_SOCIAL_USERNAME` field (:53). In the harvester `__init__`, drop the `self.username` line and read from settings:
  ```python
  self.base_url = settings.SCRAPECREATORS_BASE_URL
  self.user_id = settings.TRUTH_SOCIAL_USER_ID
  ```
  The `:73` / `:95–:96` interpolation sites are unchanged (they read `self.base_url` / `self.user_id`, now settings-backed).
- **Rationale (recommended vs. alternative):** The API is driven by `user_id`, so config should expose `user_id` — that is the "honest config" outcome with **zero new machinery**. The alternative — keep `TRUTH_SOCIAL_USERNAME` and *resolve* the id from it — requires either a hardcoded `{username: user_id}` map (relocates the same literal, throws for any other handle) or a live ScrapeCreators lookup (network dependency + new failure mode in init). Both add machinery, and username→account resolution logically belongs to the multi-source dispatch work (#193/#211), which this phase must not touch. Keeping `TRUTH_SOCIAL_USERNAME` as a "documentation-only" field is rejected outright — that *is* the loaded-but-ignored anti-pattern this cleanup exists to remove. Leaving a dead setting in a dead-code-cleanup PR would be self-defeating. → **Delete it.**
  - Safety of deletion: `pydantic-settings` `BaseSettings` ignores undeclared env vars (production already runs with many env vars not present in this model), so a stale `TRUTH_SOCIAL_USERNAME=...` in a developer's `.env` is inert after removal. Update the README docs that mention it (`shit/README.md:226`, `shitposts/README.md:111`).
- **Scope guard:** config hoisting only. Do **not** touch harvester source-dispatch / `--source` / registry logic — that is issue **#193/#211**, a separate cluster. No changes to `ENABLED_HARVESTERS`, `base_harvester.py`, or the registry in this PR.

## Implementation Plan

### Steps

1. **`shitvault/prediction_operations.py`** — `store_analysis` (:43–:50): delete the `*,` line (:48) and the `use_signal: bool = True,` line (:49); delete the docstring line at :57. Resulting signature: `(self, content_id, analysis_data, content_data=None) -> Optional[str]`.
2. **`shitvault/prediction_operations.py`** — `handle_no_text_prediction` (:151–:158): delete the `*,` line (:156) and the `use_signal` line (:157); delete the docstring line at :167. Resulting signature: `(self, content_id, content_data, bypass_reason=None) -> Optional[str]`.
3. **`shitvault/prediction_operations.py`** — `check_prediction_exists` (:222–:229): delete only the `use_signal` line (:226) and the docstring line at :238; **keep** the `*,` (:225) so `llm_provider`/`llm_model` stay keyword-only.
4. **`shitpost_ai/shitpost_analyzer.py`** — remove `use_signal=True` from the three calls: `:394` → `check_prediction_exists(shitpost_id)`; `:478` → `handle_no_text_prediction(shitpost_id, shitpost, bypass_reason)`; `:565` → `store_analysis(shitpost_id, enhanced_analysis, shitpost)`.
5. **`shit_tests/shitpost_ai/test_shitpost_analyzer.py:352`** — change the assertion to `mock_check.assert_called_once_with(sample_shitpost_data['shitpost_id'])`.
6. Re-grep: `rg use_signal -g '*.py'` must return **zero** matches (only historical docs/CHANGELOG remain).
7. **`shit/config/shitpost_settings.py`** — add `SCRAPECREATORS_BASE_URL` and `TRUTH_SOCIAL_USER_ID` fields (next to `SCRAPECREATORS_API_KEY`, ~:104); delete the `TRUTH_SOCIAL_USERNAME` field (:53).
8. **`shitposts/truth_social_s3_harvester.py`** `__init__` (:40–:45) — delete `self.username = ...` (:41); set `self.base_url = settings.SCRAPECREATORS_BASE_URL` and `self.user_id = settings.TRUTH_SOCIAL_USER_ID`. Leave the :73 / :95–:96 interpolation sites untouched.
9. **Harvester test fixtures** — because these tests patch `settings` with a `MagicMock`, add the two new fields wherever the mock is built so the harvester reads real strings (not `MagicMock` attrs):
   - `shit_tests/shitposts/test_truth_social_s3_harvester.py` — every `mock_settings.TRUTH_SOCIAL_USERNAME = ...` block (:49, :68, :89, :116, :139, :147, :600, :655): replace/augment with `mock_settings.SCRAPECREATORS_BASE_URL = "https://api.scrapecreators.com/v1"` and `mock_settings.TRUTH_SOCIAL_USER_ID = "107780257626128497"`. Remove the now-invalid `assert harvester.username == "realDonaldTrump"` at **:83** (attribute deleted); keep `assert harvester.user_id == "107780257626128497"` at :84.
   - `shit_tests/shitposts/test_harvester_registry.py` (:180, :187, :195) — same mock field swap.
   - `shit_tests/conftest.py` — shared `mock_settings` fixture (:184) swap `TRUTH_SOCIAL_USERNAME` for the two new fields; env-setup/cleanup block (:546, :556) drop `TRUTH_SOCIAL_USERNAME` (optionally add `TRUTH_SOCIAL_USER_ID`).
10. **`shit_tests/shit/config/test_shitpost_settings.py`** — repoint the `TRUTH_SOCIAL_USERNAME` assertions to `TRUTH_SOCIAL_USER_ID` (mechanical: `hasattr` :31, `isinstance` :53/:639, env-override dict :73 + assert :101, default value :416, unicode :559/:563, not-None :594). Add a default-value assertion for `SCRAPECREATORS_BASE_URL` / `TRUTH_SOCIAL_USER_ID` if the file has a "defaults" test.
11. **Docs** — remove `TRUTH_SOCIAL_USERNAME` from `shit/README.md:226` and `shitposts/README.md:111`; note the two new env vars. (No `.env.example` file exists in the repo.)
12. **`CHANGELOG.md`** `[Unreleased]` — add `### Removed` (use_signal param; TRUTH_SOCIAL_USERNAME setting) and `### Changed` (harvester base URL + user id now settings-driven) entries. Note new env vars `SCRAPECREATORS_BASE_URL`, `TRUTH_SOCIAL_USER_ID`.
13. `ruff check .` / `ruff format .`; run the targeted test suites.

## Acceptance Criteria
- [x] No `use_signal` token remains in any `.py` file (`rg use_signal -g '*.py'` is empty); remaining matches are only historical CHANGELOG/spec/plan/archive/overview docs, intentionally retained.
- [x] `store_analysis` / `handle_no_text_prediction` no longer have a dangling `*,`; `check_prediction_exists` keeps `*,` for `llm_provider`/`llm_model`. Module imports without `SyntaxError`.
- [x] Harvester reads `base_url` + user id from settings (`settings.SCRAPECREATORS_BASE_URL`, `settings.TRUTH_SOCIAL_USER_ID`); `self.username` is gone and `TRUTH_SOCIAL_USERNAME` is removed from `shit/config/shitpost_settings.py`.
- [x] `rg 'self\.username' shitposts/` and `rg TRUTH_SOCIAL_USERNAME -g '*.py'` are both empty.
- [x] `source venv/bin/activate && pytest shit_tests/shitpost_ai/ shit_tests/shitvault/ shit_tests/shitposts/ shit_tests/shit/config/` green — **503 passed**.
- [x] Lint-neutral: `ruff check` on the 9 touched files shows the **same 53 pre-existing errors on this branch as on `main`** (no new findings). Repo-wide `ruff format .` was deliberately NOT run — it would reformat ~1,300 lines of pre-existing quote-style drift across the test tree; formatting was kept to the touched lines to avoid unrelated churn.
- [x] `CHANGELOG.md` `[Unreleased]` updated (Removed + Changed; new env-var names noted).

## Test Plan
- **#188:** run `shit_tests/shitpost_ai/test_shitpost_analyzer.py` (the :352 assertion is the only test that references `use_signal`) and `shit_tests/shitvault/test_prediction_operations.py` (confirms the three methods still behave — those tests never passed `use_signal`, so they should pass unchanged once the signatures drop the param).
- **#195:** run `shit_tests/shitposts/test_truth_social_s3_harvester.py` (esp. `test_initialization_defaults`, now asserting `user_id` from settings; the `username` assertion at :83 is removed), `shit_tests/shitposts/test_harvester_registry.py`, and `shit_tests/shit/config/test_shitpost_settings.py` (repointed `TRUTH_SOCIAL_USERNAME` → `TRUTH_SOCIAL_USER_ID`).
- **Mock caveat:** these harvester tests patch `settings` as a `MagicMock`; the two new settings fields MUST be set on the mock (step 9) or the harvester will interpolate `MagicMock` reprs into the request URL. No test currently asserts on the full URL string (grep-confirmed), so only value-equality assertions (`user_id`) are at risk — but set the fields regardless for correctness.
- **Config defaults:** both new fields have defaults, so no required `.env` change; document the env-var names in the READMEs (no `.env.example` exists). Full sweep before PR: `source venv/bin/activate && pytest`.

## Rollback
- `git revert` of the PR restores both the `use_signal` shim and the hardcoded harvester identity — no data or schema involved, so revert is complete and safe.
- **#195 introduces two new settings env-var names** — `SCRAPECREATORS_BASE_URL` and `TRUTH_SOCIAL_USER_ID` — and removes `TRUTH_SOCIAL_USERNAME`. A revert re-adds `TRUTH_SOCIAL_USERNAME` and drops the two new fields; any deploy env that had set the new vars can leave them (ignored after revert).

## Notes / Dedup
- **#188 ≡ #229 (L15)** — the same dead `use_signal` param is catalogued by Wave B finding #229 line 15. Reference **both** issue numbers in the PR title/body so both close together.
- **#195** is config-hoisting only. Source-dispatch / `--source` / registry changes are out of scope here and tracked separately under **#193/#211**.
