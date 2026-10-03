# PR #258 "Engine PR 1: foundation": review round 3

**Reviewed:** f4194b7, "fold in gauntlet round 2", on top of 6f28906. Earlier rounds: [round 1](pr-258-round-1.md), [round 2](pr-258-round-2.md).

**Passes**, each run by a fresh agent:
- **verify**, on the whole PR: clauDNA verify-completion, checking the brief and every round-2 id, with a revert-the-fix mutation for each named test and by-hand runs at default timings.
- **review**, of the new commit: the built-in code-review at high effort plus clauDNA review-work. It re-ran the round-2 probes, wrote new probes and ran mutations, some of them under CPU load.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passed 66/66 on seven full runs, one of them under CPU load and one as a superuser named `engine`, like CI.
  - There is one Alembic head, and CI is green on f4194b7.
- **Round 2 is fixed:**
  - **B1:** `raise_if_cancelling()` runs first in every retrying handler. On Python 3.13 it handles uncancel correctly: `asyncio.timeout` and TaskGroup uncancel their own cancels, so a consumed cancel isn't re-raised and an outside one isn't missed. Every round-2 B1 probe passes, 5 of 5 runs. Each named test catches a revert of its own call.
  - **S1:** the stalled-holder probe passes 15/15 at ttl/renew 1/0.2, 12/4 and 30/10. The holder stops 0.00 to 0.06 s after its deadline and the other copy never takes the row first. At the validator's edge (ttl = 3×renew) it steps down before expiry.
  - **S2:** a crash loop gives 1 `engine_failed` and 0 `engine_recovered`, 5 of 5 runs.
  - **Nits:** N3-N10 are in, and all six N5 pins catch their revert. N7's PR-body wording matches settings. N1 is partly fixed (S2 and N1 below).
- **By hand, at default timings:**
  - `kill -9` on the holder: the other copy took over 26.2 s later, while the row had 25.5 s left.
  - SIGTERM on the holder: it exits in 0.16 s, and the next copy holds the lease 7.6 s later.
  - SIGTERM during a lock-blocked acquire: exits in 0.16 s.
  - N9: a refused port, a bad host and a wrong password each print one line and exit 1, with no password or URL in the output.
- **Round 1:** every regression test is still there and passing.

**Result: changes needed.** 3 should-fix and 5 nits, all from new code or newly exercised paths.

## How to answer

- Same as before: fix each should-fix or decline it with a reason; nits are optional. Send me the new head with one line per id.
- Tell the PR 2 and PR 3 builders when you push. Both are mid-round, and both merge your branch.

**Probes:** [pr-258-round-3-probes/](pr-258-round-3-probes/)
- `test_r3_probes.py` asserts the correct behaviour, so a failing probe means the bug is real.
  - Fail at f4194b7: `test_a_succeeded_job_is_not_rerun_…`, the surrogate probes, `test_cancelling_run_engine_during_the_release_…` and `test_a_sync_lock_on_engine_meta_can_deadlock_…`.
  - Pass, for regression: `test_step_down_at_the_edge_settings` and `test_a_job_that_turns_its_cancellation_into_an_error_is_left_running`.
- `verify_byhand.py` is the by-hand driver for S1.
- `proposed_fix_release_connect_timeout.diff` is verify's trial fix for S1. It isn't a final patch, but all 66 tests pass with it.
- Copy files into engine/tests/ to run them, and don't commit them as they are.

---

## Should-fix

### S1. Nothing bounds a connection attempt, so a stopped copy can hang in `release()`, and `migrate`/`status` hang silently (verify)
- **Where:**
  - runtime.py:81-83 calls `await lease.release()` with no time limit, even when this copy never held the lease. The same applies at runtime.py:113-114.
  - lease.py:76-85 (`release()`) opens a new connection with no lock or statement timeout. It is the one lease statement without them.
  - db.py:23 and :28, and migrations/env.py:13, set no `connect_timeout`. libpq's default is to wait for ever.
- **Problem:** if the database host accepts the TCP connection and then never answers, every connection attempt waits for ever. A Neon proxy stall or a half-open network path does this.
  - A copy stopped while it waits for the lease runs `release()`, opens a new connection and never returns.
  - `migrate` and `status` print nothing and never finish. The PR body's "an unreachable database gives a one-line error" holds for a refused connection, not a silent one.
  - Separately, SIGTERM on a holder while another session holds its lease row waits as long as that lock.
- **Scenario:**
  - Railway redeploys during a Neon stall. The old copy ignores SIGTERM until Railway's SIGKILL.
  - A pre-deploy `migrate` hangs, and the deploy hangs with it.
- **Evidence (verify, by hand):**
  - SIGTERM with the first connection on a port that accepts and never answers: no exit within 45 s, and SIGKILL was needed. A stack dump shows it stuck at runtime.py:83.
  - SIGTERM on a holder whose lease row another session had locked: exit took 45 s, until the lock was released.
  - `status` and `migrate` against a silent port: no output for 40 s or more.
  - With `connect_timeout=10`, both commands print "could not reach the engine database: connection timeout expired" after 10.6 s. Without the env.py change, `migrate` still hangs.
- **Fix:**
  1. Add `connect_args={"connect_timeout": 10}` in `make_engine`, `make_sync_engine` and migrations/env.py, or a setting.
  2. In `release()`:
     - skip the DELETE when this copy never held the lease;
     - bound the call with `asyncio.timeout(lease_renew_seconds)` at both call sites;
     - give its statement the same lock and statement timeouts `_take_or_renew` uses.
  3. Tests:
     - stop `run_engine` against a local server that accepts and never answers, and assert it returns quickly;
     - extend `test_bad_settings_are_a_clear_error_that_never_prints_the_url` with a silent local port.

