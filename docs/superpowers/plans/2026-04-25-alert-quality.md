# Play 4: Alert Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Telegram alert quality with better ticker filtering, automated calibration, ensemble agreement visibility, historical echo context, and unified alert enrichment across both dispatch paths.

**Architecture:** Create a shared `enrich_alert()` function in `alert_engine.py` that both the cron engine and event consumer call. This function adds calibrated confidence and Historical Echoes to every alert. Ensemble metadata already flows through both paths. Fix ticker false positives by expanding the validator blocklist.

**Tech Stack:** Python 3.13, PostgreSQL (Neon), Telegram Bot API, Railway cron

**Spec:** `docs/superpowers/specs/2026-04-25-alert-quality-design.md`

---

## File Structure

### Files to Modify
- `shit/market_data/ticker_validator.py` — Expand BLOCKLIST
- `notifications/alert_engine.py` — Add `enrich_alert()`, wire into cron path
- `notifications/event_consumer.py` — Replace inline echo lookup with `enrich_alert()` call
- `notifications/db.py` — Add `calibrated_confidence` and post text to predictions query

### Test Files to Modify
- `shit_tests/shit/market_data/test_ticker_validator.py` — Test new blocklist entries
- `shit_tests/notifications/test_alert_engine.py` — Test `enrich_alert()`
- `shit_tests/events/consumers/test_notifications.py` — Update for `enrich_alert()` call

---

## Task 1: Ticker Blocklist Expansion

**Files:**
- Modify: `shit/market_data/ticker_validator.py:25-40`

- [ ] **Step 1: Expand the BLOCKLIST**

In `shit/market_data/ticker_validator.py`, replace the BLOCKLIST (lines 25-40):

```python
    # Known non-ticker strings the LLM commonly extracts
    BLOCKLIST: frozenset[str] = frozenset(
        {
            # Economic/financial terms
            "DEFENSE", "CRYPTO", "ECONOMY", "TARIFF",
            "GDP", "CPI", "FED", "IPO", "ESG",
            # Media/orgs
            "NEWSMAX", "NATO", "CEO",
            # Commodities-as-words (Trump frequently references these)
            "GOLD", "STEEL", "COAL", "SILVER", "CORN", "GAS",
            # Political/news words that collide with tickers
            "TAX", "USA", "NEWS", "WIN", "WAR", "VOTE", "JOBS",
            "NICE", "FAST", "REAL", "TRUE", "HOPE", "BEAR", "BULL",
        }
    )
```

- [ ] **Step 2: Run existing ticker validator tests**

Run: `source venv/bin/activate && pytest shit_tests/shit/market_data/test_ticker_validator.py -v`

