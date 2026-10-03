# Engine PR 5: backtest v1 and the Gate 0 report

You are building PR 5 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists, as draft PRs stacked in order:
- **#258, PR 1:** foundation.
- **#259, PR 2:** feeds, `engine.signals` and the history import, about 21,600 text posts since February 2022.
- **#260, PR 3:** the Alpaca adapter, instruments, aliases, the calendar and daily bars.
- **#261, PR 4** (branch `claude/engine-pr4-9xmif8`), in `engine/engine/extract/`:
  - the rules picker (`rules.json`, `topics.json`, `aliases.json`);
  - the AI picker (`ai_picker.json`: gpt-4.1 and Haiku 4.5, both must agree; test window from 2025-11-01);
  - the similarity model and every post's vector;
  - match rule v1 (`match_rule.json`: score 0.85 or more, at most 50 matches);
  - the `extractions` and `signal_mentions` tables.

Read them first and build on them.

PR 5 answers the project's main question: do Trump's posts carry a tradable edge? It runs the backtest for both pickers, writes the frozen report, and Chris reads it against Gate 0. PR 6 onward is built for whatever passes. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on. **Never** change the Gate 0 rules to suit a result.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use DEV_DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. Build AI clients only with keys passed explicitly from settings.
- **Paid AI calls.** Only with ENGINE_OPENAI_KEY and ENGINE_ANTHROPIC_KEY, each under Chris's $75 monthly cap. ENGINE_XAI_KEY stays unused. This PR's AI run is projected at about $15. Stop and tell the engine planner before total spend would pass $30.
- **Alpaca.** Market data only (`data.alpaca.markets`). Stay under about 150 calls a minute. The keys never appear in logs, fixtures, the PR or chat.
- **Prices stay private.**
  - Raw prices and entry prices live only in the `prices` schema or in the bars cache outside the repo.
  - `engine` tables, the report and the PR carry % moves and counts only.
  - Committed fixtures use stand-in prices, as PR 3's do.
- **Frozen inputs.** Rules v1, AI picker v1 and match rule v1 are frozen by PR 4. If you find a bug in one, stop and tell the engine planner; never tune them against results.
- **Other services.** Never call Truth Social's API or ScrapeCreators. No Telegram, email or SMS. No crons. No Railway calls.
- **Scope.** Design from first principles and build nothing before something uses it. Test-only code stays thin and is marked test-only. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **shitpost_dev** should hold the imported posts, the seeds' daily bars, rules v1 over all history and every vector. If it doesn't, rebuild them with PRs 2–4's commands first.
- **Keys and hosts.** Alpaca, OpenAI and Anthropic keys and hosts are set up. Check that the variables exist without printing them.
- **Disk.** Space is limited. Cache only the bars the windows need (see section 3), and report the cache's size.
- **Outputs for review** go in `/mnt/project-files/engine/pr5/`.

## Two parts
- **Part A** needs nothing beyond PR 4's code. It covers:
  - the Gate 0 file;
  - windows, entries and moves;
  - random times;
  - statistics;
  - the send-rule filters;
  - the tables;
  - the report writer;
  - the planted-effect tests on synthetic prices.

  Start it now on PR 4's branch.
- **Part B** is the real run. It needs PR 4 finished, with rules v1, AI picker v1 and match rule v1 frozen and every vector stored. If PR 4 isn't there yet, finish Part A, open the draft PR with Part B listed as not done, and stop. A later session on the same branch does Part B.

## Scope
**1. The Gate 0 file comes first.**
- **What it is.** Commit `engine/reports/gate0-v1.md` before any real-data run, in its own commit, so the history shows it came first. Take the rules from the plan as written:
  - **The 11 pairs per picker** (22 tests):
    - any text post with a market link → SPY at 1 hour, the close and 1 trading day;
    - the same → QQQ at the same three windows;
    - the same → BTC at 1 hour, 4 hours and 24 hours;
    - a post that names a company → that company's stock at the close and 1 trading day.
  - **The pass rule.** A pair passes when all five hold:
    1. at least 30 calls on different days;
    2. entry 2 minutes after the post;
    3. the average move in the called direction after 20 bp of round-trip costs is above zero. That is the raw move for SPY, QQQ and BTC, and the move net of beta × SPY for a company;
    4. it beats random times: p under 0.10 after Benjamini-Hochberg across all 22 tests;
    5. the average is still above zero over the last 12 months alone, from at least 10 calls.

    Gate 0 passes if any pair passes.
  - **Send rule v1 filters** that the gate applies: rules 1 (market link), 3 (enough matches), 4 (better than random) and 6 (no burst).
  - **The head-to-head rule.**
    - On the posts both pickers were tested on, the AI picker picks only if at least one of its pairs passes and its total net move across its passing pairs beats the rules' total across theirs.
    - Otherwise the rules pick, and a tie goes to the rules.
  - **Every definition below:** windows, entries, moves, random times, statistics and day-counting.
