# Phase 03: Smart Default View & Copy Cleanup

**Status:** ✅ COMPLETE
**Started:** 2026-03-04
**Completed:** 2026-03-04

**PR Title:** fix: smart screener timeframes, professional copy, remove dead MarketMovement model
**Risk Level:** Medium (query logic change affects production dashboard data)
**Effort:** Medium (~3-4 hours)
**Files Modified:** 8
**Files Created:** 0
**Files Deleted:** 0 (tests are modified, not deleted)

---

## Context

Three problems undermine the dashboard's credibility:

1. **Structurally empty 7D screener.** The `get_asset_screener_data()` query filters `prediction_date >= 7_days_ago AND correct_t7 IS NOT NULL`. This is logically impossible -- a prediction made 5 days ago cannot have a T+7 outcome yet. The screener shows zero assets for the 7D period, every time.

2. **Self-deprecating copy.** KPI subtitles say things like "coin flip is 50%" and "Monopoly money, for now." Insight cards say "The suspense is killing us" and "Maybe we should just flip a coin." The screener empty state says "The market hasn't had time to prove us wrong." This tone undermines a system that is actually producing real results.

3. **Dead `MarketMovement` model.** This was superseded by `PredictionOutcome` in `shit/market_data/models.py`. It still lives in `shitvault/shitpost_models.py` with a relationship on `Prediction`, importing in `sync_session.py`, and tests. No runtime pipeline code instantiates it.

---

## Dependencies

- **Depends on:** None (independent of other phases)
- **Unlocks:** None
- **Parallel-safe with:** All other phases, provided no other phase modifies `shitty_ui/data/asset_queries.py`, `shitty_ui/brand_copy.py`, `shitty_ui/data/insight_queries.py`, `shitty_ui/components/screener.py`, `shitvault/shitpost_models.py`, `shit/db/sync_session.py`, or `shit_tests/shitvault/test_shitpost_models.py`.

---

## Detailed Implementation Plan

### Change 1: Fix 7D Screener Query Logic

#### Problem Analysis

In `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/asset_queries.py`, the function `get_asset_screener_data()` (line 18) builds a date filter on line 37-38:

```python
if days is not None:
    date_filter = "AND po.prediction_date >= :start_date"
    params["start_date"] = (datetime.now() - timedelta(days=days)).date()
```

This filter is applied alongside `WHERE po.correct_t7 IS NOT NULL` (line 53). For `days=7`, this means: "predictions made in the last 7 days that already have T+7 outcomes." That is structurally impossible -- it takes at least 7 trading days (~10 calendar days) for `correct_t7` to be populated.

The same issue affects `get_dashboard_kpis()` (line 178 of `performance_queries.py`) and `get_dashboard_kpis_with_fallback()` (line 241), which use the same pattern. When the 7D period returns `total_signals == 0`, the fallback kicks in silently, showing "All-time" data with a small note -- but the user selected "7D" and doesn't realize they're seeing all-time numbers.

#### Solution: Adaptive Timeframe Based on Period

Instead of always using `correct_t7` / `return_t7` / `pnl_t7`, the screener and KPIs should use the timeframe that makes sense for the selected period:

| Period | Timeframe columns | Date window logic |
|--------|-------------------|-------------------|
| 7D | `correct_t1`, `return_t1`, `pnl_t1` | `prediction_date >= 7 days ago` |
| 30D | `correct_t3`, `return_t3`, `pnl_t3` | `prediction_date >= 30 days ago` |
| 90D | `correct_t7`, `return_t7`, `pnl_t7` | `prediction_date >= 90 days ago` |
| All | `correct_t7`, `return_t7`, `pnl_t7` | No date filter |

This way, the 7D view shows predictions from the last week using next-day outcomes (which mature fast enough to populate), while longer windows use deeper timeframes.

#### Step 1a: Add timeframe mapping helper

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/base.py`

Add the following helper as a shared utility (both `asset_queries.py` and `performance_queries.py` need it):

```python
def _timeframe_for_period(days: int | None) -> str:
    """Return the outcome timeframe suffix appropriate for the given period.

    Shorter periods use faster-maturing outcomes to avoid structurally
    empty results (e.g., 7D period can't show T+7 outcomes).

    Args:
        days: Number of days in the selected period (None = all time).

    Returns:
        Suffix string: "t1", "t3", or "t7".
    """
    if days is not None and days <= 7:
        return "t1"
    elif days is not None and days <= 30:
        return "t3"
    return "t7"
```

#### Step 1b: Update `get_asset_screener_data()`

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/asset_queries.py`

