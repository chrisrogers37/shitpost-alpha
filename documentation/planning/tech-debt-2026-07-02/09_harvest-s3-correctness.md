# WS09 — Harvest & S3 Correctness (incremental, end_date, timezones, async)

**Priority**: HIGH
**Type**: bug
**Findings**: H7, H8, M25, M26
**Primary files**: `shitvault/s3_processor.py`, `shit/s3/s3_data_lake.py`, `shit/s3/s3_client.py`, `shitposts/truth_social_s3_harvester.py`, `shitposts/base_harvester.py`, `shit/db/database_utils.py`

---

## Findings

### H7 — Incremental S3 processing can reprocess everything
`s3_processor.py:76-99`: if the latest DB `signal_id` isn’t found in the S3 listing, the code falls back to processing **all** S3 keys. This is expensive and races with concurrent harvests. It also depends on `list_raw_data` returning keys in an order that contains that marker.

**Fix**: Use a durable watermark (max `published_at`/processed key) rather than "find last signal_id in listing"; if the marker is missing, do not silently process everything — log and process only strictly-new keys by timestamp.

### H8 — `list_raw_data()` ignores `end_date`
`s3_data_lake.py:197-246` accepts and documents `end_date` but never applies it, so range mode (`s3_processor.py:66,102-104`) loads files past the requested window. Related: it sorts by numeric post id and claims "chronological order," which only holds for monotonic Snowflake-style ids.

**Fix**: Apply `end_date` filtering to the listed/parsed keys; sort by actual timestamp where available.

### M25 — Fake-async S3 client + inconsistent `to_thread`
`s3_client.py:46-74` methods are `async def` but call synchronous boto3 (`head_bucket`, client creation) with no `to_thread`. In `s3_data_lake.py`, `store_raw_data`/`get_raw_data` use `to_thread` (109-124) but `list_raw_data`/`get_data_stats` run sync paginators inline (220-293). Net: intermittent event-loop blocking.

**Fix**: Wrap all blocking boto3 calls in `asyncio.to_thread` consistently (or make the S3 layer honestly sync and call it via threadpool from async code).

### M26 — Naive-UTC timestamps stripped through the pipeline
The harvester does `.replace(tzinfo=None)` (`truth_social_s3_harvester.py:133-137`) and `parse_timestamp()` strips tz (`database_utils.py:40-42`), while events/models use tz-aware UTC. Combined with naive date filters in harvester/S3/analyzer, edge-of-day and DST behavior is ambiguous.

**Fix**: Standardize on tz-aware UTC (`datetime.now(timezone.utc)`) end to end; store aware datetimes; compare with aware bounds.

## Acceptance criteria

- [ ] Incremental S3 processing never falls back to "process all" on a missing marker; it processes only strictly-new files (test with a marker absent from the listing).
- [ ] `list_raw_data(end_date=...)` excludes files after `end_date` (test).
- [ ] All blocking S3 calls are offloaded off the event loop.
- [ ] Timestamps are tz-aware UTC through harvest → S3 → DB → analysis.
