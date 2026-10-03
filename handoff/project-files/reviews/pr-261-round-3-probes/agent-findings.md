# PR #261 "Engine PR 4: extraction and similarity": review round 3 (combined review and verify)

**Reviewed:** 4554d3d..178bbab, plus a check of the whole PR.

- **B2:**
  - cdd6411: freeze v1 on gpt-4.1 + Haiku 4.5, both must agree.
  - eb48824: changelog.
  - a784773: freeze by hash; prices and the reason line moved outside it.
- **Builder:** 57257a8, the round-2 fold-in.
- **Merge:** 178bbab.

**Earlier rounds:** [round 1](pr-261-round-1.md), [round 2](pr-261-round-2.md).

**Probes and raw output:** `review-261-r3/` next to this file.

## Result

**No blocker, 1 should-fix, 6 nits and 2 questions.**

- Every round-2 should-fix is fixed, or declined with a reason that holds.
- The new lease, the freeze and the length-sorted batching all hold up under probes and mutation.
- The should-fix is the remaining half of round 2's S7: v1's files are frozen, but no test pins the request the code builds from them.

## Command results (at 178bbab, in `$SP/r3-261-wt`)

| Check | Result |
| --- | --- |
| `ruff check .` | clean (exit 0) |
| `ruff format --check .` | 90 files already formatted (exit 0) |
| `mypy` (strict) | no issues in 85 source files |
| `alembic heads` | `0004 (head)`, one head |
| `pytest`, run 1 | 463 passed in 203.94 s, no skips (model files present) |
| `pytest`, run 2 | 463 passed in 187.22 s |
| `pytest` as the `engine` role | 463 passed in 185.43 s |
| PR 1's `tests/test_lease.py` and `tests/test_runtime.py` alone | 30 passed in 38.32 s. Both files are unchanged since 4554d3d. |
| SQL from the default `Lease` (take, renew, release) | identical at 4554d3d and 178bbab: same INSERT ... ON CONFLICT, same DELETE, same `'10000ms'` timeouts for ttl 30 / renew 10. See `lease_sql_*.txt`. |
| Merge 178bbab | `git merge-tree` of 57257a8 and a784773 conflicts only in CHANGELOG.md. The resolution keeps both sides, and the merge differs from the auto-merge in nothing else. |
| Key scan | For every secret variable set in this sandbox, its full value, its first 14 characters and its last 12 characters appear 0 times, both in the PR diff (a2493db..178bbab, 8,743 lines) and in each commit. A generic pattern scan finds only test dummies (`sk-test-...-DO-NOT-LOG`, `sk-ant-test-...`, `xai-test-...`). |
| Round-2 probes, adapted | 21 pass: 18 in `test_r2a_*` plus the partial-index probe and the 2 fixed-behaviour probes. |
| Round-1 probes, adapted | All 15 fail as expected; each asserts a round-1 bug, so the bugs stay fixed. |
| Round-3 probes | 16 pass, plus the SIGINT/SIGKILL subprocess probe. |
| Real model: `probe_embed.py` | Same output as round 2: bitwise repeatable, a batch equals each post alone, a long post is cut at 512 tokens. |
| Real model: `probe_batching.py`, 303 posts | See the batching table below. |
| Mutations | 52 valid mutants: 34 killed, 18 survived. F2 and F7 in batch 1 were syntax errors; they were redone as F2' and F7', and both are killed. Results are in `mutations.txt`, `mutations2.txt` and `mutations3.txt`. |

**Batching probe** (303 posts, real model):

| Batching | Time | Peak RSS |
| --- | --- | --- |
| Old: time order | 111.3 s | 4,082 MB |
| Sorted by length | 34.1 s | 1,831 MB |
| 178bbab's `embed_batches` | 13.2 s | 648 MB |

All three give bitwise-identical vectors: 303×384, maximum difference 0.0.

**Mutation survivors:**

| Kind | Mutants |
| --- | --- |
| By design | F8: Haiku's price changed. Prices sit outside the hash on purpose. |
| Script-only or declined, as expected | N6, N7, P1, P2 and D1 (scripts), N13 (tie-break), N4a and N4b (the declined half of N4) |
| Test gaps, reported below | C2-C5 (S1); S2c (N2); G2 (N3); F10 (N5); S1c and V5 (N6) |

