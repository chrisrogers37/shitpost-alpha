---
name: cloud-env-setup
description: Tested cloud setup script, network host list and test baseline for shitpost-alpha sandboxes (2026-09-30)
metadata:
  type: project
  modified: 2026-09-30T14:37:54.833Z
---

Setup script + host list: /mnt/project-files/setup/setup.sh and README.md. Builds a venv next to the repo (/home/user/venv in the shitpost-alpha env; py3.13 + ruff), frontend npm ci, local Postgres 16 + pgvector with all 13 tables; exports DEV_DATABASE_URL (not DATABASE_URL, so tests stay on SQLite). Pasted by Chris into the shitpost-alpha cloud environment settings (claude.ai/code environment picker, not Project settings) on 2026-09-30.

Test baseline with no secrets: 1986 pass, 9 fail, 40 errors, all repo test bugs (shitpost_ai tests need OPENAI_API_KEY and then call the live API; s3_processor and public_read_api tests drifted). ruff: 1628 pre-existing findings. Never set a dummy OpenAI key to "fix" them: tests then try the real API.

GitHub: session's GitHub identity is chrisrogers37 and git push --dry-run to origin succeeds, so push/PR access works.

**Why:** avoid redoing environment discovery each session.
**How to apply:** a red test run matching this baseline is not a regression. See [[dev-database-branch]].

Environment shitpost-alpha (env_01BRkta6oZnX34AW2kCabFSi) is the project default since 2026-09-30. It had real DATABASE_URL, OPENAI_API_KEY and AWS keys stored as variables; Chris deleted them 14:08 UTC. Plain settings kept: S3_PREFIX, AWS_REGION, S3_BUCKET_NAME, FILE_LOGGING, SYSTEM_LAUNCH_DATE. If secrets ever reappear there, stop and flag it.

Env check 2026-09-30 14:25 (thread "Check the new environment setup"):
- SCRAPECREATORS_API_KEY still present with a real value (not in Chris's pasted list; may live in env vars or Project settings API credentials). Asked Chris to delete. S3_PREFIX, AWS_REGION, FILE_LOGGING were absent from the container. AWS_* values are proxy placeholders ("prox...").
- Network OK except trumpstruth.org 301-redirects to www.trumpstruth.org, which is blocked: add www.trumpstruth.org. ix.cnn.io archive JSON (~20 MB) downloads. Yahoo answers 429 to plain curl/crumb, but yfinance still returns SPY history, so backtest prices work. api.anthropic.com is always reachable (harness NO_PROXY), not a policy leak.
- setup.sh v2 run by hand in the real env: clean in 1m24s (py3.13.12, ruff 0.16.9, node_modules, pgvector 0.6.0, 13 tables). Startup run unverified. Env-manager log showed env_init (setup script) starting in parallel with the git clone; likely why v1 said "repo not found" (inferred). If a fresh session still misses the repo, setup.sh must wait for the checkout.
- Reading /proc/1/environ is denied by auto mode; don't try it.
- setup.sh v3 (14:40): checks /home/user/shitpost-alpha first, venv beside repo, waits up to 5 min for the clone.
- 14:36: Chris deleted SCRAPECREATORS_API_KEY and added www.trumpstruth.org. Network allowlist edits apply live to running sessions (www.trumpstruth.org went blocked -> 200 mid-session, /feed downloads); variable edits only reach new sessions. No other allowed host redirects to a different name. pytest in the real env (keys unset, v2 hand-run setup) matched the baseline exactly: 1986/9/40. Only the startup run of setup.sh (and the key's absence) remains to verify in a fresh session (v3 startup).
- v5 (14:55): Claude's Bash re-exports PATH after .bashrc; setup.sh writes exec wrappers into ~/.local/bin for python/pip/pytest/ruff. Final environment check: env ready, tests match baseline.
