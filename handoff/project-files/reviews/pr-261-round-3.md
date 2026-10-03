# PR #261 "Engine PR 4: extraction and similarity": review round 3

**Reviewed:** 178bbab. That is 4554d3d..178bbab (your fold-in 57257a8, B2's freeze cdd6411, eb48824 and a784773, and the merge), plus a check of the whole PR. One fresh agent ran the review and verify passes together.

Earlier rounds: [1](pr-261-round-1.md), [2](pr-261-round-2.md).

I reproduced the should-fix myself: with OpenAI's instructions sent as a `developer` message, test_ai, test_batch and test_score still pass 116/116.

**Result: one should-fix left.** No blocker. The 6 nits are optional. Q1 is closed here; Q2 is for B2.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean. Alembic has one head (0004).
  - pytest passes 463/463 twice and once as the `engine` role, with no skips (the model files were present).
  - The key scan of the diff and of each commit finds no real key; only the tests' dummies.
- **The Lease change is safe for PR 1.** The default name sends the same SQL with the same timeouts at 4554d3d and 178bbab, and PR 1's 30 lease and runtime tests pass unchanged.
- **The merge** conflicted only in CHANGELOG.md, and both sides were kept.
- **Probes:** the 21 round-2 probes pass (adapted), the 15 round-1 probes fail as they should (each asserts a bug that stays fixed), and 16 new probes pass.
- **Batching on the real model, 303 posts:** `embed_batches` takes 13.2 s and 648 MB, against 111.3 s and 4,082 MB in time order. The vectors are bitwise identical.
- **Mutations:** 52 valid, 34 killed. The survivors are by design (a price change), script-only or declined, or the gaps below.

## Round 2 ids

| Id | Status |
| --- | --- |
| S1 | **Fixed.** OpenAI's `insufficient_quota` stops the run at once, by code or type; `rate_limit_exceeded` is still retried. |
| S2 | **Fixed.** The "ai-pick" lease row: two runs at once pay each post once; an error, a cancel and SIGINT release the row. Two gaps are N1 and N2. |
| S3 | **Declined to PR 6, accepted.** "harm" is narrowed, and `reason.json` has its own version. |
| S4 | **Fixed.** The version carries a digest, the golden vector catches a pooling change, and the ranges are bounded. Gap: N3. |
| S5 | **Fixed.** The threshold is tied to the labels by a test. |
| S6 | **Fixed.** Every key comes back once, with its own text, in input order for ties, and a killed run resumes correctly. |
| S7 | **Fixed by B2** (a784773): `frozen` holds v1's hash, the loader refuses a mismatch, each `ai:` row records `picker_hash`, and the worker and ai-pick check it. `window_start` is New York midnight. Gaps: S1 and N5 below. |
| N1, N2, N8, N10 | Fixed. |
| N6, N7, N13 | Fixed, without tests (scripts and a tie-break); fine. |
| N3, N5, N9, N11 | Declines accepted. |
| N4 | Partly fixed, accepted. Untested still: `finished` after `pick()`, a new instrument named by its ticker, and `--window-start`. |
| N12 | Done by B2. N14 is moot. Q1-Q5 answered or moot. |

## Should-fix

### S1. v1's files are frozen, but no test pins the request the code builds from them

**Where:** ai.py:310-330 (`OpenAIChat.ask`: the message roles, the output cap, the response format), ai.py:376-396 (`AnthropicMessages.ask`: `system`, `max_tokens`, `output_config`) and ai.py:772-775 (`user_message`). The only SDK-level body checks, test_ai.py:150-186, assert temperature, `strict` and the format type.

**Problem:** the hash covers `ai_picker.json` and `picker.md`, but what each provider receives is assembled by code. Each of these mutants passes all 116 tests in test_ai, test_batch and test_score:
- OpenAI gets the instructions as a `developer` message, not `system` (I re-ran this one);
- Anthropic's `system` gets an extra sentence;
- the configured output cap is ignored and 4,096 is sent;
- `why` isn't cut to 100 characters.

**Failure scenario:** PR 5's Part B adds a Batch API path for the v1 run, as results.md's projection assumes. A refactor there sends `picker.md` as a user turn or drops the cap. Every test passes, `frozen` still matches, and the backtest's "v1" answers come from a different request than the one row A measured.

**Fix:**
- One golden test per provider: build the request for a fixed post with a quoted post through the real SDK on a `MockTransport`, from `current_ai_config()`, and assert that the whole JSON body equals a committed fixture (model, messages or system, temperature, max tokens, response format or output config).
- One line in ai.json's `about`: changing that fixture means a new version.
- Optionally, a 150-character `why` test.

PR 5's batch path can then be checked against the same fixture.

## Nits (optional, file:line at 178bbab)

- **N1. ai-pick renews its lease only between posts and never steps down** (batch.py:244-250, :280-297, :349-351; README.md:206-208). One post's Alpaca checks can take about 130 s per request under retries, so a post can pass 600 s. A second run then takes the lapsed row and pays for that post too, and the first run's cost record for it is lost, so "spent so far" undercounts by under a cent. Probe: `probes/test_r3_lease.py::test_a_post_longer_than_the_lease_lets_a_second_run_pay_for_it_too`. **Fix:** run `lease.keep()` in a TaskGroup around the loop, or correct the docstring's "at most about 75 s" and the README.
- **N2. No test pins that ai-pick uses its own row** (batch.py:244, tests/test_batch.py:338-400). `AI_PICK_LEASE = "engine"` passes all 68 batch and lease tests. That mistake would make ai-pick on Railway take the engine's row during a deploy and stop the engine copy. **Fix:** adopt `probes/test_r3_lease.py::test_the_engine_lease_and_the_ai_pick_lease_do_not_block_each_other`.
- **N3. The golden vector runs only where the model is fetched, and truncation isn't pinned** (tests/test_similarity.py:215-238, similarity.py:146, engine.yml:47). CI skips it, and Railway installs from ranges with no lock file, so a new tokenizers release reaches production unchecked. Truncating at 256 instead of 512 passes all 16 similarity tests with the model present. **Fix:** check the golden vector once in `OnnxEmbedder.__init__` (0.5 s load, about 29 ms per post), failing like `ModelMissing`, and assert a 1,000-word text encodes to exactly `pin.max_tokens` ids. Or pin exact versions.
- **N4. The frozen-version error says "raise the version" even when it was raised** (ai.py:200-204). With `"version": 2` and v1's `frozen` left in place, the message misleads. **Fix:** "'frozen' in ai.json doesn't match its files: a frozen version never changes; raise the version and remove or replace 'frozen'".
- **N5. The worker's stops on an AI version mismatch aren't documented, and one isn't tested** (README.md:224-229, CHANGELOG.md:41, score.py:213-223 and :240-241). The README names the missing model and names, not a changed frozen file or answers recorded with other files. Making `live_ai` swallow `RulesFileChanged` passes all 63 score and AI tests. **Fix:** a README/CHANGELOG sentence, and a test that `live_ai` with `ai_live` on raises on a changed frozen file.
- **N6. Small test gaps:** quota detection by `code` alone passes, because the test body sets both `code` and `type` (add a body with `type` only); review-list's "named by both models" filter at `models >= 1` passes, because no test name comes from one model only.

## Questions

- **Q1 (closed here). Brief §6 listed the price table as frozen, and §8 listed `ai:xai`.** a784773 moved prices to `ai_models.json` outside the hash, and 0004 drops `ai:xai` from its CHECK. The xAI drop follows from Chris's 22:03 decision. The price move changes no pick or recorded answer: each row keeps the cost computed at the time, and only the budget caps read the file. It is disclosed in the CHANGELOG, README, `about` and the PR body. Accepted; no owner decision needed.
- **Q2 (for B2). Were row A and the review-list names built before 57257a8's N1 change?** results.md was last written at 23:12 and a784773 at 23:14; 57257a8 (23:17) changed which mention a model's own list keeps when it gives a name twice (ai.py:886). The freeze pins files, not code, so a stored answer that names one name twice can vote differently at 178bbab. Please re-map and re-vote the recorded answers with 178bbab's code, with no model calls, and confirm row A (89% / 57% / 5/5 / 5/10) and the review-list names are unchanged. If anything moves, update results.md and the PR body.

## Dropped

- The engine's own lease row, SQL and timeouts are unchanged; releasing a lost lease deletes only its own holder's row; `holder_id` is unique per process.
- The freeze is only as strong as `frozen` in the same file: the `V1_HASH` pin in test_ai.py:55 also fails CI, so changing v1 takes two deliberate edits.
- `other_files` costs one `LIMIT 1` query at worker start and per ai-pick; the sandbox rows were re-stamped and production starts empty.
- The worker halting the whole stage on a mismatch matches the rules' `RulesFileChanged` design.
- `reason.json` has no `frozen`: PR 6 is where reason lines get stored.
- `window_start` isn't enforced in ai-pick, by design, since the dev and early sets are asked too.
- With two models, round 2's N2 sort key never decides; it's harmless.
- No `cache_control` on Haiku: a picker call is about 1,500 tokens, under Haiku 4.5's 4,096-token minimum.
- The two-model vote is consistent across the code, README, CHANGELOG and PR body, and no xAI or three-model logic is left in engine/.
- Migration 0004 edited in place: unmerged and disclosed.

**Probes:** [pr-261-round-3-probes/](pr-261-round-3-probes/)
- `probes/`: `test_r3_lease.py` (N1, N2), `test_r3_freeze.py`, `test_r3_embed.py` and `test_r3_sigint.py`, with their `conftest.py`.
- `feat/`: the real-model probes (`probe_embed.py`, `probe_batching.py`, `probe_fetch.py`, `probe_draw_pairs.py`).
- `r1adapted/` and `r2adapted/`: the earlier rounds' probes against the new API.
- `mutate*.py` and `mutations*.txt`: the 52 mutants; S1's are C2-C5 in `mutations2.txt`.
- `agent-findings.md`: the agent's full write-up.

Copy the tests into engine/tests/ to run them. Don't commit them as they are, except as tests you adopt.

---

## Q2 answered by B2 (00:16): nothing moves

B2 re-mapped and re-voted every recorded answer with 178bbab's code, with no model calls. Over run 1's 500 (post, run) pairs there are 0 differences in per-model mentions, votes or market links. precision.py still gives 89% (25/28) and 57% (25/44) for the market link and 100% (5/5) and 50% (5/10) for names, and the review-list names are unchanged. results.md now says so. Q2 is closed.
