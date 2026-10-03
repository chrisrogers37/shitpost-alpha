## Ironclad Review: Signal engine plan

Dispatching 6 lenses via subagent mode.

**Cycle:** 1 · **Type:** plan · **Lenses:** 6 completed / 0 failed (adversarial-review ran its five reviewer angles plus a 10th-Man inline, so their independence is reduced)

Lens key: AR adversarial-review · FP first-principles · CB cost-benefit · AM align-to-mission · PH plan-health-audit · PC precedent-check

### Blockers

- **E1 [critical] scope: the edge gate comes after almost everything it should gate** (AR, FP; AM, PC, CB agree). The stop rule sits at PR 10, after PRs 1-9, N1, N2, D1 and the public soft launch at PR 8. PR 5's keyword backtest needs only PRs 2-4 and costs $0. Repo precedent: April 2026 shipped 9 of 12 features in 3 days while the benchmark and significance test were never built (#133-#139).
  - Fix: gate 0 after PR 5. Chris reads the PR 5 report (keyword layer over the archive, SPY/QQQ/BTC/ETH included, plus the old live record only if exported) with a decision rule agreed in advance, before PR 6 is written. Size PR 6 onward by what it shows (windows, asset classes, evidence unit). Make PR 3's first task the Alpaca depth check.

### Risks

