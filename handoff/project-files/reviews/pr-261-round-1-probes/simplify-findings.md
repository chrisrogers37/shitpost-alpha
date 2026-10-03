# PR #261 (Engine PR 4), round 1: simplify pass

Scope: only PR 4's own changes, `git diff 56a32f7 df77049` (46 files). Line numbers are at df77049, relative to `engine/`. I read the brief's Part A first, so nothing below removes something the brief asks for.

**How I checked.** I made every change marked "verified green" in a scratch worktree at df77049. After the changes, everything passes: `ruff check`, `ruff format --check`, `mypy` (strict) and the full engine suite (382 passed, 1 skipped; the skip is the real-model test, as before). The combined patch is `review-261-r1/simplify/simplify.patch`: 14 files, +316/-318.

**Why the patch is only 2 lines shorter.** S7 adds about 25 lines on purpose, to batch the inserts. ruff's SIM117 rule also merged the nested `async with` blocks in `scripts/history_report.py`, which re-indents that file. Without S7, the other changes cut about 75 lines. No secrets were set, no real AI or Hugging Face calls were made, and the only databases touched were the throwaway ones the tests create.

Ranked by value.

---

## S1. Each AI-scored post loads the name book twice, and `ai-pick` reads each quoted post twice

- **Where**
  - `engine/extract/score.py:97-98` (`record_ai`)
  - `engine/extract/score.py:132` (`Scorer.handle`)
  - `engine/extract/batch.py:241` and `:261`
- **Problem**
  - `Scorer.handle` calls `load_book(conn, self.rules)` for the rules pick, then calls `record_ai`. `record_ai` calls `load_book` again on the same connection and in the same transaction. Each load costs:
    - two SELECTs (all instruments and all aliases);
    - a `NameBook.build`;
    - a `check_synced` pass;
    - compiling the regex of every alias.
  - `run_ai_pick` does the same thing per row: `load_book` at `:261`, then the second one inside `record_ai`.
  - `run_ai_pick` also builds every post's `PostText` before the cost projection (`:241`, which queries each quoted post). `record_ai` then rebuilds it with `normalize(row.text)` and `quoted_words`, which runs a second SELECT per quote.
- **Fix**
  - `record_ai(conn, row, book, post, ai, rules_pick, add_new, *, run, retries)` takes the book and the `PostText` the caller already has.
  - Replace `quoted_words` with `post_text(conn, row) -> PostText`. Its callers are the stage and the projection pass, and `run_ai_pick` zips each row with its pre-built `PostText`.
  - The semantics don't change. Before, both books were fresh copies loaded within one transaction. Now the AI uses the same book the rules just read, and the AI only adds tickers after the rules pick.
- **Saves**
  - About 4 lines.
  - Per AI-scored post: 2 SELECTs plus one book build. Per quote post in `ai-pick`: 1 more SELECT.
- **Verified green:** yes.
- **Not done:** loading the book once per `ai-pick` run (as `run_extract` does). It would be safe only after the bug noted at the end is fixed, because today `book.add` can widen a ticker's dates.

## S2. Picker and config are carried side by side, and "is the AI ready" is decided in two places

- **Where**
  - `engine/extract/score.py:121, 144, 154-167, 172, 180, 185`
  - `engine/extract/batch.py:227-235`
  - `engine/extract/ai.py:719-724`
- **Problem**
  - `AiPicker` already holds `config`. Even so, `live_ai` returns a `(picker, config)` tuple, `Scorer` keeps a separate `ai_config` field, `ai_loader` is typed as returning the tuple, and `record_ai` takes `config` as its own argument. This makes room for a picker and a config that disagree.
  - `live_ai` and `run_ai_pick` each repeat the same two checks with their own messages: `config.problems()`, then `from_settings(...) is None`.
- **Fix**
  - `AiPicker.from_settings` raises `NotReady` (it already exists, and is barely used) with the reason: "AI picker version N isn't ready: ...", or "no ENGINE_ AI key is set".
  - `live_ai` returns `AiPicker | None` and logs `"ENGINE_AI_LIVE is on but %s; the AI picker is off"`.
  - `run_ai_pick` says the same and returns 2.
  - Drop `Scorer.ai_config` and the tuple, and use `ai.config` / `picker.config`.
  - Tests change in three places:
    - `live_ai(...) is None`;
    - `ai_loader=lambda s: AiPicker(config, clients)`;
    - `pytest.raises(NotReady)` in `test_no_engine_keys_means_no_client_and_no_picker`.
- **Saves:** about 9 lines, and one invariant less.
- **Verified green:** yes. The log assertions in `test_the_ai_is_off_by_default`, including the no-key text, still pass.

