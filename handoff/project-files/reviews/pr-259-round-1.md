# PR #259 "Engine PR 2: sources and signals": review round 1

Reviewed: PR 2's own commit only, `git diff a69a1dd 4cb9f49` (a69a1dd = PR 1's head when PR 2 branched; 4cb9f49 = PR 2's head). Line numbers are at 4cb9f49.
Passes: **simplify** (reuse, simplification, altitude), **review** (correctness and project rules; built-in code-review at high effort plus clauDNA review-work), **verify** (clauDNA verify-completion against /mnt/project-files/build-briefs/engine-pr2.md). Each pass ran in a fresh agent; findings are merged, de-duplicated and checked against the code.

## Before you start: PR 1 changed under you

PR 1 (#258) folded in its own round 1 at be04d50 (/mnt/project-files/reviews/pr-258-round-1.md), and its round 2 is running now. Merge `claude/engine-foundation-k6mh6s` into your branch (a merge commit; no rebase or force-push) before or while you fold these in. APIs that changed and that your code touches:
- `Settings.database_url` is now a `SecretStr`; code uses `settings.db_url`.
- `configure_logging(level)` lost its parameter (you edited logs.py, so expect a conflict).
- `StageRunner(batch_size=...)` and `Lease(name=...)` are gone.
- Workers now restart with a capped back-off and one message per failure streak (`FailureStreak`); any other engine-work failure steps down, notifies once, backs off and retakes the lease.
- Settings validation got stricter (timings `gt=0`, `max_attempts ge=1`).
- The lease has its own pool; migrations pin `search_path` to public.

## Where it stands

- Every requirement in the brief is delivered and works when run. Verify re-ran it fresh: ruff, ruff format and mypy strict are clean; pytest 82/82 twice; one Alembic head (0002); CI green on 4cb9f49.
- By hand on a throwaway database: `import-history` printed 29,469 + 7,155 = 36,624 added (same as the PR body), and a second run added 0. A 170 s mirrors-only live run (direct and ScrapeCreators off, no key) polled CNN 12 times (11 not-modified) and trumpstruth 3 times, and stored one new real post at stage `score` via trumpstruth. The burst numbers match the PR body exactly, and an independent SQL check gives the same.
- First copy wins holds under real overlapping writes. Post time from `id >> 16` is within 1 ms on all 36,624 rows. The ScrapeCreators key stays in the header (no redirects, nothing logged).
- Your ten defaults are reasonable and accepted. Nine have tests; #6 (trumpstruth can't page back) has none.
- Rules all pass: only ENGINE_ variables, no old key names, no old-code imports, honest User-Agent, no proxies/impersonation/logins, untouched old folders, no committed data beyond test slices, unverified fixtures marked.

**Result: changes needed.** 0 blockers, 9 should-fix, 19 nits.

## How to answer

Fix each should-fix, or decline it with a reason. Nits are optional; take the cheap ones. When you push, send the gauntlet thread (session_013E4KMGG5c9USVygEcNJkqa) the new head commit and one line per finding id: fixed, or declined and why.

Proof-of-bug probes are in [pr-259-round-1-probes/](pr-259-round-1-probes/): `test_review259_probes.py` (23 probes plus controls, using your conftest and tests/feeds_helpers.py; copy it into engine/tests/ to run) and `mutate.py` (the mutation script behind S7). Against 4cb9f49 every probe passes, which means each bug is real. They were written to prove bugs, not as finished tests: turn the ones you need into proper regression tests, and don't commit them as they are. After merging PR 1, some probe setup may need `db_url`/`SecretStr` tweaks.

---

## Should-fix

### S1. Catch-up can skip a gap silently and for good, depending on which feed stores first after an outage (review)
- **Where:** engine/engine/feeds/live.py:100-114 (`_with_catch_up` compares against the newest post *any* feed stored); engine/engine/feeds/store.py:37-43 (`newest_posted_at`).
- **Problem:** after a restart following a long outage, every feed is due at once. If a feed whose read doesn't reach back stores first (trumpstruth's roughly 4-day window, or direct after its page cap), the others then find a "newest stored" post inside their own window and skip catch-up. CNN never downloads its file, the posts between the old newest post and the start of that window are never fetched, and no operator message goes out. Later polls can't notice it, since every read then overlaps stored posts.
- **Scenario:** mirrors only (the setup until PR 7), engine down 6 days. On restart trumpstruth answers before CNN's range read. CNN's head (about 2.5 days) is then all older than the newest stored post, so days 6 to 4 are missing for good.
- **Evidence:** `test_p1_gap_hidden_when_trumpstruth_stores_first` (0 downloads, gap not stored, even after 3 more CNN polls); control `test_p1_control_cnn_first_fills_gap` (CNN first fills it); `test_p1b_real_loop_race` through the real `Live.run()`: with CNN 0.1 s slower the gap stays empty, with trumpstruth 0.1 s slower it fills.
- **Fix:** decide catch-up per feed. Snapshot `newest_posted_at` once in `Live.start()` before any feed stores, keep a per-feed `caught_up_to` starting there, persisted in `engine.feed_status` (0002 isn't merged, so add the column there), and catch up when a read's oldest post is newer than the feed's own `caught_up_to`. Advance it only after a store that reached back (for a feed that can't page back, after warning once). Add the P1 probe as a regression test with trumpstruth polled first.

