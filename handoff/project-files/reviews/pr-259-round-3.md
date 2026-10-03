# PR #259 "Engine PR 2: sources and signals": review round 3

**Reviewed:** everything since round 2's head 0974fe2, as of 7d96886.
- 872135b, the round-2 fold-in;
- the merge 2b6216c, which brings in PR 1's f4194b7;
- 7d96886, which re-raises cancellations (S2).

**How:** one agent ran review and verify together, since the change was small:
- the built-in code-review at high effort plus clauDNA review-dimensions;
- clauDNA verify-completion;
- the round-1 and round-2 probes, 14 new probes, 19 mutations and a by-hand live run.

The key-leak finding (B1) came from PR 3's round 1 and was then probed on PR 2's code here.
Earlier rounds: [round 1](pr-259-round-1.md), [round 2](pr-259-round-2.md).

## Where it stands

- **Checks:** ruff, ruff format and mypy strict are clean. pytest passes 178/178 three times, once as a superuser named `engine` like CI. Alembic has one head (0002). CI is green on 7d96886.
- **Round 2's should-fix items are fixed:**
  - **S1:** a block or bug during catch-up now keeps the head read and the feed up. It backs off from 60 s, counts as a block or an error, and the gap is filled afterwards. Round-2 probes r1 and r1b now fail, and reverting the fix fails all three committed tests.
  - **S2:** `raise_if_cancelling()` runs first in all four handlers. Removing any one fails exactly its own variant of the new test, in about 22 s, with no hang. None of the 17 `except` clauses in feeds/ is left uncovered. An httpx timeout doesn't trigger a false re-raise.
- **Nits:**
  - N3 and N5-N10 are in; all four N5 pins catch their mutation.
  - N1 and N2 are partly fixed (E1, E2 below).
  - N4's decline was accepted.
- **Mutations:** 18 of 19 caught. The one that survives is CNN's `part="catch-up"` (E2).
- **The merge 2b6216c is clean:**
  - cli.py puts import-history inside PR 1's unreachable-database handler; otherwise the file has only PR 2's additions on top of f4194b7.
  - PR 1's db, runtime, lease, scheduler, stages, migrate and notify modules and their tests are byte-identical to f4194b7.
- **By hand:**
  - **Mirrors-only live run, 120 s:** SIGTERM exits 0 in 0.16 s and releases the lease. CNN did 8 polls (7 not modified) and trumpstruth 2. `first_seen_via` matches the earliest sighting on 100 of 100 posts. The log has 0 warnings and 0 errors.
  - **Unreachable database:** migrate, status and import-history each print one line and exit 1, with no password or URL.
- **Rules:** clean.

**Result: changes needed.** 1 blocker (the key leak), 1 should-fix, 7 nits and 1 question.

## How to answer

- Same as before: fix each blocker and should-fix, or decline it with a reason; nits are optional. Send me the new head and one line per id.
- PR 3's round 1 ([pr-260-round-1.md](pr-260-round-1.md), B1) has the same key leak for the Alpaca keys, and its S5 asks PR 3 to build its client with your `make_client`. Put the shared pieces (the key check and the error scrub) where PR 3 can reuse them, and tell PR 3's builder (session_018SyJAjgwB3XPJPjSHcuKjy) what they're called.

**Probes:** [pr-259-round-3-probes/](pr-259-round-3-probes/)
- `probe_sc_key.py` (B1) runs on its own, against a local socket only. It prints whether the key leaks.
- In `test_review259_r3_probes.py`:
  - `test_r3bug_…` pass at 7d96886 when the bug is real;
  - `test_r3check_…` and `test_r3control_…` are checks and controls that should keep passing.
  - Copy it into engine/tests/ to run, and don't commit it as it is.
- `conn_reuse_probe.py` and `conn_reuse_fix_check.py` are for E1.

---

## Blocker

