# Current State - Dashboard Architecture Reference

## Overview

This document describes the current implementation of the Shitpost Alpha dashboard as of the Phase 0.2 redesign. Use this as a reference when implementing new features.

---

## Directory Structure

```
shitty_ui/
├── app.py          # Application entry point
├── layout.py       # Layout components and callbacks (632 lines)
├── data.py         # Database query functions (564 lines)
└── README.md       # Module documentation

shit_tests/shitty_ui/
├── __init__.py
├── conftest.py     # Test configuration and mocks
├── test_data.py    # Data layer tests (28 tests)
└── test_layout.py  # Layout component tests (21 tests)
```

---

## Application Entry Point

**File**: `shitty_ui/app.py`

```python
# app.py creates the Dash app and registers callbacks
from layout import create_app, register_callbacks

app = create_app()
register_callbacks(app)

if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
```

**Key Points**:
- `create_app()` builds the Dash application with layout
- `register_callbacks()` adds all interactive behavior
- Server runs on port 8050 by default

---

## Layout Architecture

**File**: `shitty_ui/layout.py`

### Color Palette

```python
COLORS = {
    "primary": "#1e293b",      # Slate 800 - main background
    "secondary": "#334155",    # Slate 700 - cards
    "accent": "#3b82f6",       # Blue 500 - highlights
    "success": "#10b981",      # Emerald 500 - bullish/correct
    "danger": "#ef4444",       # Red 500 - bearish/incorrect
    "warning": "#f59e0b",      # Amber 500 - pending
    "text": "#f1f5f9",         # Slate 100 - primary text
    "text_muted": "#94a3b8",   # Slate 400 - secondary text
    "border": "#475569",       # Slate 600 - borders
}
```

### Layout Hierarchy

```
App Layout
├── Header (create_header)
│   ├── Title: "Shitpost Alpha"
│   └── Subtitle: "Trump Tweet Prediction Performance Dashboard"
│
├── Main Content Container (max-width: 1400px)
│   ├── Performance Metrics Row (id="performance-metrics")
│   │   ├── Prediction Accuracy Card
│   │   ├── Total P&L Card
│   │   ├── Avg Return Card
│   │   └── Predictions Evaluated Card
│   │
│   ├── Two-Column Layout (dbc.Row)
│   │   ├── Left Column (md=7)
│   │   │   ├── Accuracy by Confidence Chart (id="confidence-accuracy-chart")
│   │   │   └── Performance by Asset Chart (id="asset-accuracy-chart")
│   │   │
│   │   └── Right Column (md=5)
│   │       ├── Recent Signals Card (id="recent-signals-list")
│   │       └── Asset Deep Dive Card
│   │           ├── Dropdown (id="asset-selector")
│   │           └── Content (id="asset-drilldown-content")
│   │
│   └── Collapsible Data Table
│       ├── Toggle Button (id="collapse-table-button")
│       └── Collapse Content (id="collapse-table")
│           ├── Filter Controls
│           │   ├── Confidence Slider (id="confidence-slider")
│           │   ├── Date Range Picker (id="date-range-picker")
│           │   └── Limit Selector (id="limit-selector")
│           └── Table Container (id="predictions-table-container")
│
└── Footer (create_footer)
    └── Disclaimer + GitHub link
```

### Component Functions

#### `create_app() -> Dash`
Creates the main Dash application with layout.

```python
def create_app() -> Dash:
    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.DARKLY,
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
        ],
        suppress_callback_exceptions=True
    )
    app.title = "Shitpost Alpha - Prediction Performance Dashboard"
    app.layout = html.Div([...])
    return app
```

#### `create_metric_card(title, value, subtitle, icon, color) -> dbc.Card`
Creates a metric display card.

```python
# Example usage
create_metric_card(
    title="Prediction Accuracy",
    value="65.2%",
    subtitle="42/64 correct",
    icon="bullseye",
    color=COLORS["success"]
)
```

#### `create_signal_card(row: dict) -> html.Div`
Creates a signal card from a DataFrame row.

**Expected row keys**:
- `timestamp`: datetime or string
- `text`: Post content
- `confidence`: float (0-1)
- `assets`: list of ticker symbols
- `market_impact`: dict mapping asset to sentiment
- `return_t7`: float or None (7-day return)
- `correct_t7`: bool or None

```python
# Example row
row = {
    'timestamp': datetime(2024, 1, 15, 10, 30),
    'text': 'Great news for American manufacturing!',
    'confidence': 0.82,
    'assets': ['AAPL', 'GOOGL', 'MSFT'],
    'market_impact': {'AAPL': 'bullish'},
    'return_t7': 2.5,
    'correct_t7': True
}
card = create_signal_card(row)
```

