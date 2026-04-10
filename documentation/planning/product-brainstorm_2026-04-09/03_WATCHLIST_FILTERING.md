# 03: Watchlist Filtering

**Feature**: Users specify tickers they care about via Telegram bot commands. Only get alerts when the LLM identifies their watchlist tickers.

**Status**: Planning
**Date**: 2026-04-09
**Estimated Effort**: Small (1 session)

---

## Overview

Currently, subscribers receive alerts for every high-confidence prediction regardless of which tickers are involved. The `alert_preferences` JSON field on `telegram_subscriptions` already has an `assets_of_interest` array, and the `/settings assets AAPL TSLA` command exists. But subscribers have to know this hidden setting exists and use the clunky `/settings` syntax to manage it.

This design adds dedicated `/watchlist` commands to the Telegram bot -- a natural, discoverable interface for managing which tickers generate alerts. Empty watchlist means "send everything" (backward compatible). The filtering logic already exists in `filter_predictions_by_preferences()` via the `assets_of_interest` check; this feature mainly adds the user-facing commands and polishes the data flow.

---

## Motivation: The Alert Noise Problem

### Current State

- The system generates 5-15 completed predictions per day.
- Each prediction typically involves 1-3 tickers.
- A subscriber interested only in TSLA still receives alerts about AAPL, SPY, XLE, etc.
- The only way to filter is `/settings assets AAPL TSLA` which is undiscoverable and hard to manage.
- Subscribers who receive too many irrelevant alerts tend to /stop (churn).

### Desired State

- A subscriber types `/watchlist add TSLA NVDA` and immediately only receives alerts involving those tickers.
- `/watchlist show` displays their current watchlist with human-readable names.
- `/watchlist remove NVDA` adjusts without rebuilding the full list.
- `/watchlist clear` returns to "all tickers" mode.
- Empty watchlist = all tickers (backward compatible default).

### Impact

With 5-15 predictions/day and a typical 2-ticker watchlist, a subscriber would receive 1-3 relevant alerts instead of 5-15. This is a significant noise reduction that should improve retention.

---

## User Commands: Telegram Bot Interface

### Command Overview

| Command | Description | Example |
|---------|-------------|---------|
| `/watchlist` | Show current watchlist | `/watchlist` |
| `/watchlist add <tickers>` | Add tickers to watchlist | `/watchlist add TSLA NVDA AAPL` |
| `/watchlist remove <tickers>` | Remove tickers from watchlist | `/watchlist remove NVDA` |
| `/watchlist clear` | Clear watchlist (receive all alerts) | `/watchlist clear` |
| `/watchlist show` | Same as `/watchlist` (explicit) | `/watchlist show` |

### Response Messages

**`/watchlist` or `/watchlist show` (with watchlist)**:
```
📋 *Your Watchlist*

You're tracking 3 tickers:
• TSLA — Tesla Inc. (Technology)
• NVDA — NVIDIA Corp. (Technology)
• AAPL — Apple Inc. (Technology)

You'll only receive alerts when these tickers appear in a prediction.

_Use /watchlist add TICKER or /watchlist remove TICKER to modify._
```

**`/watchlist` or `/watchlist show` (empty watchlist)**:
```
📋 *Your Watchlist*

Your watchlist is empty — you're receiving alerts for ALL tickers.

To focus on specific tickers, use:
`/watchlist add TSLA NVDA AAPL`
```

**`/watchlist add TSLA NVDA`**:
```
✅ Added to watchlist: TSLA, NVDA

Your watchlist (2 tickers):
• TSLA — Tesla Inc.
• NVDA — NVIDIA Corp.
```

**`/watchlist add TSLA` (already in watchlist)**:
```
ℹ️ TSLA is already on your watchlist.

Your watchlist (3 tickers):
• TSLA — Tesla Inc.
• NVDA — NVIDIA Corp.
• AAPL — Apple Inc.
```

**`/watchlist remove NVDA`**:
```
✅ Removed from watchlist: NVDA

Your watchlist (2 tickers):
• TSLA — Tesla Inc.
• AAPL — Apple Inc.
```

**`/watchlist remove NVDA` (not in watchlist)**:
```
ℹ️ NVDA is not on your watchlist. No changes made.
```

**`/watchlist clear`**:
```
✅ Watchlist cleared. You'll now receive alerts for ALL tickers.
```

**`/watchlist add FAKESYMBOL`**:
```
⚠️ Unknown ticker: FAKESYMBOL (not in our registry)

Added to watchlist: (none)
Skipped: FAKESYMBOL

_We only track tickers that have appeared in past predictions. Try a standard US ticker like AAPL, TSLA, or SPY._
```