### B1. A ScrapeCreators key with a stray space or newline is logged, stored where the web role can read it, and sent to the operator
- **Where:**
  - settings.py:70-73: `_empty_key_is_no_key` treats only "" as no key, so the value is taken as given.
  - mastodon.py:104-106 sends it as the `x-api-key` header.
  - base.py:137-138 builds `FeedFailed(f"{type(exc).__name__}: {exc}")`.
  - live.py:236 logs that reason.
  - live.py:242-247 puts it in the `feed_blocked` notice once the feed blocks.
  - live.py:248-256 writes it to `engine.feed_status.last_error`.
  - migrate.py:58-62: `WEB_GRANTS` gives the web role `SELECT` on `engine.*`.
- **Problem:** h11 refuses a header value with leading or trailing whitespace or a CR/LF. Its error includes the whole value: `LocalProtocolError: Illegal header value b'<key>\n'`. That text becomes the feed's failure reason.
- **Scenario:** the key is pasted into Railway with a trailing newline. Every ScrapeCreators poll fails, and each failure:
  - logs the key;
  - writes it to `feed_status.last_error`, which the web role (and so the public API's database user) can read.

  After five failures the feed blocks, and the `feed_blocked` message to the operator carries the key. Later PRs send that message out over Telegram.
- **Evidence:** `probe_sc_key.py` calls `Feed.get` against a local socket with the key plus `\n`, a space and `\r\n`. All three print `leaks | LocalProtocolError: Illegal header value b'probe-fake-sc-key-0123456789\n'` (and the same for the other two endings). Nothing contacted ScrapeCreators.
- **Fix:**
  1. Strip the key in Settings. Reject a value that isn't printable ASCII without whitespace, with a message that names the variable but not the value.
  2. In `Feed.get`, scrub any secret header values out of the error text before raising. A small helper that both PR 2 and PR 3 call keeps this in one place.
  3. Add a test over a real local socket with a key ending in `\n`. The key must not appear in the `FeedFailed` text, the log records, `feed_status.last_error` or the notice.

## Should-fix

### S1. A post Postgres can't store wedges the feed silently, and while a catch-up is owed CNN re-downloads its full file every poll (E5 + E3)
- **Where:**
  - live.py:334-341: `_run_feed`'s one handler logs a non-transient store error such as `DataError` and carries on. It writes nothing to `feed_status` or `source_stats`.
  - live.py:176 resets `catch_up_wait`/`catch_up_error` before `_answered` stores (197-214). If the store fails, `catch_up_after` is already in the past, so the next poll catches up again at once.
- **Problem:**
  - A post whose text holds `\u0000` makes every store fail with `DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`. Postgres text and jsonb both reject it.
  - While that post is in the feed's window, the feed stores nothing. Status still says "up" with an old last good read, and the counters show nothing. That is the silent failure the block and error design exists to prevent.
  - If a catch-up is owed at the same time, each 15 s CNN poll downloads the whole file (about 4 MB gzipped, 20 MB parsed) for as long as the post stays in the window. That goes against the brief's "gently". Paged feeds re-walk up to `catchup_max_pages`.
  - A full database outage is bounded by the lease. A store error that persists is not.
- **Evidence:**
  - `test_r3bug_poison_post_wedges_cnn_silently_but_no_hot_loop`: DataError, no status row, 0 signals, counters (0,0,0). There's no hot loop: retries run at the feed's interval.
  - `test_r3bug_failed_store_after_catch_up_downloads_again_every_poll`: 3 polls, 3 downloads. The control `test_r3control_failed_download_is_backed_off` gives 3 polls and 1 download.
  - The real CNN file has no such post today, since round 2's import of 36,625 succeeded.
- **Fix:**
  1. Strip `\x00` when mapping, in `clean_text` and in the raw strings stored.
  2. Have the per-feed handler record a non-transient store failure as an error count plus `last_error`, so status shows it.
  3. Reset the catch-up wait only after `_answered` commits, or start it before the attempt whatever the outcome.
  4. Turn the two `test_r3bug_` probes into tests.

## Nits (optional)

- **E1. N1 still doesn't reuse CNN's connection at the real poll rate** (base.py:126-130 and 37-47):
  - **304:** `get` returns from inside `client.stream(...)` without reading the empty body, so the connection is closed.
  - **Keep-alive:** `make_client` keeps httpx's default 5 s `keepalive_expiry`, but CNN polls every 15 s.
  - **Evidence:** the live run made a new TLS handshake to ix.cnn.io on 8 of 8 polls. Locally, 4 back-to-back 304s used 4 connections.
  - **Fix:** `await response.aread()` before `return None`, and `limits=httpx.Limits(keepalive_expiry=75)` in `make_client` (above the 60 s interval). Each gives 1 connection locally.
  - **Tests and PR body:** add a 304 and a gap to `test_cnn_range_reads_reuse_one_connection`. Otherwise drop the PR body's "so the connection is reused".
- **E2. Paged feeds' page-backs share the newest page's skip memo** (mastodon.py:47-50):
  - `statuses()` uses the default `part="read"` for page-backs too, so a catch-up resets the head's memo and the same odd item is warned about twice (`test_r3bug_n2_direct_page_back_resets_the_heads_skip_memo`).
  - **Fix:** thread `part` through `page()` and `statuses()`, and pass `part="catch-up"` from `read_back`.
  - **Tests:** add a test for the paged case. CNN's `part="catch-up"` (cnn.py:291) also needs one, since removing it passes every test.
  - **PR body:** "logged once" needs the same caveat until this is fixed.
- **E4. `import-history` clones GitHub and downloads CNN's file before it touches the database** (history.py:84-93):
  - With a wrong URL, all that work happens before the one-line error.
  - Since the whole import sits inside the "could not reach the engine database" handler, any mid-import `OperationalError` (a dropped connection, a statement timeout) is labelled that way too.
  - **Fix:** open the database first, for example by reading `trump_source_id` before the clone.
- **E6. The catch-up back-off carries over to the next incident** (live.py:159-162). The "reaches the mark" and "only checking" early returns leave `catch_up_wait` alone. In the probe, ScrapeCreators' first failure in a new incident waited 480 s instead of 60 s (`test_r3bug_catch_up_wait_is_not_reset_when_the_gap_closes_without_a_catch_up`). **Fix:** reset `catch_up_wait` and `catch_up_error` in those returns.
- **E7. A 20-digit status id fails every CNN poll instead of being skipped** (posts.py:23, 46-48):
  - `status_time` overflows for such an id. The `OverflowError` is raised in `_catch_up` (live.py:158-159), outside `map_items`, and isn't in `UNEXPECTED` (base.py:21).
  - One such item in CNN's first 32 KB blocks CNN after 5 polls (`test_r3bug_preexisting_a_20_digit_id_fails_every_cnn_poll_instead_of_being_skipped`). `import-history`'s `settled()` would crash on it the same way.
  - Real ids are 18 digits and won't reach 20 for a very long time, so this only matters for a malformed item.
  - **Fix:** add `OverflowError` to `UNEXPECTED` and compute `posted_at` inside the mapper, or range-check the id in `parse_status_id`.

## Question

- **Q1. Should a refused catch-up notify the operator?** A 403 or 429 during a page-back or the full download now counts as a block and shows in status as "catch-up owed". It sends no `notify_operator`, because the feed stays up, which is what round 2 asked for. My default is to leave it as is: status and the block count show it, and the head keeps flowing. Say so if you see it differently.

## Dropped

- **"left N posts" double-counting posts in both archives** (history.py:107): it counts items in the files by design, like the totals line.
- **`settled()` crashing on a bad CC0 id:** this isn't a regression, since `cnn_post` raised on the same items before N7. E7 covers the overflow case.
- **Catch-up counts lost when the store fails:** every counter in a failed transaction is lost, consistently.
- **The memo hiding a growing count of the same reason:** that is what round 2 asked for.
