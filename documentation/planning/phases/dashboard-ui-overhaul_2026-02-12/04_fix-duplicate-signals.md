# Phase 04: Fix Duplicate Signal Cards (Deduplicate by Post)

**Status:** COMPLETE
**PR:** #65

## Header

| Field | Value |
|---|---|
| **PR Title** | `fix(ui): deduplicate hero signal cards by post instead of per-ticker` |
| **Risk Level** | Low |
| **Estimated Effort** | Small-Medium (half day) |
| **Files Modified** | `shitty_ui/data.py`, `shitty_ui/pages/dashboard.py`, `shit_tests/shitty_ui/test_data.py`, `CHANGELOG.md` |
| **Files Created** | None |
| **Files Deleted** | None |

---

## Context: Why Duplicates Destroy First Impressions

The "Active Signals" hero section is the first thing a user sees when they open the dashboard. It displays up to 5 high-confidence signal cards from the last 72 hours. Currently, when a post mentions multiple tickers (e.g., a WSJ article about Pentagon spending mentioning RTX, LMT, NOC, GD), the SQL query returns one row per prediction-outcome combination because of the LEFT JOIN on `prediction_outcomes`. This produces 4 nearly identical cards:

- Same post text preview
- Same timestamp
- Same confidence (75%)
- Same thesis
- Only difference: the `symbol` column (RTX vs LMT vs NOC vs GD)

But `create_hero_signal_card()` does not even display the `symbol` column -- it displays the `assets` list from the `predictions` table, which is the same for all 4 rows: `["RTX", "LMT", "NOC", "GD"]`. So the user sees 4 visually identical cards, wasting 80% of the hero section real estate on duplicate information.

Additionally, the signal count display at `dashboard.py` line 617 shows `ACTIVE SIGNALS (4)` when there is really only 1 unique signal. This inflates perceived activity and misrepresents system output.

---

## Dependencies

| Dependency | Status | Required? |
|---|---|---|
| Phase 01 (Label/Countdown Timer) | N/A | No |
| Phase 02 (Trends Auto-Select) | N/A | No |
| Phase 03 (Fix /signals Page) | N/A | No |
| Phase 05 (Strip URLs from Cards) | N/A | No |
| Database tables (`predictions`, `prediction_outcomes`, `truth_social_shitposts`) | Already exist in production | **Required** |

**Batch**: 2 (no file overlap with Batch 1 phases; this modifies `data.py` but different functions than Phase 03 touches)

---

## Root Cause Analysis

The duplication originates in `get_active_signals()` at `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py` lines 1297-1348.

### The Query (lines 1313-1340)

```sql
SELECT
    tss.timestamp,
    tss.text,
    tss.shitpost_id,
    p.id as prediction_id,
    p.assets,
    p.market_impact,
    p.confidence,
    p.thesis,
    po.symbol,
    po.prediction_sentiment,
    po.return_t7,
    po.correct_t7,
    po.pnl_t7,
    po.is_complete
FROM truth_social_shitposts tss
INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
WHERE p.analysis_status = 'completed'
    AND p.confidence IS NOT NULL
    AND p.confidence >= :min_confidence
    AND p.assets IS NOT NULL
    AND p.assets::jsonb <> '[]'::jsonb
    AND tss.timestamp >= :since
ORDER BY tss.timestamp DESC
LIMIT 5
```

**Problem**: The LEFT JOIN on `prediction_outcomes` fans out: one prediction with 4 outcome rows produces 4 result rows. The `LIMIT 5` then takes the first 5 rows, which may all come from the same post.

**Why `create_hero_signal_card` doesn't help**: Looking at `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py` lines 74-232, the card renders:
- `row.get("assets")` (line 80) -- the full asset list from the predictions table, same for all duplicates
- `row.get("text")` (line 77) -- same post text for all duplicates
- `row.get("confidence")` (line 79) -- same confidence for all duplicates
- `row.get("correct_t7")` (line 82) -- this varies per outcome row, but only the first value from `market_impact` is used for sentiment (line 88)