## S3. Dead placeholder answers in `AiPicker.pick`

- **Where:** `engine/extract/ai.py:749-755, 763`
- **Problem**
  - For each provider without a client, `pick` appends a `ModelAnswer(error="no client ...")`.
  - `vote()` counts only `ok` answers, and `mapped` is built only for `ok` answers, so the placeholders change nothing.
  - Line 763 then filters them back out (`real = ... if a.provider in self.clients`).
  - The placeholders are made and thrown away. They also need `config.models[provider].model or ""`.
- **Fix:** `answers = await asyncio.gather(*asked)`, then `AiPick(tuple(answers), ...)`. The docstring's "a provider without a client counts as failed" stays true, because the vote needs 2 `ok` answers.
- **Saves:** 8 lines.
- **Verified green:** yes. The `answered` and `fallback` values are unchanged.

## S4. Two copies of the hash-pinned manifest loader

- **Where**
  - `engine/extract/rules.py:196-219` (`_sha256` + `load_rules`)
  - `engine/extract/ai.py:154-172` (`load_ai_config`)
- **Problem**
  - Both loaders do the same work:
    - read the manifest JSON;
    - loop over `files`;
    - SHA-256 each file under `PACKAGE_DIR`;
    - raise `RulesFileChanged` with the same message;
    - collect the texts.
  - `load_rules` reads each file twice (`_sha256` reads bytes, then `read_text`).
  - `load_ai_config` builds a `hashes` dict that is identical to `data["files"]`, because every digest was just checked equal.
- **Fix**
  - Add `read_pinned(manifest) -> (data, texts)` in `rules.py`, which reads each file once. `load_rules` and `load_ai_config` both call it.
  - The AI hash becomes `sha256(json.dumps(data["files"], sort_keys=True))`.
  - Drop `_sha256`, and drop the `PACKAGE_DIR` / `RulesFileChanged` imports in `ai.py`.
- **Saves:** about 9 lines and one file read per pinned file.
- **Verified green:** yes. I confirmed the AI picker hash is unchanged: `a68c46fb...54fa` before and after.

## S5. Dead code

| Where | What | Lines | Verified green |
| --- | --- | --- | --- |
| `engine/extract/rules.py:367-373` | `NameBook.names_of` is never called. | 8 | yes |
| `engine/extract/records.py:108-119` | `has_extraction` is never called; the batch code uses the `_lacks()` SQL instead. Its removal also frees the `select` import. | 14 | yes |
| `engine/extract/ai.py:98` | `ModelSpec.provider` is never read; the models dict is already keyed by provider. Drop it, and the first argument in `load_ai_config` and `tests/extract_helpers.ready_config`. | 1 (+2 call sites) | yes |
| `tests/extract_helpers.py:29, 32` | `CountsAll.asked` is written but never read; the `.asked` reads in tests are `StubClient.asked`. | 2 | yes |
| `tests/replay.py:43-50` | `replay_embedder` is never called. It is the brief's "or the real model when its files are present", so wire it into `test_the_replay_harness_runs_recorded_posts` (stub when absent) or drop it. | 9 | not tried |
| `tests/replay.py:61` | `Replayed.delivered` is set but never read; the replay test checks its own `delivered` list. | 2 | not tried |

## S6. The "counted symbols" expression is written out three times

- **Where**
  - `engine/extract/rules.py:469-470` (`pick`)
  - `engine/extract/ai.py:573-576` (`Vote.result`)
  - `tests/test_ai.py:49-52` (`symbols`)
- **Problem:** The same set-of-counted-instrument-symbols expression, which looks up each counted mention's ticker in the book, sorts and dedups, appears in all three places.
- **Fix:** Add `NameBook.symbols(mentions) -> list[str]` ("the counted instruments' tickers, sorted"), and use it at all three sites.
- **Saves:** about 5 lines (about 3 net after ruff format).
- **Verified green:** yes.

## S7. `extract` and `embed` make one round trip per post

- **Where**
  - `engine/extract/batch.py:69-76` (`run_extract`: one `record()` per row, each an INSERT ... RETURNING, plus a mentions INSERT when there are names)
  - `engine/extract/batch.py:108-115` (`run_embed`: one `store_embedding` INSERT per post)
  - `engine/extract/records.py:54-105`
  - `engine/extract/score.py:56-71, 100-101`
- **Problem**
  - About 36,600 history posts means about 36,600 to 45,000 statements per `extract` run and 36,600 per `embed` run, each a full round trip.
  - That runs once per rules or model version, and PR 5 will rerun it.
  - Against a remote database (Neon), round-trip latency dominates.
