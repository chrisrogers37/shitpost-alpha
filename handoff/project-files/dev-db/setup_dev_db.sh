#!/usr/bin/env bash
# Stand up a local Postgres in a Claude cloud sandbox for shitpost-alpha dev/backtests.
# Never touches production: it only ever talks to localhost.
# Usage: bash /mnt/project-files/dev-db/setup_dev_db.sh [repo_dir] [venv_dir]
set -euo pipefail
REPO="${1:-/home/claude/shitpost-alpha}"
VENV="${2:-/home/claude/venv}"
DB_URL="postgresql://shitpost:<redacted>@localhost:5432/shitpost_dev"

# 1. Postgres 16 + pgvector (post_embeddings needs the vector extension)
if [ ! -f /usr/share/postgresql/16/extension/vector.control ]; then
  apt-get install -y -q postgresql-16-pgvector >/dev/null 2>&1 || \
    { apt-get update -q >/dev/null && apt-get install -y -q postgresql-16-pgvector >/dev/null; }
fi
service postgresql start >/dev/null
for i in $(seq 1 20); do pg_isready -q -h localhost && break; sleep 0.5; done

# 2. Role + database (idempotent)
su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='shitpost'\"" | grep -q 1 || \
  su postgres -c "psql -qc \"CREATE ROLE shitpost LOGIN PASSWORD 'shitpost' SUPERUSER\""
su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='shitpost_dev'\"" | grep -q 1 || \
  su postgres -c "psql -qc \"CREATE DATABASE shitpost_dev OWNER shitpost\""
psql "$DB_URL" -qc "CREATE EXTENSION IF NOT EXISTS vector"

# 3. Python deps (repo targets 3.13)
if [ ! -x "$VENV/bin/python" ]; then
  python3.13 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$REPO/requirements.txt"
fi

# 4. Schema from the ORM models (all of them), then the SQL migrations in order
cd "$REPO"
DATABASE_URL="$DB_URL" "$VENV/bin/python" - <<'PY'
from sqlalchemy import create_engine
from shit.db.data_models import Base
import shitvault.shitpost_models, shitvault.signal_models, shit.market_data.models  # noqa
import shit.events.models, shit.echoes.models, notifications.models  # noqa
engine = create_engine("postgresql+psycopg://shitpost:<redacted>@localhost:5432/shitpost_dev")
Base.metadata.create_all(engine)
print("tables:", len(Base.metadata.tables))
PY
for f in scripts/[0-9][0-9][0-9]_*.sql; do
  echo "== $f"; psql "$DB_URL" -q -v ON_ERROR_STOP=0 -f "$f" 2>&1 | grep -E "ERROR" || true
done

echo "Ready. export DATABASE_URL=$DB_URL"