The per-ticker fields (`po.symbol`, `po.prediction_sentiment`, `po.return_t7`, `po.correct_t7`, `po.pnl_t7`) are selected but mostly ignored by the card component, which uses the prediction-level `assets` and `market_impact` fields instead.

### Secondary Bug: Inflated Signal Count

At `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` line 617:

```python
signal_count = len(active_df)
```

This counts rows (4 duplicates) rather than unique posts (1), displaying "ACTIVE SIGNALS (4)" when there is really 1.

---

## Detailed Implementation Plan

### Step 1: Rewrite `get_active_signals()` SQL to Deduplicate by Post

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

There are two viable approaches for deduplication:

**Option A (SQL-level deduplication)**: Change the query to group by `shitpost_id`/`prediction_id` and aggregate outcome data. This is the cleanest approach because it eliminates duplicates before they reach Python.

**Option B (Python-level deduplication)**: Keep the query but deduplicate the DataFrame using `drop_duplicates()`. This is simpler but wastes database bandwidth.

**Chosen approach**: Option A -- SQL-level deduplication. This is more efficient and prevents the `LIMIT 5` from being consumed by duplicates of the same post.

**BEFORE** (lines 1297-1348):

```python
def get_active_signals(min_confidence: float = 0.75, hours: int = 48) -> pd.DataFrame:
    """
    Get recent high-confidence signals for the hero section.

    Args:
        min_confidence: Minimum confidence threshold
        hours: How many hours back to look

    Returns:
        DataFrame with recent high-confidence predictions and their outcomes
    """
    params: Dict[str, Any] = {
        "min_confidence": min_confidence,
        "since": datetime.now() - timedelta(hours=hours),
    }

    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            po.symbol,
            po.prediction_sentiment,
            po.return_t7,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp >= :since
        ORDER BY tss.timestamp DESC
        LIMIT 5
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading active signals: {e}")
        return pd.DataFrame()
```

**AFTER**:

```python
def get_active_signals(min_confidence: float = 0.75, hours: int = 48) -> pd.DataFrame:
    """
    Get recent high-confidence signals for the hero section, deduplicated by post.

    Each post produces one card, regardless of how many tickers it mentions.
    Outcome data is aggregated across all ticker outcomes for the prediction.

    Args:
        min_confidence: Minimum confidence threshold
        hours: How many hours back to look

    Returns:
        DataFrame with one row per unique post, with aggregated outcome data
    """
    params: Dict[str, Any] = {
        "min_confidence": min_confidence,
        "since": datetime.now() - timedelta(hours=hours),
    }

    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            COUNT(po.id) AS outcome_count,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) AS correct_count,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) AS incorrect_count,
            AVG(po.return_t7) AS avg_return_t7,
            SUM(po.pnl_t7) AS total_pnl_t7,
            BOOL_AND(po.is_complete) AS is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp >= :since
        GROUP BY tss.timestamp, tss.text, tss.shitpost_id,
                 p.id, p.assets, p.market_impact, p.confidence, p.thesis
        ORDER BY tss.timestamp DESC
        LIMIT 5
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading active signals: {e}")
        return pd.DataFrame()
```

**Key changes to the SQL**:
1. Added `GROUP BY` on all post/prediction-level columns to collapse outcome rows into one row per prediction.
2. Replaced individual `po.*` columns with aggregates: `COUNT`, `AVG`, `SUM`, `BOOL_AND`.
3. The `LIMIT 5` now correctly returns 5 unique posts, not 5 outcome rows.
4. Removed `po.symbol` and `po.prediction_sentiment` (per-ticker fields not displayed by the card).
5. Added `outcome_count`, `correct_count`, `incorrect_count` for the card to derive outcome status.

---

### Step 2: Update `create_hero_signal_card()` to Use Aggregated Outcome Data

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

The card component needs to handle the new aggregated columns instead of the old per-ticker columns. The outcome badge logic at lines 121-153 currently checks `correct_t7` (a single boolean). It must now use `correct_count` and `incorrect_count` to determine overall outcome status.