Replace the entire function body of `get_asset_screener_data()` (lines 18-89) with:

```python
@ttl_cache(ttl_seconds=300)
def get_asset_screener_data(days: int = None) -> pd.DataFrame:
    """Get combined asset screener data for the dashboard table.

    Joins per-asset accuracy metrics with the latest prediction sentiment
    for each asset, plus average confidence. Uses adaptive timeframe
    columns based on the selected period to avoid structurally empty results.

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        DataFrame with columns: symbol, total_predictions, correct,
        incorrect, avg_return, total_pnl, accuracy, latest_sentiment,
        avg_confidence, timeframe. Sorted by total_predictions descending.
    """
    tf = _timeframe_for_period(days)

    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        WITH asset_metrics AS (
            SELECT
                po.symbol,
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN po.correct_{tf} = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_{tf} = false THEN 1 END) as incorrect,
                ROUND(AVG(CASE WHEN po.return_{tf} IS NOT NULL
                    THEN po.return_{tf} END)::numeric, 2) as avg_return,
                ROUND(SUM(CASE WHEN po.pnl_{tf} IS NOT NULL
                    THEN po.pnl_{tf} ELSE 0 END)::numeric, 2) as total_pnl,
                ROUND(AVG(po.prediction_confidence)::numeric, 2) as avg_confidence
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {{date_filter}}
            GROUP BY po.symbol
            HAVING COUNT(*) >= 2
        ),
        latest_sentiment AS (
            SELECT DISTINCT ON (po.symbol)
                po.symbol,
                po.prediction_sentiment
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {{date_filter}}
            ORDER BY po.symbol, po.prediction_date DESC
        )
        SELECT
            am.symbol,
            am.total_predictions,
            am.correct,
            am.incorrect,
            am.avg_return,
            am.total_pnl,
            am.avg_confidence,
            ls.prediction_sentiment as latest_sentiment
        FROM asset_metrics am
        LEFT JOIN latest_sentiment ls ON am.symbol = ls.symbol
        ORDER BY am.total_predictions DESC
    """.format(date_filter=date_filter))

    try:
        rows, columns = _base.execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
            df["timeframe"] = tf
        return df
    except Exception as e:
        logger.error(f"Error loading asset screener data: {e}")
        return pd.DataFrame()
```

**CRITICAL implementation note:** The f-string uses `{tf}` for column name interpolation (which is safe because `tf` is always one of the hardcoded strings "t1", "t3", "t7" from our helper -- never user input). The `{date_filter}` placeholder uses `.format()` (double braces `{{date_filter}}` in the f-string become `{date_filter}` after f-string processing, then `.format()` fills it). This two-stage interpolation is necessary because `text()` handles `:start_date` parameter binding, while column names cannot be parameterized.

**Alternative cleaner approach** -- use single `.format()` instead of f-string + `.format()`:

```python
    query_template = """
        WITH asset_metrics AS (
            SELECT
                po.symbol,
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN po.correct_{tf} = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_{tf} = false THEN 1 END) as incorrect,
                ROUND(AVG(CASE WHEN po.return_{tf} IS NOT NULL
                    THEN po.return_{tf} END)::numeric, 2) as avg_return,
                ROUND(SUM(CASE WHEN po.pnl_{tf} IS NOT NULL
                    THEN po.pnl_{tf} ELSE 0 END)::numeric, 2) as total_pnl,
                ROUND(AVG(po.prediction_confidence)::numeric, 2) as avg_confidence
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {date_filter}
            GROUP BY po.symbol
            HAVING COUNT(*) >= 2
        ),
        latest_sentiment AS (
            SELECT DISTINCT ON (po.symbol)
                po.symbol,
                po.prediction_sentiment
            FROM prediction_outcomes po
            WHERE po.correct_{tf} IS NOT NULL
            {date_filter}
            ORDER BY po.symbol, po.prediction_date DESC
        )
        SELECT
            am.symbol,
            am.total_predictions,
            am.correct,
            am.incorrect,
            am.avg_return,
            am.total_pnl,
            am.avg_confidence,
            ls.prediction_sentiment as latest_sentiment
        FROM asset_metrics am
        LEFT JOIN latest_sentiment ls ON am.symbol = ls.symbol
        ORDER BY am.total_predictions DESC
    """
    query = text(query_template.format(tf=tf, date_filter=date_filter))
```

**Use this cleaner approach.** It avoids the f-string + `.format()` double-brace confusion.

