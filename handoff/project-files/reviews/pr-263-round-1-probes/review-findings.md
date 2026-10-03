# PR #263 (Engine PR 5, Part A): review, round 1

Reviewed: the PR's own change, `git diff 178bbab b267c39` (28 files, +4,825/-77), in a
detached checkout at b267c39 (`$SP/review-263-r1-wt`). The brief was
`/mnt/project-files/build-briefs/engine-pr5.md`, and the frozen rules were
`engine/reports/gate0-v1.md`. Part B (the real run) is not done, by design.

**Verdict: request changes.** The code follows gate0-v1.md closely. I checked every
definition against the code and found one place where it doesn't: a match's maturity
ignores its benchmark's exit (B1). Five reproducibility and robustness defects (F1-F6)
would bite Part B. Three of the frozen spec's own definitions have look-ahead or
statistical problems that the planner has to rule on before Part B is run (Q1-Q3). Q1
matters most: on a realistic posting pattern, the p-value rejects a true null about 4x
as often as it should, and the PR's no-effect test can't see it because its synthetic
posts all fall in market hours.

Baseline: from `engine/` at b267c39, `ruff check`, `ruff format --check` and `mypy engine
tests` pass, and so does the full suite (`503 passed in 270.91s`).

Probes: `$SP/review-263-r1/review/test_probe_*.py`. Each one passes while the bug it
names is real. They use synthetic prices and posts only, on the PR's throwaway databases
and fake Alpaca. Run them with `$SP/review-263-r1/runprobe.sh $SP/review-263-r1-wt/engine
-q <probe file>`, which strips every secret variable. All 15 probe tests pass at b267c39.
`SP=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad`.

---

## Blockers

### B1. The match pool takes a match before its benchmark's exit is known (look-ahead)

- **Where:**
  - `engine/engine/backtest/evaluate.py:182-186`: `MoveBook.judged` returns `moves.matured[window]`, the instrument's own exit.
  - `evaluate.py:284-287`: `Matcher.matches` pools on that.
  - `engine/engine/backtest/moves.py:317-336`: `adjusted()` builds the net move from the benchmark's move but never combines the two maturities.
- **Problem:**
  - A company's judged move, and ETH's, is `move - beta x benchmark move`. The benchmark makes its own entry and exit "by the same rules" (gate0-v1.md, Moves). The benchmark's entry can be later than the instrument's: a coin may enter up to 5 minutes after the alert, and a stock enters at the first bar it has.
  - When that happens, the benchmark's exit is later too, so the judged move is only known at the later of the two exits.
  - The pool admits the match at the instrument's own exit. A post whose alert falls between the two exits gets a match whose value contains benchmark prices from after that post's alert.
- **Scenario:**
  - BTC has no bars from t0+2 to t0+5 (allowed: BTC enters at t0+6, within 5 minutes). ETH enters at t0+2.
  - The match post at t0 matures for ETH 1h at t0+62, but its net move uses BTC's price at t0+66.
  - A similar post at t0+61 (alert t0+63) gets this match. Scaling BTC prices only from t0+64 onwards changes the match's judged move by about 5% (beta 1).
  - For the gate's company pairs, the same applies whenever SPY lacks a regular-session minute bar at the company's entry minute. That is rare on the SIP, so the practical reach is mostly the ETH secondary view. Still, it is look-ahead in the pool, and the brief treats any as disqualifying.
- **Evidence:** `test_probe_lookahead.py::test_probe_a_match_whose_benchmark_exit_is_after_the_alert_is_in_the_pool` passes. It asserts:
  - the ETH exit is at t0+62, at or before the alert;
  - the BTC exit is at t0+66, after the alert;
  - the match is in the pool;
  - the match's judged move changes by more than 0.01 when only post-alert BTC prices change.

  No PR test covers a benchmark whose entry is later than the instrument's.
- **Fix:**
  - In `adjusted()`, also return the per-window maturity `np.maximum(moves.matured[w], benchmark.matured[w])` (NONE if either is NONE). `MoveBook._post` and `judged()` then use it for net instruments.
  - Store the same value in `signal_moves.matured_*` for net instruments, since PR 6 pools from it.
  - Add a test with a lagging benchmark entry.

---

## Should-fix

### F1. `--rebuild`'s hash depends on posts after the sample

- **Where:**
  - `engine/engine/backtest/run.py:114`: `every_text_post = await all_text_post_times(conn)`.
  - `engine/engine/backtest/data.py:108-110`: every text post in `engine.signals`, with no date bound.
  - `engine/engine/backtest/report.py:179-180`: `bursts.all_text_posts` goes into the JSON.
