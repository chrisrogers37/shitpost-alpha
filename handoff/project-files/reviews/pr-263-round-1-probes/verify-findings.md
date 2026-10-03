# PR #263 round 1: verify-completion (Part A) at b267c39

Scope: Part A of `/mnt/project-files/build-briefs/engine-pr5.md`, PR 5's own change
`git diff 178bbab b267c39` (28 files, +4,825/-77). Checkout: `$SP/verify-263-r1-wt` (detached
b267c39). Probes and logs: `$SP/review-263-r1/verify/`. Nothing was pushed or written to GitHub,
no production database or real Alpaca/AI host was touched, and the PR is unchanged.

**Verdict.** Part A is done and works. Every item in the brief has code and a test. lint, format,
mypy and all 503 tests pass in three runs: twice on the sandbox Postgres and once as the
`engine` role, like CI. CI's `check` is green on b267c39. By hand on throwaway databases, all of
these work: `build-moves` (idempotent, and it resumes after a kill), `backtest`, `backtest --rebuild`
(same JSON hash across processes and hash seeds, no outbound attempt), the web role's access and
the one-line errors. The real problems are:
- a stuck state when `build-moves` runs within 16 minutes after New York midnight (V1);
- runs outside Railway record the code commit as `unknown` (V2);
- test gaps, chiefly an end-to-end test that makes no calls (V3), a no-price test that misses a
  price leaking into a statistic (V4), and pass-rule condition 5, rule 6 inside the gate, rule 4's
  direction, BH's step-down and the p-value's cost handling all untested (V5).

No Blockers.

---

## 1. Checklist: Part A against the brief

Paths are at b267c39 and relative to the repo root. `bt/` means `engine/engine/backtest/`,
`t/` means `engine/tests/`.

### 1a. The Gate 0 file (brief §1)

| Requirement | Status | Evidence |
| --- | --- | --- |
| `engine/reports/gate0-v1.md` committed alone, before any real-data commit | Done | c81076b touches only that file (230+). No `backtest-v1.json/.md` exists in any commit (`git log --all -- engine/reports/` shows only c81076b). |
| Unchanged since | Done | `git diff c81076b b267c39 -- engine/reports/gate0-v1.md` is empty; `git log --follow` lists only c81076b |
| 11 pairs per picker (SPY, QQQ at 1h/close/1d; BTC 1h/4h/24h; company close/1d) | Done | gate0-v1.md:30-41; `bt/gate.py:64-67` |
| Pass rule's five conditions | Done | gate0-v1.md:169-180; `bt/evaluate.py:380-393` |
| Cond. 3: raw move for SPY/QQQ/BTC, net of beta×SPY for a company | Done | gate0-v1.md:86-98; `bt/evaluate.py:52-56`, `bt/moves.py:317-336` |
| Cond. 4: p < 0.10 after BH across 22 | Done (the file says q < 0.10, same thing) | gate0-v1.md:165-166,176; `bt/evaluate.py:590-595` |
| Cond. 5: last 12 months > 0 from ≥ 10 calls | Done (≥ 10 *days*, per the day-counting rule) | gate0-v1.md:167,177-178; `bt/evaluate.py:384-388,515-518` |
| Send rule filters 1, 3, 4, 6 | Done | gate0-v1.md:113-134 |
| Head-to-head rule, tie to the rules, "flattering" label | Done | gate0-v1.md:182-192; `bt/evaluate.py:600-605`; `bt/report.py:375-376` |
| Every definition (windows, entries, moves, random times, statistics, day-counting) | Done | gate0-v1.md:43-167 |

### 1b. Windows, entries, moves (brief §2)