## Round-2 ids

| Id | Status | Evidence at 178bbab |
| --- | --- | --- |
| S1 | **Fixed** | `_fatal()` (ai.py:457-464) makes OpenAI's 429 `insufficient_quota` fatal, and xAI is gone. In the adapted probe, the run stops at post 1 unrecorded after one call with no back-off, and a rerun works. Detection works on code+type, type only and code only; `rate_limit_exceeded` and an empty body are still retried 4 times. Mutations S1a and S1b are killed. S1c (check `code` only) survives because the test body sets both fields: see N6. |
| S2 | **Fixed** | Details below the table; two gaps are N1 and N2. |
| S3 | **Declined to PR 6, accepted** | "harm" is narrowed: Harmonized and Harmony pass; harming, harmful and harms are rejected. "Social Security benefits" is still rejected, and "skyrocket" and "plummet" still pass, as declined. The reason line now has its own version (`reason.json` v1). |
| S4 | **Fixed** | Version is `bge-small-en-v1.5@5c38ec7c405e.eaa83ab2`: the commit plus a digest of files, pooling, max_tokens and dims. The golden vector is at test_similarity.py:236-238. Ranges are `onnxruntime>=1.22,<2` and `tokenizers>=0.21,<0.24`. S4a-S4d are killed, and G1 (mean pooling in code) is killed by the golden vector. G2 (truncation at 256 in code) survives: see N3. Re-embedded vectors are bitwise equal (batching probe). |
| S5 | **Fixed** | `rule.threshold == pick_threshold(*counts())` is tested. S5a (0.80) and S5b (0.90) are killed. There is no hash pin on match_rule.json; accepted, since its `model_version` is checked at load and the test ties the threshold to the labels. |
| S6 | **Fixed** | `embed_batches` (batch.py:96-107): shortest first, at most 64 per batch, and at most `EMBED_BATCH_CHARS` = 32,768 padded characters. Probe: every key appears exactly once with its own text, ties keep input order, and a run killed at batch 4 resumes with each stored vector equal to its text's vector. S6a-S6c are killed. Time and memory are in the batching table above. |
| S7 | **Fixed by B2 (a784773)** | Details below the table; F10 survives (N5), and the request code is still unpinned (S1 below). |
| N1 | **Fixed** | ai.py:886 sorts each model's own list so the mapped mention comes first. The adapted probe passes, and V3 is killed. |
| N2 | **Fixed** | ai.py:757 uses the key `(not counted, -(models or 0), instrument_id is None)`. V4 is killed. It can only make a difference with three or more models (see "Checked and dropped"). |
| N3 | **Declined, accepted** | The reason holds: Anthropic reports a low credit balance as a 400, so a mid-run 400 can be account-level. The stop persists on rerun, as round 2 described. |
| N4 | **Partly fixed, accepted** | Now tested: seeded tickers as reviewed (test_rules.py:88-89), re-embedding for a new model version (`test_embed_makes_vectors_again_for_a_new_model_version`), and a dropped download (test_similarity.py:188; N10a and N10b killed). Still untested: `finished` after `pick()` (N4a survives), a new instrument named by its ticker (N4b survives) and `--window-start` (P2 survives). |
| N5 | **Accepted** | README.md:204-205 says "no default, so pass what's left of the budget". The double Alpaca check for a new ticker stays. |
| N6 | **Fixed** (untested) | `draw_pairs` skips `precision_*` keys. Probe: 300 held-out keys in the index, 0 drawn, 415 pairs, none later than its post and none pairing a post with itself, at most 3 per post per band. Mutation N6 survives (script). |
| N7 | **Fixed** (untested) | `pairs` refuses when any label is marked; the probe was refused and the file was unchanged. Mutation N7 survives (script). |
| N8 | **Fixed** | `coverage` exists and scores are written with `.6f`. The history numbers weren't re-run here: there are no history vectors in this sandbox. |
| N9 | **Declined to PR 7, accepted** | |
| N10 | **Fixed** | Files are chmod 0644 before the replace, and `.part-*` files are cleared. Fetch probe on a mock transport: a dropped connection and Ctrl-C leave nothing, a 404 keeps the already-checked `model.onnx`, and files land 0644. N10a and N10b are killed. |
| N11 | **Noted for PR 5, accepted** | |
| N12 | **Done by B2** | samples.py refuses a rules version other than 1 (`DEV_MARKET_RULES`). Mutation D1 survives (script). |
| N13 | **Fixed** (untested) | `order_by(posted_at, signal_key)` at similarity.py:283. Mutation N13 survives. |
| N14 | **Moot** | The xAI config copies are gone. |
| Q1 | Answered | 0.85 stays; the match-weighted share goes to PR 5. |
| Q2 | Answered | PR 5 wires the match rule, and the PR body says so. |
| Q3 | Answered by a784773 | Two models and the 2025-11-01 window. The sandbox rows were rebuilt and re-stamped (results.md:36); see Q2 below. |
| Q4 | Answered | For PR 7. |
| Q5 | Moot | Grok is comparison-only. |

