# Architect: will the growth plan's hookups work as written?

Reviewer 1 of 5, run inline (no subagents). Source: source-growth.md (doc rev 14) plus notes/growth-plan.md; hookups checked against plans/engine.md, plans/dashboard.txt, plans/notifications.txt and the notes.

## A1. The "receipt" is an editable message (major)
- Growth wants each signal page to link "to its Telegram post as the receipt" (source-growth.md:291-292). The same plan's Telegram row says every alert is "edited in place as results come in" (source-growth.md:119-121), as N1 builds it (notifications.txt:87-90).
- A Telegram edit replaces the text. Readers see an "edited" mark but not the first version. So the post that is meant to prove the first call shows only its latest edit. Append-only `alert_revisions` (engine.md:169) proves nothing to an outsider, because the owner can drop the trigger.
- The plans also disagree on whether a public reader can get revision 1 back. notifications.txt:31-32 says "a reader that missed a change gets the alert as it stands", while ui-plan-hookups says the change feed may return several revisions.
- Fix, which also removes work: never edit an alert post. Results go out as one daily results post that links to the alerts (the growth plan already wants "each day's results"), or as a reply to the alert. N1 then drops edit-in-place, the message-id bookkeeping for edits and the per-revision Telegram edits. Expose `/api/v1/alerts/{id}/revisions` (or promise that `changes?after=0` returns every revision) so a first call can be checked.

## A2. Branch A's "per-destination delay already does this" is false (major)
- source-growth.md:187-189 says the paid head start comes free from the notification plan's per-destination delay. That delay applies only to push destinations.
- Reads stay public and unauthenticated: the alerts API, the `/changes` feed polled every 5 s, the dashboard and MCP (notifications.txt:144-147, 389-391). Anyone polling `/api/v1/alerts/changes` would get the paid tier's head start for free.
- Branch A therefore also needs a read-time delay on every public endpoint, plus an authenticated paid read path: keys tied to entitlements, Whop webhooks and the users/entitlements tables. That is a real build, not a filter tweak. (This is one more reason to drop branch A; see Skeptic S2.)

## A3. The derived-numbers rule misses the public alert object, and its reason does not hold (major)
- The change list says "applies the derived-numbers rule to everything public". But engine PR 10 puts "the entry price and time used" into a new alert revision (engine.md:173), and N1 carries it in the first result (notifications.txt:169-170). Revisions are the public alert object (API, webhooks, MCP, Telegram), so the entry price leaks there. The other leaks were found earlier and are not re-derived here: `/api/v1/bars`, `/prices/latest`, and the entry-price column in the Evidence drill-down (dashboard.txt:151-152). The growth plan fixes the policy but does not name these surfaces, so each planner can read "everything public" differently.
- The reason given for hiding the entry price is that "% series plus one price rebuilds prices" (source-growth.md:253-256). That argument is weak: the entry time is public, and any free quote gives the price at that minute. Hiding the entry price protects little. What matters is whether Alpaca allows publishing derived data at all, above all a 1-minute "% since the post" chart (dashboard.txt:125-127), which re-encodes Alpaca's minute bars almost one for one.
- Fix: name the fields that must never appear in `alert.v1`, `/signals`, `/evidence` or `/bars`. Until Alpaca answers in writing, show window results (5m, 15m, 1h, close, 1/3/5d) and drop the minute-level % chart from public pages.

## A4. Public post text: the site becomes a free real-time Trump feed (critical)
- Growth says "we never sell Trump's posts. We quote a line and link to the original" (source-growth.md:244).
- The dashboard does something else. The live list has an "All posts" filter of every post (dashboard.txt:109-110). The signal page shows the post's full text (dashboard.txt:122), served by the public `/api/v1/signals` (dashboard.txt:210-217) with a 5-second change cursor. The engine keeps the mirror's raw payload on the row (engine.md:126).
- Together these republish, in near real time and in full, data compiled by CNN and trumpstruth.org. That is the product TMTG sells for $60-100k a month. The growth change list does not touch it.
- The schemas freeze early: `alert.v1` is published at N2 and the signals API ships in D1, both before cutover. Narrowing them later is a breaking change.
- Fix: decide before N2 and D1 that public surfaces carry an excerpt (first line, capped length), the post time and a link to the original, and never the raw payload. "All posts" can list excerpts or leave the public site.

## A5. Attribution machinery needs an inbound Telegram path (cut)
- The change list asks for "a named Telegram invite link per outlet" and a daily audience count that notifications owns (source-growth.md:303-305).
- From memory of the Bot API (verify): the ChatInviteLink object has no joined-count field. Counting joins per link means receiving `chat_member` updates, which in turn means an update consumer (getUpdates or a webhook) inside the engine process. N1 only sends.
- People who join through the public @username carry no invite link, so most joins would show up as unattributed anyway.
- The Telegram app already shows admins "N joined" for each invite link.
- Cut `audience_daily` and the attribution code. Chris reads the counts by hand weekly, or reads them once at the gate.

## A6. Other pushed changes and their build cost
- Server-rendered preview images per signal, ticker, topic, record and report page: per-page meta tags injected by FastAPI into the SPA shell are cheap, but per-page image rendering needs a renderer (Pillow, a headless browser or Satori) in the web service. Keep titles and descriptions plus one static image.
- Ticker pages, topic pages and a report page are three new page types on top of the dashboard's five, which earlier rounds already said were too many. Fold ticker and topic views into `/evidence?ticker=...&topic=...` with server-rendered titles. Publish the report as a static page built from the report file the engine already writes (engine.md:164), so the engine needs no "export for a report page".
- The MCP Registry listing under our domain needs DNS-based namespace verification (verify). It is cheap, but only useful once N4 exists. Hold it.
- Moving the site to our domain on cutover night stacks a DNS change on top of the cutover. Do it before cutover (both URLs serve the old site) or after.

## Where growth meets earlier findings (not re-derived)
- Rate limiter keyed on Railway's proxy: growth makes this worse. The Show HN, Reddit and reporters day is the traffic spike, and every visitor would share one bucket. Fix before launch step 4.
- Raw prices on public endpoints: growth fixes the policy but leaves the alert object (A3).
