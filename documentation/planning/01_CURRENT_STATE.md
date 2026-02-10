# Current State - Dashboard Architecture Reference [COMPLETED]

## Overview

This document describes the current implementation of the Shitpost Alpha dashboard as of the latest review (2026-02-06). Use this as a reference when implementing new features.

> **Deployment Status**: Live on Railway with Neon PostgreSQL database. Both dashboard and scraping services are operational. However, **the UI is largely non-functional** due to data pipeline gaps. See [UI_SYSTEM_ANALYSIS.md](../UI_SYSTEM_ANALYSIS.md).

---

## Directory Structure

> **Updated 2026-02-06** - Reflects all implemented features including alerts and asset deep dive.

```
shitty_ui/
├── app.py              # Application entry point (25 lines)
├── layout.py           # Layout components and callbacks (~3,862 lines)
├── data.py             # Database query functions (20+ functions, ~1,360 lines)
├── alerts.py           # Alert checking and dispatch (716 lines)
├── telegram_bot.py     # Telegram bot integration (806 lines)
└── README.md           # Module documentation

shit_tests/shitty_ui/
├── __init__.py
├── conftest.py         # Test configuration and mocks
├── test_data.py        # Data layer tests (34 tests)
├── test_layout.py      # Layout component tests (33 tests)
├── test_alerts.py      # Alert system tests
└── test_telegram.py    # Telegram bot tests
```

**Total UI-specific tests: ~150** (67 data+layout + 83 alerts+telegram)

---

## Application Entry Point

**File**: `shitty_ui/app.py`

```python
from layout import create_app, register_callbacks

def serve_app():
    app = create_app()
    register_callbacks(app)
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
```

**Key Points**:
- `create_app()` builds the Dash app with the main layout (URL router + stores)
- `register_callbacks()` adds all interactive behavior (~20 callbacks)
- Server runs on port 8050 by default (Railway provides `$PORT`)

---

## Layout Architecture

**File**: `shitty_ui/layout.py` (~3,862 lines)

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

### Layout Hierarchy (Current)

```
App Layout (create_app)
├── dcc.Location (URL routing)
├── dcc.Interval x3 (refresh, countdown, alert-check)
├── dcc.Store x6 (selected-asset, selected-period, last-update, alert-prefs, etc.)
├── Alert Config Offcanvas (slide-out panel)
└── Page Content (id="page-content") -- swapped by router callback
    │
    ├── Dashboard Page (/) -- create_dashboard_page()
    │   ├── Header (create_header)
    │   │   ├── Title: "Shitpost Alpha"
    │   │   ├── Alert bell icon with badge
    │   │   └── Refresh indicator with countdown
    │   │
    │   ├── Time Period Selector (7D / 30D / 90D / All)
    │   │
    │   ├── Performance Metrics Row (id="performance-metrics")
    │   │   ├── Prediction Accuracy Card
    │   │   ├── Total P&L Card
    │   │   ├── Avg Return Card
    │   │   └── Predictions Evaluated Card
    │   │
    │   ├── Two-Column Layout (dbc.Row)
    │   │   ├── Left Column (md=7)
    │   │   │   ├── Accuracy by Confidence Chart
    │   │   │   └── Performance by Asset Chart (click to drill down)
    │   │   │
    │   │   └── Right Column (md=5)
    │   │       ├── Recent Signals Card (10 items)
    │   │       └── Asset Deep Dive Card
    │   │           ├── Dropdown selector
    │   │           └── Historical predictions content
    │   │
    │   ├── Collapsible Data Table
    │   │   ├── Filter Controls (confidence, dates, limit)
    │   │   └── DataTable with conditional formatting
    │   │
    │   ├── Alert History Panel (collapsible)
    │   └── Footer (disclaimer + GitHub link)
    │
    └── Asset Page (/assets/{symbol}) -- create_asset_page()
        ├── Asset Header (back link, symbol, current price)
        ├── Stat Cards Row (accuracy, total predictions, P&L, avg return)
        ├── Two-Column Layout
        │   ├── Left (md=8): Candlestick Price Chart with prediction overlays
        │   └── Right (md=4): Performance Summary + Related Assets
        ├── Prediction Timeline (scrollable)
        └── Footer
```

