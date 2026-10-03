# PR #260 "Engine PR 3: market data": review round 1

Reviewed: PR 3's own changes, `git diff 872135b ef1cba7` (fd9c8f0 and ef1cba7), plus the merge d77c2df. Line numbers are at ef1cba7.
Passes, each in a fresh agent:
- **simplify:** the built-in simplify lens, report-only, with changes applied on a scratch checkout only;
- **review:** built-in code-review at high effort plus clauDNA review-work, with probes and 10 mutations;
- **verify:** clauDNA verify-completion against engine-pr3.md, with 49 revert-the-fix mutations and by-hand runs.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest gives 208/208, three times, including once as a superuser named `engine` like CI.
  - Alembic has one head (0003), and 0003 downgrades and upgrades cleanly.
  - CI is green on ef1cba7.
- **The merge d77c2df is clean:**
  - `--remerge-diff` is empty.
  - PR 2's feeds, lease, runtime and scheduler are byte-identical to 872135b.
  - What PR 3 imports from PR 2 didn't change.
- **Part B** (the recorded claim calls, the backfill into shitpost_dev and the cross-check run) is listed honestly as not done in the PR body and in the README's claims table. That is allowed by the brief. Its code exists and is tested on the `*.unverified.json` fixtures.
- **The agreed defaults are reasonable:** "what counts" on the latest session with data, the 14-day overlap with a whole refetch, `rebased_at`, the `-2` slugs, and coins stored as `crypto_us`/`raw`. All are tested except the coins' feed and adjustment (S4).
- **By hand:**
  - migrate and status work, and the seeds are right (qqq→spy, eth→btc).
  - A role with PR 1's web grants reads `engine.instruments` and `engine.instrument_aliases` and is denied `prices.market_bars`.
  - `backfill-bars` with no keys and Alpaca unreachable exits 1 in 2 s, with one clear line per instrument and no traceback.
  - The calendar helpers give the right answers for the half day, holidays, both 2024 DST changes, Saturday→Monday and N trading days.
- **Rules:**
  - market-data host only, no trading hosts;
  - fixture keys are fake; nothing in `engine/engine` imports yfinance;
  - no DATABASE_URL, old key names, old code, crons or sends;
  - only CHANGELOG.md is touched outside `engine/`.
- **PR 1's round-2 blocker (a retry loop swallowing a cancellation):** PR 3 adds no loop with that shape. `_get` raises at once on transport errors, and `run_backfill` catches only `AlpacaError`. A probe that cancelled a real request got `CancelledError`. Keep it that way if N3 or N4 widen a handler.

**Result: changes needed.** 1 blocker, 5 should-fix and 17 nits, plus 2 questions for Part B.

## How to answer

Same as PRs 1 and 2:
- Fix each blocker and should-fix, or decline it with a reason. Nits are optional.
- When you push, send the gauntlet thread (session_013E4KMGG5c9USVygEcNJkqa) the new head and one line per id.
- PR 1 (f4194b7) and PR 2 (7d96886) have new heads in their own round 3. Merge them in when they settle; PR 2's head brings `raise_if_cancelling` and `TRANSIENT_ERRORS` from PR 1.

**Probes:** [pr-260-round-1-probes/](pr-260-round-1-probes/)
- `test_probe_*.py` assert the **buggy** behaviour, so they pass at ef1cba7 when the bug is real and should fail once it's fixed. Copy them into engine/tests/ to run; don't commit them as they are.
- `mutate.py` and `mutations.txt` are the review's mutation run.
- `simplify.patch` is the simplify pass's scratch diff (S5 and N14-N16); it keeps all 208 tests green.

---

## Blocker

### B1. An Alpaca key with a stray space or newline is printed in full (review)
- **Where:**
  - alpaca.py:211-212: `raise AlpacaError(f"{path}: {type(exc).__name__}: {exc}")`.
  - bars.py:216-218: `say(f"{instrument.slug}: failed: {exc}")`.
  - settings.py:71-76 and 84-87: the keys are taken as given; only an empty string counts as no key.
