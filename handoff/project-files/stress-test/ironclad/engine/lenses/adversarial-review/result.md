---
lens: adversarial-review
worker: adversarial-review
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-engine.md
started: 2026-10-01T01:00:30Z
completed: 2026-10-01T01:13:00Z
status: completed
severity: critical
---

## Blockers

- **[critical] scope**: The edge gate comes after nearly everything it should be gating. The plan answers its deciding question at PR 10: does any post-to-instrument effect survive the alert delay, the placebo and costs? ("PR 10 waits for you to read the backtest report; if nothing beats the placebo after costs, we stop and rethink", Build order › Gates.) By then PRs 1–9, notification N1/N2, dashboard D1 and the growth plan's public soft launch at PR 8 have all shipped, so the rethink arrives after about 80% of the build. Yet PR 5, the keyword backtest on the 21,862 archive text posts, needs only PRs 2–4 and costs $0 in the sandbox. PR 6, meanwhile, carries machinery that pays off only if there is an edge: two Alpaca WebSocket streams, `latest_prices`, per-minute `alert_progress`, provisional IEX bars replaced by an evening capture (Workstream F 'Live prices'), and crypto alerting, which Chris's card has not yet approved. Raised by the Skeptic and the 10th-Man Contrarian. The Counter-Planner's alternative is built on it.
  - **Recommendation:** Add a gate after PR 5. Chris reads the keyword-layer report, with SPY, QQQ, BTC and ETH among the instruments, before PR 6 is written. Split PR 6. Before the gate, build only what replacing the old system needs: the alert object, insert-only revisions with the seq cursor, the wake hook and worker registration. Move the rest into one post-gate PR, built only for the windows where an edge shows: the live streams, `latest_prices`, `alert_progress`, provisional-bar replacement, and crypto alerting with its stream and Coinbase fallback. With no edge, the minimal live path still meets goals 1–2: it replaces ScrapeCreators and the broken old pipeline, and nothing growth-facing is built on top of it.

## Risks

- **[major] performance**: The latency target, and the growth plan's public '2 to 4 minutes after a post', rest on three posts (Latency table). Over the same window, CNN's file changed every 8.2–25.7 minutes, a mean of 15 (research/plan-lag-poll/lag-2026-09-30.jsonl). If those refreshes are periodic, a random post waits about 8.6 minutes for CNN, and only about 20% wait 3 minutes or less. Two of the three posts beat that, which happens about 10% of the time by chance, so either CNN refreshes on new posts or the sample was lucky; three posts can't tell which. trumpstruth's uncached lag was 3.2–17 minutes. The backtest also needs an assumed alert time for every historical post ("entered at the first regular-session price after the alert would have gone out", Workstream E), and the plan never says what latency it assumes. That number decides the 5- and 15-minute results.
  - **Recommendation:** Before PR 2 merges, take these from the 24-hour Railway probe (expect 20 or more posts): each mirror's p50 and p95 lag, the same for whichever mirror is first, and how often both are over 5 minutes at once. Set the backtest's historical alert time to that first-mirror lag's p90 plus measured processing time, and report the p50 version as a sensitivity check. Put no minutes figure on any public page, profile or launch post until the shadow week has measured it end to end.

- **[major] data-integrity**: An alert's evidence may describe a different population from the alert itself, and most evidence will be too thin to use. Live alerts get topic, tickers and direction from the LLM (Workstream D). The only full-history layer is keyword-labelled; the LLM layers are the post-cutoff backfill and the live record, both small (E 'Three evidence layers, never pooled'). The plan never says which layer an alert quotes (F 'Evidence'). The hypothesis space is also very large: 8–12 topics × every named ticker × 7 windows × 2 entry views × 2 cost levels × 2 asset classes × 3 layers, with BH across 'every topic, ticker and window'. Most cells will fall under the 20-case LOW line. So 'alerts carry evidence' will in practice mean LOW on nearly every alert, or a few lucky cells that BH then removes. The brainstorm's own option (c), where the LLM extracts and the statistics decide direction, was dropped without saying why.
  - **Recommendation:** Before PR 4, make the evidence key deterministic. Topic and instrument come from versioned keyword and alias rules applied identically to history and live, so the full-history keyword layer is the alert's evidence. The LLM writes the reason line, and its direction is shown as a cross-check, not used as the key. Before PR 5, pre-register a small primary family, for example topic → SPY/QQQ/BTC at 1 hour, close and 1 day, and named company → that ticker at close and 1 day. Tier only on that family, pool tickers within a topic, and drop the pre-market second view and the 15-minute window from v1; everything else is exploratory and never becomes a tier. The $40 LLM backfill and PR 9's extra layer then become optional, to decide after PR 5.

