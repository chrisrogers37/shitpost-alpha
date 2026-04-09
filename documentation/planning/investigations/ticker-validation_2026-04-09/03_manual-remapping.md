# Tier 3: Manual Remapping (Aliases)

**Impact:** Medium — fixes known corporate action issues for past and future predictions
**Effort:** Low — data dict in the validation service (Tier 2)
**Risk:** Low — remapping is deterministic and auditable

---

## Problem

Corporate actions (mergers, renames, delistings) create a mismatch between the symbol the LLM extracts and the symbol yfinance can price. This is a recurring problem — every corporate action creates a new stale ticker.

## Design

The alias mapping lives as a static dict in `TickerValidator` (Tier 2). This is deliberate:

1. **Not a DB table** — corporate actions happen ~monthly, not daily. A code dict is version-controlled, testable, and reviewable. A DB table adds operational complexity for a problem that changes slowly.
2. **Applied at extraction time** — before the ticker reaches `prediction.assets`, so the stored prediction always has the current symbol.
3. **Null mappings** — `TWTR: None` means "this ticker has no valid replacement, filter it out."

## Known Aliases (Seed Data)

| Old | Current | Action | Date |
|---|---|---|---|
| RTN | RTX | Raytheon/UTC merger | Apr 2020 |
| FB | META | Facebook rebrand | Oct 2021 |
| RDS.A | SHEL | Shell plc rename | Jan 2022 |
| RDS.B | SHEL | Shell plc rename | Jan 2022 |
| CBS | PARA | CBS/Viacom → Paramount | Dec 2019 |
| AKS | CLF | AK Steel → Cleveland-Cliffs | Mar 2020 |
| TWTR | None | Twitter taken private | Oct 2022 |
| PTR | None | PetroChina delisted from NYSE | Sep 2022 |
| SNP | None | China Petroleum delisted | Sep 2022 |
| KOL | None | VanEck Coal ETF closed | Dec 2020 |
| OIL | None | iPath Oil ETN delisted | Apr 2021 |

## Maintenance Process

When a new corporate action is identified:
1. Add entry to `ALIASES` dict in `ticker_validator.py`
2. Add to the Known Aliases table in this doc
3. Run retroactive fix (Tier 5) if old symbol exists in historical predictions

## Existing Prediction Remediation

For the 17 currently-invalid tickers, Tier 5 (retroactive cleanup) will:
1. Update `prediction.assets` JSON to use the new symbol where a mapping exists
2. Update `prediction.market_impact` JSON keys to match
3. Re-trigger outcome calculation for remapped predictions

## Deliverables

- [ ] ALIASES dict seeded in `TickerValidator` (covered by Tier 2)
- [ ] Known aliases documented in this file
- [ ] Maintenance process documented
