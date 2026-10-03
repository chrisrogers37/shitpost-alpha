#!/usr/bin/env bash
# shitpost-alpha cloud environment setup (paste into the environment's Setup script).
# Builds: Python 3.13 venv with requirements.txt + ruff, frontend node_modules,
# and a LOCAL Postgres 16 + pgvector database. Never touches production:
# it only talks to localhost and sets no secrets.
# It never exits non-zero: a failing setup script blocks every new session,
# so each step warns and moves on instead.
set -uo pipefail
log()  { echo "setup: $*"; }
warn() { echo "setup: WARNING: $*" >&2; }
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo -n"

# --- Locate the repo checkout -------------------------------------------------
is_repo() { [ -n "${1:-}" ] && [ -f "$1/requirements.txt" ] && [ -f "$1/shitpost_alpha.py" ]; }
REPO=""
for c in "${CLAUDE_PROJECT_DIR:-}" "$PWD" "$(git rev-parse --show-toplevel 2>/dev/null)" \
         "$HOME/shitpost-alpha" /home/user/shitpost-alpha /home/claude/shitpost-alpha \
         /workspace/shitpost-alpha /code/shitpost-alpha; do
  if is_repo "$c"; then REPO="$c"; break; fi
done
if [ -z "$REPO" ]; then
  for root in ${SETUP_SEARCH_ROOTS:-/home /workspace /code /root /tmp /srv /opt /mnt}; do
    hit="$(find "$root" -maxdepth 4 -name shitpost_alpha.py -not -path '*/node_modules/*' 2>/dev/null | head -1)"
    if [ -n "$hit" ] && is_repo "$(dirname "$hit")"; then REPO="$(dirname "$hit")"; break; fi
  done
fi
if [ -z "$REPO" ]; then
  # The environment can start this script while the repo is still being cloned:
  # wait up to 5 minutes for the checkout to appear.
  log "repo not there yet, waiting for the clone"
  for i in $(seq 1 150); do
    sleep 2
    hit="$(find /home /workspace /code /root -maxdepth 3 -name shitpost_alpha.py -not -path '*/node_modules/*' 2>/dev/null | head -1)"
    if [ -n "$hit" ] && is_repo "$(dirname "$hit")"; then REPO="$(dirname "$hit")"; break; fi
  done
  # let git finish writing the rest of the checkout
  [ -n "$REPO" ] && for i in $(seq 1 30); do [ -f "$REPO/.git/index.lock" ] || break; sleep 1; done
fi
if [ -n "$REPO" ]; then log "repo=$REPO"; else warn "repo not found (pwd=$PWD user=$(id -un)); skipping repo steps"; fi

if [ -n "$REPO" ] && [ -w "$(dirname "$REPO")" ]; then VENV="$(dirname "$REPO")/venv"
elif [ -d /home/claude ] && [ -w /home/claude ]; then VENV=/home/claude/venv
else VENV="$HOME/venv"; fi
DB_URL="postgresql://shitpost:<redacted>@localhost:5432/shitpost_dev"

# --- 1. Python 3.13 venv + deps + ruff ----------------------------------------
PY=$(command -v python3.13 || command -v python3)
if [ ! -x "$VENV/bin/python" ]; then "$PY" -m venv "$VENV" || warn "venv creation failed"; fi
if [ -x "$VENV/bin/pip" ]; then
  "$VENV/bin/pip" install -q --upgrade pip || warn "pip upgrade failed"
  if [ -n "$REPO" ]; then
    "$VENV/bin/pip" install -q -r "$REPO/requirements.txt" ruff || warn "pip install failed"
  else
    "$VENV/bin/pip" install -q ruff || warn "ruff install failed"
  fi
fi

# --- 2. Frontend deps ---------------------------------------------------------
if [ -n "$REPO" ] && [ -f "$REPO/frontend/package-lock.json" ]; then
  (cd "$REPO/frontend" && npm ci --no-audit --no-fund --loglevel=error) || warn "npm ci failed"
fi