**S2 in detail:**

- **The lease row:** an "ai-pick" row, `Lease(..., name=AI_PICK_LEASE)`, with TTL 600 s. It is renewed by `acquire()` before each post (batch.py:349-351) and released in `finally` (batch.py:296). `holder_id` moved to lease.py and is unique per process (host:pid:random).
- **PR 1 unchanged:** the default-name SQL is identical and PR 1's 30 tests pass.
- **Probes:**
  - Two runs started together: one works, each post is paid once, and the row is cleared.
  - An error, a task cancel and SIGINT on a subprocess each release the row; SIGKILL leaves it until it lapses.
  - The engine's lease and ai-pick's lease don't block each other.
- **Mutations:** S2a, S2b, S2d, S2e and S2f are killed.
- **Gaps:** a post longer than the TTL lets a second run in (N1), and S2c survives (N2).

**S7 in detail:**

- **The freeze:**
  - `"frozen"` in ai.json holds V1_HASH `750126437c71…`, and `_pinned()` refuses a mismatch (ai.py:200-204).
  - Every `ai:<provider>` row records `picker_hash`.
  - `other_files` (score.py:192-210) checks `method LIKE 'ai:%'` with `IS DISTINCT FROM`, so a NULL result or a missing hash is flagged. It is scoped to the version, and rules rows aren't checked.
  - `other_files` runs in ai-pick and at worker start (score.py:240-241). `live_ai` lets `RulesFileChanged` through.
- **`window_start`:** 2025-11-01 at New York midnight = 04:00 UTC (probe).
- **Outside the hash:** prices and `reason.json`. A missing price gives "anthropic: price not checked" with the hash unchanged.
- **Mutations:** F1, F2', F3, F4, F5, F6, F7' and F9 are killed. F10 survives (N5).
- **Remaining gap:** the request code is not pinned (S1 below).

## New findings

### Should-fix

#### S1. v1's files are frozen, but no test pins the request the code builds from them

- **Where:**
  - ai.py:310-330 (`OpenAIChat.ask`: message roles, the output cap, the response format);
  - ai.py:376-396 (`AnthropicMessages.ask`: `system`, `max_tokens`, `output_config`);
  - ai.py:772-775 (`user_message`);
  - tests/test_ai.py:150-186, the only SDK-level body checks: temperature, `strict` and the format type.
- **Commit:** a784773 makes the claim ("a frozen version never changes"); the gap is older.
- **Problem:**
  - The frozen hash covers `ai_picker.json` and `picker.md`. What each provider receives is assembled by code, and no test pins it.
  - Each of these mutants passes all 116 tests in test_ai, test_batch and test_score:
    - C2: OpenAI gets the instructions as a `developer` message, not `system`.
    - C3: Anthropic's `system` gets an extra sentence.
    - C4: the configured output cap is ignored and 4,096 is sent.
    - C5: `why` isn't cut to 100 characters.
  - The user message and the quoted post are pinned (C1 and C6 killed), and so is `strict` (C7 killed).
  - 57257a8's N1 shows that a code change can move v1's results under an unchanged hash. That one was intended (see Q2), but nothing would flag one that wasn't.