### Key Component Functions

| Function | Returns | Purpose |
|----------|---------|---------|
| `create_app()` | `Dash` | Initialize app with stores, intervals, layout |
| `create_dashboard_page()` | `html.Div` | Main dashboard page content |
| `create_asset_page(symbol)` | `html.Div` | Asset deep dive page content |
| `create_header()` | `html.Div` | Header with alert bell and refresh timer |
| `create_metric_card(...)` | `dbc.Card` | Single KPI metric card |
| `create_signal_card(row)` | `html.Div` | Recent signal display card |
| `create_prediction_timeline_card(row)` | `html.Div` | Asset page prediction entry |
| `create_related_asset_link(row)` | `html.Div` | Related asset clickable link |
| `create_performance_summary(stats)` | `html.Div` | Asset vs overall comparison |
| `create_error_card(msg, details)` | `dbc.Card` | Error state display |
| `create_empty_chart(msg)` | `go.Figure` | Empty chart placeholder |
| `create_filter_controls()` | `dbc.Row` | Table filter inputs |
| `create_alert_config_panel()` | `dbc.Offcanvas` | Alert settings slide-out |
| `create_alert_history_panel()` | `dbc.Card` | Alert history collapsible |
| `create_footer()` | `html.Div` | Footer with disclaimer |

### Callbacks (~20 total)

| Callback | Trigger | Purpose |
|----------|---------|---------|
| `route_page` | URL change | Route to dashboard or asset page |
| `update_period_selection` | Period button clicks | Track selected time period |
| `update_dashboard` | Refresh interval + period | Main data fetch and render |
| `handle_asset_chart_click` | Chart click | Select asset from bar chart |
| `update_asset_drilldown` | Asset selector | Show historical predictions |
| `toggle_collapse` | Table button click | Toggle data table |
| `update_predictions_table` | Table open + filters | Fetch and render table |
| `update_asset_page` | Asset page symbol | Populate asset page sections |
| `update_asset_price_chart` | Symbol + range buttons | Render candlestick chart |
| `update_asset_range_buttons` | Range button clicks | Style active range button |
| `toggle_alert_config` | Bell icon click | Open/close alert panel |
| `toggle_email_input` | Email toggle | Show/hide email input |
| `toggle_sms_input` | SMS toggle | Show/hide SMS input |
| `toggle_quiet_hours` | Quiet hours toggle | Show/hide time inputs |
| `update_confidence_display` | Confidence slider | Display percentage |
| `update_alert_status` | Master toggle | Show active/inactive |
| `populate_alert_assets` | Panel open | Load assets from DB |
| `save_alert_preferences` | Save button | Persist to localStorage |
| `load_preferences_into_form` | Panel open | Load from localStorage |
| `run_alert_check` | Alert interval | Check for new predictions |
| `render_alert_history` | History data change | Render alert cards |
| `clear_alert_history` | Clear button | Reset localStorage |
| Clientside: countdown | 1s interval | Refresh countdown timer |
| Clientside: browser notification | Alert data | Show OS notification |
| Clientside: test alert | Test button | Send test notification |
| Clientside: badge count | History data | Update bell badge |

---

## Data Layer

**File**: `shitty_ui/data.py` (~1,360 lines)

### Database Connection