#### Step 1c: Update `get_dashboard_kpis()`

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/performance_queries.py`

Import `_timeframe_for_period` from `data.base` (already added in Step 1a).

Then replace `get_dashboard_kpis()` (lines 178-238) with an adaptive version:

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_dashboard_kpis(days: int = None) -> Dict[str, Any]:
    """Get the four key metrics for the main dashboard KPI cards.

    Returns only evaluated predictions (where the appropriate timeframe
    outcome is not NULL). Uses adaptive timeframe: T+1 for 7D, T+3 for
    30D, T+7 for 90D and all-time.

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        Dict with keys:
            total_signals: int - count of evaluated prediction-outcome rows
            accuracy_pct: float - percentage correct at chosen timeframe
            avg_return: float - mean return at chosen timeframe (percentage)
            total_pnl: float - sum of P&L at chosen timeframe (dollar amount)
            timeframe: str - which timeframe was used ("t1", "t3", or "t7")
    """
    tf = _timeframe_for_period(days)

    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query_template = """
        SELECT
            COUNT(*) as total_signals,
            COUNT(CASE WHEN correct_{tf} = true THEN 1 END) as correct_count,
            AVG(return_{tf}) as avg_return,
            SUM(CASE WHEN pnl_{tf} IS NOT NULL THEN pnl_{tf} ELSE 0 END) as total_pnl
        FROM prediction_outcomes
        WHERE correct_{tf} IS NOT NULL
        {date_filter}
    """
    query = text(query_template.format(tf=tf, date_filter=date_filter))

    try:
        rows, columns = _base.execute_query(query, params)
        if rows and rows[0]:
            row = rows[0]
            total = row[0] or 0
            correct = row[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0.0

            return {
                "total_signals": total,
                "accuracy_pct": round(accuracy, 1),
                "avg_return_t7": round(float(row[2]), 2) if row[2] else 0.0,
                "total_pnl": round(float(row[3]), 2) if row[3] else 0.0,
                "timeframe": tf,
            }
    except Exception as e:
        logger.error(f"Error loading dashboard KPIs: {e}")

    return {
        "total_signals": 0,
        "accuracy_pct": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl": 0.0,
        "timeframe": tf,
    }
```

**Note:** We keep the key name `avg_return_t7` for backward compatibility (the callback in `content.py` line 130 references `kpis['avg_return_t7']`). The actual timeframe used is communicated via the new `timeframe` key.

#### Step 1d: Update `get_dashboard_kpis_with_fallback()` to improve transparency

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/performance_queries.py`

Replace the function at lines 241-265 with:

```python
def get_dashboard_kpis_with_fallback(days: int | None = 90) -> dict:
    """Get dashboard KPIs with automatic fallback to all-time data.

    When the selected time period has no evaluated predictions (total_signals == 0),
    falls back to all-time data and marks the result so the UI can display a note.

    Args:
        days: Number of days to filter. None = all time.

    Returns:
        Dict with KPI values plus:
            is_fallback: bool - True if showing all-time data instead of requested period
            fallback_label: str - Display label like "Showing all-time data" (empty if not fallback)
            timeframe_label: str - Human-readable label for the active timeframe (e.g., "1-day", "7-day")
    """
    kpis = get_dashboard_kpis(days=days)
    tf = kpis.get("timeframe", "t7")

    tf_labels = {"t1": "1-day", "t3": "3-day", "t7": "7-day"}
    kpis["timeframe_label"] = tf_labels.get(tf, "7-day")

    # If period has evaluated signals, return as-is
    if kpis["total_signals"] > 0 or days is None:
        kpis["is_fallback"] = False
        kpis["fallback_label"] = ""
        return kpis

    # Fall back to all-time
    kpis = get_dashboard_kpis(days=None)
    tf = kpis.get("timeframe", "t7")
    kpis["timeframe_label"] = tf_labels.get(tf, "7-day")
    kpis["is_fallback"] = True
    kpis["fallback_label"] = "Showing all-time data"
    return kpis
```

#### Step 1e: Update KPI subtitle to reflect active timeframe

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/content.py`

On line 92, the fallback note is built:
```python
fallback_note = kpis["fallback_label"] if kpis["is_fallback"] else ""
```

After that line (~line 92), add a timeframe label extraction:
```python
tf_label = kpis.get("timeframe_label", "7-day")
```

Then update the three timeframe-dependent `create_metric_card()` calls to use `tf_label` via COPY format templates (see Step 2a for the template definitions in brand_copy.py):

On the accuracy card, change:
```python
COPY["kpi_accuracy_subtitle"],
```
to:
```python
COPY["kpi_accuracy_subtitle"].format(tf_label=tf_label),
```

