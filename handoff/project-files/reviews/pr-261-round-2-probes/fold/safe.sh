#!/bin/bash
# safe.sh <dir> <cmd...>: run a command in <dir> with every secret stripped.
SP=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad
D=$1; shift
cd "$D" && exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ANTHROPIC_BASE_URL \
  -u ALPACA_API_KEY_ID -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  -u OPENAI_BASE_URL -u OPENAI_ORG_ID -u OPENAI_PROJECT_ID -u OPENAI_CUSTOM_HEADERS -u ANTHROPIC_CUSTOM_HEADERS \
  ENGINE_MODEL_DIR=${ENGINE_MODEL_DIR_OVERRIDE:-/home/user/engine-models} \
  PYTHONPATH=$D PATH=/home/user/engine-venv-261/bin:$PATH "$@"