```python
from shit.config.shitpost_settings import settings
DATABASE_URL = settings.DATABASE_URL

# Convert async URL to sync for Dash
sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
engine = create_engine(sync_url, pool_size=5, max_overflow=10, pool_recycle=1800)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

### Query Functions

| Function | Cache | Returns | Purpose |
|----------|-------|---------|---------|
| `load_recent_posts(limit)` | No | DataFrame | Posts with predictions (LEFT JOIN) |
| `load_filtered_posts(...)` | No | DataFrame | Posts with advanced filters |
| `get_available_assets()` | No | List[str] | **Hardcoded list** (not from DB) |
| `get_prediction_stats()` | 5 min | Dict | Basic prediction counts |
| `get_recent_signals(limit, min_conf, days)` | No | DataFrame | Signals with outcomes |
| `get_performance_metrics(days)` | 5 min | Dict | Accuracy, P&L, returns |
| `get_accuracy_by_confidence(days)` | 5 min | DataFrame | Confidence level breakdown |
| `get_accuracy_by_asset(limit, days)` | 5 min | DataFrame | Per-asset accuracy |
| `get_similar_predictions(asset, limit, days)` | No | DataFrame | Historical predictions for asset |
| `get_predictions_with_outcomes(limit, days)` | No | DataFrame | Full table data |
| `get_sentiment_distribution(days)` | 5 min | Dict | Bullish/bearish/neutral counts |
| `get_active_assets_from_db()` | 10 min | List[str] | Assets with actual outcomes |
| `get_cumulative_pnl(days)` | No | DataFrame | Equity curve data |
| `get_rolling_accuracy(window, days)` | No | DataFrame | Rolling accuracy over time |
| `get_win_loss_streaks()` | No | Dict | Current and max streaks |
| `get_confidence_calibration(buckets)` | No | DataFrame | Predicted vs actual accuracy |
| `get_monthly_performance(months)` | No | DataFrame | Monthly P&L summary |
| `get_asset_price_history(symbol, days)` | No | DataFrame | OHLCV from market_prices |
| `get_asset_predictions(symbol, limit)` | No | DataFrame | Predictions for specific asset |
| `get_asset_stats(symbol)` | 5 min | Dict | Per-asset aggregate stats |
| `get_related_assets(symbol, limit)` | No | DataFrame | Co-occurring assets |
| `get_new_predictions_since(since)` | No | List[Dict] | New predictions for alerts |
| `clear_all_caches()` | N/A | None | Invalidate all TTL caches |

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
    -- ... other fields (45+ columns in SQLAlchemy model)
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
    prediction_sentiment TEXT,
    prediction_confidence FLOAT,
    price_at_prediction FLOAT,
    price_t1 FLOAT, price_t3 FLOAT, price_t7 FLOAT, price_t30 FLOAT,
    return_t1 FLOAT, return_t3 FLOAT, return_t7 FLOAT, return_t30 FLOAT,
    correct_t1 BOOLEAN, correct_t3 BOOLEAN, correct_t7 BOOLEAN, correct_t30 BOOLEAN,
    pnl_t1 FLOAT, pnl_t3 FLOAT, pnl_t7 FLOAT, pnl_t30 FLOAT,
    is_complete BOOLEAN,
    created_at TIMESTAMP
);
```

### market_prices
```sql
CREATE TABLE market_prices (
    id SERIAL PRIMARY KEY,
    symbol TEXT,
    date DATE,
    open FLOAT, high FLOAT, low FLOAT, close FLOAT,
    volume BIGINT,
    adjusted_close FLOAT
);
```

---

## Known Issues & Current Limitations

### Critical (Blocking UI)

1. **Near-empty `prediction_outcomes` table** (~9 rows) - Most dashboard queries return no data
2. **Sparse `market_prices` table** (~528 rows, 14 assets) - Asset deep dive pages show empty charts
3. **Potential column name mismatch** - `data.py` queries reference `text`, `timestamp`, `shitpost_id` but SQLAlchemy model uses `body`, `created_at`, `id`
4. **`get_available_assets()` returns hardcoded list** - Not queried from database

### Moderate

5. **3,862-line `layout.py` monolith** - Hard to navigate and maintain; should be split into page modules
6. **No `/performance` page** - Data layer functions exist but no route or components
7. **Alert system untested E2E** - Code written but never verified with real SMTP/Twilio/Telegram
8. **`load_recent_posts()` and `load_filtered_posts()` not used by any callback** - Dead code in data layer

### Low Priority

9. **No data export functionality** (CSV/JSON)
10. **No dark/light theme toggle**
11. **No WebSocket for real-time updates** (polling every 5 min is fine for now)

---

## Next Steps

1. **Execute Phase 0 (Stabilization)** - Fill data pipeline gaps and verify queries
2. **Build `/performance` page** - Data functions already exist, need components
3. **Split `layout.py`** - Extract pages into `pages/dashboard.py`, `pages/assets.py`, `pages/performance.py`

See [00_OVERVIEW.md](./00_OVERVIEW.md) for the full development roadmap.
See [UI_SYSTEM_ANALYSIS.md](../UI_SYSTEM_ANALYSIS.md) for detailed bug and gap analysis.
