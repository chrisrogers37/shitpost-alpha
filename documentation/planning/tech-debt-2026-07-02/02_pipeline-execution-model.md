# WS02 — Unify the Pipeline Execution Model (CLI subprocess vs events)

**Priority**: CRITICAL
**Type**: architecture
**Findings**: C3, M10, M11
**Primary files**: `shitpost_alpha.py`, `shitposts/*`, `shitvault/event_consumer.py`, `shitvault/s3_processor.py`, `shitpost_ai/event_consumer.py`, `shitpost_ai/shitpost_analyzer.py`, `railway.json`

---

## Problem

There are **two parallel ways the pipeline runs**, and both can be active at once:

1. **Orchestrator subprocess chain** — `shitpost_alpha.py` shells out to `python -m shitposts`, `python -m shitvault`, `python -m shitpost_ai` in sequence (`shitpost_alpha.py:118-152`).
2. **Event-driven workers** — each phase *also* emits events (`SIGNALS_STORED`, `PREDICTION_CREATED`, …) that Railway cron workers consume (`*/event_consumer.py`), and `railway.json` schedules exactly these workers every 5 minutes.

If both the orchestrator and the workers run, the same S3 files get loaded twice and the same posts get analyzed twice (duplicate LLM spend). The system currently relies on operators not enabling both — an implicit, undocumented invariant.

## Findings

### C3 — Dual execution paths with no idempotency guard
- Harvest/S3/analyze emit events inline *and* the orchestrator runs the same phases synchronously (`shitpost_alpha.py:118-152`, `shitvault/s3_processor.py:123-140`, `shitpost_ai/shitpost_analyzer.py:571-620`).
- `railway.json` deploys the workers as the production path, making the orchestrator’s in-process phases redundant (and dangerous) in prod.

### M10 — Consumers ignore the IDs in their event payload
The analyzer worker logs `count` but then runs a **generic incremental pass over all unprocessed signals** rather than the specific `signal_ids` in the event (`shitpost_ai/event_consumer.py:39-49`). Same shape in `notifications/event_consumer.py`. This does extra work and is race-prone (two events triggering overlapping full scans).

### M11 — Consumer reaches into private processor internals
`shitvault/event_consumer.py:65-66` calls `S3Processor._process_single_s3_data()` directly, bypassing the public `process_s3_to_database()` and duplicating event-emission logic — two code paths to keep in sync.

## Proposed direction

Pick **one** production execution model and make the other explicitly dev-only:

- **Recommended: events are the production path** (matches `railway.json`). Then:
  - Change consumers to process **exactly the IDs in the payload** (idempotent, targeted), not a full incremental scan.
  - Make each processing step idempotent (dedup on `signal_id` / `prediction_id`) so a retried event is a no-op — this also backstops WS04/WS01 idempotency.
  - Repurpose `shitpost_alpha.py` as a dev/backfill-only orchestrator, clearly documented as "not for the Railway cron deployment," or have it enqueue events instead of doing work in-process.
  - Expose a public method on `S3Processor` for single-item processing so the consumer stops calling `_process_single_s3_data()`.

- Document the chosen model in `CLAUDE.md` and `railway.json` comments so the "don’t run both" invariant is explicit.

## Acceptance criteria

- [ ] Exactly one production execution model is documented and enforced; running the "other" path is either disabled or provably idempotent.
- [ ] Event consumers process the specific IDs from their payload (or are provably idempotent full scans), verified by a test that a duplicate event does no duplicate work.
- [ ] `shitvault/event_consumer.py` uses a public `S3Processor` API.
- [ ] `CLAUDE.md` describes which path is live and how backfill differs.
