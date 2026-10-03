# PR #258 "Engine PR 1: foundation": review round 4

**Reviewed:**
- 99fe7bb, the round-3 fold-in. One fresh agent ran the review and verify passes together: the built-in code-review at high effort plus clauDNA review-dimensions, and clauDNA verify-completion. It re-ran the round-2 and round-3 probes, added 8 new probes, ran mutations, and did by-hand runs at default timings.
- 5e13024, the test-only fix on top (the `db` fixture opens its first connection before the test runs). I checked that myself, with slow-connect probes.

Earlier rounds: [1](pr-258-round-1.md), [2](pr-258-round-2.md), [3](pr-258-round-3.md).

**Result: passed.** There's no blocker or should-fix left. The 10 nits below are optional, and none of them lets two copies work at once or loses a recorded result.

- **If you take any nits,** push them together and send me the head. I'll check only that delta, and then PR 2 and PR 3 each merge it in.
- **If you take none,** PR 1 is done at 5e13024. Post the result in your thread.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 80/80: in 62.9 s, again as a superuser named `engine` like CI, and in 80.6 s under 4 busy loops.
  - Alembic has one head (0001), and CI is green on 99fe7bb.
- **Round 3:**
  - **S1 is fixed.** `connect_timeout=10` reaches the async engine, the sync engine and the migration env, and removing it from any one fails a test. A `connect_timeout` in the URL wins. Both of `release()`'s new guards are pinned.
  - **S2 is fixed.** The busy-pool probe runs the job once and records `succeeded`. Changing the classification either way fails a test.
  - **S3 is fixed.** The lock test passes 30/30 with an async locker. Putting the sync locker back hangs once in 30 runs.
  - **N1, N2 and N4 are fixed.**
  - **N3 and N5 are partly done:** see F8, F2 and F3.
- **By hand, at default timings:**
  - `kill -9` on the holder: the other copy took over 26.6 s later.
  - SIGTERM on a holder exits in 0.16 s, and the waiting copy holds the lease 7.6 s later.
  - SIGTERM with connections going to a silent port exits in about 0.1 s.
  - A holder whose lease row another session has locked exits in 10.2 s (45 s in round 3).
  - `status` and `migrate` against a silent port print one line after 10.6 s and exit 1, with no URL or password.
- **5e13024:**
  - It is sound and only touches tests. Production's answer window is 10 s, and the tests' is 0.6 s.
  - With the first async connect to each database slowed by 0.7 s, 14 tests fail at 99fe7bb and 2 at 5e13024 (F10).

## Nits (optional; file:line at 99fe7bb, unchanged at 5e13024)

- **F1. A take whose answer is late, or whose connection drops, makes the next stop skip the DELETE** (lease.py:83 and :133).
  - `_ever_held` is set only after the answer arrives, so the next copy can wait up to 30 s.
  - **Fix:** set the flag once the connection is open, before the statement is sent.
  - **Probe:** R4-3.
- **F2. Pin `_hold`'s `raise_if_cancelling`** (runtime.py:107). In `test_cancelling_the_copy_works_when_its_work_turns_the_cancel_into_an_error`, assert that no `engine_failed` notice is sent. R4-1 shows this catches the revert without flakiness.
- **F3. Pin the renewal cadence** (lease.py:71). R4-2 saw renewals 0.200-0.205 s apart in 10 of 10 runs under load, and 0.305 s once mutated.
- **F4. Pin `release()`'s `raise_if_cancelling` and its lock and statement timeouts** (lease.py:90 and :97). Commit R4-5.
- **F5. A cancelled `run_engine` whose release fails skips both `dispose()` calls and the "stopped" log** (runtime.py:81-85).
  - R4-4 leaves 2 sessions open on the database.
  - **Fix:** put the disposes and the log in a nested `finally`.
- **F6. With a frozen network, `release()` takes its answer window plus psycopg's 10 s cancel: 20 s at defaults** (lease.py:86).
  - The PR body says release is "bounded by the same answer window" as renewals.
  - **Fix:** run the DELETE as its own task and stop waiting at the deadline, as `keep()` does, or change the wording.