- **Problem:** h11 refuses a header value with leading or trailing whitespace or a CR/LF, and its error includes the whole value: `LocalProtocolError("Illegal header value b'<secret>\n'")`. `_get` copies that text into `AlpacaError`, and `run_backfill` prints it once per instrument. Coin calls also send the keys when they are set, so all four seeds print it. This breaks the brief's non-negotiable rule that the keys never appear in logs, and the PR body's claim that they never appear in an error.
- **Scenario:** Chris pastes the secret into Railway or a `.env` with a trailing newline. Every `backfill-bars` run, and any later job, writes the secret to stdout and Railway's logs four times.
- **Evidence:**
  - `test_probe_keys.py::test_probe_a_key_with_stray_whitespace_leaks_into_the_error` (trailing `\n`, space and `\r\n`). Re-run here: `AlpacaError: /v1beta3/crypto/us/bars: LocalProtocolError: Illegal header value b'probe-fake-secret-0123456789\n'`.
  - `test_probe_market.py::test_probe_run_backfill_prints_a_whitespace_key`: 4 of 5 output lines carry the secret.
  - The committed `test_keys_are_sent_but_never_logged` can't see this, because `MockTransport` skips h11.
  - Control: httpcore's DEBUG trace over a real socket logs no header values.
- **Fix:**
  1. In `Settings`, strip both keys, and reject anything that isn't printable ASCII without whitespace, with a message that names the variable but not the value.
  2. In `_get`, scrub both key values out of any error text before raising.
  3. Add a test over a real local socket with a key ending in `\n`: the secret appears in no error, no `say` line and no log record.
- **Same mechanism in PR 2:** `Feed.get` (feeds/base.py:137-138) builds `FeedFailed` the same way, and ScrapeCreators' key goes in `x-api-key`. That text is stored in `engine.feed_status.last_error`, which the web role can read. I'm raising it with PR 2's builder separately. If you change anything shared, such as `make_client` under S5, do it in a way PR 2 can use too.

## Should-fix

### S1. "What counts" caches a "no bar" answer for the session in progress for the rest of the day (review)
- **Where:**
  - instruments.py:115-125 (`Listings._trading_days`) stores `(latest_session_with_data(now), days)`.
  - instruments.py:81-88 treats a session that opened 16 minutes ago as having data.
- **Problem:** the first check of a symbol with no trade yet today caches "doesn't count", and every later check by the same `Listings` reuses it, even after the stock trades. Examples: an IPO opening at midday, a thin or halted name, or any stock early in the session if daily bars ignore pre-market prints. This isn't the agreed design either, which says a live post whose session has no bar yet "is checked against the latest session with data".
- **Evidence:** `test_probe_market.py::test_probe_listings_caches_no_bar_before_the_bar_exists`, re-run here: `early=False late(same Listings)=False late(fresh Listings)=True`.
- **Fix:**
  - Cache only through the last session whose daily bar is final (`is_final_day`).
  - For the session in progress, never cache a miss. Either refetch that one day, or fall back to the previous session when today's bar is absent, which matches the design's wording.
  - Turn the probe into a test.

### S2. `change_symbol` isn't idempotent, and `add_alias` silently drops a corrected date (review)
- **Where:**
  - instruments.py:211: `on_conflict_do_nothing(constraint="instrument_aliases_key")`. The key (alias, instrument, kind, valid_from) leaves out `valid_to`.
  - instruments.py:215-233: `change_symbol` checks nothing.
- **Problems:**
  - (a) Rerunning `change_symbol(meta, "META", on)` adds `meta` as an old ticker of itself.
  - (b) Recording FB→META again with a corrected date is a silent no-op, so `fb` keeps the wrong window.
  - (c) `new_symbol` isn't validated: `"meta inc"` is stored as symbol and Alpaca symbol `META INC`, and a symbol another instrument holds raises a bare IntegrityError.
  - (d) An A→B→A→C history loses the second `a` window, the same way as (b).
