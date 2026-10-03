# Engine PR 7: the shadow week

You are building PR 7 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists, as draft PRs stacked in order:
- **PRs 1–5:** foundation, feeds, market data, pickers and similarity, and the backtest.
- **PR 6:** alerts, revisions, the change cursor and the send rule.
- **N1,** the notification plan's first PR: the delivery workers and the Telegram outlet, plugged into PR 6.

Read them first and build on them.

PR 7 gets the engine ready to run for real on Railway, sending only to Chris's admin chat, for a seven-day shadow week. It adds:
- grading;
- the growing match pool;
- the outside check;
- the daily heartbeat and coverage check;
- the Railway setup;
- the production fill;
- the runbook.

Chris creates the services himself from your setup file: you never touch Railway or a production database. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What Gate 0 decides
Nothing here. Grading covers every call, sent, FYI or challenger, whatever `send_rule.json` holds.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Production stays out of the sandbox.**
  - Never touch a production database, and never read or set DATABASE_URL.
  - No production credential enters this session: not the engine's database address, the ScrapeCreators key, the bot token, Railway's AI keys or the Healthchecks URL.
  - Everything here is tested against the sandbox Postgres in DEV_DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No paid AI calls in this PR.
- **Railway.** No Railway calls at all, including read-only ones. Chris creates and configures the services from `engine/SETUP.md`.
- **Public numbers only.**
  - Grades are % moves, moves against the benchmark, and hit or miss.
  - Entry prices and minute bars go only in `prices`.
- **Other services.**
  - Never call Truth Social's API or ScrapeCreators from the sandbox.
  - No Telegram, email or SMS from the sandbox: tests use dry-run delivery and a stub Healthchecks server.
  - No crons: every schedule lives in the engine's own scheduler.
- **Scope.** Design from first principles and build nothing before something uses it. Test-only code stays thin and is marked test-only. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **Alpaca** keys and host are set up, for grading tests against real bars.
- **CNN and trumpstruth** may be read gently for the coverage check's live test.

## Scope
**1. Grading.** It runs in a separate process from the live path (a worker process the engine starts), so it can never stall scoring or alerts.
- **What gets graded:** every call, sent or FYI, and every challenger call.
- **When:** once each window has closed and the consolidated bars are out. That is 16 minutes after the window's end on Alpaca's free plan, so every grade is final.
- **The rules:** entry and exit exactly as PR 5's Gate 0 file defines them. Never use a daily bar for an unfinished session.
- **Fetching:** live prices come from Alpaca's REST bars as each window closes, not from streams.
- **What's stored:**
  - each call's entry price and time in `prices.alert_entries`;
  - the minute bars it used in `prices`;
  - for alerts, a result revision in `alert_revisions` per call and window, with:
    - the window;
    - the % move;
    - the move against the benchmark;
    - the random-time move from `random_baselines`;
    - hit or miss;
    - the time it matured.

    A later result revision for the same call and window supersedes the earlier one and carries a short reason, because N7 posts a correction reply when a posted result changes;
  - for challenger calls, the same, in their own table.
- **Missed windows.** Grading catches up after a restart or an outage. A window whose bars never arrive is marked ungraded with a reason after a set time, never guessed.
- **Results stay hidden.** `ENGINE_RESULTS_PUBLIC`, off by default, is the flag the API and site read to hide grades until the public launch.

**2. The growing match pool.** As each new text post's windows close, write its moves to `signal_moves` for SPY, QQQ, BTC, ETH and every listed instrument, so it becomes a match for later posts.
- Use multi-symbol bar requests to keep the calls few.
- The backtest's figures stay frozen. The live record is a separate thing (PR 9).

**3. The outside check, the heartbeat and coverage.**
- **Healthchecks.io.** Ping `ENGINE_HEALTHCHECKS_URL` every minute from the live process. Chris's check emails him when pings stop for 5 minutes.
  - Skip the ping while any live delivery place's `app.outlet_cursors.checked_at` (N1's delivery loop's last pass) is more than 2 minutes old.
  - That way a stuck delivery loop alarms too, without relying on the Telegram path that's stuck.
