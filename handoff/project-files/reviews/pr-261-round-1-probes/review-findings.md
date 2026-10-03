# PR #261 (Engine PR 4: extraction and similarity), review pass r1

- Head reviewed: df77049. Own changes: `git diff 56a32f7 df77049` (46 files).
- Checkout: `$SP/review-261-r1-wt`. Mutation checkout: `$SP/review-261-r1-mut` (restored after each mutation, clean).
- Probes: `$SP/review-261-r1/review/test_probe_*.py`, 14 files, 32 tests. Each one passes while its bug is real. Run them with `$SP/review-261-r1/run_probe.sh $SP/review-261-r1/review/`. The last run printed `32 passed` (log: `$SP/review-261-r1/probes.log`).
- Mutations: `$SP/review-261-r1/mutate.py`, results in `$SP/review-261-r1/mutations-all.log`.
- Baseline at df77049: `pytest` gives 382 passed, 1 skipped (the real-model test). `ruff check`, `ruff format --check` and `mypy` are clean. This matches the PR body.
- Safety: every command ran with the old and ENGINE_ AI key variables and ANTHROPIC_BASE_URL unset. Providers were reached only through mock transports or stubs, with obviously fake keys. Only throwaway databases were used. Nothing was written to GitHub.

($SP = /tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad)

---

## Blocker

### B1. A counted `ai:vote` mention is silently dropped from `engine.signal_mentions`

- **Where:** `engine/engine/extract/records.py:102` (`for m in {m.normalized: m for m in answer.mentions}.values()`) together with `engine/engine/extract/ai.py:598-633` (`vote()` appends the unmapped `by_name` mentions after the mapped `by_instrument` ones).
- **Problem:** `record()` dedups mentions by `normalized` and keeps the last one. A vote can produce a mapped mention and an unmapped mention with the same normalised name:
  - two models give a name with a ticker, so it maps by ticker and counts 2 of 3;
  - the third model gives the same name with `ticker: null`, which the prompt allows ("null if you are not sure"), so it is unmapped with `no_ticker`.

  The unmapped row overwrites the counted one in the dict, and the counted row is never written. Any name without an alias maps by ticker, and that is most AI names, since aliases cover 61 instruments.
- **Failure scenario:** a post's vote counts NVDA. The `result` JSON of the `ai:vote` row says `symbols: ["NVDA"]`, but `signal_mentions` holds only `("some chip firm", counted=False, "no_ticker")`. Three readers use `signal_mentions` and none sees the counted name:
  - review-list (`batch.py:286`);
  - `scripts/precision.py` (the AI name precision and recall in B2);
  - PR 5's backtest, which reads mentions by instrument and post time (the index this PR adds for it).

  The loss is silent and permanent, because records are never overwritten.
- **Evidence:** `test_probe_vote_mentions_dedup.py::test_counted_vote_mention_is_lost_when_a_model_gives_null_ticker` passes. The vote result says NVDA, and the only vote mention row is the unmapped one. Mutation M9 (drop the dedup) also survives the PR's tests, so no test makes two mentions with one normalised name. With M9 applied, this scenario would hit the `signal_mentions_key` unique constraint instead.
- **Fix:** do one of the following.
  - (a) In `vote()`, fold an unmapped name whose `normalized` equals a mapped vote mention's name into nothing. That model named the same thing without a ticker, so do not emit a second row for it. Leave the `models` count as it is.
  - (b) Make the key `(extraction_id, normalized, instrument_id)` with NULLS NOT DISTINCT, and dedup in `record()` on that pair.

  Either way, make `record()` raise on a collision it would drop rather than overwrite silently. Add a vote test with one model's ticker null.

---

## Should-fix

### F1. An Alpaca failure while mapping a model's new ticker isn't contained: paid answers are lost, re-asked, and posts end at `error`

