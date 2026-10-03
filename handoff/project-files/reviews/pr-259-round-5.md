# PR #259 "Engine PR 2: sources and signals": final check (round 5)

**Reviewed:** edbbc13. It holds 0e92d5c (round 4's nits) and a merge of PR 1's round-3 head 99fe7bb. I checked it myself; the change is small.

**Result: passed.** PR 2's own code has had no blocker or should-fix left since round 4 ([pr-259-round-4.md](pr-259-round-4.md)).

## What was checked

- **Checks:** ruff, ruff format and mypy strict are clean (46 files). pytest gives 206/206 at edbbc13 on the sandbox Postgres.
- **The merge edbbc13:** `--remerge-diff` shows one hand edit. PR 1 replaced `TRANSIENT_ERRORS` with `is_permanent()`, so `_run_feed` now warns and retries a database or OS error that isn't permanent. Anything else is logged with its traceback and recorded in the feed's status through `_record_failure`. That is correct.
- **Round 4's nits:**
  - **N1:** NUL and lone surrogates are dropped from text and raw payloads.
  - **N2:** a catch-up that is waiting on its store shows "not stored yet".
  - **N3:** trumpstruth's `originalUrl` path is range-checked.
  - **N4:** `hide_input_in_errors=True`.
  - **N5:** connection caps are explicit, and the keep-alive claim is limited to the 15 s and 60 s feeds.
  - **N8:** the cancellation in `_record_failure` is pinned.
  - **N9:** a post dated more than a day ahead is skipped as odd, so it can't move the mark.

  The builder reports 6 of 6 mutations caught.
- **Declines accepted:**
  - **N6:** a keep-alive test needs a real gap over 5 s, and `make_client` without a transport picks up the sandbox proxy. Reuse was verified live instead: 1 TLS handshake in 8 polls.
  - **N7:** catching `ProgrammingError` around the whole import would also mislabel a mid-import bug as "not migrated".

## One optional note

`_run_feed` records a failure in status only in the permanent or unexpected branch. A non-permanent error that keeps recurring shows only in the log as a warning. Examples are `InternalError`, `NotSupportedError` and a pool timeout. Calling `_record_failure` in both branches would make that visible too: it is best-effort, and it just logs if the database is down. This is not required.

## If PR 1 changes again

PR 1 (#258) is in its round 4. If it pushes again, merge it in and send me the head, and I'll check that merge only.

## Merge check: a58681f (still passed)

- a58681f merges PR 1's 5e13024, which is a test-only change: the `db` fixture opens its first connection before the test runs. Its diff against edbbc13 is exactly that commit's two lines in `engine/tests/conftest.py`.
- pytest gives 206/206 here on the sandbox Postgres.
- The decline of the optional note is accepted. Writing status on every non-permanent error would hit a database that is already struggling.

## Merge check: 85bd2f0 (still passed)

- 85bd2f0 merges PR 1's 201e01e, its round-4 nits, with no hand edits: `--remerge-diff` is empty. Its changed lines match 201e01e's exactly.
- ruff, ruff format and mypy strict are clean, and pytest gives 213/213 here (206 plus PR 1's 7 new tests).
- `import-history` goes through the CLI's shared handler, so it uses `database_error_line` too.

## Test fix check: 0235161 (still passed)

- 0235161 is test-only. In `test_all_dark_sends_one_message_and_clears_when_a_feed_answers`, the fixed 0.3 s wait for the first good poll becomes a wait of up to 5 s for the feeds_back notice. That is the flake PR 4's CI hit.
- The hunk is byte-identical to PR 4's 6a24a0b, so the later merges stay clean.
- `tests/test_live.py` passes 49/49 here, and the builder reports 213/213 with lint and types clean.