- **[major] architecture**: PR 10's 'nightly refresh' in production has nowhere to read from and no safe place to run. The placebo needs 'years of minute bars for every ticker', which 'stays as files in the backtest workspace' in the sandbox (Data model › Storage tiers). The production database keeps 1-minute bars only for alert windows and the last 30 days, and Railway has no copy of the files; S3 is retired. Running permutation, bootstrap and BH in the one asyncio process alongside the pollers, LLM calls, streams and N1's delivery workers (Workstream A 'One process') would stall polling or get the service killed for memory.
  - **Recommendation:** In PR 10, import historical layers as frozen, versioned runs (rows and summary) built in the sandbox. Production's nightly job only grades live alerts whose windows have closed, using REST bars fetched per window, and recomputes the live layer's counts. Any placebo draws for live alerts are fetched on demand for those few signals. The job runs in a subprocess with a memory cap, so a slow night never delays a poll.

- **[major] compatibility**: One Alembic history is applied by the engine at start-up, which "refuses to start if one fails" (Workstream A 'Database'), and it also holds app-schema tables owned by the notification, dashboard and growth plans (H 'App schema'). So a bad migration from any of those plans stops the live alert path. And one merge redeploys the engine and web services together, so the web code can run against the old schema until the engine restarts; the web role is not allowed to migrate.
  - **Recommendation:** Run migrations as their own release step: `python -m engine migrate` as a pre-deploy command on the engine service (check that Railway supports pre-deploy commands for this service type before PR 1), expand-then-contract only. The engine refuses to start only if its own required revision is missing. Create the DB roles once in the Neon console rather than in migrations, so no role password lives in code.

- **[major] dependencies**: Both sources can be pulled, and neither is cleared for the money goal. The growth plan reports that CNN's live-feed terms bar commercial use (unverified), and trumpstruth, run by Defending Democracy Together, states no reuse terms. This plan busts trumpstruth's Cloudflare cache 1,440 times a day from a fixed Railway IP (Workstream B), which raises the odds of being blocked. The plan's answer to losing both is "a lasting outage of both needs a parser fix" (Risks). Separately, the 32 KB CNN range read holds only about 58 posts (20.3 MB / 36,571). A refresh gap during a posting spree, or a recovery after an outage, can drop posts the 100-item RSS no longer shows.
  - **Recommendation:** Verify CNN's terms for ix.cnn.io before the paid gate, and before the public launch if the channel takes Telegram's ad share. Send a User-Agent with a contact address, and email trumpstruth before the shadow week. Add a catch-up path: when the last-seen ID is not in the 32 KB window, fetch the full gzip (3.7 MB). After the probe, decide with Chris what the product does when both mirrors are dark for over an hour (status banner plus operator message), and whether a cold standby is worth its cost: ScrapeCreators, or the probe's direct result.

- **[major] dependencies**: The Alpaca facts the backtest and public site depend on all come from search results and are unverified: minute bars back to 2016, 200 calls a minute, crypto history, and whether computed % moves may be shown publicly (Decisions › Price data; Workstream C). `data.alpaca.markets` is not on the sandbox allowlist today. If the depth claim fails, the 5-minute to 1-hour windows exist only for the last 60 days (yfinance) and most of the evidence design goes with them. The 'no raw entry price' rule also hides less than it seems: a minute-resolution % series plus one public reference price, such as the day's close from any free source, rebuilds the raw prices.
  - **Recommendation:** Before PR 3 is written, Chris opens the free account and adds the host. One recorded call per claim (oldest SPY minute bar, the rate-limit headers, BTC minute bars from 2021) becomes PR 3's fixture. Ask Alpaca in writing whether derived % moves and hit/miss may be published, before D1 ships a % chart. Until the answer comes, public pages show window results (5 minutes to 5 days, hit or miss), not a minute-by-minute % series.