- **Where:**
  - `engine/engine/extract/score.py:43-53` (`new_ticker_adder` catches only `DoesNotCount`);
  - `engine/engine/extract/ai.py:542` (`await add_new(...)`, inside `AiPicker.pick` after the answers are in);
  - `engine/engine/extract/batch.py:256-258` (builds `Listings(Alpaca(settings))` even with no Alpaca keys).
- **Problem:** an `AlpacaError` from `Listings.counts` escapes `map_item`, then `AiPicker.pick`, then `record_ai`. In the live stage it fails the whole handler transaction: the rules answer, the mentions, the vector and the three paid answers all roll back. The StageRunner then retries, which asks all three models again, and after `max_attempts` moves the post to `error`. In ai-pick it ends the run with a traceback, losing that post's paid answers.
  - The live path guards against missing Alpaca keys (`score.py:183`). The batch path doesn't: with no `ALPACA_API_*` keys, the first model answer that names a ticker not in the book raises `AlpacaKeysMissing`.
- **Failure scenario:** once PR 7 sets `ENGINE_AI_LIVE=true`, Alpaca has a 5xx streak. Every post whose answer names a new ticker costs three times the AI calls and drops out of the pipeline at `error`, with one operator message per post. Separately, a B2 `ai-pick` run on a machine without Alpaca keys crashes on the first new ticker.
- **Evidence:** `test_probe_alpaca_failure_in_ai_mapping.py` passes both tests.
  - `test_live_stage_retries_paid_ai_calls_and_ends_in_error`: stage is `error`, the error holds "AlpacaError", 0 extractions and 0 vectors are left, and each stub model was asked 3 times.
  - `test_ai_pick_without_alpaca_keys_crashes_on_a_new_ticker`: `AlpacaKeysMissing` escapes and 0 rows are recorded after 3 answers. The keys check comes first, so no Alpaca call is made.
- **Fix:**
  - In the adder, catch `AlpacaError` (and httpx errors) and return an outcome that `map_item` records as unmapped with a new reason, such as `listing_unchecked`. Log it once.
  - In `run_ai_pick`, build `Listings` only when `settings.alpaca_keys` is set, else pass `add_new=None`, as `score_worker` does.
  - More robust still: record the raw model answers before mapping, so a mapping failure never discards paid answers.

### F2. Answers that are billed but rejected keep no cost, no tokens and no body, so the cost guard and PR 4's $15 tracking undercount

- **Where:** `engine/engine/extract/ai.py`:
  - `OpenAIChat.ask` raises on `finish_reason != "stop"` or empty content (`:270-274`);
  - `AnthropicMessages.ask` raises on `stop_reason != "end_turn"` (`:332-333`);
  - `ask_model` builds the failed `ModelAnswer` without `reply` or `cost` (`:473-476`, `:493`), including when `parse_answer` rejects a reply it already holds.
- **Problem:** the provider bills these calls, but the extraction row gets NULL `cost_usd`, NULL tokens and NULL `response`. The brief's records keep "the raw response body … tokens … the cost". The guards sum recorded costs (`spent()` in `batch.py:173`, `cost +=` in `batch.py:270`), so they miss exactly the most expensive failures: an answer cut at `max_output_tokens` bills all 800 output tokens.
- **Evidence:** `test_probe_invalid_answer_cost.py` passes both tests.
  - A `finish_reason: "length"` reply through the real OpenAI SDK (mock transport, 1500 in and 800 out, so $0.0094 billed) is recorded with `(cost_usd, output_tokens, response) == (None, None, None)`.
  - An invalid-JSON reply with 800 output tokens adds $0 to ai-pick's running total.
- **Fix:** have `ask()` return the `Reply` (with `finish_reason`/`stop_reason` on it) and let `ask_model` validate it. On any failure after a reply exists, keep `reply` and `cost` on the failed `ModelAnswer`; `AiPick.extractions` already writes them through. Add a test.

### F3. ai-pick turns a systemic provider error into permanent version-1 records for the whole batch