---

## Data Model

### Existing Schema

The `telegram_subscriptions.alert_preferences` JSON field already supports the `assets_of_interest` key:

```json
{
    "min_confidence": 0.7,
    "assets_of_interest": [],       // <-- This is the watchlist
    "sentiment_filter": "all",
    "quiet_hours_enabled": false,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}
```

### No Schema Changes Needed

The watchlist is stored in the existing `assets_of_interest` array. No new columns or tables required.

The `/watchlist` commands simply read and write to `alert_preferences.assets_of_interest` using the existing `update_subscription()` function in `notifications/db.py`.

### Example Data Flow

```
User sends: /watchlist add TSLA NVDA

1. parse command → action="add", tickers=["TSLA", "NVDA"]
2. validate tickers against ticker_registry
3. get_subscription(chat_id) → current prefs
4. prefs["assets_of_interest"] = list(set(current + ["TSLA", "NVDA"]))
5. update_subscription(chat_id, alert_preferences=prefs)
6. Format response with ticker names from registry
```

---

## Filter Logic: Notification Worker Changes

### Current Filtering (Already Works)

In `notifications/alert_engine.py`, `filter_predictions_by_preferences()` already checks `assets_of_interest`:

```python
# Check asset filter (empty list = match all)
if assets_of_interest:
    pred_assets = pred.get("assets", [])
    if not isinstance(pred_assets, list):
        pred_assets = []
    if not any(asset in assets_of_interest for asset in pred_assets):
        continue
```

This logic is correct. An empty `assets_of_interest` list means "match all" (backward compatible). A non-empty list requires at least one prediction asset to be in the watchlist.

### No Changes Needed in Alert Engine

The filtering is already implemented. The only gap was the lack of a user-friendly interface to populate `assets_of_interest` -- which is what this feature adds.

### Event Consumer Path

The `NotificationsWorker` in `notifications/event_consumer.py` also calls `filter_predictions_by_preferences()`, so the watchlist filtering applies to both the cron-based and event-driven alert paths.

---

## Ticker Validation

### Validating User Input

When a user types `/watchlist add XYZ`, we need to check if XYZ is a valid ticker that we track. Three options:

1. **Registry check only (Recommended)**: Check `ticker_registry` for active tickers. If the ticker isn't in our registry, it means we've never seen it in a prediction and can't send alerts for it. This is the correct validation -- there's no point adding a ticker to a watchlist if we'll never predict on it.

2. **yfinance check**: Validate against yfinance to confirm it's a real tradeable ticker. Overkill -- we only alert on tickers the LLM extracts, which are already validated.

3. **No validation**: Accept any string. Risk: user adds "LOLWTF" and never gets alerts because the LLM never extracts that ticker. Bad UX.

### Validation Function

```python
def _validate_watchlist_tickers(symbols: list[str]) -> tuple[list[str], list[str]]:
    """Validate tickers against the ticker_registry.

    Args:
        symbols: List of ticker symbols from user input.

    Returns:
        Tuple of (valid_symbols, invalid_symbols).
    """
    from shit.db.sync_session import get_session
    from shit.market_data.models import TickerRegistry

    symbols_upper = [s.strip().upper() for s in symbols if s.strip()]
    if not symbols_upper:
        return [], []

    with get_session() as session:
        known = session.query(TickerRegistry.symbol).filter(
            TickerRegistry.symbol.in_(symbols_upper),
            TickerRegistry.status == "active",
        ).all()
        known_set = {r.symbol for r in known}

    valid = [s for s in symbols_upper if s in known_set]
    invalid = [s for s in symbols_upper if s not in known_set]
    return valid, invalid
```

### Handling Aliases (META/FB)

The `TickerValidator.ALIASES` dict maps old tickers to new ones (FB -> META). Should `/watchlist add FB` auto-remap to META?

**Recommendation**: Yes, apply the same alias remapping. This is a small quality-of-life improvement:

```python
from shit.market_data.ticker_validator import TickerValidator

def _normalize_ticker(symbol: str) -> str:
    """Apply alias remapping to a ticker symbol."""
    symbol = symbol.strip().upper()
    alias = TickerValidator.ALIASES.get(symbol)
    if alias is not None:
        return alias  # None means delisted with no replacement
    return symbol
```

If the alias maps to `None` (delisted with no replacement, e.g., TWTR), tell the user:

```
⚠️ TWTR — Twitter is no longer publicly traded. Cannot add to watchlist.
```

---

## Edge Cases

### Empty Watchlist

An empty `assets_of_interest` list means "receive all alerts." This is the default for new subscribers and the state after `/watchlist clear`. The existing filter logic handles this correctly.

