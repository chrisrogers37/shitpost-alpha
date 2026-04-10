# Product Brainstorm — Shitpost Alpha Feature Roadmap

**Session Date**: 2026-04-09
**Status**: Plans complete — ready for `/implement-plan` sessions

---

## Context

Shitpost Alpha is live in production, monitoring Trump's Truth Social posts every 5 minutes, analyzing them with GPT-4, and sending alerts via Telegram. The system works end-to-end, but **isn't delivering enough value** to the small group of traders using it:

1. **Alerts are too slow** — 5-minute cron intervals mean 0-5 minute detection latency, plus pipeline processing time
2. **Analysis lacks historical context** — The LLM analyzes each post in isolation, with no reference to how similar posts moved markets before
3. **No feedback loop** — Users never learn whether past alerts were right or wrong unless they check manually

The system has rich historical data (1000+ predictions with multi-timeframe outcomes) and unused infrastructure (3 LLM providers, email/SMS dispatch, signals table) — but none of it is surfaced to users.

---

## Feature Ideas — Dependency Graph

```
Phase A: Foundation (no dependencies)
├── 01 Always-On Harvester ──────────┐
├── 02 Fundamentals-Enriched Prompts │
└── 03 Watchlist Filtering           │
                                     │
Phase B: Analysis Quality ───────────┤
├── 04 Historical Echoes ◄───────────┤ (uses faster data from 01)
├── 05 Multi-LLM Ensemble            │
└── 06 Confidence Calibration        │
                                     │
Phase C: Alert Experience ───────────┤
├── 07 Pre-Market Briefing ◄─────────┤ (uses echoes from 04, calibration from 06)
├── 08 "What Happened" Follow-ups    │
├── 09 Smart Alert Batching          │
└── 10 Push Notification Gateway     │
                                     │
Phase D: Social & Engagement ────────┘
├── 11 Conviction Voting ◄──────────── (uses alert flow from Phase C)
└── 12 Weekly Scorecard ◄───────────── (uses outcomes + optional voting data)
```

### Hard Dependencies
- **04 Historical Echoes** benefits from 01 (faster data) but can work without it
- **07 Pre-Market Briefing** is richer with 04 (echoes) and 06 (calibration) but functional without
- **12 Weekly Scorecard** is richer with 11 (voting data) but functional without

### No Dependencies (can be built in any order)
- 01, 02, 03 are fully independent
- 05, 06 are independent of each other
- 08, 09, 10 are independent of each other

---

## Effort Estimates

| # | Feature | Effort | New Code | Reused Code | New Infra |
|---|---------|--------|----------|-------------|-----------|
| 01 | Always-On Harvester | Medium | Polling loop, health checks | Harvester, event system | Railway always-on service |
| 02 | Fundamentals Prompts | Low | Prompt context block | ticker_registry, LLM prompt builder | None |
| 03 | Watchlist Filtering | Low | Bot commands, filter logic | telegram_bot, alert_preferences | None |
| 04 | Historical Echoes | Medium-High | Embeddings, similarity search, echo aggregation | prediction_outcomes, feed API | pgvector or FAISS |
| 05 | Multi-LLM Ensemble | Medium | Parallel calls, consensus merge | All 3 LLM providers, prediction storage | None |
| 06 | Confidence Calibration | Medium | Calibration curve, weekly refit | prediction_outcomes, statistics | Cron job |
| 07 | Pre-Market Briefing | Low-Medium | Digest formatter, market calendar | Telegram sender, prediction queries | Cron job |
| 08 | What Happened Follow-ups | Low-Medium | Follow-up scheduler, message templates | prediction_outcomes, Telegram sender | DB table + cron |
| 09 | Smart Alert Batching | Medium | Burst detector, summary generator | Notification worker, LLM client | None |
| 10 | Push Notification Gateway | Medium | FCM integration, service worker | Dispatcher multi-channel pattern | Firebase project |
| 11 | Conviction Voting | Low-Medium | Vote handler, inline keyboards, accuracy calc | Telegram bot, prediction_outcomes | DB table |
| 12 | Weekly Scorecard | Low | Digest formatter, leaderboard query | statistics.py, prediction_outcomes, Telegram | Cron job |

**Total estimated effort**: ~6-8 implementation sessions across all features

---

## Recommended Build Order

### Sprint 1: Quick Wins (1-2 sessions)
- **02 Fundamentals Prompts** — Lowest effort, immediate analysis quality improvement
- **03 Watchlist Filtering** — Low effort, immediate user value
- **05 Multi-LLM Ensemble** — Medium effort, big analysis quality jump

### Sprint 2: Historical Intelligence (1-2 sessions)
- **04 Historical Echoes** — The signature feature; transforms raw data into actionable context
- **06 Confidence Calibration** — Makes confidence numbers trustworthy

### Sprint 3: Speed & Alerts (1-2 sessions)
- **01 Always-On Harvester** — Cuts detection latency from minutes to seconds
- **08 What Happened Follow-ups** — Closes the feedback loop
- **07 Pre-Market Briefing** — Morning context for the trading day

### Sprint 4: Polish & Social (1-2 sessions)
- **09 Smart Alert Batching** — Prevents alert fatigue
- **11 Conviction Voting** — Makes it social
- **12 Weekly Scorecard** — Builds trust through transparency
- **10 Push Notification Gateway** — Sub-second native alerts

---

## Design Documents

Each feature has a detailed design doc in this directory:

| File | Feature |
|------|---------|
| [01_ALWAYS_ON_HARVESTER.md](01_ALWAYS_ON_HARVESTER.md) | Sub-minute post detection |
| [02_FUNDAMENTALS_ENRICHED_PROMPTS.md](02_FUNDAMENTALS_ENRICHED_PROMPTS.md) | Company context in LLM prompts |
| [03_WATCHLIST_FILTERING.md](03_WATCHLIST_FILTERING.md) | User-specific alert routing |
| [04_HISTORICAL_ECHOES.md](04_HISTORICAL_ECHOES.md) | Similar-post pattern matching |
| [05_MULTI_LLM_ENSEMBLE.md](05_MULTI_LLM_ENSEMBLE.md) | Multi-model consensus analysis |
| [06_CONFIDENCE_CALIBRATION.md](06_CONFIDENCE_CALIBRATION.md) | Calibrated confidence scores |
| [07_PRE_MARKET_BRIEFING.md](07_PRE_MARKET_BRIEFING.md) | Morning trading digest |
| [08_WHAT_HAPPENED_FOLLOWUPS.md](08_WHAT_HAPPENED_FOLLOWUPS.md) | Outcome follow-up notifications |
| [09_SMART_ALERT_BATCHING.md](09_SMART_ALERT_BATCHING.md) | Rage-tweet storm consolidation |
| [10_PUSH_NOTIFICATION_GATEWAY.md](10_PUSH_NOTIFICATION_GATEWAY.md) | Native push notifications |
| [11_CONVICTION_VOTING.md](11_CONVICTION_VOTING.md) | Group bull/bear voting |
| [12_WEEKLY_SCORECARD.md](12_WEEKLY_SCORECARD.md) | Performance digest + leaderboard |

---

*Generated by /product-brainstorm on 2026-04-09. Use `/implement-plan` to begin building any feature.*
