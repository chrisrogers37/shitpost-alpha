# PR #261 round 2: the feature commits (simplify, review and verify)

Head: **4554d3d**, in a detached scratch worktree at `$SP/r2feat-261-wt`, which is clean again.

| Part | Commits |
| --- | --- |
| B1 (PR 4 builder) | b494bad (pins, loader, reading script); 6efd98b (match rule v1, 274 labels) |
| B2 (B2 thread) | ba4d296 (prompt rounds, reason line); ea66a40 (gpt-4.1 and Haiku 4.5 pins) |

Line numbers are at 4554d3d. Probes and outputs are in `$SP/review-261-r2/feat/`.

**Verdict.** There are no blockers.
- B1 matches the brief section by section, and its reading table reproduces exactly from committed data.
- The weak spots are versioning:
  - the model version covers only the repo commit;
  - the match rule's threshold is pinned by nothing;
  - the AI version has no frozen-hash guard.
- Each weak spot has a mutation that survives. A scratch patch kills the B1 ones and keeps everything green.
- B2's two commits keep the pins, prices and hashes consistent. No held-out post leaked into the dev-set rounds.

---

## 1. B1 checklist

### Model pin

| Item | Status | Evidence |
| --- | --- | --- |
| Repo `BAAI/bge-small-en-v1.5` | OK | `engine/engine/extract/model.json:3` |
| Revision pinned (`5c38ec7c405e…`) | OK | `model.json:5`. Not re-checked against the hub, because no network calls are allowed. |
| Per-file SHA-256 (4 files) | OK | `model.json:6-11`. `sha256sum` of all four files in `/home/user/engine-models` matches each pin. |
| Licence MIT | OK | `model.json:4`. Data only: `ModelPin` doesn't carry it. |
| CLS pooling | OK | `model.json:12` "cls". The downloaded `1_Pooling/config.json` has `pooling_mode_cls_token: true`, and the rest are false. The code takes `hidden[:, 0, :]` (`similarity.py:159`). The ONNX output 0 is `last_hidden_state [b, seq, 384]`. |
| Normalised | OK | `similarity.py:109-113, 159`. All probe vectors have norm 1.000000. |
| Unused files are pinned (config.json, 1_Pooling) | Note | They are pinned for provenance only; the code hard-codes "cls". |

### fetch-model

| Item | Status | Evidence |
| --- | --- | --- |
| Hash refusal | OK | `similarity.py:217-219`. Covered by `test_fetch_model_refuses_a_file_that_does_not_match`; mutation M1 was killed. |
| Partial file cleaned up | OK, untested | `similarity.py:204-216`. `probe_fetch.py`: a `ReadError` mid-stream and a `KeyboardInterrupt` mid-stream both leave nothing on disk. No test covers this (M17 survived; see N12). |
| Atomic write | OK | A temp file in the same directory, then `Path.replace` (`similarity.py:204, 220`). There is no fsync, but the hash check at load catches a torn file. |
| Hosts reported | OK | `similarity.py:209-210`, `cli.py:146-147`. The probe reports `{huggingface.co, cas-bridge.xethub.hf.co}`. |
| Redirect carries no credentials | OK | Both hosts get only `accept`, `accept-encoding`, `connection` and `user-agent`. No auth header is set. httpx 0.28 reads no netrc. |
| User-Agent | OK | `shitpost-alpha-engine/0.1.0 (+https://github.com/chrisrogers37/shitpost-alpha)` (`similarity.py:191`). |
| File mode | Nit | Files land 0600 (the tempfile default), as seen in `/home/user/engine-models`. See N6. |

### Embedding (real model, `probe_embed.py` and `probe_batching.py`)

| Item | Status | Evidence |
| --- | --- | --- |
| Same text twice | OK, bitwise | 11/11 texts give bitwise-equal vectors. |
| Different batch sizes | OK, bitwise | Batch sizes 1, 2 and 11 are bitwise equal. On 303 real post texts, 64-post batches in time order and in length order are bitwise equal (max diff 0.0). |
| Truncation at 512 | OK | 510 words of "the" give 512 tokens and are not truncated. 511 words give 512 tokens with `truncated=True`. 1000× "tariffs" is truncated and flagged. `similarity.py:141, 161`. |
| Edge text | OK | Empty, "a", non-ASCII (accents, em dash) and emoji all give finite, unit-norm vectors. All-URL text normalises to "" and is skipped by the stage (`score.py:168`) and by `embed` (`batch.py:111`). `embed([])` returns `[]`. |
| Emoji-only text | Nit | 🔥, 🙏 and 🇺🇸🇺🇸🇺🇸 all tokenise to `[CLS] [UNK] [SEP]`: one identical vector. See N7. |
| Live inference off the event loop | OK | `score.py:169` (`asyncio.to_thread`); the model load runs in a thread too (`score.py:204`). |