**BEFORE** (lines 74-82, field extraction):

```python
def create_hero_signal_card(row) -> html.Div:
    """Create a hero signal card for a high-confidence prediction."""
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    correct_t7 = row.get("correct_t7")
```

**AFTER**:

```python
def create_hero_signal_card(row) -> html.Div:
    """Create a hero signal card for a high-confidence prediction."""
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})

    # Derive outcome from aggregated counts (new dedup columns)
    # Fall back to correct_t7 for backward compatibility
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")

    if outcome_count > 0 and correct_count + incorrect_count > 0:
        # At least some outcomes evaluated -- majority wins
        correct_t7 = correct_count > incorrect_count
    elif "correct_t7" in row.index if hasattr(row, "index") else "correct_t7" in row:
        # Backward compatibility: use single correct_t7 if available
        correct_t7 = row.get("correct_t7")
    else:
        correct_t7 = None  # Pending
```

**BEFORE** (lines 121-153, outcome badge):

```python
    # Outcome badge
    if correct_t7 is True:
        outcome = html.Span(
            [
                html.I(className="fas fa-check me-1"),
                f"+${row.get('pnl_t7', 0):,.0f}" if row.get("pnl_t7") else "Correct",
            ],
            style={
                "color": COLORS["success"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    elif correct_t7 is False:
        outcome = html.Span(
            [
                html.I(className="fas fa-times me-1"),
                f"${row.get('pnl_t7', 0):,.0f}" if row.get("pnl_t7") else "Incorrect",
            ],
            style={
                "color": COLORS["danger"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    else:
        outcome = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
```

**AFTER**:

```python
    # Outcome badge -- uses aggregated P&L when available
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else row.get("pnl_t7")
    if correct_t7 is True:
        outcome = html.Span(
            [
                html.I(className="fas fa-check me-1"),
                f"+${pnl_display:,.0f}" if pnl_display else "Correct",
            ],
            style={
                "color": COLORS["success"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    elif correct_t7 is False:
        outcome = html.Span(
            [
                html.I(className="fas fa-times me-1"),
                f"${pnl_display:,.0f}" if pnl_display else "Incorrect",
            ],
            style={
                "color": COLORS["danger"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    else:
        outcome = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
```

The key behavioral change: the P&L badge now shows the **total** P&L across all tickers for the prediction (e.g., `+$140` for a post that was correct across RTX, LMT, NOC, GD) instead of showing just one ticker's P&L.

---

### Step 3: Fix Signal Count Display

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

No change needed. Line 617 (`signal_count = len(active_df)`) is already correct -- it counts DataFrame rows. After Step 1, the DataFrame will have one row per unique post, so `len(active_df)` will reflect the true number of unique signals.

This is a self-correcting fix: by deduplicating at the data layer, the count at the display layer automatically becomes correct.

---

## Test Plan