- **[major] scope**: The data model is built for sources, venues and vendors that don't exist yet: about 22 engine tables for one account, two hard-coded mirrors and one price vendor. This repo has done this before. In April, PR #140 built multi-source scaffolding: `shitposts/harvester_registry.py` and a `TwitterHarvester` that raises NotImplementedError (shitposts/twitter_harvester.py:83). The CHANGELOG declared the migration complete (CHANGELOG.md:63). By July all of it was filed as dead code (#224 M24, documentation/planning/dead-code-cleanup_2026-07-24/06_finish-signals-migration.md). The second source (PR 12) is gated on an edge anyway. Separately, `signals.seq` is not described as taking the lock that `alert_revisions.seq` takes, so with concurrent writers (two pollers, stage updates) a reader can skip a row that commits out of order.
  - **Recommendation:** Cut or defer these:
    - `feeds`: make it config.
    - `feed_health` per poll: one row per feed with counters, or 7-day retention; as specified it is about 7,200 rows a day.
    - `price_sources` and its API check: replace with one rule, that the public API never serves bars or prices.
    - `latest_prices` and `alert_progress`: defer with the streams (Blocker).
    - `slug_redirects`: add at the first ticker rename, with slugs keyed off the instrument id.
    - `instruments.venue`.
    - The yfinance and Coinbase fallback adapters: keep yfinance only as a one-off cross-check script in PR 3.

    `signals.seq` should either take the same lock or be dropped, with the 'All posts' list re-querying the newest N every 5 s. Keep `sources` and the `<platform>:<id>` key, since that generality costs nothing.

## Gaps

- **[major] testing**: The gates and rules that decide what ships and what subscribers see are never defined:
  - 'a clean shadow week' (PR 8)
  - 'a clean week on the engine' (PR 11)
  - 'an edge' (PR 10, PR 12): which layer, which windows, what threshold
  - the sent, FYI and suppressed rule before tiers exist. PRs 7–9 run with "evidence still being built", and from PR 8 the public channel gets whatever counts as sent.

  The admin rule "one runs 30 minutes behind the other" will also fire often, given CNN's gaps of up to 26 minutes and trumpstruth's lag of up to 17.
  - **Recommendation:** Write numbers into the plan before PR 7. For example:
    - Clean shadow week: no post the old system saw that the engine missed, p95 within target, no unhandled crash, and each mirror healthy on 95% or more of polls.
    - Edge: a pre-registered primary cell with BH q<0.10, n≥30, net of 20 bp.
    - Disposition before tiers: sent only for a mapped instrument tradeable now (market open, or crypto if approved); FYI otherwise.

    Set the behind-alarm from the probe's p99, not a round number.

