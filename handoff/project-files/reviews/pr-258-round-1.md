# PR #258 "Engine PR 1: foundation": review round 1

Head reviewed: a69a1dd (branch claude/engine-foundation-k6mh6s). Base: main 139b145.
Passes: **simplify** (reuse, simplification, altitude), **review** (correctness bugs and project rules; built-in code-review at high effort plus clauDNA review-work), **verify** (clauDNA verify-completion against /mnt/project-files/build-briefs/engine-pr1.md). Each pass ran in a fresh agent; findings below are merged, de-duplicated and checked against the code.

## Where it stands

- Every requirement in the brief is delivered. Verify re-ran everything fresh: ruff, ruff format, mypy strict clean; pytest 29/29 twice plus 5 more runs of the timing tests with no flakes; one Alembic head (and a two-head control makes the CI check fail); GitHub CI green on a69a1dd.
- CLI behaviour checked on a throwaway database: migrate three times keeps stream_id; a `web` role reads `engine` and is denied on `prices`; with default timings a `kill -9` holder is replaced 25 s later; SIGTERM hands over in 7.5 s; crash-safe stages hold up under real `kill -9` restarts with exactly one operator message per failed item.
- The `app` grant deviation (USAGE plus per-table lines) is accepted.
- Rules all pass: only ENGINE_DATABASE_URL, no key names, no crons or sends, no old-code imports, api/ frontend/ root railway.json and railpack.json untouched, test-only code marked, CHANGELOG entry present.

**Result: changes needed.** 1 blocker, 9 should-fix, 14 nits.

## How to answer

Fix each blocker and should-fix, or decline it with a reason. Nits are optional; take the cheap ones. When you push, send the gauntlet thread (session_013E4KMGG5c9USVygEcNJkqa) the new head commit and one line per finding id: fixed, or declined and why.

Proof-of-bug probes are in [pr-258-round-1-probes/](pr-258-round-1-probes/). They are pytest files that use the PR's own conftest fixtures; copy one into engine/tests/ to run it. Against a69a1dd a passing probe means the bug is real. They were written to prove bugs, not as finished tests: turn the ones you need into proper regression tests (with assertions, without prints), and don't commit them as they are.

---

## Blocker

### B1. A late `acquire()` answer lets a copy work on a lease the database already counts as expired, so two copies can work at once (review)
- **Where:** engine/engine/lease.py:51-53 (`acquire` returns `held` however late the answer comes); lease.py:57-60 (`keep()` sleeps a full `renew` before its first deadline check); lease.py:86-101 (expiry is `now()` + ttl, and `now()` is the transaction start, so it goes stale after any lock wait); engine/engine/runtime.py:46-52 (work starts as soon as `acquire` returns True).
- **Problem:** the step-down guarantee is `_deadline = started + ttl - renew`, but nothing checks it between `acquire()` returning and `keep()`'s first wake-up `renew` seconds later. If the answer arrives more than ttl - renew (20 s) after the statement started, the copy runs workers and jobs for up to 10 s on a row whose `expires_at` is already past, and any other copy polling then takes it too.
- **Realistic trigger:** a pre-deploy `python -m engine migrate` that ALTERs `engine.engine_meta` (say, a new status column) in one slow transaction while the old copy runs. The old copy's lease transaction blocks on its `UPDATE engine_meta`. When the migration commits, `acquire` returns True with an expired `expires_at`, and the new copy starting after pre-deploy takes the row while the old one works. A 20 s network stall or host pause does the same.
- **Evidence:** `test_review_probes.py::test_late_acquire_answer_lets_two_copies_work` asserts both workers ran at the same time (A ran 11 ticks after B started). `test_review_migration_lock.py` (prints, no assert) shows A working from t=3.01 to 3.21 s while the database showed its lease expired 1.3 to 1.5 s earlier. Re-run against a69a1dd in this round: passes, so the bug is real.
- **Fix:**
  1. Reject a late answer: `held = await self._take_or_renew(first=True)`, then `return held and loop.time() + self._renew < self._deadline`. The next poll re-takes the row as "mine" with a fresh deadline. Checked in a scratch copy: both probes show no overlap, and the existing lease, process and scheduler tests still pass.
  2. Move the `engine_meta` heartbeat out of the lease-row transaction, so a lock on `engine_meta` can't hold up the lease.
  3. Bound the lease transaction (see S1).
  4. Add a regression test, built from the late-answer probe.

## Should-fix

