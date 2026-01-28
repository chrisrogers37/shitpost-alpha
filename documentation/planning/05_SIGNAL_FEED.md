# Signal Feed Page Specification

## Overview

This document specifies a new `/signals` feed page for the Shitpost Alpha dashboard. The signal feed is a chronological, filterable stream of LLM-generated predictions derived from Trump's Truth Social posts. It displays each prediction as a card with the original tweet text, predicted assets, sentiment direction, confidence score, and validation outcome. The feed polls for new signals every two minutes and provides visual indicators when new signals arrive.

**Estimated Effort**: 2-3 days
**Priority**: P2 (Nice to Have)
**Prerequisites**: Core dashboard (layout.py, data.py) must be functional. The `prediction_outcomes` table must be populated.

---

## Architecture

### File Changes

| File | Action | Description |
|------|--------|-------------|
| `shitty_ui/data.py` | **Modify** | Add four new query functions for the signal feed |
| `shitty_ui/layout.py` | **Modify** | Add signal feed page layout, components, and callbacks |
| `shitty_ui/app.py` | **Modify** | Add multi-page routing support |
| `shit_tests/shitty_ui/test_data.py` | **Modify** | Add tests for new data functions |
| `shit_tests/shitty_ui/test_layout.py` | **Modify** | Add tests for new layout components and callbacks |

### Database Tables Referenced

All three tables are read-only from the dashboard. The dashboard never writes to the database.

```
truth_social_shitposts
  - shitpost_id (TEXT, PK)
  - timestamp (TIMESTAMP)
  - text (TEXT)
  - replies_count (INTEGER)
  - reblogs_count (INTEGER)
  - favourites_count (INTEGER)

predictions
  - id (INTEGER, PK)
  - shitpost_id (TEXT, FK -> truth_social_shitposts.shitpost_id)
  - assets (JSONB)           -- e.g. ["AAPL", "TSLA"]
  - market_impact (JSONB)    -- e.g. {"AAPL": "bullish", "TSLA": "bearish"}
  - confidence (FLOAT)       -- 0.0 to 1.0
  - thesis (TEXT)
  - analysis_status (TEXT)   -- 'completed', 'bypassed', 'pending'
  - analysis_comment (TEXT)

prediction_outcomes
  - id (INTEGER, PK)
  - prediction_id (INTEGER, FK -> predictions.id)
  - symbol (TEXT)            -- e.g. "AAPL"
  - prediction_date (DATE)
  - prediction_sentiment (TEXT)  -- 'bullish', 'bearish', 'neutral'
  - prediction_confidence (FLOAT)
  - price_at_prediction (FLOAT)
  - price_t1 (FLOAT)
  - price_t3 (FLOAT)
  - price_t7 (FLOAT)
  - price_t30 (FLOAT)
  - return_t1 (FLOAT)
  - return_t3 (FLOAT)
  - return_t7 (FLOAT)
  - return_t30 (FLOAT)
  - correct_t1 (BOOLEAN)
  - correct_t3 (BOOLEAN)
  - correct_t7 (BOOLEAN)
  - correct_t30 (BOOLEAN)
  - pnl_t1 (FLOAT)
  - pnl_t3 (FLOAT)
  - pnl_t7 (FLOAT)
  - pnl_t30 (FLOAT)
  - is_complete (BOOLEAN)
```

### Color Palette

The signal feed uses the same palette defined in `layout.py`. Do not define a second copy. Import `COLORS` from `layout.py` wherever needed.

```python
COLORS = {
    "primary": "#1e293b",      # Slate 800 - main background
    "secondary": "#334155",    # Slate 700 - cards
    "accent": "#3b82f6",       # Blue 500 - highlights
    "success": "#10b981",      # Emerald 500 - bullish / correct
    "danger": "#ef4444",       # Red 500 - bearish / incorrect
    "warning": "#f59e0b",      # Amber 500 - pending
    "text": "#f1f5f9",         # Slate 100 - primary text
    "text_muted": "#94a3b8",   # Slate 400 - secondary text
    "border": "#475569",       # Slate 600 - borders
}
```

### Badge Color Mapping