### Model version

| Item | Status | Evidence |
| --- | --- | --- |
| Recorded with every vector | OK | `score.py:79-89` writes `model_version=version`. M11 (a constant version) was killed. |
| Changing model.json changes it | **Partly** | Only `repo` and `revision` feed it (`similarity.py:52-55`). Changing `max_tokens` (M13), pooling or a file hash leaves the version unchanged. M13 and M14 survived. This contradicts `model.json:2`: "Changing anything here changes the model version". See SF1. |

### Match rule v1

| Item | Status | Evidence |
| --- | --- | --- |
| The file | OK | `engine/engine/extract/match_rule.json:2-7`: version 1, `model_version` = the pinned version, threshold 0.85, `max_matches` 50, normalisation described. |
| Versioned | OK | It has `"version": 1`. |
| Hash-pinned | **No** | No manifest pins it. The test checks only `0.7 <= threshold < 1` (`tests/test_similarity.py:223-226`). M8 (0.85 → 0.80) survived. See SF2. |
| Used by `similar()` and the score stage | **No** | `load_match_rule` (`similarity.py:292-307`) is called only by tests. `similar()` takes `min_score` from its caller and has its own `k=50`. The score stage only stores vectors. See Q2. |
| Excludes the post itself | OK | `similarity.py:255`. M5 killed. |
| Excludes posts at or after `before` | OK | `similarity.py:255` uses `<`. M6 (`<=`) and M7 (ignore `before`) killed. |
| At most 50 | OK | `similarity.py:247, 257-259`. M4 (k=51) killed. |
| Threshold applied | OK | `similarity.py:255`. M3 killed. |
| Speed | OK | The 40k-vector test passes. |
| Loader refuses another model version | OK | `similarity.py:301-306`. M10 killed. |

### Reading method against brief section 5

| Item | Status | Evidence |
| --- | --- | --- |
| 30 posts, fixed seed, outside the 300 | OK | `scripts/samples.py:91` uses the shared `SEED`, drawn after the earlier sets. The 30 `match` keys share no key with `precision_*`, `labels.csv` or the dev sets. |
| Bands 0.90+, 0.85, 0.80, 0.75, 0.70 | OK | `scripts/match_rule.py:39`. |
| "Matches" are earlier posts, never the post itself | OK | `scripts/match_rule.py:83-84`. `probe_draw_pairs.py` uses a synthetic index of 2,030 posts: 397 pairs, 0 later or same-time pasts, 0 self-pairs, at most 3 per post per band, bands agree with the unrounded scores, and two draws are identical. |
| Threshold rule | OK | It picks the lowest band where that band and every band above it reach 80%. The brief asks only for the lowest band at 80%; the script's rule is stricter and gives the same answer here. |
| Statistics reproducible | **OK** | Running `python -m scripts.match_rule table` on the committed `precision/match-labels.csv` prints exactly match-rule.md's table: 14/14, 26/32, 28/58, 17/80, 11/90, threshold 0.85. A recount of all 30 rows of match-rule.md's per-post table from the CSV matches every cell. 274 pairs, no duplicates. |
| `pairs` itself | Not re-run | It needs the embedded history, and this session's `shitpost_dev` has no `engine` schema. Its logic was checked offline (above). |
| History numbers in match-rule.md | Not reproducible | 39.6% with a match, median 2, p90 14, 0.9% at the cap, 16,087 embedded, 48 cut, 5,523 skipped. None comes from committed code. See N4. |
| Held-out posts kept out of drafting | Minor breach | One past post that was read is a `precision_window` post (`match-labels.csv:256`). See N2. |

---

## 2. Commands and mutations

Every command ran with DATABASE_URL, the three old `*_API_KEY` variables and the three `ENGINE_*_KEY` variables removed. It ran from `engine/` with `PYTHONPATH=<checkout>/engine` and `ENGINE_MODEL_DIR=/home/user/engine-models`.

