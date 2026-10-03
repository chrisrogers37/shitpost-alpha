---
lens: first-principles
worker: first-principles
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-engine.md
started: 2026-10-01T01:00:34Z
completed: 2026-10-01T01:09:10Z
status: completed
severity: critical
---

## Blockers

- **[critical] scope**: The plan answers its deciding question last. With the solution taken out, the problem is: "find out whether Trump's posts carry a price move that can still be traded a few minutes after they appear and, if they do, tell people within minutes with the proof attached" (mission goals 3 and 4, plus the added growth goal). Everything else depends on that answer: the alert machinery, live prices, crypto, slugs, display rights and the public pages. Its shape also depends on where the edge shows up, within 15 minutes or over days. The growth plan already makes the paid product depend on exactly this. Yet the plan's own stop rule ("if nothing beats the placebo after costs, we stop and rethink before spending more", Build order > Gates) sits at PR 10. By then PRs 1-9, N1, N2, D1 and the cutover are done. The LLM evidence arrives only at PR 9, after cutover. The old live record is the only existing LLM evidence that is free of look-ahead, and it costs $0, but the plan uses it only from the cutover on (G. Rollout; PR 8 and 9 rows). The keyword run in PR 5 comes earlier, but it measures keyword rules, which do not make the alerts.
  - **Recommendation:** Move the gate to the front.
    1. Ask Chris for the read-only live-record export now. It should hold predictions only; subscriber chat ids stay out of the sandbox.
    2. Have PR 5 run the keyword and live-record layers over the archive and REST bars ($0, sandbox). Chris reads that report (call it gate 0) before PR 6 is written.
    3. Size PR 6 and everything after it by what gate 0 shows: which windows (this decides streams and live progress, finding 2), which asset classes (finding 4) and which evidence unit (finding 5).
    4. Until then, build only the minimal live path: pollers, save, extract, alert, and N1's Telegram outlet. Deploy PR 2's pollers on their own to Railway once it merges, so weeks of real mirror data build up instead of one 24-hour probe and one shadow week. Retire the probe service at the same time, and check that this fits the $40 Railway cap.
    5. If gate 0 looks promising, run the capped LLM backfill as soon as that Railway service exists, before the cutover.

## Risks

- **[major] scope**: Live price streams, `latest_prices`, `alert_progress` and the provisional-bar lifecycle serve a display the licence may forbid, for an edge window nobody has measured. F. Live prices and Data model > Historical and live prices add:
  - two Alpaca WebSockets, with stocks capped at 30 symbols, so a rotation rule is needed
  - a recompute every minute while markets are open
  - provisional IEX-only bars, and an evening job that replaces them with consolidated ones

  Their only consumer is the "move so far" line on the dashboard signal page and in notification messages. Grading does not need them: outcomes come from bars fetched after each window closes (C. Forward record; F. Outcome updates). The growth plan concedes speed ("We can't win on speed"). The plan's own latency table shows mirror lag of 1.6 to 17 minutes, which outweighs anything the streams save. Each stream is also one more long-lived connection inside the single process, with reconnect and health handling of its own.
  - **Recommendation:** Cut streams, `latest_prices` and `alert_progress` from PR 6. Compute "move so far" on request from Alpaca's REST latest price or minute bars, cached for about 60 s, or show moves only when a window ends. Bring streams back only if gate 0 finds an edge inside the first hour and a source that allows display exists. Verify in PR 3 that the free plan's REST endpoints return a current IEX price (not checkable from here).