### S1. Lease statements have no lock or statement timeout, and `acquire()` has no time bound (review)
- **Where:** lease.py:104 (the transaction); runtime.py:46 (`await lease.acquire()`, unbounded).
- **Problem:** if the old holder is frozen or partitioned mid-renewal with the lease row locked, the waiting copy's `INSERT ... ON CONFLICT` blocks on that row long after expiry. It stays blocked until the server drops the dead session, which can take hours with default keepalives, so no copy works at all. While blocked it also ignores SIGTERM, because `stop` is checked only between acquires.
- **Evidence:** `test_review_lock.py`: one connection holds an uncommitted `UPDATE engine.engine_lease`; after expiry, `b.acquire()` is still blocked when the 5 s probe timeout fires.
- **Fix:** `SET LOCAL lock_timeout` and `statement_timeout` (about `renew`) at the start of the lease transaction, and wrap `acquire()` in `asyncio.timeout(ttl - 2 * renew)` in `run_engine`, treating a timeout as not held. Also let `stop` interrupt a pending acquire.

### S2. A database error while recording a job's result crashes the whole engine, and a job that succeeded then runs again (review)
- **Where:** engine/engine/scheduler.py:130 and :138 (`_finish` called inside `except`/`else`); runtime.py:73-76 (only `LeaseLost` and `_Stopping` are handled).
- **Problem:** during a short Neon blip, `_finish` raises `OperationalError`. That escapes the job task, aborts `Scheduler.run`'s TaskGroup, matches neither `except*` in `_work`, and propagates out of `run_engine` and `asyncio.run`: the process exits, killing every worker and job. The row stays `running`, so after Railway restarts the process the job counts as interrupted and runs a second time. `tick` already tolerates the same errors (scheduler.py:58), so this is inconsistent.
- **Evidence:** `test_review_probes.py::test_finish_error_crashes_run_engine`: `run_engine` raised an ExceptionGroup wrapping `OperationalError`, and the row was left `('running', 1)`.
- **Fix:** in `_execute`, retry `_finish` with a short backoff until it lands or the task is cancelled (at minimum catch `SQLAlchemyError, OSError` and log). Have `_work` treat any other unexpected exception as "stop work, notify once, back off, re-acquire" instead of crashing the process.

### S3. Job retries run back to back, so all 3 attempts are spent in about 30 s (review)
- **Where:** scheduler.py:86-96. The `ON CONFLICT ... WHERE status IN ('running','retry') AND attempts < max` claim has no time condition.
- **Problem:** a job that hits a one-minute upstream outage tries at :00, :15 and :30 (15 s tick), then is marked failed for the day. Only the latest slot is ever considered, so that day's run never happens even though the outage cleared seconds later.
- **Evidence:** `test_review_probes.py::test_job_retries_are_back_to_back`: attempts at 0.0, 0.11 and 0.21 s with tick 0.1.
- **Fix:** a retry delay for `retry` rows, e.g. claim only when `finished_at < now() - retry_delay * attempts`, with `job_retry_seconds` a setting (e.g. 300). Keep the immediate retry for stale `running` rows. Add a test.

### S4. `latest_slot` compares New York wall-clock times, not instants, so DST days go wrong (review)
- **Where:** scheduler.py:39-41. `slot > local` compares two datetimes that share the `NEW_YORK` tzinfo, so Python ignores fold and offset.
- **Problem:** on the fall-back day (2026-11-01) a 01:30 job's slot jumps back to the previous day during the repeated hour, so a copy that was down is caught up twice, the second time with yesterday's `scheduled_for`. On the spring-forward day (2026-03-08) a 02:30 job runs at 03:00 EDT with a `scheduled_for` 30 minutes in the future.
- **Evidence:** `test_review_probes.py::test_latest_slot_goes_backwards_on_fall_back`, `test_latest_slot_in_spring_gap_is_in_the_future`, `test_fall_back_runs_job_twice_in_one_day`. A 5-minute sweep of both 2026 transition days for 7 times: backwards once and future 6 times with the PR code, 0 and 0 with the fix. The current test (tests/test_scheduler.py:21-28) only covers days before and after a change.
- **Fix:** compare instants: `if slot > now:` (`now` is tz-aware, so this compares by instant). Add tests on 2026-03-08 and 2026-11-01 with `at` inside the gap and inside the repeated hour.

### S5. A crash-looping worker sends an operator message on every restart (review)
- **Where:** runtime.py:88-91.
- **Problem:** a worker that raises at once is restarted every `worker_restart_seconds` (30 s) with a `notify_operator` each time: 2,880 messages a day once notifications go to Telegram. Everything else in the PR follows "retry, then one message".
- **Evidence:** `test_review_probes.py::test_crashlooping_worker_messages_every_restart`: 15 `worker_failed` notices in 1.5 s with restart 0.1.
- **Fix:** exponential backoff on the restart sleep (capped), one notice for the first failure of a streak, and a recovery notice once it has stayed up for a while. Add a test asserting one notice for a crash loop.

