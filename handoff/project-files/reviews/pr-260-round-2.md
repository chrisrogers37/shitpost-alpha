# PR #260 "Engine PR 3: market data": review round 2

**Reviewed:**
- 9c356f9, which is the round-1 fold-in f65287b plus two merges of PR 2: e709971 (7d96886) and 9c356f9 (558d50c).
- Part B on top, de6b046. I checked that myself.

**Passes**, each in a fresh agent:
- **review:** the built-in code-review at high effort plus clauDNA review-work. It covered the fold-in and both merges, re-ran the round-1 probes, added new probes, and ran 17 + 25 mutations.
- **verify:** clauDNA verify-completion against the brief and every round-1 id, with 55 revert-the-fix mutations and by-hand runs.

Round 1: [pr-260-round-1.md](pr-260-round-1.md).

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 262/262 at 9c356f9 three times, once as a superuser named `engine` like CI.
  - Alembic has one head (0003), and CI is green on 9c356f9.
  - At de6b046, ruff, format and the 84 market tests pass here, and the builder reports 272 for the whole suite.
- **Round 1:**
  - **B1, the reported path:** fixed.
    - `_clean_keys` strips both Alpaca keys and refuses anything that isn't printable ASCII.
    - `request_error_text(exc, self._client.headers)` blanks the keys even though they're the client's default headers.
    - The real-socket test passes, all 7 B1 revert mutations are caught, and round 1's `run_backfill` probe finds the secret in 0 of 5 lines.
    - The merge narrowed one part of the fix (S1 below).
  - **S1:** fixed.
    - A sweep of 7,725 instants matched an independent oracle with 0 wrong. It covers both DST changes, the half day, holidays, the 2025-01-09 closure, weekends, and New York and UTC midnights at +15:59 and +16:00.
    - The fallback is always the settled session.
  - **S2:** fixed. FB→META→FB→MTA holds, and an end before the start is refused.
  - **S3:** fixed. An unreadable file is refetched and no `.part` file is left. A cancellation can't be swallowed, because the read runs in a thread.
  - **S4:** fixed. Every listed safety property now has a test that fails when it is removed (17/17 caught).
  - **S5:** fixed. The client comes from `engine.http_client.make_client`.
- **Nits and questions:**
  - Fixed or documented: N2-N9, N11, N12 and N14-N17.
  - Declines accepted: N10 (no factory before PR 5), N13's slug race (one writer under the lease, and no CLI path adds instruments), N5's empty-page rule (the 1,000-page cap bounds the loop), N8 (documented) and N17's `ENGINE_ALPACA_*` names.
  - Q1 and Q2 are answered by claims g and h.
  - Part B's finding that coin days are UTC days settles N1 and N2.
- **Merges:**
  - **e709971 is clean.** Only cli.py conflicted: `backfill-bars` now sits inside PR 2's handler, with a lazy import.
  - **9c356f9:** PR 2's files are byte-identical to 558d50c, and one key check and one header scrub are kept. The exception is S1 below.
- **By hand at 9c356f9:**
  - migrate, status and the seeds are fine.
  - A role with PR 1's web grants reads the instruments and aliases, and is denied `prices.market_bars` and inserts.
  - **Fake keys:** a fake secret ending in `\n` is accepted after the strip, and the key never appears in output. A space inside a key exits 2 in 0.55 s without printing the value, but names the wrong variable (N3).
  - **`backfill-bars` with Alpaca unreachable:** it exits 1 with one line per instrument. It now takes about 62 s without keys and 122 s with them, because of N4's retries; that's fine.
  - `crosscheck_yfinance.py --help` makes no network calls.
  - The calendar works across the year boundary, and with the clock patched to 2027.
- **Part B (de6b046), which I checked myself:**
  - Both merges are clean.
  - The diff has no key material, and the fixtures keep no request headers.
  - Stand-in bar numbers keep raw prices out of the public repo.
  - The PR body and README publish only counts and percentages.
  - All eight claims are recorded and tested.

**Result: changes needed.** 2 should-fix and 8 nits. Both should-fix triggers depend on answers we haven't seen, but each fix is small.

## How to answer

As before: fix each should-fix or decline it with a reason, and treat nits as optional. Send me the new head and one line per id.

PR 1's round-3 push (99fe7bb) is in its own round 4. Merge it in when you merge PR 2's next head, which will carry it.

**Probes:** [pr-260-round-2-probes/](pr-260-round-2-probes/)
- `test_review_probe_r2.py`: each `test_probe_…` passes at 9c356f9 while its finding stands.
- `test_review_probe_r2_s1.py`: controls that pass and catch the unpinned S1 and N12 mutations.
- `test_verify_probe_r2.py`: two ready-to-commit pins that pass at 9c356f9 and fail under the revert.

Copy them into engine/tests/ to run. Don't commit them as they are, except as tests you adopt.

---

## Should-fix

### S1. The merge narrowed B1's scrub to httpx's own error text; Alpaca's answer text is no longer scrubbed (review, verify)
- **Where:** alpaca.py:251-254. `_fail` raises its text as given.
  - :235 puts `response.text[:300]` into the error.
  - :203 puts `{exc!r}` of an unexpected answer into it.
  - At f65287b, `_fail` cut both keys out of every AlpacaError. The 9c356f9 merge replaced that with `request_error_text`, which covers only httpx exceptions (:249).