### S2. A job that succeeded can run again when its result write meets a busy pool (review)
- **Where:** scheduler.py:216-225 (`_record`) and db.py:39 (`TRANSIENT_ERRORS`).
- **Problem:** N1 narrowed `_record`'s retry to `OperationalError`, `InterfaceError` and `OSError`. A pool checkout timeout raises `sqlalchemy.exc.TimeoutError`, which is in none of them. So `_record` gives up and leaves the row `running`. The next tick reclaims it as interrupted and runs the job again with no retry wait. That brings back round 1's S2 failure for this error.
- **Scenario:** a daily job finishes while a Neon stall, or PR 2's stage handlers, have the 15-connection app pool busy for 30 s.
- **Evidence:** `test_a_succeeded_job_is_not_rerun_when_its_result_write_meets_a_busy_pool`. With a 1-connection pool, a 0.3 s checkout timeout and another task holding the connection, the job ran twice and the row ended `('succeeded', 2)`, 3 of 3 runs. Adding `TimeoutError` makes it run once.
- **Fix:** turn the rule around. Give up only on errors that can't succeed on a retry (`DataError`, `IntegrityError`, `ProgrammingError`, `StatementError` from bad parameters), and only when not cancelling. Retry everything else. Add the probe as a test, and add one that pins the give-up branch (no committed test catches a revert of it).

### S3. `test_a_lock_on_the_status_row_does_not_stall_the_lease` can hang the suite until CI's 15-minute limit (verify, review; also seen by PR 3's builder)
- **Where:** test_runtime.py:315-316. The test takes its lock with a synchronous psycopg `execute` on the event-loop thread.
- **Problem:** if that UPDATE lands while the engine's heartbeat is between its own UPDATE and COMMIT, the test blocks the loop waiting for the heartbeat's lock. The heartbeat can't commit because the loop is blocked. Neither has a lock timeout, so the run waits until it is killed.
- **Evidence:**
  - Verify saw it hang until a 600 s kill. The database showed the heartbeat `idle in transaction` and the test's statement waiting on its lock for 526 s. That was about 1 hang in 20 runs that included the test.
  - PR 3's builder saw one hang in a full run on its branch.
  - Review measured about 0.2% at random moments, with `test_a_sync_lock_on_engine_meta_can_deadlock_with_the_heartbeat`.
- **Fix:** take and release the lock with `await asyncio.to_thread(locker.execute, ...)` (and the same for the rollback), or use an async connection. Either way, set `lock_timeout` on the locker so a regression fails rather than hangs.

## Nits (optional)

- **N1. `error_text` can still produce text Postgres rejects** (db.py:55-57; review).
  - A lone surrogate in an exception message makes psycopg raise `UnicodeEncodeError`, which no handler catches. Only `str()` of raw external text does this; repr-formatted messages are already escaped.
  - In the end-to-end probe, the scheduler's task group died and the copy stepped down 3 times. The only notice said "interrupted 3x" and the real error was never stored. Stages lose the reason the same way.
  - Fix: `.encode("utf-8", "backslashreplace").decode()` after stripping NULs. The four surrogate probes then pass.
- **N2. One carry-on handler still swallows a converted cancellation** (runtime.py:113-115, the `suppress` around `release()` after a work failure; review).
  - Production stops through the `stop` event, so this matters only to code that cancels `run_engine`. The CHANGELOG and the db.py docstring do claim full coverage, though.
  - Fix: `except (...): raise_if_cancelling()` there. Probe: `test_cancelling_run_engine_during_the_release_after_a_failure_is_not_swallowed`.
- **N3. CLI one-line error edge cases** (cli.py:54-58; review). Each is minor alone.
  - Every `OperationalError` is labelled "could not reach", including a statement timeout on a reachable database, and the traceback is dropped.
  - `splitlines()[0]` raises `IndexError` on an empty driver message. That is a constructed case.
  - With an unescaped `@` in the password, the rest of the password is printed as the host name. The old traceback did the same, and Neon passwords are alphanumeric, but the "never the password" comment isn't strictly true.
  - Fix: "database error: …" unless it's a connection failure, `(str(exc).splitlines() or [type(exc).__name__])[0]`, and a note in the comment.
- **N4. 60 s test teardowns under CPU load** (test_runtime.py:223 and conftest.py:36; review).
  - The crash-loop test leaves half-open psycopg connections in reference cycles. `DROP DATABASE` then waits out the server's 1-minute authentication timeout, which stalls other DROPs on the same server.
  - Seen in 12 of 13 repeat runs under load, and never without load.
  - Fix: `gc.collect()` before the DROP takes teardown to 0.23 s.
- **N5. Fixes no committed test pins** (verify, review). Each of these can be reverted with all 66 tests green:
  - `raise_if_cancelling()` in `_record`, `_execute` and `_hold`. The probe `test_a_job_that_turns_its_cancellation_into_an_error_is_left_running` pins `_execute`.
  - N1's narrowing in `_record`, which S2 changes anyway.
  - N2's renewal cadence.
  - N3's once-per-runner scan: the old scan-every-pass passes. Count the unknown-stage queries over 3 passes and assert 1.
  - keep()'s deadline check and release() waiting for the renewal are left out of this list: the `asyncio.wait` timeout already enforces them, so they need no test.

## Dropped

Checked and not backed:
- release() leaving a checked-out connection or an unretrieved task exception after a step-down. After a renewal it is bounded by psycopg's cancel budget. The silent first connection is S1.
- release() deleting a row another copy now holds: holder ids are unique.
- A false recovery from any path.
- N2 mis-scheduling after a failed renewal.
- `cancel_wedged` hiding a failure: both callers still assert.
