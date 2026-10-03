# Notifications N1: delivery core and the channel

You are building N1, the first PR of the notification layer in chrisrogers37/shitpost-alpha. The signal engine (a new `engine/` package: one always-on asyncio process) scores Trump's posts and saves alerts. N1 gives it one transport with several landing places:
- it follows the engine's numbered alert entries;
- it decides once, per landing place, whether to send each alert;
- it renders the alert for that place and sends it to Telegram at most once.

N1 also brings the operator notices and the one-time invite to the old system's subscribers.

The rest of the repo is the old system, shut down in production since 1 October. Don't import it, edit it or copy its design, including the old `notifications/` package.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read its sections "How an alert goes out", "Landing places", "The messages" and "Hookup to the engine and the site" first. Where this brief and the plan differ, this brief wins.

Questions go by send_message:
- notification design: to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8);
- the engine's alert format, wake hook or lease: to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ).

If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Engine PRs 1 to 6 are draft or merged PRs titled "Engine PR n: ...". Find them with the GitHub tools and read them before writing anything:
- **PR 1:**
  - `Settings` (ENGINE_ prefix);
  - Alembic with the `engine`, `prices` and `app` schemas, and `WEB_GRANTS` in `engine/engine/migrate.py`;
  - the lease;
  - the daily scheduler and `engine.job_runs`;
  - `Registry.register_worker` (workers run only in the copy holding the lease, and restart with backoff);
  - `notify_operator(kind, text)` in `engine/engine/notify.py`, which only logs today;
  - `make_client` and `scrub` in `engine/engine/http_client.py`.
- **PRs 2 to 4:** sources and signals, instruments and prices, extraction and similarity.
- **PR 5:** the frozen backtest report, which says which instrument and window pairs passed Gate 0.
- **PR 6:**
  - `engine.alerts` with the `AlertV1` model and its public-format test;
  - the insert-only `engine.alert_revisions` with `seq` in commit order;
  - `engine_meta.stream_id`;
  - the in-process wake hook after each alert commits;
  - the setting that pauses all sends;
  - the alert fields N1 reads: disposition `sent` or `fyi` with `fyi_reason`, `send_until` (post time plus 15 minutes), `excerpt` (200 characters or less, links removed), `market_open`, a short `public_id`, and the similar-posts evidence block.

Use PR 6's names for all of these; the plan's names are only what was agreed beforehand. If PR 6 isn't up yet, stop and say so.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The engine reads ENGINE_DATABASE_URL; locally use DEV_DATABASE_URL.
- **No keys or tokens in the sandbox.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist. There is no Telegram bot token here, and none may be added.
- **Nothing is sent from here.** No Telegram, X, email or SMS sends. api.telegram.org isn't reachable from the sandbox and must not be added. Tests use a fake Telegram (an httpx mock transport or a local fake server).
- **No crons and no Railway calls** (connector or CLI). Nothing deploys from this PR.
- **Public output.**
  - Percentage moves only, never a raw or entry price.
  - No links in alert posts.
  - "Not investment advice." ends every public template.
  - No referral or affiliate links.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests create and drop their own throwaway databases; leave shitpost_dev alone.
- **Outputs for review** go in `/mnt/project-files/notifications/n1/` (create it).

## Scope
**1. Settings** (ENGINE_ prefix; tokens and ids are secrets that never print):
- `telegram_bot_token`;
- `telegram_operator_chat_id`;
- `telegram_test_channel_id`;
- `telegram_channel_id`;
- `outlet_<place>_mode` for each place below (`off`, `dry_run` or `live`; default `off`);
- `outlet_notices_mode` (default `dry_run`);
- `live_environment` (default `production`).

**Live means two things.** A place is live only when its mode is `live` and `RAILWAY_ENVIRONMENT_NAME` (set by Railway) equals `live_environment`. Anywhere else it behaves as `dry_run`: it logs what it would send and writes a `dry_run` row.