| Requirement | Status | Evidence (code; test) |
| --- | --- | --- |
| Alert = post + 2 min; mirrors + 20 | Done | `bt/gate.py:15-16`, `bt/moves.py:74-76,191-192`; `t/test_backtest_moves.py:64` |
| Stock entry: open of first regular bar at or after the alert; shut means next open | Done | `bt/moves.py:193-212`; `t/test_backtest_moves.py:56` |
| 5m/15m/1h windows, skipped past the regular close and counted | Done | `bt/moves.py:220-229`; `t/test_backtest_moves.py:93` |
| Close ≥ 30 min after entry, half day | Done | `bt/moves.py:231-243`; `t/test_backtest_moves.py:75` |
| 1/3/5 trading days on official closes | Done | `bt/moves.py:234-237`; same test (1d) |
| Pre-market entry 04:00-09:30 on extended bars (SPY, QQQ) | Done | `bt/moves.py:197-200`, `bt/build.py:83-87`; `t/test_backtest_moves.py:157` |
| Coin entry; windows 5m…7d; exit at the bar or the close within 5 min | Done | `bt/moves.py:131-145,250-282`; `t/test_backtest_moves.py:103,118` |
| Coin skips counted per pair | Done | `bt/evaluate.py:240-250,450-458`; `bt/report.py:153-160`; `t/test_backtest_moves.py:131` |
| % move = exit/entry − 1 | Done | `bt/moves.py:244-245,279-280` |
| Company net of beta × SPY, beta on the prior 120 sessions | Done | `bt/moves.py:293-314`; `t/test_backtest_moves.py:172,185` |
| ETH net of BTC | Done (alignment of the two coins' daily axes is untested, see V5) | `bt/evaluate.py:212-226`; `t/test_backtest_moves.py:214` |
| Costs: every result after 5 and 20 bp; gate uses 20 | Done | `bt/evaluate.py:507-509` |
| `adjustment=all`, `rebased_at`, current symbols | Done | cache by slug/adjustment (`engine/engine/market/bars.py:355-359`); `bt/build.py:136-137` |
| Never a daily bar for an unfinished session | Done | `bt/moves.py:240` (NOT_YET past the cutoff); `bt/build.py:74-80`; `t/test_backtest_moves.py:144` |

### 1c. Bars (brief §3; the real fetch is Part B)

| Requirement | Status | Evidence |
| --- | --- | --- |
| Minute cache under ENGINE_BARS_CACHE_DIR, compact (start/open/close) | Done | `engine/engine/market/bars.py:289-327,430-447` |
| Regular hours for companies, extended for SPY/QQQ | Done | `bt/data.py:228-232` |
| Report cache size and call count | Done | `bt/build.py:302-308`; by hand: "Alpaca calls: 26; minute cache: 18 files, 1.1 MB; signal_moves: 1,032 rows, 0.4 MB" |
| A rerun makes no Alpaca calls | Done (one exception, see V1) | by hand: second build `Alpaca calls: 0`, `FAKE_REQUESTS 0`; `t/test_backtest_run.py:209-213` |

### 1d. Similar-post calls and the send rule (brief §4)

| Requirement | Status | Evidence |
| --- | --- | --- |
| PR 4's `similar()` with match rule v1 (0.85, ≤ 50) | Done | `bt/evaluate.py:268-288`, `bt/run.py:78-79,124` |
| Pool: earlier posts whose window had matured by the alert | Done | `bt/evaluate.py:281-288`; `t/test_backtest_gate.py:37` |
| Match's move = this post's instrument/window at the match's time (company net of SPY) | Done | `bt/evaluate.py:433-436` |
| Call = majority direction; tie = no call | Done | `bt/evaluate.py:302-308`; `t/test_backtest_gate.py:107-109` |
| Rule 1 market link (picker under test) | Done | `bt/evaluate.py:411-425`; `t/test_backtest_gate.py:120` |
| Rule 3 ≥ 10 match days | Done | `bt/evaluate.py:311-312`; `t/test_backtest_gate.py:80` |
| Rule 4: ≥ 60% one way, median beats the stored baseline by > 20 bp | Done (the direction isn't pinned by a test, see V5) | `bt/evaluate.py:313-318`; `t/test_backtest_gate.py:92` |
| Rule 6: ≤ 1 call per instrument per 30 min, drops counted | Done (never exercised inside the gate, see V5) | `bt/evaluate.py:322-334,445-447`; `t/test_backtest_gate.py:112` |
| Burst rule against PR 2's burst numbers | Done | `bt/report.py:163-186,453-467` |

### 1e. Random times and statistics (brief §5)

| Requirement | Status | Evidence |
| --- | --- | --- |
| 100 per post, fixed seed, same NY weekday and hour, random sample date | Done | `bt/randomtimes.py:49-57`; `t/test_backtest_stats.py:60` |
| Same entry/window/move rules for random times | Done | `bt/evaluate.py:195-209` (`judged_at`) |
| Day-counting | Done | `bt/stats.py:17-42`, `bt/evaluate.py:504-506`; `t/test_backtest_stats.py:13` (not exercised through the gate, see V5 M52/M53) |
| Calls, days, mean, Wilson hit rate, p, q, last-12 mean and count, five conditions | Done | `bt/evaluate.py:353-393,483-526`; `bt/report.py:54-82` |
| p = (1 + draws ≥ observed)/10,001 over 10,000 random-move draws | Done | `bt/stats.py:55-83`; `t/test_backtest_stats.py:34` |
| BH across 22 at q < 0.10 | Done | `bt/stats.py:86-99`; `t/test_backtest_stats.py:28` |
| Planted effect recovered and passes | Done | `t/test_backtest_gate.py:137` (by probe: spy:1h, spy:close, spy:1d pass) |
| No effect passes nothing in ≥ 95% of 20 seeds | Done | `t/test_backtest_gate.py:155` (by probe: 0 of 20 seeds pass anything) |

### 1f. Pickers, head-to-head, views (brief §6; the AI run is Part B)

| Requirement | Status | Evidence |
| --- | --- | --- |
| Rules over every text post since 2022-02-01 from stored extractions | Done | `bt/data.py:121-175` |
| AI picks from stored votes in its window, frozen hash | Done | `bt/data.py:157-175` |
| Head-to-head on shared posts; rules' shared results reported apart | Done (AI total not restricted to shared posts, see V6) | `bt/evaluate.py:558-559,582-605` |
| Secondary: ETH, 5/15 min, pre-market, all market-link posts, each AI model, XLE for energy | Done | `bt/evaluate.py:549-577`, `bt/gate.py:68-73` |
| Mirrors-only view | Done | `bt/evaluate.py:564` |
| BTC without divergent days, sandbox only | Done | `bt/run.py:59-63,235-239`; `bt/report.py:24,94`; `bt/run.py:187-188`. By hand, the view is printed and absent from the JSON, the MD and `backtest_summary`. |

### 1g. Tables (brief §7)

| Requirement | Status | Evidence |
| --- | --- | --- |
| New add-only migration | Done | `engine/engine/migrations/versions/0005_backtest.py` (heads: 0005 only; up, down, up OK; `alembic check` clean) |
| `backtest_runs`: commit, 4 hashes, data range, report hash, created at | Done in shape; commit is `unknown` outside Railway (V2) | 0005:81-102; `bt/run.py:157-184` |
| `backtest_summary` per run, pair, picker, view | Done | 0005:103-139; `bt/run.py:187-202` |
| `signal_moves` per post and instrument: move and adjusted per window, entry rule, matured, basis | Done | 0005:23-48; `bt/build.py:118-144` |
| `random_baselines` per instrument, window, weekday, hour: median and count | Done | 0005:49-80; `bt/build.py:147-179` |
| `build-moves` deterministic and resumable | Done | by hand: a run killed after two instruments and then resumed equals a clean build, row for row |
| Web role reads them, nothing in `prices` | Done | `t/test_backtest_run.py:307`; by hand (§4) |

### 1h. The report (brief §8)

| Requirement | Status | Evidence |
| --- | --- | --- |
| `backtest-v1.json` (numbers) and `.md` (plain words) | Done | `bt/report.py:85-232,314-436` |
| Gate 0 per pair and picker; head-to-head; sends a year; live sample size; secondaries and views; coin skips; data range; hashes | Done | `bt/report.py:102-146` |
| No price, no outside link: a failing test | Partly: the test exists but has holes (V3, V4) | `t/test_backtest_run.py:228-235,320,327` |
| `--rebuild` regenerates with no API calls and the same JSON hash | Done | `bt/run.py:205-247`; `t/test_backtest_run.py:237-243`; by hand across processes |

### 1i. "How to check your work"

Every listed test exists: next open while shut (moves:56), close ≥ 30 incl. half day (moves:75),
skipped 1 h (moves:93), coins across midnight UTC (moves:118), coin skip (moves:131), beta net of SPY
(moves:185), ETH vs BTC (moves:214), match pool (gate:37), the four filters (gate:80,92,112,120),
random times (stats:60), day-averaging (stats:13), p-value known answer (stats:34), BH (stats:28),
Wilson (stats:22), planted/no-effect (gate:137,155), no-price (run:228-235,327), rebuild hash
(run:237-243), idempotent writes (run:209-213,272), web role (run:307). ruff, format, mypy,
pytest and CI pass (§3).

### 1j. Delivery

| Item | Status | Evidence |
| --- | --- | --- |
| Draft PR, title, "after #258, #259, #260 and #261" near the top | Done | PR #263: draft, title exact, merge order in the first paragraph |
| Before / After / How / testing / Gate 0 table / head-to-head / not done | Done | PR body. The tables say "Not run yet (Part B)". |
| Part B listed as not done | Done | PR body "Not done" lists the 6 Part B steps |
| CHANGELOG under [Unreleased] | Done | CHANGELOG.md:34-40 |
| Scope: only `engine/` and CHANGELOG; no old-system imports | Done | `git diff --name-only` shows only CHANGELOG.md outside engine/; nothing in `engine/engine/backtest/` imports outside the engine |

---

## 2. History

- `git log 178bbab..b267c39`: c81076b (gate file only, 22:35:30) → d0ed7b8 (migration) → 4f239e4
  (merge PR 4) → ac673ac (cache) → 32db69f (backtest) → 03c6cfd (merge PR 4) → b267c39.
- c81076b changes exactly `engine/reports/gate0-v1.md` (+230). No later commit touches it, and
  `git diff c81076b b267c39 -- engine/reports/gate0-v1.md` is empty.
- No commit adds `backtest-v1.json`/`.md` or any real-data result. The PR body says the only
  real-data step so far is the match reading over stored vectors, which is not a result file.

## 3. Commands (from `engine/`, secrets stripped, `PYTHONPATH=<checkout>/engine`)

| Command | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 108 files already formatted |
| `mypy` (strict) | Success: no issues found in 102 source files |
| `pytest` run 1 (sandbox Postgres) | **503 passed** in 259 s, rc 0 |
| `pytest` run 2 (sandbox Postgres) | **503 passed** in 279 s, rc 0 |
| `pytest` as role `engine` (`DEV_DATABASE_URL=postgresql://engine:<redacted>@localhost:5432/postgres`, like CI) | **503 passed** in 364 s, rc 0 (role used as is, not altered) |
| `alembic heads` | `0005 (head)`; exactly one head |
| upgrade head → downgrade 0004 → upgrade 0005 → downgrade 0004 → upgrade head (throwaway DB) | The four tables appear, vanish, appear, vanish and appear; alembic_version follows. `alembic check`: no new upgrade operations. |
| CI on b267c39 | `check` success (23:37-23:41), GitGuardian success |

## 4. By hand (throwaway databases `verify263_{a..g}_e72ffc`; synthetic posts; the tests' fake Alpaca via `httpx.MockTransport`; no real hosts)

The CLI commands ran with a socket guard (a `sitecustomize` that logs and refuses any
non-loopback `connect`/`getaddrinfo`; it loaded in every process). They also ran with
`HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY` pointed at a trap proxy on 127.0.0.1 that logs and refuses.
Both logs stayed empty for every migrate, build and backtest. The only trap entry came from the
deliberate "Alpaca unreachable" case below.

**Migrate.** `python -m engine migrate` with `ENGINE_WEB_ROLE=verify263_web_e72ffc` (a throwaway
role) ran 0001→0005 and "applied WEB_GRANTS".

**build-moves, idempotent** (DB B, the tests' world).
- Run 1: 6 instruments, "Alpaca calls: 26; minute cache: 18 files, 1.1 MB; signal_moves: 1,032
  rows, 0.4 MB".
- Run 2: "Alpaca calls: 0", fake requests 0. An md5 over every `signal_moves` and
  `random_baselines` row, `built_at` included, is unchanged.

**build-moves, killed and resumed** (DB A).
- SIGKILL after the second instrument's line: SPY and BTC were committed (140 baselines and 172
  moves each), and QQQ's transaction rolled back.
- The rerun built only qqq, eth, aapl and xle, with 18 calls.
- The final contents of both tables equal clean DB B's (md5 equal apart from `built_at`). A
  third run changed nothing.

**backtest / --rebuild / backtest again** (DB A).
- They ran with `PYTHONHASHSEED` 1, 2 and 3, in separate processes. All three JSONs have SHA-256
  `c8fe8248…e69d8` and all three MDs are identical. The rebuild said "matches run 1", rc 0.
- DB B (built cleanly) gives the same JSON hash, so the build is deterministic across kill and
  resume.
- Guard and trap logs are empty.

**A world with calls** (DB C, my probe).
- Vectors are 0.002 from the theme and SPY gets +1% after each linked post's entry.
- `backtest` gives "Gate 0 passes: 1 of 22 pairs (rules spy:1h)": 31 calls/days, mean after 20 bp
  +80.8 bp, q 0.0022.
- `--rebuild` under another hash seed: same JSON hash `0441772a…`, "matches run 1". This
  exercises the matches, filters and p-value draws through the database and the cache, which the
  committed end-to-end test does not (V3).

**No price, no outside link.** Checked on DB A's and DB C's reports:
- No JSON numeric value is ≥ 100 apart from `sends.per_year` = 191.9. The other large digit runs
  are inside SHA-256 hex strings.
- No number in either file equals any of the 149,249 stand-in prices the fake served.
- No key or word "price".
- The only link is `](gate0-v1.md)`.
- `signal_moves`, `random_baselines` and `backtest_summary` hold fractions only: max |value| is
  0.376, 0.324 and 0.220.

**`--divergent-days`.** The private view is printed with the "sandbox only" header. It is absent
from the JSON (same hash), the MD and `backtest_summary` (0 rows).

**Web role** (`SET ROLE verify263_web_e72ffc` on DB A):
- it reads `signal_moves` (1,032 rows), `random_baselines` (840), `backtest_runs` (2) and
  `backtest_summary` (272);
- `prices.market_bars` gives "permission denied for schema prices", and
  `has_schema_privilege('prices','USAGE')` = f;
- an INSERT into `backtest_runs` is denied.

**Bad settings and unreachable databases** (each one line on stderr unless noted; no password,
key or fake key in any output):

| Case | build-moves | backtest | backtest --rebuild |
| --- | --- | --- | --- |
| No ENGINE_DATABASE_URL | rc 2 "invalid engine settings: ENGINE_DATABASE_URL: Field required" | same | same |
| Unreachable DB (127.0.0.1:1, password in URL) | rc 1 "could not reach the engine database: … port 1 failed: Connection refused" | same | same |
| Wrong password | rc 1 "… password authentication failed for user "nobody"" | same | same |
| `ENGINE_ALPACA_CALLS_PER_MINUTE=999` | rc 2, one line | same | same |
| **DB not migrated** | **rc 1, 145-line traceback** (V8) | **rc 1, 157 lines** | **rc 1, 152 lines** |
| No Alpaca keys, bars needed | rc 1 "stock bars need ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY; coin bars don't", no attempt | n/a | n/a |
| Fake keys, Alpaca unreachable (trap) | rc 1 "/v2/stocks/bars: ProxyError: 403 Forbidden"; one CONNECT to the local trap; keys not printed | n/a | n/a |
| `--to` today | rc 1 "--to 2026-10-02 hasn't ended in New York yet; the latest is 2026-10-02" (V9) | n/a | n/a |
| `--to 2021-12-31` | rc 1 "… is before the sample starts (2022-02-01)" | n/a | n/a |
| Missing `--to` / bad date / `--to` with `--rebuild` | rc 2 argparse | rc 2 argparse | rc 2 argparse |
| Empty cache dir | n/a | rc 1 "<path> is missing and this run makes no Alpaca calls: run `…build-moves --to 2022-03-31`" | same |
| Cache dir is a file | n/a | rc 1 "backtest failed: [Errno 20] Not a directory: …" (plus one WARNING "fetching it again", V11) | |
| `--to` with no baselines | n/a | rc 1 "no baselines for aapl, btc, … up to 2022-03-30: run `…`" | |
| `--divergent-days` missing / `--out /proc/x` | n/a | rc 1 "backtest failed: [Errno 2] …" | |
| No run recorded yet | n/a | n/a | rc 1 "no backtest run recorded yet: …" (test) |

**Stuck state after midnight** (DB G, V1):
- `build-moves --to 2022-03-31` with the clock at 2022-04-01 00:05 New York. The stocks fail
  with TooRecent (PR 3's 16-minute SIP rule, rc 1). BTC and ETH are built, but their last cache
  window (`btc/raw/all/20220401T0000-20220401T0359.npz`) is not written: it ended under 16 minutes
  before the fetch.
- Builds at 01:05 and a day later finish the stocks and then make 0 calls.
- `backtest` fails every time: "…/btc/raw/all/20220401T0000-20220401T0359.npz is missing … run
  `python -m engine build-moves --to 2022-03-31`". The advice it gives cannot fix it.

## 5. Docs against code

- engine/README.md's backtest section matches the code, except that it credits
  `report.check_publishable` with "Neither file holds a price". That function only refuses links
  (V10).
- CHANGELOG.md:34-40 matches.
- PR body: matches, with these notes.
  - "SPY at 1 hour, the close and 1 day pass (q about 0.001)": spy:1d's q is 0.0953 by probe
    (V12).
  - "nothing passes in any of 20 seeds" is true (probe: 0/20).
  - "503 engine tests pass" is true.
  - "Neither file holds a stand-in price" is true for that test, but its report has no calls (V3).

## 6. Mutation results

**Method.** 64 mutations, applied one at a time in scratch worktrees
(`$SP/verify-263-r1-mut{,2,3}`; each restored after, all clean now). Each ran
`pytest -x tests/test_backtest_{stats,moves,gate,run}.py` (39 tests). Runner:
`review-263-r1/verify/mutate.py`; raw results in `mut-{a,b,c,d}.txt`.

**Result.** 36 killed, 27 survived and 1 equivalent.

| Property (from the task) | Mutations killed | Survived |
| --- | --- | --- |
| Match pool no look-ahead | M01 drop matured≤alert; M02 +1 h | M59 the 50-match cap applied before the pool filter (Gate: after) |
| Entry 2 min after the post | M03 delay 0; M04 stock delay ignored; M05 floor instead of ceil | none |
| Close ≥ 30 min after entry | M06 minimum 0; M08 never next session | M07 `>=`→`>` (exact-30-minute boundary) |
| Rule 1 market link | M09 | none |
| Rule 3 enough match days | M10 matches not days; M11 9 days | none |
| Rule 4 better than random | M12 drop 60%; M13 50%; M14 `>`→`>=`; M16 no baseline = 0 | **M15** `abs()`: a median beating random in the *other* direction passes |
| Rule 6 no burst | M17 `<`→`<=`; M18 across instruments | **M19** `no_bursts` not called in `Universe.test` |
| Beta net of SPY / ETH vs BTC | M20 beta 1; M21 no netting; M22 beta uses the entry session's own return; M23 2 returns | M24 QQQ/XLE judged net (Gate: raw); M25 ETH and BTC daily axes not aligned |
| BH | M27 wrong rank | **M26** no step-down min; **M28** q = p in the gate; **M62** condition 4 on p |
| p-value | M29 no +1; M30 `>` not `>=` | **M31** call direction ignored; M32 draws not less costs; **M33** observed mean before costs (anti-conservative) |
| Last-12-months condition | none | **M34** 366 days; **M35** 10 years; **M36** full mean; **M37** no 10-day minimum; **M38** condition always true |
| Head-to-head tie rule | M41 rules' full-history total | **M39** a tie goes to the AI; **M40** AI picks with no passing pair |
| No-price test | M42 a daily close in the JSON; M43 a minute open in the JSON; M44 an outside link in the MD; M45 link check disabled | **M63** a minute close in `hit_high`; **M64** a call's entry price in `hit_high` |
| Rebuild determinism | M48 timestamp in the JSON | **M47** `--rebuild` exits 0 on a mismatch; M46 seeds from `hash()` (vary across processes; survived 6/6 fixed hash seeds, one random-seed run failed by chance) |
| Others | M49 minute windows past the close; M50 coin entry 50 min; M54 any weekday; M55 next hour; M56 Wilson 90%; M58 mean before costs; M60 tie makes a call | **M52** no day-averaging in the gate; **M53** days = calls; **M61** condition 1 at 3 days; M57 zero day counts as a hit |
| Equivalent | M51 (daily windows past the cutoff): sessions end on `data_to`, so `exit_at > cutoff` can't hold when `target < len(sessions)`. It's a redundant guard, not a gap. | |

Survivors in **bold** are what V5 asks to cover. The rest are V14 (Nit).

## 7. Findings

### Blocker

None. The code does what Part A and the Gate 0 file say. I found no wrong result, no price or
link in an output, no outbound call and no secret printed.

### Should-fix

**V1. `build-moves` run within 16 minutes after New York midnight leaves the backtest stuck
for good.**
- **Where.** `engine/engine/backtest/build.py:74-80` (`check_data_to` lets a day through from
  00:00), `engine/engine/market/bars.py:378` (a window ending less than 16 minutes before the
  fetch is not cached), and `engine/engine/backtest/build.py:239-247,325-326` (an instrument
  counts as done once its baselines exist).
- **Problem.** A coin's last cache window ends at the sample's end (04:00 UTC). If the fetch is
  under 16 minutes later, the file is never written. The moves and baselines are still built from
  the fresh bars, so the instrument is marked done. From then on:
  - `backtest` and `--rebuild` raise CacheMiss;
  - every later `build-moves` skips the instrument and makes 0 calls;
  - the advice printed ("run `build-moves --to D`") cannot fix it.
  Stocks are safe only because PR 3's TooRecent refuses them. PR 7 plans to run this on Railway,
  where a cron near midnight is plausible.
- **Evidence.** DB G (§4): build at 00:05 NY, then at 01:05 and a day later (0 calls). Every
  `backtest` fails on `btc/raw/all/20220401T0000-20220401T0359.npz is missing`.
- **Fix.** In `check_data_to`, refuse until `day_start(data_to + 1) + SIP_DELAY <= now`. Or count
  an instrument as done only when every cache window it read was written. Either way, make the
  CacheMiss message name a recovery that works.

**V2. `backtest_runs.code_commit` is `unknown` for any run outside Railway.**
- **Where.** `engine/engine/backtest/run.py:166` writes `settings.code_version`, which defaults to
  "unknown" without `ENGINE_CODE_VERSION`/`RAILWAY_GIT_COMMIT_SHA`
  (`engine/engine/settings.py:26-29`).
- **Problem.** Brief §7 asks for "the code commit". Part B runs in the sandbox, and the README
  doesn't say to set `ENGINE_CODE_VERSION`.
- **Evidence.** Both by-hand runs recorded `code_commit = unknown` (§4).
- **Fix.** Fall back to `git rev-parse HEAD` of the checkout when neither variable is set. Or
  refuse to record a run whose commit is unknown. Document the variable for Part B.

**V3. The end-to-end database test never makes a call.**
- **Where.** `engine/tests/test_backtest_run.py:105-127`. Linked posts are the theme plus
  N(0, 0.03) noise in 384 dimensions, so the cosine between two of them is about 0.74, under
  the 0.85 threshold.
- **Problem.**
  - Every gate test in that run has `no_matches: 43` and 0 calls.
  - So the rebuild-hash and no-price assertions (lines 228-243) check an empty report.
  - The path from the database through matches, filters, random-time draws and the p-value to
    the report is never tested end to end.
- **Evidence.** The by-hand DB A uses the same seeding: all 22 gate tests have 0 calls, with
  `counts: {"no_matches": 43}` (§4). My DB C, with 0.002 noise and +1% SPY after each linked
  post, gives spy:1h passing (31 days, q 0.0022) and a matching rebuild hash. So the code works;
  the test doesn't show it.
- **Fix.** Seed the linked posts tight (for example 0.002) and plant a move in the fake's SPY
  minutes. Assert calls > 0 and a pass before checking the hash and the leaks.

**V4. The no-price test misses a price that leaks into a per-test statistic.**
- **Where.**
  - `engine/tests/test_backtest_run.py:228-235` only looks at numbers between 1,000 and 200,000,
    in a report with no calls (V3).
  - `engine/tests/test_backtest_run.py:341-342` compares against every 997th open only.
- **Problem.** Brief §8 says "A test fails if either file holds a price, an entry price …".
- **Evidence.** M63 (a minute close in `hit_high`) and M64 (the call's own entry price in
  `hit_high`) both survive.
- **Fix.** Make the check structural. Every number in the JSON must be either a count or day field
  (an explicit key list) or a fraction or probability with |x| ≤ 1 (allowing `per_year`).
  Alternatively, compare against *all* opens, closes and daily closes of the world, and run the
  check on a report with calls (V3).

**V5. Several of the properties the brief names are not pinned by any test (mutation
survivors, §6).** The code is right in each case; nothing stops a regression.
- (a) **Pass condition 5 (last 12 months)**: M34-M38 all survive. Nothing fails a pair on its
  last-12 mean or its 10-day minimum, and the planted world's whole sample is one year.
  - Code: `engine/engine/backtest/evaluate.py:384-388,515-518`.
  - Test to add: a world over 2+ years where the effect stops in the last year, and one with
    fewer than 10 recent days.
- (b) **BH inside the gate**: M28 (q = p) and M62 (condition 4 on p) survive. Only the
  function is tested. M26 (no step-down `min`) also survives, because the known list
  `[0.01, 0.04, 0.03, 0.005]` never needs the step-down.
  - Code: `evaluate.py:590-595`, `engine/engine/backtest/stats.py:95-98`.
  - Test to add: assert a gate test's q against BH of the 22 p-values, and a list such as
    `[0.04, 0.041]` (q 0.041, 0.041).
- (c) **p-value**: M31 (direction ignored) survives because the "down call" case in
  `engine/tests/test_backtest_stats.py:49` gives 1.0 either way (0.01 and −0.01 less cost are
  both ≥ −0.012). M33 (observed mean before costs, draws after: an anti-conservative p) and M32
  survive because the glue in `evaluate.py:519-526` is untested.
  - Test to add: a down-call case whose answer depends on the sign, and a gate-level case where
    the cost shift moves p.
- (d) **Rule 6 inside the gate**: M19 (`no_bursts` not called) survives. The planted world has
  one post a day, so the gate never sees a burst.
  - Code: `evaluate.py:445-447`.
  - Test to add: two linked posts 10 minutes apart, so the `burst` count is 1.
- (e) **Rule 4's direction**: M15 (`abs`) survives.
  - Code: `evaluate.py:317`.
  - Test to add: a down call whose median sits more than 20 bp *above* the baseline must be
    `not_better_than_random`.
- (f) **Head-to-head**: M39 (a tie goes to the AI) and M40 (AI picks with no passing pair)
  survive.
  - The test's "a tie at best" case (`engine/tests/test_backtest_gate.py:169`) is not a tie: by
    probe the totals are ai 0.954 against rules 1.196.
  - The PR body's "a tie goes to the rules" is therefore untested.
  - Tests to add: an exact tie, and a case where the rules' shared total is negative and the AI
    has no passing pair.
- (g) **Day-counting and condition 1 through the gate**: M52 (no day-averaging), M53 (days =
  calls) and M61 (30 → 3 days) survive.
  - Code: `evaluate.py:504-506`, `engine/engine/backtest/gate.py:29`.
  - Test to add: two calls on one New York date counted once, and a pair with 29 days failing
    condition 1.
- (h) **Match cap after the pool filter**: M59 survives. This is the order PR 4's review (Q2)
  asked for and the Gate file states (gate0-v1.md:103-106).
  - Code: `evaluate.py:287`.
  - Test to add: more than 50 scored posts, most not yet matured.
- (i) **`--rebuild` exits 1 on a mismatch**: M47 survives.
  - Code: `engine/engine/backtest/run.py:240-244`.
  - Test to add: change a stored `report_sha256` and expect rc 1 and "differs from".

**V6. The sample silently drops text posts that have no vector.**
- **Where.** `engine/engine/backtest/data.py:75-94` inner-joins `signal_embeddings`. A text post
  with words but no vector for the pinned model is left out without a word, and the report's
  `text_posts` has no denominator.
- **Problem.** Part B's first step is a re-embed under PR 4's new model version (PR body). A
  partial re-embed would shrink both the sample and the match pool unnoticed. The Gate says a
  text post "has a similarity vector" as a fact, not as a filter (gate0-v1.md:16-18).
- **Fix.** Count the text posts in the span that have words but no vector, and refuse when it
  isn't 0 (or at least report it in `data`).

### Nit

**V7.** The head-to-head AI total isn't restricted to the shared posts:
`engine/engine/backtest/evaluate.py:600` sums the AI's gate results over all its picks. The Gate
says "each pair's calls taken from those posts only" (gate0-v1.md:186-188). The two are the same
only while every AI-voted post has a rules v1 answer. Fix: compute the AI's total on a `shared`
view too, or assert that the AI's picks are a subset of the rules' picks.

**V8.** The paid-gate sample size uses 1.644854/0.841621 (`engine/engine/backtest/gate.py:41-45`).
The frozen formula says 1.6449 and 0.8416 (gate0-v1.md:223). For 17 of 4,800 hit rates in
0.52-1.0, the rounded-up n differs by 1 (h 0.5204 gives 3712 against the file's 3713; 0.5407
gives 931 against 932; 0.5436 gives 811 against 812). Fix: use the file's constants, since the
report is judged "as written".

**V9.** On an unmigrated database, or one not yet at 0005, `build-moves`, `backtest` and
`--rebuild` print a 145-157-line ProgrammingError traceback. `engine/engine/cli.py:124-126,199-220`
catch only OperationalError. `status` already says "not migrated" (cli.py:246), but PR 4's
`extract` and `review-list` share the gap. Fix: catch UndefinedTable and print one line naming
`python -m engine migrate`.

**V10.** `engine/engine/backtest/build.py:78` prints "--to 2026-10-02 hasn't ended in New York
yet; the latest is 2026-10-02". The latest allowed day is the day before. Fix: print `today - 1`.

**V11.** Two small mismatches around the report and cache.
- `engine/README.md:271-272` credits `report.check_publishable` with "Neither file holds a
  price". That function only refuses links (`engine/engine/backtest/report.py:206-213`).
- In a read-only (rebuild) run, `engine/engine/market/bars.py:425-426` still deletes an unreadable
  cache file and logs "fetching it again". The rebuild never fetches.

**V12.** The PR body claims more than shown in two places.
- "SPY at 1 hour, the close and 1 day pass (q about 0.001)": spy:1d's q is 0.0953 (probe).
- "The AI: … a tie goes to the rules" is listed as tested, but no test has a tie (V5f).

**V13.** The report's "What the filters dropped and what was skipped" table
(`engine/engine/backtest/report.py:418,439-450`) includes a `not yet` column. The Gate says a
window maturing after the data is "left out, not counted as a skip" (gate0-v1.md:82-84). Fix:
label it apart, for example "not yet known (left out)".

**V14.** Minor untested edges (§6): the exact-30-minute close (M07), the 365-day edge (M34),
a zero day as a hit (M57), QQQ and XLE judged raw (M24), and the ETH/BTC alignment when their
daily series start on different days (M25, `engine/engine/backtest/evaluate.py:212-226`).
Cross-process seed determinism (M46) is also untested; I verified it by hand (§4: three hash
seeds, one JSON hash).

### Questions (Gate file is frozen; none of these asks to edit it)

**Q1.** gate0-v1.md:4-5 says "Chris approved these rules on 1 October 2026, before anyone saw a
result". The file was written on 2 October (c81076b, 22:35 UTC). It holds definitions the brief
doesn't give, and the PR's "Defaults picked" doesn't list them:
- the 60-return minimum for beta;
- the hit rate counted before costs;
- "no baseline, not sent";
- not-yet windows left out;
- the seed texts;
- a call's day being the post's New York date;
- XLE as the only sector fund.
Were these specific choices approved, or are they builder defaults that should be listed as such
in the PR?

**Q2.** The hit rate is counted before costs (gate0-v1.md:158-159), and it sets the paid gate's
live sample size. A pair can pass with an after-cost mean just above zero while the live gate
confirms a before-cost hit rate. Is that intended?

**Q3.** Rule 4's baseline is the median over random times drawn from the whole sample,
including dates after the post (gate0-v1.md:122-126,138-150). Brief §4 asks for exactly this. It
is a mild look-ahead into a send filter, while the match pool forbids look-ahead. Confirm that's
intended.

**Q4.** `signal_moves` has no `data_to`. Each `build-moves` overwrites rows with its own sample's
NULL "not yet" windows, while `random_baselines` keeps one set per `data_to`
(engine/engine/migrations/versions/0005_backtest.py:31-48). PR 6 can't tell which sample a row
came from. Intended?

---

Cleanup: the throwaway databases `verify263_{a..g}_e72ffc` and the role `verify263_web_e72ffc`
were dropped (0 left). Role `engine` was untouched (still superuser). The trap proxy is
stopped. The worktrees under `$SP` are left clean at b267c39.
