#!/bin/bash
# Run probes (or any pytest args) against a checkout's engine dir, with secrets stripped.
# usage: runprobe.sh <engine_dir> <pytest args...>
ENG="$1"; shift
cd "$ENG" || exit 2
exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ALPACA_API_KEY_ID \
  -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  PYTHONPATH="$ENG" ENGINE_MODEL_DIR=/home/user/engine-models \
  /home/user/engine-venv-261/bin/python -m pytest -p no:cacheprovider -c "$ENG/pyproject.toml" --rootdir "$ENG" "$@"