- **Where:** `engine/engine/extract/batch.py:259-275` (no stop on a non-retryable error), `:200` (`select_posts` skips any post with an `ai:vote` row for the version and run), and `ai.py:749-755` (a provider without a client counts as failed and the vote is still recorded).
- **Problem:** a wrong `ENGINE_*_KEY` (401), a revoked key (403) or a mistyped model id (404) fails every post the same way. ai-pick carries on, pays the other two providers for every post, and records each post's failed answer plus a two-model vote as run 1. Records never overwrite and `select_posts` excludes those posts, so a rerun with the key fixed asks nothing. The same happens if a run starts before all three keys exist.
- **Failure scenario:** B2's first real run over the 300 precision posts with one bad key. The AI precision is then measured on a two-model vote for good, unless the version is bumped or rows are deleted by hand.
- **Evidence:** `test_probe_ai_pick_bad_key.py::test_a_wrong_key_poisons_the_whole_batch` passes. The exit code is 0, the bad model was asked once per post (5 of 5), the good models were paid 5 times each, and 5 `ai:openai` rows hold the 401. A rerun with fixed clients prints "0 posts" and never asks the fixed model.
- **Fix:**
  - In `run_ai_pick`, treat `AuthenticationError`, `PermissionDeniedError`, `NotFoundError` and `BadRequestError` from either SDK as fatal. Roll back that post's transaction, print one line, and return non-zero.
  - Refuse to start unless all three providers have clients, or require an explicit flag.
  - Optionally ask one canary post first.

### F4. One model's new ticker becomes a rules bare ticker immediately, so frozen rules v1 changes its answers over time

