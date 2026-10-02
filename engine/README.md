# Signal engine

One always-on asyncio process. It holds a lease so only one copy works at a time, reads
Trump's posts from four feeds, runs daily jobs at New York times, and moves items through
crash-safe stages. Nothing here imports the old code in the rest of the repo.

## Commands

Run from this directory, with `ENGINE_DATABASE_URL` set (never the old `DATABASE_URL`):

    python -m engine migrate   # upgrade to head, then grant the web role (Railway pre-deploy)
    python -m engine run       # wait for the lease, then work while holding it
    python -m engine status    # the status row, the lease, each feed's state, signals by stage
    python -m engine import-history   # past posts: CC0 archive copy, then CNN's live file

Settings are `ENGINE_*` variables; see `engine/settings.py`.

## Feeds

`engine/feeds/`: four feeds of Trump's posts polled side by side; the first copy of a post
wins (`engine.signals`), and every feed's first sighting is kept (`engine.signal_sightings`).

| Feed | What | Every |
| --- | --- | --- |
| `direct` | Truth Social's own API | 60 s |
| `trumpstruth` | trumpstruth.org RSS, with `?t=` to skip Cloudflare's cache | 60 s |
| `cnn` | first 32 KB of CNN's archive file (a range read) | 15 s |
| `scrapecreators` | paid API; only with `ENGINE_SCRAPECREATORS_KEY` | 2 min while direct is blocked or off, else hourly |

- `ENGINE_SOURCES_OFF=direct,scrapecreators` switches feeds off; the others carry on.
- A 403, a 429, a challenge page or five failures in a row mark a feed blocked: it backs
  off from 1 minute, doubling up to 30, with one operator message per incident and one on
  recovery. No proxies, rotating addresses, browser impersonation or logins, ever.
- When a read doesn't reach back to the newest stored post, the feed catches up: CNN reads
  its whole file, direct and ScrapeCreators page back. trumpstruth can't page back.
- If no feed answers for 10 minutes, one operator message, and status shows "dark since".
- A post's time comes from its status id (`id >> 16` is milliseconds since the epoch).
- Text posts wait at stage `score` (PR 4). Reposts, posts without text and imported
  history are saved at `done`, with the reason in `not_scored`.

## Database

Three schemas: `engine` (the web role may read it), `prices` (engine only) and `app`
(tables other plans add). The web role's access is the `WEB_GRANTS` map in
`engine/migrate.py`: a PR that adds a table the web app needs adds a line there. Grants
run on every migrate and only if the role in `ENGINE_WEB_ROLE` (default `web`) exists.

Migrations add first and remove later: old and new copies overlap during a deploy, so a
migration must keep the previous release working. New revision:
`alembic revision -m "..."` (writes into `engine/migrations/versions/`).

## Plug-in points

In `engine/registry.py`, `build_registry()`:

- `register_job(name, at, func, heavy=False)`: a daily job at New York time `at`, logged
  in `engine.job_runs`. `heavy=True` runs it in a separate process.
- `register_worker(name, func)`: a long-running task (delivery workers, the live loop),
  run only while this copy holds the lease and restarted if it raises.

`engine.notify.notify_operator(kind, text)` only logs for now.

`engine.stages.StageRunner` moves rows of a table with `stage_columns()` through named
stages, with three attempts per stage before the final `error` state.

## Tests

    pip install -e ".[dev]"
    DEV_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres pytest
    ruff check . && ruff format --check . && mypy

Tests create and drop their own databases on the `DEV_DATABASE_URL` server.
