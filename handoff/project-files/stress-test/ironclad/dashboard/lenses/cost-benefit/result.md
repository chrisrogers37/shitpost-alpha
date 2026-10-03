---
lens: cost-benefit
worker: cost-benefit
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-dashboard.md
started: 2026-10-01T01:13:34Z
completed: 2026-10-01T01:24:00Z
status: completed
severity: major
---

## Risks

- **[major] scope**: D1 is the only dashboard PR on the cutover's path, and most of the growth list lands on it. D1 was already size L before growth: a new React app, the live list with change polling, the signal page, link previews, the /api/v1/signals and /api/v1/bars endpoints, deleting the old frontend, and Vitest, Playwright and a frontend CI job (Build order, D1). The growth row adds the domain, canonical links, sitemap, server-rendered previews, receipt links, follow buttons with ?ref, visit counts, a methodology and disclaimer page, % charts and a README landing page, and says each item "should fit inside a PR the plan already has" (growth plan, "What changes in the other plans", Dashboard row). Most of this earns nothing at the cutover. Growth's own Launch section makes the cutover a soft launch where "nothing is promoted before the evidence is in" (engine PR 10). Every item added to D1 delays the cutover: "D1 is the only PR on the cutover's path" (Build order), and "the new dashboard merges right after PR 8" (engine G).
  - **Recommendation:** Limit D1 to what the cutover needs: the live list (alerts only), the signal page with a % chart, a title and description injected on the server for each signal page, a footer disclaimer and an /about page (see the Connect finding), the domain with canonical tags, the visit-count beacon, deleting the old frontend, and CI with one Playwright smoke test. Move the sitemap, ticker pages, report page, preview images and README landing page into a new "launch" PR timed with engine PR 10 and the report. Add that PR to the build-order table so every growth item has a PR.

- **[major] scope**: Too many page types. With growth folded in, the site goes from five menu pages plus the signal page to about ten page types: Live, Signal, Evidence, Track record, Status, Connect, Ticker, Topic, Report and Methodology. Three pairs overlap:
  - Evidence and Report show the same backtest_summary from the same run (Pages > Evidence; growth row: "Exports the backtest report's numbers so the dashboard can publish a report page").
  - The Evidence drill-down ("A row opens the posts behind it"), ticker pages and topic pages run the same query (signals × mentions × backtest rows) with different filters.
  - Connect and Methodology are both static explainer pages.

  Each page type costs a route, a server-rendered preview, a sitemap entry, screenshots at two widths and Playwright coverage. Because "the site has no private endpoints" (Decisions: One API for people and agents), each one also needs a public, documented /api/v1 contract that agents may come to depend on. More page types means more public API to support.
  - **Recommendation:** Keep six page types: `/` (live), `/s/<id>` (signal), `/record`, `/report` (written narrative on top, the Evidence table below; drop `/evidence` or redirect it), `/t/<slug>` (a ticker page that is also the Evidence drill-down, with a topic filter) and `/about` (methodology, disclaimer, how to connect). Cut topic pages, since the report table filtered by topic covers them, and cut the separate Connect page. Feed ticker pages from filters on existing endpoints (`/api/v1/signals?instrument=`, `/api/v1/evidence?instrument=`) rather than new endpoints. Tell the engine planner that no plan has source pages, so the per-source all-topics rows and per-source page indexes in engine E "Output" and H "Indexes for pages" have no reader yet.

- **[major] scope**: Server-rendered preview images for five page types (signal, ticker, topic, record and report) are the largest single growth item and the weakest return at this stage. They need an image renderer in the web service (fonts, layout, caching, a test per page type and CPU on every new share) and a second server-side rendering path next to the React app. The benefit is smaller than it looks, for three reasons:
  - The notification plan keeps links out of our own X posts ($0.20 a post with a link vs $0.015 without; notifications Costs), so our own posts never show the card.
  - Telegram and X cache a link's preview when it is first fetched (an outside fact not checked here). A card that shows a move or a result goes stale, and a stale move can mislead.
  - The soft launch is not promoted.

  Text previews (og:title and og:description, served with the page) get most of the benefit.
  - **Recommendation:** In D1, insert the title, description and canonical link into index.html for each route in the FastAPI catch-all route: one indexed read, cached. Use a few prebuilt images: a brand card, plus one per direction and tier if wanted. Previews show only facts that never change (the call as first made, ticker, direction, tier, post time), never the move so far. Build generated images only after visit counts show that shared links bring visitors, and check how Telegram and X cache previews before building any per-signal image.