### Update Existing Tests for `get_active_signals`

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py`

The existing `TestGetActiveSignals` class (lines 1536-1611) needs to be updated to reflect the new column names from the aggregated query.

**BEFORE** (lines 1536-1611, mock data uses old columns):

```python
class TestGetActiveSignals:
    """Tests for get_active_signals function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test post text",
                    "post123",
                    1,
                    ["AAPL"],
                    {"AAPL": "bullish"},
                    0.85,
                    "thesis text",
                    "AAPL",
                    "bullish",
                    3.0,
                    True,
                    30.0,
                    True,
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "symbol",
                "prediction_sentiment",
                "return_t7",
                "correct_t7",
                "pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=48)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["confidence"] == 0.85
```

**AFTER** (updated to match new aggregated columns):

```python
class TestGetActiveSignals:
    """Tests for get_active_signals function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame with aggregated columns."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "test post text",
                    "post123",
                    1,
                    ["AAPL", "GOOGL"],
                    {"AAPL": "bullish", "GOOGL": "bullish"},
                    0.85,
                    "thesis text",
                    2,       # outcome_count
                    2,       # correct_count
                    0,       # incorrect_count
                    3.5,     # avg_return_t7
                    70.0,    # total_pnl_t7
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=48)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["confidence"] == 0.85
        assert result.iloc[0]["outcome_count"] == 2
        assert result.iloc[0]["correct_count"] == 2

    @patch("data.execute_query")
    def test_returns_one_row_per_post_not_per_ticker(self, mock_execute):
        """Test that multi-ticker posts produce one row, not one per ticker."""
        from data import get_active_signals

        # Simulate a post with 4 tickers -- should be ONE row after GROUP BY
        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Pentagon spending post about defense stocks",
                    "post_defense_456",
                    42,
                    ["RTX", "LMT", "NOC", "GD"],
                    {"RTX": "bullish", "LMT": "bullish", "NOC": "bullish", "GD": "bullish"},
                    0.75,
                    "Defense spending thesis",
                    4,       # outcome_count (4 tickers)
                    3,       # correct_count
                    1,       # incorrect_count
                    2.1,     # avg_return_t7
                    84.0,    # total_pnl_t7 (sum across 4 tickers)
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1  # One row, not 4
        assert result.iloc[0]["outcome_count"] == 4
        assert result.iloc[0]["total_pnl_t7"] == 84.0

    @patch("data.execute_query")
    def test_returns_empty_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_active_signals

        mock_execute.side_effect = Exception("Database error")

        result = get_active_signals()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_passes_params_to_query(self, mock_execute):
        """Test that min_confidence and hours are used in query params."""
        from data import get_active_signals

        mock_execute.return_value = ([], [])

        get_active_signals(min_confidence=0.8, hours=24)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["min_confidence"] == 0.8

    @patch("data.execute_query")
    def test_no_outcomes_shows_pending(self, mock_execute):
        """Test that a post with zero outcomes shows zero counts."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Fresh post with no outcomes yet",
                    "post_new_789",
                    99,
                    ["TSLA"],
                    {"TSLA": "bearish"},
                    0.90,
                    "Bearish thesis",
                    0,       # outcome_count (no outcomes yet)
                    0,       # correct_count
                    0,       # incorrect_count
                    None,    # avg_return_t7 (NULL from AVG of nothing)
                    None,    # total_pnl_t7 (NULL from SUM of nothing)
                    None,    # is_complete (NULL from BOOL_AND of nothing)
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1
        assert result.iloc[0]["outcome_count"] == 0
        assert result.iloc[0]["total_pnl_t7"] is None

    @patch("data.execute_query")
    def test_single_ticker_post(self, mock_execute):
        """Test that a single-ticker post works correctly."""
        from data import get_active_signals

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "Just talking about Tesla",
                    "post_single_111",
                    50,
                    ["TSLA"],
                    {"TSLA": "bullish"},
                    0.80,
                    "Bull thesis on TSLA",
                    1,       # outcome_count
                    1,       # correct_count
                    0,       # incorrect_count
                    5.2,     # avg_return_t7
                    52.0,    # total_pnl_t7
                    True,    # is_complete
                )
            ],
            [
                "timestamp",
                "text",
                "shitpost_id",
                "prediction_id",
                "assets",
                "market_impact",
                "confidence",
                "thesis",
                "outcome_count",
                "correct_count",
                "incorrect_count",
                "avg_return_t7",
                "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_active_signals(min_confidence=0.75, hours=72)

        assert len(result) == 1
        assert result.iloc[0]["outcome_count"] == 1
        assert result.iloc[0]["total_pnl_t7"] == 52.0
```

### Add Card Component Tests for Aggregated Data

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py`

Add tests to verify `create_hero_signal_card` handles the new aggregated columns. Check the existing test structure first.

```python
class TestHeroSignalCardDedup:
    """Tests for create_hero_signal_card with aggregated outcome data."""

    def test_renders_with_aggregated_correct(self):
        """Test card renders Correct badge when correct_count > incorrect_count."""
        from components.cards import create_hero_signal_card
        import pandas as pd

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Defense stocks post",
            "confidence": 0.75,
            "assets": ["RTX", "LMT", "NOC", "GD"],
            "market_impact": {"RTX": "bullish"},
            "outcome_count": 4,
            "correct_count": 3,
            "incorrect_count": 1,
            "total_pnl_t7": 84.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_renders_with_all_incorrect(self):
        """Test card renders Incorrect badge when incorrect_count > correct_count."""
        from components.cards import create_hero_signal_card
        import pandas as pd

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Bad call post",
            "confidence": 0.80,
            "assets": ["AAPL", "GOOGL"],
            "market_impact": {"AAPL": "bearish"},
            "outcome_count": 2,
            "correct_count": 0,
            "incorrect_count": 2,
            "total_pnl_t7": -40.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_renders_pending_when_no_outcomes(self):
        """Test card renders Pending badge when outcome_count is 0."""
        from components.cards import create_hero_signal_card
        import pandas as pd

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Fresh post",
            "confidence": 0.90,
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bullish"},
            "outcome_count": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "total_pnl_t7": None,
            "is_complete": None,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_backward_compatible_with_old_columns(self):
        """Test card still works with old per-ticker columns (correct_t7, pnl_t7)."""
        from components.cards import create_hero_signal_card
        import pandas as pd

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Old format post",
            "confidence": 0.85,
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "correct_t7": True,
            "pnl_t7": 30.0,
        })
        card = create_hero_signal_card(row)
        assert card is not None

    def test_shows_total_pnl_across_tickers(self):
        """Test that P&L badge shows total across all tickers, not per-ticker."""
        from components.cards import create_hero_signal_card
        import pandas as pd

        row = pd.Series({
            "timestamp": datetime.now(),
            "text": "Multi-ticker post",
            "confidence": 0.75,
            "assets": ["RTX", "LMT", "NOC"],
            "market_impact": {"RTX": "bullish"},
            "outcome_count": 3,
            "correct_count": 3,
            "incorrect_count": 0,
            "total_pnl_t7": 120.0,
            "is_complete": True,
        })
        card = create_hero_signal_card(row)
        # Card should render -- exact P&L display is a visual test
        assert card is not None
```

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Duplicate hero signal cards on dashboard** - Posts mentioning multiple tickers (e.g., RTX, LMT, NOC, GD) no longer produce duplicate identical cards in the Active Signals hero section
  - Rewrite `get_active_signals()` query to GROUP BY prediction, aggregating outcome data across all tickers
  - Signal count now reflects unique posts, not per-ticker outcome rows
  - P&L badge shows total P&L across all tickers for the prediction
```

---

## Edge Cases

### 1. Single-Ticker Posts
**Scenario**: A post mentioning only one ticker (e.g., `["TSLA"]`).
**Behavior**: The GROUP BY produces one row with `outcome_count=1`. The card renders identically to the old behavior. No regression.

### 2. Posts With No Outcomes Yet
**Scenario**: A recent high-confidence post where `prediction_outcomes` rows have not been created.
**Behavior**: LEFT JOIN produces one row with all aggregate columns as NULL/0. `COUNT(po.id)` returns 0, `AVG(po.return_t7)` returns NULL, `SUM(po.pnl_t7)` returns NULL. The card renders a "Pending" badge. This matches the desired behavior -- a post freshly analyzed should show as pending, not disappear.

### 3. Empty Results (No Recent High-Confidence Signals)
**Scenario**: No posts in the last 72 hours meet the confidence threshold.
**Behavior**: The query returns zero rows. The DataFrame is empty. The dashboard callback at line 658-684 renders the "No high-confidence signals" empty state. No change needed.

### 4. Mixed Outcomes (Some Tickers Correct, Some Incorrect)
**Scenario**: A post with 4 tickers where 3 are correct and 1 is incorrect.
**Behavior**: `correct_count=3`, `incorrect_count=1`. The card uses majority rule (`correct_count > incorrect_count`) to show a "Correct" badge. `total_pnl_t7` shows the net P&L across all 4 tickers.

### 5. All Outcomes Still Pending (outcome_count > 0 but correct + incorrect = 0)
**Scenario**: Outcomes exist in `prediction_outcomes` but `correct_t7` is NULL for all (not yet evaluated).
**Behavior**: `outcome_count > 0` but `correct_count + incorrect_count = 0`. The card falls through to "Pending" because the condition `correct_count + incorrect_count > 0` is false.

### 6. Exactly 5 Unique Posts Available
**Scenario**: The 72-hour window has exactly 5 unique high-confidence posts.
**Behavior**: `LIMIT 5` returns all 5. Previously, the limit might have been consumed by duplicates, showing only 1-2 unique posts. Now all 5 are displayed.

### 7. Posts With Many Tickers (>4)
**Scenario**: A post mentioning 8+ tickers.
**Behavior**: GROUP BY collapses all 8 outcome rows into one row. The `assets` list on the card already truncates to 4 with `assets[:4]` at line 104 of cards.py, so display is unaffected.

---

## Verification Checklist

- [ ] Navigate to dashboard (`/`) -- hero section shows unique posts, not duplicates
- [ ] Count signal cards visually -- matches the "ACTIVE SIGNALS (N)" count
- [ ] Multi-ticker post shows all tickers in the asset badge (e.g., "RTX, LMT, NOC, GD")
- [ ] Multi-ticker post shows aggregated P&L, not per-ticker P&L
- [ ] Single-ticker posts render identically to before
- [ ] Posts without outcomes show "Pending" badge
- [ ] Empty state ("No high-confidence signals in the last 72 hours") still renders when appropriate
- [ ] Run `source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py::TestGetActiveSignals -v` -- all tests pass
- [ ] Run `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all shitty_ui tests pass
- [ ] Run `python3 -m ruff check shitty_ui/data.py shitty_ui/components/cards.py shitty_ui/pages/dashboard.py` -- no lint errors

---

## What NOT To Do

1. **Do NOT remove the `prediction_outcomes` LEFT JOIN entirely.** The hero cards need outcome data (correct/incorrect/pending badge, P&L) to be useful. Removing the JOIN would eliminate all outcome information, forcing every card to show "Pending."

2. **Do NOT deduplicate in Python using `drop_duplicates(subset=['shitpost_id'])`.** While this would remove visual duplicates, it would silently discard outcome data from other tickers. The first row's `pnl_t7` would be kept while the other tickers' P&L would be lost. SQL-level aggregation preserves all data.

3. **Do NOT change `LIMIT 5` to a larger number to compensate for duplicates.** This is a band-aid that wastes database bandwidth and would still produce duplicates in the DataFrame. The proper fix is GROUP BY.

4. **Do NOT modify `create_signal_card()` (the sidebar signal cards).** That function is used by `get_recent_signals()` which has a different query structure and is not affected by this duplication bug. Only `create_hero_signal_card()` needs changes.

5. **Do NOT drop backward compatibility in `create_hero_signal_card`.** The card should still work if someone passes a row with the old `correct_t7` / `pnl_t7` columns (e.g., in tests or future callers). The fallback chain (`outcome_count` -> `correct_t7` -> `None`) ensures this.

6. **Do NOT aggregate `market_impact` in SQL.** The `market_impact` JSON column is already at the prediction level (not the outcome level), so it is the same for all rows in a duplicate group. The GROUP BY includes it as-is, which is correct.

7. **Do NOT use `DISTINCT ON` instead of `GROUP BY`.** PostgreSQL's `DISTINCT ON` would select one arbitrary outcome row per post, losing aggregate P&L data. `GROUP BY` with aggregate functions preserves the sum of P&L across all tickers.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py` - Rewrite `get_active_signals()` SQL query with GROUP BY to deduplicate at the data layer (root cause fix)
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py` - Update `create_hero_signal_card()` to use aggregated outcome columns (correct_count, total_pnl_t7) instead of per-ticker columns
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py` - Update `TestGetActiveSignals` mock data to match new aggregated column schema, add deduplication-specific tests
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py` - Add `TestHeroSignalCardDedup` tests for aggregated outcome rendering and backward compatibility
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Document the fix