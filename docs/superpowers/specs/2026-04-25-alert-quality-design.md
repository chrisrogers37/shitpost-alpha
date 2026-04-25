# Play 4: Alert Quality — Design Spec

**Status**: Approved
**Created**: 2026-04-25

---

## Goal

Improve Telegram alert quality with four enhancements: better ticker filtering, automated calibration, ensemble agreement visibility, and historical echo context. Unify the two alert paths (event consumer + cron engine) so both produce identically enriched alerts.

---

## Components

### F4: Ticker Blocklist Expansion

**File:** `shit/market_data/ticker_validator.py`

Expand the `BLOCKLIST` frozenset to catch common words that collide with real or phantom ticker symbols. Current blocklist has 12 entries (DEFENSE, CRYPTO, ECONOMY, etc.). Add:

```python
# Commodities-as-words (Trump frequently references these)
"GOLD", "STEEL", "COAL", "SILVER", "CORN", "GAS",
# Political/news words that collide with tickers
"TAX", "USA", "NEWS", "WIN", "WAR", "VOTE", "JOBS",
"NICE", "FAST", "REAL", "TRUE", "HOPE", "BEAR", "BULL",
```

Note: `OIL` is already handled via `ALIASES` (mapped to None). Adding it to BLOCKLIST too for belt-and-suspenders is fine — blocklist check runs first.

### F3: Calibration Refit Cron

**File:** `shit/market_data/calibration.py` (CLI already exists)
**Config:** Railway cron service

The `refit_all()` function and CLI entry point exist at lines 206-260. No Railway service runs it. Add:

- Railway cron service `calibration-refit` running weekly: `0 0 * * 0` (Sunday midnight UTC)
- Command: `python -m shit.market_data.calibration refit`

In the enrichment function (see below), apply `CalibrationService.calibrate()` to the raw confidence and add `calibrated_confidence` to the alert dict.

### F5: Ensemble Agreement in Alerts

**File:** `notifications/telegram_sender.py` (formatting already exists)

`_format_ensemble_section()` (lines 202-245) already renders agreement level, provider count, confidence spread, and dissenting views. It renders when `ensemble_metadata` is in the alert dict.

Ensure `ensemble_metadata` flows through both alert paths by including it in the shared enrichment function.

### F2: Historical Echoes in Alerts

**File:** `shit/echoes/echo_service.py` (service already exists)
**File:** `notifications/telegram_sender.py` (`_format_echo_section()` already exists at lines 166-199)

The event consumer already does echo lookups (lines 70-83 of `event_consumer.py`). Move this logic into the shared enrichment function so both paths get echoes.

Echo enrichment flow:
1. Get embedding for `prediction_id` via `EchoService.get_embedding()`
2. Find similar posts via `EchoService.find_similar_posts(embedding, limit=5, exclude_prediction_id=prediction_id)`
3. Aggregate outcomes via `EchoService.aggregate_echoes(matches, timeframe="t7")`
4. Set `alert["echoes"] = aggregated_result`

### Unified Alert Enrichment

**File:** `notifications/alert_engine.py`

Create `enrich_alert(alert: dict) -> dict` that both paths call after building the base alert dict:

```python
def enrich_alert(alert: dict) -> dict:
    """Enrich an alert dict with calibrated confidence, echoes, and ensemble data.
    
    Called by both the cron alert engine and the event consumer.
    Failures in any enrichment step are logged and skipped — never block the alert.
    """
    prediction_id = alert.get("prediction_id")
    
    # 1. Calibrated confidence
    try:
        from shit.market_data.calibration import CalibrationService
        raw_confidence = alert.get("confidence")
        if raw_confidence is not None:
            calibrated = CalibrationService(timeframe="t7").calibrate(raw_confidence)
            if calibrated is not None:
                alert["calibrated_confidence"] = calibrated
    except Exception as e:
        logger.debug(f"Calibration skipped: {e}")
    
    # 2. Historical Echoes
    if prediction_id and not alert.get("echoes"):
        try:
            from shit.echoes.echo_service import EchoService
            echo_service = EchoService()
            embedding = echo_service.get_embedding(prediction_id)
            if embedding:
                matches = echo_service.find_similar_posts(
                    embedding, limit=5, exclude_prediction_id=prediction_id
                )
                if matches:
                    alert["echoes"] = echo_service.aggregate_echoes(matches, timeframe="t7")
        except Exception as e:
            logger.debug(f"Echo lookup skipped: {e}")
    
    return alert
```

**Cron engine path** (`alert_engine.py`): Call `enrich_alert(alert)` in the loop at line ~78, after building the base alert dict. Also add `calibrated_confidence` and `ensemble_metadata` to the base dict from the DB query.

**Event consumer path** (`event_consumer.py`): Replace the inline echo lookup (lines 70-83) with `from notifications.alert_engine import enrich_alert` and call `enrich_alert(alert)`. Remove duplicated echo code.

---

## Data Flow

```
Signal → LLM Analysis → Prediction (with ensemble_metadata)
                              ↓
                    PREDICTION_CREATED event
                              ↓
              ┌───────────────┴───────────────┐
              ▼                               ▼
     Event Consumer                    Cron Alert Engine
     (builds base alert)               (builds base alert from DB)
              │                               │
              └───────────┬───────────────────┘
                          ▼
                   enrich_alert()
                   ├─ calibrated_confidence
                   ├─ echoes (similarity + outcomes)
                   └─ ensemble_metadata (already present)
                          ▼
                   format_telegram_alert()
                   ├─ _format_echo_section()
                   └─ _format_ensemble_section()
                          ▼
                   Telegram message sent
```

---

## Changes Summary

| File | Change |
|------|--------|
| `shit/market_data/ticker_validator.py` | Expand BLOCKLIST with ~15 new entries |
| `notifications/alert_engine.py` | Add `enrich_alert()` function; call it in cron path; add calibrated_confidence + ensemble_metadata to base alert dict |
| `notifications/event_consumer.py` | Replace inline echo lookup with `enrich_alert()` call |
| `notifications/db.py` | Already returns `ensemble_metadata` and `calibrated_confidence` — no changes needed |
| Railway config | Add `calibration-refit` cron service |

---

## What Does NOT Change

- `telegram_sender.py` formatting — echo and ensemble sections already render correctly
- `echo_service.py` — service is complete, no changes needed
- `calibration.py` — refit logic is complete, just needs scheduling
- Frontend — no UI changes in this play
- LLM prompts — no prompt changes (that's Play 1)

---

## Error Handling

Every enrichment step wraps in try/except. A failed echo lookup or calibration should never prevent an alert from being sent. Log at `debug` level (these are optional enrichments, not critical failures).

---

## Testing

- Update existing alert_engine tests to verify `enrich_alert()` adds expected keys
- Update event_consumer tests to verify it calls `enrich_alert()`
- Add ticker_validator tests for new blocklist entries
- Run full test suite: `source venv/bin/activate && pytest -v`
