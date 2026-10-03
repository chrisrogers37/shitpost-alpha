# PR #258 "Engine PR 1: foundation": round 4 (review + verify) at 99fe7bb

Scope: `git diff f4194b7 99fe7bb` (16 files, +405/-80), reviewed with the built-in code-review skill at high effort plus clauDNA review-work dimensions; the whole PR verified per clauDNA verify-completion. Every claim below comes from a command I ran in this session.

Trees: the read-only checkout `scratchpad/pr258-r4` (HEAD 99fe7bba…; `git status --porcelain --ignored` unchanged after my pytest runs; see Cleanup for caches another agent added later) for ruff, mypy, pytest x3, the S3 loop, the Alembic check and every by-hand run (all with `PYTHONDONTWRITEBYTECODE=1`, no caches). Probes and mutations ran in my copy `scratchpad/review-258-r4`; a probe printed `engine.__file__` = `…/review-258-r4/engine/engine/__init__.py`, and the mutation harness restores each file with `git checkout` and asserts `git diff --quiet` after every mutation.

**Result: round 3 is fixed.** S1, S2, S3, N1, N2 and N4 are fixed and each fix is pinned by a committed test that fails when it is reverted. N3 and N5 are partly done. No blocker and no should-fix. The new findings below are all nits: test gaps, wording, and edge cases with no safety impact (no path lets two copies work at once or loses a recorded result).

## (a) Round-3 items

| Id | Status | Evidence |
|---|---|---|
| S1 connect timeout, bounded release | **Fixed** | db.py:27-49 passes `connect_timeout=10` to `make_engine`, `make_sync_engine`, and so env.py:13 (now `make_sync_engine`) and `migrate()`'s grant engine; psycopg receives it as a conninfo kwarg (async and sync both read it in `timeout_from_conninfo`). A URL `connect_timeout` makes `_connect_args` return `{}`, so the URL's value reaches psycopg (test_processes uses `connect_timeout=2` this way: 2 s per command). Mutations: dropping it from the async engine, the sync engine, or env.py alone each fail `test_db::test_new_connections_time_out`. release(): lease.py:83 never-held return (mutation fails `test_release_does_nothing_if_the_lease_was_never_held`), lease.py:86 `asyncio.timeout` (mutation fails `test_release_gives_up_in_time_if_the_database_stalls`). By hand at defaults: `status`/`migrate` against a silent port print one line `could not reach the engine database: connection timeout expired` after 10.6 s, rc 1, no password/URL; SIGTERM on a copy whose connections go to a silent port exits in 0.16 s (4 s in) and 0.11 s (12 s in); SIGTERM on a holder whose lease row another session has locked exits in 10.15 s (round 3: 45 s, until the lock went). Caveats: lease.py:90's lock/statement timeouts in release are unpinned (redundant with the asyncio timeout); the 10 s is per address (F7); with a frozen network release takes 20 s, not 10 (F6). |
| S2 busy pool reruns a succeeded job | **Fixed** | `is_permanent` (db.py:58-63) is True only for DataError/IntegrityError/ProgrammingError and non-DBAPI StatementError; `_record` (scheduler.py:216-224) retries everything else every `scheduler_tick_seconds`, calling `raise_if_cancelling()` first. Round-3 probe `test_a_succeeded_job_is_not_rerun_…busy_pool` now passes: `calls 1 rows [('succeeded', 1, None)] record gave up: 0`. Mutations: making `sqlalchemy.exc.TimeoutError` permanent fails `test_db::test_only_errors_no_retry_can_fix_are_permanent` and `test_scheduler::test_a_busy_pool_…`; never giving up fails `test_a_result_no_retry_can_write_leaves_the_run_to_count_as_interrupted`. A permanent error leaves the row `running`; the next passes rerun it as interrupted (probe with a P0001 trigger: job ran 3x, row `('failed', 3)`, notice "interrupted 3x"). Caveat: unclassified permanent errors retry silently for ever (F9). |
| S3 status-lock test can deadlock | **Fixed** | test_runtime.py:314-326 locks with `psycopg.AsyncConnection` and `SET lock_timeout = '5s'`; no sync statement left on the loop thread in an engine-running test (grep: the other sync lockers in test_lease.py:121/150 and test_runtime.py:332 lock before or without a running engine). Committed test: 30/30 pass, 4.0-4.4 s each, 60 s per-run limit, 0 hangs. Mutation (exact pre-fix sync locker back): 29 pass, **1 hang** (killed at 60 s) in 30, which is the old flaw; sync locker that keeps `lock_timeout 5s`: 30/30 pass. Round-3 sync-locker probes still fail by design: 12 would-be hangs in 6592 tries; 1 in 60 replays. |
| N1 lone surrogates | **Fixed** | db.py:82-83. Round-3 surrogate probes pass (job row `('failed', 3, 'RuntimeError: cannot parse caf\\udcff')`, stage row error `…\\ud83d…`, end-to-end: worker starts 1, engine_failed 0). Mutation (no backslashreplace) fails 3 committed tests (test_db, test_scheduler, test_stages error-text tests). |
| N2 suppress around release | **Fixed** | runtime.py:82 and :112 are plain awaits; release catches its own errors and calls `raise_if_cancelling()` (lease.py:97). Round-3 probe `test_cancelling_run_engine_during_the_release_after_a_failure_is_not_swallowed` passes. Caveats: lease.py:97 is unpinned by committed tests (F4); on cancel, a failing release now skips dispose (F5). |
| N3 CLI one-line errors | **Partly** | cli.py:53-58: empty-message fallback, "error from" for non-connection errors, comment on the unescaped "@". But a host that doesn't resolve now prints "error from the engine database: failed to resolve host …" (F8; round 3 printed "could not reach"), and neither the label nor the fallback is pinned (both mutations: 4/4 test_processes pass). |
| N4 gc.collect before DROP | **Fixed** | conftest.py:37. Full run under CPU load: 80 passed in 80.6 s, slowest call 8.65 s, no 60 s teardowns. |
| N5 unpinned fixes | **Partly** | Pinned now: `_record`'s `raise_if_cancelling` (mutation fails `test_cancelling_the_scheduler_while_it_records_a_result_works`), `_execute`'s (fails `test_a_job_that_turns_its_cancellation_into_an_error_is_left_running`), once-per-runner scan (fails `test_only_the_first_pass_looks_for_unknown_stages` and `test_items_at_an_unknown_stage_are_left_alone`). Declines: **`_hold` "unpinnable on 3.13" does not hold** (F2): the TaskGroup does un-cancel and re-cancel the parent, so the copy still ends cancelled, but without runtime.py:107 `_hold` first logs "engine work failed; stepping down" and sends an `engine_failed` operator notice; probe R4-1 catches the revert, no committed test does. **Renewal cadence "timing-flaky"**: a pin with a wide margin exists (F3): renewal starts 0.200-0.205 s apart, 10/10 under 6 busy loops on 4 cores (load 4.5), vs 0.305 s with the flat sleep. |

