#!/usr/bin/env bash
# Run a command from the verify checkout's engine/ with every secret stripped.
# Usage: clean.sh <command> [args...]
cd /tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/verify-261-r1-wt/engine || exit 99
exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY \
  -u ALPACA_API_KEY_ID -u ALPACA_API_SECRET_KEY -u ANTHROPIC_BASE_URL -u OPENAI_BASE_URL \
  \
  PATH=/home/user/engine-venv-261/bin:$PATH \
  PYTHONPATH=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/verify-261-r1-wt/engine \
  "$@"