- **[major] security**: Raw-price surfaces are still in the plan after the derived-numbers rule was agreed. The hookups note adds `/api/v1/prices/latest`, "polled every 5 s on an open signal page" (00:05). Pages > Signal page draws "1-minute prices since the post". The Evidence drill-down lists "entry price". The reads table keeps a public `/api/v1/bars/<symbol>`. The agreed rule (engine Data model > Display rights; growth "Legal and data rules > Prices") is that nothing public shows a raw price or the raw entry price, because Alpaca's free data may not be displayed publicly (unverified). Under that rule the public bars and latest-price endpoints can serve nothing, yet each still needs a display-rights check, tests and docs. Polling every 5 seconds for a value that alert_progress recomputes once a minute (engine F, "Live prices") is wasted load.
  - **Recommendation:** Cut `/api/v1/prices/latest` and the public `/api/v1/bars/<symbol>`. Return the chart's data from the signal endpoint as a derived series: % since the post for each instrument and its benchmark (SPY, or BTC for crypto), computed on the server from market_bars, together with the alert_progress row. Refetch it once a minute while the market is open, not every 5 seconds. Remove the entry-price column from the drill-down. With no raw-price endpoint, the dashboard needs no display-rights code until the paid gate brings a licensed feed.

- **[major] scope**: Cut the Status page (D2). Its readers are Chris and agents, and it rebuilds what the engine already provides: `python -m engine status` and a health endpoint that show feed freshness, signals per stage, job runs and each post's timings (engine A, "Status"), plus operator messages on failure (notifications N1). D2 recomputes the same percentiles in the web app from feed_health, job_runs and signal times. That ties the web app to internal engine tables that will change, and it pulls in the notification plan's `/api/v1/status/outlets`, whose only stated reader is this page (notifications, Dashboard touchpoints). As a public page it also shows outages and names the mirrors we poll. The growth plan notes that the CNN live feed's terms may bar commercial use (unverified), so naming it in public adds risk for no gain. Visitors get the same reassurance more cheaply from each signal page's timing and the header's freshness dot, both already in D1.
  - **Recommendation:** Drop D2 and `/status`. Keep D1's freshness dot, driven by one field (time of the newest sighting) on a response the page already fetches. Show "first seen N min after the post" on signal pages without naming the feed. If N4 keeps its `engine_status` MCP tool, have it call the engine's single status query rather than adding `/api/v1/status/engine`. Tell the notification planner that `/status/outlets` can go. This saves one PR and two endpoints.

- **[major] scope**: Public grading of calls is the growth plan's whole pitch ("called in minutes, graded in public"), but the plan bundles it with the backtest pages behind the evidence gate. D3 ships Track record, Evidence and the per-signal results together, and "if nothing beats random times after costs, it waits for the rethink" (Build order). This causes two problems:
  - The soft launch at cutover starts "the public record" (growth Launch, step 3), but no page grades it until engine PR 10.
  - If the backtest finds no edge, the live record is never published. Yet the live record is what tells Chris whether he would trade on these alerts, and growth's gate check 2 ("8+ weeks live inside backtest range") depends on it.

  Grading does not need the backtest. It is the realized move against the benchmark at each window, which the engine already computes every minute in alert_progress from PR 6. Only the "outcome updates" revisions wait for PR 10 (engine F).
  - **Recommendation:** Split D3. Ship Track record and the per-signal results once graded live outcomes exist, whatever the edge gate shows. Ask the engine planner to move live-alert grading (realized and abnormal move per window, hit or miss) from PR 10 into PRs 6 to 8, and leave tiers and evidence lines in PR 10. Ship Evidence and the report with the public launch. Start Track record small: one sentence, one cumulative line for all sent alerts against random times, and the list of alerts. Add the per-tier lines and the "whether the tiers hold" panel once each tier has enough live alerts to mean something (for example 30).

