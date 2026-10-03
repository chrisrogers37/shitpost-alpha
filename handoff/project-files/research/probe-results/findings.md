# Railway probe results: Truth Social sources, 24 hours

Run: service `shitpost-alpha-cloud-proj-test` (Railway, us-east4), 2026-09-30 17:35 to
2026-10-01 17:35 UTC, branch `claude/project-thread-yfvll0` (PR #257, do not merge).
Polling: direct sources and both trumpstruth feeds every 60 s, CNN every 20 s.
Lag = time first seen by the probe minus the post's `created_at`. It includes up to one
poll interval of detection delay (up to 60 s for direct, 20 s for CNN).

Files here: `new_posts.jsonl` (every first-seen record, rebuilt from Railway logs with
`rebuild.py`), `lag_per_post.csv` (one row per post, lag per source).

## Delay per source (36 Trump posts)

| Source | p50 | p90 | p95 | max | under 4 min | under 10 min |
|---|---|---|---|---|---|---|
| direct (truthsocial.com API, plain) | 0.8 min | 1.2 | 1.2 | 1.3 | 36/36 | 36/36 |
| direct_cf (same, Chrome impersonation) | 0.8 min | 1.2 | 1.2 | 1.3 | 36/36 | 36/36 |
| trumpstruth, cache-busted | 3.6 min | 36.1 | 46.2 | 69.2 | 19/36 | 27/36 |
| CNN archive JSON | 14.4 min | 22.2 | 22.5 | 44.1 | 5/36 | 10/36 |
| trumpstruth, Cloudflare-cached `/feed` | 74.5 min | 118 | 126 | 127 | 0/31 | 0/31 (5 never seen before run end) |
| best of CNN or trumpstruth-fresh | 3.4 min | | 19.4 | 22.5 | 20/36 | 29/36 |

## Reliability and blocking
- No failed, blocked or rate-limited request found. A log filter for polls with any status
  other than 200 or 304 returned nothing over the 24 hours (checked via the Railway log
  filter, not by counting every poll).
- The direct API answered every poll with HTTP 200, without login, behind Cloudflare
  (`cf-cache-status: DYNAMIC`), in about 50 ms, and sent no rate-limit headers.
  Plain `urllib` worked as well as Chrome impersonation.
- Every source saw all 36 posts, except the cached trumpstruth feed, which had not yet
  shown the last 5 posts when the run ended.

## Why the mirrors are slow
- CNN rewrites its archive file roughly every 8 to 30 minutes (judged from the times the
  probe got a 200 instead of a 304), not every 5 minutes, and paused for about 4 hours overnight
  (04:57 to 09:13 UTC). Its median delay is 14 minutes.
- trumpstruth's own origin is usually fast (median 3.6 min) but sometimes falls behind by
  30 to 70 minutes. Its public `/feed` is cached by Cloudflare for up to 2 hours, so it must
  always be cache-busted.

## Against the plan's targets (p50 under 4 min, p95 under 10 min)
- Mirrors only, best of both: p50 3.4 min passes; p95 19.4 min fails (7 of 36 posts over
  10 min, worst 22.5 min).
- Direct API: p50 0.8 min and p95 1.2 min, far inside both targets.
- So the free mirrors meet the median target but not the tail. Only the direct API meets
  both. That API is against Truth Social's terms (sections 7.1, 7.6, 7.9, 7.22), which is
  why Chris limited it to this test.
