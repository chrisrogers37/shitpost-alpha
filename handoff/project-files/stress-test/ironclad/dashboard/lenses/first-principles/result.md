---
lens: first-principles
worker: first-principles
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-dashboard.md
started: 2026-10-01T01:13:25Z
completed: 2026-10-01T01:21:00Z
status: completed
severity: critical
---

## Blockers

- **[critical] scope**: The signal page is built to answer the wrong question. "Is it still worth trading?" (Summary; Pages > Signal page; decision row "Headline on each alert", which sets the headline to the tier plus "how much of the typical move is left") is a question the engine cannot answer and the project should not be answering.
  - **No evidence supports it.** The engine's backtest (Engine §E) measures returns from entry at alert time. It never measures how much return is left after a stock has already moved x%. So "typical move minus move so far" is an invented number: the expected rest of the move, given that the stock has already moved x, is not the typical move minus x. A stock that has already moved the full typical amount can reverse or keep going.
  - **It contradicts the growth plan's positioning.** The growth plan says "We can't win on speed ... so we win on evidence" (Growth, Who it's for). Our alerts land 2-4 minutes after a post, and buyers of TMTG's millisecond feed get the first minutes (Engine, Risks).
  - **It crosses the growth plan's legal line.** A publisher stays impersonal and "not timed to specific market activity" (Growth, Legal and data rules). A per-alert verdict, updated by the minute, on whether to trade is timed advice. Track record's cumulative "what following every live alert would have returned" curve is a hypothetical-performance claim. Whether that matters for a publisher is unverified, and the lawyer comes only at the gate.
  - **It gives a misleading headline for most stock calls.** 69% of posts land while the stock market is shut (Engine, Data model), and stock entry is the first regular-session price. For those calls the headline reads "all of the move left" until the open.
  - Restated without solution terms, the page's job is: show what was called, the evidence behind it, and how it turned out against the benchmark, with misses kept.
  - **Recommendation:** Before D1 is written, change the signal page's organising question to "what was called, on what evidence, and how did it do". Drop the "move left" headline and the decision row that sets it. The headline becomes the call, the evidence tier (from PR 10) and the graded result for each window once one exists. If move-so-far stays on the page, show it as a measured fact with its time, for example "+1.2% vs SPY since the alert, as of 14:05". Put it beside the backtest's typical move for the same window, with no subtraction and no "worth trading" verdict. Replace the cumulative "following every alert" curve with hit rate and median move per window, and add the curve to the lawyer's list for the gate.

## Risks

- **[major] data-integrity**: Calls go ungraded until the backtest shows an edge. Every result the dashboard shows comes from engine PR 10's outcome updates: the signal page's Results, Track record, and the growth plan's promise of a record "graded in public, misses kept". Sources: Engine F, Outcome updates; Notifications, Hookup to the engine, Updates; and this doc's own reads table, row "Results per window ... Engine PR 10".
  - PR 10 waits for Chris to read the report, and "if nothing beats the placebo after costs, we stop and rethink" (Engine, Gates). D3 "shares the engine's evidence gate".
  - So from the cutover until PR 10, weeks at best, the public record that "starts that day" (Growth, Launch) shows calls with no grades. If no edge is found, live calls are never graded at all, and that is exactly when an honest record matters most.
  - Grading a live alert needs only bars and the benchmark, not the evidence tiers.
  - **Recommendation:** Ask the engine planner to move outcome grading out of PR 10 and into PR 6 or PR 8: each live alert's move against its benchmark for every window, computed nightly. Show those results on the D1 signal page from the cutover. Keep only the evidence lines, tiers and tradeable flag behind the edge gate. The live track record then no longer depends on the backtest verdict.

