# PR #260 "Engine PR 3: market data": final check (round 4)

**Reviewed:** b1c18e5, a merge of PR 2's passed head edbbc13 (which carries PR 1's round-3 head 99fe7bb) into 2dc1280. I checked it myself; the change is a merge only.

**Result: passed.** PR 3's own code has had no blocker or should-fix left since round 3 ([pr-260-round-3.md](pr-260-round-3.md)).

## What was checked

- **Checks:** ruff, ruff format and mypy strict are clean (62 source files). pytest gives 302/302 at b1c18e5 on the sandbox Postgres. Alembic still has one chain (0001, 0002, 0003).
- **The merge:** `--remerge-diff` shows one conflict, in `engine/settings.py`.
  - PR 3's duplicate docstring line about `hide_input_in_errors` was dropped, since PR 2 now sets it.
  - The `alpaca_backoff_seconds` docstring now matches round 3's N2: the back-off covers a 5xx, a dropped call, or a 429 that names no reset.
- **PR 2's files** match edbbc13 except `engine/http_client.py`, where PR 3 split out `scrub()` as round 2's S1 asked.
- **PR 3's own files** changed only by what PR 1 and PR 2 brought in: CHANGELOG and README lines, the CLI's one-line database error, the explicit connection caps, and the test database's `gc.collect()`.
- **Round 2 and 3 fixes still in place:**
  - `_fail` scrubs every AlpacaError text with the client's key headers (alpaca.py:256).
  - `cli._variable` keeps `ALPACA_API_SECRET_KEY` as it is (cli.py:75-79).

## If PR 1 changes again

PR 1 (#258) is in its round 4. If it pushes again, PR 2 merges it first. Then merge PR 2's new head and send me the head, and I'll check that merge only.

## Merge check: 56a32f7 (still passed)

- 56a32f7 merges PR 2's a58681f, which carries PR 1's test-only 5e13024. Its diff against b1c18e5 is the same two lines in `engine/tests/conftest.py`.
- pytest gives 302/302 here on the sandbox Postgres.
- CI's one failure at b1c18e5 (`test_a_late_answer_does_not_count_as_holding`) was the slow-first-connect timing that 5e13024 addresses.

## Merge check: 19ebf21 (still passed)

- 19ebf21 merges PR 2's 85bd2f0, which carries PR 1's round-4 nits (201e01e).
- **The two conflicts were resolved by keeping both sides:**
  - in `engine/cli.py`, PR 1's `database_error_line` sits after PR 3's `_variable`;
  - in `tests/test_processes.py`, PR 1's two new tests sit after PR 3's.
- PR 3's own diff against its base is the same size before and after the merge (44 files, +3,567 and -16).
- ruff, ruff format and mypy strict are clean, and pytest gives 309/309 here.

## Merge check: a2493db (still passed)

- a2493db merges PR 2's 0235161, its test-only flake fix, with no hand edits. The diff against 19ebf21 is that one hunk in `tests/test_live.py`.
- `tests/test_live.py` passes 49/49 here, and the builder reports 309/309 with lint and types clean.
