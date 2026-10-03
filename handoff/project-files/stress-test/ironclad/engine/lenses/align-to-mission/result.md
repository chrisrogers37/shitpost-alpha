---
lens: align-to-mission
worker: align-to-mission
pr_url: null
plan-path: /tmp/claude-0/-home-user-shitpost-alpha/a5caeb1a-7d65-5411-9ba6-dd1e66cd4527/scratchpad/ironclad.zWbnjW/source-engine.md
started: 2026-10-01T01:00:30Z
completed: 2026-10-01T01:12:00Z
status: completed
severity: major
---

## Blockers

No phase is misaligned with the mission, and no gate is broken enough to stop the plan. The problems below are over-scoping and ordering, not direction.

## Risks

- **[major] scope**: The mission's deciding question, whether any call beats the placebo after costs, is answered at PR 10, after PRs 6 to 9 and most of the spend.
  - PRs 6 to 9 build two live WebSocket price streams, the revision and cursor machinery, a Railway service that runs for 3 months (cap $40), the cutover with subscriber carry-over, and a $40 LLM backfill.
  - The only stop rule ("if nothing beats the placebo after costs, we stop and rethink") is attached to PR 10. PR 5 already produces the keyword-layer report with no spend and no production effect.
  - PR 3 and PR 5 also rest on Alpaca's minute-bar depth, which is unverified (search results, and the sandbox refuses the host). If it fails, the 5-minute and 15-minute windows shrink to recent posts. Those windows are the core of goals 3 and 4.
  - **Recommendation:** Add an explicit go, narrow or stop gate between PR 5 and PR 6, where Chris reads report v1 before the live-engine spend starts.
    - Make PR 3's first task the Alpaca depth, delay and limit check, with a written stop rule. For example: if minute bars do not reach 2022, tell Chris before PR 4 starts.
    - Add a direction-agnostic reaction test to PR 5: the absolute abnormal move after posts against the 100-time placebo, per window. It shows whether anything is there to trade and how fast it decays, and it works even if extraction is poor.
    - Gate PR 9's $40 on that read. Gate the PR 6 streams and the PR 7 service on it as well.

- **[major] scope**: Evidence is what the mission and the growth plan say the product is, yet it reaches alerts at PR 10, two PRs after the public soft launch at PR 8.
  - Growth opens the public channel and starts the permanent public record at PR 8, with the line "graded in public". Until PR 10, alerts say "evidence is still being built", with no tier and no tradeable flag. The first weeks of the record that stays up for good are therefore unevidenced calls.
  - PR 10 is also listed after PR 9, but its core (reading `backtest_summary` into an evidence line, tier and tradeable flag) needs only PR 5's output. The $40 backfill and the live-record import do not have to come first.
  - **Recommendation:** Split PR 10.
    - 10a, before PR 8: read the current keyword-layer summary, add the evidence line, the LOW tier and the tradeable flag. The shadow week then tests the real alert text.
    - 10b, after PR 9: outcome updates and the live and LLM layers.
    - If 10a cannot move, keep the Telegram channel admin-only until it lands, so the public record opens with evidence-bearing alerts.

- **[major] scope**: Crypto is unapproved and threaded through four PRs, and its stated justification is weak. This is overbuilding.
  - The mission says "tickers". The crypto card is still open and the plan labels it "Default, needs your OK", yet the approval checklist folds it into "Defaults".
  - Cost in code:
    - PR 3: an Alpaca crypto adapter and a Coinbase fallback.
    - PR 5: a second benchmark (BTC, with beta) and a second window set (5 minutes to 7 days).
    - PR 6: a second live stream, and a 24/7 calendar branch.
    - PR 10: crypto outcome updates at 1h, 4h, 24h, 3d and 7d.
    - The long tail of "any coin a post names".
  - The justification (69% of posts land off-hours) is about all posts. The plan never counts how many posts imply a crypto instrument. Off-hours stock posts are already covered by next-open and pre-market entry.
  - **Recommendation:** Hold crypto out of PRs 3 to 6 until the card is answered.
    - Before answering, count archive posts whose keyword extraction names a coin or has a crypto or macro topic. This is free.
    - If yes, start with BTC (and maybe ETH) as backtest-only in PR 5. That is one adapter, no stream, no "any coin" and no alert changes. Promote it to alerts only if BTC shows an off-hours edge against the placebo.
    - Keep `asset_class` as a column on `instruments`. It is cheap and keeps the door open.