### Callbacks

#### Main Dashboard Update
**Trigger**: `refresh-interval` (every 5 minutes)

**Outputs**:
- `performance-metrics` (children)
- `confidence-accuracy-chart` (figure)
- `asset-accuracy-chart` (figure)
- `recent-signals-list` (children)
- `asset-selector` (options)

```python
@app.callback(
    [
        Output("performance-metrics", "children"),
        Output("confidence-accuracy-chart", "figure"),
        Output("asset-accuracy-chart", "figure"),
        Output("recent-signals-list", "children"),
        Output("asset-selector", "options"),
    ],
    [Input("refresh-interval", "n_intervals")]
)
def update_dashboard(n_intervals):
    # Fetch data and return components
    pass
```

#### Asset Drilldown
**Trigger**: `asset-selector` value change

```python
@app.callback(
    Output("asset-drilldown-content", "children"),
    [Input("asset-selector", "value")]
)
def update_asset_drilldown(asset):
    if not asset:
        return html.P("Select an asset...")
    # Fetch similar predictions and display
    pass
```

#### Table Collapse Toggle
**Trigger**: `collapse-table-button` click

```python
@app.callback(
    Output("collapse-table", "is_open"),
    [Input("collapse-table-button", "n_clicks")],
    [State("collapse-table", "is_open")],
)
def toggle_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open
```

#### Table Data Update
**Trigger**: Collapse open or filter changes

```python
@app.callback(
    Output("predictions-table-container", "children"),
    [
        Input("collapse-table", "is_open"),
        Input("confidence-slider", "value"),
        Input("date-range-picker", "start_date"),
        Input("date-range-picker", "end_date"),
        Input("limit-selector", "value"),
    ]
)
def update_predictions_table(is_open, confidence_range, start_date, end_date, limit):
    if not is_open:
        return None
    # Fetch and display table
    pass
```

---

## Data Layer

**File**: `shitty_ui/data.py`

### Database Connection

