# Sandbox Postgres for dev and backtests

Chris's rule: development and backtests use the sandbox's own Postgres, never the production database.
Production's DATABASE_URL stays in Railway. Claude sessions have no DATABASE_URL by default.

## Set up (any thread, about 1 minute after deps are cached)

    bash /mnt/project-files/dev-db/setup_dev_db.sh            # repo at /home/claude/shitpost-alpha, venv at /home/claude/venv
    export DATABASE_URL=postgresql://shitpost:<redacted>@localhost:5432/shitpost_dev

What it does, idempotently:
1. Installs pgvector for the preinstalled Postgres 16 (post_embeddings needs `vector`), then starts it.
2. Creates role `shitpost` and database `shitpost_dev` on localhost.
3. Creates a Python 3.13 venv and installs requirements.txt (the repo targets 3.13; the default python3 is 3.11).
4. Builds the schema from all ORM models (13 tables), then applies scripts/001-008_*.sql in order.

Expected noise in step 4: the migrations print errors like "constraint already exists" and
"column shitpost_id does not exist". The ORM already contains most of what they add, and it has
dropped the legacy `predictions.shitpost_id` column. Those errors are harmless. The migrations still
matter: they add 2 FKs to ticker_registry, an index on price_snapshots, and drop 2 dead columns.

Checked 2026-09-30: `python -m shitvault stats` runs against it (read-only, empty DB).

## Things to know

- The sandbox is ephemeral. The database disappears when the container is reclaimed. Anything a later
  thread needs (loaded posts, prices, backtest results) should be saved as files under
  /mnt/project-files/ (CSV/Parquet, or `pg_dump -Fc` into dev-db/dumps/) and reloaded, not left only in Postgres.
- Tests (`pytest`) use SQLite fixtures and don't use this database. Baseline on main (139b145) with
  no API keys: 1959 passed, 9 failed, 40 errors. Most failures need OPENAI_API_KEY, and some try a live LLM call.
- The network policy blocks Yahoo Finance (fc.yahoo.com) and the public Truth Social archives tried
  (ix.cnn.io, trumpstruth.org). pypi works. Loading history needs those hosts allowed or data supplied another way.
