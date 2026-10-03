# Counter-Planner: a serious alternative on opposite assumptions

Reviewer 5 of 5 (inline; had read the four notes above).

## The plan's load-bearing assumptions, inverted

| The plan assumes | The counter-plan assumes |
| --- | --- |
| The site is a live trading surface; seconds matter | Telegram is the live surface; the site is the public record and the shop window |
| A client-rendered React app, reading only the JSON API | Server-rendered HTML pages, built from the same query functions that back the JSON API |
| Minute charts with a charting library | A few computed numbers per window and a small server-drawn % line, or none |
| Six pages now, growth's pages folded in later | Four pages, designed for search and sharing from day one |
| D1 ships with the cutover; the cutover waits for it | The site ships on its own schedule; the old site can be stale for days |

## The counter-plan: "the record site"

- **Pages (4 templates).** Home: the pitch line, the graded record summary, the latest calls (a 20-line script polls /api/v1/alerts/changes every 15 s and inserts rows), follow buttons with ?ref. Signal /s/<public_id>: the call as first sent (the first revision verbatim, with its time), an excerpt of the post with a link to the original, the move since the post vs its benchmark at each window, the grade once it exists, and the layer label on pre-cutover posts. Ticker /t/<slug>: every call on that instrument with results, plus its backtest rows; this is the Evidence drill-down. Record /record: track record, the backtest report (Evidence), methodology, disclaimer, how to connect (Telegram, X, API, MCP).
- **Rendering.** FastAPI + Jinja templates, each page cached 60 s, titles, descriptions, canonical links and one static preview image per page type in the HTML itself; a sitemap of alerts and ticker pages only. Link previews and search indexing work without any extra machinery.
- **API.** /api/v1 stays the agent contract and is owned by one plan (notifications), with the dashboard's queries as plain functions the templates and the JSON routes both call, so "an agent can read anything on screen" holds by construction.
- **No public prices at all.** No bars or latest-price endpoint; the signal page shows alert_progress's move vs benchmark and the window results. The display-rights question shrinks to "may we publish computed % moves", one question for Alpaca.
- **Build.** R1 (record site with home, signal, ticker, About; deletes today's frontend) merges in its own sitting, before or after the cutover. R2 (track record and report sections) merges when grading lands, and the report section when engine PR 10 does. No Node build in the Python service, no Vitest, no Playwright; template tests with the FastAPI test client and a DB built from the engine's migrations.

## What it gets right that the plan does not

- Growth's discovery and sharing needs (previews, canonical links, sitemap, indexable ticker pages) are native, not bolted on.
- Roughly half the code, one language, one CI job, and no frontend toolchain to keep current.
- No raw-price surface to police; the licence risk is limited to computed numbers.
- The cutover no longer waits on the dashboard.

## What it sacrifices

- An app-like feel: instant filter switches, a split view, an interactive minute chart with zoom and crosshair.
- Chris's approved stack decision ("React, TypeScript and Vite ... chosen for the live list and the charts").
- Some design polish; server templates make rich interactions harder to add later.

## Synthesis I would actually recommend

Keep the plan's information design (signal page sections minus the "left" headline, the evidence rule, the labelled layers, the live-only record) and its JSON-first principle. Take from the counter-plan: four pages instead of six-plus-growth's-five, no public price endpoints, per-URL HTML meta in the catch-all (a server-rendered shell even if React hydrates it), the site off the cutover's critical path, and one owner for /api/v1. Whether to go fully server-rendered is a 10-minute decision for Chris, not a defect; the SPA is acceptable only if the catch-all serves per-URL meta from D1.