| Command | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 90 files already formatted |
| `mypy .` (strict) | Success: no issues found in 85 source files |
| `pytest tests/test_similarity.py tests/test_score.py` (real model present) | 28 passed, 0 skipped |
| `pytest` (full suite) | **451 passed** in 178 s, 0 skipped. This matches the builder's count. |
| Full suite with the scratch patch (section 5) | 451 passed; ruff, format and mypy clean |
| Leftover test databases | None. Only `postgres`, `shitpost_dev` and the templates exist. |

**Mutations.** `mutate.py` applies each one, runs the named tests, then restores the file. Output is in `mutate_out.txt`.

| # | Mutation | Result |
| --- | --- | --- |
| M1 | fetch-model hash refusal off | killed |
| M2 | load-time hash check off | killed |
| M3 | threshold ignored in `similar()` | killed |
| M4 | cap 50 → 51 | killed |
| M5 | post itself not excluded | killed |
| M6 | `before`: `<` → `<=` | killed |
| M7 | `before` ignored | killed |
| **M8** | **match_rule.json threshold 0.85 → 0.80** | **survived** (77 tests) |
| M9 | match_rule.json `max_matches` 50 → 60 | killed |
| M10 | match rule's model-version guard off | killed |
| M11 | vector row's `model_version` set to a constant | killed |
| M12 | `load_similarity` ignores `model_version` | killed |
| **M13** | **model.json `max_tokens` 512 → 256 (version unchanged)** | **survived** |
| **M14** | **CLS → mean pooling** | **survived** (28 tests, real model present) |
| M15 | vectors not normalised | killed |
| M16 | truncation flag always False | killed |
| **M17** | **fetch partial-file cleanup off** | **survived** (behaviour itself is correct, per the probe) |
| M18 | fetch mismatch cleanup off | killed |
| **M19** | **`embed` resume ignores the model version** | **survived** |
| M20 | `store_embedding` overwrites | killed |
| M21 | version ignores the revision | killed |
| M22 (B2) | reason check drops benefit and harm | killed |
| **M23 (B2)** | **Haiku input price 1.0 → 3.0, with ai.json rehashed** | **survived** (92 tests) |
| M24 (B2) | prompt edited, hash not updated | killed (`RulesFileChanged`) |
| M25 (B2) | xAI model changed to the alias `grok-4` | killed |

With the scratch patch, M8, M13 and M14 are killed (`mutate_after_fixes.txt`). M17 and M19 still survive: those need new tests (N12).

---

## 3. Findings

### Blocker

None.

### Should-fix

**SF1 (B1, b494bad). The model version covers only the repo and revision, not the rest of the pin.**
- **Where:** `engine/engine/extract/similarity.py:52-55`. Also `model.json:2` ("Changing anything here changes the model version recorded with every vector").
- **Problem:** `version` is `bge-small-en-v1.5@<revision[:12]>`. `max_tokens`, `pooling`, `dims` and the file hashes are not part of it.
- **Failure scenarios:**
  - Someone lowers `max_tokens` to 256 for speed, or pins `onnx/model_quantized.onnx` at the same commit. New vectors are made differently but stored under the same version.
  - `embed` treats every post as done (`batch.py:96-99`), so history and live vectors silently mix two encodings.
  - `load_match_rule`'s guard, which exists for exactly this case, doesn't fire, so the 0.85 rule is applied to vectors it wasn't read on.
- **Evidence:** M13 (`max_tokens` 512 → 256) and M14 (mean pooling) pass all 77 and 28 tests.
- **Fix:** add a digest of the rest of the pin to the version:
  ```python
  rest = json.dumps([self.files, self.pooling, self.max_tokens, self.dims], sort_keys=True).encode()
  return f"{name}@{rev[:12]}.{hashlib.sha256(rest).hexdigest()[:8]}"
  ```
  - That gives `bge-small-en-v1.5@5c38ec7c405e.eaa83ab2`. Update `match_rule.json`'s `model_version` to match and re-embed the sandbox copy (about 14 minutes; under 4 with SF3).
  - Also add a golden-vector check to the real-model test, which kills M14: the first 6 dimensions of the test sentence are `[-0.0720, 0.0076, -0.0272, 0.0465, 0.0500, 0.0316]`, with `abs=2e-4`.
  - Both are in the scratch patch.