- **Never edit it after the run.** If a definition turns out unworkable, stop and ask the engine planner.

**2. Windows, entries and moves.** The alert time is the post time plus 2 minutes; the mirrors-only view (section 6) uses 20 minutes.
- **Stocks and ETFs.**
  - **Entry:** the open of the first regular-session minute bar at or after the alert time. If the market is shut, it's the next regular open.
  - **Windows:**
    - 5 minutes, 15 minutes and 1 hour: the bar at entry plus N minutes. A window that would run past the session's regular close is skipped and counted.
    - **The close:** the first regular-session close at least 30 minutes after entry.
    - **1, 3 and 5 trading days:** the regular close N sessions after the close's session.
  - **Pre-market entry, a secondary view:** when the alert time falls between 04:00 and 09:30 New York time, entry is at the first extended-hours bar at or after it.
- **Coins.**
  - **Entry:** the open of the first minute bar at or after the alert time.
  - **Windows:** 5 and 15 minutes, 1, 4 and 24 hours, and 3 and 7 days.
  - **Exit:** the last bar at or before entry plus the window, within 5 minutes.
  - **Missing bars:** a call with no bar within 5 minutes of entry or exit is skipped, and the skips are counted per pair.
- **Moves.**
  - **% move** is exit over entry, minus 1.
  - **For a company:** the move minus beta × SPY's move over the same window, with beta from the prior 120 trading days of daily returns.
  - **For ETH:** the same, against BTC.
  - **Costs:** report every result after 5 bp and after 20 bp. The gate uses 20.
- **One adjustment basis.** Use `adjustment=all` and respect PR 3's `rebased_at` handling. Use current symbols only: old tickers are only for "traded that day".
- **Partial bars.** Never use a daily bar for the current, unfinished session.

**3. Bars for the run.**
- **Which bars.** Minute bars from Alpaca for SPY, QQQ, BTC, ETH and every instrument the pickers named in history, from 2022-02-01 or each one's first bar.
- **Where.** Keep them in PR 3's minute cache under `ENGINE_BARS_CACHE_DIR`, stored compactly: only the fields the windows use.
- **Size.**
  - Regular hours are enough for companies.
  - Keep extended hours for SPY and QQQ, for the pre-market view.
  - Report the cache's size and the number of calls.
- **Reruns.** A rerun makes no Alpaca calls.

**4. Similar-post calls.**
- **Matching.** For each post, use PR 4's `similar()` with match rule v1. The pool is every earlier text post whose window had already closed by this post's alert time, as live.
- **Matches' moves.** A match's move is the move of **this post's** instrument and window at the match's time.
  - SPY's move for SPY pairs.
  - For a company pair, that company's move net of SPY, even if the match didn't name the company.
- **The call.** The direction most matches moved. A tie means no call.
- **Send-rule filters,** per pair: the gate tests only the posts these would send.
  - **Market link:** by the picker under test.
  - **Enough matches:** at least 10 matches on different days.
  - **Better than random:** at least 60% of matches moved one way, and their median move beat the random-time median by more than 20 bp in that direction. The random-time median is the pair's baseline: the median move of that instrument and window over all random times in the post's New York weekday and hour, from `random_baselines` (section 7). Live alerts use the same stored table, so history and live use one method.
  - **No burst:** at most one call per instrument per 30 minutes. A later call in the window is dropped from the gate and counted.

  Also report the burst rule against PR 2's burst numbers.

**5. Random times and statistics.**
- **Random times.**
  - **Draw:** 100 per post with a fixed seed. Each is a random minute in the same New York weekday and hour, on a random date in the sample period. Don't exclude other posts' times.
  - **Same rules:** each random time goes through the same entry, window and move rules, including "shut means next open".
- **Day-counting.** Calls on the same New York date are averaged into one value, so each day counts once. Every mean, count and test uses days.
- **Per pair and picker, report:**
  - calls and days;
  - the mean net move;
  - the hit rate with its Wilson interval;
  - the p-value;
  - the BH-adjusted q;
  - the last-12-months mean and its count;
  - pass or fail on each of the five conditions.
- **The p-value.**
  - **Each of 10,000 draws:** replace each call's move with one of its own post's random-time moves, in the call's direction, then compute the day-averaged mean the same way.
  - **p** = (1 + draws at or above the observed mean) / 10,001.
  - **BH** runs across all 22 tests at q < 0.10.
- **The planted-effect test** (Part A, synthetic prices):
  - plant a known move after a known set of posts and recover it, with that pair passing;
  - a no-effect version passes nothing in at least 95% of seeds you try (say 20).

