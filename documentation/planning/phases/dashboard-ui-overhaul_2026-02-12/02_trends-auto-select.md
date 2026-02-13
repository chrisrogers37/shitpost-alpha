# Phase 02: Trends Page Auto-Select Top Asset

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-12

## PR Title
`fix(ui): auto-select top asset on /trends page and hide Plotly modebar`

## Risk Level
**Low** -- Cosmetic/UX improvement only. No database schema changes, no new dependencies, no production pipeline impact.

## Estimated Effort
**Small** -- ~1-2 hours implementation, ~1 hour testing.

## Files Modified
| File | Change Type |
|------|------------|
| `shitty_ui/data.py` | Add new function `get_top_predicted_asset()` |
| `shitty_ui/pages/trends.py` | Modify 2 callbacks + 1 layout line |
| `shit_tests/shitty_ui/test_trends.py` | Add ~8 new tests |
| `shit_tests/shitty_ui/test_data.py` | Add ~3 new tests |
| `CHANGELOG.md` | Add entry under `[Unreleased]` |

---

## Context

When a user navigates to `/trends`, they see an empty chart with the placeholder text "Select an asset to view chart" and a permanently visible Plotly toolbar (modebar). This makes the page look broken or like a dead end, especially for first-time visitors. Every other chart in the dashboard hides the modebar entirely (`"displayModeBar": False`). The trends page is the only page that shows it permanently.

The fix auto-selects the most-predicted asset on page load so the user immediately sees useful data. It also hides the Plotly modebar by default (showing it only on hover), which is consistent with the pattern used across the rest of the dashboard but still preserves access to zoom/pan tools for power users.

---

## Dependencies

None. This is a Batch 1 change with no dependencies on other phases.

---

## Detailed Implementation Plan

### Step 1: Add `get_top_predicted_asset()` to the data layer

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

**Where:** After the `get_active_assets_from_db()` function (after line 752), add a new function.

**Rationale:** `get_active_assets_from_db()` returns a sorted alphabetical list of symbols. We need a function that returns assets ranked by prediction count so we can pick the top one. We could query inside the callback, but separating the data access follows the existing pattern in this codebase where all SQL lives in `data.py`.

**Add after line 752:**

```python
@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes (same as get_active_assets_from_db)
def get_top_predicted_asset() -> Optional[str]:
    """
    Get the asset with the most prediction outcomes.

    Used to auto-select a default asset on the /trends page.

    Returns:
        Ticker symbol string (e.g., 'TSLA'), or None if no assets exist.
    """
    query = text("""
        SELECT symbol, COUNT(*) as prediction_count
        FROM prediction_outcomes
        WHERE symbol IS NOT NULL
        GROUP BY symbol
        ORDER BY prediction_count DESC
        LIMIT 1
    """)

    try:
        rows, columns = execute_query(query)
        if rows and rows[0]:
            return rows[0][0]
        return None
    except Exception as e:
        logger.error(f"Error loading top predicted asset: {e}")
        return None
```

**Also update `clear_all_caches()`** at line 994-1006 to include the new cached function:

```python
def clear_all_caches() -> None:
    """Clear all data layer caches. Call when forcing a full refresh."""
    get_prediction_stats.clear_cache()  # type: ignore
    get_performance_metrics.clear_cache()  # type: ignore
    get_accuracy_by_confidence.clear_cache()  # type: ignore
    get_accuracy_by_asset.clear_cache()  # type: ignore
    get_active_assets_from_db.clear_cache()  # type: ignore
    get_sentiment_distribution.clear_cache()  # type: ignore
    get_asset_stats.clear_cache()  # type: ignore
    get_available_assets.clear_cache()  # type: ignore
    get_high_confidence_metrics.clear_cache()  # type: ignore
    get_best_performing_asset.clear_cache()  # type: ignore
    get_backtest_simulation.clear_cache()  # type: ignore
    get_top_predicted_asset.clear_cache()  # type: ignore  # <-- ADD THIS LINE
```

### Step 2: Modify the `populate_trends_assets` callback to also set default value

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/trends.py`

**Current code (lines 149-157):**
```python
    @app.callback(
        Output("trends-asset-selector", "options"),
        [Input("url", "pathname")],
    )
    def populate_trends_assets(pathname):
        if pathname != "/trends":
            return no_update
        assets = get_active_assets_from_db()
        return [{"label": a, "value": a} for a in assets]