- **Problem:** if a response body quotes a key, the secret reaches AlpacaError and every `backfill-bars` line, while the README and CHANGELOG say errors have the keys cut out. That could be Alpaca echoing a rejected header, or a proxy or captive page in between.
- **Evidence:**
  - `test_probe_a_response_body_echoing_the_key_reaches_alpaca_error_and_the_line`: a 403 whose body quotes `APCA-API-SECRET-KEY` puts the secret in AlpacaError and in 4 of 5 `run_backfill` lines.
  - The same probe at f65287b shows `[key]`.
  - Claim b's real 403 body doesn't quote the key, so the trigger is unconfirmed.
- **Fix:**
  1. Split the replace loop out of `request_error_text` into a public `http_client.scrub(text, *headers)`, and call it from `request_error_text`.
  2. Call `scrub(text, self._client.headers)` in `_fail`.
  3. Turn the probe into a test.

### S2. N12's delete can lose stored history for good when a whole refetch comes back short (review)
- **Where:** bars.py:145-158 and :179-191, which call `_remove_days_not_in` whenever `refetched and bars`.
- **Problems:**
  - **A short answer:** a whole refetch that succeeds but lacks most stored days deletes all of them. The next run looks back only 14 days from the last stored bar, so the lost days never come back.
  - **An empty answer:** it deletes nothing, but it still moves `rebased_at`, which drops every cached minute window, and it reports that everything was fetched again.
- **Scenario:** Alpaca briefly serves a partial history after a corporate action or a symbol remap.
- **Evidence:**
  - `test_probe_a_short_whole_answer_deletes_history_that_never_comes_back`: 2,222 bars dropped to 138, and a later run with the full history served stayed at 138, starting 2024-01-01.
  - `test_probe_an_empty_whole_answer_still_moves_rebased_at`.
  - The trigger is unconfirmed.
- **Fix:**
  1. If the whole answer is empty, or lacks more than a few of the stored days (say more than 5, or more than 1%), fail that instrument with a clear line. Write nothing, delete nothing and don't move `rebased_at`, so the next run retries.
  2. Add tests for the short and empty cases.
  3. `test_control_an_empty_whole_answer_removes_nothing` already pins the empty case's delete.

## Nits (optional, file:line at 9c356f9)

- **N1. Fixes no test pins** (review, verify). Each can be reverted with every test green:
  - **S1's staleness guard** `cached[0] >= settled` (instruments.py:138). It's the one that matters most. Commit `test_probe_a_cached_history_is_refetched_once_its_settled_session_moves_on`, or `test_control_a_long_lived_listings_refetches_once_a_new_session_settles`.
  - **N3's database-error handling** (bars.py:248). Commit `test_probe_a_database_error_on_one_instrument_does_not_stop_the_others`.
  - **N6's yearly calendar rebuild** (calendar.py:20-30). Patch the clock to next year and assert `trading_days_after(date(next_year, 12, 31), 1)` works.
  - **N7's lazy import:** a subprocess test that pandas isn't in `sys.modules` after `import engine.cli`.
  - **N11's `--help`:** it raises `SystemExit(0)` and never builds a client.
  - **N2's coin skip** in the cross-check.
  - **S3's fsync and unlink** (bars.py:313, 326). Recording the `os.fsync` call is optional.
- **N2. A 5xx waits on `X-RateLimit-Reset` when it carries one** (alpaca.py:224-227). The probe saw waits of `[2,2,2,2]` or `[~50]×4` instead of the doubling back-off. **Fix:** use `_backoff` for 5xx and keep the reset header for 429 (`test_probe_a_5xx_waits_for_the_rate_limit_reset_not_the_back_off`).
- **N3. A bad Alpaca key names a variable that doesn't exist** (cli.py:47-50, PR 1's line, reached through PR 3's aliased fields).
  - It prints `ENGINE_ALPACA_API_SECRET_KEY:`. The error is located at the alias, and the CLI prefixes `ENGINE_` to every location. Chris would see this while setting up the keys.
  - **Fix:** `name if name.isupper() else f"ENGINE_{name.upper()}"`.
  - **Test:** a CLI test where a bad `ALPACA_API_SECRET_KEY` exits 2, and stderr names `ALPACA_API_SECRET_KEY` without the prefix or the value.
- **N4. `change_symbol` updates the symbol before `add_alias` refuses the window** (instruments.py:299-305). A same-day typo correction (METAA→META) raises after the symbol has already changed, and there's no way to make the correction (`test_probe_change_symbol_updates_the_symbol_before_refusing_the_day`). **Fix:** check the window before the UPDATE, inside the same transaction.
- **N5. A database error prints several lines of `[SQL: …]` per instrument** (bars.py:248-251). **Fix:** print the first line of the cause, as the CLI does.
- **N6. An unhashable `next_page_token` raises TypeError and stops the whole `run_backfill`** (alpaca.py:204-209; this predates round 1). **Fix:** check it's a string, or fail it as an unexpected answer.
- **N7. `_minute` reads a naive time as the host's local time** (bars.py:292-293). At ef1cba7, `utc_text` refused it. With TZ set to New York, 14:00 becomes 18:00Z. **Fix:** refuse naive times again.
- **N8. Small items:**
  - `parse_collisions` and `load_collisions` (collisions.py:26, :40) still have no docstrings.
  - With Alpaca unreachable, `backfill-bars` now takes about a minute per instrument at 5 tries. That's fine, but worth a README line.

## Dropped

- **Stale since Part B:** verify's notes that the PR body says 252 tests and lists Part B as not done. de6b046's body says 272 and has the claims and results.
- **N1 of round 1 (a coin bar final an hour early):** claim d shows coin days are UTC days, so `start + 24h` is the true end.
- **The calendar crashing at the end of its range:** unreachable after N6's rebuild.
- **`add_alias` reopening a closed alias:** documented behaviour.
- **The cross-check's `model_validate` skipping env keys:** pydantic-settings 2.15 reads them.