On the avg return card, change:
```python
COPY["kpi_avg_return_subtitle"],
```
to:
```python
COPY["kpi_avg_return_subtitle"].format(tf_label=tf_label),
```

On the P&L card, change:
```python
COPY["kpi_pnl_subtitle"],
```
to:
```python
COPY["kpi_pnl_subtitle"].format(tf_label=tf_label),
```

The Total Signals card subtitle remains as-is (no timeframe reference):
```python
COPY["kpi_total_signals_subtitle"],
```

#### Step 1f: Update screener column header to reflect timeframe

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/screener.py`

The column header on line 270 says `"7d Return"`. This should be dynamic based on the timeframe the data was computed with.

Add a `timeframe` parameter to `build_screener_table()`. Change the function signature (line 197) from:

```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
```

to:

```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
    timeframe_label: str = "7d",
) -> html.Div:
```

Then on line 270, change:
```python
_sort_header("7d Return", "avg_return", "right"),
```
to:
```python
_sort_header(f"{timeframe_label} Return", "avg_return", "right"),
```

Update the caller in `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/content.py` at line 78. After constructing `screener_df`, compute the timeframe label:

```python
            # Determine display label for timeframe column
            tf_map = {"t1": "1d", "t3": "3d", "t7": "7d"}
            screener_tf = "7d"
            if not screener_df.empty and "timeframe" in screener_df.columns:
                screener_tf = tf_map.get(screener_df["timeframe"].iloc[0], "7d")

            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
                timeframe_label=screener_tf,
            )
```

---

### Change 2: Replace Self-Deprecating Copy

#### Step 2a: Update brand copy

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/brand_copy.py`

Replace the following lines (keeping all other COPY entries unchanged):

**Line 24** -- `kpi_total_signals_subtitle`:
```python
# BEFORE (line 24):
"kpi_total_signals_subtitle": "predictions we actually checked",
# AFTER:
"kpi_total_signals_subtitle": "evaluated prediction outcomes",
```

**Line 26** -- `kpi_accuracy_subtitle`:
```python
# BEFORE (line 26):
"kpi_accuracy_subtitle": "correct after 7 days (coin flip is 50%)",
# AFTER:
"kpi_accuracy_subtitle": "{tf_label} prediction accuracy",
```

**Line 28** -- `kpi_avg_return_subtitle`:
```python
# BEFORE (line 28):
"kpi_avg_return_subtitle": "mean return per signal (not great, not terrible)",
# AFTER:
"kpi_avg_return_subtitle": "mean {tf_label} return per signal",
```

**Line 30** -- `kpi_pnl_subtitle`:
```python
# BEFORE (line 30):
"kpi_pnl_subtitle": "simulated $1k trades (Monopoly money, for now)",
# AFTER:
"kpi_pnl_subtitle": "simulated $1K per trade ({tf_label})",
```

**Line 42** -- `empty_feed_period`:
```python
# BEFORE (line 42):
"empty_feed_period": "No predictions for this period. The money printer is paused.",
# AFTER:
"empty_feed_period": "No predictions in this period. Try a wider time range.",
```

**Line 43** -- `empty_posts`:
```python
# BEFORE (line 43):
"empty_posts": "No posts to show. Even shitposters sleep sometimes.",
# AFTER:
"empty_posts": "No posts to display. Waiting for new activity.",
```

**Line 44** -- `empty_predictions_table`:
```python
# BEFORE (line 44):
"empty_predictions_table": "No predictions match these filters. We're not THAT prolific.",
# AFTER:
"empty_predictions_table": "No predictions match these filters. Adjust your criteria.",
```

**Line 51** -- `insight_empty`:
```python
# BEFORE (line 51):
"insight_empty": "Nothing interesting to report. Check back in 5 minutes.",
# AFTER:
"insight_empty": "No insights available for this period. Check back soon.",
```

**Lines 54-59** -- chart empty states:
```python
# BEFORE (lines 54-59):
"chart_empty_accuracy": "Not enough data to chart accuracy yet",
"chart_empty_accuracy_hint": "Predictions need 7+ trading days to mature. Patience, money isn't made overnight.",
"chart_empty_confidence": "No accuracy data for this period",
"chart_empty_confidence_hint": "Takes 7+ days per prediction. We'll get there.",
"chart_empty_asset": "No asset performance data yet",
"chart_empty_asset_hint": "Asset accuracy appears after the market proves us wrong (or makes us rich)",
# AFTER:
"chart_empty_accuracy": "Not enough data to chart accuracy",
"chart_empty_accuracy_hint": "Predictions need time to mature. Try a wider period or check back later.",
"chart_empty_confidence": "No accuracy data for this period",
"chart_empty_confidence_hint": "Not enough evaluated predictions. Try a wider time range.",
"chart_empty_asset": "No asset performance data yet",
"chart_empty_asset_hint": "Asset-level accuracy requires evaluated prediction outcomes.",
```

