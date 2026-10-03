# PR #259 "Engine PR 2: sources and signals": review round 2

Reviewed: the fold-in commit 0974fe2 (`git diff b54bc26 0974fe2`), the merge b54bc26's conflict resolutions (`git show --remerge-diff b54bc26`), and the whole of PR 2 relative to PR 1 (`git diff be04d50 0974fe2`). Round 1: [pr-259-round-1.md](pr-259-round-1.md).
Passes: **verify** on the whole PR (clauDNA verify-completion: brief plus every round-1 id, with a revert-the-fix mutation for each named test, and by-hand runs) and **review** of the new code (built-in code-review at high effort plus clauDNA review-work, the round-1 probes, new probes, about 45 mutations). Each ran in a fresh agent.

## Where it stands

- Every brief requirement holds. ruff, ruff format and mypy strict are clean; pytest 153/153 twice and once as a superuser named `engine` like CI; one Alembic head (0002); CI green on 0974fe2.
- By hand on a throwaway database: `import-history` added 36,625 (CNN gained a post since round 1), and a second run added 0. A 170 s mirrors-only live run was clean (CNN 12 polls, 11 not-modified; trumpstruth 3 polls; no errors or blocks). Two more runs on the same database restored feed state with no catch-up, no messages and no new sightings, and trumpstruth kept its 60 s schedule across the restart. Burst numbers match. Post time from `id >> 16` is exact on all 36,625 rows.
- The merge is clean: nothing from PR 1's be04d50 was lost, and PR 2 uses PR 1's new APIs correctly (`db_url`/`SecretStr`, `configure_logging()`, the worker FailureStreak, the settings bounds). PR 1's newer head 6f28906 merges cleanly (same test_migrate.py change).
- Round 1's should-fix items S1-S9 are all fixed: 17 round-1 bug probes now fail, the 6 controls pass, and the round-1 mutations M1-M10 are all caught. Nits N1-N14 and N16-N19 are in; N19 and N1 change exactly the intended rows on the real CC0 data (3 and 18), with no false positives.
- **N15 decline accepted:** both briefs and PR 1's docs name `build_registry()` in registry.py as the plug-in point, so moving it is PR 1's call.