**6. Both pickers and the head-to-head.**
- **Rules.** Over every text post since 2022-02-01, using PR 4's stored extractions.
- **AI picker, one run.**
  - **Posts:** every text post from 2025-11-01 to the newest post, with PR 4's frozen `ai-pick` and its stored-answer rule. Posts it already answered aren't asked again.
  - **API:** use the standard API with the 15 s cap, so misses match live. No batch API.
  - **Spend:** print the projected cost first, and run with `--max-usd 30`.
  - **Answers:** every raw answer is stored.
- **Head-to-head.** On the posts both pickers covered, apply the rule exactly as the Gate 0 file states. The rules' results on those posts are reported apart from their full-history results. The winner's figure is labelled flattering, since it is the better of two.
- **Secondary results.** These can't pass the gate:
  - ETH;
  - the 5- and 15-minute windows;
  - pre-market entry;
  - all market-link posts, not just those the send rule picks;
  - each AI model alone;
  - sector ETFs, only if the topics map cleanly to one (energy to XLE, say); otherwise skip them and say so.
- **Two more views.**
  - **Mirrors-only delay:** every pair with entry at post + 20 minutes. It isn't judged now.
  - **BTC without divergent days:** the BTC pairs with the 30 days removed where Alpaca and Yahoo differed by more than 0.5%. The list is in PR 3's cross-check output; recompute it with `engine/scripts/crosscheck_yfinance.py` if needed. Its numbers stay in the sandbox and are never published.

**7. Tables (a new migration; add-then-remove only).** All in `engine`, holding % moves and counts only.
- **`backtest_runs`:**
  - the code commit;
  - the hashes of the Gate 0 file, rules v1, AI picker v1 and match rule v1;
  - the data range;
  - the report hash;
  - created at.
- **`backtest_summary`:** one row per run, pair, picker and view, with the section 5 numbers.
- **`signal_moves`:** one row per text post and instrument, with:
  - the % move and the benchmark-adjusted move for each window as columns;
  - the entry rule (main, pre-market, mirrors);
  - when each window matured;
  - the adjustment basis.

  It covers every text post for SPY, QQQ, BTC and ETH, and for every instrument the pickers named. Live evidence in PR 6 reads it, so report its row count and size.
- **`random_baselines`:** per instrument, window, New York weekday and hour, the median random-time move and its count. It is built from section 5's draws, stored with the run, and used by the "better than random" filter here and in PR 6.
- **`python -m engine build-moves`** fills `signal_moves` and `random_baselines` deterministically and resumably. PR 7 reruns it on Railway to fill production, because nothing travels from the sandbox to production.

**8. The report.**
- **Files.** `engine/reports/backtest-v1.json` (numbers only) and `engine/reports/backtest-v1.md` (method and results in plain words). The dashboard serves them as they are.
- **Contents:**
  - the Gate 0 result per pair and picker;
  - the head-to-head and which picker picks;
  - how many posts a year the send rule would have sent;
  - the live sample size the paid gate needs: calls on different days to confirm each passing pair's backtest hit rate against 50% (one-sided, 5% error, 80% power);
  - the secondary results and both views;
  - the coin skips;
  - the data range;
  - the frozen inputs' hashes.
- **Plain words.** Size every claim to the result: "no edge found" is a valid report.
- **No prices.** A test fails if either file holds a price, an entry price or a link other than our own.
- **Rebuild.** `python -m engine backtest --rebuild` regenerates both files from saved data (bars cache, stored extractions, stored AI answers, fixed seeds) with no API calls, and gets the same JSON hash.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Windows:**
  - entry at the next open for a post while the market is shut;
  - the close at least 30 minutes after entry, including a half day;
  - a skipped 1-hour window near the close;
  - coin windows across midnight UTC;
  - a coin skip without a bar.
- **Moves:** beta net of SPY, and ETH against BTC.
- **The match pool:** it excludes posts whose window hadn't closed by the alert time.
- **Send-rule filters:** each of the four on a hand-made case.
- **Random times:** same weekday and hour, deterministic for a seed.
- **Statistics:**
  - day-averaging;
  - the p-value on a case with a known answer;
  - BH on a known list;
  - Wilson intervals.
- **The planted-effect and no-effect tests.**
- **The report:** the no-price test, and `--rebuild` reproducing the JSON hash.
- **The tables:** idempotent writes, and the web role can read them.

Part B, by hand:
- the AI run's spend;
- the bars calls and cache size;
- the `signal_moves` size;
- the rebuild check;
- the report.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 4's branch `claude/engine-pr4-9xmif8` while PR 4 is unmerged, or from main once it has merged. Commit and push. The Gate 0 file's commit comes before any commit with real results.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 5: backtest v1 and the Gate 0 report", saying near the top that it goes in after #258, #259, #260 and #261. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the Gate 0 table for both pickers;
   - the head-to-head;
   - any part not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Report to the engine planner** when the run is done:
   - the Gate 0 table;
   - the head-to-head result;
   - sends a year;
   - the paid-gate sample size;
   - anything surprising.

   The planner checks the report and brings it to Chris for Gate 0.
5. **Stop.** No merge and no further PRs.