### S2. The ETag is saved before the poll succeeds, so a failed catch-up or store is never retried (review)
- **Where:** engine/engine/feeds/base.py:95-96 (`self._etag = ...` inside `get`, before parsing, catch-up and store); used by cnn.py:80-92 and mastodon.py:81.
- **Problem:** after a 200 or 206 the poll can still fail: the CNN full download fails, a direct page-back fails, a parse error, or the store transaction fails on a Neon blip. The next poll sends the new `If-None-Match`, gets 304, and the feed reads as "up" with nothing to store. That feed never stores those posts and never retries the catch-up; with S1, a gap can stay for good.
- **Evidence:** `test_p2_failed_catch_up_is_never_retried` (download 503 on poll 1; five healthy polls later: state up, 1 download, head not stored); `test_p2_failed_store_is_never_retried` (one `OperationalError`; then 10 store calls, head never stored).
- **Fix:** return the ETag in `Read` (e.g. `Read.etag`) and have `FeedPoller` commit it to the feed only after `_answered`'s transaction commits; leave it unchanged on `FeedFailed`, `FeedBlocked` or a database error. Retry a failed catch-up on the feed's back-off, not every 15 s, so a failing 4 MB download isn't repeated at the poll rate.

### S3. One odd answer from one feed cancels every feed, and the worker then restart-loops (review, simplify)
- **Where:** live.py:228-237 (`_run_feed` catches only `SQLAlchemyError, OSError`; `Live.run` is one TaskGroup); live.py:93-96 (`poll` catches only `FeedBlocked`, `FeedFailed`); cnn.py:26-29, 36, 88-92, 95-98; mastodon.py:84-87 and 107-113. The four parse-error handlers have drifted: only ScrapeCreators catches `AttributeError`.
- **Problem:** an `AttributeError` from a malformed answer aborts the TaskGroup: a CNN 200 whose body is a JSON object, a CNN 206 error body like `{"message": "...", "codes": [429]}` (`leading_items` takes the first `[` anywhere and returns `[429]`), or a direct list containing `null`. The worker restarts; each restart builds a new `Live`, so blocked feeds are polled again at once with a new "feed_blocked" message (see S4), and ScrapeCreators makes a paid call. PR 1's new FailureStreak caps the `worker_failed` messages, but the re-polling and repeat block messages remain.
- **Evidence:** `test_p3_cnn_json_object_kills_all_feeds` (ExceptionGroup with `AttributeError`, trumpstruth cancelled); `test_p3_direct_list_with_null_kills_all_feeds`; `test_p3b_crash_loop_resets_blocks` through `run_engine` with a 0.1 s restart at the old PR 1 code: 13 `worker_failed`, 13 `feed_blocked`, 13 direct requests in 1.5 s. Simplify's probe: a JSON list of non-objects makes both `DirectFeed.read()` and `CnnFeed.read()` raise a bare `AttributeError`.
- **Fix:**
  - One helper next to `FeedFailed` in base.py, e.g. `@contextmanager def unexpected_answer()`, catching `(ValueError, KeyError, TypeError, AttributeError)` and raising `FeedFailed`; use it at all four places.
  - Type-check items in the mappers (`cnn_post`, `mastodon_post` raise `FeedFailed` when an item isn't a dict), and make `leading_items` require the body to start with `[` (`text.lstrip().startswith("[")`).
  - As the backstop, catch `Exception` per poll in `_run_feed` (letting `CancelledError` through), log it with its traceback, and count it as a failed poll, so five in a row back off instead of crashing the worker.
  - Add a test that an odd CNN body leaves trumpstruth polling.

### S4. Block state lives only in memory, so a restart or handover breaks "one message per incident and one on recovery" (review)
- **Where:** live.py:62-75 (`FeedPoller` state), live.py:210-219 (`Live.start()` restores only "off" rows and `feeds_dark_since`), live.py:81-86 (`last_poll is None` means due now).
- **Problem:** every new `Live` (a deploy's lease handover, a worker restart, a lease loss) starts each feed "up" and polls it at once, even when `engine.feed_status` says it is blocked with a 30-minute back-off. If the block holds: a second "feed_blocked", the back-off restarts at 1 minute, and `blocked_since` moves. If it lifted across the handover: no "feed_recovered" at all.
- **Evidence:** `test_p4_restart_forgets_block_new_message_and_immediate_poll` (2 `feed_blocked`, `blocked_since` moved); `test_p4b_recovery_after_handover_is_never_announced` (1 blocked, 0 recovered).
- **Fix:** in `Live.start()`, restore blocked rows from `feed_status`: stored `blocked_since`, the back-off (add `backoff_seconds` to `feed_status` in 0002, or derive it), and the next try at `updated_at + backoff` on the database clock. Don't re-send "feed_blocked" for a restored block; send "feed_recovered" when it answers. Optionally persist ScrapeCreators' last check so each deploy doesn't add a paid call. Test: block, new `Live`, no request before the back-off, one blocked notice in total, one recovery notice after the handover.

### S5. A blocked feed can poll more often than a healthy one (review)
- **Where:** live.py:85, `wait = self.backoff if self.state == "blocked" else self.live.interval(self.name)`.
- **Problem:** the back-off starts at 60 s, but ScrapeCreators' healthy interval is 120 s (fallback) or 3600 s (hourly check). A bad key or empty balance (401/402) turns the hourly check into 6 paid calls in the first hour; a 429 makes it retry sooner than when healthy, the opposite of "back off; never evade".
- **Evidence:** `test_p5_blocked_scrapecreators_polls_faster`: healthy 120 s vs blocked 60 s; on a bad key, waits of 60, 120, 240, 480, 960, 1800 s against a healthy 3600.
- **Fix:** `wait = max(self.backoff, interval) if blocked else interval`. Test: a blocked ScrapeCreators with direct healthy isn't due before 3600 s, and with direct off not before 120 s.

### S6. If CNN ever answers 200 (Range ignored), every poll pulls the whole file and still stores nothing (review)
- **Where:** cnn.py:80-92 (`Accept-Encoding: identity`; on a 200, `response.json()` parses the whole body and maps every item); store.py:102-112 (the sightings insert is one statement, not batched like signals' `BATCH = 500`).
- **Problem:** on a 200 the poller downloads about 20 MB uncompressed every 15 s (about 115 GB a day from a source we promised to read gently), parses 36k posts on the event loop (about 1.2 s stall), and tries to store them all. The single sightings `INSERT` exceeds psycopg's 65,535-parameter limit, the transaction rolls back, it's logged as "database write failed", and the feed stays "up" with nothing stored. Any store of 32,768 or more posts fails the same way, including a very large catch-up.
- **Evidence:** `test_p7_cnn_200_full_file` (synthetic 36,624 items, 18.7 MB: 4 full transfers and 75 MB in 40 s, 0 stored, the parameter-limit error); `test_p7b_store_posts_over_32767_posts_fails` (33,000 posts fail after 10.7 s, 0 rows).
- **Fix:** read at most `HEAD_BYTES` whatever the status (`client.stream(...)` and stop at 32 KB, then `leading_items`); on a 200, log a warning and count a failure so repeated 200s back off; batch the sightings insert and the `first_seen` update with the same `BATCH`.

### S7. Promised behaviours with no test that would catch their breakage (review, verify)
- **Mutations that pass every feed test** (`mutate.py`): CNN stops sending `If-None-Match` (cnn.py:84; `test_cnn_304_and_full_download_retry` answers 304 whether or not the header was sent); the `errors` and `blocks` counters swapped (live.py:160); `not_modified` never counted (live.py:131); `polls` never counted (live.py:130); `Live.start()` no longer reloads `feeds_dark_since` (live.py:215-217, so "one dark message across a restart" is unpinned); ScrapeCreators pages with `max_id` instead of `next_max_id` (mastodon.py:101-102).
- **Untested paths:** the trumpstruth `originalUrl` fallback (trumpstruth.py:22-25); trumpstruth post time (no assertion against `pubDate`); the feeds worker's registration in `build_registry()`.
- **Fix:**
  - CNN: route a 304 only when `If-None-Match` matches, and assert it on the second read.
  - Drive a 304, a 500 and a 403 through `FeedPoller` and assert the `source_stats` row (`polls`, `not_modified`, `errors`, `blocks`, `posts_seen`, `posts_first`).
  - A two-`Live` dark test: dark, new `Live`, then exactly one `feeds_dark` and one `feeds_back`.
  - ScrapeCreators catch-up: copy `test_catch_up_pages_back_without_duplicates` with a key set and the other feeds off; assert the second request carries `next_max_id` = the oldest id on page one and no `max_id`, 2 requests, gap posts at `score`, no duplicate keys.
  - trumpstruth: an item with no `originalId`, an `originalUrl` for 117307289681145880 and a description linking 117304284426928910 gets id 117307289681145880 and `points_to` 117304284426928910; an `originalUrl` that isn't a Truth Social status link raises `FeedFailed`. Assert `0 <= posted_at - pubDate < 1 s` for each fixture item (verify checked all 8 hold).
  - `assert "feeds" in build_registry().workers`.
  - Regression tests for S1-S6.

### S8. The ScrapeCreators fixture set is short of the brief (verify)
- **Where:** tests/fixtures/scrapecreators_posts.unverified.json; tests/test_feed_mapping.py:264-273.
- **Problem:** the brief asks for hand-built direct and ScrapeCreators fixtures with a post, a reply, a quote, a repost, a media-only post and an HTML challenge page. The ScrapeCreators set has only a post, a repost and a reply, and its test asserts kinds only.
- **Fix:** add a quote and a media-only status (and use the challenge page for ScrapeCreators too); assert key, kind, `points_to`, text, `has_media` and `posted_at` against `created_at`, as the direct test does.

### S9. The test helper pins four timings to their default values, so the back-off test checks the helper, not the shipped defaults (simplify)
- **Where:** tests/feeds_helpers.py:110-114; the back-off test at tests/test_live.py:124-148.
- **Evidence:** changing the default `feed_backoff_min_seconds` to 120 passes every test at 4cb9f49; with the fix below, the back-off test fails as it should.
- **Fix:** delete the four default-valued lines from `feed_settings()`; tests that need other values already pass them.

## Nits (optional)

- **N1. Mojibake repair runs on every feed and can rewrite correct text** (posts.py:31-33, 113; review). `html_text("<p>CAFÉ&nbsp;OWNERS</p>")` gives `CAFɠOWNERS`. No false positives in the CC0 data, but 30 CC0 posts keep an orphan `Â` or a truncated emoji after repair, and since CC0 is imported first they win over CNN's clean copy. Fix: repair only on the CNN/CC0 path (`plain_text`), not in `html_text`; optionally drop an orphan `Â` before whitespace or at the end.
- **N2. `download_archive` skips `Feed.check()`** (cnn.py:51-73; review). A 403/429 during catch-up is a plain failure, not a block, and a 200 HTML challenge is retried 3 times. Fix: route it through `check()` and don't retry a block.
- **N3. One bad item fails the whole read** (trumpstruth.py:34-39, same pattern in cnn.py and mastodon.py; review). A trumpstruth item without `originalId`/`originalUrl` (a site notice, say) fails every poll; after 5 the feed is "blocked" with a misleading message, and its 99 good items are never stored from that feed. Probe `test_p10_one_bad_item_blocks_trumpstruth`. Fix: skip, log and count the bad item, keep the rest.
- **N4. Every successful CNN catch-up logs a false "could not read back" warning** (live.py:110-113; review). CNN's `read_back` returns only posts newer than `until` (cnn.py:99), so the check always fires, including in `test_cnn_catch_up_reads_the_whole_file`. Fix: have `read_back` report whether it reached `until`.
- **N5. Two "feeds_back" messages when two feeds answer together** (live.py:239-247; review). `answered()` awaits the database before clearing `dark_since`. Probe `test_p8_two_feeds_back_messages`. Fix: clear it before awaiting, or use a lock; the same race lets `_go_dark` write after `answered()` cleared it.
- **N6. "blocked since None"** (live.py:153-169; review). If the `feed_status` write fails while entering a block, the notice is out but `blocked_since` stays None. Probe `test_p11_blocked_since_none`. Fix: set `blocked_since` before the write.
- **N7. New feed settings have no bounds** (settings.py:42-62; review). `feed_backoff_min_seconds=0` hammers a blocked host, `feed_failures_to_block=0` blocks on the first failure, `feed_tick_seconds=0` busy-loops, `catchup_max_pages=0` disables catch-up. Fix: `gt=0` / `ge=1`, matching PR 1's new validation.
- **N8. Catch-up parses and maps the full file on the event loop** (cnn.py:61, 94-99; review, simplify). About 1.2-1.9 s of CPU and about 72 MB peak per catch-up. Fix: filter on `status_time(parse_status_id(item["id"])) > until` before mapping (0.07 s, per simplify), and/or `asyncio.to_thread` for the parse.
- **N9. `import-history` can race a running engine** (history.py:79-97; review). Posts minutes old get stored as imported and skip live scoring. Fix: skip CNN posts newer than about an hour, or document that the import runs before the first deploy.
- **N10. Direct catch-up also stores posts older than the stored one, at `score`** (mastodon.py:57-69; test_live.py:252; review). The PR body's "nothing older than the stored post" holds for CNN only. Fix: filter `posted_at > until` as CNN does, or fix the claim.
- **N11. Mixed clocks in the dark message** (live.py:256-270; review, simplify). The message uses the host clock, `feeds_dark_since` the database's; the brief says one clock. Fix: use the `now()` returned by the update.
- **N12. `Feed.expects` adds nothing** (base.py:59-60, 110-111; cnn.py:78, mastodon.py:47, trumpstruth.py:46; simplify). It only matters for content types holding both "html" and "json"/"xml" (e.g. `xhtml+xml`), where it lets a page through. Fix: `if "html" in content_type: raise FeedBlocked(...)` and drop the ClassVar.
- **N13. `Live(clock=...)` is a test hook no test uses** (live.py:41, 176, 180 and 5 call sites; simplify). Fix: call `time.monotonic()` directly.
- **N14. `SIGNAL_KINDS` and `NOT_SCORED` are never used** (tables.py:93-94; simplify, verify). Fix: build the two CheckConstraints from them, or delete them.
- **N15. `build_registry()` imports inside the function to dodge an import cycle** (registry.py:63-69; simplify). Each later PR would copy it. Fix: move `build_registry()` to cli.py, its only caller, and update the registry.py docstring and engine/README.md:54. Check this against PR 1's latest registry first.
- **N16. Test helper cleanups** (simplify): test_feed_mapping.py:28 `KEY_STATUS` is the account id (import `ACCOUNT_ID`); :36-38 the async generator fixture can be sync; :257-259 `test_every_feed_names_itself` should check `tuple(f.name for f in FEEDS) == FEED_NAMES`; test_live.py:98-104 and test_feed_mapping.py:96-105 repeat the same two block-route lambdas (share them in feeds_helpers.py).
- **N17. Hard-coded download retry pause** (cnn.py:66, `asyncio.sleep(2 * attempt)`; verify). It makes one test take 2 s. Fix: a setting, or patch the sleep in that test.
- **N18. PR body wording** (verify): "7,377 media-only" is 7,375 media-only plus 2 posts with neither text nor media.
- **N19. Three imported posts keep HTML entities** because CNN's source escaped them twice: 111816932435666592, 109530624305246261, 108771228720714184 (verify). Optional: unescape until stable.

## Dropped

- `trust_env=True` in `make_client` (a proxy variable in the environment would be used): the sandbox's own egress needs it, and the brief's "no proxies" rule is about evasion, not the platform's configured egress.
- Not backed or not worth it: `Feed.get` returning `Response | None`; a helper for the shared 2-line quote-or-post ending; `Live.interval` building a dict per call; the ScrapeCreators key check mypy needs; the newest-post query per poll (indexed); repeated small test query helpers; migration 0002 written out in full (migrations should be frozen snapshots).
- Not this PR's concern: PR 4 and 5 batch selection. Imported text posts are exactly `not_scored = 'imported'`; reposts and no-text posts carry their own reasons.