### Invalid Tickers

Tickers not in `ticker_registry` are rejected with a helpful message. The user is told which tickers were added and which were skipped.

### Case Sensitivity

User input is uppercased before processing (`"tsla"` -> `"TSLA"`). All comparisons are case-insensitive.

### Duplicate Additions

`/watchlist add TSLA TSLA` deduplicates before storing. If TSLA is already in the watchlist, it's a no-op for that ticker.

### Sector Filters (Future)

The current design only supports ticker-level filtering. A future enhancement could support sector filters:

```
/watchlist add-sector Technology
/watchlist add-sector Energy
```

This would filter alerts to any ticker in the specified sectors using `ticker_registry.sector`. Not in scope for this feature but the data model supports it (just add a `sectors_of_interest` key to `alert_preferences`).

### Maximum Watchlist Size

Cap the watchlist at 50 tickers to prevent abuse:

```python
MAX_WATCHLIST_SIZE = 50

if len(current_watchlist) + len(new_tickers) > MAX_WATCHLIST_SIZE:
    return f"Watchlist is limited to {MAX_WATCHLIST_SIZE} tickers. You have {len(current_watchlist)}."
```

---

## Implementation Plan

### Step 1: Add `handle_watchlist_command()` to Telegram Bot

**File**: `notifications/telegram_bot.py`

```python
def handle_watchlist_command(chat_id: str, args: str = "") -> str:
    """Handle /watchlist command — view/modify ticker watchlist.

    Supports:
        /watchlist              — Show current watchlist
        /watchlist show         — Same as above
        /watchlist add TSLA     — Add tickers
        /watchlist remove TSLA  — Remove tickers
        /watchlist clear        — Clear watchlist (receive all alerts)
    """
    sub = get_subscription(chat_id)
    if not sub:
        return "\\u2753 You're not subscribed. Send /start first."

    prefs = sub.get("alert_preferences", {})
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}

    current_watchlist = prefs.get("assets_of_interest", [])
    args = args.strip()

    if not args or args.lower() == "show":
        return _format_watchlist_display(current_watchlist)

    parts = args.split()
    action = parts[0].lower()
    tickers_raw = parts[1:] if len(parts) > 1 else []

    if action == "add":
        return _handle_watchlist_add(chat_id, prefs, current_watchlist, tickers_raw)
    elif action == "remove":
        return _handle_watchlist_remove(chat_id, prefs, current_watchlist, tickers_raw)
    elif action == "clear":
        return _handle_watchlist_clear(chat_id, prefs)
    else:
        # If user typed "/watchlist TSLA", treat as "add TSLA"
        return _handle_watchlist_add(chat_id, prefs, current_watchlist, parts)
```

### Step 2: Add Helper Functions

```python
def _format_watchlist_display(watchlist: list[str]) -> str:
    """Format watchlist for display with company names."""
    if not watchlist:
        return """
\\U0001f4cb *Your Watchlist*

Your watchlist is empty — you're receiving alerts for ALL tickers\\.

To focus on specific tickers, use:
`/watchlist add TSLA NVDA AAPL`
"""
    # Look up company names from ticker_registry
    names = _get_ticker_names(watchlist)
    lines = ["\\U0001f4cb *Your Watchlist*\n"]
    lines.append(f"You're tracking {len(watchlist)} tickers:")
    for symbol in sorted(watchlist):
        name = names.get(symbol, "")
        if name:
            lines.append(f"\\u2022 {symbol} — {_escape_md(name)}")
        else:
            lines.append(f"\\u2022 {symbol}")
    lines.append(
        "\nYou'll only receive alerts when these tickers appear in a prediction\\."
    )
    lines.append(
        "\n_Use /watchlist add TICKER or /watchlist remove TICKER to modify\\._"
    )
    return "\n".join(lines)


def _get_ticker_names(symbols: list[str]) -> dict[str, str]:
    """Look up company names for a list of symbols."""
    if not symbols:
        return {}
    from notifications.db import _execute_read, _row_to_dict
    from sqlalchemy import text
    from shit.db.sync_session import get_session

    try:
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT symbol, company_name, sector
                    FROM ticker_registry
                    WHERE symbol = ANY(:symbols)
                """),
                {"symbols": symbols},
            )
            rows = result.fetchall()
            columns = result.keys()
            return {
                row[0]: f"{row[1]}" + (f" ({row[2]})" if row[2] else "")
                for row in rows
                if row[1]
            }
    except Exception:
        return {}
```

### Step 3: Register Command in `process_update()`

**File**: `notifications/telegram_bot.py`, in the `process_update()` function:

