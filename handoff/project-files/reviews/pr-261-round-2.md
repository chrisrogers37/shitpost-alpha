# PR #261 "Engine PR 4: extraction and similarity": review round 2

**Reviewed:** 4554d3d. Earlier round: [round 1](pr-261-round-1.md).

| Pass | What it covered |
| --- | --- |
| Fold-in (review + verify) | a4c438f, every round-1 id, and the merges 2c1ffcc, 2af7aec and 4554d3d. 86 mutations; round 1's probes re-run and adapted; 39 new probes. |
| Features (simplify + review + verify) | B1's b494bad and 6efd98b against brief sections 4-5. The B2 thread's ba4d296 and ea66a40 for what they change; B2's completion waits for that thread. 25 mutations. |

The pinned model was fetched here through `fetch-model` and hash-checked, so the real-model tests ran.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 451/451, with no skips, twice and once more as the `engine` role.
  - Alembic has one head (0004), and the 0004 round trip works.
  - `precision.py` still reproduces rules-precision.md.
- **Merges:** clean. 4554d3d's conflict resolutions are the documented ones, and all of PR 3's a2493db is present.
- **Round 1:**
  - **Fixed:** B1, S1-S6, S8-S10, and N1, N2, N3, N6, N7, N8, N9, N11, N13 and N14. All of round 1's mutation survivors are now killed.
  - **S6's history claim holds.** On 17,948 history posts, rules v1 answers are identical before and after. With 10 AI-added tickers, the old code changed 105 posts and the new code changes 0.
  - **S7 is partly fixed:** see S3 below.
  - **Declines and partial fixes accepted:** N5, N10, N12 (k kept for the reading script), N15 (own client for the CDN redirect), C3 and the skipped simplifications. N4 moves to B2 (still no `cache_control` at 4554d3d).
  - **Questions:** Q1-Q4 are answered. The `--max-total-usd` option and the advisory lock are new; see S2.
- **B1 meets sections 4 and 5:**
  - The model pin checks out: repo, revision, four SHA-256s, MIT, CLS.
  - `fetch-model` refuses a wrong hash and writes atomically. A dropped connection or Ctrl-C leaves nothing, and only a User-Agent goes to the hub and the CDN.
  - Vectors are bitwise identical across repeats and across batch sizes 1, 2, 11 and 64. The 512-token cut is exact, and inference runs off the event loop.
  - Matching excludes the post itself and anything at or after `before`, caps at 50 and applies the threshold.
  - `python -m scripts.match_rule table` on the committed labels prints match-rule.md's table exactly, all 30 per-post rows included.
- **B2's two commits:**
  - No dev-set post overlaps the held-out sets.
  - The new prompt example isn't from a held-out post.
  - gpt-4.1's and Haiku 4.5's ids and prices match what the code charges.

**Result: changes needed.** No blocker, 7 should-fix and 14 nits. S7 belongs to B2's freeze commit.

## How to answer

- As before: fix each should-fix or decline it with a reason. Nits are optional. Send me the head with one line per id.
- S7 and the items marked (B2) are for the B2 thread's freeze commit. Pass them on, or tell me its session and I'll send them there.

**Probes:** [pr-261-round-2-probes/](pr-261-round-2-probes/)
- `fold/probes/test_probe_r2_*.py`: each passes while its finding stands.
- `fold/r1adapted/`: round 1's probes adapted to the new API.
- `fold/mutate.py` and `fold/mutations.txt`: the mutation runs.
- `feat/`:
  - `probe_embed.py`, `probe_batching.py`, `probe_fetch.py` and `probe_draw_pairs.py`;
  - `scratch-fixes.patch`: SF1's digest and golden vector, SF2's test, SF3's sort and N14's tie-break. It stays green and kills three survivors.
  - `scratch-harm-regex.patch`.
- `fold-findings.md` and `feat-findings.md`: the passes' own write-ups.

---

## Should-fix

### S1. OpenAI's out-of-credit error is retried, not fatal, so round 1's S3 batch poisoning comes back (fold)
- **Where:** ai.py:64 and 399-420. `FATAL` covers 401, 403, 404, 400 and 422, but OpenAI answers an empty balance with **429** `code: "insufficient_quota"`, and 429 is retryable.
- **Effect:** mid-batch, when the balance hits zero:
  - Every later post pays the other two models, waits 2+4+8 s, and records a two-model vote as run 1. `ai-pick` exits 0.
  - After topping up, the rerun prints "0 posts".
