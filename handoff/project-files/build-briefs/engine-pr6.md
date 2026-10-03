# Engine PR 6: alerts and the send rule

You are building PR 6 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists, as draft PRs stacked in order:
- **PRs 1–3:** the foundation, the feeds and signals, and market data.
- **PR 4:** the pickers, the similarity model and the live `score` stage.
- **PR 5:** the backtest, with `signal_moves`, `random_baselines`, `backtest_summary` and the frozen report in `engine/reports/`.

Read them first and build on them.

PR 6 turns each scored post into an alert: the public alert object, its insert-only revisions, the change cursor the outlets follow, the similar-post evidence and the send rule. It sends nothing itself. The notification plan's first PR (N1) plugs delivery workers into it next, and the site and API read it. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What Gate 0 decides, and what it doesn't
This PR is built before Gate 0 is read, so nothing here depends on its result.
- **The send-rule file decides.** Which pairs may send and which picker picks are data in a versioned file, `send_rule.json`.
  - **Version 1 ships with no passing pairs and the rules picker in use.** Every alert is then FYI with reason `no_passing_pair`, which is exactly the plan's research mode.
  - **After Gate 0,** a one-line change to that file, with Chris's OK, switches pairs on. Don't build anything per pair.
- **Coin pairs** go through the same generic code as the rest. Build nothing coin-only: no coin pages and no coin wording. Coin alerts are switched on only if a BTC pair passes.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use DEV_DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. Tests use stub models; no paid calls in this PR.
- **Public numbers only.**
  - An alert carries % moves, counts, times and text only: no price, no entry price, no minute series.
  - The only link it may carry is our own signal page.
  - Raw prices stay in `prices`.
- **No sending.** No Telegram, email, SMS or X from this PR or the sandbox: delivery is N1's, and tests use dry-run delivery.
- **Other services.** Never call Truth Social's API or ScrapeCreators. No crons. No Railway calls.
- **Scope.** Design from first principles and build nothing before something uses it. Test-only code stays thin and is marked test-only. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **No new hosts or keys** are needed.

## Scope
**1. `alert.v1` and `engine.alerts`** (a new migration; add-then-remove only).
- **One alert per scored post,** enforced by a unique constraint. Every text post with a market link (by the picker in use) gets one alert, sent or FYI. A post with no market link gets none.
- **Fields:**
  - a short public id: random, unique, URL-safe, about 8 characters;
  - the signal key;
  - the post time;
  - the alert time;
  - `send_until`, the post time plus 15 minutes;
  - `excerpt`: 200 characters or fewer, with links removed;
  - the topic;
  - the picker that made it;
  - the reason line (or null);
  - `market_open` (stocks: inside the regular session at the alert time; coins: always true);
  - `disposition` (`sent` or `fyi`);
  - `fyi_reason` (`no_passing_pair`, `few_matches`, `not_better_than_random`, `late` or `burst`; null when sent);
  - the instruments: asset class, symbol and slug, and never a venue;
  - one call per pair, each with:
    - the instrument and window;
    - the direction;
    - its evidence (section 3);
    - whether the pair passed Gate 0.
- **Storage.** Keep the current `alert.v1` document on the row as JSON, with the fields that queries filter on as columns.
- **The public-format test.**
  - It is a schema test in CI that holds the allowlist of public fields, each with its unit (`percent`, `count`, `time` or `text`).
  - Any other field fails it, as does any number that looks like a price or any link other than our own signal page.
  - It is the one test the notification and dashboard PRs rely on, so keep it in one obvious place.

**2. Revisions and the change cursor.**
- **`engine.alert_revisions`.**
  - Every change to an alert writes a revision in the same transaction: the alert's creation is revision 1, and later ones are results (PR 7) and corrections.
  - **Insert-only,** enforced by a database trigger that refuses UPDATE and DELETE.
  - **Order.** Each revision takes the next `seq` under a lock held until commit, and reads its time after taking the lock. So `seq` order is commit order and time order.
- **The cursor.**
  - One function returns revisions after a given `seq`, with a limit.
  - Every reply carries the database's stream id from PR 1's `engine_meta`, so a reader notices a different database.
  - Outlets, the API and the site each keep their own bookmark.
- **The wake hook.**
  - After each alert commits, call the delivery workers registered through PR 1's registration point, in-process. Until N1 lands nothing is registered, so tests register a dry-run worker.
  - Workers also poll every 30 s, which covers a missed wake.
  - Operator messages go through `notify_operator`, which N1 makes real.
- **Pausing.**
  - `ENGINE_SENDS_PAUSED` pauses all sends while scoring and grading carry on. Workers read it through one function.
  - Every outlet gets each alert at the same moment: there is no paid-first delay.

**3. Similar-post evidence,** one method for history and live, as PR 5 defines it.
- **Matching.**
  - PR 4's `similar()` with match rule v1, against earlier text posts whose window has closed.
  - Keep the vectors in memory in the engine process, and add each new post's vector as it is scored.