**Lines 62-63** -- asset page:
```python
# BEFORE (lines 62-63):
"asset_no_predictions": "No predictions found for {symbol}. We kept our mouth shut for once.",
"asset_no_related": "No related assets. This one's a loner.",
# AFTER:
"asset_no_predictions": "No predictions found for {symbol}.",
"asset_no_related": "No co-occurring assets found.",
```

**Line 64** -- asset no price:
```python
# BEFORE (line 64):
"asset_no_price": "Price unavailable (the market is keeping secrets)",
# AFTER:
"asset_no_price": "Price data unavailable",
```

**Keep these entries unchanged** (they have appropriate tone):
- `app_subtitle` (line 14) -- brand identity, fine
- `footer_disclaimer` (lines 15-20) -- intentionally irreverent, serves a legal purpose
- `footer_source_link` (line 21) -- fine
- `analytics_header` (line 32) -- "Show Me The Money" is a section header, fine
- `latest_posts_subtitle` (line 38) -- has personality but is informative

#### Step 2b: Update insight query copy

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/insight_queries.py`

**Lines 79, 85** -- latest_call insight body text:
```python
# BEFORE (line 79):
                    body = "Cha-ching." if return_t7 > 2 else "Not bad."
# AFTER:
                    body = f"Predicted correctly with {ret_str} return." if return_t7 > 2 else f"Called it. {ret_str} return."

# BEFORE (line 85):
                    body = "Ouch." if return_t7 < -2 else "Close, but no cigar."
# AFTER:
                    body = f"Missed by a wide margin." if return_t7 < -2 else f"Close to the threshold."
```

**Line 137** -- best_worst insight body:
```python
# BEFORE (line 137):
            body = "Can't win 'em all."
# AFTER:
            body = "Range of outcomes across the period."
```

**Lines 174, 177, 180** -- system_pulse insight body:
```python
# BEFORE (lines 174, 177, 180):
                body = "Not bad for a shitpost-powered AI."
                ...
                body = f"Coin flip is 50%. We're {'barely beating' if accuracy > 50 else 'losing to'} random."
                ...
                body = "Maybe we should just flip a coin."
# AFTER:
            if accuracy > 55:
                body = f"Outperforming random baseline by {accuracy - 50:.0f} percentage points."
                ins_sentiment = "positive"
            elif accuracy > 45:
                body = f"Near the 50% baseline. {'Slightly above' if accuracy > 50 else 'Slightly below'} random."
                ins_sentiment = "neutral"
            else:
                body = f"Below 50% baseline. Model underperforming in this period."
                ins_sentiment = "negative"
```

**Lines 234-237** -- hot_asset insight body:
```python
# BEFORE (lines 234-237):
            body = (
                "Trump can't stop talking about it."
                if count > 10
                else "Keeps showing up."
            )
# AFTER:
            body = (
                f"Most frequently referenced asset with {count} total mentions."
                if count > 10
                else f"Recurring asset in recent analysis."
            )
```

**Lines 286-287** -- hot_signal awaiting body:
```python
# BEFORE (line 286-287):
                headline = f"High-confidence call: {sentiment.upper()} on {symbol} ({conf_pct}). Awaiting results."
                body = "The suspense is killing us."
# AFTER:
                headline = f"High-confidence call: {sentiment.upper()} on {symbol} ({conf_pct}). Awaiting results."
                body = "Outcome pending -- check back after maturation."
```

**Lines 291** -- hot_signal correct body:
```python
# BEFORE (line 291):
                body = "Even a broken AI is right twice a day."
# AFTER:
                body = f"High-confidence signal validated."
```

**Lines 296** -- hot_signal incorrect body:
```python
# BEFORE (line 296):
                body = "Confidence \!= competence."
# AFTER:
                body = "High confidence did not translate to accuracy here."
```

#### Step 2c: Update screener empty state

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/screener.py`

Replace lines 223-226:
```python
# BEFORE (lines 223-226):
                    html.Span(
                        "No asset data yet. The market hasn't had time "
                        "to prove us wrong.",
                        style={
# AFTER:
                    html.Span(
                        "No asset data for this period. Try a wider time range "
                        "or check back after predictions mature.",
                        style={
```

---

### Change 3: Remove Dead MarketMovement Model

#### Step 3a: Remove MarketMovement class from models

**File:** `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_models.py`

