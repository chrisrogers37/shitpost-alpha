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

Settings are `ENGINE_*` variables; see `engine/settings.py`. New database connections
give up after 10 s; a `connect_timeout` in the URL wins. In `engine.engine_meta`,
`last_heartbeat_at` shows whether a copy is working; `lease_holder` names the last holder
and is not cleared when it stops.

## Feeds

`engine/feeds/`: four feeds of Trump's posts polled side by side; the first copy of a post
wins (`engine.signals`), and every feed's first sighting is kept (`engine.signal_sightings`).

| Feed | What | Every |
| --- | --- | --- |
| `direct` | Truth Social's own API | 60 s |
| `trumpstruth` | trumpstruth.org RSS, with `?t=` to skip Cloudflare's cache | 60 s |
| `cnn` | first 32 KB of CNN's archive file (a range read; a 200 is a failure) | 15 s |
| `scrapecreators` | paid API; only with `ENGINE_SCRAPECREATORS_KEY` | 2 min while direct is blocked or off, else hourly |

- `ENGINE_SOURCES_OFF=direct,scrapecreators` switches feeds off; the others carry on.
- A 403, a 429, a challenge page or five failures in a row mark a feed blocked: it backs
  off from 1 minute, doubling up to 30 (never sooner than its usual interval), with one
  operator message per incident and one on recovery. No proxies, rotating addresses,
  browser impersonation or logins, ever. An answer of an unexpected shape is a failure;
  one odd item in an answer is skipped and logged. A poll that fails for any other reason
  (a post the database refuses, a bug) counts as an error and shows in status.
- `engine/http_client.py` is the one HTTP client for anything the engine fetches: honest
  User-Agent, no redirects, connections kept 75 s so the feeds polled every 15 or 60 s
  reuse one.
  API keys are stripped of a pasted space or newline and must be printable ASCII; error
  text blanks every key header (`SECRET_HEADERS`), so a key never reaches a log, a status
  row or an operator message.
- Each feed has a catch-up mark (the newest post it has read without a gap). A read that
  doesn't reach back to it catches up first: CNN reads its whole file, direct and
  ScrapeCreators page back (ScrapeCreators only while it stands in for direct).
  trumpstruth can't page back. A failed catch-up keeps the new posts, leaves the feed up
  (a refusal counts as a block in its stats) and tries again after a back-off; status
  shows why it is owed. A feed switched back on starts from the newest stored post, so it
  doesn't fill a gap left while it was off.
- `engine.feed_status` keeps each feed's state, back-off, last poll and mark, so the next
  copy (a deploy, a restart) carries on without re-polling a blocked host.
- If no feed answers for 10 minutes, one operator message, and status shows "dark since".
- A post's time comes from its status id (`id >> 16` is milliseconds since the epoch).
  NULs and lone surrogates are dropped from a post's text and payload (Postgres refuses
  them), and a post dated more than a day ahead is skipped as odd.
- Text posts wait at stage `score` (PR 4). Reposts, posts without text and imported
  history are saved at `done`, with the reason in `not_scored`. `import-history` checks
  the database before it downloads anything and leaves posts under an hour old to the
  live feeds.

## Database

Three schemas: `engine` (the web role may read it), `prices` (engine only) and `app`
(tables other plans add). The web role's access is the `WEB_GRANTS` map in
`engine/migrate.py`: a PR that adds a table the web app needs adds a line there. Grants
run on every migrate and only if the role in `ENGINE_WEB_ROLE` (default `web`) exists.

Migrations name the schema of every table. They run with `search_path` pinned to
`public`, so a table that forgets its schema lands in `public`, never in `engine` where
the web role could read it. The pin is a `SET LOCAL` in the migration transaction, so on
Neon run `migrate` against the direct (unpooled) endpoint, or set
`ALTER ROLE <engine role> SET search_path = public` once.

Migrations add first and remove later: old and new copies overlap during a deploy, so a
migration must keep the previous release working. New revision:
`alembic revision -m "..."` (writes into `engine/migrations/versions/`).

## Plug-in points

In `engine/registry.py`, `build_registry()`:

- `register_job(name, at, func, heavy=False)`: a daily job at New York time `at`, logged
  in `engine.job_runs`. A failed or interrupted run is retried up to `ENGINE_MAX_ATTEMPTS`
  times, then marked failed with one operator message. `heavy=True` runs it in a
  separate process. There is no job timeout yet: a hung job is skipped silently while it
  runs, so whoever adds the first real job adds `ENGINE_JOB_TIMEOUT_SECONDS` with it.
- `register_worker(name, func)`: a long-running task (delivery workers, the live loop),
  run only while this copy holds the lease and restarted with backoff if it raises (one
  operator message per failure streak).

`engine.notify.notify_operator(kind, text)` only logs for now.

`engine.stages.StageRunner` moves rows of a table with `stage_columns()` through named
stages, with `ENGINE_MAX_ATTEMPTS` attempts per stage before the final `error` state.
Rows at a stage this copy doesn't know are left alone (a newer copy may know it).

## Tests

    pip install -e ".[dev]"
    DEV_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres pytest
    ruff check . && ruff format --check . && mypy

Tests create and drop their own databases on the `DEV_DATABASE_URL` server.