## (b) Probes and mutations

Probes are in `review-258-r4/engine/tests/` (copies of the round-2/3 files unchanged; `test_r4_probes.py` is new). Outputs in `review-258-r4/out/`.

- Round-3 probes (`r3_probes_run1.txt`): 9 pass, including the busy-pool rerun, both surrogate probes, the cancelled-release probe, the step-down edge settings (0.385 s and 0.180 s) and the converted-cancel job. `test_a_sync_lock_on_engine_meta_can_deadlock_with_the_heartbeat` fails by design (12/6592). `test_r3_lockrepeat.py` fails by design (1/60).
- Round-2 probes (`r2_probes_run1.txt`): 13/13 pass (stalled holder at 1/0.2, 12/4 and 30/10; crash loop 1 engine_failed, 0 recovered; network fault; stop during first connection; lock timeouts).
- Round-4 probes (`r4_probes_run1.txt`), each asserting the behaviour I'd call correct:
  - R4-1 `_hold` cancel is not reported as a failure: passes at 99fe7bb; fails with runtime.py:107 removed.
  - R4-2 renewal cadence: passes (gaps 0.201); fails with the flat sleep (0.305).
  - R4-3 late-committed take then release: **fails** (F1).
  - R4-4 cancelled copy whose release fails: **fails** (F5).
  - R4-5 release re-raises a converted cancel: passes; fails with lease.py:97 removed.
  - R4-6 unwritable result reaches the operator: **fails** with an XX000 trigger (F9): 19 retries in 2 s, 1 job call, no notice.
  - R4-7 DNS failure labelled unreachable: **fails** for status and migrate (F8).
  - R4-8 connect timeout bounds the whole connection: **fails**: 2 silent addresses with timeout 2 give up after 4.00 s (F7).

Mutations (`mutate_r4.py`, `mutate_s3.sh`; logs in `out/mutations/`), committed tests only unless noted:

| Mutation | Result |
|---|---|
| S1 async engine without connect_timeout | caught: test_db::test_new_connections_time_out |
| S1 sync engine without connect_timeout | caught: same |
| S1 migrations/env.py back to plain create_engine | caught: same (the migrate attempt) |
| S1 release never-held return removed | caught: test_lease::test_release_does_nothing_if_the_lease_was_never_held |
| S1 release asyncio.timeout removed | caught: test_lease::test_release_gives_up_in_time_if_the_database_stalls |
| S1 release lock/statement timeouts removed | **not caught** (26 pass; asyncio.timeout still bounds it) |
| N2 release's raise_if_cancelling removed | **not caught** by committed tests (26 pass); caught by R4-5 |
| S2 pool TimeoutError permanent | caught: test_db classification + test_scheduler busy pool |
| S2 nothing permanent | caught: test_a_result_no_retry_can_write_leaves_the_run_to_count_as_interrupted |
| S3 exact old sync locker | 1 hang in 30 runs (60 s limit), 29 pass |
| S3 sync locker + lock_timeout 5s | 30/30 pass |
| N1 backslashreplace removed | caught by 3 tests |
| N3 always "could not reach" | **not caught** |
| N3 empty-message fallback removed | **not caught** |
| N5 `_record` raise_if_cancelling | caught |
| N5 `_execute` raise_if_cancelling | caught |
| N5 `_hold` raise_if_cancelling | **not caught** by committed tests (18 pass); caught by R4-1 |
| N5 unknown-stage scan every pass | caught by 2 tests |
| N5 renewal cadence flat sleep | **not caught** by committed tests (30 pass); caught by R4-2 |
| Round-2 S1: keep() awaits the cancelled renewal (checks the TTL→TTL/3 test change) | caught: stepped down 1.12 s after acquire, limit 0.9 s |

## (c) Commands and by-hand runs

- `ruff check .`: All checks passed. `ruff format --check .`: 29 files already formatted. `mypy`: no issues in 28 files.
- `pytest -v`: **80 passed in 62.87 s**; as superuser role `engine` (`DEV_DATABASE_URL=postgresql://engine:<redacted>@localhost:5432/postgres`, role used as is and left in place): **80 passed in 62.65 s**; under 4 busy loops (load 3.45 on 4 cores): **80 passed in 80.63 s**.
- S3 test 30 times, 60 s per-run limit: 30 pass, 0 fail, 0 hang (4.0-4.4 s).
- Alembic, as engine.yml runs it: `alembic heads` → `0001 (head)`; count check rc 0.
- CI (`pull_request_read get_check_runs`): head 99fe7bba; `check` completed **success** 19:39:56-19:41:34Z; GitGuardian success. PR is open, draft, not merged.
- PR body and CHANGELOG match the code, with two wording gaps: "release … is bounded by the same answer window as renewals" (F6: 20 s with a frozen network at defaults) and "new connections give up after 10 s" (F7: per address). "80 tests, about 70 s" matches (63-81 s).

By hand, from the checkout, default timings, database `engine_verify258d_3b39418d` (dropped; `out/byhand_*.txt`, logs in `byhand-logs/`):
- `status` before migrate: rc 1 "not migrated"; `migrate` 0.66 s; `status` prints the row, lease free; second migrate keeps stream_id `9ac15048-…`.
- Two copies: one holds at 0.01 s. `kill -9` on it with 25.47 s left on the row: the other took over **26.56 s** later. SIGTERM on the new holder: exit **0.16 s**; the waiting third copy held the lease **7.55 s** later (its poll); SIGTERM on that one: 0.16 s, lease row gone. Logs: 0 password/URL hits.
- SIGTERM on a copy whose connections go to a local port that accepts and never answers: **0.16 s** (4 s in) and **0.11 s** (12 s in, after "lease answer took over 10s").
- SIGTERM on a holder while another session holds its lease row locked: **10.15 s** ("could not release the lease (TimeoutError()); it expires in 30s"; the row had 17.8 s left).
- `status` and `migrate` vs silent port: **10.6 s** each, rc 1, one line, no leak. Refused port: 0.60-0.68 s, rc 1, one line. Wrong password (throwaway login role, dropped, count 0): 0.55-0.63 s, rc 1, one line "could not reach … password authentication failed", no leak.
- Extra: `status` vs a two-address silent host: **20.6 s**; with `PGCONNECT_TIMEOUT=3`: still 10.6 s.
- Extra (freezable proxy, `freeze_proxy.py`): holder's network frozen, SIGTERM 1 s later: exit **20.18 s** (psycopg "query cancellation failed" at +15 s, "closing connection" at +20 s, then "could not release"); other copy took over 27.6 s after the SIGTERM. Frozen 5 s after holding, SIGTERM at 13 s (renewal and heartbeat in flight): exit **20.14 s** (10 s TaskGroup cancel, 10 s release); the other copy took over 20.2 s after, after the holder had stopped all work. No hang in any case.

