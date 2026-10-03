# Notifications N7: results and corrections

You are building N7 of the notification layer in chrisrogers37/shitpost-alpha. Every call the channel sent gets its result as a reply underneath it when its named window closes. A result that is later regraded gets a correction reply. The day's graded calls go out in a daily results message. Calls are never edited.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design.

Plan (approved by Chris on 2 October): https://claude.ai/code/artifact/ae6bcfea-ae61-4417-b649-45ab7822b7b0. Read "How an alert goes out" (results as replies) and "The messages" first. Where this brief and the plan differ, this brief wins. Two changes since the plan:
- **Correction posts are new.** They come from the growth plan's correction policy.
- **Daily results leave out the running hit rate for now.** N9 adds that line from the engine's record query, once engine PR 9 exists.

Questions go by send_message:
- notification design: to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8);
- grading and result revisions: to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ).

If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What exists
Read these first; find them with the GitHub tools. If N1 or engine PR 7 isn't up yet, stop and say so.
- **N1** ("Notifications N1: delivery core and the channel"):
  - the delivery worker with one loop per place, bookmarks and decide-once rules;
  - `app.deliveries` with its item keys, statuses and stored message ids, and `app.public_posts`;
  - the Telegram sender, which already supports `reply_parameters` with `allow_sending_without_reply`;
  - `render(entry, place)` with golden tests;
  - live and dry-run switches, `notify_operator` and pacing.

  Until now N1 passes result revisions without a send.
- **Engine PR 6:** `AlertV1`, alert revisions, and the evidence block. The block's headline names the call's window (for example 1 hour, the close or 1 trading day).
- **Engine PR 7:** grading. Every call, sent or FYI, gets a result revision for each of its windows, 16 minutes after the window closes, from final bars. Each one carries:
  - the % move;
  - the move against the benchmark;
  - the move at random times;
  - hit or miss;
  - the time it matured.

  A later revision for the same call and window replaces an earlier one. That happens only after a grading fix, and the engine may record a reason.
- **Engine PR 1's scheduler:** daily jobs at a New York time, logged in `engine.job_runs`. A missed run is caught up once, and a failed run sends an operator notice.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally use DEV_DATABASE_URL, with throwaway test databases.
- **No keys or tokens in the sandbox.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. No Telegram token here.
- **Nothing is sent from here.** No Telegram, X, email or SMS sends: tests use N1's fake Telegram. No crons and no Railway calls.
- **Public output.**
  - Percentage moves only, never a raw or entry price.
  - "Not investment advice." ends the daily results message.
  - No links in replies, and no referral or affiliate links.
- **Scope.**
  - Design from first principles, and build nothing before something uses it.
  - Test-only code stays thin and is marked test-only.
  - Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, superuser `shitpost`, URL in DEV_DATABASE_URL. Tests use throwaway databases.
- **Outputs for review** go in `/mnt/project-files/notifications/n7/`.

## Scope
**1. Result replies.**
- **Which result.** For each result revision of the call's named window (the evidence headline's window), each place that sent that alert live posts one reply under the stored message id, with `allow_sending_without_reply`. If someone deleted the call, the result still arrives as a plain message.
- **Notified.** The reply always notifies, even in quiet hours.
- **Other windows** reach the site and the API only.
- **No reply when the call wasn't sent:** an alert row that is `unknown`, `failed` or skipped gets no reply. A `dry_run` alert gets a `dry_run` reply row.
- **No late rule.** Results are part of the record. After an outage they go out when the place catches up, paced.
- **Delivery.** Each reply is its own item in `app.deliveries`, with the same at-most-once handling as N1. The channel's reply also gets a `public_url` and appears in `app.public_posts` as kind `result`.
- **Template:**
  ```
  SPY, 1 hour after the 2:02 pm call: -0.3% vs 0.0% at random times. Called down: hit.
  ```
  Use the benchmark wording for a company's stock, for example "+1.2% vs SPY".

**2. Correction replies.**
- **When.** A result revision for a call and window replaces a result that a place already posted, and the public numbers or the grade differ. That place posts a correction reply under the original alert.
- **Silence otherwise.** An identical revision posts nothing. A call whose result was never posted gets no correction.
- **Template,** with the engine's reason appended when it records one:
  ```
  Correction to the 1-hour result of the 2:02 pm SPY call: -0.2% vs 0.0% at random times, a hit. First posted as +0.1%, a miss.
  ```
- **Notified,** like result replies.
- **Daily results** for that day list each correction.

**3. Daily results** (a daily job at 17:00 New York, under the lease):
- **What it lists:**
  - each call that was sent live and whose named window was graded since the last daily results message, with hit or miss and its move;
  - each call the channel didn't send that day, and why (late, `unknown` or failed);
  - each correction.
- **Every graded sent call appears in exactly one daily results message.** The first message after N7 goes live lists every call graded since go-live.
- **Skipped** when there is nothing to list.
- **Ends** with "Not investment advice."
- **Long messages** over 3,500 characters split into numbered parts.
- **No running hit rate.** N9 adds it from the engine's record query.
- **Where it goes:** the setting `ENGINE_DAILY_RESULTS_TO`.
  - `operator` (the default) sends only to Chris's chat, as a preview. It needs his chat id and live, and works whatever `outlet_operator_mode` says.
  - `places` sends to every place in live or dry-run mode, through `render`. Places added later (X in N5, bot chats in N8) bring their own template.
- **Each run** is one item per place in `app.deliveries`, so a rerun of the same slot never posts twice.

**4. One path for later places.**
- Result replies, corrections and daily results all go through `render(entry, place)` and the per-place loops.
- N5 and N8 add only their templates and pacing. A place without a template for an item kind skips that item without sending, rather than failing.

**5. Notices.**
- A daily results run that fails, or is caught up late, already notifies through the scheduler. Check that it does, and that the message names the job.
- A reply that ends `unknown` or `failed` notifies through N1's kinds.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests on a throwaway database with N1's fake Telegram:
- **Golden renders** from fixture grades: a hit, a miss, a company against SPY, a correction with and without a reason, and a daily results message long enough to split.
- **Reply targets.** A result reply lands under the right message, in each place that sent the call.
- **No reply** after `unknown`, `failed` or skipped. A dry-run place writes dry-run rows.
- **Quiet hours** don't silence replies.
- **Corrections.** One is posted only when a posted result changes; nothing for identical numbers or an unposted result.
- **Other windows** post nothing.
- **Daily results:**
  - on a fake clock, a missed 17:00 run is caught up once, with a notice;
  - nothing to list means no message;
  - a skipped call appears with its reason;
  - each graded call appears in exactly one message, across a restart;
  - `operator` against `places`;
  - a rerun of the same slot never posts twice.
- **Crash safety.** A crash mid-reply leaves `unknown`, never a second reply.

**Samples.** Write every golden render to `/mnt/project-files/notifications/n7/samples.md`.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from whichever of N1's and engine PR 7's branches is still unmerged, merging the other in if both are. Use main once both have merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Notifications N7: results and corrections". Say near the top which PRs it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the samples;
   - `ENGINE_DAILY_RESULTS_TO` and its default.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