- **Fix**
  - `record_all(conn, [(signal_key, posted_at, Extraction), ...])`:
    - one multi-row `INSERT ... ON CONFLICT DO NOTHING RETURNING id, signal_key, method, version, run`;
    - ids are mapped back by the unique key;
    - one batched mentions INSERT via the existing `feeds.store.batches()`.
  - `record()` becomes a one-line wrapper, so the existing tests are unchanged.
  - `store_embeddings(conn, version, [(key, words, vector), ...])` makes one INSERT per 64-post batch.
  - `record_ai` records its 4 answers with one `record_all` call.
- **Measured:** throwaway database, local Postgres 16, 6,000 synthetic posts.
  - `extract`: 7.89 s down to 2.76 s.
  - `embed` (stub model): 4.08 s down to 1.17 s.
  - Statements per 500 posts drop from about 500 to 1,000 to about 2 or 3.
  - The gain over a network is far larger.
  - I hashed every extraction's topic, result and mentions on 1,200 posts. The hash was identical before and after: `c138f3df...`.
- **Cost:** about 25 more lines. This is the one finding in the patch that adds code.
- **Verified green:** yes.

## S8. A `make_engine` / `try` / `finally: dispose()` block is repeated 8 times

- **Where**
  - `engine/extract/batch.py:56, 91, 237, 329`
  - `engine/extract/names.py:66-72`
  - `scripts/precision.py:178`
  - `scripts/samples.py:42`
  - `scripts/history_report.py:26`
- **Problem:** Every command repeats this 4-line wrapper. Earlier PRs (`cli._status`, history, bars) repeat it too.
- **Fix**
  - Add to `engine/db.py`:

    ```python
    @asynccontextmanager
    async def database(url: str, **pool: Any) -> AsyncIterator[AsyncEngine]
    ```

    It is `make_engine` plus `dispose()` in a `finally`.
  - Then each site becomes `async with database(settings.db_url) as db:`. ruff SIM117 then merges it with the inner `db.connect()` / `Alpaca(...)` where possible, for example in `run_sync_names` and `history_report`.
  - The earlier PRs' sites can adopt it later.
- **Saves:** about 16 lines at PR 4's sites, minus 9 for the helper.
- **Verified green:** yes.

## S9. `run_ai_pick` is 71 lines, and three places repeat the rules step

- **Where**
  - `engine/extract/batch.py:210-280`
  - The rules step at `engine/extract/score.py:131-134` and `engine/extract/batch.py:72-74, 261-265`
- **Problem**
  - `run_ai_pick` is well over the repo's 50-line guide.
  - "Pick with the rules, then record `rules_extraction(pick, now, now)`" is written out three times: in the stage, in `run_extract` and in `ai-pick`.
- **Fix**
  - `record_rules(conn, book, row) -> RulesPick` in `score.py`, used by the stage and by `ai-pick`. `run_extract` builds its batch with `rules_extraction` directly for S7.
  - Move the per-post loop to `_pick_each(db, posts, picker, listings, run, max_usd, say) -> bool`. `run_ai_pick` drops to about 38 lines.
  - The row type is `Row[*tuple[Any, ...]]`, so `run_extract`'s 3-column rows type-check.
- **Saves:** about 4 lines. The main gain is function length.
- **Verified green:** yes.

## S10. `scripts/samples.py` re-implements `TEXT_POSTS`

- **Where:** `scripts/samples.py:48`, against `engine/extract/batch.py:40`.
- **Problem:** The same `or_(not_scored IS NULL, not_scored = 'imported')` condition is spelled out again. "What counts as a text post" should live in one place.
- **Fix:** Import `TEXT_POSTS` from `engine.extract.batch`. The query is unchanged.
- **Saves:** 1 line.
- **Verified green:** yes, and all three scripts still import.

## S11. Small items (low value)

1. **Loop-invariant sets in the precision script.**
   - `scripts/precision.py:153, 157`: `all_mine` and `all_truth` don't depend on the loop variable, but are rebuilt on each pass of the 3-kind loop.
   - Fix: build them once before the loop.
   - Verified green: yes.
2. **The model download borrows the CNN archive's timeout.**
   - `engine/extract/similarity.py:184`: `fetch_model` uses `settings.cnn_download_timeout_seconds`, and it sends no engine User-Agent.
   - Fix: rename that setting to a generic `download_timeout_seconds` (clean slate allows it), and pass `headers={"User-Agent": USER_AGENT}` from `engine.http_client`. Redirects stay on, because the brief needs them.
   - Not tried.
3. **The "isn't pinned yet" check is written twice.**
   - `engine/extract/similarity.py:116` and `:180` raise the same check with the same message.
   - Fix: a `ModelPin.require_pinned()` method.
   - About 2 lines. Not tried.
