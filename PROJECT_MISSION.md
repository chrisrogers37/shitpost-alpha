# Project Mission — Shitpost Alpha

## What this project is

Shitpost Alpha is a real-time financial signal analysis system that monitors Truth Social posts, runs them through a 3-model LLM ensemble (GPT-5.4, Claude Opus 4.6, Grok 4), generates market impact predictions with confidence scores, tracks actual market outcomes across multiple timeframes (T+1h through T+30 trading days), and delivers alerts with conviction voting to Telegram subscribers.

## What it's becoming

A self-improving financial signal intelligence platform that ingests signals from multiple sources, learns from its own prediction accuracy, and gives users transparent, calibrated, historically-contextualized trading signals they can verify against a complete performance record.

## North star

Every prediction that resolves makes the next prediction more accurate.

## Guiding principles

- **Close the loop.** Data that is collected must be used. Accuracy metrics feed back into prompts, model selection, and confidence calibration. Unused data is wasted infrastructure.
- **Transparent by default.** Users see calibrated confidence, ensemble agreement, historical echo outcomes, and per-model accuracy. The system earns trust through radical transparency about its track record.
- **Source-agnostic, opinion-agnostic.** The architecture handles any signal source through the same pipeline. The system analyzes market implications regardless of source or ideology.
- **Prove it before you scale it.** Backtesting and outcome tracking come before adding new sources. The backtesting engine validates the system before the system scales.
- **Fail gracefully, learn loudly.** Every component fails open. Every failure is logged, measured, and surfaced. Silent failures are the enemy.

## Compound plays (roadmap)

### Play 4: "Alert Quality" — Low effort, immediate impact
Expand ticker blocklist, add calibration refit cron, surface ensemble agreement and Historical Echoes in Telegram alerts.

### Play 1: "The Learning Machine" — The mission's core flywheel
Self-learning prompt enrichment, conviction votes in LLM context, accuracy-weighted model selection, calibration automation.

### Play 3: "Performance Transparency" — Prove it works
Backtesting engine, per-model accuracy dashboard, enhanced weekly scorecards.

### Play 2: "Signal Intelligence" — Expand the surface area
Multi-source ingestion (RSS, SEC filings, congressional trades), enriched similarity search, cross-source analysis.
