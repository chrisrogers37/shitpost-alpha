# Brainstorm Guide — Future Enhancements

> Living document of enhancement ideas for Shitpost Alpha. Revisit when planning the next development session.

---

## 1. Aggregate Analytics Pages

**Priority:** High — comes after single-post enrichments are solid

Dashboard with portfolio-level performance metrics across all predictions:
- Win rates by ticker, timeframe, confidence band
- Sharpe ratio, drawdown analysis, max consecutive wins/losses
- Rolling performance windows (7d, 30d, 90d trailing accuracy)
- Cumulative P&L chart (hypothetical $1000-per-trade portfolio)
- Heatmaps: accuracy by day-of-week, hour-of-day, market timing
- Backtest simulator with configurable confidence thresholds

**Depends on:** Single-post feed enrichments (Phases 1-4) providing richer per-post data.

---

## 2. Signals Migration

**Priority:** High — unblocks multi-source architecture

Complete the 5-phase migration plan at `documentation/planning/SIGNALS_MIGRATION.md`:
- **Phase 0:** Historical backfill (signals table only has posts since Feb 2026)
- **Phase 1:** Migrate analyzer from ShitpostOperations to SignalOperations
- **Phase 2:** Migrate all raw SQL queries from `truth_social_shitposts` to `signals`
- **Phase 3:** Remove dual-write to legacy table
- **Phase 4:** Remove legacy FK and cleanup

Currently 13 read queries still hit `truth_social_shitposts` instead of `signals`. The `signals` table has 100% column coverage for the migration.

**Effort estimate:** ~8-10 hours total.

---

## 3. Multi-Source Expansion

**Priority:** Medium-High — the big vision

Same feed, multiple sources with source badges:
- **Elon Musk via X (Twitter)** — first target, same single-post feed format
- **Congressional filings** (stock trades by legislators)
- **SEC EDGAR** (13F filings, insider trades)
- **Reddit** (r/wallstreetbets, r/stocks sentiment)

Each source gets its own harvester implementing `SignalHarvester` base class. Posts flow into the shared `signals` table. The feed view shows source badges (Truth Social, X, SEC, etc.) on each post.

Architecture evaluation (Kafka vs DB polling) at `documentation/planning/ARCHITECTURE_EVALUATION_ADDENDUM_KAFKA.md` — recommends event-driven backbone at ingestion layer for multi-source.

**Depends on:** Signals migration (item 2).

---

## 4. Multi-Model Analysis

**Priority:** Medium — transformative for prediction quality

Run every post through multiple LLMs in parallel, then synthesize:
- **GPT-4** (current) + **Claude** + **Grok (xAI)**
- Cross-model theses: each model produces its own analysis independently
- Parallel ticker extraction: one model may identify tickers another missed
- Consensus scoring: agreement between models increases confidence
- Divergence highlighting: where models disagree is the most interesting signal

Implementation considerations:
- Parallel API calls per post (3 providers simultaneously)
- New DB schema: per-model predictions linked to a consensus prediction
- Cost management: ~3x LLM spend per post
- UI: show individual model theses in expandable sections, highlight consensus/divergence

---

## 5. Ticker-Dedicated Pages

**Priority:** Medium — strong standalone feature

Full price horizon with ALL shitposts annotated on the chart:
- Navigate to `/ticker/TSLA` and see the entire price history
- Every mention of TSLA across all posts plotted as markers on the timeline
- Click any marker to see the post + prediction + outcome
- Aggregate stats for that ticker: total mentions, win rate, avg return, best/worst prediction
- Fundamentals panel (already have data in `ticker_registry`)
- Compare against S&P 500 or sector benchmark

**Depends on:** Current chart component patterns, existing outcome data.

---

## 6. Ticker Validation

**Priority:** Medium — data quality improvement

Currently seeing nonsense tickers extracted by the LLM. Improvements:
- Cross-reference extracted tickers against known exchanges (NYSE, NASDAQ, AMEX)
- Maintain a blocklist of common false positives (e.g., "USA", "GDP", "CEO")
- Validate via yfinance `.info` call before registering in `ticker_registry`
- Flag invalid tickers with `status='invalid'` and `status_reason`
- Consider structured output schemas (JSON mode) to reduce extraction errors
- Retroactive cleanup: scan existing predictions for invalid tickers

---

## 7. Enhanced Prompting

**Priority:** Medium — improves everything downstream

Review and improve the LLM analysis prompts:
- Audit current prompt at `shit/llm/` for gaps and biases
- Prompt versioning: store prompt version with each prediction for A/B analysis
- Structured output schemas (OpenAI JSON mode, Claude tool_use)
- Better ticker extraction instructions with examples
- Timeframe-specific prompting: some posts are about immediate impact, others long-term policy
- Few-shot examples of high-quality analyses
- Evaluate prompt performance: accuracy by prompt version

---

## 8. Prediction Backfilling

**Priority:** Low-Medium — historical depth

Run LLM analysis on old posts that predate the analysis pipeline:
- ~28,000 historical posts in the database, many unanalyzed
- Batch processing with rate limiting and cost monitoring
- Backtest predictions against known market outcomes (outcomes already exist)
- Compare "what we would have predicted" vs actual market moves
- Use as training data for prompt optimization

**Cost consideration:** At ~$0.03/post for GPT-4, full backfill = ~$840.

---

## 9. Backtesting Framework

**Priority:** Low-Medium — advanced analytics

Systematic backtesting of prediction strategies:
- Portfolio simulation: given confidence threshold X, what's the historical P&L?
- Position sizing strategies: equal weight, confidence-weighted, Kelly criterion
- Risk metrics: max drawdown, Sortino ratio, value-at-risk
- Strategy comparison: "only trade bullish TSLA signals above 70% confidence"
- Walk-forward analysis: train on older data, test on recent data
- Monte Carlo simulation for confidence intervals

**Depends on:** Sufficient historical prediction+outcome data (currently ~5,000 predictions).

---

## 10. Alerting Completion

**Priority:** Low — code is 95% done, just needs configuration

Telegram bot is fully implemented and deployed:
- **All that's needed:** Set `TELEGRAM_BOT_TOKEN` in Railway environment
- Run `python -m notifications set-webhook <url>` to register
- Users can `/start` the bot to subscribe

Future alerting channels:
- **Email** (SMTP/SendGrid) — code exists in `notifications/dispatcher.py`
- **SMS** (Twilio) — code exists, needs Twilio account
- **Browser push notifications** — WebPush API integration
- **Webhooks** — custom integrations for power users
- **Slack** — workspace integration

---

## Implementation Order (Suggested)

1. Aggregate analytics pages (builds on enriched feed data)
2. Ticker validation (data quality fix, small scope)
3. Signals migration (unblocks multi-source)
4. Multi-source expansion (Elon Musk via X first)
5. Enhanced prompting (continuous improvement)
6. Ticker-dedicated pages
7. Multi-model analysis
8. Alerting completion (quick config win)
9. Prediction backfilling
10. Backtesting framework
