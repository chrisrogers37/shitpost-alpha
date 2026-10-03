---
lens: cost-benefit
worker: cost-benefit
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-engine.md
started: 2026-10-01T01:00:41Z
completed: 2026-10-01T01:08:30Z
status: completed
severity: major
---

## Risks

- **[major] scope**: PR 6 combines the alert backbone with a live-price subsystem. The live-price half has low ROI and sits on the cutover's critical path. Per Build order row 6, F "Live prices" and Data model "Historical and live prices", PR 6 adds:
  - two Alpaca WebSocket streams, with a 30-symbol rotation on the stock side;
  - the `latest_prices` table;
  - 1-minute bars flagged provisional, plus an evening job that replaces them with consolidated bars;
  - an `alert_progress` recompute every minute, around the clock for crypto.

  Cost is L on its own, with new failure modes (stream drops, resubscribes). Network and credentials says these streams are only "tested from recordings in the sandbox and run only on Railway", so they cannot be verified before production. The benefit is one "move so far" panel on the dashboard's signal page. The shadow week, the cutover and the evidence alerts need none of it, and Telegram edits results once a day (notifications plan, "Updates"). The one hookup that would justify streams is `/api/v1/prices/latest`, polled every 5 s (notes/ui-plan-hookups.md, added 00:05). It serves raw prices, which the derived-numbers rule (growth "Prices", agreed 00:35) bars from public view, so `latest_prices` has no allowed public reader. Yet N1, PR 7 and PR 8 all wait on PR 6 (H; Build order).
  - **Recommendation:**
    - Cut PR 6 down to `alerts`, `alert_revisions`, the cursor, the wake hook and worker registration.
    - Move "move so far" to a PR after the cutover, or into PR 10. Build it first as an on-demand calculation: Alpaca REST minute bars for alerts from the last 24 to 72 hours, cached about 60 s. Write it to `alert_progress` only if a page needs a stored table.
    - Cut `latest_prices`, the provisional flag and the evening consolidation job.
    - Drop `/api/v1/prices/latest` from the dashboard hookup.
    - Add streams later only if measured REST freshness falls short. Before that PR, verify that Alpaca's free REST plan returns current-minute IEX bars. That is an external fact I could not check.

- **[major] scope**: PR 3 builds four price adapters and a display-rights registry for one provider Chris has already chosen. Per Decisions "Price data" and C, PR 3 builds:
  - Alpaca for stocks and Alpaca for crypto;
  - a yfinance fallback, which C presents as the option "if you would rather not open an account", though the Status line says Chris confirmed Alpaca;
  - Coinbase public candles;
  - the `price_sources` table with display rights;
  - three bar storage tiers;
  - a "forward record" evening job.

  The cost comes from two dimensions:
  - **Maintenance.** Each fallback is an adapter with tests that never runs unless something breaks.
  - **Dependencies.** Network and credentials adds Coinbase's host "only if it is needed". Yet PR 3's "Verified by" compares Alpaca's crypto bars with Coinbase's, a check the sandbox cannot run without that host.

  The benefit is small:
  - The forward record exists "so later checks never depend on a source's lookback". That guard dates from yfinance; Alpaca's minute history back to 2016 makes it redundant.
  - Until the paid gate, every `price_sources` row would hold the same value, "none" (growth "Public prices and charts").
  - The hourly tier ("hourly bars for 2 years") has no named reader. Research history is kept as files, and pages use alert-window minute bars and daily bars.
  - **Recommendation:**
    - Make PR 3 one Alpaca client behind the provider interface; stocks and crypto share its host and key. Add instruments and aliases, the calendar, daily bars, and per-alert-window minute bars, fetched and cached.
    - Use yfinance only in a cross-check script for PR 3's verification, flagged for removal, not as a production adapter.
    - Build Coinbase only if Alpaca crypto fails PR 3's first-use check. Remove the Coinbase comparison from "Verified by", or add the host explicitly.
    - Replace `price_sources` with a `source` column on bars and one API rule: no raw prices in public responses. Create the table at the gate, when a licensed source exists.
    - Cut the forward-record job and the hourly tier.