**2. Tables** (one new migration in the engine's history; add-then-remove only):
- **`app.outlet_cursors`:**
  - one row per place, holding the bookmark (`last_seq`) and its `stream_id`;
  - `checked_at`, the delivery loop's last pass, which engine PR 7's outside check reads.
- **`app.deliveries`:**
  - one row per place, chat and item, unique on those three. An item is an alert revision, or one run of a scheduled post: N1 defines the item key; N7 and N9 use it.
  - Each row holds the alert's id and public id, the revision seq, the decision and status, the external message id, and the message it replies to.
  - It also holds a `public_url` set only for the channel and X, the attempts, the error, and the created and sent times.
- **`app.operator_notices`:** an outbox and throttle for `notify_operator`.
- **`app.public_posts`:** a view of live `sent` rows for the real channel and X only, with public id, revision seq, kind (alert or result), place, `public_url` and sent time. Your chat, the test channel, bot chats, dry runs, skips, `unknown` rows and chat ids never appear in it. D1 turns search listing on at its first row.
- **Grants.** Add `"app.public_posts": "SELECT"` to `WEB_GRANTS`. The web role gets nothing else in `app`.

**3. Landing places in N1:**
- `operator`: Chris's chat, for alerts during the shadow week only;
- `test_channel`;
- `channel`.

X (N5) and bot chats (N8) plug in later the same way, so a place is a bookmark, a target, a template and pacing limits.

**4. The delivery worker**, registered with `register_worker`.

**Waking.** It wakes on PR 6's wake hook, or every 30 seconds to cover a missed wake.

**Each place has its own loop,** so one slow place never holds up another. Each pass:
- **Stream check.** Compare the bookmark's stream_id with `engine_meta`'s. If it differs, jump to the head without sending anything, and send one notice. A place with no bookmark starts at the head too, so a new place never replays old alerts.
- **Read entries** after the bookmark in seq order. A first revision is a new alert. Anything else, such as a result, passes without a send until N7 adds result replies; no call is ever edited.
- **Decide once, at first sight:**
  - `fyi` gets no row;
  - a `sent` alert first seen after `send_until` is skipped as late, with one notice per alert;
  - otherwise the place sends it, or writes `dry_run`.
- **Pause.** While PR 6's pause setting is on, places don't advance. When it's off again, anything past `send_until` is late.
- **Bookmark.** Advance it after each entry is decided.

**At most once.**
- Commit the row as `sending` before the HTTP call, and set `sent` with the message id after it.
- Retry only clear failures before `send_until`: HTTP 429 (honour `retry_after`) and connection errors raised before the request was sent. Hold such a row in a `retry` state with its next attempt time, which a restart may safely resume.
- 400 and 403 responses are `failed`, with a notice.
- A timeout after sending, a 5xx or a dropped connection is `unknown` and never retried.
- When the worker starts, any row still `sending` becomes `unknown`, with a notice. A row left `sending` or `unknown` for 5 minutes also raises a notice.

**Pacing.** At most 1 message a second to Chris's chat, and about 20 a minute to each channel.

**Draining.**
- On SIGTERM, the worker claims nothing new and finishes the sends under way, for up to 10 seconds, before the engine cancels it.
- Add `"drainingSeconds": 15` to the deploy block of `engine/railway.json`. If Railway's config schema refuses it, leave it out and say so in the PR, so Chris sets `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=15` instead.

**5. Telegram sender** (plain httpx on the Bot API, no bot framework):
- **Sending.** `sendMessage` with `parse_mode` HTML and one escaping function for all inserted text. Turn link previews off. Use `disable_notification` for quiet hours. `reply_parameters` with `allow_sending_without_reply` is ready for N7.
- **Chat ids** are numeric. Read each response's `migrate_to_chat_id`, 429 `retry_after` and error descriptions.
- **Timeouts.** Every call has a hard timeout.
- **The token is in the URL path.**
  - Keep it out of every log line, exception text and row. Quiet the request loggers, add a redaction filter, and scrub error text.
  - A test captures all logs at DEBUG through a run with failures, and asserts the token never appears.
- **Message cap.** Every message is capped at 3,500 characters.

**6. Renderer.** One `render(entry, place)` returns the messages for that place, with golden tests for every template:
- a stock alert with the market open;
- a stock alert with the market closed;
- few similar posts (the evidence's low-sample flag): the alert says "only N similar posts" and leaves out the hit rate;
- hostile text (`<`, `&`, quotes, emoji, right-to-left marks).

**Coin templates.** Add them only if PR 5's report shows a passing BTC pair; say which way it went in the PR.

**The channel's alert,** with numbers from the evidence block:
```
SPY down · tariffs
"…excerpt…" (Trump, 2:02 pm ET)
Like 14 past posts: SPY fell within 1 hour after 64% of them (median -0.4% vs 0.0% at random times). This method's hit rate: 58%.
Closest: 12 Mar 2025 -0.9% · 2 Apr 2025 -1.6% · 9 Jul 2025 +0.2%
Market open
Not investment advice.
```

**Quiet hours.** Between 22:00 and 07:00 New York, an alert whose markets are all closed goes out silently.

**7. Operator notices.**
- **Signature.** `notify_operator(kind, text)` keeps its signature. It always logs, never raises, and never blocks its caller for long.
- **The outbox.** When the engine's database is configured, it writes the notice to the outbox. The delivery worker sends it to Chris's chat when `outlet_notices_mode` is live.
- **Throttle.** At most one message an hour per kind. Count the suppressed ones and mention them in the next message.
- **Sources.** The engine's own kinds already call it. Add these:
  - a call skipped as late;
  - a send left `sending` or `unknown`;
  - a stream change;
  - a failed send.
- **Never mixed with alerts.** After go-live Chris's chat gets notices only, so he never sees a call before the channel does.

**8. Commands.**
- **`python -m engine telegram-chats`:**
  - It reads `getWebhookInfo`. If a webhook is set (the old bot had one), it prints its host and calls `deleteWebhook`.
  - Then it calls `getUpdates` once and prints each recent chat's id, type and title or username, so Chris can read his chat id and the channel ids.
  - It refuses to run unless live, meaning `RAILWAY_ENVIRONMENT_NAME` equals `live_environment`.
- **`python -m engine invite-old-subscribers`:**
  - It reads the old subscribers from a CSV file or from `ENGINE_OLD_SUBSCRIBERS` (columns or fields: chat_id, is_active, created_at).
  - It keeps the ones active and subscribed before 2026-08-21.
  - It sends each the text given with `--invite-link` once, at 1 a second.
  - It logs every send and refusal.
  - It runs as a dry run unless `--send` is given, and `--send` also requires live.
  - It records its sends in `app.deliveries`, so a second run skips anyone already sent.

**9. Wire-up.** Register the worker in `build_registry()`. Put the new code in the engine package under a name of its own (for example `engine/engine/outlets/`), never `notifications`.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes.

**Replay.** Tests replay recorded alerts through the fake Telegram on a throwaway database:
- a crash mid-send (kill -9) leaves `unknown`, never a second message;
- with two engine copies, only the lease holder sends;
- ten alerts in two minutes, with a 429 in the middle, all go out within `send_until` and in order;
- hostile text renders correctly;
- a late alert is skipped, with a notice;
- a stream change jumps to the head and sends nothing old;
- a new place starts at the head;
- pausing holds the places, and unpausing marks anything past `send_until` late;
- the token is absent from every log line.

**Other tests:**
- dry run outside the live environment, even with mode `live`;
- the notice throttle;
- `app.public_posts` stays empty after dry runs and after sends to Chris's chat or the test channel;
- the web role can read `app.public_posts` and gets "permission denied" on `app.deliveries`;
- the invite command's filter, dry run and second-run skip.

**Samples for Chris.** Write every golden render to `/mnt/project-files/notifications/n1/samples.md`, as Telegram would show them. Chris approves those before the shadow week.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from engine PR 6's branch while that PR is unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N1: delivery core and the channel". Say near the top which engine PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the coin-template decision;
   - whether railway.json took `drainingSeconds`;
   - the Railway variables Chris sets: `ENGINE_TELEGRAM_BOT_TOKEN`, `ENGINE_TELEGRAM_OPERATOR_CHAT_ID`, `ENGINE_TELEGRAM_TEST_CHANNEL_ID`, `ENGINE_TELEGRAM_CHANNEL_ID`, and the mode variables, each with when it's set.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link, the samples file and anything unfinished.
