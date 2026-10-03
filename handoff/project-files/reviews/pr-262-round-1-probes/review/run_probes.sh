#!/bin/bash
# Run probe tests against a checkout (default: the PR worktree). Usage: run_probes.sh [-w <checkout>] <pytest args>
SP=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad
WT=$SP/review-262-r1-wt
if [ "$1" = "-w" ]; then WT=$2; shift 2; fi
cd $WT/engine || exit 1
exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY \
  -u ALPACA_API_KEY_ID -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  -u ENGINE_DATABASE_URL -u WEB_DATABASE_URL \
  PYTHONPATH=$WT/engine timeout 900 /home/user/engine-venv-262/bin/python -m pytest \
  -c $WT/engine/pyproject.toml --rootdir=$WT/engine -p tests.conftest -p tests.web.conftest \
  -p no:cacheprovider "$@"