- **Where:** `engine/engine/extract/ai.py:538-546` (`add_new` then `book.add`; a single model is enough, the vote isn't needed); `engine/engine/extract/rules.py:401-415` (bare tickers match any instrument in the book), with the book loaded from `engine.instruments`.
- **Problem:** brief section 2 has every instrument symbol used as a bare word read against up to 10 posts and collision-listed if any use isn't the company, and the rules version is meant to pin the rules' behaviour. Instruments the AI adds later skip that review: on the next load they match as bare capitals in every post, under the same rules version 1.
- **Failure scenario:** a model names Intercontinental Exchange (ICE, which owns the NYSE) on any post. From then on, every "ICE agents arrested …" post is scored by rules v1 as topic `companies` with a market link and a counted ICE mention. ICE is not on the collision list. 5 of the 300 held-out posts contain bare "ICE", roughly 360 posts across history.
  - Live posts get false market links.
  - `extract` is idempotent per version, so history scored before the add and history scored after it disagree under one version number.
- **Evidence:** `test_probe_ai_added_ticker_changes_rules.py::test_an_ai_added_ticker_turns_into_a_rules_bare_ticker` passes. Before the add: no symbols, `border_crime`, no market link. After `map_item` adds ICE: `("ICE",)`, `companies`, market link, version still 1.
- **Fix:** without dropping the brief's rule, add a list of tickers that have been reviewed for bare-word use to the rules files. It can sit in `aliases.json` or next to `collisions.json`, under the rules hash and version. Bare-word matching then applies only to those. AI-added instruments count by cashtag or alias until a rules version reviews them; review-list already surfaces them. If the planner prefers to keep "any instrument in engine.instruments", collision-check every new symbol before `add_new` succeeds.

### F5. A model's ticker for an existing instrument maps outside that ticker's dates, skipping PR 3's "counts at the post's time" check (coordinator's lead, confirmed)

- **Where:** `engine/engine/extract/ai.py:531-546`, `engine/engine/market/instruments.py:188-189` (`add_instrument` returns an existing symbol before `listings.counts`), and `engine/engine/extract/rules.py:329-332` (`NameBook.add` appends a hold with no start or end).
- **Problem:** `book.ticker(ticker, on)` correctly says the ticker wasn't this instrument's on the post's date, so `map_item` falls through to `add_new`. `add_instrument` finds the existing row by symbol and returns it without the counts check. `book.add` then gives it an open-ended hold and the mention is counted.
  - Affected windows in aliases.json: VG (listed 2025-01-24), PSKY (2025-08-07), META as a ticker (2022-06-09). DJT is safe because it is collision-listed.
  - The rules are unaffected: the live stage and ai-pick pick the rules from a book loaded before `record_ai`, and books are reloaded per post. The damage is the post's AI mentions and its vote.
- **Failure scenario:** a January 2024 post about the LNG export pause. Models imply Venture Global, VG, which was not listed then. The vote counts VG and PR 5 grades a pre-IPO name. Likewise a 2024 "Paramount" post mapped to PSKY, while aliases.json treats pre-merger Paramount Global as delisted and unmapped.
- **Evidence:** `test_probe_existing_ticker_outside_dates.py::test_an_existing_ticker_maps_before_its_hold_starts` passes for PSKY on 2024-05-01, META on 2022-05-02 and VG on 2024-01-27. In each case `book.ticker` is None for that date, the mention is counted anyway, `CountsAll.asked == []` (no counts check ran), and afterwards the ticker maps even on 2000-01-03 in that book.
- **Fix:** in `map_item`, if `ticker in book.tickers` (the instrument exists but isn't that ticker's holder on the date), return `unmapped("not_listed_then")` instead of calling `add_new`. Have the adder report "new" versus "existing", and call `book.add` only for a really new instrument.

### F6. A missing `sync-names` sends every new live post to the final `error` stage

- **Where:** `engine/engine/extract/names.py:19-33` (`load_book(check=True)`), called per post from `Scorer.handle` (`score.py:132`) and `record_ai` (`score.py:97`).
- **Problem:** `NamesNotSynced` is raised per post, inside the stage. Each post burns its attempts and lands at `error`, with one operator message per post. It stays there after the operator syncs. Missing model files, by contrast, fail the worker at start and leave posts waiting at `score` (`score.py:179`), which is what the brief asks for a misconfigured deploy.
- **Failure scenario:** each rules-version deploy that changes aliases.json runs ahead of `sync-names`. Every post in that gap is lost to `error` until someone resets the stages by hand.
- **Evidence:** `test_probe_unsynced_names_error_posts.py::test_unsynced_names_send_live_posts_to_error` passes. Both posts are at `error` with NamesNotSynced, including after a later sync and two more runner passes.
- **Fix:** in `score_worker`, load and check the book once at start and fail the worker there, the same path as ModelMissing. Per post, call `load_book(..., check=False)`, or reuse a book refreshed per tick.

### F7. The reason-line rule check passes lines that state a direction

- **Where:** `engine/engine/extract/reason.py:17-25` (`DIRECTION`).
- **Problem:** the brief says "A rule check rejects lines that break this". The prompt itself bans "up" and "down", but the regex has neither. It also lacks higher/lower, increase/decrease, benefit, decline, pressure, tailwind/headwind, strengthen/weaken and "good/bad news for".
- **Evidence:** `test_probe_reason_check_gaps.py` passes for all 11 lines. Examples: "Steel tariffs could send Nucor higher", "Drug price cuts may push Pfizer down", "New tariffs benefit US steel makers like Nucor", "Chip export ban could cause Nvidia sales to decline", "A tailwind for Lockheed Martin and Northrop Grumman", "Bad news for Pfizer and Merck".
- **Fix:** add `up|down|higher|lower|increas\w*|decreas\w*|benefit\w*|declin\w*|pressur\w*|headwind\w*|tailwind\w*|strengthen\w*|weaken\w*|(?:good|bad|great|terrible)\s+(?:news\s+)?for|upbeat|gloomy`. Failing closed is fine here, since a rejected line means the alert goes out without one. Add these lines to the parametrised test.

### F8. `AiPicker` and `Scorer` reprs print the three keys in plain text

- **Where:** `engine/engine/extract/ai.py:711-724`. `@dataclass class AiPicker` has a `secrets: Sequence[str]` field built from `settings.ai_keys.values()`. `Scorer` (`score.py:117`) is a dataclass holding the picker.
- **Problem:** Settings keeps the keys as `SecretStr`, and the picker undoes that. Several things format reprs: pytest failure output, `--showlocals`, any `log.*("%r", ...)`, and error trackers that capture locals. Each would print the keys. No current code path does this, which is why this is Should-fix rather than Blocker, but the builder's goal is "keys never appear in logs".
- **Evidence:** `test_probe_picker_repr_keys.py::test_the_picker_and_the_scorer_print_the_keys` passes. All three fake keys are in `repr(picker)` and `repr(scorer)`, while `repr(settings)` hides them.
- **Fix:** `secrets: Sequence[str] = field(default_factory=tuple, repr=False)`, or keep them as `SecretStr` and unwrap them in `scrubbed`. Add the repr check to the keys test.

### F9. The Anthropic client follows a cross-host redirect with `x-api-key`

- **Where:** `engine/engine/extract/ai.py:305-311`. The production path passes no `http_client`, so the SDK's default client follows redirects. The same holds for `OpenAIChat` at `:240-246`, but httpx strips `Authorization` there.
- **Problem:** pinning `base_url` stops the environment variables from redirecting a key, but not an HTTP 3xx. httpx and httpx2 strip only `Authorization` on a cross-origin redirect. Anthropic's key travels in `x-api-key`, so it would be forwarded. PR 3's Alpaca client refuses redirects for this exact reason ("keys stay on this host").
  - Likelihood is low: only the pinned host, or an intercepting proxy that already sees the key, can send the redirect. That is why this is Should-fix and not Blocker; the fix is one line.
- **Evidence:** `test_probe_redirect_key.py` passes both tests.
  - Anthropic: `production.client._client.follow_redirects is True`. With the SDK's own `DefaultAsyncHttpxClient` and a mock transport, a 307 from api.anthropic.com to elsewhere.example arrives with `x-api-key` set to the key.
  - Contrast: the OpenAI bearer is dropped on the same redirect.
- **Fix:** pass `http_client=anthropic.DefaultAsyncHttpxClient(follow_redirects=False)`, and `openai.DefaultAsyncHttpxClient(follow_redirects=False)` for both OpenAI-SDK clients. A 3xx then becomes an error, which the scrubber already handles.

### F10. Tests for brief-listed behaviours pass vacuously or are missing (mutation survivors)

Of 18 mutations, 6 were killed (M6, M13–M18 cover base URLs, scrubbing, the spend stop, run-2 isolation, timeout no-retry and the vote). These survived, meaning the PR's own tests still pass:

- **M2: `AiPicker.from_settings` passes `()` as secrets.** It survives `test_ai.py`, `test_score.py` and `test_batch.py`. The production wiring that scrubs keys from errors is untested: `test_keys_never_reach_errors_or_logs` passes `secrets=` to `ask_model` by hand. A regression would put an echoed key into `engine.extractions.error`, which the web role reads, and into logs.
- **M10: `live_ai` drops the `ENGINE_AI_LIVE` check.** It survives. `test_the_ai_is_off_by_default` gets `(None, None)` only because ai.json isn't ready yet (xAI model unpinned, prices unchecked), so the brief-listed test "the AI is off by default" proves nothing until B2.
- **M1** (SDK `APITimeoutError` becomes retryable), **M3** (AI keys skip the header-safety validator, the h11 "Illegal header value" guard) and **M5** (batch `retries=3` set to 0).
- **M4** (a new collision ticker skips the name check before `add_new`).
- **M12** (the projection ignores output price). It survives because each provider's projection is rounded to cents before comparison, so `$0.03` comes out either way.

**Fix:**
- Build the picker via `from_settings` with fake ENGINE_ keys in a test, with a mock 401 echoing the key, and assert the recorded error and logs are scrubbed.
- Run `live_ai` against a ready config (monkeypatch `current_ai_config` to `ready_config()`) with keys set and `ai_live=False`.
- Add one test each for M1, M3, M4 and M5.
- Compare the unrounded projection with `--max-usd` (see N2).

---

## Nit

- **N1.** One ENGINE_ key builds a picker that can only fall back (`ai.py:719-724`). With one client every vote is `ai_fallback`, yet that model is asked and paid on every post. Evidence: `test_probe_one_key_picker.py` passes (`fallback=True, answered=1`, stub asked). Fix: return None from `from_settings` unless at least 2 clients exist, and refuse in ai-pick (see F3).
- **N2.** `--max-usd` takes `nan` and `Infinity` (`cli.py:59`).
  - `nan` crashes with `decimal.InvalidOperation` at `batch.py:250`. `Infinity` turns the guard off.
  - The projection is rounded to cents per provider (`batch.py:169`) before the `>` comparison, so a small run can project as $0.00.
  - Evidence: `test_probe_max_usd_values.py` passes both tests.
  - Fix: `type=` a validator requiring a finite value of 0 or more, and compare unrounded totals.
- **N3.** Expected operator errors from the new commands are tracebacks, not one line and an exit code (`cli.py:110-133`). Examples: `extract` or `ai-pick` before `sync-names` (NamesNotSynced), a wrong `--keys` path (FileNotFoundError), `sync-names` or `ai-pick` with an Alpaca failure, and `fetch-model` with a network error (only ModelMissing is caught). PR 3's `backfill-bars` catches AlpacaError per item. Evidence: `test_probe_cli_tracebacks.py` passes both tests. Fix: catch NamesNotSynced, RulesFileChanged, AlpacaError, NotReady, OSError and httpx.HTTPError in `_extract_command`; print one line and return 1.
- **N4.** The SDKs still read `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`, `OPENAI_CUSTOM_HEADERS` and `ANTHROPIC_CUSTOM_HEADERS` from the environment, and send them as headers, including to api.x.ai (`ai.py:240-246`, `:305-311`). The old system doesn't set them today; I grepped. Evidence: `test_probe_sdk_env_headers.py` passes. Fix: pass `organization`/`project` explicitly and strip those headers via `default_headers`, or document the variables as forbidden for the engine.
- **N5.** Prompt caching never applies on Anthropic (`ai.py:319-330`). The brief puts the fixed prompt first "so the providers' prompt caching applies". Anthropic caches only at a `cache_control` marker, and `system` is sent as a plain string with no marker. `Price.cost` has no cache-write rate (1.25× input) either. The prompt is about 4 KB, roughly 1k tokens, close to the 1,024-token minimum for both OpenAI and Anthropic, so B2 should check whether caching happens at all. Evidence: `test_probe_anthropic_no_cache.py` passes. Fix: `system=[{"type": "text", "text": instructions, "cache_control": {"type": "ephemeral"}}]`, plus a `cache_write` price.
- **N6.** An alias word inside a longer model name beats a conflicting ticker (`ai.py:519-521`). "Apple Hospitality REIT"/APLE maps to AAPL, and "Meta Materials"/MMAT maps to META. Evidence: `test_probe_alias_inside_longer_name.py` passes. Fix: when the model's ticker is a different, mappable instrument, prefer the ticker or mark the mention as a conflict.
- **N7.** The score worker this PR registers polls `engine.signals` every second (`ENGINE_SCORE_TICK_SECONDS=1`). It runs `WHERE stage IN ('score') ORDER BY key LIMIT 100` with no stage index, which walks the whole table (about 36.6k rows) 86,400 times a day on serverless Postgres. Evidence: `test_probe_score_poll_seq_scan.py` passes (no stage index; the plan filters row by row). Fix: a partial index `ON engine.signals (key) WHERE stage NOT IN ('done','error')` in 0004, or a longer tick.
- **N8.** Dead code, against the brief's "build nothing before something uses it":
  - `records.has_extraction` (`records.py:108`);
  - `NameBook.names_of` (`rules.py:367`);
  - `tests/replay.replay_embedder`. It is never called, so the replay never uses "the real model when its files are present", which the brief asks for.
- **N9.** Rules rows record `started_at == finished_at` (`score.py:134`, `batch.py:72-73`), so the timing columns carry nothing. Take `finished` after `pick()`.
- **N10.** The first model's free-text name becomes the new instrument's permanent `name` (`score.py:48`, then `add_instrument`), and the web role reads `engine.instruments`. Example: "US steel makers (Nucor)". Use the alias file's name or Alpaca's asset name, or keep the model's text off the instrument.
- **N11.** The replay harness's `deliver` hook runs inside the stage transaction, before commit (`score.py:150-151`, `tests/replay.py:114`). It is marked delivered even if the transaction rolls back. PRs 6 and 8 will fill it, so call it after the stage commits.
- **N12.** Window boundaries are UTC midnights: `scripts/samples.py:34` (`WINDOW_START`) and `scripts/precision.py:197` (`--window-start`). ai-pick dates and the brief's "start of the next day" read as New York days, so up to about 4 hours of posts can land in the wrong group. Pick one zone and say which.

---

## Questions

- **Q1. Held-out timing of `rules.py`.**
  - The data files, labels and samples are provably frozen: the rules data files (topics, aliases, collisions, `rules.json`) and the labels are unchanged since f442395 (20:01), samples.csv since 84b6602, and nothing after them touches these files.
  - But the code that interprets the files, `engine/extract/rules.py`, first appears in 997fe4c (20:34), 33 minutes after the labels. That includes the bare-ticker regex, the hyphen rule, the topic `names` flag and the veto semantics.
  - Git can't show that it wasn't adjusted against the labelled posts in that window. Can the builder confirm that no rules-versus-labels comparison ran before 997fe4c? `rules-precision.md` is stamped 20:38.
- **Q2. AI picker version versus its content in B2.**
  - `ai.json`'s `version` doesn't change when the pinned hashes change, so nothing forces a bump.
  - `select_posts` keys idempotence on the version only. Per-model rows don't store `picker_hash`; only the vote row does.
  - So a second prompt round on the dev set prints "0 posts" unless the version is bumped. Bumping each round means the frozen picker won't be "version 1".
  - How should B2 iterate? Suggestion: key `_lacks` on `(version, picker_hash)`, or keep a committed hash-to-version history that the loader enforces.
- **Q3. Live backlog and live spend.** Until B1, live posts wait at `score`. When the model lands, and especially once PR 7 sets `ENGINE_AI_LIVE`, the whole backlog is AI-picked at once, and the live stage has no spend cap. Is that intended to be handled in PR 7? For example, skip AI for posts older than N hours, or apply a daily cap.
- **Q4. The $15 PR 4 cap.** The tool enforces `--max-usd` per run only. Repeated runs aren't capped against `spent()`, and two concurrent runs both pay, with the second one's records dropped by `ON CONFLICT DO NOTHING`, so `spent()` misses that spend. Is a cumulative `--max-total-usd` (spent plus projected) wanted?

---

## Checked and dropped

- **Base URLs pinned against the environment.** `OPENAI_BASE_URL` and `ANTHROPIC_BASE_URL` are ignored because `base_url` is explicit. Tests set both variables and assert the host. Mutations M6 and M13 were killed.
- **SDKs falling back to the old credential variables.** I read the SDK source for openai 2.54 and anthropic 1.11:
  - openai reads `OPENAI_API_KEY` only when `api_key is None`;
  - anthropic reads `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` only when no explicit credential is passed.

  Explicit `api_key=` blocks both, and no client is built without its ENGINE_ key.
- **The h11 "Illegal header value" path.** The settings validator restricts ENGINE_*_KEY to printable ASCII with no spaces, and h11 accepts every such character. Both SDKs wrap transport errors as "Connection error." without the cause text, and `ask_model` logs without `exc_info`. The only gap is test coverage (M3 in F10).
- **Scrubbing.**
  - `ask_model` errors and reason-line logs are scrubbed (M14 and M7 killed).
  - InvalidAnswer and timeout messages carry no key, and `Reply.body` is the response body only.
  - No exception that escapes into `signals.error` or operator messages carries an AI key; Alpaca errors are scrubbed by PR 3.
  - OpenAI and xAI 401 bodies show masked fragments (prefix and last 4 characters), not the key. Acceptable.
- **The vote rules.** All three agree, 2 of 3, one failed so the other two must agree, two failed so the rules stand in as `ai_fallback`, and a timeout counts as missed and is never retried, for both asyncio and SDK timeouts. All are correct; M11, M17 and M18 were killed.
- **Records idempotence.**
  - `extract`, `ai-pick` and the stage rerun cleanly: `ON CONFLICT DO NOTHING` on `extractions_key`, and mentions are written only for a new run-1 row.
  - Run 2 is isolated (M16 killed) and embeddings are keyed per (post, model version).
  - Per-post transactions mean a crash loses at most that post, with no partial rows. Paid answers lost that way are covered in F1.
- **Cost guard happy path.** The refusal over projection and the in-run stop both work (M15 killed). The projection is conservative on caching and fair on input, since the schema's tokens are small next to 3.5 characters per token.
- **Cancellation.** `ask_model` catches `Exception` only, so CancelledError propagates through retries and back-off sleeps. The SDKs don't convert cancellation into APIConnectionError. No new retry loop catches database errors, so `raise_if_cancelling` isn't needed there; StageRunner and Alpaca keep theirs.
- **Migration 0004.**
  - Add-only, and the downgrade reverses it.
  - It matches tables.py (`test_migrations_match_table_definitions`).
  - No GRANT is added. `WEB_GRANTS` `engine.*` SELECT covers the new tables, and nothing goes to `app` or `prices`.
  - No price is stored. The new tables hold provider response bodies and errors, which are not private, apart from the F2/F10 caveats.
- **Public-repo rule.**
  - The only key-like strings in the diff are fake test keys under ENGINE fields.
  - The AI fixtures are hand-made bodies with no request headers.
  - `samples.csv` and `labels.csv` hold ids and labels only, with no text and no prices.
  - Post text is only in `/mnt/project-files`.
- **Held-out discipline.**
  - The labels equal exactly the 300 `precision_*` keys, and the sets in samples.csv are disjoint.
  - The label-guide and prompt examples (McDonald's, Tim Apple, Jensen, Rumble) appear in none of the 300.
  - The rules' measured misses (S&P Global, TKO, FWONK) were not added to aliases afterwards.
  - The precision table, recomputed from the spot-check file, matches the PR: 34/52 and 34/44 for the window, 9/17 and 9/9 for early, and topic agreement of 129 and 55.
- **Quoted text** goes to the AI only when the quoted signal exists. Quotes in history are left as posts, as the brief allows.
- **Matching** excludes the post itself and anything at or after `before`, takes the top k, and applies the threshold. **`fetch_model`** checks hashes, cleans up partial files and reports hosts.
- **Score worker failing at start before B1** (ModelMissing) is by the brief, and the PR body discloses it.
- **The brief's "tests never build a real client".** Tests construct SDK client objects with fake keys and mock transports only. No network is touched, so this matches the rule's intent.
- **Anthropic temperature via `extra_body`.** Disclosed; B2 verifies it.
