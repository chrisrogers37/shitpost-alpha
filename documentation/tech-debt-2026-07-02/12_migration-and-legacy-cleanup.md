# WS12 — Finish `signals` Migration & Remove Dead Abstractions

**Priority**: MEDIUM
**Type**: tech-debt
**Findings**: H9, M22, M23, M24, L11, L13, L14, L15
**Primary files**: `shitvault/signal_operations.py`, `shitvault/statistics.py`, `shitvault/shitpost_models.py`, `shitpost_ai/shitpost_analyzer.py`, `shitposts/harvester_registry.py`, `shitposts/twitter_harvester.py`, `shitposts/cli.py`, `shitposts/__main__.py`, `shit/db/database_utils.py`, `shit/content/bypass_service.py`, `shitvault/s3_processor.py`, `shitvault/prediction_operations.py`

---

## Theme

Two half-finished migrations leave dead code and dual sources of truth: (1) `truth_social_shitposts` → `signals`, and (2) single-source → multi-source harvesting. New contributors can’t tell what’s live.

## Findings

### M22 — Dual identity (`shitpost_id` ↔ `signal_id`)
Analyzer, CLI, and events still speak `shitpost_id` while DB writes only `predictions.signal_id`; aliases are injected at read time, not stored (`signal_operations.py:160-161`, `shitpost_analyzer.py:386-394,603-604`). Callers that bypass `SignalOperations` break.

**Fix**: Standardize on `signal_id` end to end; keep DB-level backward compat but stop threading `shitpost_id` through app code. Update the `PREDICTION_CREATED` payload (drop the explicit `shitpost_id: None`).

### M23 — Legacy table still drives stats
`statistics.py:31-99` counts `truth_social_shitposts` for totals and `analysis_rate`. Post-migration dashboards under-report.

**Fix**: Compute stats from `signals`.

### M24 / H9 — Multi-source harvesting is dead at runtime
`HarvesterRegistry`/`create_default_registry()` and the Twitter stub are exported but never invoked; `python -m shitposts` always runs the Truth Social harvester, so `--source` (and `--max-id` resume) are dead CLI contracts (`shitposts/cli.py:44-48`, `__main__.py:9-13`, `truth_social_s3_harvester.py:36-45`).

**Fix**: Either wire `__main__`/CLI to the registry (making `--source`/`--max-id` real) or remove the registry + Twitter stub and the dead flags until multi-source is actually needed. Don’t ship a non-functional stub that `ENABLED_HARVESTERS` could accidentally enable.

### Cleanups
- **L11**: Remove dead `transform_s3_data_to_shitpost()` (`database_utils.py:49-134`) — the S3 processor uses `SignalTransformer`.
- **L15**: Remove the `use_signal` parameter documented "deprecated, ignored" but still threaded through call sites (`prediction_operations.py:49-57`).
- **L14**: Implement or remove the `get_s3_processing_stats` stub (`s3_processor.py:236-245`) so `processing-stats` isn’t misleading.
- **L13**: Tighten bypass test phrases (`bypass_service.py:60,159-160`) so single-word real posts ("hi"/"hello") aren’t bypassed.
- Decide the fate of the `TruthSocialShitpost` ORM model (`shitpost_models.py:29-97`) — retained for history but no write path; document clearly as archive-only.
- Align docs (`shitvault/README.md`) that still describe `store_shitpost`/`shitpost_id` FK.

## Acceptance criteria

- [ ] App code references `signal_id` only; `shitpost_id` remains only for archived rows/DB compat (documented).
- [ ] Stats computed from `signals` (test).
- [ ] `--source`/`--max-id` either work end to end or are removed along with the dead registry/Twitter stub.
- [ ] Dead transformer, `use_signal` param, and stub stats removed/implemented.
- [ ] Bypass phrase list no longer bypasses legitimate short posts.
- [ ] `shitvault/README.md` matches the `signals`-only reality.