- **E2 [major] scope: PR 6 is overpacked and on the cutover path** (all but PC). Two Alpaca WebSocket streams, `latest_prices`, per-minute `alert_progress` and the provisional-bar evening swap serve one "move so far" panel; N1, PR 7 and PR 8 wait on PR 6. Fix: PR 6 = alert object, insert-only revisions, cursor, wake hook, worker registration. Streams and progress move to an optional post-gate PR, built only if the edge is in minutes; "move so far" comes from a cached REST call meanwhile.
- **E3 [major] scope: crypto is threaded through PRs 3, 5, 6 and 10 before any evidence** (AM, CB, FP, AR). The 69% figure says when posts land, not that they move coins. Fix: BTC/ETH (SOL) in the PR 5 backtest only; crypto alerting only if it shows an edge. Chris's crypto card decides.
- **E4 [major] scope: the data model is overbuilt** (all six). About 22-28 tables for one source, two hard-coded mirrors and one vendor. Precedent: PR #140's multi-source scaffolding (`shitposts/twitter_harvester.py:83`) was filed as dead code by July (#224). Fix: no table or adapter lands before the PR whose code reads it. Cut or defer `slug_redirects`, `price_sources` (a code rule: the public API never serves raw prices), `latest_prices`, `alert_progress`, `feeds` (config), per-poll `feed_health` (about 7,200 rows/day; keep counters), `instruments.venue`, `audience_daily`/users/entitlements, and the app-schema tables in PR 1. `signals.seq` must take the same lock as `alert_revisions.seq` or be dropped.
- **E5 [major] data-integrity: evidence may describe a different population than the alert, and most alerts will read LOW** (AR, FP, AM, CB). Live alerts are LLM-labelled; the only full-history layer is keyword-labelled; the plan never says which layer an alert quotes. Topic x ticker x 7 windows x 2 entries x 2 costs x 3 layers, corrected by BH, leaves most cells under 20 cases. Fix: make the evidence key deterministic (versioned keyword and alias rules applied identically to history and live; the LLM writes the reason line). Pre-register a small primary family (for example topic to SPY/QQQ/BTC at 1h, close, 1d; named company to its ticker at close and 1d). PR 5 reports the share of posts that would get a non-LOW tier. The $40 LLM backfill becomes optional after gate 0, run on a slice first.
- **E6 [major] dependencies: the sources are not cleared for the money goal and can be pulled** (AR, FP, AM, PH). The growth plan reports CNN's live-feed terms bar commercial use (unverified); trumpstruth states no terms and gets cache-busted 1,440 times a day from one Railway IP; both scrape Truth Social, so one block can take out both; the engine plan has no risk row for any of this and cancels ScrapeCreators before anyone reads the terms. The 32 KB CNN read holds about 58 posts. Fix: read and quote both sources' terms before PR 2; keep ScrapeCreators until that is settled; send a User-Agent with a contact address; add a catch-up full fetch when the last-seen ID falls outside the range read; decide with Chris what the product shows when both mirrors are dark.
- **E7 [major] dependencies: every Alpaca fact is unverified** (AR, CB, FP). Minute bars to 2016, 200 calls/min, crypto history, and whether derived % moves may be published. If depth fails, short windows exist only for 60 days. Fix: Chris opens the free account and the host goes on the allowlist before PR 3; one recorded call per claim becomes PR 3's fixture. One Alpaca adapter; yfinance only as a cross-check script; Coinbase cut (its host is not even planned). Ask Alpaca in writing about derived numbers before D1 ships a % chart.
- **E8 [major] compatibility: one shared migration history applied at engine start-up** (AR, FP, PC, CB, PH). Any other plan's bad migration stops live alerts; deploy overlap runs two pollers and two Alembic runs. Fix: `engine migrate` as a pre-deploy step, expand-then-contract only, a CI check for a single Alembic head, roles created once in the Neon console, a singleton guard. Correction from the notifications round (M9): Railway overlaps old and new deploys and then SIGKILLs the old one with no grace, and session advisory locks don't work through Neon's pooled endpoint, so the singleton is a lease row (or uses the direct connection), not a session lock.
- **E9 [major] architecture: single-process safety repeats old failures** (PC). #201 (crash between claim and process wedged events), #207 (retry-forever LLM spend), #202 (double sends); a poison post plus `railway.json` ON_FAILURE with 10 retries can leave the only process stopped. Fix: per-signal attempts with a terminal error stage, UNIQUE alert per signal, kill-9 and two-instance tests in PR 6, always-restart.
- **E10 [major] observability: the watchdog lives inside the process it watches** (PC). Four old failures ran for months unnoticed (maturation since 31 Jul, snapshot capture at 0, the winter briefing, #198). `notify_operator` only logs until N1. Fix: an external uptime check plus a daily heartbeat to the admin chat from PR 7.
- **E11 [major] data-integrity: ticker collisions** (PC). 377 of 2,694 old completed predictions (14%) had a bad ticker; GOLD, STEEL, TAX and WAR needed a blocklist (5bdf84b). "US-listed with bars on the post date" accepts them all. Fix: the collision list as data, a cashtag or company name required for ambiguous symbols, hand-labelled keyword precision published in PR 4.
- **E12 [major] performance: the latency claim rests on three posts** (AR, AM). CNN's file changed every 8-26 minutes in the lag poll; if periodic, a typical post waits about 8.6 minutes for CNN. The backtest never states the alert delay it assumes for history, and that decides the 5- and 15-minute results. Fix: take p50/p95 from the 24-hour probe; set the backtest's historical alert time to the first mirror's p90 lag plus processing; no public "minutes" claim until the shadow week measures it.
- **E13 [major] architecture: PR 10's nightly refresh has nothing to read and nowhere safe to run** (AR, FP, PH). Research minute bars live as sandbox files; heavy statistics would stall the one asyncio loop. Fix: import historical layers as frozen runs; production only grades closed live alerts from REST bars, in a subprocess.
- **E14 [major] data-integrity: the public alert shape contradicts the prices rule and cannot be fixed later** (PH, FP). F and H put the entry price in public revisions and `venue` in `alert.v1`; revisions are insert-only. Fix before PR 6, with a schema test.
- **E15 [major] scope: evidence reaches the public after the public launch** (AM, FP, AR). Growth opens the public channel and permanent record at PR 8; evidence lands at PR 10, which needs only PR 5. Fix: split PR 10. 10a (keyword-layer evidence line, tier, tradeable flag) lands before PR 8; 10b (outcome updates) after. Or keep the channel admin-only until 10a. State what decides "sent" before tiers exist.

### Gaps

- **E16 [major] testing: the gates are never defined** (AR, PH, AM, FP). "Clean shadow week" (PR 8), "clean week on the engine" (PR 11), "an edge" (PR 10, 12), the sent/FYI rule before tiers; the latency target appears both as fixed numbers and as a probe-reset formula; most "Verified by" cells have no pass threshold, and PR 6's 30 s p95 cannot be shown with a stub model. Fix: numbers, for example clean shadow week = zero posts missed vs the old system, p95 within target, no unhandled crash, each mirror healthy on 95%+ of polls; edge = a pre-registered primary cell with BH q<0.10, n>=30, net of 20 bp.
- **E17 [major] scope: the shadow-week comparison needs the old production database** (CB, FP), which the engine never touches, and compares against a known-broken system. Fix: a one-off script outside `engine/` (coverage and timing only), deleted in PR 11.
- **E18 [minor] data-integrity: importing the old live record is negative ROI** (CB, AR, AM, PC). Different, buggy predictor (#217, #218), `post_timestamp` holds analysis time, the track record starts at cutover anyway, and the export carries subscriber PII. Fix: drop it from PRs 8 and 9 (at most a one-off report labelled "old system"). Count active subscribers first; if a few dozen, the bot description and /start reply carry the channel link. Any subscriber export goes to Railway, never the sandbox.
- **E19 [minor] scope: PR 8 depends on D1 and N2 while D1 keeps growing** (CB, PH). Fix: write a minimum D1 (live list and signal page) into PR 8's gate. Rollback is not "a switch" once D1 deletes the old frontend in the same sitting.
- **E20 [minor] data-integrity: outsiders cannot check the record** (AR). The owner role can drop the trigger; Telegram posts are edited in place. Fix: append each first revision, or a daily hash, to a public GitHub repo; or post the first call unedited and results as replies.
- **E21 [minor] cost: Neon** (FP, AR). Writes every 15 s keep compute awake; does the new database share compute with production? Verify before PR 7.
- **E22 [minor] scope: no burst policy** (PC). Burst fatigue was the old plan's top UX problem. Measure bursts in PR 2; a per-instrument FYI rule in PR 6.

### Cuts and deferrals (overbuilding)

- PR 12 (second source): cut to a placeholder; `sources` already leaves room (CB, FP).
- From PR 6: streams, `latest_prices`, `alert_progress`, provisional-bar swap (E2).
- From PR 3: Coinbase adapter, yfinance as a runtime fallback, `price_sources`, hourly bar tier (E4, E7).
- Tables: per E4.
- Old live-record import and the shadow-week comparison against the old DB (E17, E18).
- Engine status served three ways (CLI, health endpoint, /status/engine): keep one source (FP).

### Questions

- Does approving crypto mean coin alerts from PR 6, or BTC/ETH in the backtest first? (AR, CB, AM)
- How many active old subscribers are there? (AM, AR)

### Kept (the lenses agree these hold)

One process with no events table; the raw payload on the row and S3 retired; no ensemble; post time from the snowflake ID; insert-only `alert_revisions` under one locked sequence; alerts that quote evidence; spend caps; a shadow week with rollback until PR 11.

**Not converged:** 1 blocker, 16 major risks/gaps open; decision forks open: crypto, edge-gate placement, old-record import.

---
*Reviewed by /ironclad — cycle 1*
