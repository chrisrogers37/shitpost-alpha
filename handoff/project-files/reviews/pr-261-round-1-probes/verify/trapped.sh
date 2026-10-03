#!/usr/bin/env bash
# clean.sh, with every outbound request sent to the local trap proxy (127.0.0.1:18999)
# and the throwaway by-hand database as the engine database.
exec env HTTPS_PROXY=http://127.0.0.1:18999 HTTP_PROXY=http://127.0.0.1:18999 \
  https_proxy=http://127.0.0.1:18999 http_proxy=http://127.0.0.1:18999 NO_PROXY=localhost no_proxy=localhost \
  ENGINE_DATABASE_URL="${ENGINE_DATABASE_URL:-postgresql://shitpost:<redacted>@localhost:5432/verify261_hand}" \
  /tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-261-r1/verify/clean.sh "$@"
