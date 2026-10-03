# PR #261 "Engine PR 4: extraction and similarity": review round 1

**Reviewed:** df77049, PR 4's own commits on top of PR 3 (`git diff 56a32f7 df77049`, 46 files, +6,242). Completion was judged against Part A of build-briefs/engine-pr4.md. B1 and B2 are out of scope for this round.

**Passes**, each in a fresh agent:
- **simplify:** the built-in simplify lens, report-only, with each change tried on a scratch checkout.
- **review:** the built-in code-review at high effort plus clauDNA review-work. It wrote 32 probes and ran 18 mutations.
- **verify:** clauDNA verify-completion against Part A. It ran 35 mutations and did by-hand runs against a local fake AI server and a trap proxy that logged zero outbound calls.

I re-ran the blocker probe and all 32 review probes myself (32 pass at df77049).

**Your head has moved since:** 2c1ffcc (PR 3 merged), b494bad (B1 started) and 6a24a0b (the test_live flake fix). Round 2 will cover the fixes, the B1 delta after df77049, and the merges.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 382 with 1 skip (the real-model test, waiting for B1), three times, once as the `engine` role like CI.
  - Alembic has one head (0004), and upgrade, downgrade and upgrade of 0004 work. CI is green on df77049.
- **Part A is complete.** Every item in the brief is present; verify's checklist has file:line for each.
- **The precision numbers reproduce exactly:**
  - Re-running the committed rules picker over the 300 posts gives 0 differences.
  - `scripts/precision.py` gives a table identical to rules-precision.md.
  - The 102 labelled posts in the offline CC0 copy match the spot-check file.
- **Held-out discipline holds:** samples (19:43), then labels (f442395, 20:01), then picker code (997fe4c, 20:34). The rules files are unchanged since the labels, and no prompt example appears in the 300. Q1 asks one thing git can't show.
- **By hand, on throwaway databases:**
  - `extract` is idempotent, and `status` shows the score stage.
  - `embed`, `fetch-model` and `ai-pick` refuse with one line when they're not ready.
  - With the AI on against the fake server, the live stage moves posts to `done` with three answers and a vote.
  - A fake 401 that echoes the key is stored and logged as `[key]`.
  - A 17 s answer counts as a timeout, and the other two models decide.
- **Checked clean:**
  - explicit keys and base URLs pinned against `*_BASE_URL`;
  - scrubbing of SDK errors and h11 header text;
  - the 2-of-3 vote and its fallback;
  - run-2 isolation and the in-run spend stop;
  - cancellation;
  - migration 0004: add-only, and the web role reads nothing private;
  - the public-repo rule: fake test keys only, and the CSVs hold ids and labels only.

**Result: changes needed.** 1 blocker, 10 should-fix, 15 nits, 9 optional simplifications and 4 questions.

## How to answer

- Fix each blocker and should-fix, or decline it with a reason. Nits and simplifications are optional.
- Push the fixes with your B1 commits if that's easier, and send me the head with one line per id.

**Probes:** [pr-261-round-1-probes/](pr-261-round-1-probes/)
- `review/`: run with `review/run_probe.sh <file>` after pointing `WT` at your checkout's `engine/`. Each `test_probe_…` passes while its finding stands.
- `verify/`:
  - `fake_ai.py` is the local fake AI server, and `trap_proxy.py` logs any outbound attempt.
  - `stage_probe.py` and `ai_probe.py` drive the stage and `ai-pick`.
  - `mutate.py` and `mutations.txt` hold the mutation runs.
- `simplify/simplify.patch`: the tried simplifications. It applies to df77049, and the full suite passes with it.
- The three passes' own write-ups: `review-findings.md`, `verify-findings.md` and `simplify-findings.md`.

Copy the probes into engine/tests/ to run them. Don't commit them as they are, except as tests you adopt.

---

## Blocker

### B1. A counted vote mention is silently dropped from `engine.signal_mentions` (review)
- **Where:**
  - records.py:102 dedups mentions by `normalized`, and the last one wins.
  - ai.py:598-633: `vote()` appends the unmapped `by_name` mentions after the mapped `by_instrument` ones.
