#!/bin/bash
# Usage: E.sh <checkout-engine-dir> cmd...  -- runs cmd with secrets stripped, PYTHONPATH set, models dir.
W="$1"; shift
cd "$W" || exit 1
exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ALPACA_API_KEY_ID -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY PYTHONPATH="$W" ENGINE_MODEL_DIR=/home/user/engine-models PATH=/home/user/engine-venv-261/bin:$PATH "$@"