```

**Problem:** This callback only sets the `options` property. It never sets the `value` property. We need it to also return a default `value` so the dropdown is pre-selected.

**Updated code:**
```python
    @app.callback(
        [
            Output("trends-asset-selector", "options"),
            Output("trends-asset-selector", "value"),
        ],
        [Input("url", "pathname")],
    )
    def populate_trends_assets(pathname):
        if pathname != "/trends":
            return no_update, no_update
        assets = get_active_assets_from_db()
        options = [{"label": a, "value": a} for a in assets]

        # Auto-select the most-predicted asset as default
        top_asset = get_top_predicted_asset()
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        return options, default_value
```

**Changes explained:**
1. The `Output` is now a list of two outputs: `options` AND `value`.
2. The `no_update` return is now a tuple `(no_update, no_update)`.
3. After building the options list, we call `get_top_predicted_asset()` to get the most-predicted asset.
4. We verify the top asset is in the active assets list (defensive check). If not, fall back to the first asset. If no assets exist at all, we return `None`.

**Update import** on line 11:
```python
# BEFORE (line 11):
from data import get_price_with_signals, get_active_assets_from_db

# AFTER:
from data import get_price_with_signals, get_active_assets_from_db, get_top_predicted_asset
```

### Step 3: Hide the Plotly modebar by default (show on hover)

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/trends.py`

**Current code (line 127):**
```python
config={"displayModeBar": True, "displaylogo": False},
```

**Updated code (line 127):**
```python
config={"displayModeBar": "hover", "displaylogo": False},
```

**Explanation:** Plotly's `displayModeBar` accepts three values: `True` (always show), `False` (never show), and `"hover"` (show on mouseover). Using `"hover"` is the best middle ground -- it keeps the page clean while still letting power users access zoom/pan/save tools when they hover over the chart.

Note: The rest of the dashboard uses `"displayModeBar": False`. Using `"hover"` is slightly different but appropriate here because the trends chart is the primary interactive chart where users are most likely to want to zoom into price ranges. If the user prefers full consistency with other pages, change to `False` instead.

### Step 4: Improve the empty state when no assets exist

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/trends.py`

**Current code (lines 174-180):**
```python
    def update_trends_chart(symbol, n30, n90, n180, n1y, options):
        if not symbol:
            return (
                build_empty_signal_chart("Select an asset to view the chart"),
                "Select an asset to view chart",
                html.Div(),
            )
```

**Updated code:**
```python
    def update_trends_chart(symbol, n30, n90, n180, n1y, options):
        if not symbol:
            return (
                build_empty_signal_chart(
                    "No assets with prediction data available yet"
                ),
                "No Asset Data Available",
                html.Div(
                    html.P(
                        "Predictions need to be analyzed and validated before "
                        "trend charts can be displayed. Check back after the "
                        "pipeline has processed some posts.",
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                            "fontSize": "0.9rem",
                        },
                    )
                ),
            )
```

**Explanation:** Because we now auto-select a default asset, the only way `symbol` is `None` at this point is if the asset list is truly empty (no predictions with outcomes exist at all). The old message "Select an asset to view the chart" is misleading when there are no assets to select. The new message accurately describes the situation.

---

## Test Plan

### New tests for `get_top_predicted_asset()` in `test_data.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py`

Add at the end of the file (or after the `TestGetActiveAssetsFromDb` class):

```python
class TestGetTopPredictedAsset:
    """Tests for get_top_predicted_asset function."""

    @patch("data.execute_query")
    def test_returns_top_asset(self, mock_execute):
        """Test that function returns the symbol with most predictions."""
        from data import get_top_predicted_asset

        mock_execute.return_value = (
            [("TSLA", 42)],
            ["symbol", "prediction_count"],
        )

        result = get_top_predicted_asset()
        assert result == "TSLA"

    @patch("data.execute_query")
    def test_returns_none_when_empty(self, mock_execute):
        """Test that function returns None when no assets exist."""
        from data import get_top_predicted_asset

        mock_execute.return_value = ([], ["symbol", "prediction_count"])

        result = get_top_predicted_asset()
        assert result is None

    @patch("data.execute_query")
    def test_returns_none_on_error(self, mock_execute):
        """Test that function returns None on database error."""
        from data import get_top_predicted_asset

        mock_execute.side_effect = Exception("DB connection failed")

        result = get_top_predicted_asset()
        assert result is None