Expected: All existing tests pass (new blocklist entries don't break existing tests).

- [ ] **Step 3: Add tests for new blocklist entries**

Add a test to the existing test file:

```python
def test_blocklist_rejects_commodity_words(self):
    """Verify common words that collide with tickers are blocked."""
    validator = TickerValidator()
    commodity_words = ["GOLD", "STEEL", "COAL", "SILVER", "CORN", "GAS"]
    result = validator.validate_symbols(commodity_words)
    assert result == [], f"Expected all blocked, got {result}"

def test_blocklist_rejects_political_words(self):
    """Verify political words that collide with tickers are blocked."""
    validator = TickerValidator()
    political_words = ["TAX", "USA", "NEWS", "WIN", "WAR", "VOTE", "JOBS"]
    result = validator.validate_symbols(political_words)
    assert result == [], f"Expected all blocked, got {result}"
```

- [ ] **Step 4: Run tests**

Run: `source venv/bin/activate && pytest shit_tests/shit/market_data/test_ticker_validator.py -v`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add shit/market_data/ticker_validator.py shit_tests/shit/market_data/test_ticker_validator.py
git commit -m "fix: expand ticker blocklist to catch GOLD, STEEL, and other false positives"
```

---

## Task 2: Add calibrated_confidence and text to predictions query

**Files:**
- Modify: `notifications/db.py:369-402`

- [ ] **Step 1: Update the SQL query in `get_new_predictions_since()`**

Add `p.calibrated_confidence` and a join to get post text. Replace the query (lines 370-393):

```python
    results = _execute_read(
        """
        SELECT
            p.post_timestamp AS timestamp,
            p.signal_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.calibrated_confidence,
            p.thesis,
            p.analysis_status,
            p.ensemble_metadata,
            p.created_at as prediction_created_at,
            s.text as text
        FROM predictions p
        LEFT JOIN signals s ON s.signal_id = p.signal_id
        WHERE p.analysis_status = 'completed'
            AND p.created_at > :since
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
        ORDER BY p.created_at DESC
        LIMIT 50
        """,
        params={"since": since},
        default=[],
        context="get_new_predictions_since",
    )
```

- [ ] **Step 2: Run notifications tests**

Run: `source venv/bin/activate && pytest shit_tests/notifications/ -x -q`

Expected: Tests pass (query returns additional columns that existing code ignores).

- [ ] **Step 3: Commit**

```bash
git add notifications/db.py
git commit -m "feat: add calibrated_confidence and post text to predictions query"
```

---

## Task 3: Create enrich_alert() and wire into both paths

**Files:**
- Modify: `notifications/alert_engine.py`
- Modify: `notifications/event_consumer.py`

- [ ] **Step 1: Add `enrich_alert()` to `alert_engine.py`**

Add this function after the imports (after line 27):

```python
def enrich_alert(alert: dict) -> dict:
    """Enrich an alert dict with calibrated confidence and historical echoes.

    Called by both the cron alert engine and the event consumer to ensure
    identical alert quality regardless of dispatch path.

    Failures in any enrichment step are logged and skipped — never block the alert.
    """
    prediction_id = alert.get("prediction_id")

    # Calibrated confidence
    if alert.get("calibrated_confidence") is None:
        try:
            from shit.market_data.calibration import CalibrationService

            raw_confidence = alert.get("confidence")
            if raw_confidence is not None:
                calibrated = CalibrationService(timeframe="t7").calibrate(
                    raw_confidence
                )
                if calibrated is not None:
                    alert["calibrated_confidence"] = calibrated
        except Exception as e:
            logger.debug(f"Calibration skipped for prediction {prediction_id}: {e}")

    # Historical Echoes
    if prediction_id and not alert.get("echoes"):
        try:
            from shit.echoes.echo_service import EchoService

            echo_service = EchoService()
            embedding = echo_service.get_embedding(prediction_id)
            if embedding:
                matches = echo_service.find_similar_posts(
                    embedding,
                    limit=5,
                    exclude_prediction_id=prediction_id,
                )
                if matches:
                    alert["echoes"] = echo_service.aggregate_echoes(
                        matches, timeframe="t7"
                    )
        except Exception as e:
            logger.debug(f"Echo lookup skipped for prediction {prediction_id}: {e}")

    return alert
```

- [ ] **Step 2: Wire `enrich_alert()` into the cron path**

In `check_and_dispatch()`, add the enrichment call after building alerts (after line 78):

Replace:
```python
        alerts.append(alert)
```
With:
```python
        alerts.append(enrich_alert(alert))
```

- [ ] **Step 3: Update the cron path to include `calibrated_confidence` and `text`**

In the alert dict construction (lines 67-77), the `text` field already exists but `calibrated_confidence` is missing. Add it:

Replace:
```python
        alert = {
            "prediction_id": pred.get("prediction_id"),
            "signal_id": pred.get("signal_id"),
            "text": pred.get("text", "")[:200],
            "confidence": pred.get("confidence"),
            "assets": pred.get("assets", []),
            "sentiment": _extract_sentiment(pred.get("market_impact", {})),
            "thesis": pred.get("thesis", ""),
            "timestamp": pred.get("timestamp"),
            "ensemble_metadata": pred.get("ensemble_metadata"),
        }
```
With:
```python
        alert = {
            "prediction_id": pred.get("prediction_id"),
            "signal_id": pred.get("signal_id"),
            "text": pred.get("text", "")[:200],
            "confidence": pred.get("confidence"),
            "calibrated_confidence": pred.get("calibrated_confidence"),
            "assets": pred.get("assets", []),
            "sentiment": _extract_sentiment(pred.get("market_impact", {})),
            "thesis": pred.get("thesis", ""),
            "timestamp": pred.get("timestamp"),
            "ensemble_metadata": pred.get("ensemble_metadata"),
        }
```

- [ ] **Step 4: Replace inline echo lookup in event_consumer.py with `enrich_alert()`**

In `notifications/event_consumer.py`, replace the inline echo code (lines 69-83) with a call to `enrich_alert()`:

Replace:
```python
        # Enrich alert with Historical Echoes
        try:
            from shit.echoes.echo_service import EchoService

            echo_service = EchoService()
            embedding = echo_service.get_embedding(prediction_id)
            if embedding:
                matches = echo_service.find_similar_posts(
                    embedding,
                    limit=5,
                    exclude_prediction_id=prediction_id,
                )
                alert["echoes"] = echo_service.aggregate_echoes(matches, timeframe="t7")
        except Exception as e:
            logger.debug(f"Echo lookup skipped for prediction {prediction_id}: {e}")
```
With:
```python
        # Enrich alert with calibrated confidence and historical echoes
        from notifications.alert_engine import enrich_alert

        alert = enrich_alert(alert)
```

- [ ] **Step 5: Run all notification tests**

Run: `source venv/bin/activate && pytest shit_tests/notifications/ shit_tests/events/consumers/test_notifications.py -x -q`

Fix any failures.

- [ ] **Step 6: Commit**

```bash
git add notifications/alert_engine.py notifications/event_consumer.py
git commit -m "feat: unified alert enrichment with calibration and echoes"
```

---

## Task 4: Tests for enrich_alert

**Files:**
- Modify: `shit_tests/notifications/test_alert_engine.py`

- [ ] **Step 1: Add tests for `enrich_alert()`**

```python
from unittest.mock import patch, MagicMock
from notifications.alert_engine import enrich_alert


class TestEnrichAlert:
    """Tests for the unified alert enrichment function."""

    def test_adds_calibrated_confidence(self):
        """enrich_alert adds calibrated_confidence from CalibrationService."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch("notifications.alert_engine.CalibrationService") as mock_cal:
            mock_cal.return_value.calibrate.return_value = 0.65
            result = enrich_alert(alert)
        assert result["calibrated_confidence"] == 0.65

    def test_skips_calibration_if_already_set(self):
        """enrich_alert does not overwrite existing calibrated_confidence."""
        alert = {"prediction_id": 1, "confidence": 0.8, "calibrated_confidence": 0.7}
        result = enrich_alert(alert)
        assert result["calibrated_confidence"] == 0.7

    def test_adds_echoes(self):
        """enrich_alert adds echoes from EchoService."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        echoes_result = {"count": 3, "win_rate": 0.67, "avg_return": 1.2}
        with patch("notifications.alert_engine.EchoService") as mock_echo:
            mock_echo.return_value.get_embedding.return_value = [0.1] * 1536
            mock_echo.return_value.find_similar_posts.return_value = [{"prediction_id": 2}]
            mock_echo.return_value.aggregate_echoes.return_value = echoes_result
            with patch("notifications.alert_engine.CalibrationService") as mock_cal:
                mock_cal.return_value.calibrate.return_value = None
                result = enrich_alert(alert)
        assert result["echoes"] == echoes_result

    def test_skips_echoes_if_no_prediction_id(self):
        """enrich_alert skips echo lookup when prediction_id is missing."""
        alert = {"confidence": 0.8}
        result = enrich_alert(alert)
        assert "echoes" not in result

    def test_calibration_failure_does_not_block(self):
        """enrich_alert continues when calibration raises an exception."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch("notifications.alert_engine.CalibrationService", side_effect=Exception("boom")):
            result = enrich_alert(alert)
        assert "calibrated_confidence" not in result

    def test_echo_failure_does_not_block(self):
        """enrich_alert continues when echo service raises an exception."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch("notifications.alert_engine.CalibrationService") as mock_cal:
            mock_cal.return_value.calibrate.return_value = None
            with patch("notifications.alert_engine.EchoService", side_effect=Exception("boom")):
                result = enrich_alert(alert)
        assert "echoes" not in result
```

- [ ] **Step 2: Run tests**

Run: `source venv/bin/activate && pytest shit_tests/notifications/test_alert_engine.py -v`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add shit_tests/notifications/test_alert_engine.py
git commit -m "test: add tests for enrich_alert unified enrichment"
```

---

## Task 5: Final verification and CHANGELOG

- [ ] **Step 1: Run full test suite**

Run: `source venv/bin/activate && pytest -x -q`

Expected: All tests pass (except the pre-existing test_notifications failure).

- [ ] **Step 2: Update CHANGELOG.md**

Add under `## [Unreleased]`:

```markdown
### Changed
- **Alert Quality (Play 4)** — Unified alert enrichment across both dispatch paths
  - Calibrated confidence displayed in all Telegram alerts
  - Historical Echoes (similar posts + win rate) included in alerts
  - Ensemble agreement level already rendered when present
  - Ticker blocklist expanded: GOLD, STEEL, COAL, and 12 other false positives blocked
  - New `enrich_alert()` function ensures both cron and event paths produce identical alerts
```

- [ ] **Step 3: Commit and push**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for Play 4 alert quality improvements"
```
