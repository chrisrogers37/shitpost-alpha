# WS06 — Transaction Safety & Failure Persistence

**Priority**: HIGH
**Type**: bug
**Findings**: H4, H5, H6, L16
**Primary files**: `shitvault/prediction_operations.py`, `shitpost_ai/shitpost_analyzer.py`, `shit/echoes/echo_service.py`

---

## Findings

### H4 — No `session.rollback()` on prediction write failure
`store_analysis()` / `handle_no_text_prediction()` (`prediction_operations.py:147-149,218-220`) catch exceptions and return `None` without rolling back. In a batch, one failed write leaves the session in a broken state, poisoning subsequent operations in the same session.

**Fix**: `await session.rollback()` in the except block before returning/raising.

### H5 — Failed LLM analysis leaves no DB footprint
On analysis failure the analyzer returns `None` (`shitpost_ai/shitpost_analyzer.py:539-541`) and never writes an `analysis_status='error'` row, even though the model supports it. The signal stays "unprocessed" and is retried indefinitely — repeated LLM spend and no visibility into chronic failures.

**Fix**: Persist an `error` prediction row (with `analysis_comment`) on failure so the signal exits the unprocessed queue and failures are queryable. Consider a bounded retry count before marking permanently errored.

### H6 — `check_prediction_exists` fails open
`prediction_operations.py:254-256` returns `False` on DB error ("doesn’t exist"), which invites duplicate analysis and duplicate LLM cost precisely when the DB is unhealthy.

**Fix**: Distinguish "confirmed absent" from "unknown/error"; on error, raise or return a sentinel that callers treat as "do not re-analyze blindly."

### L16 — TOCTOU in `echo_service.embed_and_store`
`echo_service.py:56-78` checks existence in one session, calls OpenAI to embed, then inserts in a second session. Concurrent workers can duplicate embeddings or hit the `prediction_id` unique constraint.

**Fix**: Use `INSERT ... ON CONFLICT DO NOTHING` (or a single transaction with a uniqueness guard) and treat a conflict as success.

## Acceptance criteria

- [ ] Write-failure paths roll back the session; a subsequent write in the same batch succeeds (test).
- [ ] LLM analysis failure writes an `error` status row; the signal is not re-fetched as "unprocessed" indefinitely (test).
- [ ] `check_prediction_exists` does not silently report "absent" on DB error.
- [ ] Concurrent `embed_and_store` for the same prediction cannot violate the unique constraint (idempotent insert).
