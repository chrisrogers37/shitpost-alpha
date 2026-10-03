# Cloud environment setup (shitpost-alpha)

## Setup script
Paste `setup.sh` (this folder) into Project settings > Environment > Setup script.
Tested 2026-09-30 in a fresh sandbox: first run 1m27s, repeat run 6s (idempotent).
v2 (14:15 UTC): v1 exited 1 with "repo not found" in the real environment. v2 looks in
$CLAUDE_PROJECT_DIR, the working dir, git, common clone paths, then searches /home, /workspace,
/code, /root, /tmp, /srv, /opt, /mnt. It never exits non-zero (steps warn instead), because a
failing setup script blocks every new thread. Tested: normal path, repo at an unusual path, no repo.
Produces:
- `/home/claude/venv` — Python 3.13.12, requirements.txt + ruff 0.16.9 (activated in ~/.bashrc)
- `frontend/node_modules` via `npm ci` (`npm run build` passes)
- Local Postgres 16 + pgvector 0.6.0, db `shitpost_dev`, all 13 tables + scripts/*.sql
  URL `postgresql://shitpost:<redacted>@localhost:5432/shitpost_dev`, exported as
  `DEV_DATABASE_URL` (deliberately NOT `DATABASE_URL`, so tests keep using SQLite).

## Network policy: Custom, allowed hosts
Packages / setup:
  pypi.org
  files.pythonhosted.org
  registry.npmjs.org
  github.com
  archive.ubuntu.com       (setup installs postgresql-16-pgvector via apt)
  security.ubuntu.com
Truth Social (dev only; a sandbox test proves nothing about blocking):
  truthsocial.com
  ix.cnn.io                (CNN Truth Social archive, recommended free mirror)
  trumpstruth.org          (RSS mirror, recommended free mirror)
  www.trumpstruth.org      (trumpstruth.org redirects here)
Market data for backtesting (yfinance 1.7.0 calls exactly these):
  query1.finance.yahoo.com
  query2.finance.yahoo.com
  fc.yahoo.com             (cookie/crumb bootstrap; yfinance fails without it)
  finance.yahoo.com
  guce.yahoo.com           (consent redirect)
  consent.yahoo.com
Keep OFF (and no SCRAPECREATORS_API_KEY in variables or API credentials): api.openai.com, api.anthropic.com, api.x.ai, api.telegram.org,
api.sendgrid.com, api.twilio.com, api.scrapecreators.com (paid), www.alphavantage.co (keyed fallback).

## Secrets
None. Do not add DATABASE_URL (prod) or OPENAI_API_KEY.
Verified: with a dummy OPENAI_API_KEY, analyzer tests try to reach the live OpenAI API,
so a real key would make paid calls.

## Baseline test results (fresh setup, no secrets)
1986 passed, 9 failed, 40 errors. None are environment problems:
- 40 errors + 5 failures in shitpost_ai: tests need OPENAI_API_KEY set and then call the
  real LLM (tests aren't hermetic).
- 3 in events/consumers/test_s3_processor.py and 1 in api/test_public_read_api.py: test/code drift.
`ruff check .` reports 1628 pre-existing findings.

v3 (14:40 UTC): the real environment clones to /home/user/shitpost-alpha (now checked first);
venv goes next to the repo (/home/user/venv there); if the repo isn't there yet, waits up to 5 min.
v4 (14:50 UTC): startup run confirmed working (~52s). Fix: the venv/DEV_DATABASE_URL block now goes at the
TOP of ~/.bashrc, because Ubuntu's .bashrc returns early for non-interactive shells (Claude's Bash tool).
v5 (14:55 UTC): Claude Code's Bash tool re-exports its own PATH after .bashrc, so the venv's bin
was dropped. Step 5 now also writes small exec wrappers for python, python3, pip, pip3, pytest and ruff
into ~/.local/bin (first on that PATH). Lines from v5-path-fix.sh (Final environment check thread).
