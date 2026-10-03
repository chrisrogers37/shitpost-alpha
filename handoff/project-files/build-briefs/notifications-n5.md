# Notifications N5: X

You are building N5 of the notification layer in chrisrogers37/shitpost-alpha: X as a landing place. From the public launch, X gets the same posts as the Telegram channel, as plain posts and replies:
- alerts;
- result replies and corrections;
- daily results;
- from N9, the scorecard and the weekly finding.

X posts carry no links, except the scorecard's sponsor link (N9). Spending is held under a hard monthly cap.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read "Landing places", "The messages" and "Outside costs" first. Where this brief and the plan differ, this brief wins.

Questions go to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8) by send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If N1 or N7 isn't up yet, stop and say so.
- **N1:**
  - the delivery worker, with one loop per place, bookmarks and decide-once rules;
  - `app.deliveries` and its item keys, and `app.public_posts` (the channel and X only);
  - `render(entry, place)` with golden tests;
  - live and dry-run switches, `notify_operator` and pacing;
  - the key-scrubbing helpers in `engine/engine/http_client.py`.
- **N7:** result replies, corrections and daily results through the per-place path. A place without a template for an item kind skips that item without sending.
- **N8,** if it has merged: the bot-chats place, which waits for the channel and X.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys in the sandbox.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No X keys here, and none may be added.
- **Nothing is sent from here.** No X, Telegram, email or SMS sends. api.x.com isn't reachable from the sandbox and must not be added. Tests use a fake X built from recorded request and response shapes, in fixtures named `*.unverified.json` until a live post confirms them. No crons and no Railway calls.
- **Public output.**
  - Percentage moves only.
  - No links in any X post except the scorecard's sponsor link.
  - "Not investment advice." on every alert and on the daily results.
  - No referral or affiliate links.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **Outputs for review** go in `/mnt/project-files/notifications/n5/`.

## Scope
**1. Settings** (secrets never print):
- `x_api_key`, `x_api_secret`, `x_access_token` and `x_access_token_secret` (OAuth 1.0a user context for @shitpostalpha);
- `outlet_x_mode` (`off`, `dry_run` or `live`; live also needs the live environment, as in N1);
- `x_monthly_budget_usd` (default 10);
- `x_price_per_post_usd` (default 0.015);
- `x_price_per_link_post_usd` (default 0.20).

No X client is built while the keys are unset.

**2. The poster** (plain httpx; one small OAuth 1.0a HMAC-SHA1 signer, or a well-known library that signs httpx requests):
- **Posts and replies.** `POST https://api.x.com/2/tweets` with `text`. Replies add `reply.in_reply_to_tweet_id`, taken from the alert's X delivery row.
- **Signer test.** Check the signer against the worked example in X's documentation, copied into a fixture.
- **Timeouts.** Every call has a hard timeout.
- **Keys and signatures** never appear in logs, rows, errors or the PR. Scrub the `Authorization` header from error text.
- **At most once.** N1's rules apply: retry only 429s (honour the reset header) and connection errors raised before sending. A duplicate-content refusal is `failed`, with a notice.
- **Public link.** A sent post's `public_url` is `https://x.com/i/status/<id>`, so it appears in `app.public_posts`.

**3. Templates** (through `render`):
- **Weighted length.** Every post fits X's weighted 280-character limit, using the twitter-text v3 weights. Write the weighting with tests: ASCII, accents, CJK and emoji.
- **The call's time.** Every post carries it, because X refuses repeated text.
- **Alert:**
  ```
  SPY down after Trump's 2:02 pm post on tariffs. Like 14 past posts: SPY fell within 1 hour after 64% of them (median -0.4% vs 0.0% at random times). Not investment advice.
  ```
  No excerpt: post text can contain things X turns into links.
- **Few similar posts:** "only N similar posts", with no hit rate.
- **Result reply and correction:** as in N7, under the X alert.
- **Daily results.** One post: the day's graded calls, compactly, then "and N more" if they don't fit, then "Not investment advice."
- **No links.** A test fails any X post, other than the scorecard, that contains a URL or anything X would turn into a link (a bare domain such as `example.com`, a cashtag is fine).

**4. Cost cap.**
- **This month's spend** is the count of this calendar month's (UTC) sent X rows, times their price: linked posts at the link price.
- **Before each post,** if it would pass `x_monthly_budget_usd`, the row is `capped`. X pauses until the next month, and one notice says so. Prepaid credits with auto top-up off are the backstop outside the code.
- **The kill switch** is `outlet_x_mode=off`.

**5. Order.** X goes after the channel: its loop waits until the channel has decided an entry, or is off.

**6. Dry-run week.**
- X rows store the rendered text.
- `python -m engine x-preview [--days 7]` prints the X rows (dry run and sent) of the last days, so Chris can read a week of would-be posts before going live.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests with the fake X on a throwaway database:
- **Requests.** Their shapes match the recorded ones, and a reply carries the right in-reply-to id.
- **Weighted length.** Every golden template fits 280, including worst cases (the longest symbol, topic and numbers).
- **Links.** No alert, result, correction or daily results post contains a link or a linkable domain.
- **Cap.** A simulated month at 5 alerts a day, with replies and daily results, stays under $10 at the default prices. At the cap, the row is `capped`, with one notice and no post.
- **Failures.** A 429 retries within `send_until`. A duplicate refusal is `failed`, with a notice. A crash mid-post leaves `unknown`, never a second post.
- **No keys.** With the keys unset, no client is built. Keys and signatures never appear in logs.
- **Order.** X waits for the channel.
- **x-preview** prints dry-run rows.

**Samples.** Write every golden render to `/mnt/project-files/notifications/n5/samples.md`, with each one's weighted length.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from N8's branch while it is unmerged, or from N7's if N8 hasn't been opened. Use main once those have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N5: X". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the samples;
   - the cost model;
   - the variables Chris sets.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
