---
name: engine-pr2-build
description: Engine PR 2 (#259, sources and signals): what it built, data facts found, and sandbox tips for later engine builders (2026-10-02)
metadata:
  type: project
  modified: 2026-10-02T20:57:00.000Z
---

Draft PR #259 (branch claude/engine-sources-i0sp5e, on top of #258; merge after #258). Thread "Build engine PR 2" (cmsg_01Ru8H43VFwFbPoWty16Gd6hTiii8z7iqnx2waJtEkFoHv). Gauntlet round 1 (/mnt/project-files/reviews/pr-259-round-1.md) folded in at 0974fe2 on 2 Oct 14:5x UTC; #258's be04d50 merged in at b54bc26 (merge commits only). Gauntlet thread session_013E4KMGG5c9USVygEcNJkqa re-checks. Round 2 (pr-259-round-2.md) folded in at 872135b (2 Oct 17:25 UTC); S2 (raise_if_cancelling in every feed-loop handler) at 7d96886 (18:04 UTC) after merging PR 1's f4194b7 (2b6216c). Round 3 (pr-259-round-3.md: key leak B1, NUL/stuck-feed S1, nits) folded in at 558d50c (2 Oct 19:03 UTC). Shared with PR 3: engine/http_client.py (make_client, USER_AGENT, SECRET_HEADERS, request_error_text; raise from None) and Settings._clean_keys (add key fields to its decorator); PR 3's builder told. Round 4 (pr-259-round-4.md: PR 2 code passed; 7 of 9 nits, N6/N7 declined) at 0e92d5c; PR 1's round 3 (99fe7bb) merged at edbbc13, where TRANSIENT_ERRORS was gone so _run_feed now retries on `SQLAlchemyError | OSError and not is_permanent(exc)`. PASSED the gauntlet at edbbc13 (pr-259-round-5.md, 2 Oct 19:53 UTC); told Chris in the thread. Optional note left as is: transient DB errors in _run_feed only warn (recording them would add a DB write while the DB struggles). Later merges of PR 1 (5e13024 at a58681f, round-4 nits 201e01e at 85bd2f0, 213 tests) re-confirmed by the gauntlet; PR 1 passed at 201e01e. Both PRs wait only on Chris's merge (#258 first). If PR 1 pushes again: merge, send the gauntlet the head, it checks that merge only.

Built: engine/feeds/ (posts, base, mastodon [direct+scrapecreators], cnn, trumpstruth, store, live, history, status); migration 0002 (engine.sources seeded, signals, signal_sightings, source_stats, feed_status, engine_meta.feeds_dark_since). signals.not_scored = repost | no_text | imported; text posts wait at stage "score" (PR 4). Imported history: raw_via/first_seen_via cc0_archive or cnn_archive, no sightings. Catch-up is per feed: feed_status.caught_up_to (mark) + backoff_seconds; Live.start() restores block state/last poll from feed_status; ScrapeCreators' hourly check (direct up) never pages back. PR 4/5 batch set = not_scored='imported' (21,609 text posts).

Data facts (2 Oct 2026, differ from the PR 2 brief):
- CC0 copy (stiles/trump-truth-social-archive @40a8834) has 29,469 posts to 2 May 2026, with a gap Nov 2025-Apr 2026; CNN file has 36,624 (all CC0 ids included). Import = CC0 + 7,155 CNN-only.
- Mirrors: reposts are "RT @handle<text>" (handle glued) or "RT: <status url>"; no "RE: url" quotes in CNN; a quote with no words is a bare status URL (278). ~890 CNN posts have Latin-1 mojibake; CNN text has HTML entities. trumpstruth RSS has no media info and no paging.
- id>>16 can differ from CNN created_at by a few ms (within 1 s).
- Bursts: 80.1% of text posts within 30 min of another; 43% within 5 min.

Sandbox tips: engine venv /home/user/engine-venv (pip install -e ".[dev]" in engine/); start Postgres with `service postgresql start` + role/db from the dev-db recipe steps 1-2 (old ORM schema not needed). curl/httpx need no CA tweaks (SSL_CERT_FILE is set). CNN full download is ~4.9 MB gzip.

Related: [[plan-stage]], [[engine-live-sourcing]], [[truth-social-sourcing]], [[dev-database-branch]]