- **[major] scope**: Live price streams, `latest_prices`, `alert_progress` and provisional-bar handling serve the dashboard's "is it still worth trading?" view, not the mission's alert-plus-evidence. This is overbuilding inside PR 6.
  - Goals 3 and 4 need cached REST bars per post window and per-alert outcomes at fixed windows. Neither needs a stream.
  - PR 6 adds:
    - Two Alpaca streams, with a 30-symbol IEX cap and dynamic subscription to "recently alerted tickers".
    - A once-a-minute recompute and a provisional flag.
    - An evening job that swaps IEX bars for consolidated ones.
    - Three storage tiers.
  - All of it is tested only from recordings and runs for real first on Railway, so it is the least verifiable code in the plan. It sits in the heaviest PR on the cutover's critical path.
  - Public pages show only derived moves, so a REST-fed "move so far, labelled 15 minutes delayed" covers the mission.
  - **Recommendation:** Cut the streams, `latest_prices`, `alert_progress` and the provisional-bar and evening-swap machinery from PR 6.
    - If Chris wants the live "move so far" view, it becomes its own post-cutover PR, owned with the dashboard.
    - Keep the REST bars per alert window and the small evening forward-record job.
    - Drop the 2-year hourly tier unless a page needs it.

- **[major] scope**: The schema has about 22 engine tables, and many are sized for a growth plan Chris has not yet approved. They land in PRs 1 to 4, ahead of the cutover.
  - Examples:
    - `slug_redirects`. No ticker has been renamed yet.
    - Avatar and profile fields on `sources`. There is one source.
    - Per-source all-topics summary rows.
    - A full-text index for "post and keyword counts". Growth ranks prediction-market traders "later and only if cheap".
    - `engine_meta.stream_id`.
    - The advisory-lock and `clock_timestamp` ordering trick, plus the wake hook and a 30 s sweep. All are sized for many outlets, and launch has one channel and one polling dashboard.
    - A `price_sources` display-rights table, which could be a config constant until a second provider exists.
    - App-schema tables in PR 1, which belong to other plans. PR 1 needs the schema and roles only.
  - The plan's own claim that "a new source or market is a row and an adapter", plus Alembic, shows that additive migrations are cheap. Front-loading buys nothing.
  - **Recommendation:** Cut the examples above from PRs 1 to 4. Each returns as an additive migration in the PR that first reads it, after Chris approves growth.
    - Keep `alert_revisions` as an insert-only table with its trigger. It is cheap and makes the first call checkable, which growth relies on. The receipt followers will actually trust is the timestamped Telegram post, so do not build more ordering machinery around it.

- **[major] scope**: The topic taxonomy fragments the evidence the mission asks for, so most alerts may end up LOW and uninformative.
  - Chris asks which tickers moved, how far, over which windows, and how often the call was right. The plan keys evidence on topic by ticker by window: 8 to 12 topics, 7 windows, 2 entry views, with Benjamini-Hochberg correction across all of it.
  - Only about 21.9k posts are extractable (36,580 minus 7,352 retruths and 7,361 media-only), and fewer name a ticker. Most cells will fall under the 20-case LOW threshold.
  - PR 5's check (a planted effect is recovered) tests the machinery, not whether any real alert will be non-LOW. The plan can pass every criterion while alerts read "LOW" nearly every time.
  - The $40 backfill is limited to posts after each model's training cutoff. Its case count is not estimated before the spend.
  - **Recommendation:** Make instrument by direction by window the primary evidence key and promote the already-planned all-topics row to the headline. Show a topic as a secondary stratum only at 20 or more cases, and run the multiple-testing correction on that smaller family.
    - Add to PR 5's report the number of cells and the share of archive posts that would have received a non-LOW tier.
    - PR 9's go decision needs an estimate of post-cutoff, ticker-naming posts. If it cannot clear the threshold for any cell, do not spend.

- **[major] dependencies**: Feed licensing is unaddressed in the engine plan, while the added goal is to make money.
  - The growth plan marks as unverified that CNN's live-feed terms bar commercial use, that trumpstruth.org states no reuse terms, and that Truth Social allows personal use only. Those two mirrors are the engine's only inputs.
  - The engine's risk table covers parser breakage and lag but not rights. It plans to cancel ScrapeCreators, the only paid route, after one clean week, before anyone has read the terms.
  - Growth's "free" step still earns Telegram ad share on a public channel from the cutover.
  - The scraper decision was approved without the rights question in front of Chris.
  - The growth plan's paid gate lists a price licence but no feed licence.
  - **Recommendation:** Add a risk row and a PR 2 task to read and record both mirrors' terms, quoting the clause.
    - Re-open the "no paid fallback" decision with Chris before PR 8's public channel if the live feed bars commercial use. At the very least, do not cancel ScrapeCreators ($17 to $20 a month) until that is settled.
    - Ask growth to add feed rights as a paid-gate check.