4. **Error text is built by hand.**
   - `engine/extract/ai.py:482` and `engine/extract/reason.py:69` build `f"{type(exc).__name__}: {exc}"` by hand, and `records.record` later passes it through `storable`.
   - `engine.db.error_text` already does this: NUL-free, surrogate-safe and capped.
   - Fix: `scrubbed(error_text(exc), secrets)`.
   - Not tried.
5. **`Rules.topic(id)` has only one engine caller.**
   - `engine/extract/rules.py:132-133`: the only engine caller is `choose_topic`'s fallback (`:460`), and `parse_topics` already guarantees `topics[-1]` is `other`.
   - Not tried.
6. **`rules_extraction` takes two times that are always equal.**
   - `engine/extract/records.py:41`: every caller passes `now, now` for `started_at` and `finished_at`.
   - Fix: take a single `at`.
   - Not tried.
7. **A test imports a helper from another test module.**
   - `tests/test_ai.py:34` imports `file_book` from `tests.test_rules`.
   - Fix: move it into `tests/extract_helpers.py`, which exists for exactly this.
   - Not tried.
8. **`Tally` wraps a list.**
   - `scripts/precision.py:128`: `Tally` only wraps a list with `add()`. A plain `list[tuple[...]]` would do.
   - Not tried.

---

## A bug I tripped over (for the bug pass, not a simplification)

- **Where:** `engine/extract/ai.py:538-546` with `NameBook.add` (`engine/extract/rules.py:329-332`).
- **When it happens**
  - A model gives a ticker whose instrument already exists but isn't valid on the post's date, for example `META` on 2022-05-02.
  - Then `book.ticker()` returns None and `add_new` is called.
  - `add_instrument` returns the existing row unchanged.
- **What goes wrong**
  - `book.add` appends `Held(id, None, None)`, an open-ended hold.
  - The ticker is counted on that post outside its validity.
  - From then on the in-memory book maps `META` on every date: checked at 2022-05-02 and 2016-01-04, using a stub that behaves like `add_instrument`.
- **How far it reaches**
  - Today the damage stops at one post, because books are reloaded per post.
  - It is also why S1 can't load the book once per `ai-pick` run.
- **Likely fix:** skip `add_new` when the symbol is already in `book.instruments`, and map the item to `does_not_count` / `not_an_instrument` on that date.

## Checked and fine

- **Migration 0004 repeats the tables in `tables.py`.** It matches the earlier migrations' pattern, and frozen migrations shouldn't import live metadata.
- **`ai.json` and `ai_picker.json` are separate files.** The manifest has to sit outside the config it hashes, just as `rules.json` pins `topics.json` and `aliases.json`. `model.json` is a different kind of pin (external files). Merging any of these would lose change detection.
- **Data the brief requires is all present:**
  - `topics.json`, `aliases.json` and the collision bump;
  - `label-guide.md`, `labels.csv` and `samples.csv`;
  - the three `*.unverified.json` fixtures;
  - `Similarity` (B1/PR 5 use it);
  - `ReasonSpec`'s `version` / `provider` (PR 6 uses them).
- **`OpenAIChat` and `AnthropicMessages` are two separate small adapters.** The SDKs differ enough (`response_format` vs `output_config`, usage fields) that a shared base would add indirection without saving lines.
- **`reason_line` and `ask_model` share a timeout and exception shape.** They differ in parsing and retries, so a shared helper would save only about 4 lines.
- **`fetch_model` doesn't use `engine.http_client.make_client`.** That is deliberate: the shared client forbids redirects, and the Hugging Face download needs them. Only the UA reuse in S11.2 applies.
- **`OnnxEmbedder` hashes every model file on each load.** It costs about 0.3 s for roughly 130 MB at worker start or at each `embed` run, which is fine for a pin check.
- **`normalize()` runs about 3 times per post in the stage** (rules, embedding, AI text). That cost is negligible.
- **`find_names` is 56 lines.** That is mildly over the guide, but its three loops are parallel and readable, and splitting it would add lines.
- **No test duplicates another.** Rules, mapping, vote, records, stage and replay each cover a distinct item from the brief's checklist. The two `ai-pick` tests in `test_batch.py` exercise different paths (refusal vs mid-run stop).
- **`Similarity.similar`.** It is one matrix product plus masks and `argpartition`, and it is already minimal. The speed test passes comfortably.
- **Settings and CLI additions are proportionate.** The settings are 3 keys, `ai_live`, `model_dir` and `score_tick_seconds`; the CLI dispatch is `_extract_command`.
