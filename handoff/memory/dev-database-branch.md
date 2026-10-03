---
name: dev-database-branch
description: Dev/backtest DB is the sandbox's own local Postgres (not Neon); recipe at /mnt/project-files/dev-db/; backtest data from public hosts
metadata:
  type: project
  modified: 2026-09-30T17:57:42.625Z
---

Decision (Chris, 2026-09-30): development and backtests use the sandbox's own Postgres, never the production DB. The Neon dev-branch idea was dropped. Production DATABASE_URL lives only in Railway; Claude sessions have none.

Recipe: `bash /mnt/project-files/dev-db/setup_dev_db.sh` then `export DATABASE_URL=postgresql://shitpost:shitpost@localhost:5432/shitpost_dev`. See /mnt/project-files/dev-db/README.md (pgvector install, py3.13 venv, ORM create_all + scripts/001-008, expected migration errors).

Also from Chris: prove the free scraper where it will run (Railway), not in the sandbox, because cloud sessions egress via Anthropic's proxy.

Backtest data (settled 2026-09-30 in the "Plan the signal engine" thread): Yahoo via yfinance, loaded into the sandbox Postgres. The project's default environment (shitpost-alpha, since 2026-09-30 13:55Z) already allows ix.cnn.io, trumpstruth.org, www.trumpstruth.org and the Yahoo hosts (fc, query1, query2, finance, guce, consent), plus pypi, npm, GitHub and Ubuntu. Threads started before that switch run on the old environment and see those hosts as blocked. Don't ask Chris to add hosts.

**Why:** project constraint is never touch production. The sandbox DB is ephemeral.
**How to apply:** run the recipe at the start of any DB work and save datasets and results as files under /mnt/project-files. See [[repo-facts]].
