# PR #258 "Engine PR 1: foundation": review round 2

Reviewed: be04d50 ("fold in gauntlet round 1 findings") and the test-only 6f28906 on top. Round 1: [pr-258-round-1.md](pr-258-round-1.md).
Passes: **verify** on the whole PR (clauDNA verify-completion: brief plus every round-1 id, with a revert-the-fix mutation for each named test) and **review** of the new commit (built-in code-review at high effort plus clauDNA review-work, the round-1 probes adapted to the new API, new probes, mutations). Each ran in a fresh agent.

## Where it stands

- Every brief requirement still holds. ruff, ruff format and mypy strict are clean; pytest 55/55 on several runs, as `shitpost` and as a superuser named `engine` like CI, at be04d50 and at 6f28906; one Alembic head; CI green on both commits.
- By hand at default timings: `kill -9` on the holder, takeover 27.4 s later (the row had 27.3 s left); SIGTERM exits in 0.18 s and the next copy holds the lease 7.6 s later; settings errors print field names only, and no output carries the URL or password.
- Round 1's blocker and should-fix items are all fixed for the causes reported: every round-1 bug probe now fails, and each named regression test catches a revert of its fix (B1, S1-S9). Nits N1-N4, N6-N12 and N14 are in; N13 is documented.
- **Declines accepted.** S8 at runtime: runtime queries all name `schema="engine"` and run no DDL, and a session `SET` doesn't survive a transaction pooler, so pinning where tables get created is enough. N5: no job exists yet to size a timeout for. Two small asks follow from these in the nits (N10).

**Result: changes needed.** The new code has 1 blocker, 2 should-fix and 10 nits.

## How to answer

As before: fix each blocker and should-fix or decline it with a reason; nits are optional. When you push, send the gauntlet thread (session_013E4KMGG5c9USVygEcNJkqa) the new head and one line per id. Please tell the PR 2 builder too, since #259 merges your branch.

Probes: [pr-258-round-2-probes/](pr-258-round-2-probes/). `test_r2_swallow.py`, `test_r2_reset.py`, `test_r2_cancel.py` and `test_r2_new.py` assert the correct behaviour, so a failing probe means the bug is real (re-checked here: `test_r2_swallow.py` fails at be04d50). `test_zz_verify_scratch.py` holds four ready-to-port tests for fixes that have none yet (N5 below). Copy into engine/tests/ to run; don't commit them as they are.

---

## Blocker

### B1. Retry loops can swallow a cancellation, so a copy can wedge: not working, not stepping down, ignoring SIGTERM, while its heartbeat says it is alive (review)
- **Where:** four loops that catch `(SQLAlchemyError, OSError)` and carry on: engine/engine/lease.py:76-82 (`_renew_until_answered`), engine/engine/runtime.py:145 (`_heartbeat`), engine/engine/scheduler.py:66 (`Scheduler.run`), engine/engine/scheduler.py:206 (`_record`).
- **Problem:** psycopg can turn a cancellation into a database error. If the connection drops while it waits out a cancel, it raises `OperationalError` instead of `CancelledError`; a cancel during the pool's first connection setup comes out as `ProgrammingError: Explicit rollback() forbidden within a Transaction context`. These loops catch that and keep going:
  - `keep()`'s `timeout_at(deadline)` never sees its cancellation arrive, so it never raises `LeaseLost` while the database is unreachable.
  - The heartbeat keeps `_work`'s TaskGroup open forever after a lease loss or a stop, so the copy never retakes the lease and ignores SIGTERM, while still advancing `last_heartbeat_at`, the documented liveness signal.
- **Scenario:** a Neon compute restart or a stall of more than about 10 s that ends in connection resets, or a SIGTERM during a slow first connection (a Neon cold start). With one copy the engine is silently down with a live-looking status row, and Railway won't restart it because the process is still running. During a deploy overlap the old copy can keep working beside the new one.
- **Evidence:**
  - `test_r2_reset.py::test_a_network_fault_does_not_wedge_the_copy`: a proxy stalls, drops and then heals the connection. After it healed, the lease row was still the intruder's, `last_heartbeat_at` kept advancing, "lost the lease" was never logged, and stop was ignored for 5 s.
  - `test_r2_reset.py::test_a_dropped_connection_during_step_down_still_steps_down`: `keep()` hadn't stepped down 11.1 s past its deadline; the other copy had taken the row 10.1 s earlier; 50 renewal retries.
  - `test_r2_swallow.py::test_stop_during_the_first_connection_is_not_ignored` (deterministic): the heartbeat logs "Explicit rollback() forbidden" and stop is ignored for 8 s or more. Re-run here against be04d50: fails.
  - The same hang appeared by itself in 5 of 13 runs of an always-failing-scheduler probe.
- **Fix:**
  1. In each of those `except` blocks, re-raise when the task is being cancelled, e.g. `if (task := asyncio.current_task()) and task.cancelling(): raise asyncio.CancelledError`. A small shared helper keeps the four alike.
  2. In `keep()`, also raise `LeaseLost` when `loop.time() >= self._deadline`, whatever the inner call did.
  3. Tests where `_take_or_renew` and the heartbeat turn their cancellation into `OperationalError`: the copy still steps down and still stops.
  4. PR 2's feed loops have the same pattern (`except Exception` in `FeedPoller.poll`, and `_run_feed`); its round 2 asks for the same fix there.

## Should-fix

