#!/bin/bash
# ruff, format, mypy and tests in the simplify-263-r1 scratch checkout. Args: pytest targets.
cd /tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/simplify-263-r1/engine
V=/home/user/engine-venv-261/bin
E="env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ALPACA_API_KEY_ID -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY PYTHONPATH=$PWD ENGINE_MODEL_DIR=/home/user/engine-models"
$E $V/ruff check . 2>&1 | tail -15
$E $V/ruff format --check . 2>&1 | tail -3
$E $V/mypy 2>&1 | tail -8
$E $V/pytest -q -p no:cacheprovider "${@:-tests}" 2>&1 | tail -12
