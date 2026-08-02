# AGENTS.md

## Cursor Cloud specific instructions

This section captures durable, non-obvious setup/run details for future cloud agents.
The VM snapshot already has Python deps (in `./venv`), frontend deps (`frontend/node_modules`),
and a local PostgreSQL 16 + pgvector installed. The startup update script only refreshes those
dependencies — it does **not** start services. See `README.md` / `CLAUDE.md` for standard,
already-documented commands (tests, stats, pipeline CLIs); the notes below only cover things
that are not obvious from those docs.

### Services overview
- **FastAPI backend** (`api/main:app`) — serves the JSON API and, when `frontend/dist` exists, the built React SPA. Runs on port **8000**.
- **React + Vite frontend** (`frontend/`) — dev server on port **5173**; `vite.config.ts` proxies `/api` and `/telegram` to `http://localhost:8000`, so the backend must be on 8000.
- **Pipeline workers** (`shitposts/`, `shitvault/`, `shitpost_ai/`, `shit/market_data/`, `notifications/`) — cron/one-shot batch jobs (not servers). They require real external credentials (ScrapeCreators, OpenAI, AWS S3) and are **not** needed to run or test the dashboard. Do not run production/backfill modes without explicit user approval (see `CLAUDE.md`).

### Python environment
- Use the project venv: `./venv/bin/python`, `./venv/bin/pytest`, `./venv/bin/uvicorn`. VM Python is 3.12 (repo docs say 3.13; 3.12 works fine).

### Database: the dashboard requires PostgreSQL, not the default SQLite
- `DATABASE_URL` defaults to `sqlite:///./shitpost_alpha.db`, which is enough to import modules and run the test suite, **but the dashboard feed query is PostgreSQL-specific** (JSON `->>`/`->` operators, `::int` / `::text` casts, `COUNT(*) OVER()`), so `GET /api/feed/at` returns **500 on SQLite**. Use Postgres for any real dashboard work.
- A local Postgres is provisioned: database `shitpost_alpha`, role `shitpost` / password `shitpost`, with the `vector` extension enabled. The repo-root `.env` (gitignored) points `DATABASE_URL` at it and sets `ENVIRONMENT=development`.
- Postgres does not auto-start on boot. Start it with: `sudo pg_ctlcluster 16 main start`.
- Create/refresh the schema (also needs the pgvector extension for the `post_embeddings` table): `./venv/bin/python -c "from shit.db.sync_session import create_tables; create_tables()"`.

### Running the app (development)
- Start Postgres first (above), then:
  - Backend: `ENVIRONMENT=development ./venv/bin/uvicorn api.main:app --reload --host 0.0.0.0 --port 8000` (it reads `.env`).
  - Frontend: `npm run dev` in `frontend/` (port 5173).
- Health check: `curl http://localhost:8000/api/health` → `{"ok": true, ...}`.
- Feed endpoint is `GET /api/feed/at?offset=0` (0 = latest). It only returns posts with a `completed` prediction and non-empty `assets`; an empty DB yields 404.
- Gotcha: because the backend mounts a catch-all SPA route (`/{full_path:path}`) whenever `frontend/dist` exists, requests to **wrong** API paths return the SPA `index.html` (HTML) rather than a JSON 404. Double-check exact route paths when an endpoint "returns HTML".
- `frontend/dist` is a build artifact; running `npm run build` regenerates it and makes the backend serve the SPA at `/`. For hot-reload frontend dev, use the Vite dev server on 5173 instead.

### Tests, lint, build
- Tests: `./venv/bin/python -m pytest -c shit_tests/pytest.ini` (config lives in `shit_tests/pytest.ini`, not repo root). ~1976 tests pass. The heavy `shit_tests/requirements-test.txt` is **not** required — nothing in the suite imports moto/faker/etc.; base `requirements.txt` is sufficient.
- Known pre-existing failures (not environment issues): several `shitpost_ai` analyzer/ensemble tests instantiate `LLMClient` (via the module-level `settings` singleton captured at import) and `LLMClient.initialize()` makes a **live** OpenAI call, so they need a real, valid `OPENAI_API_KEY` in the process env; a few `events/consumers` async-mock tests and `test_performance.py` timing tests also fail independent of setup.
- Lint: there is **no** Python linter configured (CLAUDE.md mentions `ruff`, but it is not in `requirements.txt`). Frontend typecheck/build: `npm run build` (`tsc -b && vite build`) in `frontend/`.