**Result: changes needed.** 2 should-fix (one new bug in the fold-in, one carried over from PR 1's round 2) and 10 nits.

## How to answer

As before: fix each should-fix or decline it with a reason; nits are optional. When you push, send the gauntlet thread (session_013E4KMGG5c9USVygEcNJkqa) the new head and one line per id. PR 1's round 2 ([pr-258-round-2.md](pr-258-round-2.md)) has a blocker in the runtime, so expect one more PR 1 push to merge in.

Probes: [pr-259-round-2-probes/test_review259_r2_probes.py](pr-259-round-2-probes/test_review259_r2_probes.py). Tests named `test_r…` pass at 0974fe2 when the bug is real; tests named `test_…control…` are controls. Copy into engine/tests/ to run; don't commit them as they are.

---

## Should-fix

### S1. A block during catch-up throws away the read and comes back at once, so a feed can stay "blocked" for good (review)
- **Where:** engine/engine/feeds/live.py:152-168 (`_catch_up` catches only `FeedFailed`); live.py:129-130 (`poll()` turns `FeedBlocked` into `_failed(blocked=True)` and never calls `_answered`). The `FeedBlocked` comes from cnn.py:65 (`check()` in `download_archive`, added for N2) or mastodon.py:60 (paging back).
- **Problem:** `FeedBlocked` isn't a `FeedFailed`, so a 403, 429, challenge or `cf-mitigated` answer during catch-up drops the posts the head read already fetched, leaves the mark, never sets `catch_up_after`, and marks the whole feed blocked. When the back-off ends, the head reads fine, the catch-up runs straight away and is refused again. The feed never stores its own new posts. Any other exception from `read_back` does the same through the generic handler. This contradicts the PR body, CHANGELOG and README ("a failed catch-up keeps the new posts and tries again after a back-off").
- **Scenario:** after direct has been out for more than a page, Truth Social answers one page-back with 429: direct drops its 20 new posts, stays blocked retrying every 30 minutes, and ScrapeCreators runs as the paid 2-minute fallback the whole time. CNN does the same if its full file is refused. How often this happens in production is unknown; the mechanism is proven.
- **Evidence:** `test_r1_cnn_download_blocked_head_never_stored` (range read 206, full file 429: after 4 tries blocked, 4 downloads, none of the head stored); `test_r1b_direct_page_back_429_keeps_direct_blocked_and_scrapecreators_paid` (4 head reads and 4 page-backs, head dropped, ScrapeCreators at 120 s). Control `test_r1_control_download_503_keeps_head`: a 503 keeps the head.
- **Fix:** in `_catch_up`, also catch `FeedBlocked` (and `Exception` with `log.exception` as a backstop); return `Polled(posts, mark, complete=False, error=...)` and set the catch-up back-off (a block can start it at a higher floor, and count as a block in `source_stats`). The head answered, so the feed stays up while the catch-up waits. Optionally keep the pages fetched before the failure. Add both probes as regression tests.

### S2. The feed loops can swallow a cancellation, the same bug as PR 1's round-2 blocker (review of PR 1, applied here)
- **Where:** live.py:133-135 (`FeedPoller.poll`'s `except Exception`), live.py:312-315 (`_run_feed`: `except (SQLAlchemyError, OSError)` and `except Exception`, then loop), live.py:350 (`_watch_dark`'s `except (SQLAlchemyError, OSError)`).
- **Problem:** psycopg can turn a cancellation into `OperationalError` (connection dropped while it waits out the cancel) or `ProgrammingError` (a cancel during first connection setup). PR 1's round 2 proved this wedges its own retry loops (pr-258-round-2.md, B1). These feed loops catch the same errors and carry on, so when the lease is lost or the engine stops in the middle of a store, a feed task can keep polling, the TaskGroup never finishes, and the copy neither steps down nor stops.
- **Evidence:** same mechanism as PR 1's `test_r2_swallow.py` and `test_r2_reset.py` (/mnt/project-files/reviews/pr-258-round-2-probes/); not probed separately on the feeds.
- **Fix:** use the helper PR 1 adds for its B1 (re-raise when `asyncio.current_task().cancelling()`) in each of these handlers, and add one test where a store's cancellation surfaces as `OperationalError` and the feeds worker still stops.

## Nits (optional)

- **N1. Every CNN poll opens a new connection** (base.py:180-188; review). A correct 206 for `bytes=0-32767` is exactly 32,768 bytes, so `_read_body` breaks on the last chunk before httpx sees the end, and the connection is dropped instead of reused: about 5,760 new TLS handshakes to ix.cnn.io a day. `test_r5_range_read_does_not_reuse_connection`: 5 reads, 5 connections; the control (break only past the limit) uses 1. Fix: `if len(body) > limit: break`, still slicing to `limit`.
- **N2. The "skipped N of M items" warning repeats with each new CNN post** (base.py:173-176; review). The memo includes the total, and `read()`/`read_back()` share it. `test_r4_skip_warning_repeats_when_head_grows`: 3 warnings for one odd item. Fix: memo on the skipped reasons only, with a separate memo for `read_back`.
- **N3. A pending catch-up is invisible** (live.py:149-150, 193-195; status.py; review). While it waits, each poll writes `last_error=None`, and status shows errors only for blocked or off feeds, so a feed owed a catch-up reads "up" with no error for up to 30 minutes. `test_r2_waiting_poll_clears_catch_up_error`. Fix: carry the catch-up error through the waiting branch; optionally show "catch-up owed since <mark>" in status.
- **N4. A gap is dropped when a feed is switched back on** (live.py:107-109; review). An "off" feed starts at the newest stored post, so a gap trumpstruth logged as unfillable stays empty once CNN comes back on. `test_r3_feed_switched_on_after_gap_skips_it`. Deliberate, so either document it or persist the oldest unfilled mark and start a newly-on feed from it.
- **N5. Fixes no test pins** (review, verify). Each can be reverted with every test green: N6's `blocked_since` set before the write (live.py:217); a restored block that fails again sending no second "feed_blocked" (live.py:209; the control probe `test_control_restored_block_still_blocked_one_notice` shows it works); the `_go_dark` half of the shared lock (live.py:336); the brief's timing defaults (the CNN interval at 5 s or the dark threshold at 300 s passes everything). Fix: pin the defaults (60, 60, 15, 120, 3600 s; 5 failures; 60-1800 s; 600 s) in one test_settings assertion, and turn the control probe and round-1 P11 into tests. For N6, verify's recipe: patch `set_feed_status` to raise `OperationalError` once, send direct a 403, assert `blocked_since` is set, then answer OK and assert the `feed_recovered` text has no "since None".
- **N6. `feed_recovered` goes out before the store commits** (live.py:177-181 vs 182-195; verify). If that write fails and the engine restarts, a second recovery message is possible. Fix: send it after the commit.
- **N7. The one-hour import cutoff covers only CNN's part** (history.py:88-94; review). CC0 is imported unfiltered; no effect today (the copy ends around October 2025). Fix: one filter used for both parts.
- **N8. Back-off doubling is written twice** (live.py:156-159 and 214-216; review). Fix: a small `_next_backoff(current)` helper.
- **N9. N8's catch-up filter and thread offload have no test** (cnn.py:66, 99; verify; perf only). Optional: put an old malformed item in `test_cnn_catch_up_reads_the_whole_file` and assert no "skipped" warning.
- **N10. PR body:** its import and 15-minute live run ran on 4cb9f49; verify's runs at 0974fe2 give the same results, so optionally add a line saying so (verify).

## Dropped

- "0002 edited in place": it is unmerged and round 1 asked for the new columns there. Note: shitpost_dev probably still has round 1's 0002, so re-create it before the next by-hand run there.
- Not backed: a BOM in CNN's file; the unescape loop or the orphan-Â rule corrupting text (0 false positives on the real data); the import crashing on one bad item (not new). Two silent cases predate this round and stay out of scope: a read holding only other accounts' statuses, and a renamed text field.