- **Per call:**
  - the matches, counted by day;
  - the share that moved one way;
  - their median move;
  - their median move against the benchmark;
  - the random-time median from `random_baselines`;
  - the method's backtest hit rate for that pair from `backtest_summary`, labelled backtest;
  - up to three example posts, each with its excerpt, time and move;
  - a short line such as "Like 14 past posts: SPY fell after 64% of them within 1h (median -0.4% vs random 0.0%)".
- **Missing moves.** Moves come from `signal_moves`. A company with no stored moves yet (newly named) gets the call as FYI `few_matches`, and its moves are filled in the background (PR 5's `build-moves`, run for that instrument off the live path).

**4. Send rule v1.** A post is sent when all six hold; otherwise it is FYI with the first failing reason.
1. **Market link:** a market link by the picker in use.
2. **A passing pair:** at least one of its pairs is listed as passing in `send_rule.json`.
3. **Enough matches:** at least 10 matches on different days, on that pair.
4. **Better than random:** on that pair, at least 60% of its matches moved one way, and their median beat the random-time median by more than 20 bp in that direction. That is raw for SPY, QQQ and BTC, and net of SPY for a company.
5. **Point of decision:** the alert time is at or before `send_until`. Later is FYI `late`.
6. **No burst:** at most one sent alert per instrument per 30 minutes. A later one is FYI `burst`.

**The challenger.** The picker not in use runs on the same posts, and its calls are stored apart from alerts, in `engine.challenger_calls`, with the same evidence. They are never sent; PR 7 grades them.

**5. The `alert` stage.**
- Register an `alert` stage after `score` on signals. It:
  - builds the alert;
  - decides the disposition;
  - writes the alert and revision 1 in one transaction;
  - fires the wake hook after commit.
- A crash anywhere leaves either no alert or exactly one, never two.

**6. Tighten the reason-line check** (deferred to here from PR 4's round 2 review, finding S3, in /mnt/project-files/reviews/pr-261-round-2.md). The alert stage is the first caller of `reason_line`, so it must be right before anything is shown:
- **A corpus test.** Commit a test file of about 50 direction or advice lines and about 30 neutral lines, so every change to the word list is measured. Start from the review's examples:
  - lines that wrongly pass, such as "Nucor could skyrocket on the tariff news" or "Steel tariffs could squeeze Nucor margins";
  - neutral lines that are wrongly rejected, such as "Harmonized Tariff Schedule", "Social Security benefits", "lower court" and "S&P 500".
- **More direction stems:** skyrocket, plummet, tumble, slide, dip, pop, highs, boon, windfall, "blow to", "win for", upgrade, downgrade, favor, help, hit, squeeze and brighten.
- **Narrow `harm`** to `harm(?:s|ed|ing|ful)?`, so it no longer catches "Harmonized" or "Harmony".
- **Numbers:**
  - compare them with commas removed;
  - allow numbers that appear in the instruments' names;
  - add `dollars?|billion|million|trillion|bn` to the amount pattern;
  - make the check and `prompts/reason.md` agree on amounts.
- **A new prompt version.** Changing the prompt gives it a new version; the reason line decides nothing, so this doesn't touch the frozen pickers.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **One alert per post:** a second insert is refused, and a retried stage doesn't duplicate.
- **Revisions:**
  - the database refuses UPDATE and DELETE;
  - under concurrent writers (say 8 tasks writing 1,000 revisions), `seq` order matches time order and commit order, with no gaps visible to a reader at any moment;
  - the cursor returns the stream id.
- **The public-format test** fails on an extra field, a price-like number and a foreign link, and passes on a real alert.
- **Send rule:** each of the six rules on a hand-made case, including:
  - `late` just after `send_until`;
  - `burst` at 29 and 31 minutes;
  - a version 1 file with no passing pairs making everything FYI `no_passing_pair`.
- **Evidence:**
  - the match pool excludes windows not yet closed;
  - a company without stored moves is FYI `few_matches`.
- **The challenger:** its calls are stored apart and never reach the cursor.
- **Crash:** `kill -9` during the `alert` stage, then restart, leaves exactly one alert and one revision 1.
- **Two copies:** two engine copies against one database produce one alert per post. PR 1's lease does this; test it end to end.
- **Reason line:** the corpus test passes every direction and advice line as rejected and every neutral line as allowed.
- **Speed:** the replay harness (PR 4) runs recorded posts through `score` and `alert` with stub models and dry-run delivery. The engine's own processing is under 5 s at the 95th percentile, not counting the model calls, which are capped at 15 s.

Report the replay timings in the PR body. Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 5's branch once its tables are pushed, or from main once PR 5 has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 6: alerts and the send rule", saying near the top that it goes in after PRs 1–5. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the replay timings;
   - the public field allowlist.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Contract notes.** Send the engine planner the alert.v1 field list and the cursor function's signature, so N1 and the dashboard can build against them.
5. **Stop.** No merge and no further PRs.