- **Related:** `onnxruntime>=1.22` and `tokenizers>=0.21` float (`pyproject.toml:16, 22`), and the runtime isn't part of the version either. An upper bound such as `<2` / `<0.24`, or a note, would stop a tokenizer change from re-encoding silently.

**SF2 (B1, 6efd98b). Match rule v1's threshold isn't tied to its reading, and nothing pins the file.**
- **Where:** `engine/engine/extract/match_rule.json:5` and `tests/test_similarity.py:223-226`.
- **Problem:** the rules and AI versions are pinned by SHA-256 manifests, but the match rule isn't. Its only test accepts any threshold from 0.7 up to 1.
- **Failure scenario:** someone edits 0.85 to 0.80 to get more matches. CI stays green and PR 5 backtests on a rule nobody read. M8 survives 77 tests.
- **Fix:**
  1. Split `scripts/match_rule.py:table()` into `counts()` and `pick_threshold()`.
  2. Assert `load_match_rule().threshold == pick_threshold(*counts())` against the committed `precision/match-labels.csv`.
  3. Keep the `(1, REAL.version, 50)` assertion.
  4. Optionally pin `match_rule.json` and `match-labels.csv` by hash, next to the model pin.
- **Evidence:** this is in the scratch patch and kills M8.

**SF3 (B1 evidence; the code is Part A's `run_embed` and `OnnxEmbedder`). History batches pad 64 posts to their longest post: a 4 GB peak and roughly 4× the time.**
- **Where:**
  - `engine/engine/extract/batch.py:111-114`: batches of 64 in post-time order.
  - `engine/engine/extract/similarity.py:142`: `enable_padding()` pads to the longest post in the batch.
- **Problem:** one 512-token post makes the whole batch 64×512, so attention runs at 64×12×512×512. The CPU arena keeps the high-water mark.
- **Evidence:** on 303 real post texts plus 3 long posts, the run took 60.1 s with a 4,079 MB peak RSS in time order, against 14.3 s and 1,841 MB in length order.
  - Vectors are bitwise identical in both orders, so the change is safe.
  - A single 64-batch holding one long post peaked at 2.39 GB and took 13.9 s.
  - B1's history run took about 14 minutes for 16,087 posts with 48 truncated; this padding plausibly accounts for most of that.
- **Failure scenario:** PR 7 runs `embed` (a backfill, or a re-embed after a model change) on a service with under about 4 GB of memory. It is OOM-killed on the first batch that holds a long post. It resumes at the same batch and dies again, so it never finishes.
- **Fix:** sort `todo` by length before batching (one line, in the scratch patch). Better still, also cap the tokens per batch (for example 64×128) so long posts go in small batches.

**SF4 (B2, ea66a40 and ba4d296). No guard pins a frozen AI version's content, and the run-time guard can't see per-model rows.**
- **Where:**
  - `engine/engine/extract/ai.json:2-10`;
  - `engine/engine/extract/batch.py:230-242` (`other_prompt` checks only `ai:vote` rows' `picker_hash`);
  - `engine/engine/extract/ai.py:637-649` (only the vote's `result` carries `picker_hash`).
- **Problem:** in both B2 commits, every change to the version's files moves the SHA in `ai.json` while the version stays 1. That is fine while v1 isn't frozen, but nothing will stop it after the freeze. A price, model or prompt edit with a rehash passes CI.
- **Evidence:** M23 (Haiku input $1 → $3, rehashed) passes 92 tests.
  - b2/results.md says "AI picker version 1 is frozen on option A".
  - It also says the sandbox's `ai:vote` rows were "rebuilt … under version 1's hash" from per-model rows recorded under an earlier hash. The guard can't tell those apart.
  - At 4554d3d the files still pin xAI with `window_start: null`, so the frozen v1 isn't the committed v1 yet.
- **Fix, with the freeze commit:**
  - Add `"frozen": "<sha256>"` to `ai.json`. Have `load_ai_config` refuse when `config.hash != frozen` (or a test holds `{1: "<hash>"}`). Any later edit then has to raise the version.
  - Write `picker_hash` into every `ai:<provider>` row, and have `other_prompt` check those rows too.

### Nit

**N1 (B2, ba4d296). The reason check's new `benefit\w*|harm\w*` rejects neutral words.**
- **Where:** `engine/engine/extract/reason.py:24`.
- **Evidence:** in a probe, check_reason rejects all of these as "states a direction":
  - "Post changes **Harmonized** Tariff Schedule codes for steel imports from China";
  - "Post says **Harmony** Gold mine deal…" (HMY is NYSE-listed);
  - "…protect Medicare and Social Security **benefits**…".
- **Failure scenario:** a tariff post's reason line naming the Harmonized Tariff Schedule is dropped, and the alert goes out without one. The check fails closed, so nothing wrong is sent.
- **Fix:** use `harm(?:s|ed|ing|ful)?` inside the existing `\b…\b`. The scratch file `scratch-harm-regex.patch` passes the 30 reason tests and accepts Harmonized and Harmony while still rejecting harm, harming and harmful. Wrap the string at 100 columns. Accept the noun "benefits" as a known false positive, or exempt it after "Security", "Medicare" or "veterans".

**N2 (B1, 6efd98b). One held-out post was read while setting the match rule.**
- **Where:** `engine/precision/match-labels.csv:256` (past post `truth_social:116517763130501652`, set `precision_window`).
- **Problem:** brief section 3 says to keep the 300 out of all drafting. The effect is nil: the labels were committed earlier, and the match rule doesn't touch the pickers.
- **Fix:** have `draw_pairs` skip `precision_*` keys as candidates (`scripts/match_rule.py:84-93`), and say so in match-rule.md.

**N3 (B1, b494bad). `pairs` overwrites the labelled file.**
- **Where:** `scripts/match_rule.py:98-101` writes `LABELS` with an empty `same` column.
- **Failure scenario:** a re-run, for example to look at the reading file again, wipes the 274 committed labels in the working tree.
- **Fix:** refuse when any row already has `same` set, or take a `--labels` path.

**N4 (B1, 6efd98b). match-rule.md has numbers no committed code produces, and a rounded score that contradicts its band.**
- **Where:** match-rule.md's "What 0.85 gives over all history" section, and `match-labels.csv:255` (band 0.70, score `0.7500`).
- **Problem:** the history numbers are 39.6%, median 2, p90 14 and 0.9% at the cap. Separately, `f"{s:.4f}"` at `scripts/match_rule.py:101` rounds 0.74997 up to 0.7500.
- **Fix:** add a `coverage` subcommand that prints those history numbers, and write scores with `.6f`.

**N5 (B1 evidence; Part A code). ONNX Runtime thread defaults in the always-on worker.**
- **Where:** `similarity.py:143-145` builds the session with no `SessionOptions`.
- **Evidence:** on 4 CPUs there are 8 threads after load and 12 after the first embed (ORT's intra-op pool plus the tokenizers pool).
  - ORT sizes its pool from the host's cores, not a container's CPU quota, and its threads spin after each run.
  - Measured: a short post takes 8.6 ms with 1 thread against 15.1 ms by default, and a 512-token post 211 against 165 ms.
- **Fix:** for the live worker, use `intra_op_num_threads` = 1 or 2 (a setting) and `session.intra_op.allow_spinning=0`.

**N6 (B1 evidence; Part A code). Model files are saved 0600, and stray temp files stay after a kill.**
- **Where:** `similarity.py:204, 220`.
- **Failure scenario:** `fetch-model` runs as root at build time and the worker runs as another user. `_file_hash` then raises `PermissionError`, which isn't `ModelMissing`, so the worker dies with a traceback instead of the operator message. A SIGKILL leaves `tmpXXXX` files of up to 133 MB.
- **Fix:** `os.chmod(partial, 0o644)` before `replace`, and use a `.part-` prefix that the next run cleans up.

**N7 (B1 evidence; Part A code). Emoji-only posts all share one vector.**
- **Problem:** `[CLS] [UNK] [SEP]` scores 1.0 against every earlier emoji-only post, so each such post gets up to 50 spurious matches. It is rare: 0 of the 300 precision posts.
- **Fix:** treat words with no in-vocabulary alphanumeric token as "without words" in `run_embed` and the stage, or note it for PR 5.

**N8 (B2, ba4d296). The reason prompt and its check disagree on amounts.**
- **Where:** `prompts/reason.md` now says "Leave out every amount … even ones the post gives", but `check_reason` (`reason.py:46-49`) still passes any number the post has.
- **Failure scenario:** "Apple pledges 500 billion investment…" passes the check.
- **Fix:** if the rule is now "no amounts", reject any number in the check. Otherwise relax the prompt.

**N9 (B2, ba4d296). The `dev_market` draw depends on the names table and the rules version.**
- **Where:** `scripts/samples.py:62-68, 92-94`.
- **Problem:** a redraw needs `sync-names` and rules v1's book, and `Random.sample(market, 50)` raises on a small copy. The docstring's "a redraw on another copy … matches" holds only under rules v1.
- **Fix:** assert `current_rules().version == 1`, or say so in the docstring. The committed ids are what count.

**N10 (B2, ea66a40). The window start isn't checked, and it would parse as naive.**
- **Where:** `ai_picker.json:50` is null; `AiConfig.problems()` (`ai.py:149-158`) doesn't report it; `ai.py:202` parses `"2025-11-01"` as naive midnight, although the new "about" text says "the start of the next New York day".
- **Fix at the freeze:** `problems()` reports "window_start not set", and the loader does `datetime.combine(date.fromisoformat(w), time(), NEW_YORK)`. This is B2 work still in progress; noted so the freeze includes it.

**N11 (B1, b494bad). Ties at the cap aren't deterministic.**
- **Where:** `similarity.py:271` orders by `posted_at` only.
- **Problem:** when two posts are made at the same moment and tie at the 50 cap, which one is kept depends on the database's row order.
- **Fix:** `.order_by(signals.c.posted_at, signal_embeddings.c.signal_key)`. This is in the scratch patch.

**N12 (B1). Two test gaps.**
- M17: add a test where the CDN drops the connection mid-file and nothing is left behind (`probe_fetch.py` shows the code is right).
- M19: add a test where a second embedder version re-embeds posts that have only the first version's vector.

### Simplification

All of these were tried on the scratch checkout and kept green: ruff, format, mypy strict and 451 tests pass. The patch is at `$SP/review-261-r2/feat/scratch-fixes.patch` (186 lines, 6 files, +44/-21).

- **SM1** (`scripts/match_rule.py`): `table()` becomes `counts()` plus `pick_threshold()`. The SF2 test reuses them, so the threshold rule exists once.
- **SM2** (`tests/test_ai.py:79, 198, 281`): three copies of `replace(cfg, models={**cfg.models, "xai": replace(cfg.models["xai"], model=None)})` become one `without_xai(cfg)` helper. Two copies come from ea66a40 and one from the merge.
- **SM3** (`batch.py:111`): one line sorts `todo` by length (SF3).
- **SM4** (`similarity.py:52-55`): the version digest and the golden-vector test (SF1).
- **SM5** (`similarity.py:271`): the tie-break (N11).

Nothing else in the four commits is longer than about 50 lines or duplicated. `load_match_rule` and `MatchRule` have no production caller yet; see Q2 before deleting them.

### Question

**Q1 (B1, 6efd98b). Should the threshold be 0.85 or 0.90, and is the weighting right?**
- The 0.85 band is 26/32 (81%), with a Wilson interval of 65–91%. One call the other way moves the threshold to 0.90. match-rule.md lists the five generous calls: Paxton, Christie, "Leo", the MAGA slogan and Fox.
- `pairs` takes at most 3 pairs per post per band (`scripts/match_rule.py:92-93`), so each post counts equally rather than each match served. Posts with many neighbours (the templated endorsements at 0.80–0.88, the slogans) are under-weighted against what PR 5 will see with up to 50 matches.
- Could `pairs` record each post's band count, so match-rule.md can show a match-weighted share next to the per-post share before Chris settles it?

**Q2 (B1). Is the match rule left for PR 5 to wire up?**
- Nothing outside tests reads `match_rule.json`. `similar()` takes its threshold from callers and has its own `k=50`, and the refusal for another model version fires only when someone calls `load_match_rule`. Is that left for PR 5?
- If so, say it in the PR, and have PR 5 call `similar(..., min_score=rule.threshold, k=rule.max_matches)` from the loaded rule.
- Small point: a rule set for another model version raises `ModelMissing`, which the CLI reports like missing files.

**Q3 (B2). What will the freeze commit do?**
- results.md describes v1 frozen with two models and the window at 2025-11-01, but 4554d3d still has three providers, xAI pinned and `window_start: null`.
- Will the freeze commit drop xAI from `PROVIDERS`/`ai_picker.json`, set `window_start` and record the frozen hash (SF4)?
- What happens to the sandbox's per-model rows recorded under pre-freeze hashes?

**Q4 (B2). Grok prices and cutoff are unverified.**
- `grok-4.20-0309-non-reasoning` at $1.25 / $0.20 / $2.50, with the 2025-09-01 cutoff from OpenRouter, couldn't be checked here (no network). It's comparison-only under option A.

---

## 4. Checked and dropped

- **Dev-set leak (B2):** none.
  - The `dev` and `dev_market` keys (150) share no key with `labels.csv` or the `precision_*` sets.
  - No key appears in two sets.
  - The new prompt example ("if Canada becomes a state, its steel and energy would quadruple") isn't in any held-out post's text: 0 hits for "quadruple" or "steel and energy" in precision-sample.csv.
  - spend.md shows both prompt rounds ran on dev and dev_market only.
- **samples.py's UTC window against the NY window (B2):**
  - samples.py splits at UTC midnight and the AI window at New York midnight (04:00 UTC), so 4 hours differ.
  - No `precision_window` post falls in those 4 hours; the earliest is 2025-11-01 20:43 UTC.
  - The `dev` and `dev_market` sets all fall before 2025-10-24.
  - So there is no effect.
- **Reason line "100 characters" in the prompt against the check's 120 (B2):** the prompt is deliberately stricter than the brief's 120-character rule.
- **Prices against the code (B2):**
  - gpt-4.1 at $2 / $0.50 / $8 and Haiku 4.5 at $1 / $0.10 / $5 match published pricing.
  - Both ids are dated snapshots (`gpt-4.1-2025-04-14`, `claude-haiku-4-5-20251001`).
  - `Price.cost` splits cached input correctly: OpenAI's and xAI's `prompt_tokens` include cached tokens, and the Anthropic client sums the three counts.
  - Anthropic cache writes are charged at the base rate, but no `cache_control` is sent and Haiku 4.5's minimum cacheable prefix is 4,096 tokens (the prompt is about 1.1k tokens), so writes are always 0.
  - The ai-pick projection uses the full input price, which is conservative.
- **Dates on the Sonnet 4.5 deprecation:** my reference data predates 2026-09-30, so I can't confirm or refute the deprecation and retirement dates B2 cites. Haiku 4.5 is Active.
- **Cross-machine float drift:** vectors are bitwise identical within one ORT build. A different CPU or ORT version may differ by about 1e-7, far below the band widths.
- **Cancellation:** a cancelled stage rolls back its transaction, and the inference thread finishes (5–200 ms) with its result dropped. `embed` commits per batch and resumes. On shutdown the default executor waits for at most one inference.
- **Blocking work in the event loop:** inference and the model load run in threads, and fetch-model runs only from the CLI. `normalize` over history and `load_similarity`'s numpy work stay on the loop, which is acceptable for batch commands.
- **Zero or NaN vectors:** `normalized` guards zero norms. A NaN score fails `>=` and is excluded. The model produced neither on the edge text.
- **The `\d{4}` "dated snapshot" test passes `grok-…-0309`:** it's weak, but xAI leaves the vote under option A.
- **Docstrings on the script helpers (CLAUDE.md style):** the engine's own convention leaves trivial helpers undocumented; the clean-slate rule applies.
- **`similar()` with a naive `before`:** every caller passes an aware `posted_at` from the database.
- **The code-review agent's "could not run tests":** its venv lacked alembic. I ran the full suite in the right venv: 451 passed.

## 5. Artifacts

All are in `$SP/review-261-r2/feat/`:

| File | What it is |
| --- | --- |
| `probe_embed.py` | determinism, truncation, edge text, memory, threads |
| `probe_batching.py` | time-ordered against length-sorted batches; `time.npy` and `sorted.npy` hold the vectors |
| `probe_fetch.py` | dropped connection, 404, Ctrl-C, headers, file modes |
| `probe_draw_pairs.py` | an offline check of `draw_pairs` |
| `mutate.py`, `mutate_out.txt` | 25 mutations against 4554d3d |
| `mutate_keep.py`, `mutate_after_fixes.txt` | the survivors re-run with the scratch patch |
| `scratch-fixes.patch` | SF1, SF2, SF3, SM1, SM2, N11 and the golden-vector test |
| `scratch-harm-regex.patch` | N1 |