- **[major] architecture**: The data model is built for a multi-source, multi-asset, multi-outlet platform with paid tiers, not for the one-source product still being proved. The Data model lists about 22 engine tables and 4 to 6 app tables, with migrations from three planners in one history. Starting from a blank editor, v1 needs about a dozen: signals and sightings, extractions, mentions, instruments and aliases, bars, a backtest summary, alerts, outcomes, deliveries and job_runs. Several tables serve futures the plan itself puts behind gates:
  - `slug_redirects`: ticker renames are rare, and FB to META is the only example given.
  - `price_sources`, with display rights per source and an API check: the public rule is "none" for every source until growth gate 5, so this is a constant, not a table.
  - `latest_prices` and `alert_progress` (see finding 2).
  - one `feed_health` row per poll.

  `alerts` (mutable current state) and `alert_revisions` (an insert-only copy), written in one transaction, store the same thing twice. Readers already have to reconcile the two ("client keeps highest revision per alert_id", ui-plan-hookups note).
  - **Recommendation:** For PRs 1 to 8:
    - Cut `slug_redirects`, `price_sources` (make it a code constant: no raw prices in public), `latest_prices` and `alert_progress`.
    - Cut per-poll `feed_health` rows. Record state changes and an hourly summary instead.
    - Store each alert once. Either keep the insert-only `alert_revisions` and make `alerts` a view of each alert's latest revision, or store an immutable call row plus insert-only outcome rows.
    - Add each deferred table in the PR that first needs it. Adding a table later is a cheap migration; removing one that three plans read is not.

- **[major] scope**: Crypto adds a second asset class before the first has shown anything, and the evidence given for it measures timing, not effect. "69% of posts land outside US market hours" (Summary; Data model > Why crypto) says when posts land, not that they move coins. One thing is unstated and load-bearing: does a non-crypto post (tariffs at 11 pm) produce a BTC call, or only a post that names a coin?
  - If only posts that name a coin, the sample is a handful of posts and every crypto alert stays LOW (under 20 cases).
  - If any post, each call is an LLM guess with no evidence behind it yet.

  Either way, crypto doubles the design surface: a second set of windows (5 minutes to 7 days), a second benchmark rule (BTC, which is itself judged against random times only), a 24/7 calendar, a crypto stream, a Coinbase fallback adapter and host, a second entry rule, and outcome edits at any hour. Chris's crypto card is still open.
  - **Recommendation:** Recommend on the card that crypto goes into the backtest only, for now: BTC, ETH and SOL history from Alpaca or Coinbase, at $0, with a stated rule for which posts produce a coin call. Live crypto alerts, their windows, the stream and the fallback come only after gate 0 shows a crypto edge. The hookup fields (`asset_class`, `market_open`) can stay in alert.v1 as optional fields.

- **[major] scope**: The evidence grid is too fine for the sample, so "every alert carries evidence" will mostly read LOW. The unit is topic (8 to 12, plus "other") × ticker (hundreds) × window (7) × entry view (2) × cost level (2) × evidence layer (3) (E. Unit, Statistics, Three evidence layers). Benjamini-Hochberg runs across all of it, and the tier is LOW under 20 cases (F. Evidence). There are 21,862 text posts, only some name a company, and the LLM layer is cut further to posts after the model's training cutoff. Most topic × ticker cells will hold a handful of cases, and correcting across thousands of cells leaves almost no power for any of them. The placebo design (100 random times per signal, on minute bars) is what produces the "potentially hundreds of millions of rows" and forces a second, file-based research store (Data model > Storage tiers).
  - **Recommendation:**
    - In PR 4, count cases per topic × ticker cell from the free keyword run before fixing the evidence unit for alerts. Alerts should quote the coarsest unit that clears 20 cases, for example topic × direction against the benchmark, or topic × index ETF.
    - Pre-register a short list of primary hypotheses (about 10 to 20 cells) for the gate decision, and label everything else exploratory.
    - Compute the placebo once per instrument, as a matched weekday-and-hour distribution of abnormal returns reused across signals, instead of 100 fetches per signal. That removes most of the bar volume and probably the separate file store.

