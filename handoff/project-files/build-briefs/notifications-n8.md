# Notifications N8: open bot (DMs, groups and others' channels)

You are building N8 of the notification layer in chrisrogers37/shitpost-alpha. From the public launch, anyone can DM the Telegram bot, or add it to their group or channel, and get the same posts as the channel:
- alerts;
- result replies and corrections;
- daily results;
- from N9, the scorecard and the weekly finding.

The bot answers only /start, /stop and /help, with fixed text. It never calls a model.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design. That includes the old bot in `notifications/telegram_bot.py`.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read "The open bot (DMs and groups)" first. Where this brief and the plan differ, this brief wins.

Questions go to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8) by send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If N1 or N7 isn't up yet, stop and say so.
- **N1:**
  - the delivery worker, with one loop per place, bookmarks and decide-once rules;
  - `app.deliveries` and its item keys;
  - the Telegram sender, with the token kept out of logs, numeric chat ids, and its 429, `retry_after` and `migrate_to_chat_id` handling;
  - `render(entry, place)`;
  - live and dry-run switches;
  - `notify_operator`;
  - `python -m engine telegram-chats`, which deletes an old webhook.
- **N7:** result replies, corrections and daily results through the same per-place path. A place without a template for an item kind skips that item without sending.
- **Engine PR 1:** the lease (only the holder runs workers), `register_worker`, the daily scheduler and `WEB_GRANTS`.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys or tokens in the sandbox.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No Telegram token here.
- **Nothing is sent from here.** No Telegram, X, email or SMS sends: tests use N1's fake Telegram, extended for updates. No crons and no Railway calls.
- **Public output.**
  - Percentage moves only.
  - No links in alert posts.
  - "Not investment advice." in every fixed reply and in the bot's description.
  - No referral or affiliate links.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.

## Scope
**1. `app.bot_chats`** (a new migration; add-then-remove only):
- **Columns.** The numeric chat id, the chat type, the status (`active`, `paused` or `gone`), the reason, and the joined and updated times. Never names, usernames or message text.
- **Grants.** The web role gets nothing on it.

**2. Messages in** (a worker under the lease):
- **Webhook check first.** Call `getWebhookInfo`, and `deleteWebhook` if one is set, because Telegram refuses polling while a webhook exists.
- **Polling.** Long-poll `getUpdates` with `allowed_updates` of `message` and `my_chat_member`, with a hard timeout.
- **Offset.** Keep it in the database, so a restart or a new lease holder never handles an update twice.
- **Dry run.** Outside live, poll nothing.

**3. Joining and leaving:**
- **DMs.** /start subscribes the chat; /stop deletes its row.
- **Groups.** Commands may come as `/start@<bot username>`.
  - Adding the bot subscribes the group, and removing it unsubscribes.
  - Only an admin's /stop counts (check with `getChatMember`). Anyone else's /stop gets no reply.
- **Others' channels.** Adding the bot as an admin allowed to post subscribes the channel. Losing that right pauses it, and removal marks it gone.
- **A chat moved to a supergroup** moves to its new id.
- **A chat that blocks the bot, disappears or refuses posts** is marked gone or paused, and skipped from then on.

**4. Fixed replies only.**
- /start, /stop and /help each get a fixed text:
  - what the bot does;
  - /stop;
  - the channel link (the setting `ENGINE_TELEGRAM_CHANNEL_URL`, for example https://t.me/shitpostalpha);
  - "Not investment advice."
- Everything else is ignored, with no reply.
- **Bot profile.** In live mode at startup, set the bot's command list and description to the same text, with `setMyCommands`, `setMyDescription` and `setMyShortDescription`. Skip calls whose value is already set.

**5. The bot-chats place** (mode `ENGINE_OUTLET_BOT_CHATS_MODE`):
- **Order.** The same items as the channel, through `render`. It goes after the channel and X: it waits until their loops have decided an entry, or are off.
- **Delivery rows.** One per chat per item, under N1's at-most-once rules. That way result replies and corrections land under the right message in every chat.
- **Pacing.**
  - Up to 25 messages a second in all, under Telegram's limit of about 30.
  - At most 20 a minute to any one group.
  - The start point rotates on each fan-out, so no chat is always last.
  - At that rate 1,000 chats take 40 seconds, and 5,000 take about 3 minutes.
- **A 429** pauses the whole fan-out for `retry_after`.

**6. The cap.**
- `ENGINE_BOT_CHATS_CAP` is the number of active chats, default 5,000.
- A notice goes out when active chats pass 80% of it.
- At the cap, /start answers with the channel link instead of subscribing, and adding the bot to a group or channel isn't accepted.

**7. Privacy.**
- /stop deletes the chat's row.
- A daily job deletes bot-chat delivery rows older than 30 days.
- The admin check stores nothing.

**8. Notices.** For the 80% mark, a poller that keeps failing, and a fan-out longer than 2 minutes, which is the trigger for paid broadcasts in Later.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests on a throwaway database, with a fake Telegram that serves updates and 5,000 chats:
- **Pacing** stays under 25 a second overall and 20 a minute per group. The rotation works.
- **Order.** The channel always gets an entry before any bot chat.
- **Join and leave:** /start and /stop in a DM; a group join and removal; a non-admin's /stop is ignored; a channel join as a posting admin, then pause and removal.
- **Chat changes:** a migration to a supergroup; a block marks the chat gone.
- **Ignored input.** Anything else typed gets no reply, and no model is called.
- **One poller.** Across two engine copies, only one polls, and the offset survives a restart.
- **Webhook.** A webhook that is set is deleted before polling.
- **The cap:** the notice at 80%, and the channel link at the cap.
- **Delivery rows.** A result reply lands under the right message in each chat. Rows older than 30 days are deleted.
- **No names.** No chat names or text are stored anywhere.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from N7's branch while it is unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N8: open bot". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the fixed reply texts;
   - the variables Chris sets at the launch: `ENGINE_TELEGRAM_CHANNEL_URL` and `ENGINE_OUTLET_BOT_CHATS_MODE=live`.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