```python
# Add to the command routing block:
elif command == "/watchlist":
    response = handle_watchlist_command(chat_id, args)
```

### Step 4: Update Help Text

Add `/watchlist` to the `/help` command response and the `/start` welcome message:

```python
# In handle_help_command():
"/watchlist \\- Manage your ticker watchlist"

# In handle_start_command():
"/watchlist \\- Set which tickers you want alerts for"
```

### Step 5: Add Ticker Validation

Add `_validate_watchlist_tickers()` as shown in the Ticker Validation section above. Wire it into `_handle_watchlist_add()`.

---

## Testing Strategy

### Unit Tests

**File**: `shit_tests/notifications/test_watchlist.py`

1. **`test_watchlist_show_empty`**: Empty `assets_of_interest`, verify response says "receiving alerts for ALL tickers".

2. **`test_watchlist_show_with_tickers`**: `["TSLA", "AAPL"]` in watchlist, verify both listed with company names.

3. **`test_watchlist_add_valid`**: Add "TSLA NVDA" to empty watchlist, verify prefs updated.

4. **`test_watchlist_add_duplicate`**: Add "TSLA" when already in watchlist, verify no-op with info message.

5. **`test_watchlist_add_invalid`**: Add "FAKESYMBOL", verify rejected with helpful message.

6. **`test_watchlist_add_mixed`**: Add "TSLA FAKESYMBOL AAPL", verify TSLA and AAPL added, FAKESYMBOL rejected.

7. **`test_watchlist_add_alias_remapping`**: Add "FB", verify META is added instead.

8. **`test_watchlist_add_delisted`**: Add "TWTR", verify rejection message about private company.

9. **`test_watchlist_remove_existing`**: Remove "TSLA" from ["TSLA", "AAPL"], verify only AAPL remains.

10. **`test_watchlist_remove_nonexistent`**: Remove "NVDA" from ["TSLA", "AAPL"], verify no change with info message.

11. **`test_watchlist_clear`**: Clear watchlist, verify `assets_of_interest` is empty.

12. **`test_watchlist_max_size`**: Try adding 51 tickers, verify rejection at limit.

13. **`test_watchlist_case_insensitive`**: Add "tsla", verify "TSLA" is stored.

14. **`test_filter_with_watchlist`**: Call `filter_predictions_by_preferences` with `assets_of_interest=["TSLA"]` and prediction with `assets=["AAPL", "TSLA"]`. Verify match.

15. **`test_filter_with_watchlist_no_match`**: Same but prediction has `assets=["AAPL", "GOOGL"]`. Verify no match.

16. **`test_filter_empty_watchlist`**: `assets_of_interest=[]`, verify all predictions match.

17. **`test_process_update_watchlist_command`**: Send `/watchlist add TSLA` through `process_update()`, verify correct handler is called.

### Existing Test Compatibility

The `conftest.py` in `shit_tests/notifications/` has `mock_sync_session` (autouse), so new test files automatically get mocked DB sessions. No special setup needed.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `notifications/telegram_bot.py` | Modify | Add `handle_watchlist_command` and helpers; register in `process_update`; update help text |
| `notifications/db.py` | No change | Existing `get_subscription` / `update_subscription` work as-is |
| `notifications/alert_engine.py` | No change | Existing `filter_predictions_by_preferences` already handles `assets_of_interest` |
| `shit_tests/notifications/test_watchlist.py` | Create | All unit tests |

---

## Open Questions

1. **Ticker suggestions**: When a user adds an invalid ticker, should we suggest similar valid tickers? (e.g., "Did you mean TSLA?" for "TSL"). Nice to have but adds complexity. Deferred.

2. **Watchlist limits**: 50 tickers is the proposed cap. Is this enough? Most retail traders watch 5-20 tickers. 50 is generous.

3. **Sector-level filtering**: Should we support `/watchlist add-sector Technology`? This would send alerts for any ticker in the Technology sector. Useful but adds complexity. Deferred -- can be a follow-up feature using the `sectors_of_interest` key.

4. **Notification on watchlist match context**: When an alert fires because of a watchlist match, should the alert say "This alert matched your watchlist ticker: TSLA"? This adds helpful context but increases message length. Could be a v2 enhancement.

5. **Backward compatibility with /settings assets**: The existing `/settings assets AAPL TSLA` command also writes to `assets_of_interest`. Should it continue to work alongside `/watchlist`? Yes -- both commands modify the same field. The `/settings assets` command becomes a power-user alternative. No code change needed.

6. **Inline keyboard buttons**: Telegram supports inline keyboards (buttons under messages). Should `/watchlist show` include "Remove" buttons next to each ticker for easier management? Nice UX but adds complexity. Deferred.