### S6. Untested: an interrupted job run that reaches max attempts (marked failed, one message) (review)
- **Where:** scheduler.py:101-116, the `gave_up` path.
- **Evidence:** mutation: replacing `if gave_up is not None:` with `if False:` (no failed state, no message) still passes all 29 tests. `test_interrupted_run_is_retried` only seeds `attempts=1`. The PR body claims this behaviour.
- **Fix:** a test that seeds a `running` row with `attempts=3`, runs a pass, and asserts the job never runs, the status is `failed` with "interrupted during attempt 3", and there is exactly one `job_failed` notice after two more passes.

### S7. Untested lease properties the brief asks the tests to show (verify, review)
- **Where:** runtime.py:44-56 and :73-74 (lease loss); lease.py (database clock); tests/test_processes.py (two copies).
- **Problem and evidence:**
  - Losing the lease mid-run is never tested. Verify drove `run_engine` directly and it works (worker and job cancelled together, heavy child killed, copy waits, retakes once the other row expires, attempts goes to 2), but no test pins it.
  - "All lease times use the database clock" is untested: a mutation that switches to the host clock (`datetime.now(UTC)`) passes all 29 tests.
  - The two-process test's "only the holder ran the job" check carries no weight: a mutation where the scheduler runs in every copy regardless of the lease still passes it, because the unique `(job, scheduled_for)` row hides the second scheduler. Only the in-process `test_copy_without_the_lease_runs_nothing` catches it.
- **Fix:**
  - Add `test_losing_the_lease_stops_jobs_and_workers_then_waits`: register a worker and a hanging job that record start and cancellation; run `run_engine`; `UPDATE engine.engine_lease SET holder='intruder', expires_at=now()+interval '1.5 seconds'`; assert both were cancelled within about ttl, the job row is still `('running', 1)`, the worker doesn't restart while the intruder holds the row; after expiry assert the copy holds the lease again, the worker started twice and attempts is 2; then stop and assert no lease row is left.
  - Pin the database clock: e.g. a test that skews the database clock (a `now()` shadowed via search_path, or comparing `expires_at - acquired_at` with a host clock deliberately offset) and asserts `expires_at` follows the database.
  - Make the two-copy check meaningful: have the probe job record which copy ran it, or use a worker (not a job) as the "only the holder works" signal.

### S8. A database role named `engine` makes `engine` the default schema, so a table created without a schema becomes web-readable (review)
- **Where:** engine/engine/migrations/env.py:13 and engine/engine/db.py:18-23 (no `search_path` pinned); .github/workflows/engine.yml (`POSTGRES_USER: engine`, and the PR calls `engine` the likely production role); tests/test_migrate.py:101-105 works around it in one test only.
- **Problem:** with `search_path = "$user", public`, a later migration that forgets `schema=` puts its table in `engine`, and `ALTER DEFAULT PRIVILEGES IN SCHEMA engine GRANT SELECT` hands it to the web role behind the public read API. Separately, `alembic revision --autogenerate` run as that role emits three spurious `add_table` ops.
- **Evidence:** `test_review_searchpath.py`: an unqualified `CREATE TABLE telegram_subscribers` lands in `engine` and the web role reads its row. `test_review_autogen.py`: `['add_table', 'add_table', 'add_table']`.
- **Fix:** pin the search path on every engine connection (e.g. `connect_args={"options": "-c search_path=public"}` in `make_engine`, `make_sync_engine` and env.py), then drop the test-only workaround.

### S9. An item at a stage this copy doesn't know is failed with an operator message (review)
- **Where:** engine/engine/stages.py:109 (`_unknown_stage`).
- **Problem:** this goes against the brief's add-first/remove-later rule ("old and new copies both work during a deploy"). If the lease goes back to an older copy during a deploy overlap or a rollback, that copy errors out every item at a stage the newer release added, permanently, with a message per item.
- **Evidence:** a probe produced `(1, 'error', 3, "added_by_newer_release: ValueError: unknown stage ...")` with one notice.
- **Fix:** select only rows whose stage is in `self._handlers` (they stay for a copy that knows them), count no attempt for them, and log once per unknown stage.

## Nits (optional)