Cleanup: every database and role I created is dropped (`engine_%` databases: none of mine left; `verify258d%` roles: 0; `engine` role untouched, superuser). One database left by the S3 hang mutation (`engine_test_95b5d2a4`, created 20:21:27 by run 29) was dropped by name; another `engine_test_*` seen then belonged to a different agent's concurrent pytest and was not touched. No processes of mine left. The checkout's tracked files are unchanged. At the end it had three new ignored `__pycache__/` dirs (`engine/engine/migrations/`, `…/versions/`, `engine/tests/`, the last with `*-pytest-9.1.1.pyc`), written at 20:24:38 and 20:27:41. My checkout runs had all finished by then and ran with `PYTHONDONTWRITEBYTECODE=1`, so they weren't mine: another agent's pytest (`-p slow_connect_plugin tests/test_lease.py tests/test_runtime.py`) was running at 20:24. I left them alone.

## (d) New findings (all nits)

**F1. nit: "never held" is wrong when a take commits but its answer is late or lost** (lease.py:83, :133)
- Problem: `_ever_held` is set only after `_take_or_renew` returns. If the INSERT … ON CONFLICT commits and the reply arrives after acquire's `asyncio.timeout`, or the connection drops after COMMIT, acquire returns False with the row naming this copy. A stop then skips the DELETE. Before this commit release always ran the (harmless) DELETE.
- Scenario: a redeploy during a network blip: the new copy waits up to 30 s instead of taking over at once. No safety impact.
- Evidence: R4-3 (`LateAnswerDb` commits, then sleeps past the answer window): acquire → False, row holder "a", release → row still "a", b.acquire() → False.
- Fix: record "may hold" once the take is about to be sent, e.g. set the flag right after `async with self._db.begin() as conn:` in `_take_or_renew`. A copy that never connected still returns at once.

**F2. nit: N5's `_hold` decline is pinnable** (runtime.py:107; test_runtime.py:598-612)
- Problem: without line 107 the copy still ends cancelled, but `_hold` logs "engine work failed; stepping down" and sends `engine_failed: … ExceptionGroup(… OperationalError('connection lost while cancelling'))` before the re-armed cancel lands.
- Evidence: mutation run: R4-1 fails with that log and notice; all committed runtime/processes tests pass.
- Fix: add `assert operator_notices(caplog, "engine_failed") == []` to `test_cancelling_the_copy_works_when_its_work_turns_the_cancel_into_an_error`.

**F3. nit: the renewal cadence can be pinned without flakiness** (lease.py:71)
- Evidence: R4-2 wraps `_take_or_renew` so each answer takes 0.1 s more and checks the median gap between renewal starts is < renew + 0.05. Gaps were 0.200-0.205 s in 10/10 runs under load and 0.305 s with the flat sleep.
- Fix: commit R4-2.

**F4. nit: two release() details are unpinned** (lease.py:97 `raise_if_cancelling`, lease.py:90 `_bound_statements`)
- Evidence: removing either leaves all 26 lease/runtime tests passing. R4-5 (real Lease + `StalledDb`, cancel during release, assert cancelled) catches the first.
- Fix: commit R4-5. The second is redundant with the asyncio timeout and can stay unpinned.

**F5. nit: a cancelled copy whose release fails skips both dispose() calls and the "stopped" log** (runtime.py:81-85, lease.py:97)
- Problem: when `run_engine` is being cancelled and release hits an error or its timeout, `raise_if_cancelling()` raises CancelledError out of release, so `db.dispose()`, `lease_db.dispose()` and the log are skipped. The `suppress` this commit removed used to let them run.
- Scenario: only code that cancels `run_engine` (tests, a future supervisor); `python -m engine run` stops through the event.
- Evidence: R4-4 (lease row locked, then cancel): no "stopped" log, no "could not release" warning, 2 sessions still open on the database before gc.
- Fix: `try: await lease.release()` / `finally: await db.dispose(); await lease_db.dispose(); log.info(...)`.

**F6. nit: release's bound is the answer window plus psycopg's 10 s cancel budget** (lease.py:86; PR body "bounded by the same answer window as renewals")
- Problem: when the timeout interrupts a query on a frozen connection, psycopg 3.3 spends up to 5 s on a cancel request and 5 s waiting before it re-raises (connection_async.py:535-553).
- Evidence: by hand, frozen network, SIGTERM 1 s later: the release warning came 20.0 s after "stop requested", and the exit was 20.18 s. With the renewal and heartbeat in flight: 20.14 s.
- Fix: run the DELETE as its own task and `asyncio.wait` it with the timeout, then cancel without waiting (as keep() does), or reword to "about ttl − 2·renew, plus the driver's 10 s cancel budget".

