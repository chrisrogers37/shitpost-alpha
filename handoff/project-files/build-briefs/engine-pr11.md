# Engine PR 11: remove the old code

You are building PR 11 of the new signal engine in chrisrogers37/shitpost-alpha.

The old system was shut down on 1 October and its Railway services deleted. The dashboard's D0 has already deleted the old web app: `api/`, `frontend/`, the root `railway.json` and `railpack.json`. Everything that remains of the old system now goes, so the repo holds only the new engine and the plans built on it.

Design questions go to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) via send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## What Gate 0 decides
Nothing here.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges.
- **Databases.** Never touch a production database, the old one included. Never read or set DATABASE_URL.
- **Old key names.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. The old tests make paid calls when they exist, so don't run the old tests at all.
- **Other services.** No Railway calls. No Telegram, email or SMS. Don't touch S3 or any AWS resource: Chris archives those himself.
- **Keep the new code.** Keep `engine/` (and `engine/web`, `engine/api` if present), the notification plan's code, and anything the new code imports.
  - Before deleting a folder, prove nothing new imports it: grep, plus the engine's full test run after the deletion.
  - The notification plan found three import sites linking new and old code; resolve each one, and name them in the PR.

## Environment
- **Python.** 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python.
- **Postgres.** Local Postgres 16, URL in DEV_DATABASE_URL. The engine's tests use throwaway databases.

## Scope
**1. Delete the old system.**
- **Code and its tests:**
  - `shitpost_alpha.py`;
  - `shit/`, `shitvault/`, `shitposts/`, `shitpost_ai/`, the old `notifications/` (unless the notification plan reused the name; check first), `shit_tests/`;
  - the root `conftest.py`;
  - old `scripts/`.
- **The old dependencies:** the root `requirements.txt`, including the Twilio and SendGrid packages.
- **Any leftover old Railway or CI config.**

**2. Keep and update the docs.**
- **Old planning docs.**
  - Move `documentation/` and `docs/` content about the old system to `documentation/archive/`.
  - Never delete a doc: the repo's convention is to archive them.
- **The agent files, which describe the old system.**
  - Rewrite `CLAUDE.md` and `AGENTS.md` for the engine: layout, commands, tests and safety rules.
  - Remove the line pre-approving admin merges: Chris merges every PR himself.
  - Keep the production-safety rules, updated to the engine's names: ENGINE_DATABASE_URL, the sandbox-only DEV_DATABASE_URL, and the old key names.
- **Repo skills.** Archive `.claude/` skills, commands and context files that serve only the old system and its production database, and list them in the PR.
- **README.md and PROJECT_MISSION.md:** update them to the engine.
- **CHANGELOG.md:** keep it as it is, with the new entry.

**3. Chris's clean-up list,** in the PR body and sent to the engine planner. After this merges, Chris:
- archives the old Neon database;
- archives the old S3 bucket (`shitpost-alpha`);
- revokes the old keys the deleted code used: list each by variable name from the code (OpenAI, xAI, AWS, SendGrid, Twilio, the old database URL and any others you find);
- keeps two that carry over to the engine: the Telegram bot token and the ScrapeCreators key.

## How to check your work
- **Engine checks.** From engine/, ruff, ruff format --check, mypy and pytest all pass, and CI passes.
- **Other builds.** The notification plan's and dashboard's tests and the web app's build still pass.
- **No leftover imports.** `git grep` finds no imports of the deleted packages anywhere.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch.** Branch from main once D0 has merged. If D0 isn't merged yet, branch from D0's branch and say so. Commit and push.
2. **Draft PR.** Open a draft PR against main titled "Engine PR 11: remove the old code", saying what it goes in after. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - what was deleted and what was archived;
   - the three import sites;
   - Chris's clean-up list.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs.
