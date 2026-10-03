# Notifications N9: weekly posts and the running record

You are building N9, the last PR of the notification layer in chrisrogers37/shitpost-alpha. From the public launch, every landing place gets two weekly posts:
- the Monday scorecard;
- a weekly finding from the backtest report.

N9 also adds the running hit rate to the daily results. Every number comes from the engine's one record query or the frozen report, so the posts match the site.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read "The messages" first. Where this brief and the plan differ, this brief wins. One change since the plan: the daily results' running hit rate moved here from N7, so it reads the shared record query.

Questions go by send_message:
- notification design: to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8);
- the record query or the report: to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ).

If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If N7 or engine PR 9 isn't up yet, stop and say so.
- **N1:** the per-place delivery path, `app.deliveries` with item keys, `render(entry, place)`, switches, pacing and `notify_operator`.
- **N7:** result replies, corrections, and the daily results job (17:00 New York, `ENGINE_DAILY_RESULTS_TO`).
- **N8 and N5,** if merged: the bot-chats and X places, with their templates and X's cost cap. A place without a template for an item kind skips that item without sending. N9 adds the weekly templates for every place that exists, and leaves the rest to that rule.
- **Engine PR 1's scheduler:** daily jobs only, at a New York time, logged in `engine.job_runs`, with a missed run caught up once.
- **Engine PR 5:** the frozen report, a JSON file of numbers and method in `engine/reports/`.
- **Engine PR 9:** `engine.record`, the live record by pair, sent and FYI apart, against the backtest. The record page, the daily results, the scorecard and the weekly finding all share it.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys and no sends.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No Telegram or X token here. No sends: tests use the fake Telegram and fake X. No crons and no Railway calls.
- **Public output.**
  - Percentage moves only.
  - "Not investment advice." on every post.
  - Backtest numbers are labelled backtest, live ones live, and the two are never pooled.
  - No referral or affiliate links. The sponsor link is the only link, and on X only the scorecard carries it.
- **No free writing.** The weekly finding is picked by a fixed rule and filled into a fixed template. No model writes or chooses any text.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **Outputs for review** go in `/mnt/project-files/notifications/n9/`.

## Scope
**1. Weekly jobs.**
- **The scheduler change.** Extend `register_job` with an optional weekday (Monday = 0). The latest slot is then the latest matching weekday at that New York time.
- **Behaviour.** A missed weekly run is caught up once, like a daily one, never once per missed week. Daily jobs are unchanged.
- **Tests:** catch-up after a two-day outage across the slot, a DST change, and a copy without the lease running nothing.

**2. Settings:**
- `ENGINE_WEEKLY_POSTS` (`off` or `on`, default `off`), which Chris turns on at the launch;
- `ENGINE_SPONSOR_URL` (default https://shitpostalpha.com/sponsor, the dashboard's sponsor page).

**3. The Monday scorecard** (Monday 08:00 New York):
- **What it lists:**
  - the calls graded in the past 7 days, with hit or miss and the move against SPY (or against BTC for a coin);
  - the running hit rate from `engine.record`;
  - the best and the worst call of the week.
- **Under 20 graded calls** in the running record, it shows the count without a rate: "14 calls, too few for a rate".
- **The sponsor line:** "Built by Claudfather · Want to sponsor this?" with `ENGINE_SPONSOR_URL`.
- **Format.** On Telegram it splits over 3,500 characters. On X it's one post within 280 weighted characters, with the URL counted as X counts it, priced as a linked post under N5's cap.
- **Skipped** when nothing was graded that week.

**4. The weekly finding** (Thursday 12:00 New York):
- **The number.** One number from the frozen report, with its sample size, labelled backtest.
- **Candidates.** The report's per-pair results for the picker in use (instrument, window, sample, share in the called direction, median move against random times).
- **The rule.** Take the candidate with the largest sample not posted in the last 8 weeks, ties broken by a fixed order. Read the history from `app.deliveries` item keys.
- **The text.** A fixed template, for example:
  ```
  From our backtest: after 212 posts like these, SPY moved in the called direction within 1 hour 58% of the time (median -0.3% vs 0.0% at random times). Backtest, not a promise.
  ```
  Then the sponsor line and "Not investment advice."
- **The link.** On X the sponsor line carries no link.
- **If every candidate was posted in the last 8 weeks,** start again from the largest.

**5. Daily results.** Add the running hit rate line from `engine.record` to N7's daily results, with the same under-20 form.

**6. Delivery.**
- Each run is one item per place in `app.deliveries`, so a rerun of the same slot never posts twice.
- Both jobs post only while `ENGINE_WEEKLY_POSTS` is `on`.
- A failed or missed run notifies through the scheduler, and the message names the job.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests on a throwaway database:
- **Golden renders** from a fixture record and a copy of the saved report: the scorecard with and without a rate, a long scorecard split on Telegram, the X scorecard within 280 with its link, and the weekly finding on Telegram and on X.
- **Matching numbers.** The scorecard's numbers equal `engine.record` for the same week. The finding's numbers equal the report's.
- **The finding rule.** It picks the largest unposted candidate, skips ones posted in the last 8 weeks, and starts again when all were.
- **Sponsor link.** It appears only where allowed: both posts on Telegram, only the scorecard on X.
- **Weekly scheduling.** Catch-up once, and nothing while `ENGINE_WEEKLY_POSTS` is off.
- **Daily results** now carry the running rate, with the under-20 form.
- **Reruns.** A rerun of a slot posts nothing twice.

**Samples.** Write every golden render to `/mnt/project-files/notifications/n9/samples.md`.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from the newest unmerged notification PR (N5, else N8, else N7), merging in engine PR 9's branch if it is unmerged. Use main once all have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N9: weekly posts and the running record". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the samples;
   - the finding rule;
   - the variables Chris sets at the launch: `ENGINE_WEEKLY_POSTS=on`, and `ENGINE_SPONSOR_URL` if it differs from the default.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