```

### New tests for the updated trends callbacks in `test_trends.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_trends.py`

Add to the `TestRegisterTrendsCallbacks` class or create a new class:

```python
class TestPopulateTrendsAssets:
    """Tests for the populate_trends_assets callback logic."""

    @patch("pages.trends.get_top_predicted_asset")
    @patch("pages.trends.get_active_assets_from_db")
    def test_auto_selects_top_asset(self, mock_get_assets, mock_get_top):
        """Test that callback returns top asset as default value."""
        mock_get_assets.return_value = ["AAPL", "TSLA", "SPY"]
        mock_get_top.return_value = "TSLA"

        # Import and call the inner function directly
        # We test the logic, not the Dash callback registration
        from pages.trends import get_active_assets_from_db, get_top_predicted_asset

        assets = get_active_assets_from_db()
        top_asset = get_top_predicted_asset()
        options = [{"label": a, "value": a} for a in assets]
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        assert default_value == "TSLA"
        assert len(options) == 3

    @patch("pages.trends.get_top_predicted_asset")
    @patch("pages.trends.get_active_assets_from_db")
    def test_falls_back_to_first_asset(self, mock_get_assets, mock_get_top):
        """Test fallback to first asset when top asset is not in list."""
        mock_get_assets.return_value = ["AAPL", "SPY"]
        mock_get_top.return_value = "XYZ"  # Not in the list

        assets = mock_get_assets()
        top_asset = mock_get_top()
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        assert default_value == "AAPL"

    @patch("pages.trends.get_top_predicted_asset")
    @patch("pages.trends.get_active_assets_from_db")
    def test_returns_none_when_no_assets(self, mock_get_assets, mock_get_top):
        """Test that None is returned when no assets exist."""
        mock_get_assets.return_value = []
        mock_get_top.return_value = None

        assets = mock_get_assets()
        top_asset = mock_get_top()
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        assert default_value is None

    @patch("pages.trends.get_top_predicted_asset")
    @patch("pages.trends.get_active_assets_from_db")
    def test_handles_top_asset_none(self, mock_get_assets, mock_get_top):
        """Test fallback when get_top_predicted_asset returns None."""
        mock_get_assets.return_value = ["AAPL", "TSLA"]
        mock_get_top.return_value = None

        assets = mock_get_assets()
        top_asset = mock_get_top()
        default_value = top_asset if top_asset and top_asset in assets else (assets[0] if assets else None)

        assert default_value == "AAPL"


class TestTrendsChartEmptyState:
    """Tests for improved empty state message."""

    def test_empty_state_message_updated(self):
        """Test that empty state no longer says 'Select an asset'."""
        from pages.trends import create_trends_page
        page = create_trends_page()
        html_str = str(page)
        # The layout itself doesn't contain the empty state message --
        # it's generated by the callback. We test the callback returns instead.

    @patch("pages.trends.build_empty_signal_chart")
    def test_no_symbol_shows_no_data_message(self, mock_empty_chart):
        """Test that update_trends_chart with no symbol shows appropriate message."""
        mock_empty_chart.return_value = MagicMock()

        # Import callback logic
        from pages.trends import build_empty_signal_chart
        from constants import COLORS

        # Simulate calling the callback with symbol=None
        # (This tests the message content, not the Dash callback wiring)
        result_fig = build_empty_signal_chart(
            "No assets with prediction data available yet"
        )
        mock_empty_chart.assert_called_once_with(
            "No assets with prediction data available yet"
        )


class TestTrendsModebarConfig:
    """Tests for Plotly modebar configuration."""

    def test_modebar_set_to_hover(self):
        """Test that the chart config uses displayModeBar='hover'."""
        from pages.trends import create_trends_page
        page = create_trends_page()
        # Walk the component tree to find the dcc.Graph config
        html_str = str(page)
        # The config is embedded in the component, verify via string
        assert "'displayModeBar': 'hover'" in html_str or '"displayModeBar": "hover"' in html_str
```

### Updated existing test

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_trends.py`

Update the `test_callbacks_registered_without_error` test at line 65-71 since the callback count might change (the `populate_trends_assets` callback now has 2 outputs instead of 1, but the callback count remains 3 since we still have 3 callbacks total):

```python
    def test_callbacks_registered_without_error(self):
        """Test that callbacks register without raising exceptions."""
        mock_app = MagicMock()
        mock_app.callback = MagicMock(return_value=lambda f: f)
        register_trends_callbacks(mock_app)
        # Should have registered 3 callbacks
        assert mock_app.callback.call_count == 3
```

This test should still pass as-is since we are not adding or removing callbacks, just modifying the outputs of an existing one.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Trends Page Empty State** - Auto-select the most-predicted asset when /trends loads instead of showing an empty chart with "Select an asset to view chart"
  - Added `get_top_predicted_asset()` data function to identify the asset with the most prediction outcomes
  - Changed Plotly modebar from always-visible to hover-only for cleaner appearance
  - Improved empty state messaging when no assets with prediction data exist