- **Failure scenario:**
  1. PR 5 adds a second request path for the v1 backfill. results.md prices the projection at Batch API rates.
  2. A refactor there sends `picker.md` as a user turn, or drops the cap.
  3. Every test passes, since the stubs answer whatever is sent. ai.json still says v1 is frozen, and `other_files` sees the right hash.
  4. The backtest's "v1" answers then come from a request that differs from the one row A measured.
- **Evidence:** `mutations2.txt` C2-C5. The SDK body tests at test_ai.py:163-186 assert only `temperature`, `strict` and the format type.
- **Fix:**
  - Add one golden test per provider. Build the request for a fixed post, with a quoted post, through the real SDK on a `MockTransport`, using `current_ai_config()`. Assert that the whole JSON body equals a committed fixture: model, messages or system, temperature, max tokens, and response format or output config.
  - Add a line to ai.json's `about`: changing that fixture means a new version.
  - Optionally, a 150-character `why` test for C5.
  - This is a few lines, and any batch path in PR 5 can then be checked against the same fixture.

### Nits

#### N1. ai-pick renews its lease only between posts and never steps down, so a post longer than 600 s lets a second run in

- **Where:** batch.py:244-250 (the constants and the docstring "takes at most about 75 s"), :280-297 and :349-351. README.md:206-208.
- **Commit:** 57257a8.
- **Problem:**
  - The lease is renewed by `acquire()` at the start of each post, and `keep()` (PR 1's renew-and-step-down loop) is never used.
  - A post also runs Alpaca checks one at a time, for each ticker no rules version reviewed. One Alpaca request can take up to 5 tries × 20 s plus 2+4+8+16 s of back-off, about 130 s. A new ticker takes `counts()` (1-2 requests) plus `add_instrument`'s own check (round 2's N5), and an answer has up to 8 instruments per model.
  - With Alpaca timing out, one post can run past 600 s. So the docstring's "at most about 75 s" counts only the model calls.
- **Failure scenario:**
  1. During a long run, Alpaca degrades.
  2. The owner starts a second `ai-pick`, thinking the first has died. It takes the lapsed row and asks the in-flight post again.
  3. One run's answers for that post are dropped by ON CONFLICT DO NOTHING, and their cost is never recorded, so "spent so far" undercounts.
  4. The first run stops at its next post.
- **Damage:** bounded to one post's calls (under a cent).
- **Evidence:** `probes/test_r3_lease.py::test_a_post_longer_than_the_lease_lets_a_second_run_pay_for_it_too`, with the TTL scaled to 2 s and 3 s per post. Post 1 was asked 4 times, the second run finished, and the first ended with "stopped at …: lost the ai-pick lease to another run".
- **Fix (either):**
  - Run `lease.keep()` in a TaskGroup around the post loop; it renews every 60 s and steps down at 540 s.
  - Or keep the design, and correct the docstring and README to "a post slower than 10 minutes (Alpaca retries included) lets another run in".

#### N2. No test pins that ai-pick uses its own lease row

- **Where:** batch.py:244, tests/test_batch.py:338-400.
- **Commit:** 57257a8.
- **Problem:** mutant S2c (`AI_PICK_LEASE = "engine"`) passes all 68 tests in test_batch and test_lease. The tests name the row through the same constant on both sides.
- **Failure scenario:** a later cleanup drops the constant for the default `LEASE_NAME`. Then `ai-pick` on Railway either refuses to start while the engine runs, or takes the engine's row during a deploy. The engine's `keep()` then raises `LeaseLost` and the engine copy stops.
- **Fix:** add a test that holds `Lease(db, "engine copy")` with the default name and checks that `run_ai_pick` still runs and the engine's row is untouched. `probes/test_r3_lease.py::test_the_engine_lease_and_the_ai_pick_lease_do_not_block_each_other` does this.

#### N3. The golden vector runs only where the model files are fetched, and the truncation length isn't pinned