- **[major] dependencies**: The scraper is not "our own", and its two sources are neither independent nor cleared for the money goal. Mission goal 1 asks for "our own free scraper". The plan reads two third-party mirrors (Decisions > Scraper) and cancels ScrapeCreators with "no paid fallback" (Summary; B. Feed health). Both mirrors scrape Truth Social themselves, so one TMTG block can take both down at once. TMTG says it will add friction for scrapers (truth-social-sourcing note), and the Risks table's "parser fix" does not undo a block. The growth plan says the CNN live feed's terms bar commercial use and that trumpstruth states no reuse terms (growth.txt, Legal and data rules; partly unverified), which collides with the paid tier. Polling trumpstruth every 60 s with a cache-buster deliberately bypasses a small site's CDN, and its lag on the measured posts was 3.2 to 17 minutes, so polling that often buys little.
  - **Recommendation:**
    - Before PR 2 merges, verify the ix.cnn.io feed's terms and record whether a paid product may rely on it.
    - Lengthen trumpstruth's uncached poll interval, or confirm that the site tolerates one uncached request every 60 s.
    - Before ScrapeCreators is cancelled (G. Removal), have Chris choose a fallback for a block that hits both mirrors at once: ScrapeCreators month to month, the direct read the probe found working, or accepting the outage. The choice should be made on purpose, not by default.

- **[major] compatibility**: The no-raw-price rule leaks by construction, and the "derived numbers" it relies on are unverified. The Data model says the public site "leaves out the raw entry price", but the entry price still reaches public outputs:
  - F. Outcome updates and the H table (Alert updates) put "the entry price and time used" into alert revisions.
  - The notification plan serves each alert "whole" on the public, keyless `/api/v1/alerts` and `/alerts/changes`.
  - The dashboard's Evidence rows list "entry price".
  - The ui-plan-hookups note adds a public `/api/v1/prices/latest`, polled every 5 s.

  The web role can read every engine table, so one endpoint bug exposes prices. Separately, a 1-minute "% since the post" series plus any public reference price, such as the prior close, rebuilds the bars just as an entry price would. Whether Alpaca's terms treat that as redistributing derived data is unverified; the plan flags this itself ("Whether even that is allowed is one of the stress test's checks").
  - **Recommendation:**
    - Keep raw prices out of `alert.v1` and out of everything the web role can read. Put entry prices and raw bars in tables not granted to WEB_DATABASE_URL, and expose only computed window outcomes: the % move, the move against the benchmark, and hit or miss.
    - Drop `/prices/latest` and raw `/bars` from the dashboard's contract.
    - Verify Alpaca's market-data terms on derived data before PR 3 merges and before D1 draws any minute-level % chart. Until then, publish window-end numbers only.

- **[major] architecture**: After cutover, the live alert path depends on every other plan's merges and migrations. The Risks row about redeploys protects only the old services. The engine lives in the same repo, so unless Railway is set up otherwise, every dashboard, notification or growth merge to main redeploys and restarts the engine. Migrations run at start-up and "it refuses to start if one fails" (A. Database). The app-schema tables of three plans keep "their migrations in the engine's one history" (H, App schema). A bad notification or growth migration, or two parallel branches that leave Alembic with two heads, therefore stops alerts. Third-party outlets also run in the same process: N3's webhooks to arbitrary URLs with 24-hour retries, N5 (X) and N6 (Pushover) (A. One process; notifications.txt "Inside the engine").
  - **Recommendation:**
    - Run migrations as a pre-deploy step, so a failed one blocks the deploy and leaves the running engine up. Add a CI check for a single Alembic head.
    - Limit the engine service's deploy triggers to `engine/`. Verify Railway's watch-path setting before PR 7.
    - Keep the live path (pollers, extract, alert, Telegram) in its own task group, with timeouts that slow third-party outlets cannot block. This respects the one-worker rule.

## Gaps

