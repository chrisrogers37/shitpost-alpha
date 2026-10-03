# PR #259 "Engine PR 2: sources and signals": review round 4

Reviewed 558d50c, the round-3 fold-in on 7d96886. One agent ran the review and verify passes together:
- the built-in code-review at high effort plus clauDNA review-dimensions;
- clauDNA verify-completion;
- earlier rounds' probes, 17 new probes, 24 + 2 mutations, and a by-hand live run.

Earlier rounds: [1](pr-259-round-1.md), [2](pr-259-round-2.md), [3](pr-259-round-3.md).

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 188/188 three times, once as a superuser named `engine` like CI.
  - Alembic has one head (0002), and CI is green on 558d50c.
- **Round 3:**
  - **B1 is fixed.** `probe_sc_key.py` now prints "clean" for `\n`, a space and `\r\n` (`Illegal header value b'[key]\n'`). By hand, `status` with fake keys:
    - a trailing newline is accepted;
    - a space, a non-ASCII character or a control character exits 2 with one line;
    - the key never appears in any output.
  - **S1 is fixed.** NULs are dropped, and a store that keeps failing now shows in status as `up (DataError: …)`. The round-3 probe gives 1 download in 3 failed-store polls.
  - **E1, E2, E4 and E6 are fixed.** In the live run CNN made 1 TLS handshake in 8 polls (round 3: 8).
  - **E7 is partly fixed:** N3 below covers the gap.
  - **Q1** is agreed and documented.
- **Probes and mutations:**
  - All 5 round-3 bug probes now fail, and the 9 checks and controls pass. Round-1 and round-2 probe results are unchanged.
  - 19 of the 24 mutations are caught. The ones that survive are harmless, except the keep-alive (N6) and `_record_failure`'s cancellation re-raise (N8).
- **By hand:**
  - The mirrors-only run lasted 120 s, and SIGTERM exits in 0.22 s.
  - `first_seen_via` matches the earliest sighting on 100 of 100 posts.
  - The log had 0 warnings and 0 errors, and nothing contacted truthsocial.com or ScrapeCreators.
  - With the database unreachable, migrate, status and import-history each print one line.
- **Rules:** clean. Nothing still imports `make_client` from its old place.

**Result: PR 2's own code passes.** There's no blocker or should-fix left; the 9 nits below are optional.

**What's still to come:** PR 1's round 3 ([pr-258-round-3.md](pr-258-round-3.md)) asks PR 1 for three more fixes: connect timeouts and a bounded `release()`, a job rerun, and a test that can hang. When PR 1 pushes, merge it in and send me the head. I'll check that merge and any nits you fold in, then send the final "passed".

## How to answer

- The nits are optional.
- If you take any, push them with the PR 1 merge. I'll check them together.
- [pr-259-round-4-probes/test_review259_r4_probes.py](pr-259-round-4-probes/test_review259_r4_probes.py) holds the probes. The `test_r4bug_…` ones pass at 558d50c when the bug is real. The `test_r4check_…` ones show the behaviour or pin a fix.

## Nits (optional, file:line at 558d50c)

- **N1. A lone surrogate (half of an emoji) wedges a feed the way a NUL did** (posts.py:114-118, store.py:52-61).
  - While such a post is in a feed's newest read, every store fails. Status shows `up (UnicodeEncodeError: … surrogates not allowed)`.
  - It's unlikely: a source would have to cut text mid-character.
  - **Fix:** drop `[\x00\ud800-\udfff]` instead of just `\x00`. Real emoji are kept.
  - **Probe:** `test_r4bug_lone_surrogate_wedges_cnn_like_a_nul_did`.
- **N2. Status shows no reason while a catch-up's read worked but its store failed** (live.py:164-170, 181-183).
  - This is new with the back-off move. Later polls store the newest posts with no error, so status reads plain "up" while the gap is still owed.
  - **Fix:** set `catch_up_error` to "catch-up to … not stored yet" before `read_back`.
  - **Probe:** `test_r4bug_status_shows_no_reason_while_a_read_back_waits_for_its_store`.
- **N3. E7 isn't fixed on trumpstruth's `originalUrl` fallback** (trumpstruth.py:17-28).
  - That path returns the id without the range check, so an id past a bigint fails every poll, and the feed blocks after 5.
  - **Fix:** `return parse_status_id(url["id"])`.
  - **Probe:** `test_r4bug_trumpstruth_original_url_past_a_bigint_fails_every_poll`.
- **N4. A refused key is printed in full outside the engine's own CLI** (settings.py:15 and 84, migrations/env.py:12).
  - pydantic's error includes the input. Running `alembic upgrade head` directly printed `input_value='fake r4 probe key 0123'`. `python -m engine …` is safe.
  - **Fix:** `hide_input_in_errors=True` in the settings config. PR 3's merge already adds it, so take it here and PR 3's copy becomes a no-op.
- **N5. `httpx.Limits(keepalive_expiry=75)` removes httpx's connection caps** (http_client.py:38).
  - Both caps become unlimited instead of 100 and 20. This has no effect today, but matters once PR 3's price client fans out through `make_client`.
  - The docstring (http_client.py:14-15) and README:39-40 also say 75 s covers every feed. ScrapeCreators polls every 120 s or 3,600 s.
  - **Fix:** pass `max_connections` and `max_keepalive_connections` explicitly, and limit the claim to the 15 s and 60 s feeds.
- **N6. No committed test exercises the 75 s keep-alive** (test_feed_mapping.py:348, test_live.py:796).
  - Both tests pass their own transport, and httpx then ignores the client's limits.
  - **Fix:** build the client with `make_client(settings)` in the reuse test, with one gap longer than 5 s.
- **N7. `import-history` on an unmigrated database prints a 141-line traceback, where `status` prints one line** (history.py:86-87, cli.py:54-66).
  - It does stop before downloading.
  - **Fix:** catch `ProgrammingError` and print the "not migrated" line.
- **N8. No committed test pins `raise_if_cancelling()` in `_record_failure`** (live.py:362-364).
  - Without it, a cancellation during that write is swallowed. If later polls succeed, the feed never stops.
  - **Fix:** add a variant to the cancellation test where the store fails once and then works, as `test_r4check_record_failure_stops_on_a_converted_cancel_then_good_polls` does.
- **N9. A far-future post time moves the catch-up mark and hides later gaps** (posts.py:39-43, live.py:160-161; older code).
  - A 19-digit id, or an 18-digit one with a bad first digit, gives a post time centuries ahead. The feed's mark moves there, so later gaps are never caught up, silently.
  - **Fix:** skip as odd any post more than about a day in the future.
  - **Probe:** `test_r4bug_a_far_future_id_moves_the_mark_and_hides_the_next_gap`, against a control that fills the gap.

## Dropped

- The scrub forms surviving one at a time: the test key reads the same either way, so this is harmless.
- `from None` vs `from exc`: nothing logs that traceback today. Keep `from None`.
- E4's other half: a mid-import `OperationalError` is still labelled "could not reach". It's left as is, since a rerun is safe.