- **Where:** tests/test_similarity.py:215-238; pyproject.toml:16 and :22; .github/workflows/engine.yml:47 (no `fetch-model`); similarity.py:146.
- **Commit:** 57257a8.
- **Problems:**
  - CI skips the real-model test, as the PR body says. Railway installs onnxruntime and tokenizers from version ranges with no lock file, so a new minor release reaches prod without the golden check. The CHANGELOG's "a golden vector in the tests catches a changed tokenizer or runtime" holds only on a machine with the model.
  - With the model present, mutant G2 (truncation at 256 tokens instead of the pinned 512) passes all 16 similarity tests. The long-text check only asks `truncated`.
- **Failure scenario:** a tokenizers 0.2x release changes truncation or normalisation. The live worker embeds new posts under the same version string as history, and scores near 0.85 move silently.
- **Fix:**
  - Check the golden vector once in `OnnxEmbedder.__init__`, failing like `ModelMissing`. Loading takes 0.5 s and one post about 29 ms.
  - In the same check, assert that a 1,000-word text encodes to exactly `pin.max_tokens` ids.
  - Or pin exact versions.

#### N4. The frozen-version error says "raise the version" even when it was raised

- **Where:** ai.py:200-204.
- **Commit:** a784773.
- **Problem:** with `"version": 2` and v1's `"frozen"` left in place, the loader says: "version 2 in ai.json is frozen and its files changed: a frozen version never changes, so raise the version". Reproduced with a manifest in `tmp-frozen-msg/`.
- **Fix:** "'frozen' in ai.json doesn't match its files: a frozen version never changes; raise the version and remove or replace 'frozen'".

#### N5. The live stage's stops on an AI version mismatch aren't in the README or CHANGELOG, and one isn't tested

- **Where:** README.md:224-229, CHANGELOG.md:41, score.py:213-223 and :240-241.
- **Commits:** a784773, 57257a8.
- **Problems:**
  - The README says the worker fails at start when the model or the names are missing. It also stops when a frozen version's files changed (`live_ai` lets `RulesFileChanged` through), and when this version has answers recorded with other files.
  - Mutant F10 (`live_ai` catches `RulesFileChanged` and returns None, so the worker runs rules-only with a warning) passes all 63 score and AI tests. My freeze probe asserts the current behaviour.
- **Fix:** add one README/CHANGELOG sentence, and a test that `live_ai` with `ai_live` on raises on a changed frozen file.

#### N6. Other small test gaps (mutants that survive)

- **S1c:** detecting the quota error by `code` alone passes, because the test's body sets both `code` and `type`. A body with only `type` would pin the either-field check.
- **V5:** review-list's "named by both models" filter at `models >= 1` passes. `test_review_list_shows_names_the_vote_counted_that_the_rules_missed` (test_batch.py:202) has no name that only one model gave.
- **For the record (scripts, or declined):** N6, N7, P1, P2, D1, N13, N4a, N4b.

### Questions

#### Q1 (for the coordinator). Brief deviations beyond Chris's update

The brief now opens with Chris's 2 Oct 22:03 UTC update: two models, both must agree, window 2025-11-01, no xAI vote. It "replaces every 'three models' and '2 of 3' below", and results.md:3 records the same decision.

Two differences from the brief's text are not named in that update:
- **Prices are outside the frozen version.** §6 lists "a price table per model" among the items "Frozen as AI picker version 1, with its hash". a784773 moves the prices to `ai_models.json`, outside the hash.
  - This follows round 2's S7 note that prices don't change picks.
  - It is disclosed in the CHANGELOG, README, ai.json's `about` and the PR body.
  - No owner sign-off is recorded for it.
  - **Effect:** a price can be corrected without a v2. Each row keeps the cost computed at the time, and the budget caps use whatever the file says.
- **`ai:xai` is dropped.** §8's method list includes `ai:xai`; migration 0004 (edited in place, unmerged, disclosed) drops it from the CHECK. This follows from "no xAI model votes".

Are both fine as consequences of the update, or does the price move need Chris's OK?

#### Q2 (for B2). Were row A and the review-list line built with 57257a8's per-model dedup?

