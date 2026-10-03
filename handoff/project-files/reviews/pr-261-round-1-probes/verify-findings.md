# PR #261 (Engine PR 4: extraction and similarity), round 1: verify-completion

Judged: df77049 (PR 4's own changes = `git diff 56a32f7 df77049`, 46 files), against Part A of
`/mnt/project-files/build-briefs/engine-pr4.md`. Checkout: `$SP/verify-261-r1-wt` (clean).
Mutation checkout: `$SP/verify-261-r1-mut` (clean, restored after every mutation).
Probes and logs: `$SP/review-261-r1/verify/`.

**Note:** the PR's live head has moved past df77049 to 6a24a0b (b494bad "B1: pin the similarity
model; match-rule loader", 6a24a0b a test-timing fix; CI green on 6a24a0b). This pass judges
df77049 only. The PR body still lists B1 as not done. That is right for df77049, but b494bad
has started B1 since.

**Verdict:** Part A is done and works. Every Part A command, table, rule, test and doc line
in the brief is there. Lint, format, strict mypy, three full test runs, CI on df77049 and the
migration round-trip are all green. The rules precision table reproduces exactly from the
committed code and labels. The git history shows the labels came before any picker code. B1
and B2 are listed as not done, and nothing claims them except a little CHANGELOG and README
wording (V9). No blockers. There are 4 should-fixes: paid AI answers are lost on an Alpaca
error, a deploy without `sync-names` sends live posts to `error`, the reason-line check
misses common direction words, and 8 safety properties have no test.

---

## 1. Part A checklist

Status: done / partly / missing. Paths are under `engine/` at df77049 unless noted.

### Topics (section 1)
| Requirement | Status | Evidence |
| --- | --- | --- |
| Versioned data file like the collision list: 8–12 topics + `other`; each has id, name, one-line description, market flag, keyword and phrase rules | done | `engine/extract/topics.json` (12 topics + other, each with `any`/`none` phrases); `parse_topics` enforces 8–12, unique ids, `other` last with no rules, market topics first (`engine/extract/rules.py:140-163`); test `test_topics_file_rules` (`tests/test_rules.py:176`) |
| One topic per post: first match in file order, market first, else `other` | done | `choose_topic` `rules.py:453-460`; `test_topic_priority_and_other` `tests/test_rules.py:145-158` |
| Drafted from ≥400 text posts, fixed seed, Feb 2022–now, excluding the 300; PR says how many and what merged | done (as claimed) | `scripts/samples.py` (SEED 20261002, set `topics` = 400, drawn after and disjoint from the 300; I checked that all 830 keys are unique); PR body "Topics" table gives 400 posts and what each topic merged. The reading itself can't be checked from git. |
| Topics are rules-only; the AI returns a market link and names, no topic | done | `extract/ai_picker.json` schema (`market_link`, `instruments` only) |

### Name rules (section 2)
| Requirement | Status | Evidence |
| --- | --- | --- |
| Cashtags | done | `CASHTAG` `rules.py:376`, `find_names` `:387-400`; `test_a_cashtag_counts` |
| Bare tickers: instrument in `engine.instruments`, ≥2 letters, not on the collision list | done | `BARE_TICKER` `rules.py:377`, `:401-415`; `test_a_bare_ticker_counts`; mutation M15 killed |
| Name aliases case-insensitive on word boundaries (Apple ≠ pineapple); Bitcoin→BTC, Ethereum/Ether→ETH | done | `_phrase_pattern` `rules.py:60-70`; `test_names_match_on_word_boundaries`; M16 killed |
| No implied names in the rules | done | `rules.py` finds cashtag/ticker/alias only |
| Aliases drafted by reading; each US-listed one added with PR 3's add function; private/foreign-only/delisted unmapped | done | `extract/aliases.json` (61 instruments, 14 unmapped groups with reasons); `sync_aliases` uses `add_instrument`/`add_alias` (`engine/extract/names.py:42-59`) |
| Aliases as a versioned data file, synced idempotently into `engine.instrument_aliases` | done | `python -m engine sync-names`; `test_sync_names_is_idempotent_and_loads_the_book` |
| Collision list extended from reading bare uses | done (as claimed) | `market/collisions.json` v2 adds AMD, BA, DE, DJT, SPY |
| One rules version over the 3 files, recorded on every extraction, frozen v1 | done | `extract/rules.json` pins all 3 by SHA-256 (hashes match: I recomputed them); `load_rules` refuses a mismatch (`rules.py:200-219`); `extractions.version`; `test_a_changed_rules_file_is_refused`; M14 killed |

### Precision sample (section 3)
| Requirement | Status | Evidence |
| --- | --- | --- |
| 300 drawn first with a fixed seed: 200 from 2025-11-01 to newest, 100 from 2022-02-01 to 2025-10-31, text posts only | done | 84b6602 (19:43) comes before everything else in the PR; `samples.py` `draw()`. Window posts run from 2025-11-01 16:43 NY to 2026-09-28; early posts from 2022-05-18 to 2025-09-28 |
| Held out from drafting and prompt writing | done (by history) | the rules files are unchanged from f442395 to df77049 (empty `git diff --stat`); prompt files are unchanged since they first appeared in 997fe4c; the dev set is drawn from before the window |
| Label guide in the repo | done | `precision/label-guide.md` |
| Labels: market link, topic, names explicit/implied; ids and labels only | done | `precision/labels.csv` (key, market_link, topic, names; no text). Its keys are exactly the 300 `precision_*` keys |
| Labels committed before any precision run | done | see §4 |
| Precision/recall with Wilson intervals; post level and name level; explicit and implied apart; per group; rules in Part A | done | `scripts/precision.py`; `tests/test_precision.py`; table reproduced exactly (§3) |
| AI vote and each model (B2) | code done, numbers not done (B2) | `precision.py` scores `ai:vote`, `ai:openai`, `ai:xai`, `ai:anthropic` once their rows exist |
| Spot-check CSV with id, text, labels, both pickers' output | done | `/mnt/project-files/engine/pr4/precision-sample.csv`: 300 rows; AI columns empty until B2 |

### Similarity (sections 4–5: B1). Part A builds the code only
| Requirement | Status | Evidence |
| --- | --- | --- |
| Model pin, `fetch-model` (httpx, follows redirects, hash check, hosts reported), `embed`, CLS + normalise, 512-token cut counted, one normalising function | code done; pins and runs not done (B1, listed) | `extract/similarity.py`, `extract/model.json` (revision and hashes `null`), `engine/text.py`; download tests use a mock hub; real-model test skipped |
| `signal_embeddings` (one per post per model version, text hash) | done | migration `0004` `:87-101`; `test_one_vector_per_post_and_model_version` |
| `similar()`: excludes self and posts at/after `before`, ≤50, threshold, best first; 40,000 vectors well under 100 ms | done, with two gaps | `similarity.py:236-249`. I measured 1.2 ms median. The boundary "at `before`" has no test (M24 survived), and `k` isn't capped at 50 (V7) |
| Match rule (B1) | not done (listed) | — |

### AI picker (section 6): code in Part A
| Requirement | Status | Evidence |
| --- | --- | --- |
| Official SDKs; xAI through the `openai` SDK at `https://api.x.ai/v1`; 15 s per call; live calls run side by side | done | `ai.py:52-56`, `:223-344`, `:743-748` (`gather`); checked by hand against the fake server: each provider got its own path and key header |
| Input: post text plus quoted text when the engine has it; no date, engagement or prices | done | `PostText` `ai.py:640-652`, `quoted_words` `score.py:74-81`; `test_the_quoted_post_goes_in_the_message`, and the quote case in `test_with_stub_ai_on_...` |
| Strict JSON output (`market_link`; ≤8 instruments with name, ticker\|null, asset, link, why ≤100) | done | schema in `ai_picker.json`; `parse_answer` `ai.py:415-441` (cuts to 8, `why` to 100); `test_an_answer_is_checked_field_by_field` |
| What to name / implied first-order / no index funds | done | `prompts/picker.md`; `INDEX_FUNDS` `ai.py:59`; M12 killed |
| Fixed instructions first (prompt caching) | done (order); see Q2 | system prompt sent first |
| Temperature 0, output cap | done | `ai_picker.json` settings (800 tokens); the fake server saw `temperature 0.0` and `max_tokens 800` from all three |
| Stability reruns stored without overwriting | done (storage); the share is B2 | `--run 2`; `test_ai_pick_records_answers_and_a_rerun_...`; by hand: run 2 gave 20 new rows and no new mentions |
| Vote: 2 of 3; one failed → the other two must agree; two failed → rules + `ai_fallback`; batch retries 429/5xx; timeouts not retried | done | `vote` `ai.py:590-634`, `ask_model` `:451-493`; 5 vote tests; M6, M7, M8 killed; by hand, a 17 s fake xAI answer was recorded as `timeout after 15 s` and the vote stood on the other two |
| Mapping through the same aliases/collisions; a collision ticker needs its name; a new ticker added only if it counts at the post's time; unmapped kept with a reason | done, partly pinned | `map_item` `ai.py:503-546`; M9 killed, but M10 and M11 survived (V4) |
| `review-list` | done | `batch.py:286-325`; by hand it printed `NUE 'nucor' (ai_implied): 1 posts` |
| Frozen AI picker v1 with its hash: prompt, schema, model ids, settings, price table with checked dates, window start | structure done; values are B2 | `ai.json` pins 3 files; `AiConfig.hash`; xAI model, prices' `checked` and `window_start` are `null` (B2). No test refuses a changed AI file (M13 survived) |
| Keys only from `ENGINE_*`, passed explicitly; no key, no client; keys never logged | done | `build_clients` `ai.py:347-365`, `scrubbed` `:368-372`; M1–M5 killed; by hand, the fake server's 401 that echoed the key was stored and logged as `[key]`, and no fake key appeared in any log, error or response column |

### Reason line (section 7): code in Part A
| Requirement | Status | Evidence |
| --- | --- | --- |
| One designated model (default Anthropic); ≤120 chars; input = text, topic, names; versioned prompt | done | `ai_picker.json` `reason` block; `reason.py`; `prompts/reason.md` pinned in `ai.json` |
| Never a direction, price, target or advice; a rule check rejects these | partly | `check_reason` `reason.py:210-235` misses common direction, price and advice phrasings (V3) |
| On a timeout (15 s), an error or a rejected line it returns nothing | done, partly pinned | `reason.py:252-267`; no test covers the timeout (M30 survived) |

### Records (section 8)
| Requirement | Status | Evidence |
| --- | --- | --- |
| `engine.extractions`: one row per signal, method and version (+ run); model, started/finished, raw body, result, `market_link`/`topic` columns, three token counts, cost, error; never overwritten | done | `0004_extraction.py:21-47`, `tables.py`; `record` `records.py:132-183` (`ON CONFLICT DO NOTHING`); M18 killed |
| `engine.signal_mentions`: name as written and normalised, ticker, instrument or unmapped reason, found_by, models, counted, post time; index on (instrument, post time) | done | `0004:48-86`, with check constraints; `test_the_mentions_index_exists` |
| Add-then-remove migration; grants only in `engine` | done | 0004 adds tables only; upgrade → downgrade → upgrade worked (§2); the PR 1 grant step covers all `engine` tables |

### Live `score` stage and batch (section 9)
| Requirement | Status | Evidence |
| --- | --- | --- |
| Handler registered: rules + mentions, embedding, AI only with `ENGINE_AI_LIVE` (off by default); then `done` | done | `score.py:116-193`, `registry.py`; by hand: 8 live posts went from `score` to `done` with rules, vectors and (AI on, fake providers) 3 answers + vote. The "AI off by default" test passes for the wrong reason (M22, V4) |
| Missing model files → the stage fails with a clear error | done | by hand, `run` with only the score worker logged `ModelMissing: the similarity model isn't pinned yet: ...` plus one `operator notice [worker_failed]`, and posts stayed at `score` |
| History never goes through the live stage | done | imported posts are stored at `done` |
| `extract`: rules over all text posts, idempotent per version | done | by hand: 12 posts, then 0; on the CC0 copy 17,750 in 20 s, then 0 |
| `embed` idempotent and resumable | code done (needs B1 to run) | `batch.py:85-125`; M34 killed; by hand it refuses in one line (model not pinned) |
| `ai-pick`: ids or a date range, projected cost first, refuses over `--max-usd` (default 5) | done | `batch.py:210-280`; by hand it printed the projection first; M20 and M21 killed |

### Replay harness (section 10)
| Requirement | Status | Evidence |
| --- | --- | --- |
| Test-only; recorded posts through the store path and `score`, with stub AI (fixed answers per post) and a stub or real embedder; reports outputs and step timings; one dry-run delivery hook; uses PR 2's CNN and trumpstruth fixtures | done | `tests/replay.py`; `test_the_replay_harness_runs_recorded_posts` |

### How-to-check tests (brief list)
All present: rules (6), AI mapping (4), vote (5), keys, embedding with stubs plus the real-file test (skipped), matching (4, incl. speed), records (3), stage and replay (4), cost guard. File references: `tests/test_rules.py`, `test_ai.py`, `test_similarity.py`, `test_score.py`, `test_batch.py`, `test_precision.py`.

### Deliverables
| Requirement | Status | Evidence |
| --- | --- | --- |
| Branched from PR 3's branch; draft PR titled as asked, saying it goes in after #258/#259/#260 | done | PR #261 is a draft; its first line gives the merge order |
| Body: Before / After / How / testing / results / not done | done | PR body. Its Part A results are the topic list, the reading notes, the label guide summary, the rules precision and the rules over history |
| CHANGELOG entry under [Unreleased] | done | `CHANGELOG.md:33-41` (`### Added` under `## [Unreleased]`); some wording overclaims (V9) |
| Outputs in `/mnt/project-files/engine/pr4/`; no post text committed | done | 3 files there; `samples.csv` and `labels.csv` hold ids only |
| Old system untouched (api/, frontend/, root railway.json, railpack.json) | done | diffstat: only `CHANGELOG.md` and `engine/**` |

---

## 2. Command results (fresh, at df77049, every secret variable unset, ALPACA keys unset too)

| Command | Result |
| --- | --- |
| `ruff check .` | `All checks passed!` (rc 0) |
| `ruff format --check .` | `89 files already formatted` (rc 0) |
| `mypy` (strict, per pyproject) | `Success: no issues found in 84 source files` (rc 0) |
| `pytest` run 1 (role shitpost) | `382 passed, 1 skipped in 169.86s` (the skip is the real-model test) |
| `pytest` run 2 (role shitpost) | `382 passed, 1 skipped in 160.67s` |
| `pytest` as superuser role `engine` (CI's name; `test_migrate.py` relies on that role's search path) | `382 passed, 1 skipped in 163.74s` |
| `alembic heads` | `0004 (head)`, one head; the chain is 0001→0002→0003→0004 |
| On throwaway DB `verify261_mig`: `migrate`; `alembic downgrade 0003`; `upgrade head`; `downgrade 0003`; `upgrade 0004` | all rc 0; the 3 tables and 6 indexes/constraints went away and came back each time |
| GitHub CI on df77049 (`engine` run #25) | success. CI on the current head 6a24a0b is also green; run #29 on b494bad failed and was fixed by 6a24a0b (after df77049) |

Logs: `review-261-r1/verify/pytest_run1.txt`, `pytest_run2.txt`, `pytest_engine_role.txt`.

---

## 3. By-hand results (throwaway DBs, all dropped)

Every outbound request went to a local trap proxy on 127.0.0.1:18999 (`HTTPS_PROXY`/`HTTP_PROXY`).
Its log stayed empty: nothing tried to reach Alpaca, Hugging Face, the AI hosts or the feeds.
AI calls went only to a local fake provider on 127.0.0.1:18998 (`fake_ai.py`). The real SDK
clients were used, with their base URLs pointed at 127.0.0.1 inside the probe process, fake
`ENGINE_*` keys, and the tests' `ready_config()`. Names were seeded with the tests' stub
listings (no Alpaca).

**`verify261_hand`** (fixtures only: the CC0 and CNN archive slices as history, then trumpstruth's feed and CNN's head through the live store path):
- `migrate` rc 0. `status` before any posts: `signals by stage: none yet`; after seeding: `done 17, score 8`.
- `sync-names` with no Alpaca keys: rc 1, but it prints a **full traceback** ending in `AlpacaKeysMissing` (V5). The transaction rolled back, so nothing was half-written.
- `extract` before names are synced: rc 1, **traceback** ending in `NamesNotSynced: 62 names ... run python -m engine sync-names` (V5).
- After seeding names: `extract` gave `rules v1: extracted 12 posts`; a rerun gave `extracted 0 posts` (12 rows, idempotent).
- `embed`: rc 1 with one line, `the similarity model isn't pinned yet: no commit pinned; ...`. `fetch-model`: the same line, rc 1, and no network attempt.
- `ai-pick` with no selection: `choose posts: --keys or --from (and --to)`, rc 2. With a date range: `AI picker version 1 isn't ready: openai: price not checked; xai: no model pinned; ...`, rc 2. `--from 2025-13-01`: argparse error, rc 2. `--keys /nonexistent`: **traceback** `FileNotFoundError` (V5).
- `review-list` with no AI rows: the two header lines, rc 0.
- `run` with only the real score worker (no feeds): `worker score failed` → `ModelMissing ...` → one `operator notice [worker_failed]`, then backoff; a clean stop on SIGINT; posts stayed at `score`.
- Score worker with the stub embedder, AI off: 8 → 0 waiting at `score`; `status` showed `done 25`; 8 stub vectors; rules rows stayed at 12 (no duplicates).
- **AI through the CLI** (`ai-pick --keys`, with Alpaca as built, no Alpaca keys): it printed the projection, then the Apple post was answered and recorded (3 + vote). The Nucor post's 3 answers were made (6 fake-server calls in all), then mapping the new ticker NUE raised `AlpacaKeysMissing` and the command died with a traceback. **That post's three answers and their costs were never recorded** (V1).
- **AI through `run_ai_pick` with stub listings**, 4 remaining posts: OpenAI's 401 (key echoed back) was stored and logged as `... Incorrect API key provided: [key]`. The SLOWXAI post's xAI answer was recorded as `timeout after 15 s`, and the vote counted AAPL from the other two (`models 2`). NUE was added and counted (`ai_implied`, models 3). A rerun gave `0 posts` and 0 calls. `--run 2` made 20 new rows and 0 new mentions. `review-list` printed `NUE 'nucor' (ai_implied): 1 posts`. The string `NOT-REAL` (the fake keys) appears in no log, error or response.
- **Live with `ENGINE_AI_LIVE=true`** (fake providers, stub embedder): 5 new live posts all reached `done`, each with rules, 3 model answers, a vote and a vector. Errors were scrubbed the same way.

**`verify261_nosync`** (live fixtures, `sync-names` never run): the score worker took each of the 9 live text posts through 3 failed attempts (`NamesNotSynced`). All 9 ended in terminal **`error`**, with 9 operator notices (V2).

**`verify261_cc0`** (offline: the CC0 archive copy already on disk from an earlier review, commit 40a8834, 29,469 items): `extract` took 17,750 text posts in 20 s, and a rerun extracted 0 (6 s). 102 of the 300 labelled posts are in this copy (all 100 early, 2 window). For all 102, the rules answers recorded in the database (read through `scripts/precision.py`'s own `answers()`) and the stored text **match the builder's spot-check file exactly**. `history_report.py` ran (rc 0). `precision.py` on this partial DB exits with one line, `198 labelled posts aren't in this database`, rc 1.

### Reproducibility of the builder's numbers
- **Rules precision table (`rules-precision.md`, PR body, CHANGELOG): reproduced exactly.** `repro_precision.py` ran the committed rules picker over the text of all 300 posts in `precision-sample.csv`. Post times came from their status ids, and the name book was built from `aliases.json` plus the seeded SPY and QQQ. It got **0 of 300 answers different** from the file's `rules v1` columns. The labels and groups in the file equal `labels.csv` and `samples.csv`. Scoring with `scripts/precision.py`'s `score()` gives a table that is **byte-identical** (`diff` clean) to `rules-precision.md`. The PR body's counts (53 posts with a market link, 11 with names, 10 + 7 labelled names) match `labels.csv`.
- **Rules over all history (`rules-history.md`, 21,610 text posts, 12.7%)**: can't be reproduced offline. It needs CNN's live file, which this session must not fetch, and `shitpost_dev` is empty in this sandbox. It is internally consistent: the topic counts sum to 21,610, and the market topics sum to 2,732 (12.6%), so 12.7% needs only a couple of named-instrument posts outside market topics. The same script on the CC0 copy gives 10.5% against a market-topic sum of 10.46%. The PR's timing claim (26 s for all history) fits my 20 s for 17,750 posts.
- `samples.py`'s draw can't be redone without the full history either. I checked only that the sets are disjoint and that the 300 are exactly the labelled keys.

---

## 4. Held-out discipline (git)

| Commit | Time (UTC) | Content |
| --- | --- | --- |
| 84b6602 | 19:43:30 | `samples.py`, `samples.csv` (the 300 + dev, topics and match sets), `text.py` |
| f442395 | 20:01:51 | rules v1 files (topics, aliases, collisions v2, `rules.json`) + `label-guide.md` + `labels.csv` |
| 997fe4c | 20:34:41 | first picker code (`rules.py`, `ai.py`, prompts, ...), tests |
| efaae40 | 20:43:02 | `scripts/precision.py`, `history_report.py` |
| (files) | 20:38 | `/mnt/project-files/engine/pr4/*` written |

- The labels came before any picker code (997fe4c) or precision script (efaae40), and before the results files (20:38).
- The rules data files are byte-identical from f442395 to df77049, so nothing was tuned after labelling. The prompt and AI config are unchanged since they first appeared in 997fe4c, and they come after the labels.
- What git can't show is whether the 400 / dev reading avoided the 300. That they were drawn as disjoint sets is shown. Whether the rules or prompt were drafted while looking at the 300 before labelling isn't knowable from history.
- The rules' low name recall on the 300 (40% / 14%) argues against over-fitting.

---

## 5. Mutation results (35 mutations; each reverts one guard, runs the related tests, and is restored)

Killed (a test failed): M1 no client without a key, M2 key passed explicitly, M3/M4 hosts pinned against `*_BASE_URL`, M5 key scrubbing, M6 timeouts not retried, M7 2 of 3, M8 rules fallback, M9 AI collision ticker needs its name, M12 index funds, M14 rules hash refusal, M15 bare collision ticker, M16 word boundaries, M17 FB/META date boundary, M18 never overwrite, M19 run 2 writes no mentions, M20 cost-guard refusal, M21 stop once over, M23 `ai_live` default off, M25 self excluded, M26 threshold, M27 `fetch-model` hash refusal, M29 reason direction words, M31 reason length, M34 `embed` resumable, M35 `extract` per version.

M28 (the score worker fails on a missing model): detected only as a **hang**. `test_missing_model_files_stop_the_worker...` awaits the worker with no timeout, so a regression hangs the suite instead of failing it. I stopped the hung run by hand.

**Survived: these properties have no test**
| Id | Property | Code at df77049 |
| --- | --- | --- |
| M10 | the AI never adds a new ticker that is on the collision list | `ai.py:540-541` |
| M11 | a new AI ticker is checked to count **at the post's time** (passing `now` instead passes every test: `CountsAll` ignores `at`) | `ai.py:542` |
| M13 | AI picker files (prompt, config, reason prompt) are refused when their hash changes | `ai.py:159-165` |
| M22 | the live AI is off unless `ENGINE_AI_LIVE`: `test_the_ai_is_off_by_default` passes only because `ai_picker.json` isn't ready yet | `score.py:156-157`, test `tests/test_score.py:394-403` |
| M24 | matching excludes a post made exactly at `before` (`<` vs `<=`) | `similarity.py:244` |
| M30 | the reason line is dropped on a 15 s timeout | `reason.py:254` |
| M32 | quoted text goes to the AI only for a quote (a reply's parent text would also be sent) | `score.py:76` |
| M33 | the live stage doesn't use batch retries | `score.py:146-148` |

Script and full output: `review-261-r1/verify/mutate.py`, `mutations.txt`.

---

## 6. Findings

### Blocker
None.

### Should-fix

**V1. Paid AI answers are lost, with no record of their cost, when mapping a new ticker fails.**
- *Where:* `engine/extract/score.py:43-53`, `engine/extract/ai.py:756-761`, `engine/extract/batch.py:256-275` (live: `score.py:144-148`).
- *Problem:* `new_ticker_adder` catches only `DoesNotCount`. Any other error from `add_instrument` (Alpaca keys missing, an Alpaca 5xx or 429 after its retries, a dropped connection) leaves `map_item`, which runs after the three model calls. The post's transaction then rolls back, and the three paid answers and their `cost_usd` are never recorded.
- *Effect:*
  - `ai-pick` dies with a traceback.
  - "Spent so far" (the brief's $15 tracking is "from the recorded costs") undercounts.
  - A rerun pays again.
  - Live with the AI on, the stage retries the post up to `max_attempts`, paying each time, and then moves it to `error`.
- *Evidence:* the by-hand CLI run (§3). There were 6 provider calls for 2 posts, only the first post's rows exist, the recorded spend was $0.007290 (the Nucor post's ~$0.0073 is missing), and the run ended in `AlpacaKeysMissing` with a traceback.
- *Fix:*
  - In `new_ticker_adder`, catch `AlpacaError` (and `httpx` errors) and return an unmapped reason such as `count_check_failed`, logged.
  - Alternatively, record the three model answers before mapping (their own transaction, or a savepoint).
  - Add a test with a `Listings` stub that raises.

**V2. A deploy that skipped `sync-names` sends every live text post to the terminal `error` stage.**
- *Where:* `engine/extract/score.py:126-134` (`load_book(conn, self.rules)` with its sync check, per post) and `score.py:177-191` (no check at worker start).
- *Problem:* `NamesNotSynced` is raised inside the stage handler. Each post burns `max_attempts` (3) and lands in `error`, with one operator message per post. The brief wants a misconfigured deploy to show up. For the model this PR does it by failing the worker at start so posts wait at `score`; unsynced names are the same kind of misconfiguration but consume the posts instead.
- *Evidence:* `verify261_nosync` (§3): 9 live posts went to `error` with 3 attempts each and 9 notices.
- *Fix:* check the book once when the worker starts (`load_book(..., check=True)` next to `load_embedder`), so the worker fails and posts wait. Keep the per-post load without the check, or reuse the book. Add a stage test with names unsynced.

**V3. The reason-line rule check lets common direction, price and advice wording through.**
- *Where:* `engine/extract/reason.py:210-235`.
- *Problem:* the brief says the line "never states a direction, a price, a target or advice. A rule check rejects lines that break this". These all pass `check_reason`:
  - "Steel tariffs could send Nucor higher"
  - "Tariffs may push Apple stock lower"
  - "Nvidia could go up after the chip deal"
  - "Tesla may go down ..."
  - "Oil prices may increase ..."
  - "Boeing orders could double ..."
  - "A headwind for Apple ..."
  - "A tailwind for US steel makers"
  - "Expect Nvidia to outpace rivals"
  - "Apple at 200 after the tariff news" (a price with no `$`)
  - "Investors may want to watch Boeing" (advice)
- *Evidence:* the probe in §3 printed `None` (accepted) for each line.
- *Fix:*
  - Add the comparatives and verbs (`higher|lower|up|down|increas\w*|decreas\w*|rais\w*|doubl\w*|halv\w*|headwind|tailwind|outpac\w*|beat\w*|watch|investors?`).
  - Reject bare numbers next to an instrument name, or all numbers not in the post.
  - Add the lines above as test cases.
  - Since PR 6 ships it, this can wait for PR 6 if the planner prefers, but the check belongs to PR 4's scope.

**V4. Eight safety properties have no test (mutation survivors, §5).**
- *Where:* M10, M11, M13, M22, M24, M30, M32 and M33, at the lines in §5.
- *Most important:*
  - **M22:** "the AI is off by default" is pinned only by accident, because the AI config isn't ready yet. The test should use `ready_config()` (monkeypatch `current_ai_config`) with keys set and `ai_live` false.
  - **M11:** "counts at the post's time" is untested, because `CountsAll` ignores `at`. Use a stub that counts only for a given date range.
  - **M13:** a changed `picker.md`, `ai_picker.json` or `reason.md` must be refused, as the rules' test does.
- *Also:*
  - M24: add a post exactly at `before`.
  - M30: a slow reason client gives `None`.
  - M10: a collision ticker not yet in the book gives `collision_without_name`, with `add_new` never called.
  - M32: a reply's parent text is not sent.
  - M33: live doesn't retry.
  - Give `test_missing_model_files_stop_the_worker_and_posts_wait_at_score` an `asyncio.timeout`, so a regression fails instead of hanging (M28).

### Nit

**V5. New commands print tracebacks for expected operator errors.**
- *Where:* `engine/engine/cli.py:110-133`.
- *Problem:* `sync-names` without Alpaca keys (`AlpacaKeysMissing`), `extract` / `ai-pick` before `sync-names` (`NamesNotSynced`), any command after a rules file changes (`RulesFileChanged`), and `ai-pick --keys` with a missing file (`FileNotFoundError`) each print a full traceback. Exit codes are 1 and the last line is clear. PR 1–3 set a one-line-error pattern (settings errors, `OperationalError`), and `embed`/`fetch-model` already do this for `ModelMissing`.
- *Fix:* catch `NamesNotSynced`, `RulesFileChanged`, `AlpacaError` and `OSError` in `_extract_command` and print one line.

**V6. `--max-usd` accepts `Infinity` and `NaN`.**
- *Where:* `cli.py:59`.
- *Problem:* `--max-usd Infinity` turns off both cost guards, and `NaN` crashes with `InvalidOperation` at the comparison.
- *Fix:* reject anything not finite or ≤ 0.

**V7. `similar()` signature.**
- *Where:* `similarity.py:236-238`.
- *Problem:* `k` isn't capped at 50 (`k=500` returned 500), and `min_score` defaults to 0.0, while the brief's signature has `min_score` with no default and returns "up to 50".
- *Fix:* `k = min(k, 50)` (or reject a larger `k`) and make `min_score` required (the match rule supplies it).

**V8. Smaller `ai-pick` and stability gaps.**
- *Where:* `batch.py:197-207`.
- *Problem:* `--run 2` doesn't require a run-1 answer, so a "stability rerun" can be the first answer and then writes no mentions. Keys in `--keys` that aren't text posts, or aren't in the database, are silently skipped. Nothing computes the stability share B2 must report.
- *Fix:* for run 2, select only posts that have a run-1 vote. Report keys not found. B2 adds a small stability script or query.

**V9. CHANGELOG and README describe B1/B2 pins as done.**
- *Where:* `CHANGELOG.md:36` ("three pinned models"; at df77049 xAI is `null` and no price is checked), `CHANGELOG.md:38` ("`fetch-model` downloads the pinned files"; `model.json` has `revision: null`), `engine/README.md:197-198` ("pinned in `extract/model.json`").
- *Note:* the CHANGELOG headline does say the AI half waits for Part B.
- *Fix:* add "(pins filled in Part B1/B2)" to those lines.

**V10. Two window boundaries use UTC midnight.**
- *Where:* `scripts/samples.py:374-375`, `scripts/precision.py:197`.
- *Problem:* both use UTC midnight, while `ai-pick` dates and alias dates are New York dates. No current sample post is affected (the first window post is 2025-11-01 16:43 NY). B2's `--window-start` would split at UTC midnight, 4–5 h before the NY day starts.
- *Fix:* use `NEW_YORK` in both.

### Question

**Q1. Instruments added by the AI become bare-ticker matches for the frozen rules picker, with no collision review.**
- *Where:* `rules.py:312-322` (every row of `engine.instruments` gets a bare-ticker entry), with `load_book` reading the live table and `NameBook.add`.
- *Problem:* the brief does say "a bare ticker of an instrument already in `engine.instruments`". But the collision review covered only the instruments that existed when drafting. Once the AI adds, say, a ticker that is a common capitalised word, live rules answers labelled "rules v1" change without a version bump, and history extracted earlier doesn't.
- *Options:* limit bare tickers to `aliases.json`'s instruments and the seeds, or require new tickers to pass collision review (a `review-list` line) first. A question for the engine planner.

**Q2. Prompt caching may not apply.**
- *Where:* `ai.py:319-330`.
- *Problem:* the brief puts the fixed instructions first "so the providers' prompt caching applies". Anthropic only caches with `cache_control` blocks, and none are sent. The picker prompt is ~4,000 characters (≈900–1,000 tokens), around the 1,024-token minimum for OpenAI and Anthropic caching. `Price.cost` also prices Anthropic cache writes at the plain input rate.
- *Scope:* this affects B2's cost projection only. `project_cost` already ignores cached pricing, so it is conservative.

**Q3. Tests build real SDK clients.**
- *Where:* `tests/test_ai.py:92-189`.
- *Problem:* the brief says "Tests use stubs and never build a real client." `test_clients_get_the_engine_keys_passed_in` and the SDK-path tests build real `AsyncOpenAI` / `AsyncAnthropic` objects with dummy keys. They never send: one uses MockTransport, the other never calls `ask`. Their value is real (they prove keys are passed explicitly and hosts are pinned), but they differ from the letter of the brief. Should the planner confirm?

**Q4. The PR head has moved past df77049.**
- The head is now 6a24a0b. b494bad pins the model and adds a match-rule loader and reading script.
- The PR body's "Not done: Part B1" should be updated when B1 completes.
- This pass did not judge b494bad or 6a24a0b.

---

## 7. Hygiene
- No push, commit, merge or GitHub write. GitHub was read only (PR body, check runs, workflow runs).
- No production DB, no `DATABASE_URL`, and role `engine` was only connected as.
- Throwaway DBs created and dropped: `verify261_mig`, `verify261_hand`, `verify261_cc0`, `verify261_nosync`. I also dropped `engine_test_565c29d1`, left by the pytest run I stopped for M28. Remaining databases: `postgres`, `shitpost_dev` (untouched, empty), `template0`, `template1`.
- No key under `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `XAI_API_KEY`. Fake `ENGINE_*` keys were used only in the probe process, against 127.0.0.1. The trap proxy log is empty (0 outbound attempts). No Hugging Face, Alpaca, Truth Social, ScrapeCreators, CNN or AI-host traffic.
- The local servers are stopped. Both worktrees are clean.