```python
# Connection setup (simplified)
from shit.config.shitpost_settings import settings
DATABASE_URL = settings.DATABASE_URL

# Convert async URL to sync for Dash
sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
engine = create_engine(sync_url, echo=False, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

### Query Functions

#### `get_prediction_stats() -> Dict[str, Any]`
Returns basic statistics about predictions.

**Returns**:
```python
{
    "total_posts": int,
    "analyzed_posts": int,
    "completed_analyses": int,
    "bypassed_posts": int,
    "avg_confidence": float,
    "high_confidence_predictions": int
}
```

#### `get_performance_metrics() -> Dict[str, Any]`
Returns performance metrics from prediction_outcomes.

**Returns**:
```python
{
    "total_outcomes": int,
    "evaluated_predictions": int,
    "correct_predictions": int,
    "incorrect_predictions": int,
    "accuracy_t7": float,      # Percentage
    "avg_return_t7": float,    # Percentage
    "total_pnl_t7": float,     # Dollar amount
    "avg_confidence": float    # 0-1
}
```

#### `get_recent_signals(limit=10, min_confidence=0.5) -> pd.DataFrame`
Returns recent predictions with actionable signals.

**Columns**:
- `timestamp`, `text`, `shitpost_id`, `prediction_id`
- `assets`, `market_impact`, `confidence`, `thesis`, `analysis_status`
- `symbol`, `prediction_sentiment`
- `return_t1`, `return_t3`, `return_t7`
- `correct_t1`, `correct_t3`, `correct_t7`
- `pnl_t7`, `is_complete`

#### `get_accuracy_by_confidence() -> pd.DataFrame`
Returns accuracy broken down by confidence level.

**Columns**:
- `confidence_level`: 'Low (<60%)', 'Medium (60-75%)', 'High (>75%)'
- `total`, `correct`, `incorrect`
- `avg_return`, `total_pnl`
- `accuracy` (calculated)

#### `get_accuracy_by_asset(limit=15) -> pd.DataFrame`
Returns accuracy broken down by asset.

**Columns**:
- `symbol`
- `total_predictions`, `correct`, `incorrect`
- `avg_return`, `total_pnl`
- `accuracy` (calculated)

#### `get_similar_predictions(asset, limit=10) -> pd.DataFrame`
Returns historical predictions for a specific asset.

**Columns**:
- `timestamp`, `text`, `shitpost_id`
- `confidence`, `market_impact`, `thesis`
- `prediction_sentiment`
- `return_t1`, `return_t3`, `return_t7`
- `correct_t7`, `pnl_t7`
- `price_at_prediction`, `price_t7`

#### `get_predictions_with_outcomes(limit=50) -> pd.DataFrame`
Returns predictions with their validated outcomes for the table.

#### `get_sentiment_distribution() -> Dict[str, int]`
Returns count of bullish/bearish/neutral predictions.

```python
{"bullish": 45, "bearish": 30, "neutral": 25}
```

#### `get_active_assets_from_db() -> List[str]`
Returns list of assets that have prediction outcomes.

---

## Database Schema Reference

### truth_social_shitposts
```sql
CREATE TABLE truth_social_shitposts (
    shitpost_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    text TEXT,
    replies_count INTEGER,
    reblogs_count INTEGER,
    favourites_count INTEGER,
    -- ... other fields
);
```

### predictions
```sql
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    shitpost_id TEXT REFERENCES truth_social_shitposts(shitpost_id),
    assets JSONB,           -- ["AAPL", "GOOGL"]
    market_impact JSONB,    -- {"AAPL": "bullish", "GOOGL": "bearish"}
    confidence FLOAT,       -- 0.0 to 1.0
    thesis TEXT,
    analysis_status TEXT,   -- 'completed', 'bypassed', 'error'
    analysis_comment TEXT,
    created_at TIMESTAMP
);
```

### prediction_outcomes
```sql
CREATE TABLE prediction_outcomes (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id),
    symbol TEXT,
    prediction_date DATE,
    prediction_sentiment TEXT,  -- 'bullish', 'bearish', 'neutral'
    prediction_confidence FLOAT,
    prediction_timeframe_days INTEGER,

    price_at_prediction FLOAT,
    price_t1 FLOAT,
    price_t3 FLOAT,
    price_t7 FLOAT,
    price_t30 FLOAT,

    return_t1 FLOAT,  -- Percentage
    return_t3 FLOAT,
    return_t7 FLOAT,
    return_t30 FLOAT,

    correct_t1 BOOLEAN,
    correct_t3 BOOLEAN,
    correct_t7 BOOLEAN,
    correct_t30 BOOLEAN,

    pnl_t1 FLOAT,     -- Dollar amount (assumes $1000 position)
    pnl_t3 FLOAT,
    pnl_t7 FLOAT,
    pnl_t30 FLOAT,

    is_complete BOOLEAN,
    created_at TIMESTAMP
);
```

---

## Test Coverage

### Data Layer Tests (test_data.py)

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestGetPredictionStats` | 3 | Stats dict, null handling, empty results |
| `TestGetRecentSignals` | 3 | Returns DataFrame, limit, error handling |
| `TestGetPerformanceMetrics` | 4 | Metrics dict, accuracy calc, zero handling |
| `TestGetAccuracyByConfidence` | 3 | DataFrame, accuracy column, errors |
| `TestGetAccuracyByAsset` | 2 | DataFrame, limit parameter |
| `TestGetSimilarPredictions` | 3 | Asset filtering, no asset, errors |
| `TestGetPredictionsWithOutcomes` | 2 | DataFrame, limit parameter |
| `TestGetSentimentDistribution` | 2 | Distribution dict, error handling |
| `TestGetActiveAssetsFromDb` | 3 | Asset list, filters None, errors |
| `TestLoadFilteredPosts` | 3 | DataFrame, empty, limit |

### Layout Tests (test_layout.py)

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestColors` | 2 | Dict structure, valid hex |
| `TestCreateApp` | 2 | Creates Dash app, has layout |
| `TestCreateHeader` | 2 | Returns Div, contains content |
| `TestCreateFilterControls` | 2 | Returns Row, has controls |
| `TestCreateFooter` | 1 | Returns Div |
| `TestCreateMetricCard` | 3 | Returns Card, colors |
| `TestCreateSignalCard` | 8 | Various sentiment/outcome scenarios |
| `TestRegisterCallbacks` | 1 | Callbacks registered |

### Running Tests

```bash
cd shit_tests/shitty_ui
python3 -m pytest . -v
```

---

## Known Issues & Limitations

1. **No Loading States**: Components don't show loading indicators during data fetch
2. **No Error Boundaries**: Errors propagate and can crash the dashboard
3. **No Caching**: Every refresh queries the database
4. **Single Page**: No routing for dedicated pages
5. **No Time Filtering**: Can't filter by time period on charts
6. **Mobile**: Layout not optimized for mobile devices

---

## Next Steps

See the remaining planning documents for detailed implementation specs:
- [02_DASHBOARD_ENHANCEMENTS.md](./02_DASHBOARD_ENHANCEMENTS.md) - Address known issues
- [03_PERFORMANCE_PAGE.md](./03_PERFORMANCE_PAGE.md) - Add performance page
- [04_ASSET_DEEP_DIVE.md](./04_ASSET_DEEP_DIVE.md) - Add asset pages