### S1. The step-down waits for psycopg's cancel, so a stalled holder stops up to 10 s after its deadline (review)
- **Where:** lease.py:55-65 (`keep()`), and the settings validator at settings.py:41.
- **Problem:** `LeaseLost` is raised only after the cancelled call returns. A cancelled psycopg query can take up to 10 s to return (5 s for the cancel request, 5 s waiting for the query). At the 30/10 defaults the holder stops right at expiry, with zero margin; at other valid settings another copy takes the row first.
- **Evidence:** `test_r2_new.py::test_a_stalled_holder_stops_before_another_copy_takes_the_row`, with A's connection blackholed: A stopped 10.0 s after its deadline every time. ttl 1 / renew 0.2: B took the row 9.8 s before A stopped. ttl 12 / renew 4 (valid): 6.0 s before. ttl 30 / renew 10: no overlap seen, zero margin.
- **Fix:** run each renewal as its own task, `asyncio.wait` it until the deadline, and on timeout cancel it without awaiting and raise `LeaseLost` at once; `run_engine` awaits any leftover renewal before `release()`. With that, B1's step 2 holds even when the driver is slow to give up.

### S2. A false "engine_recovered" during the engine's own back-off (review)
- **Where:** runtime.py:97-112 (`_hold`). It waits out the back-off inside `except` and only cancels the `healthy` timer in `finally`, after the wait. `_supervise` (runtime.py:150-165) gets this right.
- **Scenario:** once the back-off reaches its 900 s cap, the healthy timer fires during the wait, sends `engine_recovered` and resets the streak. A broken release then sends a failed/recovered pair about every 30 minutes (about 94 messages a day), and the back-off never stays at the cap.
- **Evidence:** `test_r2_new.py::test_engine_crash_loop_sends_one_message`: 4 `engine_failed` and 3 `engine_recovered` notices in 3 s, in 3 of 3 runs; expected 1 and 0.
- **Fix:** cancel `healthy` before the wait, as `_supervise` does, and add a test.

## Nits (optional)

- **N1. `_record` retries permanent errors forever** (scheduler.py:195-208). A NUL byte in a job's error text left the row `running` with 15 retries in 1.5 s (`test_r2_new.py::test_an_error_text_with_a_nul_byte_does_not_wedge_the_job`). Fix: retry only connection errors (`OperationalError`, `InterfaceError`, or `exc.connection_invalidated`), and strip NULs and cap the error text before writing it.
- **N2. `keep()` sleeps a full `renew` after each answer** (lease.py:60), so one slow answer eats into the next renewal's window. Fix: sleep until `last renewal start + renew`.
- **N3. The unknown-stage check scans the whole table on every pass** (stages.py:84-92, `SELECT DISTINCT stage ... WHERE stage NOT IN (...)`), with no index. PR 2's signals table has 36k rows and grows. Fix: a partial index on `stage` for unfinished rows, or check unknown stages once per start.
- **N4. Superseding a `retry` row says "never finished" and overwrites its last error** (scheduler.py:95, 143). Fix: keep the last error and append "superseded".
- **N5. Fixes no committed test pins** (verify, review). Each of these can be reverted with the suite still green:
  - the step-down margin: a deadline of `started + ttl` still passes `test_holder_steps_down_before_its_lease_expires` (test_lease.py:91);
  - the server-side `lock_timeout`/`statement_timeout` on their own (the client timeout covers for them);
  - the restart back-off growth: test_runtime.py:122 asserts only `starts >= 3`, and a constant back-off passes (with doubling it starts 4 times in 1 s, constant 10); use `assert 3 <= starts <= 6`;
  - the separate lease pool (runtime.py:68): `lease_db = db` passes all 55;
  - the heartbeat kept apart from the lease (B1 of round 1): no test locks `engine_meta`;
  - stop during a blocked acquire (runtime.py:77, 180-189).

  `test_zz_verify_scratch.py` has ready-to-port versions of the last four: 15 app connections held for 3x ttl while the holder keeps renewing; `engine_meta` locked for 3x ttl while the lease still renews; `run_engine` returning in under 1 s when stopped during a blocked acquire; `_take_or_renew` against a stuck row raising `OperationalError` matching "(lock|statement) timeout".
- **N6. Docstrings still missing** on `JobContext` (registry.py:26), `Job` (registry.py:35), `Stage` (stages.py:46) and `Settings.db_url` (settings.py:48).
- **N7. PR body says "Timings must be positive"**, but `job_retry_seconds` allows 0 (settings.py:28). Reword one or the other.
- **N8. engine/README.md:28** is 111 characters; rewrap.
- **N9. `status` and `migrate` print a raw traceback** when the database is unreachable or the password is wrong (cli.py:46-52, 63-75). Optional: catch `OperationalError` in `main` and print one line (no URL).
- **N10. Notes the declines leave for later**, a README line each: a hung job is silent forever (it's skipped while it runs, so "superseded" never reaches it), so whoever adds the first job adds `job_timeout_seconds`; and the migration `SET LOCAL search_path` covers one migration transaction only, so run migrations on Neon's direct (unpooled) endpoint, or later `ALTER ROLE <engine role> SET search_path = public`.

## Dropped

Checked and not backed: a stale holder written by a late heartbeat; `_fail` lacking a stage guard; flakiness in the stuck-transaction test (12 extra runs clean); the URL leaking through a settings error (pydantic truncates the input; `alembic current` printed the password 0 times). Every URL consumer, including the heavy-job child and the subprocess tests, still gets the URL after the `SecretStr` change.
