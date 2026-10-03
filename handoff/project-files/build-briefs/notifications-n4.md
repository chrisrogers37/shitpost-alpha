# Notifications N4: MCP server and agent guide

You are building N4 of the notification layer in chrisrogers37/shitpost-alpha. It lets agents read the same alerts as the site, through:
- an MCP server at `/mcp` on the web service, with three read-only tools;
- an agent guide;
- the alert's JSON Schema.

Nothing pushes to agents; signed webhooks are in Later.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read "For agents" first. Where this brief and the plan differ, this brief wins.

Questions go by send_message:
- notification design: to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8);
- the `/api/v1` base: to the dashboard planner (session_01KCJr6bPZiRiCHvXaSz29dj);
- the record query: to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ).

If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If N2 or engine PR 9 isn't up yet, stop and say so.
- **The dashboard's D0:**
  - `/api/v1` in `engine/api/`, mounted by the web service;
  - the error shape and the real-client-IP rate limiter;
  - the no-price walker test;
  - the read-only web role;
  - the settings, including the site's host names.
- **N2:**
  - the alert routes, with one function per response shape built from `AlertV1`;
  - the change feed with `stream_id`;
  - the `WEB_PUBLIC_RESULTS` switch, which hides results until the launch.
- **Engine PR 6:** `AlertV1` and its public-format test.
- **Engine PR 9:** `engine.record`, the one record query that the record page, the daily results, the scorecard and the weekly finding share.
- **The dashboard's D2,** if it has merged: `/api/v1/track-record`, built on the same query.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys and no sends.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No Telegram, X, email or SMS. No crons and no Railway calls.
- **Public output.** No raw or entry price, raw post payload, model output or cost. "Not investment advice." in the guide and in the server's description.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json, unless D0 removed them.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases and run under the web role.

## Scope
**1. MCP server at `/mcp`.**
- **The server.** Use the official MCP Python SDK (`mcp`), pinned to a released version. It uses the streamable HTTP transport, stateless, with JSON responses.
- **Mounting.** Mount it in D0's app at exactly `/mcp`: no redirect from `/mcp/` or to it. Run its session manager inside the app's lifespan.
- **Host check.** Turn on the SDK's host check (DNS-rebinding protection). Allow the site's host names from D0's settings (shitpostalpha.com and the Railway address) and localhost for tests.
- **Limits.** D0's per-IP rate limiter covers `/mcp` too.
- **Description.** The server's name and description say what the service is, and include "Not investment advice."

**2. Three read-only tools.** Each calls the same functions as the API and the record page, and returns the same field names.
- **`latest_alerts(limit=20, instrument=None, disposition="sent")`:**
  - the newest alerts, as N2's list returns them;
  - `limit` at most 100;
  - instrument by slug or symbol.
- **`get_alert(public_id)`:** one alert as it stands, with its history, as N2's single-alert route returns it.
- **`track_record(instrument=None, window=None)`:**
  - the live record from `engine.record`, sent and FYI apart and beside the backtest figure, each labelled;
  - fewer than 20 graded calls shows the count without a rate;
  - while `WEB_PUBLIC_RESULTS` is off, it answers that results go public at the launch.

Tool descriptions are plain about what each returns. Each tool's errors are clear: an unknown id, a bad window or limit.

**3. The agent guide** at `/api/v1/docs/agents.md` (text/markdown):
- what the service is;
- a sample alert;
- the polling loop on `/api/v1/alerts/changes`: start from the head, keep `after`, restart from the head when `stream_id` changes, and poll every 15 to 30 seconds;
- the MCP endpoint, its tools, and how to add it to an MCP client (Claude Code's `claude mcp add --transport http`);
- the limits;
- "Not investment advice."

Link the schema from it.

**4. The schema** at `/api/v1/schema/alert.v1.json`:
- the JSON Schema generated from `AlertV1`;
- a test that fails when the model and the served schema drift;
- result fields documented as hidden until the launch.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests:
- **The SDK's own client,** over the ASGI app in-process: it lists the three tools and calls each, on a throwaway database with fixture alerts and results.
- **Mount checks:**
  - the lifespan starts the session manager;
  - exactly `/mcp`, with no redirect;
  - a Host header outside the list is refused;
  - the rate limiter applies.
- **Same answers.** `latest_alerts` and `get_alert` return what N2's routes return for the same inputs.
- **Results switch.** With it off, `track_record` reveals no grades, and no tool returns result fields. With it on, the numbers equal `engine.record`'s.
- **Prices.** The no-price walker passes over the tools' outputs and the schema.
- **The guide and schema** are served, and the drift test passes.
- **By hand,** with the result in the PR: run the web app locally, connect Claude Code to it with `claude mcp add --transport http`, and call each tool.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from N2's branch while it is unmerged, merging in engine PR 9's branch if that is unmerged too. Use main once both have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N4: MCP server and agent guide". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - a sample tool call and answer;
   - the guide's text.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
