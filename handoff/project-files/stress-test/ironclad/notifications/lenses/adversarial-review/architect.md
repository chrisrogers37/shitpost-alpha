# Architect: technical correctness and hookups

Reviewer 1 of 5, inline pass. Source: source-notifications.md (doc rev 47) + notes/notification-plan.md + growth change list. Line refs below are to source-notifications.md unless another file is named.

## A1. Raw entry price leaks through every public read path (critical)

- The doc says "The first result also carries the entry price and time used" (229-230). Engine F says outcome revisions carry "the realized move and the entry price and time used" (engine.md:173, hookup row engine.md:197).
- N2 returns each changed alert "whole" (193-195), webhooks POST the same object (185-192), MCP serves it (199-202), and the Telegram post is edited with results (147-150).
- The 1 Oct rule (growth.txt:237-245, engine.md:85) is "no raw entry price publicly, because a % series plus one price rebuilds the prices". The engine plan contradicts itself (engine.md:85 vs :173), and the notification doc inherits the leak.
- `alert_revisions` is insert-only, enforced by a trigger (engine.md:169). Once a revision holding a raw price is written and served, it cannot be scrubbed without breaking the "first call never edited" promise. The leak is permanent and replayable.
- Fix before engine PR 6 freezes alert.v1: the public alert.v1 holds only derived numbers (% since post, benchmark move, abnormal move, hit or miss, window). Entry price and time stay in engine tables (alert_progress, backtest_rows), never in the revision JSON. N2 adds a contract test that walks every public payload (changes, list, detail, webhook body, MCP tool output) and fails on any raw price field.

## A2. Edit-in-place conflicts with the insert-only model (critical, with User/Skeptic)

- The doc describes the Telegram channel as "edited in place as each day's results arrive" (147-150, N1 at 283-285). The engine and growth design treats the first call as immutable (engine.md:169, 77), and the dashboard links "each signal to its Telegram post as the receipt" (growth.txt:278-279).
- A Telegram edit replaces the text. As far as I know, viewers see only an "edited" mark and no history (verify). The receipt the growth plan links to is therefore the one artifact in the system that can be rewritten.
- Mechanics the plan has not specified: storing message ids per (destination, chat); edits up to 5 trading days later (crypto 7 days); "message is not modified" and "message to edit not found" errors; and the shadow-to-cutover switch. The Telegram destination's chat comes from a Railway variable (461-463), and message ids are per chat, so if the variable flips from the admin chat to the channel, any later update for a shadow-week alert would call editMessageText on the channel with an admin-chat message id.
- Recommendation: never edit. See result.md B2.

## A3. Non-alert broadcasts have no home in the cursor design (major)

- The design is "one running number, one kind of bookmark" (86-92). Every push follows alert_revisions.seq.
- The growth change list adds content that is not an alert revision: the Monday scorecard to the channel and X, daily results on X, and the report thread at public launch (lines 47-55; growth.txt:150-151, 287-290). None of these has a seq, a bookmark, a deliveries row, at-most-once handling, a dry-run switch or a give-up rule in the plan.
- Without a design, they become one-off send calls from scheduler jobs. That is exactly the "jobs that send follow-ups, briefing and scorecard" pattern the doc deletes from the old system (121-123).
- Recommendation: key deliveries by (outlet, item_key), where item_key is `alert:<id>:<rev>` or `digest:2026-10-05` or `scorecard:2026-W41`, with one `broadcast(kind, key, text)` entry point in N1. It goes through the same at-most-once record, switches and dry run. The scheduler calls it, and the numbers come from one track-record function shared with the dashboard's /record (dashboard D3).

## A4. Shared Alembic history: multiple heads equal an engine outage (major)

