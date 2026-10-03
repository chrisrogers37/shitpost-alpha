# Engine PR 3 Part B evidence (2 Oct 2026)

Private: the raw Alpaca answers and the Yahoo cross-check hold real prices, so they stay
here and never go into the public repo. No keys or request headers are saved.

- raw/: one full answer per claim call (request path and params, status, rate-limit
  headers, body), recorded 19:04 and 19:13 UTC.
- record_claims.py, record_gh.py: the recorders (keys from the environment, headers only).
- build_fixtures.py: turns raw/ into engine/tests/fixtures (bar numbers replaced by stand-ins).
- backfill.txt: `python -m engine backfill-bars` on a fresh sandbox database.
- crosscheck.txt: `python scripts/crosscheck_yfinance.py` (Yahoo numbers: personal use only).