- **N1. A heavy job whose process dies is reported as `EOFError: `** (scheduler.py:171-172; review). `receiver.poll()` is True at EOF, so `recv()` raises and the "exited with code" branch never runs; an OOM-killed job's operator message says only "EOFError: ". Probe: `test_heavy_child_death_reports_eoferror`. Fix: `try: error = receiver.recv()` / `except EOFError: error = f"exited with code {process.exitcode}"`.
- **N2. Settings accept zero or negative timings and `max_attempts=0`** (settings.py:25-30; review). `max_attempts=0` fails every stage item without running it. Fix: `Field(gt=0)` on timings, `Field(ge=1)` on `max_attempts`.
- **N3. The heavy-job pickling check is wrong both ways** (registry.py:52; review). A module-level lambda passes the check and then fails to pickle at run time (burning 3 attempts); a picklable `functools.partial` is rejected. Fix: `pickle.dumps(func)` at registration.
- **N4. `running`/`retry` rows of an older slot are never closed** (scheduler.py:68-75; review). Fix: when claiming a new slot, mark that job's older open rows `failed` ("superseded") with one notice.
- **N5. No per-job timeout** (scheduler.py:69-70; review, reasoning only). A hung job keeps its name in `_running`, so every later day is skipped silently. Fix: a `job_timeout_seconds` setting and `asyncio.timeout` around the job, counted as a failed attempt.
- **N6. The lease shares the app's connection pool** (db.py:19, runtime.py:33-41; review). With 15 pooled connections busy, the holder stepped down after 0.62 s on a healthy database (`test_review_pool.py`). Matters from PR 2 on, since stage handlers hold a transaction across the handler. Fix: give the lease its own engine (`pool_size=1, max_overflow=0`).
- **N7. Subprocess test env duplicates the fixture timings and leaves out `web_role`** (tests/test_processes.py:20-31, 156-165; simplify). The subprocess `migrate` (line 148) grants to a real `web` role on the developer's server if one exists. Fix: build the env from the fixture, `{f"ENGINE_{k.upper()}": str(v) for k, v in settings.model_dump().items()}`, and let the missing-URL test reuse `cli()` with its own environ.
- **N8. Parameters nothing uses** (simplify): `Lease(name=...)` (lease.py:41, 44, 72, 88; cli.py already uses `LEASE_NAME`), `configure_logging(level)` (logs.py:6), `StageRunner(batch_size)` (stages.py:55, 66, 77; make it a module constant), `pool_size=5` (db.py:19, the default). Also stages.py:72-80 folds to `pending = (await conn.execute(query)).scalars().all()`. Skip the `pool_size` part if you take N6.
- **N9. `probe_db` fixture writes `CREATE TABLE job_pids` in raw SQL** (tests/test_processes.py:97-101; simplify) though tests/helpers.py:13-18 already defines it. Fix: `await helpers.create_test_tables(db)`.
- **N10. `lease_row` returns a dict, forcing two `# type: ignore[operator]`** (tests/test_lease.py:19-22, 30, 36; simplify). Fix: return the `Row` and use attributes.
- **N11. The 10 s / 30 s / 3 defaults aren't pinned by a test** (settings.py:25-26; verify). Fix: `assert (s.lease_renew_seconds, s.lease_ttl_seconds, s.max_attempts) == (10.0, 30.0, 3)` for `s = Settings(database_url="x")`.
- **N12. CI and packaging** (review): `pg_isready` health check without `-U engine` logs `role "root" does not exist` every run (engine.yml); ruff and mypy are unpinned, so a new ruff release can fail `ruff format --check` on unrelated PRs (pyproject.toml:19-24); `database_url` as `SecretStr` would make "secrets never printed" structural (settings.py:14).
- **N13. `engine_meta.lease_holder` keeps the last holder after a release or kill** (lease.py:67-74; verify). `status` covers it with its live lease line, but a reader of `engine_meta` alone (the web app can read it) sees a stale holder. Fix: clear it on release, or document that `last_heartbeat_at` is the liveness signal.
- **N14. Missing docstrings** on several public functions and classes (cli.py `main`, db.py `make_engine`/`make_sync_engine`, logs.py, migrate.py `alembic_config`/`migrate`/`grant_statements`, runtime.py `holder_id`, classes `Lease`, `Scheduler`, `StageRunner`; review). The repo CLAUDE.md asks for docstrings on public functions.

## For later, no change needed now

- **Railway shutdown timing (PR 7):** unconfirmed from here (Railway docs are blocked in the sandbox). If Railway SIGKILLs right after SIGTERM, the release never runs and each deploy waits about 40 s for takeover; and a start command run through a shell may not forward SIGTERM. Worth checking when the service is created, e.g. `deploy.drainingSeconds` in engine/railway.json.
- **Blocking non-heavy jobs** defeat the step-down (no fencing token); heavy jobs exist for this. A design note for later PRs.

## Dropped

Considered and not backed by the code: a pipe file-descriptor leak on cancelled heavy jobs (fd count stayed flat over 8 cancellations); `grant_statements` not validating privileges per target type (CI's real grants test catches a bad line); per-tick upsert cost; caching finished job slots; merging the scheduler's and stage runner's retry logic; the double row read in `StageRunner._step`.
