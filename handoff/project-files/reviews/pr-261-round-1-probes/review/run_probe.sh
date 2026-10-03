#!/bin/bash
# Usage: run_probe.sh [pytest args...]  -- runs from the review worktree with secrets stripped
SP=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad
WT=${WT:-$SP/review-261-r1-wt/engine}
cd $WT && exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ANTHROPIC_BASE_URL \
  PYTHONPATH=$WT /home/user/engine-venv-261/bin/python -m pytest -c $WT/pyproject.toml --rootdir $WT \
  -p no:cacheprovider -q "$@"
