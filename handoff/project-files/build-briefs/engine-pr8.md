# Engine PR 8: go-live and the daily hash

You are building PR 8 of the new signal engine in chrisrogers37/shitpost-alpha.

What exists:
- **PRs 1–7:** the engine through the shadow week: alerts, grading, the outside check and `engine/SETUP.md`.
- **The notification plan's N1:** delivery workers and the Telegram outlet.
- **The dashboard's D1:** the minimum site, served on shitpostalpha.com behind its holding page (`WEB_HOLDING_PAGE`) since the shadow week.

Read them first and build on them.

**PR 8 is the go-live.** After a clean shadow week:
- the invite-only Telegram channel becomes the destination for sent alerts;
- the site opens on shitpostalpha.com, with the holding page switched off;
- the daily hash starts.

The engine's own code in this PR is the daily hash and the go-live switch; the channel and the old subscribers' invite script are the notification plan's. The rest of the repo is the old system: don't import it, edit it or copy its design.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What Gate 0 decides
Nothing here. In research mode every alert is FYI, and the channel then gets nothing but results and notices, which the notification plan decides.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop. Chris merges at a quiet hour, after a clean shadow week. Ignore the repo CLAUDE.md's admin-merge pre-approval.
- **Production stays out of the sandbox.**
  - Never touch a production database; never read or set DATABASE_URL.
  - No production credential enters this session: not the hash repo's token or the bot token.
  - The subscriber export goes only to Railway, never to a sandbox.
- **Other services.**
  - No Railway calls.
  - No Telegram, email or SMS from the sandbox.
  - Never write to the real hash repo from the sandbox: tests use a stub GitHub server.
  - No crons: the daily job runs in the engine's scheduler.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY.
- **Scope.** Build nothing before something uses it. Don't touch the old api/, frontend/, root railway.json or railpack.json.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. Tests use throwaway databases.

## Scope
**1. The daily hash.**
- **What it hashes.** Each day's new first revisions: revision 1 of every alert, sent or FYI, by its New York date. Each one is hashed in a canonical JSON form (sorted keys, fixed number formatting, UTF-8).
- **The file per day** is `YYYY/MM/DD.json` and lists each revision's `seq`, public id and SHA-256. It also has the day hash, which is the SHA-256 of the previous day's hash followed by that day's revision hashes in `seq` order, so the days form a chain.
- **Where it goes.** The engine commits the file to the public repo in `ENGINE_HASH_REPO`, through GitHub's contents API with `ENGINE_HASH_TOKEN`.
- **When.** It runs as a daily scheduler job, after the New York day ends. It catches up missed days in order, and never rewrites a committed day.
- **Checking it.** `engine/scripts/verify_record.py` fetches the first revisions from our public API (`/api/v1`, whose endpoint the notification and dashboard plans own; agree the path with the engine planner) and recomputes every day hash. The public repo's README explains how anyone can run it.
- **What's published.** First revisions never hold grades, so publishing their hashes reveals nothing early.

**2. The go-live switch.**
- **Section in `engine/SETUP.md`** called "Go-live", with exact values:
  - set `WEB_HOLDING_PAGE=off` on the web service; the domain and `ENGINE_WEB_HEALTH_URL` were already set in the shadow week;
  - set `ENGINE_HASH_REPO` and `ENGINE_HASH_TOKEN`;
  - N1's variable that switches the landing place from the admin chat to the channel (get its name from the N1 code);
  - the steps for the old subscribers' invite script, as the notification plan defines them. It runs once on Railway, with the export on Railway only.
- **Go-live check.** Add a go-live check to `python -m engine status`:
  - the hash job's last day;
  - the health URL;
  - the landing place;
  - whether sends are paused.

## How to check your work
From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes. Tests show:
- **Canonical JSON** gives the same hash across runs and key orders.
- **The chain** links each day to the one before.
- **Catch-up** commits missed days in order, and a committed day is never rewritten.
- **The stub GitHub server** receives the expected file and commit.
- **`verify_record.py`** passes on a fixture record and fails on one changed character.
- **The status check** shows the go-live fields.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from PR 7's branch while it's unmerged, or from main once it has merged. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 8: go-live and the daily hash", saying near the top that it goes in after PR 7 and a clean shadow week, at a quiet hour. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the Go-live section of SETUP.md.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Send the engine planner** the Go-live section when it's final, so Chris gets it as one ask.
5. **Stop.** No merge and no further PRs.