- **Problem:**
  - Two models give a name with a ticker, so it maps and counts 2 of 3.
  - The third gives the same name with `ticker: null`, which the prompt allows, so it's unmapped with `no_ticker`.
  - The unmapped row overwrites the counted one, and the counted row is never written.
  - Most AI names map by ticker, since aliases cover only 61 instruments.
- **Effect:** the vote's `result` says `symbols: ["NVDA"]`, but `signal_mentions` holds only the uncounted row. All three readers miss the counted name, for good:
  - review-list;
  - `scripts/precision.py` (B2's AI precision);
  - PR 5's backtest, which reads mentions by instrument and post time.
- **Evidence:**
  - `test_probe_vote_mentions_dedup.py::test_counted_vote_mention_is_lost_when_a_model_gives_null_ticker` passes. I ran it too.
  - No test makes two mentions with one normalised name. Removing the dedup survives the suite, and would hit the unique key instead.
- **Fix:**
  - In `vote()`, emit no unmapped row for a name whose `normalized` matches a mapped vote mention, and leave `models` as is. Or key mentions on `(extraction_id, normalized, instrument_id)`.
  - Either way, make `record()` raise on a collision instead of overwriting it.
  - Add a vote test where one model's ticker is null.

## Should-fix

### S1. An Alpaca failure while mapping a new ticker loses three paid answers (review F1, verify V1)
- **Where:** score.py:43-53. `new_ticker_adder` catches only `DoesNotCount`, and `map_item` runs after the three model calls (ai.py:542, batch.py:256-275).
- **Problem:** missing Alpaca keys, a 5xx or 429 after retries, or a dropped connection rolls back the post's transaction. The answers and their `cost_usd` are never recorded.
- **Effect:**
  - `ai-pick` dies with a traceback.
  - `spent()` undercounts, and a rerun pays again.
  - Live, the stage pays up to `max_attempts` times and then moves the post to `error`.
- **Evidence:**
  - `test_probe_alpaca_failure_in_ai_mapping.py`, both tests: the stage ends at `error` with each model asked 3 times, and `ai-pick` without Alpaca keys loses everything.
  - By hand, 6 provider calls left 1 post recorded.
- **Fix:**
  - Catch `AlpacaError` and httpx errors in the adder, and record the mention as unmapped with a new reason such as `count_check_failed`.
  - In `run_ai_pick`, pass `add_new=None` when there are no Alpaca keys, as `score_worker` does.
  - Better still, record the raw answers before mapping.
  - Add a test with a `Listings` stub that raises.

### S2. Answers that are billed but rejected keep no cost, tokens or body (review F2)
- **Where:**
  - ai.py:270-274: `finish_reason != "stop"` or empty content.
  - ai.py:332-333: `stop_reason != "end_turn"`.
  - ai.py:473-476 and :493: the failed `ModelAnswer` drops `reply` and `cost`, even when `parse_answer` rejects a reply it already holds.
- **Problem:** the brief's records keep "the raw response body … tokens … the cost". A reply cut off at `max_output_tokens` bills all 800 output tokens and records NULLs, so `spent()` and the `--max-usd` running total miss the most expensive failures.
- **Evidence:** `test_probe_invalid_answer_cost.py`.
  - A `length` reply ($0.0094 billed) is recorded as `(None, None, None)`.
  - An invalid-JSON reply adds $0.
- **Fix:** have `ask()` return the `Reply` with its finish or stop reason, and let `ask_model` validate it. Keep `reply` and `cost` on every failure after a reply exists, and add a test.

### S3. `ai-pick` turns a bad key into permanent run-1 records for the whole batch (review F3, N1)
- **Where:**
  - batch.py:259-275: no stop on an error no retry can fix.
  - batch.py:200: `select_posts` skips posts that already have a vote.
  - ai.py:749-755: a provider with no client counts as failed.
- **Problem:** a wrong key (401), a revoked key (403) or a mistyped model id (404) fails every post the same way. `ai-pick` still pays the other two models, records the failed answer plus a two-model vote as run 1, and exits 0. A rerun with the key fixed asks nothing. The same happens if a run starts with fewer than three keys.
- **Effect:** B2's first real run over the 300 posts with one bad key would measure AI precision on a two-model vote for good.
- **Evidence:** `test_probe_ai_pick_bad_key.py`.
  - 5 of 5 posts were poisoned, and the run exited 0.
  - The rerun printed "0 posts".
- **Fix:**
  - Treat `AuthenticationError`, `PermissionDeniedError`, `NotFoundError` and `BadRequestError` from either SDK as fatal. Roll back that post, print one line and exit non-zero.
  - Refuse to start without all three clients.
  - This also covers N1: one key builds a picker that always falls back, yet pays that model on every post (`test_probe_one_key_picker.py`).

### S4. A deploy that skipped `sync-names` sends every live text post to the final `error` stage (review F6, verify V2)
- **Where:** names.py:19-33 `load_book(check=True)`, called per post from `Scorer.handle` (score.py:126-134) and `record_ai` (score.py:97). Nothing checks this at worker start (score.py:177-191).
- **Problem:** each post burns 3 attempts and ends at `error`, with one operator message per post. It stays there after the sync. A missing model, by contrast, fails the worker at start and posts wait at `score`, which is what the brief wants for a misconfigured deploy.
- **Evidence:**
  - `test_probe_unsynced_names_error_posts.py`.
  - By hand, 9 posts went to `error` and 9 notices were sent.
- **Fix:** check the book once at worker start, next to `load_embedder`. Load it per post with `check=False`, or reuse one book per tick. Add a stage test with names unsynced.

### S5. A model's ticker for an existing instrument maps outside that ticker's dates (review F5, simplify)
- **Where:**
  - ai.py:531-546 falls through to `add_new` when `book.ticker(ticker, on)` is None.
  - instruments.py:188-189: `add_instrument` returns the existing row before the counts check.
  - rules.py:329-332: `NameBook.add` gives it an open-ended hold.
- **Problem:** PR 3's "counts at the post's time" check is skipped, so the mention counts. For example, a January 2024 LNG post maps to Venture Global (VG, listed 2025-01-24), and PR 5 grades a pre-IPO name. PSKY on 2024-05-01 and META on 2022-05-02 behave the same way.
- **Effect:** the damage is that post's AI mentions and vote. The rules for the post were picked from an earlier book, and books are reloaded per post.
- **Evidence:** `test_probe_existing_ticker_outside_dates.py` passes for all three cases. No counts check runs, and afterwards the ticker maps even on 2000-01-03 in that book.
- **Fix:**
  - If the ticker is in the book but not on that date, return `unmapped("not_listed_then")` instead of calling `add_new`.
  - Have the adder say whether the instrument is new, and call `book.add` only when it is.
  - Verify's M11 (S10) is the missing test for the post's-time check.

### S6. One model's new ticker becomes a rules bare ticker at once, so frozen rules v1 changes its answers (review F4, verify Q1)
- **Where:** ai.py:538-546 adds an instrument on one model's say-so, with no vote needed. rules.py:401-415 then matches every instrument in `engine.instruments` as a bare capital.
- **Problem:** the brief's section 2 reviews every bare symbol against up to 10 posts and collision-lists it, and the rules version pins the rules' behaviour. AI-added instruments skip that review and change rules v1's answers from the next load on.
- **Effect:** a model names Intercontinental Exchange (ICE) once. From then on, every "ICE agents …" post scores as `companies` with a market link and a counted ICE mention. That covers 5 of the 300 held-out posts and about 360 across history, with history scored before and after the add disagreeing under one version.
- **Evidence:** `test_probe_ai_added_ticker_changes_rules.py`.
- **Fix:**
  - Give the rules files a list of tickers reviewed for bare-word use, under the rules hash and version. AI-added instruments then count by cashtag or alias until a new rules version reviews them.
  - Or collision-check every new symbol before `add_new` succeeds.
  - If you think this needs the planner, say so and I'll pass it on.

### S7. The reason-line check passes lines that state a direction, a price or advice (review F7, verify V3)
- **Where:** reason.py:17-25 (`DIRECTION`), used by `check_reason` at :30-40.
- **Problem:** the brief says "a rule check rejects lines that break this", and the prompt itself bans "up" and "down". All of these pass:
  - "Steel tariffs could send Nucor higher"
  - "Drug price cuts may push Pfizer down"
  - "Nvidia could go up after the chip deal"
  - "New tariffs benefit US steel makers like Nucor"
  - "Chip export ban could cause Nvidia sales to decline"
  - "A tailwind for Lockheed Martin", "A headwind for Apple"
  - "Bad news for Pfizer and Merck"
  - "Expect Nvidia to outpace rivals"
  - "Apple at 200 after the tariff news"
  - "Investors may want to watch Boeing"
- **Evidence:** `test_probe_reason_check_gaps.py`, all 11 lines.
- **Fix:**
  - Add `up|down|higher|lower|increas\w*|decreas\w*|rais\w*|doubl\w*|halv\w*|benefit\w*|declin\w*|pressur\w*|headwind\w*|tailwind\w*|strengthen\w*|weaken\w*|outpac\w*|(?:good|bad|great|terrible)\s+(?:news\s+)?for|watch|investors?`.
  - Reject numbers that aren't in the post.
  - Failing closed is fine, because a rejected line just means no line. Add these cases to the parametrised test.

### S8. The `AiPicker` and `Scorer` reprs print all three keys (review F8)
- **Where:** ai.py:715. `secrets: Sequence[str]` is a plain dataclass field, and `Scorer` (score.py:117) holds the picker.
- **Problem:** Settings keeps the keys as `SecretStr`, and the picker undoes that. Pytest failure output, `--showlocals`, any `%r` log and error trackers that capture locals would all print the keys.
- **Evidence:** `test_probe_picker_repr_keys.py`: all three fake keys appear in `repr(picker)` and `repr(scorer)`.
- **Fix:** `field(default_factory=tuple, repr=False)`, or keep them as `SecretStr` and unwrap them in `scrubbed`. Add the repr check to the keys test.

### S9. The Anthropic client follows a cross-host redirect still carrying `x-api-key` (review F9)
- **Where:** ai.py:305-311. No `http_client` is passed, and the SDK default follows redirects. httpx strips only `Authorization` across origins.
- **Problem:** PR 3's Alpaca client refuses redirects for exactly this reason. Pinning `base_url` doesn't stop a 3xx.
- **Evidence:** `test_probe_redirect_key.py`: a 307 to elsewhere.example arrives with `x-api-key` set. The OpenAI bearer is dropped on the same redirect.
- **Fix:** pass `http_client=anthropic.DefaultAsyncHttpxClient(follow_redirects=False)`, and the same for both OpenAI-SDK clients (ai.py:240-246). The scrubber already handles the resulting error.

### S10. Safety properties the brief names have no test, or pass only by accident (review F10, verify V4)

Each of these mutations survives the PR's tests:

| Property | Where (df77049) | Found by |
| --- | --- | --- |
| The AI is off unless `ENGINE_AI_LIVE`. `test_the_ai_is_off_by_default` passes only because `ai_picker.json` isn't ready. | score.py:156-157, test_score.py:394-403 | both |
| `from_settings` passes the keys to the scrubber. Passing `()` survives, because the key test sets `secrets=` by hand. | ai.py:719-724 | review |
| A new AI ticker is checked at the post's time. Passing `now` survives, because `CountsAll` ignores `at`. | ai.py:542 | verify |
| A collision ticker not yet in the book needs its name before `add_new`. | ai.py:540-541 | both |
| A changed `picker.md`, `ai_picker.json` or `reason.md` is refused. | ai.py:159-165 | verify |
| AI keys go through the header-safety validator, the h11 guard. | settings.py | review |
| An SDK `APITimeoutError` is not retried. | ai.py | review |
| Batch retries happen (`retries=3`), and live doesn't retry. | batch.py, score.py:146-148 | both |
| The projection includes the output price. Rounding to cents hides it. | batch.py:169 | review |
| Matching excludes a post made exactly at `before`. | similarity.py:244 | verify |
| The reason line is dropped on a timeout. | reason.py:61-66 | verify |
| Quoted text goes to the AI only for a quote, not a reply's parent. | score.py:76 | verify |

- **Fix:**
  - Build the picker with `from_settings` and fake `ENGINE_*` keys, then send a mock 401 that echoes the key.
  - Run `live_ai` against `ready_config()` with keys set and `ai_live=False`.
  - Use a `Listings` stub that counts only within a date range.
  - Add one small test for each remaining row.
  - Give `test_missing_model_files_stop_the_worker_and_posts_wait_at_score` an `asyncio.timeout`. Today a regression there hangs the suite instead of failing it.

## Nits (optional, file:line at df77049)

- **N1. `--max-usd` accepts NaN and Infinity** (cli.py:59; review N2, verify V6).
  - NaN crashes with `InvalidOperation` at batch.py:250, and Infinity turns both guards off.
  - The projection is rounded per provider before comparing, so a small run can project $0.00.
  - **Fix:** require a finite value of 0 or more, and compare unrounded totals.
- **N2. Expected operator errors print tracebacks** (cli.py:110-133; review N3, verify V5).
  - Cases: `NamesNotSynced`, `RulesFileChanged`, `AlpacaKeysMissing` or `AlpacaError` from `sync-names` and `ai-pick`, a wrong `--keys` path, and `fetch-model` network errors.
  - **Fix:** catch them in `_extract_command`, print one line and return 1, as PRs 1-3 do.
- **N3. The SDKs read `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`, `OPENAI_CUSTOM_HEADERS` and `ANTHROPIC_CUSTOM_HEADERS` from the environment** and send them as headers, including to api.x.ai (ai.py:240-246, 305-311). Nothing sets them today.
  - **Fix:** pass `organization` and `project` explicitly, or document these variables as forbidden.
- **N4. Anthropic prompt caching never applies** (ai.py:319-330; review N5, verify Q2).
  - `system` is a plain string with no `cache_control` marker, and `Price.cost` has no cache-write rate.
  - The prompt is about 1k tokens, near the 1,024-token minimum, so B2 should check whether caching happens at all.
- **N5. An alias word inside a longer model name beats the ticker the model gave** (ai.py:519-521). "Apple Hospitality REIT"/APLE maps to AAPL, and "Meta Materials"/MMAT maps to META.
  - **Fix:** prefer the model's ticker when it maps to a different instrument, or mark the mention as a conflict.
- **N6. The score worker polls `engine.signals` every second with no index on `stage`** (review N7). That's a full scan of about 36.6k rows, 86,400 times a day, on serverless Postgres.
  - **Fix:** a partial index `ON engine.signals (key) WHERE stage NOT IN ('done','error')` in 0004, or a longer tick.
- **N7. Dead code** (review N8, simplify S5): `records.has_extraction` (records.py:108), `NameBook.names_of`, `ModelSpec.provider`, `CountsAll.asked`, `Replayed.delivered` and `tests/replay.replay_embedder`.
  - The replay never uses the real model when its files are present, which the brief asks for. Wire it in with B1 or drop it.
- **N8. Rules rows record `started_at == finished_at`** (score.py:134, batch.py:72-73). Take `finished` after `pick()`.
- **N9. A model's free-text name becomes the new instrument's permanent `name`** (score.py:48), and the web role reads `engine.instruments`. An example is "US steel makers (Nucor)". Use Alpaca's asset name instead.
- **N10. The replay's `deliver` hook runs inside the stage transaction, before commit** (score.py:150-151, tests/replay.py:114). PRs 6 and 8 will fill it, so call it after the commit.
- **N11. Window boundaries are UTC midnights** (scripts/samples.py:33-35, scripts/precision.py:196; review N12, verify V10). The rest uses New York dates. No current sample post is affected, but B2's `--window-start` would split 4-5 h early.
- **N12. `similar()` doesn't cap `k` at 50, and `min_score` defaults to 0.0** (similarity.py:236-238). The brief's signature has no default and returns "up to 50".
- **N13. `ai-pick --run 2` doesn't require a run-1 answer, and unknown `--keys` are skipped silently** (batch.py:197-207). Nothing computes the stability share yet; B2 will need it.
- **N14. The CHANGELOG and README say "pinned" for things still null at df77049** (CHANGELOG.md:36 and :38, engine/README.md:197-198; verify V9).
  - Add "(filled in Part B)" there, or let B1 and B2 make it true.
  - Update the PR body as B1 lands.
- **N15. `fetch_model` uses CNN's download timeout and sends no User-Agent** (simplify S11). Use `make_client`.

## Simplifications (optional; tried, and the suite stays green with each)

The combined patch is `pr-261-round-1-probes/simplify/simplify.patch`. Details are in `simplify-findings.md`.

- **C1. Each AI-scored post loads the name book twice, and `ai-pick` reads each quoted post twice** (score.py:97-98 and :132, batch.py:241 and :261). Pass the caller's book and text to `record_ai`. This saves 2 queries and a book build per post. Do S5 first, since the book must not be shared while it can still gain undated holds.
- **C2. The picker and its config travel side by side, and two places decide whether the AI is ready.** Have `AiPicker.from_settings` raise `NotReady` with the reason. About 9 lines.
- **C3. `AiPicker.pick` builds placeholder answers for providers with no client, then filters them out** (ai.py:749-755 and :763). If you take S3's "refuse without three clients", this goes away.
- **C4. Two copies of the hash-checked file loader** (rules.py:196-219, ai.py:154-172). One helper; the AI picker hash is unchanged.
- **C5. The "sorted counted tickers" expression appears three times.** Add a `NameBook.symbols()` method.
- **C6. `extract` and `embed` insert one post at a time.** Batching takes `extract` over 6,000 posts from 7.9 s to 2.8 s and `embed` from 4.1 s to 1.2 s locally, with identical results. The gain against Neon will be larger.
- **C7. The open-engine / try / dispose block is repeated 8 times.** Add a small `database()` context manager in db.py.
- **C8. `run_ai_pick` is 71 lines, and the rules step appears three times.** A `record_rules` helper and `_pick_each` bring it to about 38.
- **C9. scripts/samples.py:48 rewrites the text-posts filter.** Import `TEXT_POSTS` from batch.py instead.

## Questions

- **Q1. Did any rules-versus-labels comparison run before 997fe4c?** The data files and labels are provably frozen since f442395 (20:01). But rules.py, which holds the bare-ticker regex, the hyphen rule and the veto semantics, first appears 33 minutes later, and rules-precision.md is stamped 20:38.
- **Q2. How will B2 iterate on the prompt?** `ai.json`'s `version` doesn't change when the pinned hashes do, and `select_posts` keys idempotence on the version only. A second prompt round on the dev set prints "0 posts" unless the version is bumped, and bumping it each round means the frozen picker isn't "version 1". Two options:
  - key `_lacks` on `(version, picker_hash)`;
  - keep a committed hash-to-version history that the loader enforces.
- **Q3. What happens to the live backlog and live spend?** Posts wait at `score` until B1. When the model lands, and PR 7 sets `ENGINE_AI_LIVE`, the whole backlog is AI-picked at once, with no live spend cap. Is that for PR 7, for example to skip AI for old posts or apply a daily cap?
- **Q4. Is a cumulative cap wanted against PR 4's $15?** `--max-usd` caps one run only. Repeated runs aren't checked against `spent()`. Two concurrent runs both pay, and `ON CONFLICT DO NOTHING` drops the second run's records, so `spent()` misses that spend.

## Dropped

- **Tests build real SDK client objects** (verify Q3): only with fake keys and mock transports, which meets the intent of the brief's rule.
- **SDKs falling back to `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`:** an explicit `api_key=` blocks both. This was checked in the openai 2.54 and anthropic 1.11 source.
- **OpenAI and xAI 401 bodies:** they show only masked fragments of the key.
- **Anthropic temperature sent via `extra_body`:** disclosed, and B2 verifies it.
- **The score worker failing at start before B1 (ModelMissing):** as the brief says, and the PR body discloses it.
