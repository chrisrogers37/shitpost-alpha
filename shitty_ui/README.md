# Shitpost Alpha - Prediction Performance Dashboard

**Multi-page Dash application for visualizing prediction performance, market signals, and trading analytics.**

## Overview

The Shitpost Alpha dashboard is a 4-page single-page application built with Plotly Dash and Bootstrap. It provides real-time prediction performance monitoring, signal-over-trend market charts, and asset-level deep dives with a professional dark-themed trading platform design.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | KPI cards, tabbed analytics (accuracy, confidence, asset performance), recent predictions & posts |
| `/signals` | Signals | Filterable signal feed with sentiment-colored cards and confidence badges |
| `/trends` | Trends | Candlestick price charts with prediction signal overlays and time range controls |
| `/assets/<symbol>` | Asset Deep Dive | Per-asset prediction history with price chart and outcome tracking |

## Directory Structure

```
shitty_ui/
├── app.py              # Dash app entry point, Flask server & endpoints
├── layout.py           # App factory, URL router & callback registration
├── data.py             # Database query functions (2000+ lines)
├── constants.py        # Colors, typography, spacing tokens, sentiment config
├── alerts.py           # Alert preference defaults
├── telegram_bot.py     # Telegram bot integration
├── pages/              # Page layout modules
│   ├── dashboard.py    # Main dashboard with tabbed analytics
│   ├── signals.py      # Signal feed with filtering
│   ├── trends.py       # Signal-over-trend candlestick charts
│   └── assets.py       # Asset deep dive page
├── components/         # Reusable UI components
│   ├── cards.py        # Signal, prediction, metric & feed cards
│   ├── charts.py       # Candlestick charts with prediction overlays
│   ├── controls.py     # Period selector & filter controls
│   └── header.py       # Navigation header with active link highlighting
└── callbacks/          # Callback groups
    └── alerts.py       # Alert configuration panel & checking
```

## Key Features

- **Dashboard KPIs** - Accuracy rate, total P&L, average return, evaluated predictions count
- **Tabbed Analytics** - Accuracy over time, accuracy by confidence, performance by asset (switchable views)
- **Signal Feed** - Sentiment-colored cards (green=bullish, red=bearish, gray=neutral) with 3px left borders
- **Signal-Over-Trend Charts** - Plotly candlestick charts with prediction markers scaled by confidence
- **Asset Deep Dive** - Click any asset bar chart to navigate to `/assets/<ticker>` for full history
- **Smart Empty States** - Compact 80px informative messages when data is missing
- **Collapsible Sections** - Chevron icons with rotation animation for expand/collapse
- **Telegram Alerts** - Alert configuration panel with subscriber management
- **Auto-refresh** - 5-minute polling interval
- **Dark Theme** - Professional design with consistent typography scale and spacing tokens

## Setup

### Prerequisites

- Python 3.13+
- Access to the Shitpost Alpha PostgreSQL database
- Market data and prediction outcomes populated

### Running Locally

```bash
# From project root
source venv/bin/activate
cd shitty_ui && python app.py
# Open http://localhost:8050
```

### Deployment on Railway

The dashboard runs as a Railway service. Environment variables required:
- `DATABASE_URL` - Neon PostgreSQL connection string

Live at: `https://shitpost-alpha-dash.up.railway.app`

## Architecture

- **Frontend**: Plotly Dash with Dash Bootstrap Components (dark theme)
- **Backend**: Synchronous SQLAlchemy with PostgreSQL
- **Server**: Flask (Dash's underlying server) with additional endpoints:
  - `POST /telegram/webhook` - Telegram bot webhook
  - `GET /telegram/health` - Telegram system health check
- **Data Tables**: `truth_social_shitposts`, `predictions`, `prediction_outcomes`, `market_prices`, `signals`

### Key Data Functions (`data.py`)

| Function | Used By | Description |
|----------|---------|-------------|
| `get_dashboard_kpis()` | Dashboard | Evaluated prediction metrics |
| `get_performance_metrics()` | Dashboard | Accuracy and P&L summary |
| `get_accuracy_by_confidence()` | Dashboard, Performance | Calibration by confidence level |
| `get_accuracy_by_asset()` | Dashboard | Per-ticker accuracy |
| `get_recent_signals()` | Dashboard, Signals | Latest predictions with outcomes |
| `get_price_with_signals()` | Trends, Assets | OHLCV prices joined with prediction signals |
| `get_similar_predictions()` | Assets | Historical predictions for a specific asset |

### Component Patterns

**Cards** (`components/cards.py`): All card types use sentiment-aware styling via `get_sentiment_style()` helper. Backgrounds and left-border accents are driven by `SENTIMENT_BG_COLORS` in `constants.py`.

**Charts** (`components/charts.py`): `build_signal_over_trend_chart()` is shared between the Trends page and Asset page. Markers are color-coded by sentiment and sized by confidence (8-22px).

**Constants** (`constants.py`): Centralized `COLORS`, `FONT_SIZES`, `FONT_WEIGHTS`, `SPACING`, `SENTIMENT_COLORS`, `MARKER_CONFIG`, and `TIMEFRAME_COLORS` dictionaries.

## Troubleshooting

1. **No Performance Data** - Run market data backfill: `python -m shit.market_data auto-pipeline --days-back 30`
2. **Charts Empty** - Verify `prediction_outcomes` has records with `correct_t7` populated
3. **Database Connection** - Check `DATABASE_URL` in `.env`

## Related Documentation

- [Market Data Architecture](../documentation/MARKET_DATA_ARCHITECTURE.md)
- [Telegram Setup Guide](../documentation/TELEGRAM_SETUP_GUIDE.md)
- [CHANGELOG](../CHANGELOG.md)
