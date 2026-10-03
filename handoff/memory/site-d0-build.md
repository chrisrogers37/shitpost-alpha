---
name: site-d0-build
description: Site D0 (website API base) build state, PR #262, and the Railway facts it found (X-Real-IP, config-file path, blocked docs hosts)
metadata:
  type: project
  modified: 2026-10-02T22:53:14.626Z
---

D0 = draft PR #262, branch claude/site-d0-84k70e, stacked on #258 (PR 1). Thread "Build the website's API base" (cmsg_01Ru8H43VFwFbPoWty16Gd6hQJSTVJgD7Bn1mSF7yTovFg), builder session_01RZbykYzTehMFWUPpX7udYu. Round 1 (1 blocker, 5 should-fix, 11 nits) folded in at aac1f51 (2026-10-02 23:54 UTC); goes back to the gauntlet (session_013E4KMGG5c9USVygEcNJkqa) on green CI. Notes for the engine planner (role via SQL, spoof check, WEB_GRANTS narrowing question) and site planner (static assets vs the rate limit) went to the coordinator to batch. Merge order: after #258, and only once the old Railway services are deleted (it removes api/, frontend/ and the root railway.json).

What later PRs build on (N2, D1): engine/engine/web/. Routes go on an `ApiRouter`, which requires an `ApiResponse` model, and get added to `API_ROUTERS` in app.py. Take `Db` and `StreamId` from deps.py. Lists use `Page[Item]` with `page: PageParams` and `take_page` (integer cursor keys). ApiRouter also refuses include_in_schema=False; ApiModel refuses aliases; /healthz has its own one-connection HealthProbe; startup refuses a role that could read prices. Errors use `ApiError(code, msg)`, and caching uses `ResponseCache(ttl).respond(request, build)`. The README has "Public API" and "Web service" sections.

Railway facts (2026-10-02):
- The docs list "X-Real-IP for identifying client's remote IP" (docs.railway.com/networking/public-networking/specs-and-limits), so the limiter defaults to X-Real-IP with 1 hop.
- Community forum reports: with Railway's CDN (opt-in, off by default), X-Real-IP holds the CDN's address. Keep the CDN off for the web service and verify on the live service at PR 7.
- The config file doesn't follow the root directory (docs.railway.com/deployments/monorepo). The engine service must set config path /engine/railway.json, and the web service sets none.
- docs.railway.com and station.railway.com are blocked from sandboxes. Read the docs at github.com/railwayapp/docs (content/docs/...) with WebFetch instead.

Related: [[ui-plan-stage]], [[ui-plan-hookups]], [[review-gauntlets]]