1. **Delete lines 173-199** (the entire `MarketMovement` class):
```python
class MarketMovement(Base, IDMixin, TimestampMixin):
    """Model for tracking actual market movements after shitpost predictions."""
    # ... entire class through line 199
```

2. **Delete line 162** (the relationship on `Prediction`):
```python
# BEFORE (line 162):
    market_movements = relationship("MarketMovement", back_populates="prediction")
# AFTER:
    # (line deleted entirely)
```

3. **Delete lines 327-329** (the `market_movement_to_dict` function):
```python
# BEFORE (lines 327-329):
def market_movement_to_dict(movement: MarketMovement) -> Dict[str, Any]:
    """Convert MarketMovement to dictionary."""
    return model_to_dict(movement)
# AFTER:
# (lines deleted entirely)
```

#### Step 3b: Remove MarketMovement from sync_session.py import

**File:** `/Users/chris/Projects/shitpost-alpha/shit/db/sync_session.py`

On line 75, remove `MarketMovement` from the import:

```python
# BEFORE (lines 72-79):
    from shitvault.shitpost_models import (
        TruthSocialShitpost,
        Prediction,
        MarketMovement,
        Subscriber,
        LLMFeedback,
        TelegramSubscription,
    )
# AFTER:
    from shitvault.shitpost_models import (
        TruthSocialShitpost,
        Prediction,
        Subscriber,
        LLMFeedback,
        TelegramSubscription,
    )
```

**Note:** The `market_movements` table already exists in the database. Removing the model from Python does NOT drop the table. The table will remain in the database but will no longer be managed by SQLAlchemy. This is intentional -- dropping the table should be a separate database migration step if desired.

#### Step 3c: Update tests

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitvault/test_shitpost_models.py`

1. **Remove `MarketMovement` from the import** (line 13):
```python
# BEFORE (lines 10-19):
from shitvault.shitpost_models import (
    TruthSocialShitpost,
    Prediction,
    MarketMovement,
    Subscriber,
    LLMFeedback,
    shitpost_to_dict,
    prediction_to_dict,
    market_movement_to_dict
)
# AFTER:
from shitvault.shitpost_models import (
    TruthSocialShitpost,
    Prediction,
    Subscriber,
    LLMFeedback,
    shitpost_to_dict,
    prediction_to_dict,
)
```

2. **Delete the entire `TestMarketMovement` class** (lines 343-399):
```python
class TestMarketMovement:
    """Test cases for MarketMovement model."""
    # ... all methods through line 399
```

3. **Delete `test_market_movement_to_dict`** from `TestUtilityFunctions` (lines 592-607):
```python
    def test_market_movement_to_dict(self):
        """Test converting MarketMovement to dictionary."""
        # ... through line 607
```

4. **Delete `test_prediction_has_market_movements_relationship`** from `TestModelRelationships` (lines 625-629):
```python
    def test_prediction_has_market_movements_relationship(self):
        """Test Prediction has market_movements relationship."""
        mapper = inspect(Prediction)
        relationships = mapper.relationships
        assert 'market_movements' in relationships.keys()
```

5. **Delete `test_market_movement_has_prediction_relationship`** from `TestModelRelationships` (lines 631-635):
```python
    def test_market_movement_has_prediction_relationship(self):
        """Test MarketMovement has prediction relationship."""
        mapper = inspect(MarketMovement)
        relationships = mapper.relationships
        assert 'prediction' in relationships.keys()
```

6. **Delete `test_market_movement_inherits_mixins`** from `TestModelInheritance` (lines 659-665):
```python
    def test_market_movement_inherits_mixins(self):
        """Test MarketMovement inherits from Base, IDMixin, TimestampMixin."""
        assert issubclass(MarketMovement, Base)
        mapper = inspect(MarketMovement)
        assert 'id' in mapper.columns.keys()
        assert 'created_at' in mapper.columns.keys()
        assert 'updated_at' in mapper.columns.keys()
