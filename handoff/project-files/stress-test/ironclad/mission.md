# Mission and constraints for this review

This is the mission source for the align-to-mission lens and the context every lens shares. The repository's own README.md and CLAUDE.md describe the OLD system being replaced; they are not the mission. The mission is the project owner's (Chris's) stated goal below.

## The goal (Chris, project topic, 2026-09-30, verbatim)

"Make shitpost-alpha a signal engine I'd actually trade on. 1) Replace the paid Truth Social API with our own free scraper that keeps up in near real time. 2) Move from posts to a general "signals" model, with Trump as the first signal and room for others (X, Reddit, more accounts). 3) Backtest every signal against market data: which tickers moved, how far, over which time windows, and how often the call was right. 4) Send real-time alerts (within minutes of a post) that carry that evidence: what the signal says, how it has performed historically, and how confident to be. Work in stages (brainstorm, plan, stress test, build) with my approval between each, on a dev database branch, never production, within $250."

## Added goal (Chris, 2026-09-30 22:03 UTC, verbatim)

"we want all of these things to try to attract USERS or subscribers or FOLLOWERS. We want people to find us and find a way to make $"

## Clean-slate direction (Chris, 2026-09-30 21:03 UTC, verbatim)

"we do NOT need to preserve any of the vestigial code or anchor back to it. We should design from first principles and build what would be best from a clean slate tomorrow for the case that we are trying to build."

Judge every plan as a fresh build. Old code is not a constraint and is not something to preserve. Production history (old posts, old predictions, old subscribers) still counts as data.

## Chris's standing rules

- Never merge. PRs only; Chris merges. Every merge to main currently redeploys all 12 Railway services and the old code has no CI.
- Never touch the production database. No production DATABASE_URL or OpenAI key in any sandbox session. Dev and backtests use the sandbox's own Postgres.
- Never send Telegram, email or SMS, or make paid LLM calls, from a sandbox.
- No crons: "I want real time. crons don't work as a rule." One always-on worker; daily/weekly jobs run inside its own scheduler.
- Total spend within $250 for the whole project (all four plans together).
- Test/probe code must be thinly scoped and flagged for removal: "I don't want to add junk or poor architecture."
- A scraper test from a cloud sandbox proves nothing about Truth Social blocking; real scraper proof runs on Railway only.
- Stages: brainstorm (approved), plan (engine, dashboard, notifications approved; growth awaiting approval), stress test (this review), build.

## What Chris asked for in this review (verbatim)

"Please have another agent run /ironclad via clauDNA marketplace pack against each plan to stress test it, focused on adversarial and not overbuilding"

So weight two things above all: (1) adversarial failure-finding (what breaks, what is wrong, what is unverified but load-bearing), and (2) overbuilding: scope, machinery, PRs, tables, endpoints, outlets or pages that are not needed for the goal now, and what to cut, defer or simplify. A finding that says "cut X" is as valuable as one that says "fix Y".

## The four plans (all reviewed, one at a time)

- Engine (approved): plans/engine.md
- Dashboard (approved): plans/dashboard.txt
- Notifications (approved): plans/notifications.txt
- Growth and money (awaiting Chris's approval): plans/growth.txt. Its "What changes in the other plans" table lists changes it will send to the other three planners; treat those changes as part of those plans.
- Planner notes in notes/ record agreements made after the docs were last edited (data model, app schema, alert_revisions, price display rights, crypto, Hyperliquid dropped). Treat them as part of the plans. Where a doc and a note disagree, the note is newer.

The plans share one database (engine schema + app schema) and one public API (/api/v1). Each plan's review must also cover its hookups to the other three plans.

## Environment facts

- Repo checkout: /home/user/shitpost-alpha (main at 139b145; the old system). Use it only to check claims the plans make about today's code or history, never as a design constraint.
- The sandbox network only reaches the hosts in its allowlist (PyPI, npm, GitHub, Ubuntu mirrors, truthsocial.com, ix.cnn.io, trumpstruth.org, Yahoo Finance). Alpaca, Telegram, X, OpenAI/Anthropic, Coinbase are not reachable.
- The account hit its five-hour usage limit last night; parallel agents are kept few.
