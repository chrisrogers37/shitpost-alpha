# AGENTS.md

## Cursor Cloud specific instructions

This section captures durable, non-obvious setup/run details for future cloud agents.
The VM snapshot already has Python deps (in `./venv`)
and a local PostgreSQL 16 + pgvector installed. The startup update script only refreshes those
dependencies — it does **not** start services. See `README.md` / `CLAUDE.md` for standard,
already-documented commands (tests, stats, pipeline CLIs); the notes below only cover things
that are not obvious from those docs.

### Services overview
- **Web service** (`engine/engine/web/`, `python -m engine web` from `engine/`) — the public read API under `/api/v1` and `/healthz`. Runs on port **8000** (`PORT` changes it). See `engine/README.md`.
- **Pipeline workers** (`shitposts/`, `shitvault/`, `shitpost_ai/`, `shit/market_data/`, `notifications/`) — cron/one-shot batch jobs (not servers). They require real external credentials (ScrapeCreators, OpenAI, AWS S3) and are **not** needed to run or test the dashboard. Do not run production/backfill modes without explicit user approval (see `CLAUDE.md`).

### Python environment
- Use the project venv: `./venv/bin/python`, `./venv/bin/pytest`, `./venv/bin/uvicorn`. VM Python is 3.12 (repo docs say 3.13; 3.12 works fine).

### Database: the dashboard requires PostgreSQL, not the default SQLite
- `DATABASE_URL` defaults to `sqlite:///./shitpost_alpha.db`, which is enough to import modules and run the test suite. The web service never reads it: it reads `WEB_DATABASE_URL`, a Postgres URL for the engine database's web role, and its tests need `DEV_DATABASE_URL` (see `engine/README.md`).
- A local Postgres is provisioned: database `shitpost_alpha`, role `shitpost` / password `shitpost`, with the `vector` extension enabled. The repo-root `.env` (gitignored) points `DATABASE_URL` at it and sets `ENVIRONMENT=development`.
- Postgres does not auto-start on boot. Start it with: `sudo pg_ctlcluster 16 main start`.
- Create/refresh the schema (also needs the pgvector extension for the `post_embeddings` table): `./venv/bin/python -c "from shit.db.sync_session import create_tables; create_tables()"`.

### Running the app (development)
- Start Postgres first (above), then:
  - Web service: `WEB_DATABASE_URL=<engine database, as the web role> python -m engine web` in `engine/` (port 8000).
- Health check: `curl http://localhost:8000/healthz` → `{"ok": true}`.
- Unknown paths under `/api/` return a JSON 404 (`{"error": {"code": "not_found", ...}}`).

### Tests, lint, build
- Tests: `./venv/bin/python -m pytest -c shit_tests/pytest.ini` (config lives in `shit_tests/pytest.ini`, not repo root). ~1976 tests pass. The heavy `shit_tests/requirements-test.txt` is **not** required — nothing in the suite imports moto/faker/etc.; base `requirements.txt` is sufficient.
- Known pre-existing failures (not environment issues): several `shitpost_ai` analyzer/ensemble tests instantiate `LLMClient` (via the module-level `settings` singleton captured at import) and `LLMClient.initialize()` makes a **live** OpenAI call, so they need a real, valid `OPENAI_API_KEY` in the process env; a few `events/consumers` async-mock tests and `test_performance.py` timing tests also fail independent of setup.
- Lint: there is **no** Python linter configured (CLAUDE.md mentions `ruff`, but it is not in `requirements.txt`).