# --- 3. Local Postgres 16 + pgvector ------------------------------------------
if [ ! -f /usr/share/postgresql/16/extension/vector.control ]; then
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get install -y -q postgresql-16-pgvector >/dev/null 2>&1 || \
    { $SUDO apt-get update -q >/dev/null 2>&1; $SUDO apt-get install -y -q postgresql-16-pgvector >/dev/null 2>&1; } || \
    warn "pgvector install failed (needs archive.ubuntu.com in the network allowlist)"
fi
DB_OK=0
if $SUDO service postgresql start >/dev/null 2>&1; then
  for i in $(seq 1 30); do pg_isready -q -h localhost && break; sleep 0.5; done
  pgsu() { $SUDO su postgres -c "$1"; }
  pgsu "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='shitpost'\"" | grep -q 1 || \
    pgsu "psql -qc \"CREATE ROLE shitpost LOGIN PASSWORD 'shitpost' SUPERUSER\""
  pgsu "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='shitpost_dev'\"" | grep -q 1 || \
    pgsu "psql -qc \"CREATE DATABASE shitpost_dev OWNER shitpost\""
  psql "$DB_URL" -qc "CREATE EXTENSION IF NOT EXISTS vector" && DB_OK=1 || warn "vector extension unavailable"
else
  warn "could not start Postgres"
fi

# --- 4. Schema: ORM tables, then the repo's SQL migrations ---------------------
#    (some migration errors are expected because create_all already made the objects)
if [ "$DB_OK" = 1 ] && [ -n "$REPO" ] && [ -x "$VENV/bin/python" ]; then
  (cd "$REPO" && DATABASE_URL="$DB_URL" "$VENV/bin/python" - <<'PY'
from sqlalchemy import create_engine
from shit.db.data_models import Base
import shitvault.shitpost_models, shitvault.signal_models, shit.market_data.models  # noqa
import shit.events.models, shit.echoes.models, notifications.models  # noqa
engine = create_engine("postgresql+psycopg://shitpost:<redacted>@localhost:5432/shitpost_dev")
Base.metadata.create_all(engine)
print("setup: tables =", len(Base.metadata.tables))
PY
  ) || warn "schema creation failed"
  for f in "$REPO"/scripts/[0-9][0-9][0-9]_*.sql; do
    [ -f "$f" ] && psql "$DB_URL" -q -v ON_ERROR_STOP=0 -f "$f" >/dev/null 2>&1
  done
fi

# --- 5. Make the venv and local DB the default for later shells ----------------
# The block goes at the TOP of each rc file: Ubuntu's .bashrc returns early for
# non-interactive shells, and Claude Code's Bash tool loads it non-interactively.
BLOCK="# shitpost-alpha setup
[ -f $VENV/bin/activate ] && . $VENV/bin/activate
export DEV_DATABASE_URL=$DB_URL
# end shitpost-alpha setup"
for rc in "$HOME/.bashrc" /root/.bashrc /home/user/.bashrc /home/claude/.bashrc; do
  [ -w "$(dirname "$rc")" ] || continue
  touch "$rc"
  sed -i '/^# shitpost-alpha setup$/,/^# end shitpost-alpha setup$/d' "$rc"   # drop an older copy
  { printf '%s\n' "$BLOCK"; cat "$rc"; } > "$rc.tmp" && mv "$rc.tmp" "$rc"
done
# Claude Code's Bash tool re-exports its own PATH after sourcing .bashrc, dropping
# $VENV/bin. ~/.local/bin comes first on that PATH, so put small wrappers there.
# (A plain symlink loses the venv; pytest/ruff there may be uv-tool symlinks, so
# remove the link instead of writing through it.)
BIN="$HOME/.local/bin"; mkdir -p "$BIN"
for t in python python3 pip pip3 pytest ruff; do
  [ -x "$VENV/bin/$t" ] || continue
  rm -f "${BIN:?}/${t:?}"
  printf '#!/bin/sh\nexec "%s/bin/%s" "$@"\n' "$VENV" "$t" > "$BIN/$t" && chmod +x "$BIN/$t"
done
log "done. venv=$VENV local DB=$DB_URL (exported as DEV_DATABASE_URL)"
exit 0