- **The web service's health.** Check `ENGINE_WEB_HEALTH_URL` (`https://shitpostalpha.com/healthz`) every minute. The domain is pointed during the shadow week, behind D1's holding page, and `/healthz` stays live. After three failures in a row, send one operator message, and another on recovery.
- **The daily heartbeat** goes to the admin chat through `notify_operator`, with the day's counts:
  - posts by kind;
  - alerts sent and FYI, with their reasons;
  - grades done;
  - each source's uptime, and how often it was first;
  - errors.
- **The daily coverage check.**
  - Compare yesterday's posts with CNN's full file and trumpstruth's feed.
  - Import anything missed through PR 2's mapping, marked as found by the check, and tell Chris.
  - It starts with the shadow week and keeps running.
- **Live AI failures.** Today, with `ENGINE_AI_LIVE` on, an empty account or a revoked key only logs a warning, while every live vote falls back to the rules. So:
  - count failed `ai:<provider>` rows per provider per hour;
  - send one operator message when a provider fails repeatedly (say 3 or more in an hour), or at once on a fatal error such as a 401 or OpenAI's 429 `insufficient_quota`;
  - send one more message when it recovers;
  - show the counts in the heartbeat.
- **Source timing.** From sightings, a report of each source's median and 95th-percentile delay and how often it was first. `python -m engine source-report` prints it for the shadow-week review.

**4. Railway and production setup.** These are files and commands; Chris does the clicking.
- **`engine/railway.json`.**
  - It builds only the engine.
  - It runs `python -m engine migrate` as the pre-deploy step and `python -m engine run` to start.
  - It restarts on every exit, with a health check if Railway's config supports one.
  - Its watch paths cover `engine/` only, so changes elsewhere in the repo don't redeploy the engine.
  - Railway's config-file setting doesn't follow the service's root directory. So SETUP.md must tell Chris to set the engine service's config-file path to `/engine/railway.json`. D0's builder found this.
- **ONNX Runtime threads.** Add a setting, `ENGINE_ONNX_THREADS`, for the live worker's `intra_op_num_threads`, with thread spinning off. The default sizes to the host, not the container, and spins: in PR 4's review a short post took 8.6 ms on 1 thread against 15.1 ms by default. Default it to 1 or 2, and list it in SETUP.md.
- **The model files.** Fetch them with `fetch-model` at build time, so each deploy is self-contained. If the build can't, use a small Railway volume, and say so in SETUP.md.
- **The production fill,** each idempotent and resumable, run once from the Railway service's shell or as a one-off job:
  1. `import-history`;
  2. rules extraction;
  3. `embed`;
  4. `build-moves`;
  5. `import-report`, which loads `backtest_runs` and `backtest_summary` from `engine/reports/backtest-v1.json`.

  Then a check that the production moves reproduce the report's per-pair figures to within rounding. Nothing is copied from the sandbox.
