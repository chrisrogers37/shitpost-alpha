---
name: claude-bash-path
description: Why Claude's Bash tool ignores the venv on PATH in shitpost-alpha sandboxes, and the wrapper fix (2026-09-30)
metadata:
  type: project
  modified: 2026-09-30T14:53:08.904Z
---

Final environment check (2026-09-30 14:50, fresh startup of setup.sh v4):
- Setup ran at startup (env log: session_mode new, clone done 14:46:40, then setup_script 14:46:40 -> 14:49:50, ~3m10s, mostly pip). Clone now finishes before setup starts.
- Results OK: /home/user/venv py3.13.12 + ruff 0.16.9, frontend/node_modules, Postgres 16.13 + pgvector 0.6.0, shitpost_dev with 13 tables. No secrets; DATABASE_URL/OPENAI_API_KEY unset; AWS_* are proxy placeholders. Network allow/deny correct (OpenAI/Telegram get proxy 403). pytest via /home/user/venv/bin/python matched baseline 1986/9/40.
- Problem: Claude Code's shell snapshot sources ~/.bashrc (VIRTUAL_ENV and DEV_DATABASE_URL arrive) but then re-exports the harness PATH, dropping venv/bin. So bare `python` is system 3.11, and bare `pytest`/`ruff` are uv-tool copies in ~/.local/bin with no repo deps.
- Fix proposed: /mnt/project-files/setup/v5-path-fix.sh writes sh wrappers (exec $VENV/bin/<tool>) into ~/.local/bin, first on the harness PATH. A symlink does NOT work (python loses the venv). Remove the uv symlink first; never write through it.
- Until the fix is in: call /home/user/venv/bin/python -m pytest (etc.) explicitly.
- Auto mode denied writing wrappers into ~/.local/bin from a thread ("unauthorized persistence"); only the setup script can do it.

See [[cloud-env-setup]].