- The notification tables are migrations in the engine's one Alembic history (note; engine.md:204). The engine applies migrations at start-up and refuses to start if one fails (engine.md:119). Every merge to main redeploys every service (engine.md:259; mission).
- N1, N2 and N3 will each add app-schema migrations while engine PRs 6, 9 and 10 add engine migrations, all in parallel. Two PRs cut from the same head each pass CI alone, but merged together they leave two heads, and `alembic upgrade head` errors with "multiple heads". The engine does not start, so feeds, extraction and alerts all stop.
- A second, smaller race: the web service and the engine redeploy together on a merge, so a web endpoint that needs a new app column can serve before the engine has migrated.
- Recommendation: a CI step that fails when `alembic heads` returns more than one after rebasing on current main (state the rebase-before-merge rule in the PR template). The engine runs `alembic upgrade heads`, which tolerates independent heads. Web endpoints that depend on a new table check `alembic_version` at start-up and degrade with a 503 instead of a 500.

## A5. Cross-plan endpoint and table seams (major)

- The dashboard reads `alert_deliveries` for delivered times and outlet status (dashboard.txt:213, 249). No such table exists: the notification table is `app.deliveries`. Reading it directly would also couple the dashboard to this plan's internal table.
- The dashboard doc says the web role is read-only and "the dashboard writes nothing" (dashboard.txt:189-191, 310). N3's self-serve webhook registration (185-187) writes `app.destinations` from the web app. The 1 Oct model gives the web role SELECT/INSERT/UPDATE on app (engine.md:191), so the conflict is resolved on paper, but at the cost of an internet-facing service with write grants for a feature only Chris's agents use.
- N4's `get_evidence` and `track_record` "use the same queries" as the dashboard (255-256). Those queries arrive with dashboard D3 (dashboard.txt:295-301), but N4 states its gate only as engine PR 10 (335). The new Monday scorecard needs the same track-record numbers.
- Deep links: the doc sends every outlet to `/s/<signal_id>` (264). The 1 Oct model adds `alerts.public_id` for share links and moves the site to its own domain (growth.txt:273-276). Signal ids look like `truth_social:<id>`, which is long and has a colon.
- Growth wants "each alert's public post links in the alerts API" (52-53). The link (`t.me/<channel>/<msg_id>`) exists only after sending and lives in deliveries, so it cannot be in the immutable revision that cursor readers already consumed.
- Recommendation: N2 serves a mutable `delivery` envelope beside the immutable alert body (per public outlet: posted_at, url, status), joined from app.deliveries at read time. The dashboard reads only that. Outlets link to `https://<domain>/a/<public_id>` (or whatever canonical path the dashboard picks), with the base URL from config. N4 and the scorecard name D3 as a dependency, or the track-record query moves into a shared module with one owner.

## A6. Smaller correctness notes (not ranked)

- "The engine never writes them" (233-234) is literally false at the process level. The delivery workers run inside the engine process (110-111) and write deliveries and bookmarks, so the engine's DB role needs app write grants. State it in engine PR 1's role setup.
- Filter semantics across revisions are undefined. If a later revision changes disposition or tier (for example, the nightly evidence refresh), does a destination filtering `disposition=sent` post it? The give-up age stops people outlets, but webhooks would receive an alert.updated for an alert they never got as alert.created. Evaluate the filter on the first revision only, and state it in the schema doc.
- stream_id change (note): push outlets should jump their bookmark to head, not replay from zero. The 30-minute give-up hides this for people outlets, but webhooks would get 24 h of replay.
- If N3 ever ships: an httpx timeout of 5 s is per phase (connect, read, write, pool), not a total. A receiver that trickles a byte every 4 s holds a connection indefinitely. Wrap each attempt in `asyncio.timeout(5)`. Pinning the checked IP while keeping SNI and hostname verification needs a custom transport (verify before N3).
- N4 mounts the MCP ASGI app on FastAPI (316-319). slowapi's decorator limits do not apply to a mounted sub-app, so the "own per-IP limit" needs middleware.
- The alert.v2 path: revisions are stored snapshots, so a replay across a v1-to-v2 boundary returns mixed versions. The schema doc should say whether readers get stored or translated versions.