## Gaps

- **[minor] testing**: The gates that lead to the irreversible steps are not tied to the mission's numbers.
  - "A clean shadow week" is undefined. PR 6's check ("our processing under 30 s at p95") covers only the engine's own share of latency, while feed lag (1.6 to 17 minutes in the three-post sample) dominates the goal of alerting within minutes.
  - A week can be "clean" with a 14-minute p95, or with posts the old system alerted on that the engine missed.
  - **Recommendation:** Write numeric pass criteria into PR 8's gate, and have the daily comparison print them.
    - Completeness: every post the old system alerted on is alerted by the engine, with exceptions listed.
    - Latency: post to alerted p50 and p95 meet the target reset from the probe.
    - No feed alarm stays open beyond a stated time.

## Questions

- **[minor] scope**: How many active old subscribers are there? The shadow week, the doubled Railway cost, the rollback path and the carry-over runbook are sized for an audience the plan never counts. If it is a few dozen, a 2 to 3 day shadow with the numeric gate above would do.
- **[minor] scope**: The PRs carry no S/M/L/XL sizes, so proportionality cannot be checked. PRs 3 and 6 are probably the heaviest and are where crypto, streams and the front-loaded schema concentrate. Can the planner add sizes?
- **[minor] data-integrity**: PR 9 imports the old system's live predictions as an evidence layer. They were made by a three-model ensemble and a different prompt. Is that evidence for the new single fast model's alerts? If not, it must be labelled as the old system's record, not the engine's.

## Observations

- **[info] scope**: Mission anchor, taken from `mission.md`: a signal engine Chris would actually trade on (free near-real-time scraper, a general signals model, a backtest of every signal against market data, and alerts within minutes that carry that evidence, within $250, staged, never production). The added goal is to attract users and followers and find a way to make money. Clean-slate and no-crons rules apply.
  - Per PR, aligned means it directly serves the mission, and tangential means it could be cut or deferred without harming it.
    - 1 Foundation: aligned. The app-schema tables inside it are tangential (see Risks).
    - 2 Feeds and signals: aligned (goals 1 and 2). The growth-driven columns are tangential.
    - 3 Market data: aligned for stocks. Crypto, the display-rights table and the storage tiers are tangential.
    - 4 Extraction: aligned.
    - 5 Backtest v1: aligned and the key deliverable, with the topic caveat above.
    - 6 Alerts: aligned at its core. Streams and `alert_progress` are tangential.
    - 7 Shadow run: aligned as safety.
    - 8 Cutover: aligned as safety.
    - 9 Backtest v2: aligned, but the spend needs the sizing check above.
    - 10 Evidence alerts: aligned and central, but too late.
    - 11 Removal: aligned with clean-slate and the no-junk rule.
    - 12 Second source: aligned with goal 2 and correctly gated on an edge.
- **[info] scope**: Aggregate drift. At PR level the plan is healthy. Six PRs (2 to 6 and 10) are mission-direct, PR 9 supports them, four (1, 7, 8, 11) are the cost of replacing the old system, and one is gated.
  - The drift is inside PRs, concentrated in 3 and 6, and in the schema. Crypto, streams and the pre-approval growth schema are probably the largest tangential commitment, but this is an estimate because the plan gives no sizes.
  - Mission coverage is complete for goals 1 to 3. Goal 4's defining feature (evidence in alerts) is covered but late. The added goal gets plumbing only (slugs, public ids, revisions, delay hook), which is right for an engine plan.
- **[info] scope**: The plan correctly cuts the ensemble, the delivery queue, S3, the events table, the old Telegram extras and ScrapeCreators-as-fallback. It gates the second source on an edge and flags the probe for removal. Keep that discipline.
- **[info] scope**: The budget text is inconsistent but inside the cap. The Decisions table says $40 to $130, while the Budget says $35 to $90 expected with a $105 cap. Growth puts all four plans at about $155 of $250. Neon's added cost is unknown and the plan says only Chris can see it.