- **[major] scope**: Crypto is built into the live path before there is any evidence that posts move coins. The case for crypto (Data model, "Why crypto") is that 69% of posts land outside US regular hours. That is the share of all posts, not of posts that make a crypto call, and the plan does not measure how many posts name or move a coin. Crypto spreads cost across five PRs:
  - PR 3: an adapter, the Coinbase fallback and a 24/7 calendar.
  - PR 5: seven more windows and the BTC benchmark, with BTC itself judged against random times only.
  - PR 6: a second stream and around-the-clock `alert_progress`.
  - PR 10: five outcome revisions per crypto alert (1, 4 and 24 hours, 3 and 7 days).
  - Growth: crypto pages.

  "Any coin a post names" (Decisions, "What you would trade") adds a long tail of thinly traded coins with short histories. The benefit stays speculative until backtested, and Chris's crypto card is still open (Status line).
  - **Recommendation:** Put the cheaper option on the open card:
    - Keep the cheap data-model columns now: `asset_class`, calendar and benchmark.
    - In PR 5, backtest BTC, ETH and SOL from Alpaca's crypto history, which needs no key, as research files only.
    - Switch on live crypto (stream, progress, crypto outcome schedule, crypto pages) only if PR 5 shows a crypto edge after costs. PR 12 already uses the same kind of gate.
    - Hold "any coin a post names" until then.

    Growth loses nothing. It courts crypto traders from the public launch at PR 10, which comes after this gate.

