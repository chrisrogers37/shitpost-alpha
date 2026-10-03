# Engine PR 9: record numbers

You are building PR 9 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists:
- **PRs 1–7:** the engine, with alerts, grading and result revisions (PR 7), and the frozen backtest summary (PR 5).
- **PR 8:** the daily hash.

Read them first and build on them.

PR 9 computes the live record: hit rates by pair, for sent and FYI calls, beside the backtest. These numbers are read by:
- the record page (dashboard D2);
- the daily results message (notification N7);
- the Monday scorecard and the weekly finding (notification N9);
- growth's paid-tier gate, test (b).

One query serves all of them, so the numbers can never disagree. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What Gate 0 decides
Which pairs are "passing" comes from `send_rule.json`. The code treats them as data; with no passing pairs, the record still reports every pair's FYI calls.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database; never read or set DATABASE_URL. Use DEV_DATABASE_URL.
- **Public numbers only.** % moves, counts, rates and intervals only: no prices.
- **Never pool backtest and live.** They are always shown side by side and labelled.
- **Other services.** No Telegram, email, SMS or X; tests use dry runs. No Railway calls. No crons.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY.
- **Scope.** Build nothing before something uses it. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. Tests use throwaway databases.

## Scope
**1. `engine.record`.** One module with one query function (and a view if the API needs SQL), returning per pair and window:
- **Live, for sent calls and for FYI calls separately:**
  - graded calls and the days they fall on;
  - the hit rate with its Wilson interval;
  - the mean move after 20 bp, raw for SPY, QQQ and BTC and net of SPY for companies;
  - the date range.
- **The challenger's live numbers,** labelled and kept apart.
- **The backtest figures** for the same pair from `backtest_summary`, labelled backtest and flattering where PR 5 marked them so.
- **The paid gate, test (b).**
  - **Which calls count:** the pooled live record of the passing pairs, counting calls that met the send rule. That is sent calls, plus FYI calls whose only reason was `late` or `burst`.
  - **The target:** the sample size PR 5's report set, with progress towards it.
  - **The check:** whether it holds up against the backtest, with its interval.
- **Filters:**
  - a date range;
  - a pair;
  - an instrument slug, for ticker pages;
  - "since the public launch".

Grades count only once final, and only when `ENGINE_RESULTS_PUBLIC` allows them to be public. Internal callers can ask for everything.

**2. Dry-run messages.** A small CLI (`python -m engine record --day YYYY-MM-DD`, `--week`) prints the numbers each message needs, so the notification plan's N7 and N9 render from the same source. The engine sends nothing itself.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests on stored fixture results show:
- **Hit rates and Wilson intervals** on a known set.
- **Sent and FYI** are kept apart, and so is the challenger.
- **Late and burst FYI calls** count towards test (b); other FYI reasons don't.
- **Day-counting** matches PR 5's definition.
- **The filters,** and the public flag hiding grades.
- **Backtest and live** never sum together.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 8's branch while it's unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 9: record numbers", saying near the top what it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the record function's signature and output fields.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Contract.** Send the engine planner the output fields, for the dashboard and notification planners.
5. **Stop.** No merge and no further PRs.
