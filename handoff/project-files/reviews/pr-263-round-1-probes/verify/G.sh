#!/bin/bash
# Usage: G.sh <db-url-file> <cache-dir> cmd...  -- secrets stripped, socket guard loaded,
# every proxy variable pointed at the local trap, ENGINE_DATABASE_URL read from the file.
V=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-263-r1/verify
W=/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/verify-263-r1-wt/engine
URLFILE="$1"; CACHE="$2"; shift 2
cd "$W" || exit 1
URL=""
[ -n "$URLFILE" ] && [ -f "$URLFILE" ] && URL="$(cat "$URLFILE")"
exec env -u DATABASE_URL -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u XAI_API_KEY \
  -u ENGINE_OPENAI_KEY -u ENGINE_ANTHROPIC_KEY -u ENGINE_XAI_KEY -u ALPACA_API_KEY_ID \
  -u ALPACA_API_SECRET_KEY -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u NO_PROXY -u no_proxy \
  -u ENGINE_DATABASE_URL \
  ${URL:+ENGINE_DATABASE_URL=$URL} \
  ENGINE_BARS_CACHE_DIR="$CACHE" ENGINE_MODEL_DIR=/home/user/engine-models \
  HTTPS_PROXY=http://127.0.0.1:18263 HTTP_PROXY=http://127.0.0.1:18263 \
  https_proxy=http://127.0.0.1:18263 http_proxy=http://127.0.0.1:18263 \
  ALL_PROXY=http://127.0.0.1:18263 all_proxy=http://127.0.0.1:18263 \
  VERIFY_GUARD_LOG="$V/guard.log" PYTHONPATH="$V/guard:$W" \
  PATH=/home/user/engine-venv-261/bin:$PATH "$@"