- **[major] scope**: Importing the old live record (PR 8, PR 9) is negative ROI, and it gives the plans two meanings of "live". Workstream E makes "predictions production made in real time, from your one read-only export" one of three evidence layers, and G imports them at cutover. The plan's own Known bugs list says those predictions came from a system that:
  - dropped the analysis prompt (#217);
  - stored unparseable answers as completed (#218);
  - sent its alerts as "neutral";
  - stored the analysis time in `post_timestamp`.

  The old repo's CHANGELOG.md:97 shows the ensemble was opt-in and off by default, so the record mixes several models and prompts. The old predictions carry none of the new topics, so they cannot fill the topic-by-ticker evidence that alerts quote unless they are re-extracted. Meanwhile, the dashboard's /record covers "alerts since the cutover", and growth says "the public record starts that day". The engine's live layer would therefore disagree with the public track record. The cost is an export job for Chris, mapping code, an import step at the riskiest moment (cutover), and a layer that can set tiers. The benefit to the new engine is close to none.
  - **Recommendation:**
    - Keep the export as a file in the project folder. The mission counts old predictions as data, and a file is enough for a research comparison.
    - Do not import it into engine tables, and do not let it set tiers or the tradeable flag. Drop the import from PR 8 and the live-record half of PR 9.
    - Define the live layer as engine alerts from cutover, matching /record.
    - For subscriber carry-over, only the active chat IDs are needed. The old CLI already prints them (`notifications/__main__.py:171`, `list-subscribers`).

- **[major] scope**: The plan's highest-value live step is gated on three PRs from two other plans, and one of those PRs keeps growing. That step is PR 8: it retires the 12 cron services, verified in railway.json, retires ScrapeCreators and cuts latency.
  - H and G say "the new dashboard merges right after PR 8", and the dashboard plan says "the engine plan's cutover waits for this plan's first PR".
  - D1 is a full React rewrite: live list, signal page, link previews, charts, Vitest and Playwright. It waits on engine PRs 2, 3, 4 and 6 and on N2.
  - The growth plan's list then adds to the dashboard: our own domain, server-rendered previews, and ticker, topic and report pages. It also says "Cutover: soft launch … the site moves to our domain".

  Every addition that lands in D1 delays the cutover. That keeps the 12 old services and ScrapeCreators' roughly $17 to $20 a month running longer, and it delays the engine's real-world proof.
  - **Recommendation:**
    - Write a minimum D1 into PR 8's gate: the live list and the signal page, both reading /api/v1, and nothing from the growth plan's list.
    - Move the domain change, server-rendered previews and new pages to later D PRs that land before the public launch (PR 10).
    - Say in G that cutover may proceed with the old site stale for a few days if D1 slips. This is before launch, and a stale read-only page harms nothing (inference).

    After this change, N1 is the only PR from another plan that cutover strictly needs, because N2 is on the path only because D1 reads it.

## Gaps

- **[minor] scope**: PR 12 (second source) is a cut candidate: nothing depends on it, its value is undefined, and the room it stands for already exists.
  - The data model makes "a new source … a row and an adapter" (Data model; B "Adding a source"). That already meets the mission's "room for others".
  - PR 12 picks official feeds (White House, Fed, USTR) and needs new hosts "confirmed when the PR is written".
  - Official releases are scheduled and widely watched, so the speed gap the plan concedes on Trump posts ("Trading firms buy Truth Social's millisecond feed") is probably wider there. This is inference; check it before planning PR 12.
  - Keeping PR 12 holds an open decision for Chris ("Still open: the second source") and an approval checkbox, with no build value now.
  - **Recommendation:** Remove PR 12 and its checkbox from this plan, and keep the sources, feeds and adapter design as the room. After PR 10 shows an edge, plan the second source separately, with its own latency and edge check.

- **[minor] scope**: Table by table, several engine tables and columns have no consumer now, and one contradicts the plan's own rule.
  - `slug_redirects`: C says a slug "never changes once made, even when the ticker does", so there is never an old slug to redirect.
  - `signals.seq`: a second change cursor "for the site's live list". The dashboard's live list follows `/api/v1/alerts/changes`, and "All posts" can page by `first_seen_at`.
  - `feed_health` "records every poll": CNN every 15 s plus RSS every 60 s is about 7,200 rows a day, about 2.6 million a year. All of it serves a status view that needs last poll, last success and lag percentiles.
  - App tables `audience_daily`, `users` and `entitlements` (notes/plan-stage.md, notes/ui-plan-hookups.md) serve a paid gate that is months away. Until then, the gate-3 follower count can be read from Telegram and X by hand.
  - **Recommendation:**
    - Cut `slug_redirects`, and add it the first time a slug must change.
    - Cut `signals.seq` unless the dashboard commits to a live-updating "All posts" view.
    - Store feed-health state changes plus per-feed counters, or prune per-poll rows after 7 days.
    - Create no app table before the PR that first writes it, and no `users` or `entitlements` before the gate.

    With the first two Risks (`latest_prices`, `price_sources`), this removes three of the 22 named engine tables and defers a fourth (`alert_progress`), without losing any hookup a current page uses.

- **[minor] scope**: Backtest v1 (PR 5) is the plan's most important deliverable and the growth plan's public launch (growth "Launch", step 4), but it does too much for a first pass. Workstream E specifies:
  - for stocks, 7 windows plus a pre-market entry "second view", which doubles the stock rows;
  - for crypto, 7 more windows;
  - beta estimated from 120 prior days;
  - a placebo of 100 random times per signal, "matched on weekday and hour";
  - a permutation p-value, Benjamini-Hochberg correction and day-block resampling;
  - results at two cost levels.

  The 100-random-times placebo is the reason the plan "needs years of minute bars for every ticker, potentially hundreds of millions of rows" (Data model, "Storage tiers"). That in turn requires a separate file workspace and a long minute-bar download. Every extra window, view and benchmark model also enlarges the Benjamini-Hochberg family, which makes any one edge harder to show.
  - **Recommendation:**
    - Run v1 with market-adjusted returns (instrument minus benchmark, beta 1), regular-session entry only, and a short window set, for example 15 min, 1 h, close, 1 d and 5 d.
    - Draw the placebo from the same ticker's minutes at the same time of day, within about ±20 trading days of each post. That needs only bars near post dates, which are fetched anyway, and it also controls for market regime.
    - Keep Wilson intervals, Benjamini-Hochberg and day clustering. They are cheap once the rows exist, and they are what make the evidence honest.
    - Add beta, the pre-market view and more windows in v2, and only where v1 shows signal.
    - Have the methodology lens confirm the local placebo is equivalent.

- **[minor] scope**: The shadow week's daily comparison is throwaway code with a hidden dependency on the production database. G says it "lists every post each system saw, when, and what each alerted". That needs the old database, but A says "New code never reads or writes the old tables", and the engine service would need the old production URL. The "what each alerted" half compares against alerts the plan itself calls broken ("Event-path alerts go out as 'neutral'"). The code lives for one week, and Chris's rule is that test code is "thinly scoped and flagged for removal".
  - **Recommendation:**
    - Limit the comparison to coverage and timing: did each system see each post, and how many minutes after posting.
    - Write it as a one-off script outside `engine/`, run read-only against both databases by Chris or from the old web service, and delete it in PR 11.
    - The engine's `signal_sightings` already gives per-feed lag, so the script needs only the old system's post IDs and times.

- **[minor] scope**: The $40 LLM backfill (E; Budget row 2) is the largest optional spend, and the plan spends it in one run. Its value depends on one thing: the fast model beating the keyword baseline on posts after its training cutoff. A related ambiguity: until PR 9, the only historical evidence is the keyword layer. An alert decided by the LLM would quote topic-by-ticker evidence produced by a different extractor (D; E "Output"; F "Evidence").
  - **Recommendation:**
    - Stage PR 9. First run a slice of about 10 to 15% of the post-cutoff posts, a few dollars, and compare it with the keyword layer on the same posts. Spend the rest of the cap only if the LLM adds lift.
    - State in F which layer an alert's evidence comes from. If the slice shows no lift, alerts quote the keyword layer and the model writes only the one-line reason.

## Observations

- **[info] scope**: ROI for each PR. Sizes are relative: as written → after the cuts above.
  - **PR 1 Foundation (M): Critical.** Keep. CI pays off most, because the old code has no CI and every merge redeploys 12 services (railway.json lists 12).
  - **PR 2 Feeds and signals (M): Critical.** It replaces the paid scraper. Keep, and trim `feed_health`.
  - **PR 3 Market data (L → M): Moderate as written, High once trimmed** (one Alpaca adapter).
  - **PR 4 Extraction (M): High.** Keep. Its replay harness also verifies PRs 6 and 7.
  - **PR 5 Backtest v1 (L → M): Critical.** It is mission goal 3 and the growth launch. Trim the windows, views and placebo.
  - **PR 6 Alerts (L → M): Critical for the core.** The streams and progress half is Low and sits on the critical path; split it out.
  - **PR 7 Shadow week (S-M): High.** Cheap insurance. The comparison becomes a script.
  - **PR 8 Cutover (M → S-M): Critical.** Drop the live-record import and decouple it from D1.
  - **PR 9 Backtest v2 (M): Moderate.** Stage the backfill and drop the live-record export.
  - **PR 10 Evidence alerts (M): Critical.** It is mission goal 4.
  - **PR 11 Removal (S): High.** Keep.
  - **PR 12 Second source (M): Low and speculative.** Cut.
  - The growth plan asks the engine to "export the backtest report's numbers". No new export is needed: serve the report page from `backtest_summary` through the existing `/api/v1/evidence`, or publish PR 5's report file as it is.

- **[info] scope**: Most of the plan's value sits in three PRs: PR 2 (free mirrors, minutes faster), PR 5 (the evidence, and the growth launch) and PR 10 (evidence in alerts). PRs 7, 8 and 11 are migration overhead, and cheap enough to keep.
  - **Binding constraint.** Money is not it: all four plans total about $155 of the $250 (growth "Budget"), and the cuts above save little cash. The binding constraints are engineering scope and Chris's merge load: 12 engine, 6 notification and 4 dashboard PRs, 22 merges before growth's extras.
  - **Effect of the cuts.** They remove PR 12, shrink PRs 3, 5, 6 and 8, and pull the cutover forward. An earlier cutover ends ScrapeCreators' roughly $17 to $20 a month and the 12 old services sooner.
  - **Tables to keep:**
    - `sources`, `feeds`, `feed_health` (trimmed)
    - `signals`, `signal_sightings`
    - `topics`, `extractions`, `signal_mentions`
    - `instruments`, `instrument_aliases`
    - `market_bars` (daily bars plus alert windows)
    - `backtest_runs`, `backtest_rows`, `backtest_summary`
    - `alerts`, and `alert_revisions` with its insert-only trigger, which has high ROI because three plans build on it
    - `job_runs`, `engine_meta`

- **[info] dependencies**: H "App schema" and notes/plan-stage.md put both schemas in one Alembic history, with migrations from three planners.
  - Every app-table change becomes an engine deploy, because migrations run at engine start-up and the web role cannot change the schema.
  - Parallel PRs (N1, N2, N3 and the D PRs) will collide on the Alembic head.

  This cost is acceptable at this size if the plan says how it is handled. One option is an Alembic branch label per schema, with `depends_on` for foreign keys that cross schemas. The other is a rule that app migrations rebase onto the engine head and merge in PR order.
