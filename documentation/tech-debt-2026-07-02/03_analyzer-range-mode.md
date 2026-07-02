# WS03 — Fix Analyzer Range-Mode Loop & Push Date Filters to SQL

**Priority**: CRITICAL
**Type**: bug
**Findings**: C2, M12
**Primary files**: `shitpost_ai/shitpost_analyzer.py`, `shitvault/signal_operations.py`

---

## Findings

### C2 — Range-mode can loop forever
`_analyze_date_range()` (`shitpost_ai/shitpost_analyzer.py:241-296`) repeatedly calls `get_unprocessed_signals(launch_date, limit)`, which returns **newest-first with no date bound** (`shitvault/signal_operations.py:67-125`). It then filters in Python to `[start_datetime, end_datetime]`:

```270:296:shitpost_ai/shitpost_analyzer.py
                # Filter shitposts by date range
                filtered_shitposts = []
                for shitpost in shitposts:
                    ...
                        if self.start_datetime <= post_datetime <= self.end_datetime:
                            filtered_shitposts.append(shitpost)
                        elif post_datetime < self.start_datetime:
                            # If we've reached posts before the start date, we can stop
                            ...
                            break

                if not filtered_shitposts:
                    ...
                    continue
```

If **all** unprocessed posts are newer than `end_datetime` (common: new posts arrive while backfilling an old range), every batch returns the same newest rows, none fall in-range, none are `< start_datetime` (so no `break`), `filtered_shitposts` is empty → `continue` → refetch the identical batch forever. Because nothing is ever marked processed, the query result never changes. Only an external kill stops it.

### M12 — Date filtering belongs in SQL
The range predicate is applied in Python after fetching newest-first rows. This is both the cause of C2 and inefficient. `get_unprocessed_signals` already supports `launch_date`; it should support `start`/`end` bounds and an order direction.

## Proposed fix

- Add optional `published_after` / `published_before` and `order` (ASC for backfill, DESC for incremental) parameters to `get_unprocessed_signals()` and apply them in the SQL `WHERE`/`ORDER BY`.
- In `_analyze_date_range()`, request rows **within** the range in ascending order and paginate by advancing a cursor (last `published_at`/`signal_id`) so each batch strictly progresses. Terminate when the query returns no in-range rows.
- Keep a hard safety cap (max batches or max total) as defense-in-depth against any future regression.

## Acceptance criteria

- [ ] Range-mode terminates when there are unprocessed posts newer than `end_date` (regression test: seed unprocessed posts after the range, run range mode, assert it returns without looping).
- [ ] Date filtering is performed in SQL; no full newest-first scan followed by Python filtering.
- [ ] Backfill order is deterministic (ASC) and cursor-advancing.