```

---

## Test Plan

### New Tests

Add the following tests to `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data_screener.py`:

```python
class TestTimeframeForPeriod:
    """Tests for _timeframe_for_period helper."""

    def test_7d_returns_t1(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(7) == "t1"

    def test_30d_returns_t3(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(30) == "t3"

    def test_90d_returns_t7(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(90) == "t7"

    def test_none_returns_t7(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(None) == "t7"

    def test_1d_returns_t1(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(1) == "t1"

    def test_14d_returns_t3(self):
        from data.asset_queries import _timeframe_for_period
        assert _timeframe_for_period(14) == "t3"
```

Also add to `TestGetAssetScreenerData`:

```python
    @patch("data.base.execute_query")
    def test_7d_uses_t1_columns(self, mock_query):
        mock_query.return_value = ([], [])
        get_asset_screener_data(days=7)
        query_text = str(mock_query.call_args[0][0])
        assert "correct_t1" in query_text
        assert "return_t1" in query_text
        assert "pnl_t1" in query_text

    @patch("data.base.execute_query")
    def test_30d_uses_t3_columns(self, mock_query):
        mock_query.return_value = ([], [])
        get_asset_screener_data(days=30)
        query_text = str(mock_query.call_args[0][0])
        assert "correct_t3" in query_text
        assert "return_t3" in query_text

    @patch("data.base.execute_query")
    def test_alltime_uses_t7_columns(self, mock_query):
        mock_query.return_value = ([], [])
        get_asset_screener_data(days=None)
        query_text = str(mock_query.call_args[0][0])
        assert "correct_t7" in query_text

    @patch("data.base.execute_query")
    def test_result_includes_timeframe_column(self, mock_query):
        mock_query.return_value = (
            [("XLE", 10, 6, 4, 1.5, 300.0, 0.70, "bullish")],
            ["symbol", "total_predictions", "correct", "incorrect",
             "avg_return", "total_pnl", "avg_confidence", "latest_sentiment"],
        )
        df = get_asset_screener_data(days=7)
        assert "timeframe" in df.columns
        assert df.iloc[0]["timeframe"] == "t1"
```

### Existing Tests to Modify

1. **`shit_tests/shitty_ui/test_data_screener.py`** -- existing tests remain valid since they mock `execute_query` at the bottom and don't assert specific column names in the SQL. The `test_with_days_filter` test passes `days=30` which will now use `t3` columns, but the test only checks that `start_date` is in the params, which is still true.

2. **`shit_tests/shitvault/test_shitpost_models.py`** -- tests for MarketMovement are deleted (see Step 3c). No other tests break because MarketMovement was never imported or used elsewhere.

### Manual Verification Steps

1. Run `./venv/bin/python -m pytest shit_tests/shitty_ui/test_data_screener.py -v` -- all pass
2. Run `./venv/bin/python -m pytest shit_tests/shitvault/test_shitpost_models.py -v` -- all pass (minus deleted tests)
3. Run `./venv/bin/python -m pytest -v` -- full suite passes
4. Check locally that the deployed dashboard (or local dev server) shows data for the 7D period selector
5. Verify that KPI cards show a timeframe-aware subtitle (e.g., "1-day prediction accuracy" for 7D)
6. Verify the screener empty state message is professional
7. Verify that `MarketMovement` is no longer importable: `./venv/bin/python -c "from shitvault.shitpost_models import MarketMovement"` should fail with `ImportError`

---

## Documentation Updates

### CLAUDE.md

In the Database Architecture section, the `market_movements` table documentation (the paragraph starting with `**\`market_movements\`**`) should be updated to add a note:

```markdown
**`market_movements`** - Legacy table (model removed, superseded by `prediction_outcomes`)
- Table still exists in the database but is no longer managed by SQLAlchemy models
- Was replaced by `PredictionOutcome` in `shit/market_data/models.py`
```

### shitvault/README.md

1. Remove the `#### MarketMovement` section (line 230-231)
2. Remove `market_movement_to_dict` from the Utility Functions list (line 244)
3. Update the Foreign Key Relationships section (line 397) -- remove the `market_movements.prediction_id` line

### .claude/commands/db-admin.md

1. Line 33: Remove `MarketMovement` from the import example
2. Line 59: Update the table description to say "Legacy (model removed)"
3. Line 73: Add a note that this FK exists in the DB but not in the ORM
4. Line 86: Remove `MarketMovement` from the model file listing
5. Line 313: Keep `market_movements` in the table list (it still exists in the DB)

### .claude/QUICK_REFERENCE.md

Line 87: Update `market_movements` description to "Legacy table (model removed)"

### .claude/PROJECT_CONTEXT.md

Line 89: Update `market_movements` description to "Legacy table (model removed)"

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Screener 7D empty state** -- 7D period now uses T+1 outcomes (T+7 can't mature in 7 days); 30D uses T+3; 90D/All use T+7
- **KPI fallback transparency** -- fallback label now says "Showing all-time data" instead of just "All-time"

### Changed
- **Dashboard copy professionalized** -- replaced self-deprecating KPI subtitles, insight card commentary, and empty state messages with confident, data-focused language
- **KPI subtitles are timeframe-aware** -- subtitle dynamically reflects "1-day", "3-day", or "7-day" based on the active period

### Removed
- **MarketMovement model** -- dead code superseded by PredictionOutcome; removed class, relationship, utility function, and tests (database table preserved)
```

---

## Stress Testing & Edge Cases

### Screener Query Edge Cases

1. **Period has T+1 data but not T+7:** The new adaptive approach handles this -- 7D uses T+1, which matures in 1 trading day (~2 calendar days). Much more likely to have data.

2. **Period has no data at all:** Still shows the empty state (now with improved copy). The `HAVING COUNT(*) >= 2` clause stays, so single-prediction assets are still excluded.

3. **All timeframes are NULL for a prediction:** If `correct_t1` is NULL (prediction too recent even for T+1), that row is excluded by the `WHERE correct_{tf} IS NOT NULL` clause. This is correct behavior.

4. **SQL injection via timeframe:** Impossible. `_timeframe_for_period()` returns only hardcoded strings `"t1"`, `"t3"`, or `"t7"`. No user input reaches the column name interpolation.

5. **Cache invalidation with new timeframe logic:** The `@ttl_cache` is keyed on the `days` argument. Since the timeframe is derived deterministically from `days`, caching still works correctly. A call with `days=7` will always produce `t1` columns.

### KPI Fallback Edge Cases

6. **7D with T+1 data available:** No fallback needed. KPIs show real 1-day data. Subtitle says "1-day prediction accuracy."

7. **7D with no T+1 data:** Falls back to all-time with `fallback_label = "Showing all-time data"` and uses T+7 (since `days=None` maps to `t7`).

### MarketMovement Removal Edge Cases

8. **Database table still exists:** The `market_movements` table remains in Neon PostgreSQL. No migration is needed. The `create_tables()` call in `sync_session.py` no longer includes it, but `create_all()` is additive (it does not drop tables that exist but aren't modeled).

9. **Other code referencing MarketMovement:** Grep confirmed only the files listed are affected. No pipeline code (harvester, analyzer, s3_processor, market_data worker) imports or uses `MarketMovement`.

---

## Verification Checklist

- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/test_data_screener.py -v` -- all pass
- [ ] `./venv/bin/python -m pytest shit_tests/shitvault/test_shitpost_models.py -v` -- all pass
- [ ] `./venv/bin/python -m pytest -v` -- full suite passes
- [ ] `./venv/bin/python -m ruff check .` -- no lint errors
- [ ] `./venv/bin/python -m ruff format --check .` -- formatting clean
- [ ] `./venv/bin/python -c "from shitvault.shitpost_models import MarketMovement"` -- ImportError
- [ ] `./venv/bin/python -c "from shitvault.shitpost_models import Prediction; from sqlalchemy import inspect; print([r for r in inspect(Prediction).relationships.keys()])"` -- `market_movements` not in output
- [ ] Search codebase: `grep -r "MarketMovement" --include="*.py" | grep -v ".claude/worktrees" | grep -v "documentation/"` -- only hits are in documentation, not code
- [ ] CHANGELOG.md updated with entries for all three changes

---

## "What NOT To Do" Section

1. **Do NOT use user-supplied strings for column names.** The `_timeframe_for_period()` helper returns only hardcoded strings. Never pass `days` or any other user input directly into the SQL column name position.

2. **Do NOT change the `avg_return_t7` key name in the KPI dict.** Even though the actual timeframe may be T+1 or T+3, the dict key stays `avg_return_t7` for backward compatibility. The callback in `content.py` references this key. The new `timeframe` key communicates the actual timeframe.

3. **Do NOT drop the `market_movements` table from the database.** This phase only removes the Python model. Table drops require a separate database migration plan with backup verification.

4. **Do NOT remove the `market_movements` table from the table list in `db-admin.md` line 313.** The table still exists in the database -- just mark it as legacy.

5. **Do NOT change the footer disclaimer copy.** The self-deprecating tone in the footer serves a legitimate risk-disclosure purpose and is intentionally irreverent. Only the KPI/insight/screener copy should be professionalized.

6. **Do NOT use f-strings with double braces for SQL templates.** Use plain string `.format()` for SQL templates that need both column interpolation and SQLAlchemy parameter binding. Example: `query_template.format(tf=tf, date_filter=date_filter)` with `text()` wrapping.

7. **Do NOT remove the `HAVING COUNT(*) >= 2` clause from the screener query.** Assets with only 1 prediction produce meaningless accuracy stats. The threshold stays.

8. **Do NOT remove existing tests for other models** (Subscriber, LLMFeedback, etc.) just because MarketMovement was removed. Only MarketMovement-specific tests are deleted.