**F7. nit: the 10 s connect timeout applies per address** (db.py:27-49; CHANGELOG:40, README:15-16, PR body)
- Problem: psycopg makes one attempt per host and per resolved address, each with the full `connect_timeout` (`_conninfo_attempts_async.py`, connection_async.py:117-137).
- Evidence: two silent addresses: `status` gives up after 20.6 s at the default, and R4-8 after 4.00 s with a 2 s timeout. Whether the production Neon host name resolves to several addresses is unconfirmed (I made no DNS lookups).
- Fix: say "each address attempt gives up after 10 s", or bound `status`/`migrate` as a whole.

**F8. nit: N3's label calls a DNS failure "error from the engine database"** (cli.py:58)
- Problem: psycopg's message for a host that doesn't resolve starts "failed to resolve host" (round 3 output: "could not reach … failed to resolve host 'no-such-host.invalid'"), so the new rule prints "error from", for the commonest unreachable case (a typo'd host, and an unescaped "@" in the password). A wrong password, on the other hand, is labelled "could not reach".
- Evidence: R4-7 (getaddrinfo patched to fail, no network): status and migrate both print `error from the engine database: failed to resolve host 'engine-db.typo.example': …`. Mutations show neither the label nor the empty fallback is pinned.
- Fix: `reason.startswith(("connection", "failed to resolve host"))`, or drop the label ("engine database error: …"), plus a test.

**F9. nit: an unclassified permanent error makes `_record` retry silently for ever** (scheduler.py:216-224)
- Problem: the retry is fixed-interval (`scheduler_tick_seconds`), unbounded, with warnings only. The job stays in `_running`, so it isn't rescheduled until the copy steps down.
- Realistic triggers: none in this schema. A plain UPDATE on job_runs raises InternalError/NotSupportedError only through a trigger, or with a read-only database, which is legitimately transient.
- Evidence: R4-6, a trigger raising SQLSTATE XX000 (InternalError): 19 retries in 2 s at tick 0.1 s, the job ran once, no operator notice. A plain RAISE EXCEPTION is P0001, which psycopg makes a ProgrammingError, so it is treated as permanent.
- Fix: send one operator notice once a result write has failed for, say, `max_attempts` ticks, and keep retrying.

**Smaller nits**
- db.py:28 says "libpq's default is to wait for ever". psycopg 3.3 uses 130 s per attempt when `connect_timeout` is unset (conninfo.py:23, `timeout_from_conninfo`). Measured: an async connect to a silent port with no `connect_timeout` raised ConnectionTimeout after 130.0 s (`out/psycopg_default_timeout.txt`). Fix: reword.
- The explicit `connect_timeout` kwarg overrides `PGCONNECT_TIMEOUT`: with `PGCONNECT_TIMEOUT=3`, `status` still took 10.6 s. Fix: document it in the README, or skip the default when the variable is set.
- lease.py:98: "it expires in 30s" prints the ttl. By hand, the row had 17.8 s left. Fix: "expires within %gs".
- test_db.py:50-56 builds all three coroutines up front, so when one fails the others are never awaited and pytest prints a RuntimeWarning ("1 warning" in the S1 mutation runs). Fix: build each attempt inside the loop.

**Checked and dropped** (from the code-review skill's candidates and my own list):
- "release waits for the renewal inside its budget; test weakened TTL→TTL/3". The round-2 S1 revert is still caught (1.12 s vs 0.9 s). A renewal that takes longer than the window to give up means the network is frozen, so the DELETE couldn't land anyway, and the row expires `renew` s after the step-down.
- "connect_timeout doesn't bound queries". The claim is scoped to a host that accepts and never answers; a mid-query stall is a different failure and is not claimed.
- "ProgrammingError from a pooler's prepared statements": unconfirmed, and it would break lease renewals first.
- Retry loops spinning on a closed engine (dispose re-creates the pool), "current transaction is aborted" (each retry is a fresh transaction), or UnicodeEncodeError (not wrapped by SQLAlchemy, and error_text can no longer produce it): not reachable.
- release() deleting another copy's row: the holder filter plus unique holder ids rule it out. Held, lost, then stopped: `_ever_held` stays True and the DELETE matches nothing.
- 10 s connect timeout vs the lease (renew 10, ttl 30): every lease path was already bounded by the 10 s answer window, so nothing gets worse. A Neon cold start of a few seconds fits; a wake slower than 10 s would fail a pre-deploy `migrate` rather than wait (unconfirmed, and a safe failure).