- results.md was last written at 23:12, and a784773 at 23:14. 57257a8 (23:17) changed which mention a model's own list keeps when it gives a name twice (ai.py:886).
- The freeze pins files, not code. A sandbox answer that names one name twice can therefore vote differently at 178bbab than in the stored votes.
- Could B2 re-map and re-vote the recorded answers with 178bbab's code (no model calls), and confirm that row A (89% / 57% / 5/5 / 5/10) and the review-list names are unchanged?
- The sandbox database isn't reachable from here.

## Checked and dropped

**Lease (S2):**
- **Lease change for the engine's own row:** the default name gives the same row, SQL and timeouts, and PR 1's tests pass.
- **`_answer_within` for ai-pick** (600 − 2×60 = 480 s lock and statement timeout): it only bounds the lease's own statements.
- **Releasing a lost lease:** it deletes only its own holder's row, so it is a no-op after another run took the row (`TakesTheLease` test).
- **Two runs on one host:** `holder_id` includes the pid and a random suffix.
- **A leftover `ENGINE_XAI_KEY`** is ignored by Settings, which loads fine.

**Freeze (S7):**
- **The freeze is only as strong as `"frozen"` in the same file:** a re-pinned and re-frozen manifest loads. The `V1_HASH` pin in test_ai.py:55 fails CI, though (F9 killed), so changing v1 takes two deliberate edits.
- **`other_files` blocking the sandbox:** its AI rows were re-stamped with the frozen hash (results.md:36), and prod starts empty.
- **`other_files` cost:** `LIMIT 1` over one version's AI rows, once at worker start and once per ai-pick.
- **A broken reason file blocks the picker:** `load_ai_config` also loads `reason.json`, but a stale hash fails CI (`test_a_changed_picker_or_reason_file_is_refused`).
- **The live worker halts the whole stage on a mismatch:** this matches the rules' `RulesFileChanged` design, and round 2 asked for a refusal.
- **`reason.json` has no `"frozen"`:** PR 6 is where reason lines get stored.
- **`window_start` not enforced in ai-pick:** this is by design, since the dev and early sets are asked too.

**AI picker:**
- **N2's sort key with two models:** a name both models gave unmapped is a single entry with `models=2`, and a name one model mapped while the other didn't gives two entries with `models=1`. So `-(models)` never decides with two models; it is harmless and tested with a fake third provider.
- **No `cache_control` on Haiku:** Haiku 4.5's minimum cacheable prefix is 4,096 tokens, and a picker call is about 1,500, so the comment at ai.py:382-383 is right.
- **The two-model vote is consistent** across code, README, CHANGELOG and the PR body: `NEEDED = len(PROVIDERS) = 2`, and the rules stand in if either model fails (V1 and V2 killed).
- **No xAI or three-model leftovers** in engine/: the only "third" is the N2 test's fake provider.

**Scripts:**
- **precision.py UTC vs New York:** it now splits at the version's New York `window_start`, and round 2 found no window post in the gap.
- **samples.py guard relies on the names table:** documented in its docstring.
- **`coverage()` crashes on an empty index and is O(N²):** script-only, and the history is about 16,000 posts.

**Similarity:**
- **The character budget over-penalises long posts:** this costs efficiency only, and the vectors are identical.
- **Two concurrent `fetch-model` runs** delete each other's part files: an edge case for an operator command.
- **"huggingface.co and us.aws.cdn.hf.co only":** this sentence is unchanged since round 2. It is what that run observed, the CLI prints the real hosts, and SHA-256 guards the content.
- **The golden vector's tolerance (2e-4)** catches a pooling change (G1 killed) and passes benign float drift.

**Process:**
- **Migration 0004 edited in place:** unmerged and disclosed in the PR body.
- **The merge:** only CHANGELOG.md conflicted, and both sides were kept.
- **Leftover test databases:** none of this review's runs left one. The `engine_test_*` databases present at the end were being created at that moment by other agents' running test suites, so they were left alone. One stale database from an earlier interrupted run (`engine_test_04b2660d`, no connections) was dropped early in this review.
