# PR #261 round 2: review and verify of the round-1 fold-in (a4c438f) and the merges

This covers the head at 4554d3d: the round-1 fold-in a4c438f (19 files, +1,123/-263) and the merges 2c1ffcc, 2af7aec and 4554d3d. B2's feature commits (ba4d296, ea66a40) are another agent's scope.

All line numbers refer to 4554d3d. Nothing was pushed or written to GitHub. No production database was touched and no real AI, Alpaca, Hugging Face or other external call was made. Probes and logs are in `$SP/review-261-r2/fold/` (written F below).

## Verdict

The fold-in is good work.
- Every round-1 Blocker and Should-fix has a real fix, and almost every new guard is held by a test: 79 of 86 mutations are killed.
- The history claim holds: on 17,948 posts the rules v1 answers are identical before and after the change, even after 10 AI-added tickers.
- The merges are clean.

No new Blockers. Three Should-fix items:
1. OpenAI's out-of-credit 429 is still retried and recorded as a failure, so S3's batch poisoning comes back for the most likely real-world failure.
2. The `ai-pick` lock is a session advisory lock, which a transaction-mode pooler (Neon's pooled endpoint) breaks.
3. S7 is only partly fixed: the reason check still passes many common direction words (skyrocket, plummet, tumble, highs, slide, dip, boon, windfall, downgrade).

There are also seven Nits and two Questions.

## Commands (at 4554d3d)

All runs used the venv `/home/user/engine-venv-261` with `PYTHONPATH=<checkout>/engine` and `ENGINE_MODEL_DIR=/home/user/engine-models`. Every secret variable was stripped (`F/safe.sh`).

| Check | Result |
| --- | --- |
| `ruff check` | All checks passed |
| `ruff format --check` | 90 files already formatted |
| `mypy` | Success: no issues found in 85 source files |
| `alembic heads` | `0004 (head)`; the chain is 0001 → 0002 → 0003 → 0004 |
| `pytest` run 1 | 451 passed in 170.48 s (`F/pytest_run1.txt`) |
| `pytest` run 2 | 451 passed in 186.44 s (`F/pytest_run2.txt`) |
| `pytest` as role `engine` (`DEV_DATABASE_URL=postgresql://engine:<redacted>@localhost/postgres`) | 451 passed in 176.63 s, rc 0 (`F/pytest_engine_role.txt`) |
| Migration round trip on throwaway DB `r2fold_mig`, dropped afterwards (`F/mig_roundtrip.sh`) | `migrate` rc 0 and creates `signals_unfinished_idx ... WHERE (stage <> ALL (ARRAY['done','error']))`. Downgrade to 0003 removes it, upgrade restores it, final version 0004 |
| `scripts/precision.py` reproduction (`F/repro_precision.txt`) | "300 posts in the spot-check file; 0 rules answers differ from it"; the table is identical to rules-precision.md |

There were no skips, so the tests that use the real model ran. No leftover databases remain (only postgres, shitpost_dev, template0, template1) and no roles were created.

## Merge check

- **2c1ffcc** (PR 3 into PR 4): the only conflict was `engine/engine/cli.py`. Its resolution keeps both PR 3's `database_error_line` and PR 4's `EXTRACT_COMMANDS`, which is correct.
- **2af7aec**: the remerge-diff is empty. The `test_live` hunk is identical in 6a24a0b and 0235161.
- **4554d3d** (B2's ba4d296 and ea66a40 into a4c438f). Conflicts and resolutions:
  - `scripts/precision.py`: took B2's New York wording, which is identical.
  - `tests/test_ai.py` and `tests/test_batch.py`: both sides kept.
  - Hand edits:
    - `reason.py` moves "harm" into round 1's line and dedups "benefit". The semantics are the same.
    - `test_score.py` and `test_ai.py` now use unpinned or unpriced replacements, because B2 pinned the version.
  - Every line missing from either parent is one of these documented resolutions.
- **PR 3 alignment:** `origin/claude/engine-prices-f67iio` = a2493db and the PR head = 4554d3d.
  - All 49 files that differ between a2493db and 4554d3d were touched by PR 4's own commits.
  - Of the 11 files upstream changed from 56a32f7 to a2493db, the 7 PR 4 doesn't touch are byte-identical at 4554d3d.
  - In the other four (CHANGELOG.md, README.md, cli.py, test_live.py), every line upstream added is present.

## Round-1 ids

Evidence key:
- **r1** is round 1's probe re-run unchanged (`F/r1probes`, 27 failed and 5 passed). A failure means the bug is gone.
- **r1a** is a round-1 probe adapted to the new API (`F/r1adapted`, 15 failed, each for the right reason).
- **M** is a mutation in `F/mutate.py`, with results in `F/mutations.txt`.
- **p** is a new probe in `F/probes` (39 passed).

| Id | Status | Evidence |
| --- | --- | --- |
| B1 vote drops a counted mention | **fixed** | r1 `vote_mentions_dedup` fails. M F1, F2, F4 killed. F5 survives as an equivalent mutant (F4's guard raises first). There are two residuals, Nits N-1 and N-2 below. N-1: F3, the per-model `unique_names`, survives with no test, and the per-model list keeps the first mention rather than the counted one. |
| S1 Alpaca failure loses paid answers | **fixed** | r1a: the live stage now ends at `done`, and batch no longer raises `AlpacaKeysMissing`. p `fixed_behaviour`: with Alpaca down, the stage reaches `done`, 3 AI rows plus the vote row keep their costs, the vote mention is `("count_check_failed", 3)`, and Alpaca is asked 3 times. M F6, F7, F8 killed. |
| S2 billed rejected replies keep no cost | **fixed** | r1 `invalid_answer_cost` fails. M F9-F13 killed (cost, body, OpenAI `finish_reason`, Anthropic `stop_reason`, problem → failure). |
| S3 bad key poisons a batch | **fixed for the cases named; residual** | r1 `ai_pick_bad_key` and `one_key_picker` fail. M F14-F18 killed. The residual is Should-fix S-1: OpenAI's out-of-credit 429 is not fatal. A related Nit is N-3: a per-post 400 stops every rerun at the same post. |
| S4 unsynced names send live posts to `error` | **fixed** | r1 `unsynced_names_error_posts` fails. M F19 killed. |
| S5 existing ticker mapped outside its dates | **fixed** | r1 `existing_ticker_outside_dates` fails. p `fixed_behaviour`: PSKY on 2024-05-01, META on 2022-05-02 and VG on 2024-01-27 all give `not_listed_then`, Alpaca is never asked, and the book is not widened. M F20 and F22 killed. F21 is an equivalent mutant: an unreviewed instrument's hold is already `(None, None)`. |
| S6 AI ticker becomes a rules bare ticker | **fixed; history identity verified** | r1a: after the AI adds ICE, the rules pick gives `()`. On 17,948 text posts (`F/history_identity.txt`): old code (6efd98b) vs new code with the sync-names book, 0 differences. Adding 10 AI-added tickers (ICE, LNG, NYT, IRS, CIA, DEI, EU, SOS, MS, NUE) changes 105 posts under the old code (62 market links, 64 topics) and 0 under the new. M F23, F24 killed. F25 (the seeded four reviewed) survives; only a bare "QQQ" depends on it, which appears in 0 history posts (Nit N-5). |
| S7 reason check passes direction, price or advice | **partly** | Round 1's lines are now rejected: r1a `reason_check_gaps` gives 15 failures, and M F26-F28 are killed. But many common direction words still pass; see Should-fix S-3. |
| S8 reprs print keys | **fixed** | r1a `picker_repr_keys` fails. M F29 killed. |
| S9 Anthropic follows cross-host redirects | **fixed** | r1 `redirect_key` fails for Anthropic. Its OpenAI contrast test still passes, as designed. M F30, F31 killed. |
| S10 safety properties without tests | **fixed** | All of verify's mutations V1-V35 are killed, including round 1's survivors M10, M11, M13, M22, M24, M30, M32 and M33. Review's survivors R1, R2, R3, R5 and R12 are killed too. |
| N1 `--max-usd` NaN/Inf, rounded projection | **fixed** | M F33, F34 killed. r1 `max_usd_values::nan...` still passes because the function itself accepts these values. The CLI's `_dollars` blocks them, which is enough. |
| N2 operator errors print tracebacks | **fixed** | r1 `cli_tracebacks` fails. M F35, F36 killed. `AlpacaKeysMissing` subclasses `AlpacaError`, which is caught. |
| N3 SDK header environment variables | **fixed** | `build_clients` refuses when they are set (ai.py:369-373). M F32 killed. r1 `sdk_env_headers` still passes because it builds `OpenAIChat` directly, bypassing the guard. Accepted. |
| N4 Anthropic prompt caching | **left to B2** (other agent) | r1 `anthropic_no_cache` still passes at 4554d3d: no `cache_control` marker yet. Flagged for the B1/B2 agent. |
| N5 alias inside a longer name beats the model's ticker | **declined, accepted** | r1 `alias_inside_longer_name` still passes, as expected. The share-class argument holds. The "mark as conflict" option is still open if review-list ever shows it. |
| N6 no index for the 1 s poll | **fixed** | The index is in the table and in migration 0004 (tables.py:131, 0004:88-94), and the round trip works. p `partial_index`: on 20,000 signals the literal plan and the 8th prepared execution both use `signals_unfinished_idx`, and only a forced generic plan doesn't. M F45 (table side) is killed by `test_migrations_match_table_definitions`. r1 `score_poll_seq_scan` fails. |
| N7 dead code | **fixed** | `has_extraction`, `names_of`, `ModelSpec.provider` and `Replayed.delivered` are gone. `CountsAll.asked` is used by tests. `replay_embedder` is now used in test_score.py:319, with the real model when present. |
| N8 rules `started_at == finished_at` | **fixed, no test** | score.py:99. M F42 survives (Nit N-5). |
| N9 free text becomes the instrument name | **fixed, no test** | score.py:64 uses the ticker. M F46 survives (Nit N-5). |
| N10 replay `deliver` inside the transaction | **declined, accepted** | It is a test-only hook, and PR 6 reads committed rows. |
| N11 UTC window boundaries | **fixed in precision.py, no test; samples.py kept frozen (accepted)** | precision.py:199. M F43 survives; the mutant even leaves an `UnboundLocalError` behind, so the `--window-start` path never runs in tests (Nit N-5). |
| N12 `k` cap, `min_score` default | **partly, accepted** | `min_score` has no default. `k` stays a parameter for the pair-reading script, and there is no production caller over 50. |
| N13 run 2 without run 1, silent skipped keys | **fixed** | M F41 killed. The skipped-key line prints at batch.py:312-317. |
| N14 "pinned" wording | **fixed** | CHANGELOG.md:34 and :43 and the README now match what B2 pinned. |
| N15 `fetch_model` UA and timeout | **partly, accepted** | The User-Agent is sent (M F44 killed). Its own client is justified: the hub redirects to its CDN, and hash checks protect the content. |
| C1, C2, C8 | **done** | C2 is `from_settings` raising `NotReady` (ai.py:788-798), covered by M F17, F18. C8 is `record_rules` (score.py:93-101). |
| C3 | **kept, accepted** | Because S3 requires all three keys, the placeholder path is now reachable only from tests. It is harmless. |
| C4-C7, C9 | **skipped, accepted** | These were optional. |
| Q1 | **answered** | No rules-vs-labels run before 997fe4c. There are no artifacts to contradict this. |
| Q2 | **answered with a guard** | `other_prompt` (batch.py:230-242) makes `ai-pick` exit 2 for a version with votes under another `picker_hash`. M F40 killed. See Nit N-6 and Question Q-b. |
| Q3 | **deferred to PR 7, accepted** | |
| Q4 | **answered** | `--max-total-usd` (M F37, F38 killed) and the advisory lock (M F39 killed). See Should-fix S-2 for the lock. |

Mutation totals: 86 run, 79 killed, 7 survived. Of the survivors, two are equivalent (F5, F21) and five are test gaps (F3, F25, F42, F43, F46).

## New findings

### Blocker

None.

### Should-fix

**S-1. OpenAI's out-of-credit error is retried and recorded, so S3's batch poisoning returns** (ai.py:64, 399-410, 415-420)
- **Problem.** `FATAL` covers auth, permission, not-found, 400 and 422. When an OpenAI account runs out of credit, though, OpenAI returns **429** with `code: "insufficient_quota"`, and 429 is in `RETRY_STATUSES`. That error is retried 3 times and then recorded as that model's failure.
- **Failure scenario.** In the middle of a B2 batch the OpenAI balance hits zero.
  - Each later post pays the other two models, waits 2+4+8 s and records `ai:openai` as failed.
  - Its vote is a two-model vote recorded as run 1. `ai-pick` exits 0.
  - After topping up, a rerun prints "0 posts", so those posts keep the degraded run-1 vote for good. This is exactly what S3 was about. CHANGELOG.md:36 says a bad key "stops it", and to an operator this case looks the same.
- **Evidence.** `F/probes/test_probe_r2_fatal_gaps.py::test_openai_out_of_credit_is_retried_not_fatal_and_poisons_the_batch` passes. It drives the real OpenAI SDK with a `MockTransport` 429 and fake keys.
  - It sees 4 HTTP calls per post and waits of 2, 4 and 8 s per post.
  - All 3 posts are recorded with `RateLimitError ... insufficient_quota` and 3 votes, and the run returns 0.
  - The rerun with good clients prints "0 posts".
- **Fix.** In `_retryable` and the fatal test, treat `openai.RateLimitError` whose `exc.code == "insufficient_quota"` (also present in `exc.body["code"]`) as fatal and not retryable. Add the probe as a test. For xAI, confirm the status of an exhausted team; if it is 403 it is already fatal. Anthropic's "credit balance is too low" is a 400 and is already fatal.

**S-2. The one-at-a-time lock is a session advisory lock, which a transaction-mode pooler breaks** (batch.py:273-275)
- **Problem.** `pg_try_advisory_lock` is taken, then `commit()`, and the lock connection sits idle for the whole run.
  - On a direct connection that is fine. `dispose()` closes the backend and the lock goes with it.
  - Behind PgBouncer in transaction mode (Neon's `-pooler` endpoint), the lock belongs to whichever server connection ran that one statement.
  - After the commit, that server connection returns to the pooler's pool, and `dispose()` closes only the client side.
  - The engine elsewhere is built to tolerate a pooler. The lease is a table row, migrations/env.py:27 comments that "a transaction-mode pooler drops session settings", and README:229 tells Neon users to point only `migrate` at the direct endpoint. So `ENGINE_DATABASE_URL` may well be the pooled URL.
- **Failure scenario.** Either of two things can happen:
  - The lock outlives the run on a pooled server connection. Later runs that land on other backends print "another ai-pick is running" until the pooler recycles that backend; PgBouncer's default `server_lifetime` is 3600 s.
  - Two runs land on the same backend. Session advisory locks are re-entrant for the session, so both get `true` and both pay for the same posts. That double spend is what Q4 asked to prevent.
- **Evidence.** This comes from reasoning and documented Postgres and PgBouncer semantics: session advisory locks are not supported in transaction pooling mode. No pooler is installed in the sandbox, so I couldn't run it. On a direct connection the existing test passes (M F39 killed).
- **Fix.** Hold the lock in a transaction that stays open on the lock connection for the run: `await lock.begin()`, `SELECT pg_try_advisory_xact_lock(...)`, no commit, and a rollback at the end.
  - A transaction-mode pooler pins one server connection for an open transaction.
  - The lock goes away on commit, rollback, disconnect or cancel.
  - Under READ COMMITTED, a statement-only transaction holds no snapshot between statements, so it doesn't hold back vacuum.
  - The alternative is a lease row like the stage lease. Either way, add a sentence to the README about which URL `ai-pick` needs.

**S-3. S7 is only partly fixed: common direction words still pass the reason-line check** (reason.py:18-29, used at :44)
- **Problem.** The word list now catches round 1's lines and adds benefit, harm, up, down, higher, lower and more. But a word list is open-ended, and many ordinary market verbs and phrases still pass.
- **Failure scenario.** Once PR 6 calls `reason_line`, a model line like "Nucor could skyrocket on the steel tariffs" or "Tariffs may send Nucor to new highs" goes to subscribers inside an alert. The module docstring promises such lines are rejected (reason.py:4).
- **Evidence.** `F/probes/test_probe_r2_reason_check.py::test_direction_or_advice_still_passes` passes for all 20 of these lines:
  - "Steel tariffs could be a boon for Nucor"
  - "A blow to Apple's China supply chain"
  - "Tariffs could help Nucor and US Steel"
  - "Steel tariffs may hit Apple's margins"
  - "A win for Nucor and Cleveland-Cliffs"
  - "Nucor could see an upgrade after the tariff news"
  - "Apple shares could plummet on the tariff threat"
  - "Nucor could skyrocket on the tariff news"
  - "Apple could tumble on the China news"
  - "Steel tariffs favor Nucor over importers"
  - "Apple could hit two hundred dollars"
  - "A downgrade risk for Nucor from tariffs"
  - "Tariffs may send Nucor to new highs"
  - "Nucor at all-time highs"
  - "Nucor could slide as tariffs bite"
  - "A windfall for Nucor from steel tariffs"
  - "Nucor may dip on tariff news"
  - "Nucor stock could pop"
  - "Steel tariffs could squeeze Nucor margins"
  - "Nucor's outlook brightens with tariffs"
- **Fix.**
  - Add the obvious stems: `skyrocket\w*|rocket\w*|plummet\w*|tumbl\w*|slid\w*|slide|dip\w*|pop\w*|highs?|lows?|record\s+high|boon|windfall|blow\s+to|win\s+for|upgrad\w*|downgrad\w*|favou?r\w*|help\w*|hit\w*|squeez\w*|brighten\w*|boom\w*|rout\w*|moon\w*`.
  - Commit a corpus test file of about 50 direction or advice lines and about 30 neutral lines, so each later change to the list is measured. The check fails closed, so over-rejecting costs only a missing line.
  - This can land here or be carried explicitly into PR 6's brief, because nothing calls `reason_line` until PR 6.

### Nits

**N-1. Each model's own name list keeps the first mention of a name, not the counted one** (ai.py:833-835; M F3 survives)
- This is B1's pattern inside one model's answer. If a model lists a name twice, first without a ticker and then with one, `unique_names` keeps the unmapped first mention. The vote's own counted-first sort (ai.py:703) then never sees that model's mapped mention.
- Evidence: `F/probes/test_probe_r2_per_model_dedup.py` passes. Two models list "Some Chip Firm" first with no ticker and then with NVDA, and one lists it with NVDA. The per-model lists become `[('no_ticker', False)]` for two of the models, and the vote is `[('some chip firm', counted=False, models=1)]`. So NVDA is named by all three models and counted by none.
- Fix: sort each model's list with the vote's key before `unique_names`, and add this probe as a test. That test also kills F3.

**N-2. When nothing is counted, the vote sort drops the "named by 2+ models, not mapped" row** (ai.py:703)
- Two models give "Some Chip Firm" with no ticker and one gives NVDA. The sort keeps the mapped but uncounted NVDA row (models=1) and drops the unmapped models=2 row.
- review-list's "named by two or more models, not mapped" query (batch.py:396-404) therefore never sees it, and the "missed" section doesn't either, because nothing is counted.
- Evidence: `F/probes/test_probe_r2_vote_dedup.py` passes.
- Fix: when neither row is counted, prefer the higher `models`. For example, use the sort key `(not counted, -(models or 0), instrument_id is None)`. Or credit the mapped instrument with every model that gave that name.

**N-3. A provider's 400 on one post's content stops every rerun at that post** (ai.py:403 and 408, batch.py:347-349)
- `BadRequestError` and `UnprocessableEntityError` are FATAL. A provider that refuses one post's content (for example OpenAI's `invalid_prompt` flagging) stops `ai-pick` at that post. Because `select_posts` orders by `posted_at`, every rerun stops there again, and later posts are never reached.
- Evidence: `F/probes/test_probe_r2_fatal_gaps.py::test_one_post_a_provider_refuses_stops_every_run_at_that_post` passes. Over two runs it records 1 vote, and both runs stop at post 2.
- Fix: treat a 400 or 422 as fatal only on the first post asked in the run, or when its code is account-level. Otherwise record it as that model's failure. Or at least name `--keys` / `--from` in the stop line so the operator can step past the post.

**N-4. The number rule falsely rejects some lines, and amount words get through** (reason.py:31-32, 46-49, 53-54)
- These cases fail closed (no line), so the cost is only a lost line.
  - "1500" when the post says "1,500".
  - Numbers inside instrument or index names: "S&P 500", "Fortune 500", and "3M" when it appears only in the instrument names `reason_input` sends.
  - Neutral lines now rejected by the new words: "lower court", "shut down", "Medicare benefits", "crack down", "Raises questions".
- Meanwhile "$1.5 billion" is rejected as an amount, but "1.5 billion dollar" passes.
- Evidence: `F/probes/test_probe_r2_reason_check.py` (the `FALSE_REJECTIONS` and amount-word cases) passes.
- Fix:
  - Compare numbers with `,` removed.
  - Include `names` in the allowed numbers.
  - Add `dollars?|euros?|billion|million|trillion|bn` to `MONEY_OR_PERCENT`.
- "25%" vs "25 percent" is not a mismatch: both are rejected as amounts before the number rule runs.

**N-5. Several fixes have no test** (surviving mutations)
- F42: N8's `finished` is taken after `pick()` (score.py:99).
- F46: N9's instrument name is the ticker (score.py:64).
- F43: N11's New York midnight window start (scripts/precision.py:199). Tests never run the `--window-start` path; the mutant even leaves an `UnboundLocalError`.
- F25: seeded SPY, QQQ, BTC and ETH are reviewed (rules.py:344). Only a bare "QQQ" depends on it.
- Fix: one small assertion each.

**N-6. The picker hash covers files that don't change picks, and only `ai-pick` checks it** (ai.json `files`, ai.py:191, batch.py:230-242, score.py:183-192)
- The hash includes `prompts/reason.md` and the prices in `ai_picker.json`. Editing the reason prompt or correcting a price therefore makes `ai-pick` refuse (exit 2) until the version is raised, which resets "version 1" although the picks can't differ.
- The live stage (`live_ai`) doesn't check the guard. With `ENGINE_AI_LIVE` on, it records votes under the changed hash without complaint, and the next `ai-pick` then refuses.
- Fix: give the reason line its own pinned version, and hash only what affects picks (prompt, schema, model ids, settings). Or document that a price fix needs a version bump. Have `live_ai` log or refuse on the same mismatch.

**N-7. Small leftovers**
- A new ticker is checked with Alpaca twice: `new_ticker_adder` calls `counts()` (score.py:62), then `add_instrument` calls it again for a new symbol (market/instruments.py:190). On a live post the session is unsettled and not cached, so that is two calls. Fix: add an `add_checked_instrument` that skips the second check.
- `--max-total-usd` is opt-in (cli.py:63-67). With no default, an operator who forgets it has only the per-run $5 against PR 4's $15 budget. A default of 15 for v1, or a README line, would close it.

### Questions

- **Q-a.** With `ENGINE_AI_LIVE` on, a revoked key or an empty account degrades every live vote to two models, or to the rules after two failures, with only a warning log. That is by design: "live never stops". Should PR 7 add an operator notice, such as a count of failed `ai:<provider>` rows per hour?
- **Q-b.** How does B2 reach a frozen "version 1" on a dev database that already holds votes recorded under earlier prompt hashes? `other_prompt` makes `ai-pick` refuse that version until those rows are deleted or the version is raised. Is the plan a separate database, deleting dev rows, or freezing at version N?

## Checked and dropped

- **Cashtags of AI-added tickers.** Only 5 of 17,948 history posts have any cashtag (`$trump` ×3, `$worth`, `$zero`), none counted. The "cashtag only" residual of S6 changes nothing in history.
- **FATAL rollback.** The rules row and any instrument added for the stopping post roll back with the post's transaction (`db.begin()` at batch.py:339). The other two models' paid answers on that one post are not recorded or counted in `spent()`; that is at most 2 calls and is the documented "that post unrecorded".
- **Concurrency in FATAL handling.** `ask_model` returns a fatal answer rather than raising, so `gather` finishes all three requests before `record_ai` raises. No request is cancelled mid-flight.
- **Cancellation and lock release on a direct connection.** `CancelledError` and KeyboardInterrupt run the `async with` exit and `finally: dispose()`. A killed process ends its backend. A normal return or a FATAL exit releases the lock at `dispose()`, and `test_only_one_ai_pick_runs_at_a_time` holds it.
- **`--max-total-usd` arithmetic.** `so_far` is a snapshot at the start, so live spend during the run isn't counted, and the overshoot is at most one post's three calls. Both are minor and documented as "stops once passed".
- **Partial index vs the worker query.** The `IN ('score')` predicate is proven against `NOT IN ('done','error')` for literal and custom plans (probe). Only a forced generic plan misses it, and Postgres keeps custom plans for this query.
- **`picker_hash` presence.** Every vote result carries it (ai.py:649), so a NULL can't slip past the guard.
- **SDK environment.** Anthropic reads no credentials when `api_key` is explicit. `OPENAI_ADMIN_KEY` is not sent, because the bearer wins. The `*_LOG` variables only affect logging.
- **Unmapped reasons have no CHECK constraint.** This is a vocabulary question, not a defect. `review-list` prints whatever is there.
- **Exceptions escaping `_answered`.** Only something like a `RecursionError` could. That is theoretical.
- **Concurrent live and `ai-pick` on the same post.** This predates the PR, is rare, and `ON CONFLICT DO NOTHING` keeps one answer.
- **NUL and odd-character edge cases in `storable`.** Theoretical.
- **The `dollars()` printer vs unrounded comparisons.** The comparisons use the unrounded totals (M F34 killed). Printing "under $0.01" is cosmetic.

## Artefacts (all under `$SP/review-261-r2/fold/`)

- `safe.sh`: the secret-stripping wrapper.
- `pytest_run1.txt`, `pytest_run2.txt`, `pytest_engine_role.txt`: the test runs.
- `mig_roundtrip.sh`: the migration round trip.
- `mutate.py` and `mutations.txt`: 86 mutations, adapted from verify (V), review (R) and the new fixes (F).
- `r1probes/` (results in `r1probes-as-is.txt`) and `r1adapted/`: round 1's probes.
- `probes/`: the new probes, 39 passing (`probes-final.txt`).
- `history_identity.py`, `history_identity.txt`, `hist-*.json`: the history comparison.
- `repro_precision.txt`: the precision reproduction.

Worktrees, all detached and clean: `$SP/r2fold-261-wt` (4554d3d), `$SP/r2fold-261-mut` (4554d3d, restored after mutations) and `$SP/r2fold-261-old` (6efd98b).