- **F7. The connect timeout applies to each address** (db.py:27-49).
  - A host with two silent addresses takes 20.6 s. Whether Neon's host resolves to several addresses is unconfirmed.
  - **Fix:** say "per address" in the docs.
  - **Probe:** R4-8.
- **F8. N3's label is wrong for an unknown host** (cli.py:58).
  - A host that doesn't resolve prints "error from the engine database: failed to resolve host …".
  - **Fix:** also count "failed to resolve host" as unreachable, or drop the label.
  - **Test:** the label and the empty-message fallback.
  - **Probe:** R4-7.
- **F9. An error no retry can fix, but that isn't classed as permanent, retries every tick forever, with warnings only** (scheduler.py:216-224).
  - A trigger raising XX000 (InternalError) gave 19 retries in 2 s and no operator notice. No realistic trigger exists in this schema.
  - **Fix:** send one operator notice after N failed writes, and keep retrying.
  - **Probe:** R4-6.
- **F10. The slow-first-connect flake is still possible in two tests that don't use the `db` fixture:**
  - `test_lease_times_come_from_the_database_clock` (test_lease.py:47) acquires on its own `skewed` engine.
  - `test_a_crash_looping_worker_sends_one_message` (test_runtime.py:128) counts starts in a 1 s window that includes the first acquire.
  - **Fix:** open one connection on `skewed` before acquiring. In the runtime test, start the 1 s window once the lease is held.
  - **Probe:** `slow_first_connect_plugin.py`, with `PYTHONPATH=<probes dir> pytest -p slow_first_connect_plugin`.
- **Smaller:**
  - db.py:28 says libpq waits for ever by default. psycopg gives up after 130 s (measured).
  - The explicit timeout overrides `PGCONNECT_TIMEOUT`.
  - The release warning says "expires in 30s" whatever time the row has left.
  - `test_new_connections_time_out` leaves unawaited coroutines when an attempt fails, so pytest prints a RuntimeWarning.

## Dropped

- "The step-down test was weakened (TTL to TTL/3)": the revert it guards is still caught.
- "`connect_timeout` doesn't bound queries": the claim only covers a host that never answers.
- `release()` deleting another copy's row: impossible, since holder ids are unique.
- The 10 s connect timeout making the lease worse: every lease path was already bounded by its 10 s answer window.

**Probes:** [pr-258-round-4-probes/](pr-258-round-4-probes/)
- `test_r4_probes.py` holds R4-1 to R4-8. R4-1, R4-2 and R4-5 pass at 99fe7bb and catch reverts no committed test catches. The others fail while their finding stands.
- `slow_connect_plugin.py` and `slow_first_connect_plugin.py` are for F10.
- `agent-findings.md` is the agent's full write-up.

Copy the tests into engine/tests/ to run them. Don't commit them as they are, except as tests you adopt.

---

## Nit check: 201e01e (passed)

201e01e folds in 9 of the 10 nits on top of 5e13024. I checked it myself.

- **Checks:** ruff, ruff format and mypy strict are clean. pytest passes 87/87 with `-W error::RuntimeWarning`.
- **F1:** `_may_hold` is set inside `begin()`, before the take is sent. Moving it back to after the answer fails `test_release_frees_a_row_whose_take_answered_late`. Once set it stays set, so a later release may send one DELETE that matches nothing, which is harmless.
- **F5:** the disposes and the "stopped" log sit in a nested `finally`. Removing it fails `test_a_cancelled_copy_cleans_up_even_if_its_release_fails`.
- **F3:** the renewal-cadence test passed 10 of 10 runs under 2 busy loops.
- **F10:** all 30 lease and runtime tests pass under `slow_first_connect_plugin.py` (14 failed at 99fe7bb, 2 at 5e13024).
- **F2, F4, F7, F8 and the smaller items** are in as described.
- **Declines accepted:**
  - **F6's code change:** a detached DELETE would let shutdown dispose the engines under an unfinished statement. The docstring and PR body now state the real bound.
  - **F9:** no path in this schema raises such an error, and a sustained outage already shows as lease loss and the `engine_failed` notice.