- **Evidence:** `test_probe_r2_fatal_gaps.py::test_openai_out_of_credit_is_retried_not_fatal_and_poisons_the_batch`, using the real SDK with a mock 429.
- **Fix:**
  - Treat `openai.RateLimitError` with `code == "insufficient_quota"` as fatal and not retryable, and adopt the probe as a test.
  - Check xAI's status for an exhausted team; a 403 is already fatal. Anthropic's low-credit error is a 400, which is already fatal.

### S2. The one-at-a-time lock is a session advisory lock, which a transaction-mode pooler breaks (fold)
- **Where:** batch.py:273-275. It runs `pg_try_advisory_lock`, then commits, and the connection sits idle for the run.
- **Problem:** behind Neon's `-pooler` endpoint (PgBouncer, transaction mode), the lock stays on whichever server connection ran that statement. That connection goes back to the pool after the commit. The engine is otherwise built to tolerate a pooler:
  - the lease is a row;
  - migrations/env.py:27;
  - README:229 points only `migrate` at the direct endpoint.

  So `ENGINE_DATABASE_URL` may well be pooled.
- **Effect:** either case can happen.
  - A leaked lock makes later runs print "another ai-pick is running" for up to PgBouncer's `server_lifetime` (3,600 s).
  - Two runs land on one backend, where session locks are re-entrant, so both pay for the same posts.
- **Evidence:** this is reasoning from documented Postgres and PgBouncer behaviour. No pooler is installed here. On a direct connection, the existing test holds.
- **Fix:** take `pg_try_advisory_xact_lock` in a transaction kept open on the lock connection for the run, rolled back at the end. A pooler pins one server connection for an open transaction, and the lock ends with it. Or use a lease row. Either way, add a README line saying which URL `ai-pick` needs.

### S3. The reason-line check still passes common direction words, and has new false rejections (fold, features; round 1's S7)
- **Where:** reason.py:18-29 (words) and :31-54 (numbers and amounts); prompts/reason.md.
- **Lines that still pass** (`test_probe_r2_reason_check.py::test_direction_or_advice_still_passes`, 20 lines), for example:
  - "Nucor could skyrocket on the tariff news"
  - "Apple shares could plummet on the tariff threat"
  - "Tariffs may send Nucor to new highs"
  - "Steel tariffs could be a boon for Nucor"
  - "A windfall for Nucor from steel tariffs"
  - "Nucor could see an upgrade after the tariff news"
  - "Nucor may dip on tariff news"
  - "Nucor stock could pop"
  - "Steel tariffs favor Nucor over importers"
  - "Steel tariffs could squeeze Nucor margins"
- **Neutral lines that are now rejected:**
  - B2's `harm\w*` and `benefit\w*` catch "Harmonized Tariff Schedule", "Harmony Gold" and "Social Security benefits".
  - "lower court", "shut down", "crack down" and "Raises questions".
  - "1500" when the post says "1,500".
  - "S&P 500", and "3M" when it's only in the instrument names.
- **Amounts:** "1.5 billion dollar" passes. reason.md now says to leave out every amount, but the check still passes numbers the post has, for example "Apple pledges 500 billion investment".
- **Fix:**
  - Commit a corpus test file of about 50 direction or advice lines and about 30 neutral lines, so every change to the list is measured.
  - Add the stems listed in fold-findings.md (skyrocket, plummet, tumble, slide, dip, pop, highs, boon, windfall, "blow to", "win for", upgrade, downgrade, favor, help, hit, squeeze, brighten).
  - Narrow `harm` to `harm(?:s|ed|ing|ful)?`; scratch-harm-regex.patch does this.
  - Compare numbers with commas removed, and allow numbers that appear in `names`.
  - Add `dollars?|billion|million|trillion|bn` to the amount pattern.
  - Make the check and reason.md agree on amounts.
- Nothing calls `reason_line` until PR 6. If you'd rather carry this into PR 6, decline it here and I'll ask the planner to put it in PR 6's brief.

### S4. The model version covers only the repo and revision, not the rest of the pin (features, B1)
- **Where:** similarity.py:52-55, against model.json's own note that "changing anything here changes the model version".
- **Problem:** `max_tokens`, `pooling`, `dims` and the file hashes aren't part of the version. Changing any of them stores new vectors under the old version, and two things follow:
  - `embed` skips every post;
  - `load_match_rule`'s model-version guard never fires, so 0.85 applies to vectors it wasn't read on.