- **Problem:** The JSON carries a count and shares computed over every text post in the database, not the sample's. Any post imported or ingested after the run changes the JSON. `backtest --rebuild` then reports "differs", exits 1, and can never match again. The brief's acceptance check ("`--rebuild` ... gets the same JSON hash") holds only while nothing new arrives. The report's burst numbers also aren't "as of data_to".
- **Scenario:** Run `backtest` for D. A later history import or the live feed adds one post dated after D. `backtest --rebuild` now fails with `rebuild: JSON SHA-256 differs from run 1`.
- **Evidence:** `test_probe_rebuild.py::test_probe_rebuild_hash_breaks_when_a_post_arrives_after_the_sample` passes. It inserts one post 40 days after `DATA_TO`, after which:
  - the rebuild returns 1 with "differs";
  - `bursts.all_text_posts.posts` is +1;
  - the rest of the JSON is identical.
- **Fix:** Bound `all_text_post_times` to `posted_at < span.end` (and from `DATA_START`, or from PR 2's import start if "all" must mean all history up to D). The report should then label it as "all text posts to D".

### F2. build-moves treats "has baselines for D" as "done", so it can't repair a stale or lost cache window or a changed sample, and the backtest gets stuck

- **Where:**
  - `engine/engine/backtest/build.py:239-247` (`built_instruments`) and `build.py:325-326` (`todo` excludes done instruments, so they are neither backfilled nor re-cached).
  - `engine/engine/market/bars.py:424-427`: `_read` deletes any unreadable file, even in the read-only `alpaca=None` mode.
  - `run.py:104-113` (CacheMiss leads to "run build-moves").
- **Problem:** Done-ness is "random_baselines has rows for this instrument and data_to". Nothing checks that the minute cache the backtest will read is still present and fresh, or that the sample the baselines came from is still the sample. Three ways to get stuck:
  1. **Rebase.** A later `backfill-bars`, or `build-moves --to D+1` (which backfills every instrument and rebases any with a new dividend or split), sets `rebased_at`. Every cache window fetched earlier is now stale. `backtest --to D` and `backtest --rebuild` raise CacheMiss and print "run `python -m engine build-moves --to D`". That command skips every done instrument, fetches nothing, and the loop never ends.
  2. **Lost or corrupt cache file.** The same loop. `_read` itself deletes a corrupt file, including during a no-call rebuild.
  3. **Changed sample.** A post joins the sample after build-moves (a vector embedded later, or `has_words` changing, as b267c39 itself did). It gets no `signal_moves` rows, the baselines stay those of the old sample, and build-moves for D does nothing. The backtest still runs, judging the new post against the old baselines.
- **Evidence:**
  - `test_probe_rebuild.py::test_probe_a_stale_cache_window_can_never_be_rebuilt` passes:
    - after `rebased_at` is set for AAPL, build-moves exits 0 with zero calls;
    - the rebuild and `backtest --to` both fail with "... is stale ... build-moves --to 2022-03-31";
    - with one AAPL `.npz` deleted, build-moves again fetches nothing and the file stays missing.
  - `test_probe_rebuild.py::test_probe_a_changed_sample_reuses_old_baselines_and_moves` passes: the new in-sample post has no `signal_moves` rows after a rebuild, and the backtest runs with `text_posts` +1.
- **Fix:**
  - Make done-ness explicit and checkable. Record per (data_to, instrument) the sample's fingerprint (a hash of the post keys) and the instrument's `rebased_at` when built.
  - Treat a mismatch, or a cache window that `MinuteCache` reports missing or stale, as not done.
  - Or let `build-moves --to D` always run the cheap cache pass (`load_prices` with the client) for done instruments, rebuilding only when something changed.
  - In `_read`, don't unlink when the cache has no client. Raise CacheMiss and leave the file.

### F3. A daily-bar failure is swallowed: build-moves exits 0 and the instrument is built without closes, permanently

- **Where:** `engine/engine/backtest/build.py:293-297` (the `except` says "daily bars failed" and carries on without counting it) and `build.py:314` (`return 1 if failed else 0` only counts `_build_all` failures).
- **Problem:** If `backfill_daily` fails for an instrument (an Alpaca error after the retries, or a DB error), its close, 1/3/5-day windows and its beta are all missing. A company then has no judged move at all. The instrument is still built, written and marked done, the command exits 0, and later healthy runs skip it (F2). The gate's company pair silently loses that company. If the instrument is SPY, every company's beta disappears.
- **Evidence:** `test_probe_build_failures.py::test_probe_failed_daily_bars_exit_0_and_are_never_built_again` passes. The fake Alpaca answers 422 for AAPL's daily bars, then:
  - `code == 0`;
  - AAPL has `signal_moves` rows but zero `move_close` and zero `adjusted_1h`;
  - a second, healthy run makes no calls and leaves the same zeros.
- **Fix:** Count a daily failure as a failure of that instrument and of each instrument that uses it as a benchmark. Don't build those instruments in this run, and exit 1.

### F4. Test gaps: boundary and rule mutations survive, and the no-effect test doesn't cover the real posting pattern

- **Where:** `engine/tests/test_backtest_*.py`, `engine/tests/backtest_helpers.py:207-231`.
- **Problem:**
  - Thirteen of 40 mutations survive the PR's backtest tests (see the mutation table). Among them:
    - the exact boundaries of "at least 30 minutes" (M02), "past the close" (M03), 30 days (M15), the coin's 5 minutes (M16) and 365 days (M13);
    - Benjamini-Hochberg's monotone step (M12);
    - the head-to-head tie rule (M14), which gate0-v1.md states explicitly;
    - the hit rate "before costs" (M18).
  - The planted and no-effect worlds put every post at 10:30 or 14:10 on a session. A post while the market is shut, which is where Q1's inflation comes from, never appears in a statistical test.
- **Evidence:** the mutation table below (`$SP/review-263-r1/mutation_log.txt`, runner `review/mutate.py`), and `test_probe_shared_windows.py` for the posting pattern.
- **Fix:**
  - Add boundary cases: entry exactly 30 minutes before the close; a 1h window ending exactly at the close; a coin bar exactly 300 s late; days = 30 vs 29; a day exactly 365 days back.
  - Add a BH case where monotonicity bites (e.g. `[0.01, 0.011, 0.5]` gives q `[0.0165, 0.0165, 0.5]`) and a head-to-head with equal totals.
  - Add a planted case with a small effect where "before costs" and "after costs" hit rates differ.
  - Add a no-effect world with nights and weekends (and whatever Q1 decides).

### F5. `--rebuild` overwrites the recorded report before it compares

- **Where:** `engine/engine/backtest/run.py:226-244` (`backtest()` calls `report.write(built, out_dir)` at `run.py:154`, and the comparison comes after). The default `--out` is `engine/reports` (`cli.py:216`).
- **Problem:** A rebuild that differs has already replaced the committed `backtest-v1.json` and `.md` with content that matches no recorded run. The check that should protect the report damages it.
- **Evidence:** `test_probe_rebuild.py::test_probe_rebuild_hash_breaks_when_a_post_arrives_after_the_sample` (second half). A rebuild into the original directory exits 1, and the file's SHA-256 no longer equals the recorded `report_sha256`.
- **Fix:** In `--rebuild`, build and hash in memory (or into a temporary directory), and write to `--out` only if the hash matches. Or always write somewhere other than the committed path.

### F6. The run records `code_commit = "unknown"` outside Railway

- **Where:** `engine/engine/backtest/run.py:166` (`code_commit=settings.code_version`) and `engine/engine/settings.py:26-29` (default `"unknown"` unless `ENGINE_CODE_VERSION` or `RAILWAY_GIT_COMMIT_SHA` is set).
- **Problem:** The brief asks `backtest_runs` for "the code commit". Neither variable is set in this sandbox (checked with `[ -n "${VAR+x}" ]`), so Part B's run would record `unknown`. The report that decides Gate 0 couldn't be tied to the code that made it. The PR's tests pass because the fixture sets `code_version="test"`.
- **Fix:** When `code_version` is `unknown`, use `git rev-parse HEAD` (and refuse a dirty tree, or record `-dirty`), or refuse to record the run. Also put the commit in the JSON's `inputs`.

---

## Nits

- **N1. Building an earlier `--to` erases matured moves.** `signal_moves` has no `data_to` (`engine/engine/tables.py` `signal_moves`; upsert at `build.py:212-228`). After `build-moves --to D2`, a run with `--to D1 < D2` overwrites known windows with NULL ("not yet"), while D2's baselines stay. PR 6 reads a table that has gone backwards.
  - *Evidence:* `test_probe_rebuild.py::test_probe_building_an_earlier_date_erases_matured_moves` passes: SPY's known `move_5d` count drops.
  - *Fix:* add `data_to` (or `built_to`) to `signal_moves` and never overwrite a later build with an earlier one.
- **N2. One counted company with no bars blocks every backtest.** `build_instrument` writes no baseline rows when every random move is NaN (`randomtimes.py:268-269`). The company is therefore never "done", and `run.py:97-102` refuses the whole run. build-moves exits 0 and repeats the same thing forever.
  - *Evidence:* `test_probe_build_failures.py::test_probe_an_instrument_without_bars_blocks_every_backtest` passes.
  - *Fix:* write a zero-count marker row (or an explicit done record) per instrument. Let the backtest proceed and count such calls as `no_baseline` / `no_entry`.
- **N3. A missing market slug is a bare KeyError.** `used_instruments` skips a market slug that isn't in the table (`data.py:205`), but `Universe.candidates` indexes it (`evaluate.py:422,424`). A database without XLE (if `add_sector_funds` was refused) crashes on the first energy post.
  - *Evidence:* `test_probe_slugs.py` passes (KeyError 'xle').
  - *Fix:* check every `MARKET_SLUGS` entry up front in `run.backtest` and raise CannotRun.
- **N4. The live-sample formula's constants differ from the frozen file.** `gate.py:41-45` uses 1.644854 and 0.841621; gate0-v1.md writes `n = ((1.6449 x 0.5 + 0.8416 x sqrt(h(1 - h))) / (h - 0.5))^2, rounded up`. The two disagree by one day for many realistic hit rates: 36/58 gives 105 by the file and 104 by the code, and 16/30 gives 1,390 vs 1,389 (12,325 of the k/n fractions with n from 30 to 1,499).
  - *Fix:* use the file's constants as written. If the precise z-values were meant, that's a planner question for v2.
- **N5. The head-to-head AI total isn't limited to the shared posts.** `evaluate.py:600` sums the AI's gate results over all its posts, while the rules' total uses the `shared` view. gate0-v1.md says both totals are "taken from those posts only". This only differs if an AI-answered post lacks a rules answer (a rules row with `error`, skipped at `data.py:165`).
  - *Fix:* run an `("ai", View("shared", MAIN, posts=shared))` view and use it for the AI's total too.
- **N6. Uncaught errors in the CLI.** `cli.py:213-220` doesn't catch `report.NotPublishable` or `load_match_rule`'s ValueError, so they print tracebacks instead of the one-line errors other commands give.
- **N7. `record_run` re-hashes the inputs at record time.** `run.py:166-171` hashes them again instead of using the `report.Inputs` the run read. An input edited during a long run gives a `backtest_runs` row that disagrees with its own report.
- **N8. Performance and memory.**
  - `MoveBook.random_judged` (`evaluate.py:195-209`) computes every window and the benchmark for the same random times once per window. 1h, close and 1d each redo it.
  - `_moves_and_adjusted` (`build.py:98-107`) recomputes SPY's moves at the same random times for every company.
  - `run.py:106-109` holds every used instrument's full minute series in memory at once (several GB with many companies). build-moves frees each one.
  - `run.py:97` rebuilds `{k[0] for k in table}` once per used instrument.
  - `_counted_companies` (`data.py:182-196`) reads all of `signal_mentions`.
- **N9. The README overclaims.** "Neither file holds a price or another site's link (`report.check_publishable`)": `check_publishable` checks links only. The no-price guarantee is structural (only moves reach `pair_numbers`), and the price check is a test.
- **N10. `has_words` counts keycap emoji as words.** "1️⃣" or "🇺🇸 2️⃣ 0️⃣ 2️⃣ 4️⃣" has words because the keycap base is an ASCII digit (`engine/engine/text.py:14-22`). Also, the filter lives only in the backtest loader. PR 6's live matcher (`load_similarity`) must apply it too, or live matches will differ from what Gate 0 measured.
- **N11. Orphan cache files.** The last month's window is named by its end minute (`data.py:216-225`), so every new `--to` leaves one partial-month `.npz` per instrument that nothing reads again. Small, but unbounded.

---

## Questions for the engine planner (gate0-v1.md is frozen; these are its definitions)

### Q1. The p-value treats New York days as independent when many share one market window (anti-conservative)

- **Definitions:**
  - gate0-v1.md, Statistics: "Calls on the same New York date are averaged into one value, so each day counts once".
  - The p-value: "every call's move is replaced by one of its own post's random-time ... moves".
- **Code:** `evaluate.py:504-526` and `stats.py:142-170` implement this exactly.
- **Problem:**
  - Everything posted from Friday's close to Monday's open enters at Monday's open and has the same close and 1-day window. So do a Monday-evening post and a Tuesday-morning post.
  - That is 2 to 4 New York dates carrying one market move. Their calls come from almost the same match set, so they point the same way.
  - The null draws each call's random time independently, so it has none of that dependence. Its spread is too narrow and the p-values are too small.
  - Trump posts heavily at night and at weekends, and "at least 30 calls on different days" is easier to reach for the same reason.
- **Evidence:** `test_probe_shared_windows.py`, no effect planted anywhere:
  - **Pure statistics, modelled as the gate draws.** 52 weekends, calls on 13 of them, 4 dates each. Each call's random times are random weekends' Monday moves from the same sample. p < 0.05 in **14.2%** of 400 trials; nominal is 5%.
  - **The pipeline end to end (SPY at the close, filters off so the statistic is isolated, 120 seeds).**
    - Posts on Friday night, Saturday, Sunday and Monday before the open: p < 0.05 in **20%** of seeds.
    - The same number of posts on four separate sessions: **2%**.
  - I also tried overlapping 1-day windows (Monday to Thursday at 10:30). The effect there was weak (6% vs 3%) and I didn't keep it as evidence.
- **Ask:** Decide before Part B. Options:
  - (a) Gate 0 v2 where a "day" is the market window's day: the entry session for stocks and ETFs, the entry's UTC day for coins.
  - (b) Keep New York days, but in the null give every call that shares an entry (or a window) the same random draw, i.e. a cluster resample.

  Either way, the PR should add a no-effect test with night and weekend posting (F4).

### Q2. "Matured by the alert time" vs "exactly as it would be live": the free SIP is 15 minutes behind

- **Definitions:** gate0-v1.md, Matches: "every earlier text post whose window for this pair had matured by this post's alert time ... exactly as it would be live". PR 3's `SIP_DELAY` is 16 minutes, and the free plan can't read SIP data younger than 15 minutes (`tests/fixtures/alpaca_error.json`).
- **Code:** `evaluate.py:284-286` admits a stock match the moment its window ends.
- **Problem:** At a 16:05 alert, an earlier post's 16:00 close is in the pool, but live it isn't readable until 16:16. The same applies to any 5m, 15m or 1h window ending in the 16 minutes before an alert, and to the coin feed only if it lags.
- **Evidence:** `test_probe_lookahead.py::test_probe_the_pool_takes_stock_windows_the_live_feed_cannot_see_yet` passes: the match's close matures at 16:00, it is in the pool for the 16:05 alert, and 16:00 is after 16:05 − 16 min.
- **Ask:** Should the pool require `matured <= alert − SIP_DELAY` for stock and ETF windows, and does PR 6's refresh cadence of `signal_moves` change this further? As written, the backtest sees match outcomes live can't.

### Q3. Rule 4's baseline is built from random times across the whole sample, so a post's send decision reads prices from after it

- **Definitions:** gate0-v1.md, Random times: "a date drawn evenly from the dates in the sample". Baselines: "the median judged move over every post's random times in that weekday and hour", used by rule 4.
- **Code:** `build.py:182-209`, `data.py:302-333`.
- **Problem:** A July 2023 post's "better than random" test compares its matches' median with a median that includes moves from 2024 to 2026. That is look-ahead in a filter that decides which calls are tested. Live, the stored table is built through yesterday, so live doesn't have it.
- **Evidence:** `test_probe_lookahead.py::test_probe_rule_4s_baseline_reads_prices_after_the_post` passes:
  - only SPY prices from 2023-10-01 on are changed (+1% at 11:00 each session);
  - the 2023-07-03 post's bucket baseline moves by more than 10 bp;
  - matches whose median beats the old baseline by 25 bp are sent with the real past and dropped with the changed future.
- **Ask:** Either accept it, since the medians are large-sample and close to time-invariant (say so in the report), or v2 builds each post's baseline only from random times before its alert (an expanding table, which is what live sees). The p-value's random-time null can stay full-sample: it's a reference distribution, not a decision.

### Q4. "The 30 days" for BTC without divergent days

`run.divergent_days` takes BTC's 16 dates and ETH's 14 together (20 distinct days) and drops BTC calls on any of them. gate0-v1.md's "the 30 days where Alpaca's and Yahoo's daily closes differed" counts 16 + 14. Should a BTC view drop ETH's dates? This only affects a private, sandbox-only view.

---

## Mutation table

Each mutation was applied alone to a scratch checkout (`$SP/review-263-r1-mut`). The PR's
backtest tests (`test_backtest_gate.py`, `test_backtest_moves.py`, `test_backtest_stats.py`,
`test_backtest_run.py`, `test_bars.py`) were run with `-x`. "Caught" means at least one
failed.

MUTATION_TABLE

---

## Checked and dropped

CHECKED_DROPPED
