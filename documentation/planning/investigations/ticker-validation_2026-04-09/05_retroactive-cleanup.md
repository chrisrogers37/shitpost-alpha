# Tier 5: Retroactive Cleanup

**Impact:** Medium — fixes existing bad data, fills gaps in price coverage
**Effort:** Medium — CLI commands + backfill runs
**Risk:** Medium — modifies existing prediction records (requires backup)

---

## Problem

Historical predictions contain bad ticker symbols that will never resolve. Three sub-problems:

1. **109 active tickers with 0 prices** — legitimate tickers auto-registered during FK migration, need price backfill
2. **17 invalid tickers** — some have remappings (RTN→RTX), some are concepts (DEFENSE), some are truly dead
3. **Remappable predictions** — predictions that reference old tickers where a current equivalent exists

## Step 1: Backfill Prices for Active Tickers

These 109 tickers were auto-registered for FK constraint compliance. Most are legitimate symbols (AAPL, TSLA, AMZN, etc.) that just need price data fetched.

```bash
# Safe — additive operation, no data modification
python -m shit.market_data backfill-all-missing
```

This will:
- Iterate over active tickers with 0 price records
- Fetch price history from yfinance
- Mark any that fail as "invalid"
- Expected: ~100 tickers get prices, ~9 get marked invalid (indices, foreign tickers)

## Step 2: Re-validate "Active" Tickers That Failed

After backfill, some tickers will still have 0 records but remain "active" (yfinance timeout, temporary API issue). Run a targeted re-check:

```python
from shit.db.sync_session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Find active tickers that still have 0 records after backfill
    result = conn.execute(text('''
        SELECT symbol FROM ticker_registry
        WHERE status = 'active' AND total_price_records = 0
    '''))
    stale = [r[0] for r in result]
    print(f"Still-empty active tickers: {len(stale)}")
    print(stale)
```

For each, check yfinance manually and mark invalid if appropriate.

## Step 3: Remap Historical Predictions via CLI (Requires Backup)

**⚠️ This modifies existing prediction records. Create a Neon backup branch first.**

**Challenge Round Decision:** Replaced ad-hoc SQL scripts with CLI commands. Fits the codebase's CLI-first pattern (13 existing Click commands in market_data). Makes operations repeatable for future corporate actions.

### New CLI command: `python -m shit.market_data remap-tickers`

```bash
# Dry run — shows what would change, no modifications
python -m shit.market_data remap-tickers --dry-run

# Execute remapping (requires Neon backup first)
python -m shit.market_data remap-tickers
```

The command imports `ALIASES` from `TickerValidator` (single source of truth for remappings) and for each alias with a non-None replacement:
- Updates `predictions.assets` JSON array (old symbol → new symbol)
- Updates `predictions.market_impact` JSON keys (old key → new key)
- Reports affected row counts per symbol

Implementation lives in `cli_registry.py`, logic in a service method on `TickerRegistryService`.

## Step 4: Remove Concept "Tickers" via CLI

### New CLI command: `python -m shit.market_data clean-concept-tickers`

```bash
# Dry run — shows what would change
python -m shit.market_data clean-concept-tickers --dry-run

# Execute removal
python -m shit.market_data clean-concept-tickers
```

The command imports `BLOCKLIST` from `TickerValidator` and for each concept found in predictions:
- Removes from `predictions.assets` JSON array
- Removes from `predictions.market_impact` JSON keys
- Reports affected row counts per concept

## Step 5: Re-trigger Outcome Calculation for Remapped Predictions

After remapping RTN→RTX in a prediction, the prediction now references RTX but has no `prediction_outcome` for RTX. Use the existing CLI:

```bash
# Recalculate outcomes for all predictions (safe — skips already-complete ones)
python -m shit.market_data calculate-outcomes
```

## Execution Order

1. Create Neon backup branch
2. Run `backfill-all-missing` (Step 1)
3. Re-validate remaining empty tickers (Step 2)
4. Count affected predictions for each remap (dry run)
5. Execute remaps (Step 3) — user approval required
6. Remove concepts (Step 4) — user approval required
7. Re-trigger outcomes (Step 5)
8. Verify feed displays correctly

## Deliverables

- [ ] `remap-tickers` CLI command with `--dry-run` flag
- [ ] `clean-concept-tickers` CLI command with `--dry-run` flag
- [ ] Neon backup branch created
- [ ] Price backfill run for 109 active tickers
- [ ] Stale active tickers re-validated and marked invalid
- [ ] Historical predictions remapped via `remap-tickers`
- [ ] Concept tickers removed via `clean-concept-tickers`
- [ ] Outcomes recalculated for remapped predictions
- [ ] Feed verification on production