- **[major] architecture**: The plan's price surfaces break the agreed price rule, and folding the rule in naively may not fix it.
  - **What breaks the rule.** The 1-minute price chart, /api/v1/bars/<symbol>, and /api/v1/prices/latest (polled every 5 s since 00:05, per ui-plan-hookups) put raw Alpaca prices on a public API that agents read. The 1 Oct rule forbids that (Growth, "Prices: show what we compute"; Engine, Data model, Display rights).
  - **Why the obvious fix may not work.** Switching to a minute-by-minute "% since the post, ticker vs SPY" chart may still count as showing the data. The growth plan itself notes that a % series plus one price rebuilds the prices, and any ticker's price at a known minute is freely available. A minute-level % series is therefore the bars in another unit. Whether Alpaca treats such derived series as redistribution is unverified.
  - **Claims that do not match the engine's storage:**
    - "Minute bars cover every post since 2022" (Risks table) holds for the backtest, not the site. The database keeps 1-minute bars only for alert windows and the last 30 days; research history stays in files (Engine C, storage tiers).
    - "The typical path of similar past posts" (Signal page, item 4) has no engine table behind it. backtest_summary holds totals per window, not paths.
    - alert_progress is recomputed once a minute, so a 5 s price poll fetches the same row 12 times.
  - **Recommendation:** Cut from D1 and from /api/v1: /bars/<symbol>, /prices/latest, the 1-minute chart, lightweight-charts and the typical-path overlay. The signal endpoint carries computed numbers only: the move against the benchmark at each of the windows, and the latest alert_progress row, refreshed every 60 s. If a picture is wanted, draw those window points as a small inline SVG. Before any PR draws a minute-level % series, get Alpaca's written answer on whether it counts as redistribution; the growth plan already plans to ask Alpaca at the gate. Until then, show results per window only. This also removes "1-minute bars for display" from what the engine must keep.

