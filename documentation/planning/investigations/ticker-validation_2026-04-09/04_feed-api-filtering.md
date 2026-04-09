# Tier 4: Feed API Filtering

**Impact:** Medium — immediate UX improvement, hides invalid tickers from display
**Effort:** Low — SQL WHERE clause addition
**Risk:** Low — filtering only, doesn't modify data

---

## Problem

The feed API (`api/queries/feed_queries.py:88-159`) returns outcomes for ALL tickers in a prediction, including those marked "invalid" in the ticker registry. The frontend then shows "No price data available" for these tickers.

The main post query (`feed_queries.py:57-63`) selects predictions with non-empty assets, but doesn't check whether those assets are valid/priceable.

## Changes

### File: `api/queries/feed_queries.py`

**Change 1: Filter outcomes to valid tickers only**

In `get_outcomes_for_prediction()`, add a WHERE clause to exclude invalid tickers:

```sql
-- Current (line 142):
WHERE po.prediction_id = :prediction_id

-- Updated:
WHERE po.prediction_id = :prediction_id
  AND (tr.status IS NULL OR tr.status != 'invalid')
```

The `LEFT JOIN ticker_registry tr` already exists. `tr.status IS NULL` handles tickers not yet in the registry (should be rare after Tier 2, but defensive). `tr.status != 'invalid'` filters out known-bad tickers.

**Change 2: Filter `prediction.assets` in API response**

In `api/services/feed_service.py`, filter the assets list to exclude invalid tickers before sending to frontend. This is a 2-line change — the API decides what's valid, the frontend displays what it receives.

```python
# In build_prediction() or the service method that assembles the response
# Filter assets to only include tickers that have outcomes
valid_assets = [a for a in assets if a in {o["symbol"] for o in outcomes}]
```

**Challenge Round Decision:** Frontend changes (Options A/B on TickerSelector.tsx) removed.
The frontend already handles missing outcomes gracefully (`activeOutcome` is undefined, components show null).
Filtering in both SQL and frontend would be double-filtering. The API is the single source of truth for what's valid.
After Tiers 1-2 deploy, new predictions won't have invalid tickers in `prediction.assets` at all.
After Tier 5 retroactive cleanup, historical data will be fixed too. This is a diminishing problem.

## Verification

- Load feed page, navigate to a dispatch with previously-invalid tickers (e.g., RTN post)
- Verify invalid tickers no longer appear in ticker pills
- Verify valid tickers on the same prediction still display correctly
- Verify predictions with ALL invalid tickers still show (with thesis, no ticker pills)

## Deliverables

- [ ] Updated `get_outcomes_for_prediction()` WHERE clause
- [ ] API-level asset filtering in `feed_service.py`
- [ ] Manual verification on production feed