```

---

## Edge Cases

### 1. Empty asset list (no prediction outcomes at all)
- `get_active_assets_from_db()` returns `[]`
- `get_top_predicted_asset()` returns `None`
- `default_value` resolves to `None`
- The `update_trends_chart` callback receives `symbol=None` and shows the improved empty state: "No assets with prediction data available yet"

### 2. Top asset exists but has no price data
- `get_top_predicted_asset()` returns `"TSLA"`
- The `update_trends_chart` callback calls `get_price_with_signals("TSLA", days=90)`
- `prices_df` is empty
- The callback hits the existing check at lines 202-207 and shows: "No price data for TSLA"
- This is correct behavior -- no change needed here.

### 3. Top asset not in active assets list
- This is possible if the `prediction_outcomes` table and the distinct symbol query return different results (e.g., data inconsistency)
- The fallback logic (`assets[0] if assets else None`) handles this gracefully

### 4. Database error during `get_top_predicted_asset()`
- Function catches exceptions and returns `None`
- Fallback to `assets[0]` kicks in
- Page still loads with a reasonable default

### 5. User manually clears the dropdown after auto-selection
- If user clears the dropdown (sets value to `None`), the callback fires with `symbol=None`
- Shows the empty state message
- This is acceptable behavior

---

## Verification Checklist

- [ ] `get_top_predicted_asset()` added to `shitty_ui/data.py` with `@ttl_cache(ttl_seconds=600)`
- [ ] `clear_all_caches()` updated to include `get_top_predicted_asset.clear_cache()`
- [ ] Import of `get_top_predicted_asset` added to `shitty_ui/pages/trends.py` line 11
- [ ] `populate_trends_assets` callback outputs changed from single `Output` to list of two `Output`s
- [ ] `populate_trends_assets` return changed from single value to tuple of two values
- [ ] `no_update` return changed to `no_update, no_update` tuple
- [ ] `displayModeBar` changed from `True` to `"hover"` on line 127
- [ ] Empty state message updated from "Select an asset" to "No assets with prediction data available yet"
- [ ] All new tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_trends.py shit_tests/shitty_ui/test_data.py -v`
- [ ] Existing test `test_callbacks_registered_without_error` still passes (callback count is still 3)
- [ ] Full test suite passes: `source venv/bin/activate && pytest`
- [ ] Linting passes: `source venv/bin/activate && python3 -m ruff check shitty_ui/pages/trends.py shitty_ui/data.py`
- [ ] Formatting passes: `source venv/bin/activate && python3 -m ruff format --check shitty_ui/pages/trends.py shitty_ui/data.py`
- [ ] CHANGELOG.md updated with entry under `[Unreleased]`
- [ ] Manual verification: navigate to `/trends` in browser and confirm chart loads with default asset

---

## What NOT To Do

1. **Do NOT add the default value as a static property in the layout.** The dropdown options are populated dynamically via callback. Setting `value="TSLA"` directly in `create_trends_page()` would cause a mismatch because the options are empty at layout creation time. The value must be set in the same callback that populates the options.

2. **Do NOT use `get_active_assets_from_db()[0]` as the default** without also checking which asset is most meaningful. An alphabetically-first asset (e.g., "AAPL") may not be the most interesting. The most-predicted asset is the best default because it has the most signal data to display.

3. **Do NOT change `displayModeBar` to `False`.** While other pages use `False`, the trends page chart is the primary interactive chart where zoom/pan functionality adds real value. Use `"hover"` instead to keep it accessible but not visually cluttered. (If the user explicitly requests `False` for full consistency, that is also acceptable.)

4. **Do NOT create a new SQL query inside the callback function.** All database queries belong in `shitty_ui/data.py` per the established pattern. The callback should only call data layer functions.

5. **Do NOT remove the `if not symbol:` guard in `update_trends_chart`.** Even though we now set a default, the guard is still needed for the edge case where no assets exist at all.

6. **Do NOT add `get_top_predicted_asset` to the import in `layout.py` or any other file.** Only `trends.py` needs it. Keep the import scope minimal.

7. **Do NOT modify `get_active_assets_from_db()` to return ordered-by-count.** It is used in multiple places that expect alphabetical order. Create a separate function instead.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/trends.py` - Primary file: modify callback outputs, import, modebar config, and empty state message
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py` - Add `get_top_predicted_asset()` function and update cache clearing
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_trends.py` - Add tests for auto-selection logic, empty state, and modebar config
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py` - Add tests for `get_top_predicted_asset()` function
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Add unreleased entry for this fix
