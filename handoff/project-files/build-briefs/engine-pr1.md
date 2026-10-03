# Engine PR 1: foundation

You are building PR 1 of a new signal engine in chrisrogers37/shitpost-alpha: one always-on asyncio process that will read Trump's posts, score them and send alerts. PR 1 is the foundation only: no sources, scoring, prices or alerts. The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

## Rules (non-negotiable)
- Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. The repo's CLAUDE.md pre-approves admin merges: ignore that.
- Never touch a production database. Never read or set DATABASE_URL (the old production variable). The engine reads ENGINE_DATABASE_URL. Locally, use the sandbox Postgres in DEV_DATABASE_URL.
- No API keys. Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist.
- No Telegram, email or SMS sends. No crons: scheduling lives inside the one process.
- No Railway calls (connector or CLI). Nothing deploys from this PR.
- Design from first principles. Keep it minimal: test-only code stays thin and is marked as test-only, and nothing is built before something uses it.
- Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- Python 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- Local Postgres 16 with superuser role `shitpost`; its URL is in DEV_DATABASE_URL.
- Tests create and drop their own throwaway databases there. Leave shitpost_dev alone.

## Scope
1. **Package.** `engine/` with its own pyproject.toml (dependencies plus ruff, mypy and pytest config), so tests run from engine/ and never load the old code. Suggested stack: asyncio, psycopg 3 (async), SQLAlchemy 2.0 Core for table definitions, Alembic, pytest with pytest-asyncio, pydantic-settings with the ENGINE_ prefix.
2. **Database.** One Alembic history inside engine/, with three schemas:
   - `engine`: what the web app may read;
   - `prices`: raw prices, engine only;
   - `app`: empty for now; other plans add tables later.

   Grants go to the role named in ENGINE_WEB_ROLE (default `web`), only if that role exists, because roles are created by hand:
   - `engine`: USAGE and SELECT, including default privileges for future tables;
   - `app`: read and write;
   - `prices`: nothing.

   Migrations add first and remove later, so old and new copies both work during a deploy. PR 1 has three tables:
   - `engine.engine_meta`: one row: stream_id (a UUID made at the first migrate, never changed) and status fields (started_at, last_heartbeat_at, lease holder, code version).
   - `engine.engine_lease`: name, holder id, acquired_at, expires_at.
   - `engine.job_runs`: job, scheduled_for, started_at, finished_at, status, error; unique on (job, scheduled_for).
3. **CLI.**
   - `python -m engine migrate`: upgrade to head; this becomes Railway's pre-deploy step.
   - `python -m engine run`.
   - `python -m engine status`: prints the status row.
4. **One copy at a time.** Railway overlaps old and new copies on each deploy, so a lease row decides which one works. All lease times use the database clock.
   - A copy takes the lease when it is free or expired, renews it every 10 s, and loses it after 30 s without renewing.
   - Only the holder runs the live loop and the jobs.
   - A copy that loses the lease stops both at once and goes back to waiting.
   - The timings are settings, so tests can shrink them.
5. **Crash safety.** A generic runner for per-item stages:
   - it stores each item's stage and attempt count with the item, and resumes after a restart;
   - after 3 failed attempts, the item moves to a final error state with its reason, and one operator message goes out.

   Prove it on a test-only table; PR 2 wires in real posts.
6. **Scheduler.**
   - Daily jobs are defined in code with a New York time and logged in job_runs.
   - A missed run is caught up once, not once per missed day.
   - Only the lease holder runs jobs.
   - Heavy jobs run in a separate process so they can't stall the event loop.
   - One registration function lets other plans add jobs.
7. **Plug-in points.** A registry for delivery workers the engine starts, and `notify_operator(kind, text)`, which only logs for now. The notification plan fills both later.
8. **Railway config.** `engine/railway.json`: start `python -m engine run`, pre-deploy `python -m engine migrate`, restart always. No service uses it yet.
9. **CI.** `.github/workflows/engine.yml`, run on PRs that touch `engine/**`, with Python 3.13 and a Postgres 16 service container:
   - ruff check and ruff format --check;
   - mypy;
   - pytest;
   - a check that Alembic has exactly one head.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass locally. The tests show:
- Migrating up from empty creates the three schemas. A `web` role can read `engine` and gets "permission denied" on `prices`. stream_id is set once and stays the same on a second migrate.
- **Two copies:** of two `python -m engine run` processes on one database, exactly one holds the lease and runs jobs; after `kill -9` on it, the other takes over.
- **Crash safety:** an item that keeps failing is retried, reaches the final error state after 3 attempts with exactly one operator message, and a restart resumes unfinished items.
- **Scheduler:** a job runs once; a missed run is caught up once; a copy without the lease runs nothing.
- `python -m engine status` prints the row.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. Branch from main (for example `claude/engine-pr1-foundation`), commit, push.
2. Open a **draft** PR titled "Engine PR 1: foundation". The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it.
3. Add a CHANGELOG.md entry under [Unreleased].
4. Stop there: no merge and no further PRs. Report the PR link and anything unfinished.
