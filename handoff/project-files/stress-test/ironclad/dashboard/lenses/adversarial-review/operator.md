# Operator: lifecycle, scale and day-2

Reviewer 3 of 5 (inline; had read architect.md and skeptic.md).

## Launch-day load (new evidence: the deploy shape)

- The web service is one replica (railway.json:8, numReplicas 1) running one uvicorn process (railway.json:78, no --workers). Each visible tab polls /api/v1/alerts/changes every 5 s: 12 requests a minute per tab. The growth plan's public launch (X thread, Reddit, Show HN, reporters) is the moment traffic peaks. At 1,000 open tabs that is about 200 requests a second, each a DB query to Neon from one Python process. The plan calls the load "inference, not measured" (Budget) and does nothing to measure it.
- Combined with the limiter defect (architect.md: every visitor shares the proxy's bucket), the likely failure is not slowness but 429s for everyone and the header dot going grey on launch day. Corporate NAT and mobile CGNAT also share addresses, so even a fixed per-IP limit must be sized for many people behind one IP.
- Cheap fixes, all inside existing PRs: key the limiter on the real client IP (uvicorn --proxy-headers with Railway's proxy range, to verify); keep the newest seq in process memory, refreshed every second or two, so a poll that has nothing new never touches the DB; send Cache-Control: public, max-age=5 on changes, evidence and record responses so a CDN (Cloudflare, if the domain goes there) absorbs repeats; poll every 15 s instead of 5 (Telegram is the push surface; 10 s more on a web page changes nothing); one load test at 200 requests a second before the public launch.

## Cutover and rollback

- The cutover sitting stacks: engine PR 8 merge, the subscriber step, the webhook switch, WEB_DATABASE_URL, the domain (growth: the site moves to our domain at cutover), D1's merge, and switching old workers off. Each merge to main redeploys all 12 services (mission rules). D1 is the largest PR in the four plans (a new app, two endpoint families, CI, deletions) and its first contact with the production engine DB is that sitting.
- Rollback is undefined for the site. The engine's rollback is "switch the old workers back on" (engine G), but D1 has already deleted today's frontend and its endpoints, so the old site cannot come back without a revert, which is another redeploy of all 12 services.
- Fix: set WEB_DATABASE_URL at PR 7, when Chris creates the engine DB anyway, so N2 and D1's endpoints run against real shadow data on the real service for a week; make the app boot without that variable (lazy DB engine), so an early N2 merge cannot take the site down; drop "the cutover waits for D1" and let D1 merge in its own sitting, before or after; accept a stale old site for a few days as the fallback.

## Monitoring that is missing (and what is redundant)

- Nothing watches the public site. The engine's status, health endpoint and operator messages cover the engine; no one is told if the web service is down or every request is a 500. An engine scheduler job that fetches the web's /api/health each minute and calls notify_operator after 3 failures costs nothing and lives in PRs that exist.
- The public Status page (D2) is the opposite: it watches the engine, which is already watched, and shows it to the public. Cut it. Keep the header's freshness dot (one "last post seen at" field on an existing response) and one latency line on the Record page ("median post to alert this week: 3.1 min"), which is a trust signal, not an operator tool.

## Stale and growth cases

- 6 months: about 36,580 historical plus ~30 a day signals, a few hundred alerts. Volumes are trivial; the site needs plain "older" paging, not infinite scroll.
- Evidence and record are cached 5 min and rebuilt nightly. Fine.
- stream_id change (DB rebuilt): the browser must drop its bookmark and reload; one test.
- Old pool to the production DB via api/dependencies.py:7 must not survive D1 (see architect.md), or PR 11 and the archive of the old DB break the web service.