- **Evidence:** mutations M13 (`max_tokens` 512 → 256) and M14 (mean pooling) pass every test.
- **Fix:**
  - Append a short digest of `[files, pooling, max_tokens, dims]` to the version, update `match_rule.json`'s `model_version`, and re-embed the sandbox copy.
  - Add a golden-vector check to the real-model test. The values are in feat-findings.md and in the scratch patch.
  - Consider upper bounds on `onnxruntime` and `tokenizers` (pyproject.toml:16 and 22), since a tokenizer change re-encodes silently.

### S5. Match rule v1's threshold isn't tied to its reading, and nothing pins the file (features, B1)
- **Where:** match_rule.json:5; test_similarity.py:223-226 accepts any threshold from 0.7 up to 1.
- **Effect:** editing 0.85 to 0.80 keeps CI green (M8 survives), and PR 5 backtests a rule nobody read.
- **Fix:**
  - Split `scripts/match_rule.py:table()` into `counts()` and `pick_threshold()`, and assert that the loaded threshold equals `pick_threshold(*counts())` on the committed match-labels.csv. This is in the scratch patch.
  - Optionally hash-pin match_rule.json and match-labels.csv next to the model pin.

### S6. `embed` pads each batch of 64 to its longest post: 4 GB peak and about 4x the time (features; Part A code that B1's run uses)
- **Where:** batch.py:111-114 builds batches in post-time order, and similarity.py:142's `enable_padding()` pads every post to the batch's longest.
- **Evidence:** on 303 real posts plus 3 long ones:

  | Order | Time | Peak RSS |
  | --- | --- | --- |
  | Time order | 60.1 s | 4,079 MB |
  | Length order | 14.3 s | 1,841 MB |

  The vectors are bitwise identical either way.
- **Effect:** in PR 7, `embed` on a service with less than about 4 GB is OOM-killed on the first batch with a long post. It resumes at the same batch and dies again, for ever.
- **Fix:**
  - Sort `todo` by length before batching (one line, in the scratch patch).
  - Better still, also cap tokens per batch.

### S7. Nothing pins a frozen AI version's content, and the guard can't see per-model rows (features and fold; B2's freeze commit)
- **Where:**
  - ai.json:2-10.
  - batch.py:230-242: `other_prompt` checks only `ai:vote` rows.
  - ai.py:637-649: only the vote carries `picker_hash`.
- **Problem:** every edit to version 1's files moves the hash in ai.json while the version stays 1. That's fine until the freeze, but nothing stops it afterwards. M23 (Haiku input price $1 → $3, rehashed) passes 92 tests.
- **More problems:**
  - b2/results.md says v1 is frozen with votes "rebuilt" under its hash from per-model rows recorded under earlier hashes, and the guard can't tell them apart.
  - At 4554d3d, xAI is still pinned and `window_start` is null.
  - The hash also covers reason.md and the prices, which don't change picks, so fixing either forces a version bump (fold N-6).
  - The live stage doesn't check the guard at all.
- **Fix, in the freeze commit:**
  - Record `"frozen": "<sha256>"` in ai.json and have the loader refuse a mismatch.
  - Write `picker_hash` into every `ai:<provider>` row and check those rows too.
  - Have `live_ai` log or refuse on a mismatch.
  - Consider giving the reason line its own pinned version.
  - Have `problems()` report a missing `window_start`, and parse it as a New York midnight, not a naive one (ai.py:202).

## Nits (optional, file:line at 4554d3d)

- **N1. Each model's own name list keeps the first mention of a name, not the mapped one** (ai.py:833-835; fold). This is B1's pattern inside one answer: a model that lists "Some Chip Firm" first without a ticker and then with NVDA loses the mapped one. In the probe, NVDA is named by all three models and counted by none. **Fix:** sort with the vote's key before `unique_names` (`test_probe_r2_per_model_dedup.py`).
- **N2. When nothing is counted, the vote's sort drops the "named by two or more models, not mapped" row** that review-list reads (ai.py:703; fold). **Fix:** use the sort key `(not counted, -(models or 0), instrument_id is None)` (`test_probe_r2_vote_dedup.py`).
- **N3. A provider's 400 on one post's content stops every rerun at that post** (ai.py:403 and 408, batch.py:347-349; fold). **Fix:** treat a 400 or 422 as fatal only on a run's first post or for account-level codes, and otherwise record it as that model's failure. Or name `--keys` / `--from` in the stop line.
- **N4. Fixes and paths with no test** (fold and features):
  - N8's `finished` after `pick()` (score.py:99).
  - N9's ticker as the instrument name (score.py:64).
  - N11's `--window-start` path (scripts/precision.py:199). The mutant leaves an `UnboundLocalError`, and no test runs it.
  - Seeded instruments counting as reviewed (rules.py:344).
  - A dropped CDN download leaving nothing behind.
  - A second embedder version re-embedding posts that have only the first version's vector.
