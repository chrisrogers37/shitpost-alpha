# Skeptic: first principles and alternatives

Inline pass 2 of 6, run in sequence. It had read the Architect's notes; each point that repeats one cites its own evidence.

## The problem in one sentence, without the solution
Know within minutes whether a Trump post is likely to move something you can trade by more than noise, after the delay and costs, and say so with honest evidence.

The decisive unknown is whether any edge survives the delay, the placebo and costs. Everything else is plumbing, or growth surface that only matters if the answer is yes.

## Findings
1. **The gate is in the wrong place.** The plan answers the decisive question at PR 10. By then PRs 1–9, N1, N2, D1 and the growth plan's public soft launch at PR 8 have shipped. PR 5, the keyword backtest on 21,862 archive text posts, needs only PRs 2–4 and costs $0 in the sandbox. Gate after PR 5, then build the growth-facing machinery only for the windows where an edge shows.
2. **The generality is ahead of need, and this repo has a precedent.** In April, PR #140 built a source-agnostic model, a HarvesterRegistry and a TwitterHarvester that raises NotImplementedError (shitposts/twitter_harvester.py:83). The CHANGELOG called the migration complete (CHANGELOG.md:63). By July it was dead code (#224 M24, documentation/planning/dead-code-cleanup_2026-07-24/06_finish-signals-migration.md). The new plan builds `sources`, `feeds`, venues, `price_sources` with display rights, slug redirects and a second asset class, while the second source (PR 12) is gated on an edge. Keep the cheap generality (the `<platform>:<id>` key and a `sources` row) and defer the rest.
3. **The LLM's role is too large for the evidence it can have.** The brainstorm itself recommended option (c): the LLM extracts, the statistics decide direction (brainstorm §'Two traps'). The plan has the LLM decide direction instead, which forces three evidence layers and a $40 post-cutoff backfill. A deterministic, versioned topic and alias labeller gives one full-history, unmemorizable layer that matches live alerts exactly.
4. **The hypothesis space is too wide.** 8–12 topics × every ticker × 7 windows × 2 entry views × 2 cost levels × 2 asset classes × 3 layers will either flatten real effects under BH or yield LOW everywhere. Pre-register a primary family and treat the rest as exploratory.
5. **Crypto: test before you build.** It rests on 69% of posts landing outside regular hours (research/post-timing/README.md), which is a reason to test BTC, not proof that posts move it. Put BTC and ETH in the PR 5 backtest as instruments. Build the stream, the Coinbase fallback, the 7 crypto windows and the crypto outcome schedule only if they show an edge.
6. **The old live record is a different predictor.** It came from GPT-4 and then a possibly three-provider ensemble (shit/config/shitpost_settings.py:44-47) with #217 and #218. It is no evidence about the new extractor, and the dashboard's track record starts at cutover anyway. Cut it from PRs 8 and 9.
7. **Too many fallback adapters.** Chris confirmed Alpaca. A yfinance fallback adapter and a Coinbase fallback adapter (a host the sandbox can't reach) are code for contingencies nobody has asked for. Keep yfinance as a one-off cross-check script in PR 3.

## Via negativa: what the engine must NOT do
- Don't build live-price streams or per-minute progress before an edge exists.
- Don't quote evidence from a different labeller than the alert's.
- Don't publish minutes claims that come from 3 posts.
- Don't let another plan's migration stop the live path.

## Assumption map
| | Low impact if wrong | High impact if wrong |
|---|---|---|
| High confidence | Snowflake post time; RT and media-only filters | Mirrors stay up (both have now been seen live) |
| Low confidence | Neon cost; Railway $15–30 | **An edge survives at 2–10 min latency; CNN lag about 2 min (n=3); Alpaca minute depth to 2016 and its terms on derived numbers; CNN/trumpstruth tolerate commercial use; topic×ticker cells reach n≥20** |

Everything in the bottom-right cell is validated before building, and each maps to a finding in result.md.