- **[major] scope**: The engine cutover now waits on frontend scope.
  - **The dependency.** The engine's cutover, which is the deliverable that matters (alerts within minutes), waits on D1 (Summary; Build order).
  - **The growth list makes D1 bigger.** It adds the move to our own domain at the soft launch, canonical links, a sitemap, server-rendered previews, follow buttons with ?ref tags, visit counts, a disclaimer page and % charts. It also says "each item should fit inside a PR the plan already has", so all of this lands on the cutover's critical path.
  - **Two redeploys in one sitting.** D1 merges "right after engine PR 8, in the same sitting". Every merge redeploys all 12 old services, and the old code has no CI (mission, Chris's standing rules).
  - **No rollback for the site.** D1 deletes the old frontend and its endpoints. The engine's rollback ("switch the old workers back on", Engine G) would leave the new site reading a database that has stopped updating. The only way to roll the site back is to revert D1 and redeploy, and no runbook lists that step.
  - **Recommendation:**
    - Freeze D1 to what the cutover needs: the signal page that every Telegram post links to, a plain list and the disclaimer footer, served on the final domain.
    - Move every growth item to a PR timed to the public launch (engine PR 10), which is when the growth plan starts promotion anyway.
    - Add "revert D1" to the PR 8 runbook as the site's rollback.
    - Have Chris switch the old workers off before merging D1, so its redeploy affects only the web service.

- **[major] architecture**: The stack was inherited from today's app, and the growth plan has since changed what the stack needs to do.
  - **It is today's stack.** The Stack row says React, TypeScript, Vite, TanStack Query and lightweight-charts were "chosen for the live list and the charts, not because today's app uses them". The list matches today's frontend/package.json minus framer-motion (checked at main 139b145).
  - **Approved before growth changed the site's job.** The growth plan then made the site something people find through search and share: server-rendered titles and preview images for signal, ticker, topic, record and report pages, plus canonical links and a sitemap (Growth, Dashboard row).
  - **Link previews need a second renderer.** Telegram, X and Slack fetch link previews without running JavaScript. The site is a single-page app served from FastAPI's catch-all route (api/main.py:83-92), so that route would have to query the database on each HTML request and inject meta tags, while React renders the same page again in the browser.
  - **The cost.** Every public page gets two renderers, plus Vitest, Playwright, a Node toolchain and a frontend CI job. The pages change nightly or a few times a day.
  - **The stated reasons have shrunk.** Once the price rule removes the minute chart, the "charts" reason for React is gone. The "live list" reason comes down to one polled list.
  - **Recommendation:** Re-decide the Stack row before D1. The from-scratch choice is server-rendered HTML from the existing FastAPI app: Jinja templates calling the same query functions that back /api/v1, so "the site shows nothing the API does not" still holds. Add about 100 lines of plain JS, or htmx, to poll the list. Previews, canonical tags, the sitemap and search indexing then come for free. Tests stay in pytest plus one Playwright smoke test. If Chris keeps React, cap it at:
    - meta injection in the catch-all route;
    - one static preview image per page type;
    - no per-page code-splitting;
    - no Vitest unit layer.

- **[major] scope**: The site has spread to about eleven surfaces, most of them views of the same data. With the growth list folded in, they are:
  - from this doc: the live list, signal, Evidence, Track record, Status and Connect;
  - from the growth list: ticker, topic, report and methodology/disclaimer pages, plus a README landing page;
  - server-rendered previews for five of them.

  Several overlap or have nothing to show:
  - **Four views of one table.** Evidence (a topic-by-ticker table), ticker pages (one ticker across all topics), topic pages (one topic across all tickers) and the report page all read backtest_summary and backtest_rows. Track record is the live layer of the same tables.
  - **Empty before the edge.** Most of these pages have nothing to show before PR 10's edge gate. If the report shows no edge, "there is no public launch" (Growth, Launch), and the pages built for search have no job.
  - **Connect.** D4 is a whole PR, waiting on N3 and N4, for a page of links that the growth plan's follow buttons and the site footer already provide.
  - **Recommendation:** After D1, keep three page types:
    - **The report**: backtest evidence and the live record together, each labelled by layer, with filters.
    - **/ticker/<slug>** and **/topic/<slug>**: filtered permalinks of the report that also list the signals behind them.

    Drop the separate Evidence and Track record pages. Cut D4 and put the Telegram channel, X, agent guide and /docs links in the footer and README. Ship this as one PR gated on PR 10 and the edge, in place of D3, the growth additions and D4.

- **[major] performance**: The live list is overbuilt, and launch-day traffic would rate-limit every visitor at once.
  - **What the browser re-implements.** The list rebuilds the agents' change-log protocol in the browser (Decisions: Home page, How it goes live; ui-plan-hookups). That means:
    - 5 s polls of /alerts/changes;
    - keeping only the highest revision of each alert;
    - restarting when stream_id changes;
    - a "new" bar and a count in the tab title;
    - a second cursor (signals.seq) for the "All posts" filter;
    - a side-by-side view on laptops.
  - **What it tracks.** A few alerts a day: the notification plan's X budget assumes 2-5 MEDIUM or HIGH alerts daily. They arrive 2-4 minutes after the post and are pushed to Telegram, which is where people get real time.
  - **Load.** The plan's load estimate is "inference, not measured" (Budget), and it fails on the launch the growth plan is aiming for. A Show HN or a viral X thread means thousands of tabs, each polling every 5 s, uncached.
  - **The rate limiter fails under that load.**
    - Today's limiter keys on slowapi's `get_ipaddr`, which looks for an `X_FORWARDED_FOR` header with underscores that proxies never send (api/rate_limit.py:10).
    - It then falls back to the connecting address. uvicorn is started without a forwarded-allow-ips setting (railway.json:78), so behind Railway's proxy that address is the proxy's.
    - Every visitor therefore shares one bucket and the whole site returns 429 at once. Any client can also set that underscore header to choose its own bucket.
  - **Recommendation:**
    - While the page is visible, poll the first page of /api/v1/alerts every 30-60 s and replace the list. This removes the client cursor logic, the new bar and the tab counter.
    - Cache that response for the polling interval: a few seconds in-process, and `Cache-Control: public` if a CDN or Cloudflare proxy sits in front. One copy then answers every visitor.
    - Drop the "All posts" filter. Signals stay reachable by URL, ticker page and search, and the engine can drop signals.seq.
    - Fix the limiter's client key before D1. Verify on Railway whether FORWARDED_ALLOW_IPS is set.
    - Drop the side-by-side view until someone asks for it.

- **[major] scope**: The public Status page duplicates operator tools and exposes the feed sources.
  - **What D2 builds.** A public Status page and /api/v1/status/engine, showing feeds by mirror, lag percentiles, job runs and outlet delivery. The MCP engine_status tool reads the same endpoint (Notifications, For agents).
  - **The operator already has this.** `python -m engine status`, a health endpoint, and notify_operator messages on every failure (Engine A; Notifications, Operator notices).
  - **The public already has this.** Each signal page shows that post's timing, which is the latency evidence followers care about.
  - **What the page exposes.** Naming each mirror and "how often each was first" tells everyone the product runs on CNN's feed, whose terms reportedly bar commercial use (Growth, Legal and data rules; unverified). It also shows anyone who wants to disrupt the feed exactly where to aim.
  - **Recommendation:** Cut D2 and /api/v1/status/engine. Drive the header dot for late feeds from one boolean in an existing response. On signal pages, show "first seen" times without naming the feed. Ask the notification planner to drop engine_status from N4, or point it at the engine's existing health endpoint. Revisit only if paying customers ever need a status page.

## Gaps

- **[major] compatibility**: Links in channel posts are permanent, but the receipt and the URL scheme are not settled.
  - **The Telegram post is not a receipt.** The growth plan makes "each signal links to its Telegram post as the receipt" and requires canonical links. But channel posts are "edited in place as each day's results arrive" (Notifications, Outlets). The link proves where a call went, not what it said first.
  - **Two ids for one page.** /s/<signal id> uses ids like `truth_social:<status id>`, with a colon in the path (Notifications, Dashboard touchpoints, Deep links). alerts.public_id is "a short public id for share links" (Engine F).
  - **Links cannot change later.** Every channel post from PR 8 on embeds a link that cannot be changed afterwards, and the domain is only being registered now (Growth, Jobs for you).
  - **Recommendation:**
    - Before N1's first channel post in the shadow week, fix one canonical URL: either public_id or a signal id without the colon.
    - Have the domain live by PR 8, so no post ever links to *.up.railway.app.
    - On the signal page, show revision 1 from alert_revisions as the receipt: its seq, time and text as first sent. Label the Telegram link "sent here".
    - Suggest the notification planner post results as replies rather than edits, so the channel post is itself a receipt.

- **[minor] compatibility**: The result windows and benchmark are hardcoded for stocks, but crypto works differently.
  - **Stock-only assumptions in this doc.** The "Result windows" row hardcodes 5 min, 15 min, 1 hour, close, and 1, 3 and 5 days, "against SPY". The header market clock and the "market open" verdict assume stock hours, and the growth plan's chart is "ticker vs SPY".
  - **How crypto differs.** Crypto is now the engine's default (Engine E, F):
    - Coins use 5 min, 15 min, 1, 4 and 24 hours, and 3 and 7 days, against BTC; BTC itself is judged only against random times.
    - They trade around the clock.
    - Their outcome updates come after 1, 4 and 24 hours and 3 and 7 days.
  - **The Evidence table breaks.** Its "one column per window" layout cannot hold both window sets.
  - **Recommendation:** Take the windows, benchmark and calendar from each instrument in the API response, and render whatever comes back. Group evidence by asset class. The site hardcodes no window list and no "SPY" label.

## Questions

- **[minor] scope**: Who is the site's main user now? The doc was written for Chris as a trader watching the screen ("show it within seconds"). The growth plan's audience is retail followers, journalists and developers, who arrive from links and search and want the graded record. The answer decides whether the live list belongs on the home page at all, or whether the home page should be the record's headline plus the latest calls.

## Observations

- **[info] scope**: The restated problem, without solution terms: let anyone see each call the engine makes, the evidence behind it and how it turned out against the benchmark, misses included, so that the record earns followers' trust; and make a link to any call show as a readable card.
  - **The from-scratch build:** a server-rendered page per call, and one record/report page with ticker and topic permalinks, refreshed every minute. Operator health stays in the engine's CLI and notices.
  - **Where the plan diverges from it:** the single-page app with a second meta renderer, the 5 s change-log client, the public status page and the minute price charts, all covered above.
  - **Smaller cuts once those are taken:**
    - The evidence-layer switch can show the live and keyword layers, and keep the LLM-backfill layer in the report only, since it is the layer with look-ahead risk (Engine E).
    - Per-page code-splitting and the optional temporary Railway service on D1's branch during the shadow week add machinery for little gain.
    - About 40% of the 36,580 imported posts are retruths or media-only (Engine B). Only signals with a call should be indexable or listed in the sitemap.