- **`engine/SETUP.md`** is Chris's one-sitting checklist, with exact names and values:
  - **The engine database.** Neon, separate from the old production database: a new project, or a branch if his plan limits projects. It has two roles:
    - `engine`, which owns the schemas and runs the migrations;
    - `web`, a login with no privileges of its own, which the migrations grant.

    That gives two connection strings: `ENGINE_DATABASE_URL` for the engine role and `WEB_DATABASE_URL` for the web role.
  - **The engine's Railway service,** in the existing project "shitpost-alpha", from this repo with config `engine/railway.json`. Every variable is listed with what it's for:
    - `ENGINE_DATABASE_URL`;
    - `ENGINE_SCRAPECREATORS_KEY`;
    - `ENGINE_OPENAI_KEY` and `ENGINE_ANTHROPIC_KEY`: new keys for Railway only, each in its own capped project or workspace, as in his PR 4 steps, at $10 a month;
    - `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY`;
    - `ENGINE_AI_LIVE=true`;
    - `ENGINE_HEALTHCHECKS_URL`;
    - `ENGINE_WEB_HEALTH_URL=https://shitpostalpha.com/healthz`;
    - `ENGINE_SOURCES_OFF` (empty);
    - `ENGINE_SENDS_PAUSED=false`;
    - `ENGINE_RESULTS_PUBLIC=false`;
    - N1's operator place, for the shadow week's admin-only sends: `ENGINE_OUTLET_OPERATOR_MODE=live`, `ENGINE_TELEGRAM_BOT_TOKEN` and `ENGINE_TELEGRAM_OPERATOR_CHAT_ID`. N1's code has the final names.
  - **The web service:** a pointer to the dashboard plan's own steps, plus `WEB_DATABASE_URL`. `WEB_HOLDING_PAGE` stays on (its default) through the shadow week.
  - **The domain:**
    - add shitpostalpha.com to the web service in Railway;
    - enter the DNS record Railway shows at the registrar;
    - confirm the holding page and `/healthz` answer on https://shitpostalpha.com.
  - **Healthchecks.io:** a free account and one check with a 1-minute period and 5-minute grace that emails him. Its ping URL goes into `ENGINE_HEALTHCHECKS_URL`.
  - **ScrapeCreators:** one $47 pack of 25,000 credits. Its key goes into `ENGINE_SCRAPECREATORS_KEY`.
  - **The order:**
    1. Chris merges PRs 1–6 and N1.
    2. He creates the database and services.
    3. He points the domain (holding page on).
    4. He merges PR 7, which deploys.
    5. He runs the production fill.
    6. The shadow week starts.
- **The ScrapeCreators timing stretch.** During the week, Chris switches the direct API off for about 6 hours: `ENGINE_SOURCES_OFF=direct`, then back to empty. The source report then times the fallback.

**5. `engine/RUNBOOK.md`.** One page:
- restart;
- redeploy an earlier build from Railway's history;
- switch a source off;
- pause sends;
- what each operator message means and what to do;
- how to read `python -m engine status`.

**6. The shadow-week check.** `python -m engine shadow-report --days 7` prints the plan's pass numbers. The week passes when all hold for seven days in a row:
- **no post missed:** every post in the next day's CNN file and trumpstruth feed is in the engine;
- **speed:** post to alert under 4 minutes median and under 10 at the 95th percentile;
- **no unhandled crash,** and no post stuck in a stage for more than 10 minutes;
- **sources:** each switched-on source answers in 95% or more of hours, and every outage is alarmed;
- **alarms:** the outside check and the daily heartbeat both fire on a forced test;
- **grading:** every call is graded on time.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Grading:**
  - each window graded only after it closed plus 16 minutes;
  - a half day;
  - a weekend post entering Monday;
  - a coin window across midnight UTC;
  - catch-up after downtime;
  - ungraded with a reason;
  - result revisions are insert-only and on the cursor, and a correction supersedes with a reason;
  - grades are hidden while `ENGINE_RESULTS_PUBLIC` is off;
  - challenger results are stored apart.
- **The grader is separate:** a stalled or crashed grader doesn't delay the `alert` stage.
- **The match pool:** a new post's moves land in `signal_moves`, and later posts match it.
- **The outside check:** pings against a stub server, and three web-health failures make one message, plus one on recovery.
- **Live AI failures:** repeated or fatal failures of one provider make one operator message, plus one on recovery.
- **ONNX threads:** the setting reaches the session options.
- **The heartbeat:** its counts on a fixture day.
- **The coverage check:** it imports a missed post once, marked, and tells Chris once.
- **The production fill:** each step twice gives the same result, and the report check passes on the sandbox database.
- **`shadow-report`:** it computes each pass number from fixture data.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from N1's branch if N1 is unmerged, or else PR 6's branch, or main once both have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 7: the shadow week", saying near the top that it goes in after PRs 1–6 and N1, and that merging it deploys the engine once Chris has created the service. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - a link to SETUP.md.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **SETUP.md to the engine planner.** Send it when it's final, so Chris gets it as one ask.
5. **Stop.** No merge and no further PRs.