- **N5. Small leftovers** (fold):
  - A new ticker is checked with Alpaca twice: score.py:62, then instruments.py:190.
  - `--max-total-usd` has no default (cli.py:63-67). A default of 15 for v1, or a README line, would cover PR 4's budget.
- **N6. One held-out post was read while setting the match rule** (precision/match-labels.csv:256; features). It has no effect, since the labels and pickers came first. **Fix:** have `draw_pairs` skip `precision_*` keys.
- **N7. `scripts/match_rule.py pairs` overwrites the labelled file** (:98-101). Refuse when any `same` is set, or take a path.
- **N8. match-rule.md's history numbers come from no committed code** (39.6% with a match, median 2, p90 14, 0.9% at the cap). Also, a 0.74997 score prints as 0.7500 in the 0.70 band. **Fix:** add a `coverage` subcommand, and write `.6f`.
- **N9. ONNX Runtime sizes its threads to the host, not the container, and its threads spin** (similarity.py:143-145). A short post takes 8.6 ms with 1 thread against 15.1 ms by default. **Fix:** set `intra_op_num_threads` (a setting) and turn spinning off for the live worker.
- **N10. Model files are saved 0600, and a SIGKILL leaves `tmpXXXX` files of up to 133 MB** (similarity.py:204, 220). If `fetch-model` and the worker run as different users, the worker dies with a `PermissionError` traceback. **Fix:** chmod 0644 before the replace, and clean up `.part-` files.
- **N11. Emoji-only posts all share one vector**, so each matches every earlier one at 1.0. None of the 300 precision posts is emoji-only. **Fix:** treat them as "without words", or note it for PR 5.
- **N12. The `dev_market` draw depends on rules v1 and the names table** (scripts/samples.py:62-68, 92-94; B2). Assert it, or say so in the docstring.
- **N13. Ties at the 50 cap aren't deterministic** (similarity.py:271). **Fix:** add `signal_key` to the order. This is in the scratch patch.
- **N14. Duplicate test setup** (test_ai.py:79, 198 and 281): three copies of the "without xAI" config. Use one helper; it's in the scratch patch.

## Questions

- **Q1. Is 0.85 the right threshold?**
  - The 0.85 band is 26/32 (Wilson interval 65-91%), so one call the other way moves it to 0.90. match-rule.md lists the five generous calls.
  - `pairs` takes 3 pairs per post per band, so posts with many neighbours, such as templated endorsements and slogans, are under-weighted against what PR 5 serves with up to 50 matches.
  - Could match-rule.md show a match-weighted share next to the per-post one?
- **Q2. Is the match rule left for PR 5 to wire up?** Nothing outside tests loads it. If so, say so in the PR, and have PR 5 call `similar(..., min_score=rule.threshold, k=rule.max_matches)`.
- **Q3 (B2). What will the freeze commit change?** results.md describes v1 with two models and the window at 2025-11-01, while 4554d3d has three providers and `window_start: null`. What happens to the sandbox rows recorded under pre-freeze hashes? See S7.
- **Q4 (for PR 7). Should live AI failures raise an operator notice?** With `ENGINE_AI_LIVE` on, an empty account or revoked key degrades every live vote with only a warning log. For example, a count of failed `ai:<provider>` rows per hour.
- **Q5 (B2).** Grok 4.20's prices and cutoff couldn't be checked offline. It's comparison-only under option A.

## Dropped

- **Cashtags of AI-added tickers:** only 5 of 17,948 history posts have a cashtag, and none counts.
- **FATAL rollback:** the stopping post's rules row and any new instrument roll back with it. Its two good answers go unrecorded, which is at most 2 calls and documented.
- **The advisory lock on a direct connection:** a cancel or kill releases it, and the test holds.
- **`--max-total-usd` counting from a snapshot:** the overshoot is at most one post's three calls, and this is documented.
- **The partial index:** the worker's `IN ('score')` query uses it for literal and custom plans.
- **The reason prompt's 100 characters against the check's 120:** deliberately stricter than the brief.
- **The UTC versus New York window in samples.py:** no window or dev post falls in the 4-hour gap.
