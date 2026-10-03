# Proposed addition to setup.sh (v5), from the "Final environment check" thread, 2026-09-30.
# Paste at the end of step 5, just before the final `log "done..."` line.
#
# Why: Claude Code's Bash tool keeps its own PATH. Its shell snapshot sources ~/.bashrc
# (so VIRTUAL_ENV and DEV_DATABASE_URL do arrive) but then re-exports the harness PATH,
# which drops $VENV/bin. Result in a fresh session: `python` is 3.11 without the repo deps,
# and `pytest`/`ruff` are uv-tool copies with no repo packages.
# ~/.local/bin is first on that harness PATH, so small wrappers there win.
# Tested: a wrapper on PATH gives Python 3.13.12 with sys.prefix=/home/user/venv and the
# repo packages importable. A plain symlink does NOT work (Python loses the venv).
# pytest and ruff in ~/.local/bin are symlinks into uv tools: remove the link first,
# never write through it.

BIN="$HOME/.local/bin"; mkdir -p "$BIN"
for t in python python3 pip pip3 pytest ruff; do
  [ -x "$VENV/bin/$t" ] || continue
  rm -f "${BIN:?}/${t:?}"
  printf '#!/bin/sh\nexec "%s/bin/%s" "$@"\n' "$VENV" "$t" > "$BIN/$t" && chmod +x "$BIN/$t"
done