- **Evidence:** `test_probe_market.py::test_probe_change_symbol_twice_and_a_corrected_date`. The aliases end up as `[('fb', 2022-05-31), ('meta', 2022-06-08)]`, `fb` on 2022-06-05 resolves to `[]`, and after the bad call the symbol is `META INC`.
- **Fix:**
  - Return early when the symbol is unchanged.
  - Validate `new_symbol` with `STOCK_SYMBOL` (coins don't change), and raise a clear error if another instrument holds it.
  - Set the old-ticker alias's `valid_from` from the previous change.
  - In `add_alias`, update `valid_to` on conflict, or raise when the stored row differs, rather than a silent no-op.

### S3. One unreadable minute-cache file breaks that window for good (review)
- **Where:** bars.py:244-247 (`MinuteCache.bars`), 261-266 (`_read`), 269-274 (`_write`).
- **Problems:**
  - `_read` treats only `FileNotFoundError` as a miss. An empty, truncated or malformed file raises on every later read and is never refetched.
  - `_write` renames without `fsync`, so after a host crash ext4 can keep the rename with a zero-length file. The docstring's "no half file" doesn't hold.
  - A failed write (a full disk) leaves a `*.part` file behind.
- **Evidence:**
  - `test_probe_a_corrupt_cache_file_fails_every_later_read`, re-run here: `['JSONDecodeError', 'JSONDecodeError']` with 0 requests.
  - `test_probe_a_failed_write_leaves_a_part_file`.
  - The fsync part is reasoning only.
- **Fix:**
  - Treat `ValueError`, `KeyError`, `TypeError` or a non-dict as a miss: warn, delete the file and refetch.
  - Call `flush()` and `os.fsync()` before the rename, and unlink the temp file if the dump fails.
  - Add a test that a truncated file is refetched.

### S4. Safety properties the brief names have no test that would catch their removal (review, verify)
Each change below leaves the whole suite green; the review and verify mutation runs both found these.
- **The 16-minute rule:** refusing only data under 6 minutes old passes (alpaca.py:158). The test tries `now-5` and `now-16` only.
- **The limiter under concurrency:** removing the lock (alpaca.py:110) passes. 20 concurrent calls at 1200/min then take 0.05 s instead of 0.95 s. The only pacer test is sequential.
- **No redirects:** `follow_redirects=True` (alpaca.py:135) passes. httpx strips only `Authorization` on a cross-host redirect, so this guard is what keeps the `APCA-API-*` keys on Alpaca's host.
- **The 429 back-off:**
  - removing the sleep (alpaca.py:218) passes;
  - ignoring `X-RateLimit-Reset` (:237-245) passes;
  - removing the 60 s cap passes.
  - `test_a_429_waits_and_retries` only counts requests.
- **The rate setting:**
  - a default of 200, or no 200 cap (settings.py:77), passes;
  - building the client with `Pacer(1e9)` instead of the setting (alpaca.py:129) passes;
  - market_helpers.py:29 always sets 200.
- **The key env names:** renaming `validation_alias="ALPACA_API_KEY_ID"` (settings.py:71-74) passes all 208 tests. A typo there would leave production with no keys, so every stock call would fail.
- **Coins stored as `crypto_us`/`raw`:** changing `feed_of`/`adjustment_of` (bars.py:45-50) to `sip`/`all` passes. This is an agreed default in the PR body.
- **Null trade count and VWAP:** storing a missing `n` as 0 instead of NULL (alpaca.py:77-78) passes. No test has a null `n` or `vw`.

**Fix (tests to add):**
- `now - 15m59s` is refused and `now - 16m` is allowed.
- 20 concurrent `Pacer.wait()` calls take at least 19 gaps.
- A 302 to another host is not followed: one request, and the keys go nowhere else.
- With `asyncio.sleep` patched to record its waits:
  - a 429 without a header waits `[backoff, 2*backoff]`;
  - a reset of now+3 waits about 3 s;
  - a far-future reset waits 60.
- Settings:
  - assert the default is 150 and 201 is rejected;
  - the client's gap follows the setting (0.1 s at 600/min);
  - `Settings.model_validate({..., "ALPACA_API_KEY_ID": "fake-id", "ALPACA_API_SECRET_KEY": "fake-secret"})` gives `SecretStr` keys, and its repr hides both.
- Stored BTC rows are `("crypto_us", "raw")`, and the coin cache path contains `BTC-USD/raw`.
- A bar with `"n": null, "vw": null` stores NULLs.

### S5. The Alpaca client rebuilds PR 2's `make_client`, including the no-redirect guard (simplify)
- **Where:** alpaca.py:131-137 builds its own `httpx.AsyncClient` with the same User-Agent, timeout, `follow_redirects=False` and transport as feeds/base.py:37-47. alpaca.py:210 and :231-235 (`_auth()`) rebuild the key headers on every request.
- **Problem:** "no redirects, so a key never reaches another host" is a security rule, and it now lives in two places that can drift apart.
- **Fix:** build the client with `make_client(settings, transport)` and add the two key headers once with `client.headers.update(...)` when both keys are set, then delete `_auth()`. This is in `simplify.patch`, and all 208 tests stay green with it.
- **Optional:** `make_client`, `USER_AGENT` and `UNEXPECTED` now serve code that isn't a feed, so they could move to a neutral `engine/http.py`. That touches PR 2's file; your call.

## Nits (optional)

- **N1. A coin bar on a 25-hour day may be stored as final an hour early** (bars.py:62-65; crosscheck_yfinance.py:78; review). Unconfirmed: it depends on Alpaca's coin day boundary, which the README lists as unknown.
  - If coin days start at midnight US Central (the 06:00Z fixture suggests so), the fall-back Sunday's partial close is stored.
  - The next run then sees the close "moved", refetches all of BTC and moves `rebased_at`, which drops every cached BTC minute window. Any revision of a coin close does the same.
  - Probe: `test_probe_coin_bar_on_a_25_hour_day_is_stored_early_and_rebases`.
  - Fix: a coin bar is final once the next bar's start has passed, and coins upsert the overlap without the whole-refetch and rebase path.
- **N2. The cross-check may compare coin closes about 6 hours apart** (crosscheck_yfinance.py:66-68; review), if Alpaca's coin day isn't Yahoo's UTC day. Unconfirmed, for the same reason as N1. Fix: settle the boundary in claim d, then compare at matching instants or skip coins with a note.
- **N3. `run_backfill` stops the whole run on a database error** (bars.py:216; review), although its docstring says the others still run. Fix: also catch `SQLAlchemyError`, with PR 1's `raise_if_cancelling()` first.
- **N4. No retry on a 5xx, a timeout or a connection reset** (alpaca.py:211-212, 220-221; review). One 503 fails `Listings.counts`, and so `add_instrument`, outright. Fix: retry these within the same `TRIES`, with the cancellation re-raise.
- **N5. Paging has no page cap** (alpaca.py:191-204; review). A server that keeps sending new tokens with empty pages pages forever (`test_probe_paging_has_no_page_cap`: 3,711 pages, never finishing). Fix: stop with `AlpacaError` after about 1,000 pages, or on an empty page that still carries a token.
- **N6. The calendar's range is fixed at first use and ends a year later** (calendar.py:18-20; review). After that, every helper raises in a long-running process. Separately, the `exchange-calendars>=4.5` floor (pyproject.toml:12) may allow a release without the 2025-01-09 closure (unconfirmed). Fix: build the calendar with `start="2016-01-01"` and an end several years out, and raise the floor to the tested version.
- **N7. Every CLI command now imports pandas and exchange_calendars** (cli.py:18; review). This was measured: `python -m engine run` goes from 69 MB to 124 MB RSS for code the worker doesn't run yet. Simplify called the 0.3 s start-up cost not worth fixing, but the memory is what matters for an always-on worker. Fix: import `run_backfill` inside the `backfill-bars` branch.
- **N8. `add_instrument` keeps the caller's transaction open across Alpaca calls** (instruments.py:153; review), for up to about 5 minutes on repeated 429s, idle in transaction on Neon. Fix: decide `counts` before the transaction, or document that callers must.
- **N9. The minute cache keys its folder by Alpaca symbol, and file names drop sub-seconds** (bars.py:237-238; review). A reused ticker (the PR's own `fb-2` case) shares the old company's folder. Fix: key by `slug`, and floor windows to whole minutes before naming and fetching.
- **N10. Nothing reads `bars_cache_dir`** (settings.py:81; review, verify). `MinuteCache` is only ever built in tests. Fix: add `MinuteCache.from_settings(settings)` with a test that a window lands under it, or say in the PR body and README that PR 5 wires it.
- **N11. The cross-check script has no argument parsing and needs ENGINE_DATABASE_URL** (crosscheck_yfinance.py:92-104; verify, review). `--help` is ignored and `main()` starts; with keys present it would make live Alpaca and Yahoo calls. It also builds `Settings()`, which needs a database URL it never uses. Fix: `argparse.ArgumentParser(description=__doc__).parse_args()`, and either don't require the database URL there or say so in the README's run line.
- **N12. A whole refetch never removes daily rows Alpaca stopped returning** (bars.py:141-144; review). The "never mixes two adjustment bases" claim then holds only for bars Alpaca still serves. Fix: in that transaction, delete this instrument's 1Day rows that aren't in the new set, or log them.
- **N13. Small items** (review, verify):
  - pandas is imported directly in calendar.py but isn't declared in `dependencies`;
  - public functions without docstrings: `utc_text`, `feed_of`/`adjustment_of`, `session_open`/`session_close`, `all_instruments`/`instrument_by_slug`, `parse_collisions`/`load_collisions`, `compare`;
  - a slug race: `_free_slug` reads, then the insert conflicts only on `symbol`.
- **N14. `backfill_daily` opens two read connections and keeps a derivable `whole` flag** (bars.py:131-145; simplify). Fix: read `last`, `start` and the stored closes in one connection before the fetch. It's in `simplify.patch`.
- **N15. The cross-check copies `is_final_day` and the coin symbol mapping** (crosscheck_yfinance.py:26-34, 78, 96; simplify). Fix: use `is_final_day`, `COINS` and `alpaca_symbol()`. It's in `simplify.patch`.
- **N16. The test helper `instrument()` re-derives the engine's symbol rules** (tests/market_helpers.py:99-113; simplify). `.isoformat().replace("+00:00","Z")` is also written out at alpaca.py:84 and market_helpers.py:44 and :56, which is exactly `utc_text`. Fix: type the parameter as `AssetClass`, use `alpaca_symbol()`, and use `utc_text`. It's in `simplify.patch`.
- **N17. Two settings details** (verify):
  - `populate_by_name=True` (settings.py:16) also accepts `ENGINE_ALPACA_KEY_ID`, though the README says the keys take no `ENGINE_` prefix;
  - a timeout reports an empty `ReadTimeout: ` message (alpaca.py:211-212). Use `repr(exc)` or a fixed "timed out" text, scrubbed as in B1.

## Questions for Part B (add them to the claims table)

- **Q1. Does a 1Day request during a session return today's partial bar?** The live "what counts" rule assumes it does. If daily bars appear only after the close, every in-session check says "doesn't count", and S1 would freeze that. Suggested claim g: "a 1Day request ending now−16 min during a session returns today's bar".
- **Q2. Does `FB` return Facebook's 2021 bars under Alpaca's default symbol mapping?** "What counts" for an old ticker and the FB→META test assume so. Under the default `asof` (today) it may return nothing, or another company's bars. Consider passing `asof` set to the post's session, and record one `FB` call in Part B.

## Dropped

- The pacer being wrong under concurrency: it holds a 0.049 s minimum gap with 20 concurrent calls. The finding is only that no test pins it (S4).
- yfinance reaching the engine: it's only in the `crosscheck` extra and imported inside a function.
- The conftest key guard failing under an env alias: `Settings(alpaca_key_id=None)` beats the alias (probed on a toy model).
- Migration 0003 repeating the table definitions: 0001 and 0002 do the same, by design.
- `FakeAlpaca` reusing PR 2's `FakeWeb`, and the repeated fixture lambdas: too small to matter.