- **[minor] data-integrity**: The old live-record import buys little and brings an extra job and PII handling. Old predictions came from a different predictor with known defects: `analyze_ensemble` drops the prompt (#217), and the parse fallback fabricates predictions (#218) (documentation/planning/tech-debt-2026-07-02/ISSUE_MAP.md:41-42). Backfill runs were possible too (shitpost_ai/cli.py:200-210). `post_timestamp` can't separate real-time rows from backfill because it holds the analysis time: shitvault/signal_operations.py:162 passes a datetime, so shit/db/database_utils.py:42-44 falls back to now(). The dashboard's track record counts only post-cutover alerts anyway. The same 'one read-only export' also carries subscribers' chat ids and names, and PR 9 uses that export in the sandbox.
  - **Recommendation:** Drop the live-record layer from PRs 8 and 9; if Chris wants it, make it a one-off report labelled 'old system'. Before PR 8, Chris counts active subscribers. If there are a few dozen or fewer, the bot description and the /start reply carry the channel link and nobody is imported. Any subscriber export goes straight to the Railway service, never to the sandbox or the project folder.

- **[minor] data-integrity**: Outsiders cannot check the 'checkable' public record. Insert-only revisions are enforced by a trigger that the engine's owner role can drop (F 'Revisions'). The Telegram 'receipt' is edited in place as results arrive (notification plan), so its original wording isn't visible either. The growth plan's whole differentiator is 'graded in public, misses kept'.
  - **Recommendation:** In PR 6 (or N1), append each alert's first revision, or a daily SHA-256 of that day's revisions, to a public GitHub repo; or post the first call unedited and add results as replies. It costs about $0 and a few dozen lines, and it makes the record auditable.

## Questions

- **[minor] performance**: Will the engine's new database share a Neon branch and compute with the old production database? If so, during the shadow week the engine's writes (feed polls every 15 s, minute bars, stream ticks) share compute with production. Which Neon plan, and what storage cap, will hold daily bars for every instrument, 30 days of minute bars and the raw payload on every signal?
- **[minor] scope**: If Chris approves crypto on his card, does that mean coin alerts from PR 6, or BTC and ETH in the PR 5 backtest first, with alerting only after they show an edge? The growth plan's change list assumes the former. This review recommends the latter.

## Observations

- **[info] process**: Produced inline (no subagent dispatch available): unit independence is reduced, and findings share context. The five reviewer angles plus a 10th-Man Contrarian ran in sequence in one session; notes are in architect.md, skeptic.md, operator.md, user.md, counter-planner.md and contrarian.md beside this file. Because the inline path weakens independence, the 10th-Man rule was applied regardless of the Blocker count.
- **[info] scope**: Pre-mortem: it is April 2027, and the plan failed. Five reasons, written before the lenses were applied:
  1. The mirrors ran at a median of 6–9 minutes, not 2–3, and the short windows held nothing.
  2. The PR 10 report found no edge after BH and costs, but the engine, streams, crypto, N1/N2, D1 and a public channel had already shipped.
  3. Alerts quoted keyword-layer evidence on LLM calls, almost every one read LOW, and a public miss streak contradicted the evidence quoted.
  4. CNN changed or withdrew ix.cnn.io, or trumpstruth blocked the cache-busting Railway IP, the product went dark for days, and when money came, CNN's terms barred commercial use.
  5. The one process did too much: a nightly refresh pegged memory, and a notification migration failed at start-up, so alerts stopped.
- **[info] architecture**: Counter-plan, in brief: evidence first, specific now.
  - E0 (about 1 week, $0, sandbox): archive import, Alpaca bars for SPY/QQQ/sector ETFs/BTC/ETH plus every ticker a keyword rule names, deterministic topics, a pre-registered event study. Then a gate.
  - L1 (built whatever the result): the minimal live path, two pollers → `signals` → deterministic label plus an LLM reason → `alerts` and `alert_revisions` → N1 Telegram → shadow week → cutover, in about 10 tables.
  - G1 (only for the windows with an edge): tiers and outcome revisions, live progress only if the edge is in minutes, crypto alerting only if BTC/ETH show one, ticker pages only for instruments with evidence.

  It gets the deciding answer in a week and keeps evidence and alerts on one labeller. It gives up a measured record of the LLM's own calls, some recall, and possibly the timing of the public channel. The synthesis (the Blocker plus the evidence-key Risk) keeps the plan's PR order and adds the gate and the cuts.
- **[info] compatibility**: Plan claims checked against main 139b145, all accurate:
  - 12 Railway services (railway.json).
  - Outcome maturation reads columns that script 008 dropped (shit/market_data/models.py:154,160 vs scripts/008_schema_cleanup.sql:25-26).
  - `post_timestamp` holds the analysis time (shitvault/signal_operations.py:162, shit/db/database_utils.py:42-44).
  - #217 and #218 (ISSUE_MAP.md:41-42).
- **[info] compatibility**: Hookup drift to reconcile in the next doc revisions (the notes are newer than the dashboard doc):
  - The dashboard doc still names `signal_tickers` and `alert_deliveries`.
  - It says the web role is 'read-only', while the engine notes give it S/I/U on app, which N3's self-serve webhooks need.
  - Its `/api/v1/bars/<symbol>` serves raw bars, and the 5 s `/prices/latest` poll in the dashboard notes, conflict with the 'none' display rights.
- **[info] scope**: Reference class. The last 'source-agnostic' migration (PR #140) was declared complete but left a dual identity and dead multi-source code (#224). The July dead-code cleanup finished phases 1–5 in a week and never landed phase 6, and main has been idle since #242 on 2026-08-20. The tail PRs in this plan (11 removal, 12 second source) are the kind that stall. The plan gives no calendar dates; Railway's budget assumes 3 months for about 22 PRs across four plans, all merged by Chris, with week-long gates.
- **[info] architecture**: These choices hold up and should be kept: one process with no events table; the raw payload on the row and S3 retired; no ensemble; post time decoded from the snowflake ID (verified on 36,571 posts); insert-only `alert_revisions` under one locked sequence; alerts that quote evidence; spend caps totalling $105; a shadow week with rollback as a switch until PR 11.
- **[info] scope**: Press release test, for the plan as revised: "We shipped a free Trump-post engine that alerts within minutes and grades every call against SPY in public, so followers see what kind of post has actually moved which ticker, and how often." It passes only if the edge gate comes first. Without an edge, the honest release is the first clause alone.
- **[info] scope**: Murphyjitsu. As written, a failure would not surprise me: the gate is late and the latency and evidence claims are unmeasured. With the Blocker and the three evidence and latency fixes applied, it would, because the remaining risks are external (source terms, Alpaca facts), and those come with explicit verify-before-PR steps.
