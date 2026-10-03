# PR #260 "Engine PR 3: market data": review round 3

Reviewed 2dc1280, the round-2 fold-in on top of de6b046. The change is about 120 lines of code plus tests, and I checked it myself. Earlier rounds: [round 1](pr-260-round-1.md) and [round 2](pr-260-round-2.md).

**Result: PR 3's own code passes.** No blocker or should-fix is left.

What's still open: merging PR 2's current head. PR 2's branch is at **edbbc13** now, not 558d50c. It passed its final check and carries PR 1's round-3 fixes (99fe7bb). Merge it, send me the head, and I'll check that merge and give the final "passed". PR 1 is still in its round 4, so there may be one more merge after that.

## What was checked

- **Checks:** ruff, ruff format and mypy strict are clean (61 files). pytest passes 284/284 at 2dc1280 on the sandbox Postgres.
- **Round-2 probes:** all 10 bug probes now fail, which is what fixed bugs should do. The ready-made pins and the S1 controls pass.
- **`test_control_an_empty_whole_answer_removes_nothing` is obsolete.** It expected an empty answer to return quietly. It now raises `ShortHistory` and changes nothing, which is what S2 asked for.
- **S1:**
  - `http_client.scrub` was split out of `request_error_text`.
  - `_fail` now scrubs every AlpacaError text with the client's key headers.
  - A 403 body that echoes both keys never reaches an error or a backfill line.
- **S2:**
  - `_remove_days_not_in` now runs first, for every whole refetch, empty answers included.
  - It raises `ShortHistory` inside the transaction when it would drop more than 5 stored days. The delete, the upsert and `rebased_at` all roll back, the instrument reports a clear failed line, and the next run retries.
  - The parametrized test covers 6 days dropped, 2,000 dropped and an empty answer.
- **N1 adopted:**
  - the settled-session refetch (S1's staleness guard);
  - the per-instrument database error;
  - the next-year calendar rebuild;
  - the lazy pandas import.

  Leaving out `--help`, the coin skip and fsync recording is fine.
- **N2:** a 5xx backs off even when it carries a reset header (`[2, 4, 8, 16]`).
- **N3:** `cli._variable` keeps `ALPACA_API_SECRET_KEY` as it is, and the test checks exit 2, the right name and no value.
- **N4:** the date check now runs before the UPDATE. A same-day typo correction leaves no alias, which is correct, because the typo never held a day.
- **N5:** a database error prints `OperationalError: <first line>`.
- **N6:** a page token that isn't a string is an unexpected answer.
- **N7:** naive times are refused.
- **N8:** the docstrings are in, and the README's retry timing has been corrected.

## Notes, nothing to do

- A whole history that legitimately loses more than 5 days fails the instrument on every run until someone looks. That is the intended trade-off, and the failed line says why.
- An empty answer for an instrument with 5 or fewer stored days still deletes them and moves `rebased_at`. That can only happen to a brand-new instrument, so it doesn't matter.