- **[major] data-integrity**: The evidence on an alert does not measure the method that made the alert. Calls come from "one fast model" (D). Evidence is "how often this topic moved this ticker", read from `backtest_summary`, with "one current run per layer" (E. Output; F. Evidence), and no rule says which layer an alert quotes. Each layer measures something different:
  - The keyword layer measures keyword rules.
  - The live record measures the old ensemble, which dropped its prompt (#217) and stored unparseable answers as completed (#218) (Known bugs).
  - Only the LLM backfill measures the fast model, and only if it uses the same model and prompt version as the live engine.

  A hit rate belongs to one method. Quoting another method's rate on an LLM call misstates confidence, which is the product.
  - **Recommendation:**
    - Key `backtest_summary` by layer and method version: model id, prompt version and topic-list version.
    - An alert quotes only the layer for its own method: the LLM backfill for model calls, the keyword layer for keyword fallbacks.
    - Pin a dated model id and freeze the prompt before the backfill runs. Any later prompt change marks the evidence stale until it is rerun.
    - Treat the old live record as the old system's track record. Filter out #218 rows on import, and never quote that record as evidence for new calls.

- **[major] architecture**: Where the backtest runs in production is undefined. PR 10 ships "backtest results in production, nightly refresh", but research history "stays as files in the backtest workspace" in the sandbox project folder (Decisions > Database; Data model > Storage tiers). Railway has no copy of those files, and the placebo needs years of minute bars. A CPU-heavy placebo or statistics pass inside the single asyncio process would block the event loop and break the live path's 30 s budget (Latency table).
  - **Recommendation:** State this in PR 10:
    - The full backtest (keyword and LLM layers) runs offline and is loaded into production as a versioned run.
    - The nightly job only appends live-layer outcomes and recomputes the live summary, which is small. It uses the per-instrument placebo distribution from finding 5, and it runs in a worker thread or subprocess with a time limit.

- **[major] scope**: The shadow week's daily comparison needs a data source the plan forbids, and it compares against a system known to be broken. G says "A daily comparison lists every post each system saw, when, and what each alerted". A says "New code never reads or writes the old tables". PR 8's gate is "a clean shadow week", with no stated criterion. "What each alerted" means little when the old system sends every alert as "neutral" and its ensemble drops the prompt (Known bugs).
  - **Recommendation:** Cut the old-versus-new comparison job. Judge the shadow period from the engine's own data:
    - each mirror against the union of both;
    - that union against the full CNN archive and trumpstruth's archive a day later, to find missed posts;
    - the logged post-to-alert timings against the target.

    Write the PR 8 gate as numbers, for example: zero missed text posts, p95 within target, and no signal stuck in a stage for more than N minutes.

- **[minor] dependencies**: The Neon cost line uses the wrong measure. The Budget says "The engine never polls its database, so it adds little load", but Neon bills compute by active time (verify). The engine writes `feed_health` on every poll (every 15 s for CNN, section B), plus minute bars and `alert_progress` every minute, so the database never idles. Whether this costs money depends on whether the new database shares the existing compute or gets its own, and only Chris can see that.
  - **Recommendation:** Before PR 7, confirm whether the engine database shares the existing Neon compute or adds an always-on one, and put the latter's cost in the engine budget. With findings 2 and 3 applied (no per-minute progress, feed health written only on changes), the compute can idle between posts.

## Questions

- **[minor] scope**: Between cutover and PR 10 there is no evidence and no tier, so what decides whether an alert is sent, sent as FYI or suppressed? The growth plan starts the public, permanent record at cutover (its soft launch), so those pre-evidence calls stay up for good. Is each alert stamped with its method and evidence version, so the record can be read era by era?

## Observations

- **[info] scope**: The restated problem used as the anchor here: decide, with evidence a skeptic would accept, whether a market-moving signal survives the few minutes it takes to see a post, then deliver that signal and its proof to people fast enough to act on, cheaply and in a form that earns an audience. The plan can be restated without its solution, so it is problem-first, but its build order is solution-first (Blocker).
- **[info] scope**: PR 12 recommends official feeds (White House, Fed, USTR) as the second source. Those are scheduled or wire-carried releases that algorithms price in milliseconds, so a mirror that is minutes late is the least likely place for an edge. The mission also named X, Reddit and more accounts instead. Drop PR 12 from this plan, and choose a second source after the report, from what it shows, as a short plan of its own.
- **[info] architecture**: The plan already made several cuts that first principles support: one process instead of four consumers and an events table, the raw payload on the row instead of S3, one fast model instead of an ensemble, and no paid scraper on the live path. Don't let the items cut above come back as "small" additions in later PRs.
- **[info] scope**: Engine status appears in three places: `python -m engine status`, the health endpoint, and `/api/v1/status/engine` behind the dashboard's Status page. Keep one JSON source that the CLI and the page both read.