- **[major] performance**: The plan's claims that it "costs nothing extra" and adds "a little load" ("inference, not measured") break down at the moment growth is aiming for. Every open page polls `/alerts/changes` every 5 seconds, and a second cursor (`signals.seq`) is needed when "All posts" is on. A Show HN or Reddit post can bring hundreds to thousands of open tabs. Today's rate limiter shares one bucket across all visitors. `api/rate_limit.py:10` uses slowapi's `get_ipaddr`, which looks for a header named `X_FORWARDED_FOR`. That name never matches the real header, so the limiter falls back to the client address. The web service runs `uvicorn` without `--proxy-headers` (railway.json, web startCommand), so that client address is Railway's proxy. This was checked in the code at 139b145, and the notification planner noted it for N2 and N4. A new API built the same way would rate-limit the whole site at a handful of viewers on launch day.
  - **Recommendation:** Before D1, use one rate limiter for all of /api/v1, keyed on the real client address taken from trusted proxy headers, and share it with N2. Make the newest-changes request cheap for everyone: cache "nothing after seq X" in the web process for 1 to 2 seconds and send `Cache-Control: max-age` on it, so a CDN in front of the domain can absorb launch traffic (Cloudflare, if growth's registrar is used with its proxy on; check). Keep the live list to alerts only so each page runs one poll, and serve "All posts" without live updates. Before the public-launch PR, load-test that endpoint in the sandbox with a few hundred simulated tabs.

## Gaps

- **[minor] scope**: Some evidence and chart features carry hidden work or little value.
  - **Typical path:** the "typical path of similar past posts" drawn behind the chart (Pages > Signal page, item 4) needs minute-by-minute average paths for each topic and ticker. The engine does not produce these, because backtest_summary holds per-window statistics (engine E "Output", F "Evidence"), so this is unplanned engine work.
  - **Layer switch:** the evidence-layer switch (live record, keyword rules, LLM backfill) triples the public table's states and the text needed to explain them, for a distinction few visitors will use.
  - **Minute bars:** the Risks table says "minute bars cover every post since 2022". That conflicts with the engine's storage tiers, which keep 1-minute bars in the database only for alert windows and the last 30 days, with history in files. Signal pages for the roughly 36,000 archive posts get daily bars at best.
  - **Recommendation:** Mark the typical move at each window on the chart from backtest_summary instead of drawing a path. On the public page, show only the evidence layer the alerts quote, and describe the other layers in /about or the report. For archive posts, show the window results as numbers with no chart, and don't ask the engine to keep minute bars for history.

- **[minor] scope**: Connect has its own PR (D4), gated on N3 and N4, which is a whole PR for a static page, while the disclaimer has no PR at all. Growth's rules apply "from day one": "Not investment advice" in the site footer, and a notice that the operator may hold positions (growth "Legal and data rules"). The soft launch at cutover is public, but the growth row adds the methodology and disclaimer page without placing it in any PR.
  - **Recommendation:** Put the footer disclaimer and one /about page (methodology, disclaimer, the operator-positions notice, how to connect) in D1. Connect's links appear as their targets go live (the X link once the account posts, /mcp after N4), driven by a config list rather than a PR each. Delete D4.

- **[minor] observability**: Part of the attribution plan measures nothing. A ?ref tag on a follow button that points to t.me or x.com is dropped by those sites, so it cannot show which page brought a follower. Telegram's named invite links (notification plan) are what count joins. It is also unverified whether Cloudflare Web Analytics reports query strings such as ?ref (growth Budget lists the tool itself as unverified).
  - **Recommendation:** Point the site's follow buttons at the website's own named Telegram invite link, one per page type if wanted, from the notification plan's list. Use ?ref only on links we post elsewhere that lead to our domain. Before D1, check that the analytics tool shows query strings; if it does not, rely on referrers and invite-link counts and drop ?ref.

- **[minor] scope**: If crypto is approved on the engine card, it brings a second set of result windows and a 24-hour market. Crypto uses 5m, 15m, 1h, 4h, 24h, 3d and 7d; stocks use 5m, 15m, 1h, close, 1d, 3d and 5d (engine E). The dashboard's "Result windows" decision lists only the stock set. Every results view (signal page, Evidence or report, Track record) is designed around one set of columns, and the header's market clock covers stocks only.
  - **Recommendation:** Build the window columns from the windows each instrument carries rather than a fixed list. Split the report and Track record tables by asset class rather than merging ten columns. Show the market clock only on stock alerts, and update the Result windows decision row.

## Questions

- **[minor] data-integrity**: Which calls count in the public Track record? The dashboard counts "Only alerts made in real time... alerts since the cutover" (Pages > Track record). The engine's live layer also includes the old system's real-time predictions from the read-only export (engine E, G). If the record page and the report count different sets of calls, the plan's own risk "The page and the alert disagree" will happen. Including the old calls, labelled as the old system's, gives the record months of history at the soft launch. Excluding them keeps the record to the new engine's calls only. Chris should pick one definition, and every page, the report and the MCP `track_record` tool should use it.

## Observations

- **[info] scope**: Return on each part, PR by PR (sizes S, M, L, XL are relative). The table covers the plan with the growth items folded in.

  | Unit | Size | Return | Verdict |
  | --- | --- | --- | --- |
  | D1 core: live list, signal page, /api/v1/signals, delete old app, CI | L | Critical | Keep, with scope capped (first finding) |
  | D1 laptop split view (list beside open signal) | M | Low | Cut candidate: list opens the full signal page and keeps scroll on return. Chris approved this row, so it is his call |
  | D1 link-preview text (title, description) | S | High | Keep in D1 |
  | D1 /api/v1/bars and 1-minute price chart | M | Negative under the price rule | Replace with a derived % series |
  | D2 Status page and /api/v1/status/engine | M | Low | Cut |
  | D3 Track record | M | Critical (the growth pitch) | Split out; ship before the edge gate |
  | D3 Evidence | M | High at launch | Merge into /report |
  | D3 typical moves and results on signal page | M | High | Results with Track record; typical moves with PR 10 |
  | D4 Connect | S | Moderate | Fold into /about in D1 |
  | Growth: own domain, canonical links | S | High | D1 |
  | Growth: sitemap | S | Moderate | Launch PR; only signals with a call, plus ticker pages, record and report |
  | Growth: preview images for 5 page types | L | Low for now | Defer; use a few prebuilt images |
  | Growth: ticker pages | M | Moderate | Launch PR, as the Evidence drill-down |
  | Growth: topic pages | M | Low | Cut |
  | Growth: report page | M | Critical at public launch | Launch PR, merged with Evidence |
  | Growth: methodology and disclaimer | S | Critical (legal, from day one) | D1, as /about |
  | Growth: receipt link to the Telegram post | S | Moderate | Keep; needs N2 to carry post links. Channel posts are edited in place, so show "first published at" from revision 1 as the real receipt |
  | Growth: follow buttons with ?ref | S | Low as specified | Fix the mechanism (attribution finding) |
  | Growth: visit counts | S | High (measures everything else) | D1 |
  | Growth: % charts against SPY | S | Critical (price rule) | D1 |
  | Growth: README as landing page | S | Moderate | Any time; nothing depends on it |

  Net result: three PRs instead of four plus unplaced growth items. D1 is the cutover minimum. "Record" brings Track record and per-signal results once graded outcomes exist. "Launch" brings the report with the Evidence table, ticker pages, the sitemap, typical moves and the README, and lands with engine PR 10.

- **[info] scope**: Verdict on each endpoint the dashboard reads or writes.

  | Endpoint | Owner | Verdict |
  | --- | --- | --- |
  | /api/v1/signals, /api/v1/signals/<id> | Dashboard | Keep; carry the derived % series and alert_progress; add ?instrument= for ticker pages |
  | /api/v1/bars/<symbol> | Dashboard | Cut from the public API |
  | /api/v1/prices/latest | Dashboard | Cut |
  | /api/v1/evidence and /api/v1/evidence/<topic>/<ticker> | Dashboard | One endpoint with filters, serving the report and ticker pages |
  | /api/v1/track-record | Dashboard | Keep; ship early |
  | /api/v1/status/engine | Dashboard | Cut; N4 calls the engine's own status query if it keeps engine_status |
  | /api/v1/status/outlets | Notifications | Cut along with the Status page |
  | /api/v1/alerts/changes, /alerts, /alerts/<id> | Notifications | Keep; add the shared cache and fix the rate limiter |
  | New data endpoints for ticker, topic or report pages | Growth (implied) | Don't add; use filters on the endpoints above |
  | sitemap.xml and per-route meta tags | Dashboard (growth) | Keep; read-only, outside /api/v1 |
  | Preview-image route | Dashboard (growth) | Defer |

  The dashboard's own /api/v1 endpoints drop from eight, plus whatever growth implies, to four: signals, one signal, evidence and track record.

- **[info] scope**: Most of the value sits in two places. The first is the signal page: every outlet links to `/s/<id>` (notifications, Dashboard touchpoints), and it is both the page people share and the receipt. The second is the Track record. The live list matters less for growth, because followers live in the Telegram channel. Build and polish the signal page and Track record first.

- **[info] architecture**: There are two share IDs for one thing: `/s/<signal_id>` covers every post, and `alerts.public_id` is the "short public id for share links" (engine F). Make `/s/<signal_id>` canonical, because signal pages exist for posts with no alert. If a short link is wanted, `/a/<public_id>` should redirect (301) to it and never be a second page. Otherwise canonical tags, the sitemap and previews must all handle two URL schemes.

- **[info] performance**: The budget holds at about $0 for the dashboard. The domain ($10 to $20 a year) sits in growth's budget. Cloudflare Web Analytics at $0 is unverified. Railway network transfer for a launch-day spike should be a few dollars at most (inference). If the repo is private, Playwright browser installs add to the GitHub Actions minutes that engine CI also uses, so check the repo's visibility and free minutes. Generated preview images would add CPU on the web service; they are deferred above. The real cost of this plan is build effort and delay to the cutover, not money.
