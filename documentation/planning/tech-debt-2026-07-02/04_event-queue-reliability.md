# WS04 — Event Queue Reliability

**Priority**: HIGH
**Type**: bug / architecture
**Findings**: C4, M9
**Primary files**: `shit/events/worker.py`, `shit/events/producer.py`, `shit/events/event_types.py`, `shit/events/models.py`, `shit/events/cli.py`

---

## Findings

### C4 — Orphaned `claimed` events on worker crash
`worker.py:141-224` claims events in one transaction (status → `claimed`) and processes them in separate transactions. There is no stale-claim timeout or reclaim path. If a worker dies (OOM, deploy, exception outside the handler) between claim and process, those events stay `claimed` forever and are never retried — silent pipeline stall.

**Fix**: Record `claimed_at` (and optionally a worker id) on claim. On each worker run, reclaim events whose `claimed_at` is older than a visibility timeout back to `pending`. Add a CLI/metric to surface long-`claimed` events.

### M9 — Payload schemas are documented but not enforced
`event_types.py:50-84` defines `PAYLOAD_SCHEMAS`, but `producer.emit_event()` (`producer.py:19-93`) accepts any dict. Producers can emit malformed payloads that only fail deep inside a consumer.

**Fix**: Validate payloads against `PAYLOAD_SCHEMAS` in `emit_event()` (or a thin Pydantic model per event type), raising on missing/mistyped required keys. Keep it permissive for optional fields.

### Related (see also)
- `cli.py:49-54,181` references a `failed` status that the model (`models.py:37`) doesn’t have (statuses are `pending`, `claimed`, `completed`, `dead_letter`). Fix the CLI summary/help to match the real state machine.
- Per-subscriber/worker send failures are swallowed without raising (`worker.py:194-206`); combined with no idempotency this enables duplicate side effects on retry — coordinate with WS01/WS02.

## Acceptance criteria

- [ ] A crash between claim and process leaves events recoverable: stale `claimed` events are reclaimed to `pending` after a timeout (test simulates an abandoned claim).
- [ ] `emit_event()` rejects payloads missing required keys for the event type (test per event type).
- [ ] Event CLI status vocabulary matches `EventStatus` (no phantom `failed`).