| Badge | Condition | Background Color | Text Color |
|-------|-----------|-----------------|------------|
| **Correct** | `correct_t7 is True` | `COLORS["success"]` (#10b981) | white |
| **Incorrect** | `correct_t7 is False` | `COLORS["danger"]` (#ef4444) | white |
| **Pending** | `correct_t7 is None` | `COLORS["warning"]` (#f59e0b) | dark (#1e293b) |
| **New** | `timestamp` is within last 24 hours | `COLORS["accent"]` (#3b82f6) | white |

A signal card can have both "New" and one of the outcome badges displayed simultaneously (the "New" badge appears to the left of the outcome badge).

---

## Task 1: Data Layer -- New Query Functions

Add all four functions below to `shitty_ui/data.py`. Each function follows the existing pattern: build a `text()` query, call `execute_query()`, return a `pd.DataFrame` or primitive. All functions must include `try/except` blocks that log errors and return safe defaults (empty DataFrame or empty dict).

### 1.1 `get_signal_feed`

This is the primary query for the feed. It joins all three tables and supports pagination via `offset` and `limit`. It also supports filtering by sentiment, minimum confidence, asset symbol, and outcome status.

```python
def get_signal_feed(
    limit: int = 20,
    offset: int = 0,
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load signal feed data with filtering and pagination.

    This is the main query powering the /signals feed page. It returns
    predictions joined with their source posts and validation outcomes,
    ordered by timestamp descending (newest first).

    Args:
        limit: Maximum number of signals to return per page.
        offset: Number of signals to skip (for pagination / load-more).
        sentiment_filter: Filter by sentiment. One of 'bullish', 'bearish',
            or None (no filter). When set, only predictions whose
            market_impact JSONB contains this sentiment value are returned.
        confidence_min: Minimum confidence score (0.0 to 1.0 inclusive).
        confidence_max: Maximum confidence score (0.0 to 1.0 inclusive).
        asset_filter: Filter by a specific asset ticker symbol (e.g. 'AAPL').
            When set, only predictions where prediction_outcomes.symbol matches
            are returned.
        outcome_filter: Filter by outcome status. One of 'correct', 'incorrect',
            'pending', or None (no filter).

    Returns:
        DataFrame with columns: timestamp, text, shitpost_id, prediction_id,
        assets, market_impact, confidence, thesis, analysis_status, symbol,
        prediction_sentiment, prediction_confidence, return_t1, return_t3,
        return_t7, correct_t1, correct_t3, correct_t7, pnl_t7, is_complete
    """
    # Base query -- always join all three tables. We use INNER JOIN on
    # predictions because we only want posts that have completed analysis,
    # and LEFT JOIN on prediction_outcomes because outcomes may not exist yet.
    base_query = """
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            po.symbol,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.pnl_t7,
            po.is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
    """

    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Dynamic filters -- append WHERE clauses as needed.
    # ------------------------------------------------------------------

    # Sentiment filter: check if any value in the market_impact JSONB
    # matches the requested sentiment string.
    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        base_query += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    # Confidence range filter
    if confidence_min is not None:
        base_query += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        base_query += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    # Asset filter: match on prediction_outcomes.symbol
    if asset_filter:
        base_query += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    # Outcome filter
    if outcome_filter == "correct":
        base_query += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        base_query += " AND po.correct_t7 = false"
    elif outcome_filter == "pending":
        base_query += " AND po.correct_t7 IS NULL"

    # Order and paginate
    base_query += " ORDER BY tss.timestamp DESC LIMIT :limit OFFSET :offset"

    try:
        rows, columns = execute_query(text(base_query), params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading signal feed: {e}")
        return pd.DataFrame()
```

### 1.2 `get_signal_feed_count`

Returns the total number of signals that match the current filters. The feed UI uses this to show "Showing X of Y signals" and to decide whether the "Load More" button should appear.

```python
def get_signal_feed_count(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> int:
    """
    Count total signals matching current filters.

    Uses the same filter logic as get_signal_feed but returns only the count.
    This avoids fetching all rows just to count them.

    Args:
        Same filter parameters as get_signal_feed (see that docstring).

    Returns:
        Integer count of matching signals. Returns 0 on error.
    """
    base_query = """
        SELECT COUNT(*) as total
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
    """

    params: Dict[str, Any] = {}

    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        base_query += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    if confidence_min is not None:
        base_query += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        base_query += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    if asset_filter:
        base_query += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    if outcome_filter == "correct":
        base_query += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        base_query += " AND po.correct_t7 = false"
    elif outcome_filter == "pending":
        base_query += " AND po.correct_t7 IS NULL"

    try:
        rows, columns = execute_query(text(base_query), params)
        if rows and rows[0]:
            return rows[0][0] or 0
        return 0
    except Exception as e:
        print(f"Error counting signal feed: {e}")
        return 0
```

### 1.3 `get_new_signals_since`

Counts how many new signals have appeared since a given timestamp. The UI stores the timestamp of the most recent signal the user has seen and passes it here to show the "X new signals" badge at the top of the feed.

```python
def get_new_signals_since(since_timestamp: str) -> int:
    """
    Count new completed predictions since a given ISO timestamp.

    Used by the 'new signals since you last checked' indicator at the top
    of the feed. The frontend stores the timestamp of the last signal the
    user saw (in a dcc.Store) and passes it here on each poll cycle.

    Args:
        since_timestamp: ISO-format timestamp string, e.g. '2025-01-15T10:30:00'.
            Signals with tss.timestamp strictly greater than this value are counted.

    Returns:
        Integer count of new signals. Returns 0 on error or if since_timestamp
        is None/empty.
    """
    if not since_timestamp:
        return 0

    query = text("""
        SELECT COUNT(*) as new_count
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            AND tss.timestamp > :since_timestamp
    """)

    try:
        rows, columns = execute_query(query, {"since_timestamp": since_timestamp})
        if rows and rows[0]:
            return rows[0][0] or 0
        return 0
    except Exception as e:
        print(f"Error counting new signals: {e}")
        return 0
```

### 1.4 `get_signal_feed_csv`

Returns the full filtered result set (no pagination) formatted for CSV export. Column names are human-readable, and values are pre-formatted as strings.

```python
def get_signal_feed_csv(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get full signal feed data formatted for CSV export.

    Same filtering as get_signal_feed but without pagination (returns all
    matching rows) and with human-readable column names. This function is
    called when the user clicks the "Export CSV" button.

    Args:
        Same filter parameters as get_signal_feed (see that docstring).

    Returns:
        DataFrame with columns: Timestamp, Post Text, Asset, Sentiment,
        Confidence, Thesis, Return (1d), Return (3d), Return (7d),
        Outcome, P&L (7d). Returns empty DataFrame on error.
    """
    # Reuse get_signal_feed with a large limit and zero offset
    df = get_signal_feed(
        limit=10000,
        offset=0,
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )

    if df.empty:
        return pd.DataFrame()

    # Build the export DataFrame with human-readable columns
    export_df = pd.DataFrame()
    export_df["Timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    export_df["Post Text"] = df["text"]
    export_df["Asset"] = df["symbol"].fillna(
        df["assets"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else str(x)
        )
    )
    export_df["Sentiment"] = df["prediction_sentiment"].fillna("N/A")
    export_df["Confidence"] = df["confidence"].apply(
        lambda x: f"{x:.0%}" if pd.notna(x) else "N/A"
    )
    export_df["Thesis"] = df["thesis"].fillna("")
    export_df["Return (1d)"] = df["return_t1"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Return (3d)"] = df["return_t3"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Return (7d)"] = df["return_t7"].apply(
        lambda x: f"{x:+.2f}%" if pd.notna(x) else ""
    )
    export_df["Outcome"] = df["correct_t7"].apply(
        lambda x: "Correct" if x is True else ("Incorrect" if x is False else "Pending")
    )
    export_df["P&L (7d)"] = df["pnl_t7"].apply(
        lambda x: f"${x:,.2f}" if pd.notna(x) else ""
    )

    return export_df
```

---

## Task 2: Layout Components

All layout code goes in `shitty_ui/layout.py`. Add the functions below after the existing `create_signal_card` function.

### 2.1 Signal Feed Page Layout

This function builds the entire `/signals` page. It is called from the multi-page routing callback (see Task 4).

```python
def create_signal_feed_page():
    """
    Create the full /signals feed page layout.

    Structure:
    - Header with "New signals" indicator
    - Filter bar (sentiment, confidence, asset, outcome)
    - Signal card feed (scrollable list)
    - "Load More" button at the bottom
    - Export CSV button

    Returns:
        html.Div containing the entire signal feed page.
    """
    return html.Div([
        # ---------------------------------------------------------------
        # Page header with new-signals banner
        # ---------------------------------------------------------------
        html.Div([
            html.H2([
                html.I(className="fas fa-rss me-2"),
                "Signal Feed",
            ], style={"margin": 0, "fontWeight": "bold"}),
            html.P(
                "Live predictions from Trump's Truth Social posts",
                style={"color": COLORS["text_muted"], "margin": 0, "fontSize": "0.9rem"}
            ),
        ], style={"marginBottom": "20px"}),

        # New-signals banner (hidden by default, shown via callback)
        html.Div(
            id="new-signals-banner",
            children=[],
            style={"display": "none"},
        ),

        # ---------------------------------------------------------------
        # Polling interval -- fires every 2 minutes
        # ---------------------------------------------------------------
        dcc.Interval(
            id="signal-feed-poll-interval",
            interval=2 * 60 * 1000,  # 2 minutes in milliseconds
            n_intervals=0,
        ),

        # ---------------------------------------------------------------
        # Client-side stores
        # ---------------------------------------------------------------
        # Stores the ISO timestamp of the most recent signal the user has seen.
        # Initialized on first load; updated when user clicks "Show new signals".
        dcc.Store(id="signal-feed-last-seen-ts", data=None),

        # Stores the current page offset for load-more pagination.
        dcc.Store(id="signal-feed-offset", data=0),

        # Stores CSV data for download.
        dcc.Download(id="signal-feed-csv-download"),

        # ---------------------------------------------------------------
        # Filter bar
        # ---------------------------------------------------------------
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Sentiment filter
                    dbc.Col([
                        html.Label(
                            "Sentiment",
                            className="small",
                            style={"color": COLORS["text_muted"]},
                        ),
                        dcc.Dropdown(
                            id="signal-feed-sentiment-filter",
                            options=[
                                {"label": "All Sentiments", "value": "all"},
                                {"label": "Bullish", "value": "bullish"},
                                {"label": "Bearish", "value": "bearish"},
                            ],
                            value="all",
                            clearable=False,
                            style={"fontSize": "0.9rem"},
                        ),
                    ], xs=12, sm=6, md=3),

                    # Confidence slider
                    dbc.Col([
                        html.Label(
                            "Confidence Range",
                            className="small",
                            style={"color": COLORS["text_muted"]},
                        ),
                        dcc.RangeSlider(
                            id="signal-feed-confidence-slider",
                            min=0,
                            max=1,
                            step=0.05,
                            value=[0, 1],
                            marks={
                                0: {"label": "0%", "style": {"color": COLORS["text_muted"]}},
                                0.5: {"label": "50%", "style": {"color": COLORS["text_muted"]}},
                                1: {"label": "100%", "style": {"color": COLORS["text_muted"]}},
                            },
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ], xs=12, sm=6, md=3),

                    # Asset filter
                    dbc.Col([
                        html.Label(
                            "Asset",
                            className="small",
                            style={"color": COLORS["text_muted"]},
                        ),
                        dcc.Dropdown(
                            id="signal-feed-asset-filter",
                            options=[],  # Populated by callback
                            placeholder="All Assets",
                            style={"fontSize": "0.9rem"},
                        ),
                    ], xs=12, sm=6, md=3),

                    # Outcome filter
                    dbc.Col([
                        html.Label(
                            "Outcome",
                            className="small",
                            style={"color": COLORS["text_muted"]},
                        ),
                        dcc.Dropdown(
                            id="signal-feed-outcome-filter",
                            options=[
                                {"label": "All Outcomes", "value": "all"},
                                {"label": "Correct", "value": "correct"},
                                {"label": "Incorrect", "value": "incorrect"},
                                {"label": "Pending", "value": "pending"},
                            ],
                            value="all",
                            clearable=False,
                            style={"fontSize": "0.9rem"},
                        ),
                    ], xs=12, sm=6, md=3),
                ], className="g-3"),
            ])
        ], style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "marginBottom": "20px",
        }),

        # ---------------------------------------------------------------
        # Signal count + Export button row
        # ---------------------------------------------------------------
        html.Div([
            html.Span(
                id="signal-feed-count-label",
                children="Loading signals...",
                style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
            ),
            dbc.Button(
                [html.I(className="fas fa-download me-2"), "Export CSV"],
                id="signal-feed-export-btn",
                color="secondary",
                size="sm",
                outline=True,
                style={"float": "right"},
            ),
        ], style={
            "marginBottom": "15px",
            "overflow": "hidden",  # clearfix for float
        }),

        # ---------------------------------------------------------------
        # Signal cards container
        # ---------------------------------------------------------------
        dcc.Loading(
            id="signal-feed-loading",
            type="circle",
            color=COLORS["accent"],
            children=html.Div(
                id="signal-feed-cards-container",
                children=[],
            ),
        ),

        # ---------------------------------------------------------------
        # Load More button
        # ---------------------------------------------------------------
        html.Div(
            id="signal-feed-load-more-container",
            children=[
                dbc.Button(
                    [html.I(className="fas fa-chevron-down me-2"), "Load More Signals"],
                    id="signal-feed-load-more-btn",
                    color="secondary",
                    outline=True,
                    className="w-100 mt-3",
                ),
            ],
        ),

    ], style={"padding": "20px", "maxWidth": "900px", "margin": "0 auto"})
```

### 2.2 Signal Feed Card Component

Each signal in the feed is rendered as a card. This is distinct from the existing `create_signal_card` used on the main dashboard -- it has more detail, badges, and a different layout optimized for a feed view.

```python
def create_feed_signal_card(row) -> html.Div:
    """
    Create a single signal card for the feed.

    This card shows:
    - Timestamp (top-left)
    - Badges: "New" (if < 24 hours), outcome badge (top-right)
    - Truncated tweet text (max 250 chars)
    - Asset tickers
    - Sentiment with directional arrow
    - Confidence bar
    - 7-day return and P&L (if available)

    Args:
        row: A dict-like object (e.g. pandas Series) with keys matching
             the columns returned by get_signal_feed().

    Returns:
        html.Div containing the rendered card.
    """
    from datetime import datetime, timedelta, timezone

    timestamp = row.get("timestamp")
    post_text = row.get("text", "")
    confidence = row.get("confidence", 0) or 0
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    symbol = row.get("symbol")
    prediction_sentiment = row.get("prediction_sentiment")
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
    thesis = row.get("thesis", "")

    # ------------------------------------------------------------------
    # Determine if "New" badge should show (post < 24 hours old)
    # ------------------------------------------------------------------
    is_new = False
    if isinstance(timestamp, datetime):
        # Handle timezone-naive timestamps by assuming UTC
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        is_new = ts > cutoff

    # ------------------------------------------------------------------
    # Determine sentiment direction
    # ------------------------------------------------------------------
    sentiment = "neutral"
    if prediction_sentiment:
        sentiment = prediction_sentiment.lower()
    elif isinstance(market_impact, dict) and market_impact:
        first_val = list(market_impact.values())[0]
        if isinstance(first_val, str):
            sentiment = first_val.lower()

    sentiment_color = (
        COLORS["success"] if sentiment == "bullish"
        else COLORS["danger"] if sentiment == "bearish"
        else COLORS["text_muted"]
    )
    sentiment_icon = (
        "arrow-up" if sentiment == "bullish"
        else "arrow-down" if sentiment == "bearish"
        else "minus"
    )

    # ------------------------------------------------------------------
    # Format asset display
    # ------------------------------------------------------------------
    if symbol:
        asset_display = symbol
    elif isinstance(assets, list):
        asset_display = ", ".join(assets[:3])
        if len(assets) > 3:
            asset_display += f" +{len(assets) - 3}"
    else:
        asset_display = str(assets) if assets else "N/A"

    # ------------------------------------------------------------------
    # Truncate text
    # ------------------------------------------------------------------
    max_text_len = 250
    display_text = post_text[:max_text_len] + "..." if len(post_text) > max_text_len else post_text

    # ------------------------------------------------------------------
    # Build badges
    # ------------------------------------------------------------------
    badges = []

    if is_new:
        badges.append(
            html.Span(
                "New",
                className="badge me-2",
                style={
                    "backgroundColor": COLORS["accent"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    if correct_t7 is True:
        badges.append(
            html.Span(
                "Correct",
                className="badge",
                style={
                    "backgroundColor": COLORS["success"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    elif correct_t7 is False:
        badges.append(
            html.Span(
                "Incorrect",
                className="badge",
                style={
                    "backgroundColor": COLORS["danger"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    else:
        badges.append(
            html.Span(
                "Pending",
                className="badge",
                style={
                    "backgroundColor": COLORS["warning"],
                    "color": COLORS["primary"],
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    # ------------------------------------------------------------------
    # Format timestamp display
    # ------------------------------------------------------------------
    if isinstance(timestamp, datetime):
        ts_display = timestamp.strftime("%b %d, %Y %H:%M")
    else:
        ts_display = str(timestamp)[:16] if timestamp else "Unknown"

    # ------------------------------------------------------------------
    # Confidence bar (visual indicator)
    # ------------------------------------------------------------------
    conf_pct = confidence * 100
    conf_bar_color = (
        COLORS["success"] if confidence >= 0.75
        else COLORS["warning"] if confidence >= 0.6
        else COLORS["danger"]
    )
    confidence_bar = html.Div([
        html.Div(
            style={
                "width": f"{conf_pct}%",
                "height": "4px",
                "backgroundColor": conf_bar_color,
                "borderRadius": "2px",
                "transition": "width 0.3s ease",
            }
        ),
    ], style={
        "width": "60px",
        "height": "4px",
        "backgroundColor": COLORS["border"],
        "borderRadius": "2px",
        "display": "inline-block",
        "verticalAlign": "middle",
        "marginLeft": "6px",
    })

    # ------------------------------------------------------------------
    # Return / P&L display
    # ------------------------------------------------------------------
    metrics_children = []
    if return_t7 is not None:
        ret_color = COLORS["success"] if return_t7 > 0 else COLORS["danger"]
        metrics_children.append(
            html.Span(
                f"7d Return: {return_t7:+.2f}%",
                style={"color": ret_color, "fontSize": "0.8rem", "fontWeight": "bold"},
            )
        )
    if pnl_t7 is not None:
        pnl_color = COLORS["success"] if pnl_t7 > 0 else COLORS["danger"]
        if metrics_children:
            metrics_children.append(
                html.Span(" | ", style={"color": COLORS["border"], "margin": "0 6px"})
            )
        metrics_children.append(
            html.Span(
                f"P&L: ${pnl_t7:,.0f}",
                style={"color": pnl_color, "fontSize": "0.8rem"},
            )
        )

    # ------------------------------------------------------------------
    # Assemble the card
    # ------------------------------------------------------------------
    return html.Div([
        # Row 1: Timestamp + Badges
        html.Div([
            html.Span(
                ts_display,
                style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
            ),
            html.Div(badges, style={"display": "inline-flex", "alignItems": "center"}),
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "8px",
        }),

        # Row 2: Tweet text
        html.P(
            display_text,
            style={
                "fontSize": "0.9rem",
                "margin": "0 0 10px 0",
                "lineHeight": "1.5",
                "color": COLORS["text"],
            },
        ),

        # Row 3: Asset | Sentiment | Confidence
        html.Div([
            # Asset ticker
            html.Span(
                asset_display,
                style={
                    "backgroundColor": COLORS["primary"],
                    "color": COLORS["accent"],
                    "padding": "2px 8px",
                    "borderRadius": "4px",
                    "fontSize": "0.8rem",
                    "fontWeight": "bold",
                    "marginRight": "12px",
                    "border": f"1px solid {COLORS['border']}",
                },
            ),
            # Sentiment
            html.Span([
                html.I(className=f"fas fa-{sentiment_icon} me-1"),
                sentiment.upper(),
            ], style={
                "color": sentiment_color,
                "fontSize": "0.8rem",
                "fontWeight": "bold",
                "marginRight": "12px",
            }),
            # Confidence
            html.Span([
                html.Span(
                    f"{confidence:.0%}",
                    style={
                        "color": COLORS["text_muted"],
                        "fontSize": "0.8rem",
                    },
                ),
                confidence_bar,
            ]),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "flexWrap": "wrap",
            "gap": "4px",
        }),

        # Row 4: Return / P&L metrics (only if we have data)
        html.Div(
            metrics_children,
            style={"marginTop": "8px"},
        ) if metrics_children else None,

        # Row 5: Thesis (collapsed, first ~100 chars)
        html.P(
            thesis[:120] + "..." if thesis and len(thesis) > 120 else thesis,
            style={
                "fontSize": "0.8rem",
                "color": COLORS["text_muted"],
                "margin": "8px 0 0 0",
                "fontStyle": "italic",
                "lineHeight": "1.4",
            },
        ) if thesis else None,

    ], style={
        "padding": "16px",
        "backgroundColor": COLORS["secondary"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "marginBottom": "12px",
        "transition": "border-color 0.2s ease",
    })
```

### 2.3 New-Signals Banner

This banner appears at the top of the feed when polling detects new signals the user has not seen.

```python
def create_new_signals_banner(count: int) -> html.Div:
    """
    Create a banner showing how many new signals have arrived.

    Displayed at the top of the feed when the polling interval detects
    new predictions that were not present on the last user-visible load.

    Args:
        count: Number of new signals detected.

    Returns:
        html.Div with the banner content.
    """
    return html.Div([
        html.Div([
            html.I(className="fas fa-bell me-2"),
            html.Span(
                f"{count} new signal{'s' if count != 1 else ''} since you last checked",
                style={"fontWeight": "bold"},
            ),
        ], style={"display": "inline-flex", "alignItems": "center"}),
        dbc.Button(
            "Show New Signals",
            id="signal-feed-show-new-btn",
            color="primary",
            size="sm",
            className="ms-3",
        ),
    ], style={
        "backgroundColor": "rgba(59, 130, 246, 0.15)",  # accent with alpha
        "border": f"1px solid {COLORS['accent']}",
        "borderRadius": "8px",
        "padding": "12px 16px",
        "marginBottom": "16px",
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
        "color": COLORS["accent"],
    })
```

---

## Task 3: Callbacks

Add all callbacks inside the existing `register_callbacks(app)` function in `layout.py`. Each callback is documented with its trigger, inputs, outputs, and complete implementation.

### 3.1 Main Feed Loader

This callback fires when:
- The page first loads (initial call)
- Any filter value changes
- The polling interval ticks

It replaces the entire card list with fresh data from the database, resets the offset to zero, and updates the signal count label.

```python
@app.callback(
    [
        Output("signal-feed-cards-container", "children"),
        Output("signal-feed-count-label", "children"),
        Output("signal-feed-offset", "data"),
        Output("signal-feed-last-seen-ts", "data"),
        Output("signal-feed-load-more-container", "style"),
    ],
    [
        Input("signal-feed-sentiment-filter", "value"),
        Input("signal-feed-confidence-slider", "value"),
        Input("signal-feed-asset-filter", "value"),
        Input("signal-feed-outcome-filter", "value"),
        Input("signal-feed-poll-interval", "n_intervals"),
    ],
)
def update_signal_feed(sentiment, confidence_range, asset, outcome, n_intervals):
    """
    Load or reload the signal feed with current filter values.

    This callback is the main driver of the feed. It queries the database,
    builds signal cards, and returns them. It also resets pagination offset
    to zero (since filters may have changed) and updates the 'last seen'
    timestamp.

    Args:
        sentiment: 'all', 'bullish', or 'bearish'
        confidence_range: Two-element list [min, max] from the range slider.
        asset: Asset ticker string (e.g. 'AAPL') or None.
        outcome: 'all', 'correct', 'incorrect', or 'pending'.
        n_intervals: Polling tick count (ignored, just triggers refresh).

    Returns:
        Tuple of:
        - cards_children: List of html.Div signal cards
        - count_label: String like "Showing 20 of 142 signals"
        - offset: Reset to PAGE_SIZE (we just loaded the first page)
        - last_seen_ts: ISO timestamp of the newest signal in the result
        - load_more_style: dict -- visible if more signals exist, hidden if not
    """
    from data import get_signal_feed, get_signal_feed_count

    PAGE_SIZE = 20

    # Normalize filter values
    sentiment_val = sentiment if sentiment != "all" else None
    outcome_val = outcome if outcome != "all" else None
    conf_min = confidence_range[0] if confidence_range else None
    conf_max = confidence_range[1] if confidence_range else None

    # Don't filter if full range is selected
    if conf_min == 0 and conf_max == 1:
        conf_min = None
        conf_max = None

    # Fetch first page
    df = get_signal_feed(
        limit=PAGE_SIZE,
        offset=0,
        sentiment_filter=sentiment_val,
        confidence_min=conf_min,
        confidence_max=conf_max,
        asset_filter=asset,
        outcome_filter=outcome_val,
    )

    # Get total count for "Showing X of Y"
    total_count = get_signal_feed_count(
        sentiment_filter=sentiment_val,
        confidence_min=conf_min,
        confidence_max=conf_max,
        asset_filter=asset,
        outcome_filter=outcome_val,
    )

    # Build cards
    if df.empty:
        cards = [
            html.Div([
                html.I(className="fas fa-inbox", style={
                    "fontSize": "2rem", "color": COLORS["text_muted"]
                }),
                html.P(
                    "No signals match your filters.",
                    style={"color": COLORS["text_muted"], "marginTop": "10px"},
                ),
            ], style={"textAlign": "center", "padding": "40px"})
        ]
        count_label = "No signals found"
        last_seen_ts = None
        load_more_style = {"display": "none"}
    else:
        cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
        count_label = f"Showing {len(df)} of {total_count} signals"

        # Store the timestamp of the newest signal for "new signals" tracking
        newest_ts = df["timestamp"].iloc[0]
        if isinstance(newest_ts, datetime):
            last_seen_ts = newest_ts.isoformat()
        else:
            last_seen_ts = str(newest_ts)

        # Show/hide load more button
        load_more_style = (
            {"display": "block"} if total_count > PAGE_SIZE
            else {"display": "none"}
        )

    return cards, count_label, PAGE_SIZE, last_seen_ts, load_more_style
```

### 3.2 Load More Button

Appends the next page of results to the existing cards list.

```python
@app.callback(
    [
        Output("signal-feed-cards-container", "children", allow_duplicate=True),
        Output("signal-feed-offset", "data", allow_duplicate=True),
        Output("signal-feed-count-label", "children", allow_duplicate=True),
        Output("signal-feed-load-more-container", "style", allow_duplicate=True),
    ],
    [Input("signal-feed-load-more-btn", "n_clicks")],
    [
        State("signal-feed-cards-container", "children"),
        State("signal-feed-offset", "data"),
        State("signal-feed-sentiment-filter", "value"),
        State("signal-feed-confidence-slider", "value"),
        State("signal-feed-asset-filter", "value"),
        State("signal-feed-outcome-filter", "value"),
    ],
    prevent_initial_call=True,
)
def load_more_signals(n_clicks, existing_cards, current_offset, sentiment,
                      confidence_range, asset, outcome):
    """
    Append the next page of signal cards to the feed.

    Triggered when the user clicks the 'Load More Signals' button. Fetches
    the next PAGE_SIZE signals starting at current_offset and appends them
    to the existing card list.

    Args:
        n_clicks: Number of times the button has been clicked.
        existing_cards: Current list of card children already in the container.
        current_offset: Current pagination offset (number of rows already loaded).
        sentiment: Current sentiment filter value.
        confidence_range: Current confidence slider value.
        asset: Current asset filter value.
        outcome: Current outcome filter value.

    Returns:
        Tuple of:
        - updated_cards: Existing cards + new cards appended
        - new_offset: Updated offset value
        - count_label: Updated "Showing X of Y" label
        - load_more_style: Show or hide the Load More button
    """
    from data import get_signal_feed, get_signal_feed_count

    if not n_clicks:
        raise PreventUpdate

    PAGE_SIZE = 20

    # Normalize filter values (same logic as main loader)
    sentiment_val = sentiment if sentiment != "all" else None
    outcome_val = outcome if outcome != "all" else None
    conf_min = confidence_range[0] if confidence_range else None
    conf_max = confidence_range[1] if confidence_range else None

    if conf_min == 0 and conf_max == 1:
        conf_min = None
        conf_max = None

    # Fetch next page
    df = get_signal_feed(
        limit=PAGE_SIZE,
        offset=current_offset,
        sentiment_filter=sentiment_val,
        confidence_min=conf_min,
        confidence_max=conf_max,
        asset_filter=asset,
        outcome_filter=outcome_val,
    )

    # Total count
    total_count = get_signal_feed_count(
        sentiment_filter=sentiment_val,
        confidence_min=conf_min,
        confidence_max=conf_max,
        asset_filter=asset,
        outcome_filter=outcome_val,
    )

    if df.empty:
        # No more results -- hide the button, keep existing cards
        return existing_cards, current_offset, f"Showing all {current_offset} signals", {"display": "none"}

    # Build new cards and append
    new_cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
    updated_cards = (existing_cards or []) + new_cards

    new_offset = current_offset + len(df)
    count_label = f"Showing {new_offset} of {total_count} signals"

    # Hide button if we've loaded everything
    load_more_style = (
        {"display": "block"} if new_offset < total_count
        else {"display": "none"}
    )

    return updated_cards, new_offset, count_label, load_more_style
```

### 3.3 New-Signals Polling

This callback runs on the polling interval. It checks whether new signals have arrived since the user's last-seen timestamp and shows/hides the banner accordingly.

```python
@app.callback(
    [
        Output("new-signals-banner", "children"),
        Output("new-signals-banner", "style"),
    ],
    [Input("signal-feed-poll-interval", "n_intervals")],
    [State("signal-feed-last-seen-ts", "data")],
)
def check_for_new_signals(n_intervals, last_seen_ts):
    """
    Poll for new signals and show/hide the 'new signals' banner.

    Runs every 2 minutes (matching the poll interval). Compares the last-seen
    timestamp stored in the browser against the database to count new signals.

    Args:
        n_intervals: Poll tick count.
        last_seen_ts: ISO timestamp of the newest signal the user has seen,
            stored in dcc.Store. None on first load.

    Returns:
        Tuple of:
        - banner_children: The new-signals banner component (or empty list)
        - banner_style: dict with display visible or hidden
    """
    from data import get_new_signals_since

    if not last_seen_ts:
        # First load -- nothing to compare against yet
        return [], {"display": "none"}

    new_count = get_new_signals_since(last_seen_ts)

    if new_count > 0:
        banner = create_new_signals_banner(new_count)
        return [banner], {"display": "block"}
    else:
        return [], {"display": "none"}
```

### 3.4 Show New Signals Button

When the user clicks "Show New Signals" on the banner, this callback triggers a reload of the feed by updating the polling interval's `n_intervals` property (which fires the main feed loader callback).

```python
@app.callback(
    Output("signal-feed-poll-interval", "n_intervals"),
    [Input("signal-feed-show-new-btn", "n_clicks")],
    [State("signal-feed-poll-interval", "n_intervals")],
    prevent_initial_call=True,
)
def trigger_feed_reload_on_show_new(n_clicks, current_intervals):
    """
    Force a feed reload when user clicks 'Show New Signals'.

    Increments the poll interval counter, which triggers the main
    update_signal_feed callback, refreshing the card list with the
    latest data.

    Args:
        n_clicks: Click count on the 'Show New Signals' button.
        current_intervals: Current value of the poll interval counter.

    Returns:
        Incremented interval counter value.
    """
    if not n_clicks:
        raise PreventUpdate
    return (current_intervals or 0) + 1
```

### 3.5 CSV Export

Triggered by clicking the "Export CSV" button. Uses `dcc.Download` to send the CSV file to the browser.

```python
@app.callback(
    Output("signal-feed-csv-download", "data"),
    [Input("signal-feed-export-btn", "n_clicks")],
    [
        State("signal-feed-sentiment-filter", "value"),
        State("signal-feed-confidence-slider", "value"),
        State("signal-feed-asset-filter", "value"),
        State("signal-feed-outcome-filter", "value"),
    ],
    prevent_initial_call=True,
)
def export_signal_feed_csv(n_clicks, sentiment, confidence_range, asset, outcome):
    """
    Export the current filtered signal feed to a CSV file.

    Downloads a CSV containing all signals matching the current filters
    (ignoring pagination). The file is named with the current date.

    Args:
        n_clicks: Click count on the Export button.
        sentiment: Current sentiment filter.
        confidence_range: Current confidence slider range.
        asset: Current asset filter.
        outcome: Current outcome filter.

    Returns:
        dcc.send_data_frame result that triggers a browser download, or
        None if there is no data to export.
    """
    from data import get_signal_feed_csv

    if not n_clicks:
        raise PreventUpdate

    # Normalize filters
    sentiment_val = sentiment if sentiment != "all" else None
    outcome_val = outcome if outcome != "all" else None
    conf_min = confidence_range[0] if confidence_range else None
    conf_max = confidence_range[1] if confidence_range else None

    if conf_min == 0 and conf_max == 1:
        conf_min = None
        conf_max = None

    export_df = get_signal_feed_csv(
        sentiment_filter=sentiment_val,
        confidence_min=conf_min,
        confidence_max=conf_max,
        asset_filter=asset,
        outcome_filter=outcome_val,
    )

    if export_df.empty:
        # Nothing to export -- return None to suppress download
        return None

    filename = f"shitpost_alpha_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return dcc.send_data_frame(export_df.to_csv, filename, index=False)
```

### 3.6 Asset Filter Dropdown Population

Populates the asset dropdown with actual assets from the database. Fires once on page load.

```python
@app.callback(
    Output("signal-feed-asset-filter", "options"),
    [Input("signal-feed-poll-interval", "n_intervals")],
)
def populate_signal_feed_asset_filter(n_intervals):
    """
    Populate the asset filter dropdown with assets from the database.

    Fetches the list of unique asset symbols that have prediction outcomes.
    This list updates on each polling cycle in case new assets appear.

    Args:
        n_intervals: Poll tick count.

    Returns:
        List of dicts with 'label' and 'value' keys for the dropdown.
    """
    from data import get_active_assets_from_db

    assets = get_active_assets_from_db()
    return [{"label": a, "value": a} for a in assets]
```

---

## Task 4: Multi-Page Routing

The dashboard currently serves a single page. To add `/signals` as a separate page, you must convert the app to use URL-based routing via `dcc.Location`.

### 4.1 Update `app.py`

No changes are needed to `app.py`. The entry point already calls `create_app()` and `register_callbacks(app)`. The routing logic lives entirely in `layout.py`.

### 4.2 Update `create_app()` in `layout.py`

Replace the existing `app.layout` assignment with a router-based layout.

```python
def create_app() -> Dash:
    """Create and configure the Dash app."""
    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
        ],
        suppress_callback_exceptions=True,
    )

    app.title = "Shitpost Alpha - Prediction Performance Dashboard"

    # ---------------------------------------------------------------
    # Root layout: nav + page container
    # ---------------------------------------------------------------
    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),

        # Navigation bar
        create_nav_bar(),

        # Page content -- swapped by the routing callback
        html.Div(id="page-content"),

    ], style={
        "backgroundColor": COLORS["primary"],
        "minHeight": "100vh",
        "color": COLORS["text"],
        "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    })

    return app
```

### 4.3 Navigation Bar

```python
def create_nav_bar():
    """Create the top navigation bar with page links."""
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand([
                html.Span("Shitpost Alpha", style={"color": COLORS["accent"], "fontWeight": "bold"}),
            ], href="/"),
            dbc.Nav([
                dbc.NavItem(dbc.NavLink("Dashboard", href="/", active="exact")),
                dbc.NavItem(dbc.NavLink("Signal Feed", href="/signals", active="exact")),
            ], navbar=True),
        ]),
        color=COLORS["secondary"],
        dark=True,
        style={"borderBottom": f"1px solid {COLORS['border']}"},
    )
```

### 4.4 Routing Callback

```python
@app.callback(
    Output("page-content", "children"),
    [Input("url", "pathname")],
)
def display_page(pathname):
    """
    Route to the correct page based on the URL pathname.

    Args:
        pathname: The current URL path (e.g. '/', '/signals').

    Returns:
        The layout component for the matched page. Returns the main
        dashboard for '/' and the signal feed for '/signals'.
    """
    if pathname == "/signals":
        return create_signal_feed_page()
    else:
        # Default: main dashboard
        return create_main_dashboard_page()
```

### 4.5 Extract Main Dashboard Layout

Move the existing dashboard layout (currently inline in `create_app`) into its own function. This is a refactor -- no behavior change. The body of this function is the existing content of `app.layout` starting from the `dcc.Interval` through the footer.

```python
def create_main_dashboard_page():
    """
    Create the main dashboard page layout.

    This is the existing dashboard that was previously the sole page.
    It contains: refresh interval, performance metrics, charts, recent
    signals sidebar, asset drilldown, and the collapsible data table.
    """
    return html.Div([
        # Auto-refresh interval
        dcc.Interval(
            id="refresh-interval",
            interval=5 * 60 * 1000,  # 5 minutes
            n_intervals=0,
        ),

        # Store for selected asset
        dcc.Store(id="selected-asset", data=None),

        # Header
        create_header(),

        # Main content container
        html.Div([
            # Performance Metrics Row
            html.Div(id="performance-metrics", className="mb-4"),

            # ... (rest of existing layout unchanged)

            # Footer
            create_footer(),
        ], style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"}),
    ])
```

**Important**: When you refactor, copy the existing layout exactly. Do not change component IDs. All existing callbacks will continue to work because the component IDs are unchanged.

---

## Task 5: Imports

You will need to add the following imports to `layout.py` if not already present:

```python
from dash import Dash, html, dcc, dash_table, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
```

You will also need to import the new data functions in `layout.py`:

```python
from data import (
    get_prediction_stats,
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    # NEW for signal feed
    get_signal_feed,
    get_signal_feed_count,
    get_new_signals_since,
    get_signal_feed_csv,
)
```

And in `data.py`, ensure these imports are present at the top:

```python
import pandas as pd
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
```

---

## Task 6: Test Specifications

All tests go in the existing test files under `shit_tests/shitty_ui/`. Follow the existing patterns: class-based grouping, `@patch('data.execute_query')` for mocking, and descriptive docstrings.

### 6.1 Data Layer Tests (`test_data.py`)

Add the following test classes to `shit_tests/shitty_ui/test_data.py`:

```python
class TestGetSignalFeed:
    """Tests for get_signal_feed function."""

    @patch('data.execute_query')
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_signal_feed

        mock_execute.return_value = (
            [(
                datetime(2025, 1, 15, 10, 30),
                'Test post text',
                'post123',
                1,
                ['AAPL'],
                {'AAPL': 'bullish'},
                0.85,
                'Test thesis',
                'completed',
                'AAPL',
                'bullish',
                0.85,
                1.5,
                2.0,
                3.5,
                True,
                True,
                True,
                35.0,
                True,
            )],
            [
                'timestamp', 'text', 'shitpost_id', 'prediction_id', 'assets',
                'market_impact', 'confidence', 'thesis', 'analysis_status',
                'symbol', 'prediction_sentiment', 'prediction_confidence',
                'return_t1', 'return_t3', 'return_t7', 'correct_t1',
                'correct_t3', 'correct_t7', 'pnl_t7', 'is_complete',
            ]
        )

        result = get_signal_feed(limit=20, offset=0)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result['confidence'].iloc[0] == 0.85

    @patch('data.execute_query')
    def test_passes_pagination_params(self, mock_execute):
        """Test that limit and offset are passed to the query."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(limit=10, offset=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['limit'] == 10
        assert params['offset'] == 30

    @patch('data.execute_query')
    def test_applies_sentiment_filter(self, mock_execute):
        """Test that sentiment filter is included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(sentiment_filter='bullish')

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['sentiment_filter'] == 'bullish'

    @patch('data.execute_query')
    def test_applies_confidence_range(self, mock_execute):
        """Test that confidence min and max are included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(confidence_min=0.6, confidence_max=0.9)

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['confidence_min'] == 0.6
        assert params['confidence_max'] == 0.9

    @patch('data.execute_query')
    def test_applies_asset_filter(self, mock_execute):
        """Test that asset filter is uppercased and included in query params."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(asset_filter='aapl')

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['asset_filter'] == 'AAPL'

    @patch('data.execute_query')
    def test_applies_outcome_filter_correct(self, mock_execute):
        """Test that outcome filter for 'correct' adds the right WHERE clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter='correct')

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert 'correct_t7 = true' in query_str

    @patch('data.execute_query')
    def test_applies_outcome_filter_incorrect(self, mock_execute):
        """Test that outcome filter for 'incorrect' adds the right WHERE clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter='incorrect')

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert 'correct_t7 = false' in query_str

    @patch('data.execute_query')
    def test_applies_outcome_filter_pending(self, mock_execute):
        """Test that outcome filter for 'pending' adds the right WHERE clause."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed(outcome_filter='pending')

        call_args = mock_execute.call_args[0]
        query_str = str(call_args[0])
        assert 'correct_t7 IS NULL' in query_str

    @patch('data.execute_query')
    def test_no_filter_when_none(self, mock_execute):
        """Test that no extra filters are added when all params are None."""
        from data import get_signal_feed

        mock_execute.return_value = ([], [])

        get_signal_feed()

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert 'sentiment_filter' not in params
        assert 'asset_filter' not in params
        assert 'confidence_min' not in params
        assert 'confidence_max' not in params

    @patch('data.execute_query')
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on database error."""
        from data import get_signal_feed

        mock_execute.side_effect = Exception("Connection timeout")

        result = get_signal_feed()

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetSignalFeedCount:
    """Tests for get_signal_feed_count function."""

    @patch('data.execute_query')
    def test_returns_integer_count(self, mock_execute):
        """Test that function returns an integer."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(142,)], ['total'])

        result = get_signal_feed_count()

        assert isinstance(result, int)
        assert result == 142

    @patch('data.execute_query')
    def test_returns_zero_on_no_results(self, mock_execute):
        """Test that function returns 0 when query returns no rows."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([], [])

        result = get_signal_feed_count()

        assert result == 0

    @patch('data.execute_query')
    def test_returns_zero_on_error(self, mock_execute):
        """Test that function returns 0 on database error."""
        from data import get_signal_feed_count

        mock_execute.side_effect = Exception("Database error")

        result = get_signal_feed_count()

        assert result == 0

    @patch('data.execute_query')
    def test_applies_sentiment_filter(self, mock_execute):
        """Test that sentiment filter is passed to query."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(50,)], ['total'])

        result = get_signal_feed_count(sentiment_filter='bearish')

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['sentiment_filter'] == 'bearish'

    @patch('data.execute_query')
    def test_returns_zero_on_null_count(self, mock_execute):
        """Test that function returns 0 when database returns NULL count."""
        from data import get_signal_feed_count

        mock_execute.return_value = ([(None,)], ['total'])

        result = get_signal_feed_count()

        assert result == 0


class TestGetNewSignalsSince:
    """Tests for get_new_signals_since function."""

    @patch('data.execute_query')
    def test_returns_count_of_new_signals(self, mock_execute):
        """Test that function returns the count of new signals."""
        from data import get_new_signals_since

        mock_execute.return_value = ([(5,)], ['new_count'])

        result = get_new_signals_since("2025-01-15T10:00:00")

        assert result == 5

    def test_returns_zero_for_none_timestamp(self):
        """Test that function returns 0 when timestamp is None."""
        from data import get_new_signals_since

        result = get_new_signals_since(None)

        assert result == 0

    def test_returns_zero_for_empty_timestamp(self):
        """Test that function returns 0 when timestamp is empty string."""
        from data import get_new_signals_since

        result = get_new_signals_since("")

        assert result == 0

    @patch('data.execute_query')
    def test_passes_timestamp_to_query(self, mock_execute):
        """Test that timestamp is passed as query parameter."""
        from data import get_new_signals_since

        mock_execute.return_value = ([(0,)], ['new_count'])

        get_new_signals_since("2025-01-15T10:00:00")

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params['since_timestamp'] == "2025-01-15T10:00:00"

    @patch('data.execute_query')
    def test_returns_zero_on_error(self, mock_execute):
        """Test that function returns 0 on database error."""
        from data import get_new_signals_since

        mock_execute.side_effect = Exception("Database error")

        result = get_new_signals_since("2025-01-15T10:00:00")

        assert result == 0


class TestGetSignalFeedCsv:
    """Tests for get_signal_feed_csv function."""

    @patch('data.get_signal_feed')
    def test_returns_dataframe_with_export_columns(self, mock_feed):
        """Test that function returns a DataFrame with human-readable columns."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame([{
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test post',
            'shitpost_id': 'post123',
            'prediction_id': 1,
            'assets': ['AAPL'],
            'market_impact': {'AAPL': 'bullish'},
            'confidence': 0.85,
            'thesis': 'Bull thesis',
            'analysis_status': 'completed',
            'symbol': 'AAPL',
            'prediction_sentiment': 'bullish',
            'prediction_confidence': 0.85,
            'return_t1': 1.0,
            'return_t3': 2.0,
            'return_t7': 3.5,
            'correct_t1': True,
            'correct_t3': True,
            'correct_t7': True,
            'pnl_t7': 35.0,
            'is_complete': True,
        }])

        result = get_signal_feed_csv()

        assert isinstance(result, pd.DataFrame)
        assert 'Timestamp' in result.columns
        assert 'Post Text' in result.columns
        assert 'Asset' in result.columns
        assert 'Sentiment' in result.columns
        assert 'Confidence' in result.columns
        assert 'Outcome' in result.columns

    @patch('data.get_signal_feed')
    def test_returns_empty_dataframe_when_no_data(self, mock_feed):
        """Test that function returns empty DataFrame when feed is empty."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame()

        result = get_signal_feed_csv()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch('data.get_signal_feed')
    def test_formats_confidence_as_percentage(self, mock_feed):
        """Test that confidence is formatted as a percentage string."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame([{
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test',
            'shitpost_id': 'p1',
            'prediction_id': 1,
            'assets': ['AAPL'],
            'market_impact': {},
            'confidence': 0.85,
            'thesis': '',
            'analysis_status': 'completed',
            'symbol': 'AAPL',
            'prediction_sentiment': 'bullish',
            'prediction_confidence': 0.85,
            'return_t1': None,
            'return_t3': None,
            'return_t7': None,
            'correct_t1': None,
            'correct_t3': None,
            'correct_t7': None,
            'pnl_t7': None,
            'is_complete': False,
        }])

        result = get_signal_feed_csv()

        assert result['Confidence'].iloc[0] == '85%'

    @patch('data.get_signal_feed')
    def test_formats_outcome_labels(self, mock_feed):
        """Test that outcome column uses Correct/Incorrect/Pending labels."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame([
            {
                'timestamp': datetime(2025, 1, 15), 'text': 'T1', 'shitpost_id': 'p1',
                'prediction_id': 1, 'assets': [], 'market_impact': {}, 'confidence': 0.7,
                'thesis': '', 'analysis_status': 'completed', 'symbol': 'AAPL',
                'prediction_sentiment': 'bullish', 'prediction_confidence': 0.7,
                'return_t1': None, 'return_t3': None, 'return_t7': 2.0,
                'correct_t1': None, 'correct_t3': None, 'correct_t7': True,
                'pnl_t7': 20.0, 'is_complete': True,
            },
            {
                'timestamp': datetime(2025, 1, 14), 'text': 'T2', 'shitpost_id': 'p2',
                'prediction_id': 2, 'assets': [], 'market_impact': {}, 'confidence': 0.6,
                'thesis': '', 'analysis_status': 'completed', 'symbol': 'TSLA',
                'prediction_sentiment': 'bearish', 'prediction_confidence': 0.6,
                'return_t1': None, 'return_t3': None, 'return_t7': -1.0,
                'correct_t1': None, 'correct_t3': None, 'correct_t7': False,
                'pnl_t7': -10.0, 'is_complete': True,
            },
            {
                'timestamp': datetime(2025, 1, 13), 'text': 'T3', 'shitpost_id': 'p3',
                'prediction_id': 3, 'assets': [], 'market_impact': {}, 'confidence': 0.5,
                'thesis': '', 'analysis_status': 'completed', 'symbol': 'MSFT',
                'prediction_sentiment': 'neutral', 'prediction_confidence': 0.5,
                'return_t1': None, 'return_t3': None, 'return_t7': None,
                'correct_t1': None, 'correct_t3': None, 'correct_t7': None,
                'pnl_t7': None, 'is_complete': False,
            },
        ])

        result = get_signal_feed_csv()

        assert result['Outcome'].iloc[0] == 'Correct'
        assert result['Outcome'].iloc[1] == 'Incorrect'
        assert result['Outcome'].iloc[2] == 'Pending'

    @patch('data.get_signal_feed')
    def test_passes_filters_to_feed(self, mock_feed):
        """Test that filter params are forwarded to get_signal_feed."""
        from data import get_signal_feed_csv

        mock_feed.return_value = pd.DataFrame()

        get_signal_feed_csv(
            sentiment_filter='bullish',
            confidence_min=0.7,
            confidence_max=0.9,
            asset_filter='AAPL',
            outcome_filter='correct',
        )

        mock_feed.assert_called_once_with(
            limit=10000,
            offset=0,
            sentiment_filter='bullish',
            confidence_min=0.7,
            confidence_max=0.9,
            asset_filter='AAPL',
            outcome_filter='correct',
        )
```

### 6.2 Layout Component Tests (`test_layout.py`)

Add the following test classes to `shit_tests/shitty_ui/test_layout.py`:

```python
class TestCreateFeedSignalCard:
    """Tests for create_feed_signal_card function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_feed_signal_card
        from dash import html

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test post about market impact',
            'confidence': 0.85,
            'assets': ['AAPL'],
            'market_impact': {'AAPL': 'bullish'},
            'symbol': 'AAPL',
            'prediction_sentiment': 'bullish',
            'return_t7': 3.5,
            'correct_t7': True,
            'pnl_t7': 35.0,
            'thesis': 'Market will react positively',
        }

        card = create_feed_signal_card(row)

        assert isinstance(card, html.Div)

    def test_shows_correct_badge_for_correct_outcome(self):
        """Test that a 'Correct' badge is shown when correct_t7 is True."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test post',
            'confidence': 0.8,
            'assets': ['AAPL'],
            'market_impact': {},
            'symbol': 'AAPL',
            'prediction_sentiment': 'bullish',
            'return_t7': 2.0,
            'correct_t7': True,
            'pnl_t7': 20.0,
            'thesis': '',
        }

        card = create_feed_signal_card(row)
        # Card should be created without error
        assert card is not None

    def test_shows_incorrect_badge_for_incorrect_outcome(self):
        """Test that an 'Incorrect' badge is shown when correct_t7 is False."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test post',
            'confidence': 0.8,
            'assets': ['TSLA'],
            'market_impact': {},
            'symbol': 'TSLA',
            'prediction_sentiment': 'bearish',
            'return_t7': -3.0,
            'correct_t7': False,
            'pnl_t7': -30.0,
            'thesis': '',
        }

        card = create_feed_signal_card(row)
        assert card is not None

    def test_shows_pending_badge_when_no_outcome(self):
        """Test that a 'Pending' badge is shown when correct_t7 is None."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Test post',
            'confidence': 0.7,
            'assets': ['MSFT'],
            'market_impact': {},
            'symbol': 'MSFT',
            'prediction_sentiment': 'neutral',
            'return_t7': None,
            'correct_t7': None,
            'pnl_t7': None,
            'thesis': '',
        }

        card = create_feed_signal_card(row)
        assert card is not None

    def test_truncates_long_text(self):
        """Test that post text longer than 250 characters is truncated."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'A' * 300,
            'confidence': 0.8,
            'assets': ['AAPL'],
            'market_impact': {},
            'symbol': None,
            'prediction_sentiment': None,
            'return_t7': None,
            'correct_t7': None,
            'pnl_t7': None,
            'thesis': None,
        }

        card = create_feed_signal_card(row)
        assert card is not None

    def test_handles_missing_optional_fields(self):
        """Test that card handles None/missing fields gracefully."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': None,
            'text': '',
            'confidence': None,
            'assets': None,
            'market_impact': None,
            'symbol': None,
            'prediction_sentiment': None,
            'return_t7': None,
            'correct_t7': None,
            'pnl_t7': None,
            'thesis': None,
        }

        card = create_feed_signal_card(row)
        assert card is not None

    def test_handles_string_timestamp(self):
        """Test that string timestamps are handled without error."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': '2025-01-15T10:30:00',
            'text': 'Test post',
            'confidence': 0.7,
            'assets': ['SPY'],
            'market_impact': {},
            'symbol': 'SPY',
            'prediction_sentiment': 'bullish',
            'return_t7': 1.0,
            'correct_t7': True,
            'pnl_t7': 10.0,
            'thesis': 'SPY going up',
        }

        card = create_feed_signal_card(row)
        assert card is not None

    def test_displays_multiple_assets(self):
        """Test that multiple assets are displayed with +N notation."""
        from layout import create_feed_signal_card

        row = {
            'timestamp': datetime(2025, 1, 15, 10, 30),
            'text': 'Multiple assets mentioned',
            'confidence': 0.8,
            'assets': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'],
            'market_impact': {},
            'symbol': None,
            'prediction_sentiment': 'bullish',
            'return_t7': None,
            'correct_t7': None,
            'pnl_t7': None,
            'thesis': '',
        }

        card = create_feed_signal_card(row)
        assert card is not None


class TestCreateNewSignalsBanner:
    """Tests for create_new_signals_banner function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_new_signals_banner
        from dash import html

        banner = create_new_signals_banner(5)

        assert isinstance(banner, html.Div)

    def test_singular_for_one_signal(self):
        """Test that singular 'signal' is used when count is 1."""
        from layout import create_new_signals_banner

        banner = create_new_signals_banner(1)
        assert banner is not None

    def test_plural_for_multiple_signals(self):
        """Test that plural 'signals' is used when count is > 1."""
        from layout import create_new_signals_banner

        banner = create_new_signals_banner(3)
        assert banner is not None


class TestCreateSignalFeedPage:
    """Tests for create_signal_feed_page function."""

    def test_returns_html_div(self):
        """Test that function returns an HTML Div."""
        from layout import create_signal_feed_page
        from dash import html

        page = create_signal_feed_page()

        assert isinstance(page, html.Div)

    def test_contains_filter_controls(self):
        """Test that page contains filter dropdowns and slider."""
        from layout import create_signal_feed_page

        page = create_signal_feed_page()

        # Page should have children (filters, cards container, etc.)
        assert page.children is not None
        assert len(page.children) > 0

    def test_contains_polling_interval(self):
        """Test that page contains the 2-minute polling interval."""
        from layout import create_signal_feed_page

        page = create_signal_feed_page()
        assert page is not None


class TestCreateNavBar:
    """Tests for create_nav_bar function."""

    def test_returns_navbar_component(self):
        """Test that function returns a Navbar component."""
        from layout import create_nav_bar
        import dash_bootstrap_components as dbc

        navbar = create_nav_bar()

        assert isinstance(navbar, dbc.Navbar)
```

---

## Implementation Checklist

Use this checklist to track progress. Complete tasks in order -- later tasks depend on earlier ones.

### Phase A: Data Layer

- [ ] Add `get_signal_feed` function to `data.py`
  - [ ] Implement base query with three-table join
  - [ ] Implement sentiment filter with JSONB query
  - [ ] Implement confidence range filter
  - [ ] Implement asset filter
  - [ ] Implement outcome filter
  - [ ] Implement pagination (LIMIT/OFFSET)
  - [ ] Add error handling (try/except returning empty DataFrame)
  - [ ] Write all `TestGetSignalFeed` tests -- verify they pass

- [ ] Add `get_signal_feed_count` function to `data.py`
  - [ ] Implement COUNT query with same filter logic
  - [ ] Add error handling
  - [ ] Write all `TestGetSignalFeedCount` tests -- verify they pass

- [ ] Add `get_new_signals_since` function to `data.py`
  - [ ] Implement timestamp comparison query
  - [ ] Handle None/empty input
  - [ ] Add error handling
  - [ ] Write all `TestGetNewSignalsSince` tests -- verify they pass

- [ ] Add `get_signal_feed_csv` function to `data.py`
  - [ ] Reuse `get_signal_feed` with large limit
  - [ ] Format columns for human-readable export
  - [ ] Handle empty result set
  - [ ] Write all `TestGetSignalFeedCsv` tests -- verify they pass

- [ ] Run all data tests: `cd /home/user/shitpost-alpha && python -m pytest shit_tests/shitty_ui/test_data.py -v`
- [ ] All existing tests still pass: `python -m pytest shit_tests/shitty_ui/ -v`

### Phase B: Layout Components

- [ ] Add `create_feed_signal_card` function to `layout.py`
  - [ ] Implement badge logic (New, Correct, Incorrect, Pending)
  - [ ] Implement sentiment display with arrow icons
  - [ ] Implement confidence bar
  - [ ] Implement return/P&L metrics display
  - [ ] Implement text truncation
  - [ ] Handle None/missing fields gracefully
  - [ ] Write all `TestCreateFeedSignalCard` tests -- verify they pass

- [ ] Add `create_new_signals_banner` function to `layout.py`
  - [ ] Implement singular/plural text
  - [ ] Include "Show New Signals" button with correct ID
  - [ ] Write `TestCreateNewSignalsBanner` tests -- verify they pass

- [ ] Add `create_signal_feed_page` function to `layout.py`
  - [ ] Add polling interval (2 min)
  - [ ] Add dcc.Store components (last-seen-ts, offset)
  - [ ] Add dcc.Download component
  - [ ] Add filter bar (sentiment, confidence, asset, outcome)
  - [ ] Add count label and export button row
  - [ ] Add cards container with loading spinner
  - [ ] Add "Load More" button
  - [ ] Write `TestCreateSignalFeedPage` tests -- verify they pass

- [ ] Run all layout tests: `python -m pytest shit_tests/shitty_ui/test_layout.py -v`

### Phase C: Multi-Page Routing

- [ ] Add `create_nav_bar` function to `layout.py`
  - [ ] Add links to "/" and "/signals"
  - [ ] Write `TestCreateNavBar` tests -- verify they pass

- [ ] Extract `create_main_dashboard_page` function from `create_app`
  - [ ] Move existing layout body into new function
  - [ ] Keep all component IDs unchanged
  - [ ] Verify existing callbacks still work

- [ ] Update `create_app` to use `dcc.Location` routing
  - [ ] Add `dcc.Location` to root layout
  - [ ] Add `create_nav_bar` to root layout
  - [ ] Add `page-content` container

- [ ] Add `display_page` routing callback to `register_callbacks`
  - [ ] Route "/" to `create_main_dashboard_page`
  - [ ] Route "/signals" to `create_signal_feed_page`

- [ ] Run full test suite: `python -m pytest shit_tests/shitty_ui/ -v`
- [ ] Manually verify existing dashboard at "/" still works

### Phase D: Callbacks

- [ ] Add `update_signal_feed` callback
  - [ ] Wire up all filter inputs
  - [ ] Normalize filter values ("all" -> None)
  - [ ] Call `get_signal_feed` and `get_signal_feed_count`
  - [ ] Build card list from DataFrame
  - [ ] Handle empty result set with "no signals" message
  - [ ] Update count label
  - [ ] Show/hide "Load More" button

- [ ] Add `load_more_signals` callback
  - [ ] Use `allow_duplicate=True` on outputs
  - [ ] Read existing cards from State
  - [ ] Fetch next page using current offset
  - [ ] Append new cards to existing list
  - [ ] Update offset and count label
  - [ ] Hide button when all loaded

- [ ] Add `check_for_new_signals` callback
  - [ ] Read last-seen timestamp from Store
  - [ ] Call `get_new_signals_since`
  - [ ] Show/hide banner

- [ ] Add `trigger_feed_reload_on_show_new` callback
  - [ ] Increment poll interval to force reload

- [ ] Add `export_signal_feed_csv` callback
  - [ ] Read current filter values from State
  - [ ] Call `get_signal_feed_csv`
  - [ ] Return `dcc.send_data_frame` result

- [ ] Add `populate_signal_feed_asset_filter` callback
  - [ ] Call `get_active_assets_from_db`
  - [ ] Return options list

- [ ] Add required imports to `layout.py`
  - [ ] `PreventUpdate` from `dash.exceptions`
  - [ ] New data functions from `data.py`

### Phase E: Integration & Quality

- [ ] Run full test suite: `python -m pytest shit_tests/ -v`
- [ ] Run linter: `ruff check .`
- [ ] Run formatter: `ruff format .`
- [ ] Manual testing checklist:
  - [ ] Navigate to `/signals` -- page loads with signal cards
  - [ ] Change sentiment filter -- cards update
  - [ ] Adjust confidence slider -- cards update
  - [ ] Select an asset -- cards filter to that asset
  - [ ] Select outcome filter -- cards filter correctly
  - [ ] Wait 2 minutes -- polling fires (check browser devtools Network tab)
  - [ ] Click "Load More" -- additional cards appear below existing ones
  - [ ] Click "Load More" until all loaded -- button disappears
  - [ ] Click "Export CSV" -- file downloads with correct data
  - [ ] Navigate to "/" -- main dashboard still works
  - [ ] Navigate back to "/signals" -- signal feed reloads
  - [ ] Check badges: New (blue) on recent signals, Correct (green), Incorrect (red), Pending (yellow)
- [ ] Update CHANGELOG.md with new entry under `## [Unreleased]`
- [ ] Commit with descriptive message

---

## Common Pitfalls

### 1. Callback Output Collisions

Dash does not allow two callbacks to write to the same `Output` unless you use `allow_duplicate=True`. The `load_more_signals` callback writes to the same outputs as `update_signal_feed`. You **must** pass `allow_duplicate=True` to the duplicate outputs in `load_more_signals`:

```python
@app.callback(
    [
        Output("signal-feed-cards-container", "children", allow_duplicate=True),
        Output("signal-feed-offset", "data", allow_duplicate=True),
        Output("signal-feed-count-label", "children", allow_duplicate=True),
        Output("signal-feed-load-more-container", "style", allow_duplicate=True),
    ],
    ...
    prevent_initial_call=True,  # REQUIRED when using allow_duplicate
)
```

### 2. PreventUpdate Import

`PreventUpdate` is imported from `dash.exceptions`, not from `dash`:

```python
from dash.exceptions import PreventUpdate
```

### 3. dcc.Download Component

`dcc.Download` is available in Dash 2.0+. The callback must return `dcc.send_data_frame(...)` or `None`. Returning `None` suppresses the download.

```python
# This is the correct import and usage:
from dash import dcc

# In layout:
dcc.Download(id="signal-feed-csv-download")

# In callback:
return dcc.send_data_frame(export_df.to_csv, filename, index=False)
```

### 4. JSONB Filtering in PostgreSQL

The sentiment filter uses `jsonb_each_text()` to iterate over the `market_impact` JSONB field. This only works in PostgreSQL, not SQLite. If running tests against SQLite, the sentiment filter query will fail. Tests should mock `execute_query` (as shown in the test specs) to avoid hitting the actual database.

### 5. Timezone-Aware vs Naive Timestamps

The database may return timezone-naive or timezone-aware timestamps depending on the PostgreSQL config. The "New" badge logic in `create_feed_signal_card` handles both cases by assuming UTC for naive timestamps. Do not assume either form -- always check `timestamp.tzinfo`.

### 6. Page-Specific Component IDs

All component IDs for the signal feed page must be unique and must not collide with IDs on the main dashboard. Every signal feed component ID is prefixed with `signal-feed-`. Do not use generic IDs like `"sentiment-filter"` -- use `"signal-feed-sentiment-filter"`.

---

## Definition of Done

- [ ] All four data functions implemented in `data.py` with error handling
- [ ] All layout components implemented in `layout.py`
- [ ] All six callbacks implemented in `register_callbacks()`
- [ ] Multi-page routing works (both `/` and `/signals`)
- [ ] All new tests pass: `python -m pytest shit_tests/shitty_ui/ -v`
- [ ] All existing tests still pass (no regressions)
- [ ] Linting passes: `ruff check .`
- [ ] Formatting passes: `ruff format .`
- [ ] Manual testing completed (see checklist in Phase E)
- [ ] CHANGELOG.md updated
- [ ] PR created with description referencing this spec
