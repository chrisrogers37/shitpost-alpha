---
name: brainstorm-stage
description: Signal-engine brainstorm doc delivered 2026-09-30; approved by Chris 2026-09-30 14:58 (decisions 3-5 open, defaults assumed)
metadata:
  type: project
  modified: 2026-09-30T01:29:43.720Z
---

Brainstorm stage delivered 2026-09-30 at /mnt/project-files/brainstorm/signal-engine-brainstorm.md, awaiting Chris's approval before planning.
Recommendations: mirror scraper (revised after /mnt/project-files/research/truth-social-scraping.md: CNN archive ix.cnn.io/data/truth-social/truth_archive.json + trumpstruth.org/feed polled every 60s; direct Truth Social API only if Chris accepts ToS risk; ScrapeCreators fallback until mirrors clean a week); latency target revised to p50 <5 min, p95 <10 min; #224 + signal_sources watchlist; one always-on worker + fast path (fast model first, ensemble follows); event-study backtest with SPY + random-time placebo baselines, entry at first tradeable price after alert, guard LLM look-ahead bias; evidence from backtest tables in alerts. Est. spend $40-130.
Cloud sandbox proxy blocked truthsocial.com, ix.cnn.io and trumpstruth.org, so feed latencies are unverified.
Chris 2026-09-30: validate scraper only on Railway (read-only probe service proposed), dev/backtests on sandbox's own Postgres, Neon dev branch dropped. Sandbox also can't reach Yahoo Finance; GitHub is reachable; Postgres 16 installed without pgvector.
Chris approved 2026-09-30 14:58: mirrors-only scraper; real-time via always-on worker and NO crons as a rule (move daily/weekly jobs into worker scheduler too); backtest unit = signal x implicated tickers; spend ok, leftover carries forward; Railway probe OK only if thinly scoped + flagged for removal; sandbox Postgres OK. Decisions recorded in doc section 8.
**How to apply:** planning stage should start from the doc's section 7 decisions. Related: [[project-goal]]
