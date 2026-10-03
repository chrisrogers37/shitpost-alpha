# Engine PR 2: sources and signals

You are building PR 2 of the new signal engine in chrisrogers37/shitpost-alpha. PR 1 (draft PR #258, branch `claude/engine-foundation-k6mh6s`) built the foundation in `engine/`: the package, Alembic with the `engine`, `prices` and `app` schemas, the lease, the scheduler, `StageRunner` with `stage_columns()`, the worker registry (`build_registry()` in engine/registry.py) and `notify_operator`. Read it first and build on it.

PR 2 gets Trump's posts into the database: four feeds polled side by side, first copy wins, plus the full history. Nothing is scored, priced or sent yet. The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. The repo's CLAUDE.md pre-approves admin merges: ignore that.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use the sandbox Postgres in DEV_DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist.
- **Never call Truth Social's API (truthsocial.com) or ScrapeCreators from the sandbox.** Their adapters are built and tested from fixtures only; they run for real only on Railway, from PR 7.
- **CNN and trumpstruth may be read from the sandbox, gently.**
  - Use the intervals below.
  - Keep the live run short.
  - Download CNN's full file only when the import or a catch-up needs it.
- **No outside messages or schedules.** No Telegram, email or SMS. No crons: scheduling lives in the one process. No Railway calls.
- **Build only what's used.** Design from first principles and build nothing before something uses it. Test-only code stays thin and is marked test-only.
- **Old folders stay as they are.** Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** Python 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases; leave shitpost_dev alone except for the live run and the import.
- **Network.**
  - github.com works over git.
  - raw.githubusercontent.com is blocked, so clone repos instead of fetching raw files.
  - ix.cnn.io and www.trumpstruth.org answer.

## The four feeds
All four:
- send an honest User-Agent: `shitpost-alpha-engine/<version> (+https://github.com/chrisrogers37/shitpost-alpha)`;
- never use proxies, rotating addresses, browser impersonation or logins;
- run as workers registered in `build_registry()`, so only the lease holder polls;
- use intervals that are settings, so tests can shrink them.

**Trump's account id is 107780257626128497.** A post's time comes from its status id: `id >> 16` is milliseconds since the Unix epoch. This matched CNN's `created_at` within 1 s on all 36,571 posts checked; use it, not each feed's own timestamp.

1. **`direct`, Truth Social's own API, every 60 s.**
   - URL: `GET https://truthsocial.com/api/v1/accounts/107780257626128497/statuses?exclude_replies=true&limit=20`. It returns Mastodon status JSON (Truth Social runs a Mastodon fork) and pages back with `max_id`.
   - **Blocked** means a 403, a 429, a challenge page (HTML or a `cf-mitigated` header instead of JSON), or five failures in a row.
   - **While blocked:** back off from 1 minute, doubling up to 30. Send one `notify_operator` message per incident, and another when it recovers. The other feeds carry on.
   - A 24-hour Railway test saw no blocks, about 50 ms answers and no rate-limit headers.
2. **`trumpstruth`, every 60 s.**
   - URL: `GET https://www.trumpstruth.org/feed?t=<unix seconds>`. The `?t=` query is required: Cloudflare caches the plain `/feed` for up to 2 hours.
   - The feed is RSS with about 100 items (about 4 days).
   - Take the id from `truth:originalId`, or else `truth:originalUrl`, before anything else. The description can link other Trump posts: item 117307289681145880 links 117304284426928910, and a parser that scans the description first gets the wrong id.
   - `description` is HTML; strip it to plain text.
3. **`cnn`, every 15 s.**
   - URL: `GET https://ix.cnn.io/data/truth-social/truth_archive.json`. It is a JSON list, newest first: about 20 MB, or 3.7 MB with gzip.
   - Each poll reads only the first 32 KB (`Range: bytes=0-32767`, which answers 206) and parses the complete objects in it, about 58 posts.
   - Fields: `id`, `created_at`, `content` (plain text, empty on media-only posts), `url` and `media`.
   - Full downloads sometimes end early (IncompleteRead); retry them.
4. **`scrapecreators`, fallback only, as Chris chose.**
   - URL: `GET https://api.scrapecreators.com/v1/truthsocial/user/posts?user_id=107780257626128497&limit=20` with an `x-api-key` header. Page back with `next_max_id`.
   - The response is `{"success": true, "posts": [<Mastodon statuses>]}`. The old harvester shows the request (shitposts/truth_social_s3_harvester.py); read it, don't import it.
   - **Schedule:** every 2 minutes only while `direct` is blocked or switched off. Otherwise one check call an hour, so a broken key shows up before it's needed.
   - **Key:** `ENGINE_SCRAPECREATORS_KEY`. If it isn't set, this feed is off.

**Off switch.** `ENGINE_SOURCES_OFF` is a comma list of feed names to skip; the others carry on.

**Catch-up.** When a read doesn't reach back to the newest post already stored, the feed fetches more until it does, without duplicates:
- CNN reads its whole file;
- the others page back.

**All dark.** If no feed has answered for 10 minutes, send one operator message, and show "dark since <time>" in the status. Clear it when a feed answers.

## Data model (new migration; add-then-remove only)
**`engine.sources`: who we follow, not the feeds.**
- One row for Trump: platform `truth_social`, account id, handle `realDonaldTrump`, display name, avatar URL and profile link.
- Seed it in the migration.

**`engine.signals`: one row per post.**
- Key `truth_social:<status id>`.
- Columns:
  - the source it belongs to;
  - kind: `post`, `reply`, `quote` or `repost`;
  - the key of the post it points to, if any;
  - a link to the original;
  - plain text;
  - post time from the id;
  - a media flag;
  - the first copy's raw payload and the feed it came from;
  - `first_seen_at` and `first_seen_via`;
  - `stage_columns()`.
- Indexes:
  - source plus post time;
  - full-text search on the text (GIN).
- **Writing rules:**
  - Written once, from the first copy; a later copy only adds a sighting.
  - On mirrors, a repost is text starting `RT @`, and a quote carries `RE: <truthsocial url>`.
- **Stages:**
  - New text posts wait at stage `score`, which PR 4 handles. Nothing in PR 2 runs a stage over them.
  - Reposts and media-only posts are saved straight to `done`, marked as not scored.
  - Imported history also goes straight to `done`, marked imported. PRs 4 and 5 process history in batch, never through the live stages.

**`engine.signal_sightings`.**
- The time each feed first showed each post, unique per signal and feed.
- `signals.first_seen_*` copies the earliest. Use one clock for all of these: the database's or the engine's.

**`engine.source_stats`.**
- Hourly counters per feed: polls, not-modified, errors, blocks, posts seen, posts seen first.
- No row per poll.

**Status.** `python -m engine status` adds, per feed, its last successful read and whether it is up, blocked or off, plus counts of signals per stage.

**Grants.** The web role reads the `engine` schema through PR 1's grants. Add nothing to `app` or `prices`.

## History import
`python -m engine import-history`:
1. **CC0 copy.** Read the CC0 copy of CNN's archive on GitHub (`git clone --depth 1 https://github.com/stiles/trump-truth-social-archive` into a temp directory). Check its LICENSE says CC0 and note it in the PR. It holds posts up to about October 2025 (about 29,500).
2. **Live file.** Read every later post from CNN's live file through the same mapping as the live feed, about 7,055 up to 30 September.
3. **Idempotent.** A second run changes nothing, and posts the live feeds already stored are left alone.
4. **Counts.** It prints how many posts came from each part, how many were skipped as duplicates, and the total. The totals must add up to the files' counts. Never commit the data files; tests use small slices.

## Burst measurement
A small function, with a test, over imported text posts (not reposts or media-only). It reports:
- the share of posts within 5, 15, 30 and 60 minutes of the previous one;
- the cluster sizes at a 30-minute gap.

Run it once on the imported history and put the numbers in the PR body. PR 5 checks the send rule's "one alert per instrument per 30 minutes" against them.

## Fixtures
- **CNN and trumpstruth.** Record real responses from the sandbox (a 32 KB CNN range and one trumpstruth feed) and trim them.
- **direct and ScrapeCreators.** Hand-build fixtures in the Mastodon status format:
  - a post, a reply, a quote, a repost, a media-only post and an HTML challenge page;
  - mark them unverified until PR 7 records real ones on Railway.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Mapping.** Each adapter maps its fixtures to the right key, kind, text, media flag and post time, and the trumpstruth item that links another post gets its own id.
- **First copy wins.** Two feeds see one post: one signal, two sightings, and `first_seen_via` is the earlier feed.
- **Blocks.**
  - Each block signal marks `direct` blocked.
  - The back-off grows from 1 to 30 minutes.
  - Exactly one operator message per incident, and one on recovery.
  - The other feeds keep going.
- **ScrapeCreators.** Hourly while `direct` is healthy; every 2 minutes while it is blocked or listed in `ENGINE_SOURCES_OFF`; off without a key.
- **Catch-up.** Catch-up fills a gap with no duplicates.
- **All dark.** Sends one message after 10 minutes and clears when a feed returns.
- **Lease.** A copy without the lease polls nothing.
- **Import.** Running it twice gives the same counts. A repost and a media-only post are saved as not scored.

Also, by hand:
- **Live run.** Run the mirrors only (`ENGINE_SOURCES_OFF=direct,scrapecreators`) into shitpost_dev for about 15 minutes. Report the polls, sightings and any new posts.
- **Full import.** Run the full import into shitpost_dev and report its counts.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 1's branch `claude/engine-foundation-k6mh6s` while #258 is unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 2: sources and signals", saying near the top that it goes in after #258. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the import counts, the live-run results and the burst numbers.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
