# Notifications N2: alerts API

You are building N2 of the notification layer in chrisrogers37/shitpost-alpha: the public read routes for alerts, under `/api/v1`, in the engine package. Agents, the site's live list and anyone who polls follow the same numbered entries the delivery core does. Nothing pushes yet.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read its "For agents" and "Hookup to the engine and the site" sections first. Where this brief and the plan differ, this brief wins.

Questions go by send_message:
- these routes: to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8);
- the `/api/v1` base: to the dashboard planner (session_01KCJr6bPZiRiCHvXaSz29dj);
- the alert format: to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ).

If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If either isn't up yet, stop and say so.
- **Engine PRs 1 to 6** ("Engine PR n: ..."). The ones N2 reads:
  - PR 1's migrations, `WEB_GRANTS` and the web role;
  - PR 3's `engine.instruments`, with their permanent slugs;
  - PR 6's `engine.alerts` with the `AlertV1` model, its public-format test (an allowlist of public fields with units), the insert-only `engine.alert_revisions` with `seq` in commit order, and `engine_meta.stream_id`.
- **The dashboard's D0** ("Dashboard D0: ..."). It creates `/api/v1` in `engine/api/` under the engine's CI:
  - the app that the web service mounts, reading through the read-only web role (`WEB_DATABASE_URL`);
  - the error shape and paging conventions;
  - the real-client-IP rate limiter;
  - a 5-second cache for the change feed;
  - `/healthz`;
  - the test that walks every response and fails on a price-like field;
  - the role test;
  - the shared link builder.

  Use D0's conventions everywhere and add nothing D0 already has.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys and no sends.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No Telegram, X, email or SMS. No crons and no Railway calls.
- **Public output.** No raw or entry price, no raw post payload, no model output or cost, and no link other than our own pages.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json, unless D0 has already removed them.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases. Create a `web` role there if D0's tests don't already, and run the route tests through it.

## Scope
**1. `GET /api/v1/alerts/changes?after=<seq>&limit=`**
- **What it returns.** The entries after `after`, oldest first, each with:
  - `seq`;
  - its kind (a new alert, or a later revision such as a result);
  - the alert's `public_id`;
  - its time;
  - the revision's public body, built from `AlertV1`.
- **Envelope.** Every response carries `stream_id`, `head_seq` and `has_more`.
- **Limits.** `limit` defaults to 100, with a maximum of 500. A missing `after` starts from the head, so it returns nothing and the current `head_seq`.
- **Stream check.** The optional `stream` parameter: if it's given and differs from the current stream_id, answer 409 in D0's error shape, carrying the new `stream_id` and `head_seq`. The reader then starts again from the head.
- **Cache.** The feed uses D0's 5-second cache. Polling every 15 to 30 seconds is plenty: say so in the response docs.

**2. `GET /api/v1/alerts?before=<cursor>&limit=&instrument=<slug>&disposition=sent|fyi`**
- Alerts newest first, each as its current public `AlertV1`.
- An opaque cursor in D0's paging style.
- Filters by instrument slug and disposition.
- FYI alerts are included and labelled, since the site shows them.

**3. `GET /api/v1/alerts/{public_id}`**
- The alert as it stands now, plus its history. Entry 1 is the call as first sent, word for word, and the later revisions follow with their times.
- An unknown id gets a 404 in D0's shape.

**4. Results stay private until the launch.**
- **The switch.** One web-service setting, `WEB_PUBLIC_RESULTS` (or the name D0's settings conventions give it), default false.
- **While it's off:** result revisions are left out of the change feed, and result fields are left out of every response. The `seq` numbers still advance, so `has_more` and `head_seq` stay honest.
- **At the launch,** Chris sets it to true. Say so in the PR.

**5. Bodies from one model.**
- Every response body is built from the engine's `AlertV1`, through one function per shape that the site's and N4's code can reuse.
- Add the routes to D0's no-price walker test, and to the engine's public-format allowlist if it covers API shapes.

**6. Queries.**
- They read `engine` tables only, through the web role, never `prices`.
- Index whatever the queries need (for example revisions by alert, and alerts by instrument and time) in a new engine migration, add-then-remove only.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests, through the real read-only web role:
- **Following the numbers.** While another task saves alerts and revisions concurrently, a reader paging with `after` gets every entry exactly once, in order.
- **Stream change.** A changed stream_id gives a 409 with the new head.
- **Paging.** The newest-first list pages without gaps or repeats, and both filters work.
- **One alert.** Entry 1 equals the first revision exactly; a 404 for an unknown id.
- **Results switch.** With it off, no result revision or result field appears anywhere, and `head_seq` still advances. With it on, they appear.
- **Prices.** The no-price walker passes over every route.
- **No database.** With the database unreachable, every route answers 503 in D0's error shape.
- **Role.** The web role can't read `prices` or `app.deliveries`.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from whichever of D0's and engine PR 6's branches is still unmerged, merging the other in if both are. Use main once both have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N2: alerts API". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - an example response for each route;
   - the results switch's name and default.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
