# Probe parser check against live CNN and trumpstruth feeds (2026-09-30, 15:04 to 15:17 UTC)

Branch `claude/project-thread-yfvll0` at e3ff34d, `probes/truth_social_latency/ts_probe.py`.
Ran only the `cnn` and `trumpstruth` sources, 11 polls each at 60 s, from the
shitpost-alpha sandbox (Anthropic proxy). The Truth Social API was not called.
The branch was not edited. The proposed fix is `parser-fix.diff`. It applies cleanly
to e3ff34d, and its 5 tests pass (4 existing plus 1 new).

## CNN archive (ix.cnn.io): parser correct
- It's a JSON list of 36,571 posts, newest first, 20.3 MB (3.7 MB gzipped).
- Every post has a string `id`, `created_at`, `content`, `url` and `media`. No IDs are missing or duplicated.
- `created_at` is the real post time. It agrees with the ID's embedded timestamp
  (Mastodon snowflake, `id >> 16` = ms) to within 1 s on all 36,571 posts.
- `parse_cnn` returns the right 50 newest IDs and timestamps.
- Text: `content` is plain text. It's empty on 7,361 posts, which are media-only.
  Retruths start with `RT @user`. The probe doesn't read text, and it doesn't need to.
- 2 of 11 polls failed with `IncompleteRead`, about 450 KB short of 20 MB. We can't tell
  from here whether CNN or the sandbox proxy cut the transfer. On Railway, the summary counts
  these as CNN failures. Sending `Accept-Encoding: gzip` would shrink each download to 3.7 MB,
  and CNN answers `If-None-Match` with a 304. Neither is in the diff.
- Freshness: the 14:55:37 post was in CNN's file at 14:57:13 (`last-modified`), about 2 minutes after posting.

## trumpstruth RSS: timestamps correct, one ID bug, and a caching problem
- `trumpstruth.org/feed` returns a 301 to `www.trumpstruth.org/feed`, which urllib follows.
  The feed has 100 items (about 4 days). Each item carries `truth:originalUrl` and `truth:originalId`.
- On today's feed, `parse_rss` gives the right ID for 100 of 100 items. `pubDate` is the
  post time truncated to the second, 0 to 1 s before the ID timestamp.
- Text: `description` is the post's HTML. After stripping tags, it matches CNN's `content`
  for all 100 overlapping posts. The only differences are that CNN turns curly quotes straight.
- **Bug:** the ID regex scans link, guid and description before `originalUrl`. When a post
  links another Trump post, the parser returns the linked post's ID. That happened in 62 of
  36,571 archive posts, 10 of them in 2026 (for example 117307289681145880 links
  117304284426928910; its trumpstruth page has that href). I reproduced the bug with that item's shape.
  The lag stays right because it comes from `pubDate`. But the post gets the wrong ID, and it's
  dropped if the linked post is still in the feed. **Fix:** put `originalUrl` first (in the diff, with a test).
- **Caching:** Cloudflare serves `/feed` from cache. The cached copy stays `cf-cache-status: HIT`,
  its `age` passed 6,150 s (over 100 minutes) and kept rising, and it was the same at the DUB,
  LHR and MXP POPs. The 14:55:37 post reached trumpstruth's origin between 15:11:40 and 15:12:42
  (about 17 minutes). The cached `/feed` still didn't have it at 15:17. So as written, the probe
  measures Cloudflare's cache on top of trumpstruth's own lag.
  **Fix:** also poll the feed with a unique `?t=` query (`cf-cache-status: DYNAMIC`, fresh). The
  diff adds this as a `trumpstruth_fresh` source, on by default, next to the cached one. It also
  logs `cf-cache-status`, `age` and `last-modified`, so the 24-hour logs show which lag is which.
  The probe README's source table would need a `trumpstruth_fresh` row.

## New-post path
No new post appeared during the 11 polls. To exercise the path, I replayed real bodies: a baseline
without the 14:55:37 post, then the live feed. Both sources emitted `new_post` for
117360567091654673 with the same ID and `lag_s` computed correctly.
