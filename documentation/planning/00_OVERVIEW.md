# Shitpost Alpha Dashboard - Development Planning Overview

## Executive Summary

This document outlines the development roadmap for the Shitpost Alpha prediction performance dashboard. The project analyzes Trump's Truth Social posts using LLMs to generate market predictions, then tracks those predictions against actual market outcomes.

**Current State**: Phase 0.2 complete. Dashboard deployed to Railway with Neon PostgreSQL. Significant code has been written for Phases 1-3 (Asset Deep Dive pages, Alert System, Data Layer Expansion), but the **UI is largely non-functional in production** due to critical data pipeline gaps and untested integration paths.

**Goal**: Stabilize the existing dashboard, fill data pipeline gaps, and deliver a working end-to-end experience: posts -> LLM analysis -> predictions -> market data -> validated outcomes -> user-facing dashboard.

---

## Document Index

| Document | Purpose | Priority | Status |
|----------|---------|----------|--------|
| [01_CURRENT_STATE.md](./01_CURRENT_STATE.md) | Architecture reference | Reference | Needs Update |
| [02_DASHBOARD_ENHANCEMENTS.md](./02_DASHBOARD_ENHANCEMENTS.md) | Immediate UI improvements | P0 | COMPLETE |
| [03_PERFORMANCE_PAGE.md](./03_PERFORMANCE_PAGE.md) | New /performance route | P1 | Pending |
| [04_ASSET_DEEP_DIVE.md](./04_ASSET_DEEP_DIVE.md) | New /assets/{symbol} pages | P1 | Code Written, Not Deployed |
| [05_SIGNAL_FEED.md](./05_SIGNAL_FEED.md) | Real-time signal feed | P2 | Pending |
| [06_ALERTING_SYSTEM.md](./06_ALERTING_SYSTEM.md) | Push notifications | P2 | Code Written, Not Tested E2E |
| [07_DATA_LAYER_EXPANSION.md](./07_DATA_LAYER_EXPANSION.md) | New queries & caching | P1 | COMPLETE |
| [08_TESTING_STRATEGY.md](./08_TESTING_STRATEGY.md) | Test coverage plan | P0 | In Progress |
| [09_DEPLOYMENT_GUIDE.md](./09_DEPLOYMENT_GUIDE.md) | Railway deployment | COMPLETE | COMPLETE |
| **[UI_SYSTEM_ANALYSIS.md](../UI_SYSTEM_ANALYSIS.md)** | **Bug & gap analysis** | **P0** | **NEW** |

---

## Critical Status: UI Layer Dysfunction

> **The UI is extremely buggy and largely non-functional.** The core user experience -- seeing posts, LLM analysis, directional predictions, and actual stock performance -- does not work end-to-end. The visible symptoms are:
>
> 1. Only a small feed of old Truth Social posts loads
> 2. LLM feedback and directional predictions do not render
> 3. Actual stock performance data is absent or incomplete
> 4. Most dashboard sections display empty states or error cards
>
> See **[UI_SYSTEM_ANALYSIS.md](../UI_SYSTEM_ANALYSIS.md)** for the full root cause analysis.

### Root Causes (Summary)

1. **Data Pipeline Gaps**: Only 14 of ~187 assets have price data; only 9 prediction outcomes exist; the `prediction_outcomes` table is nearly empty
2. **Schema Mismatch**: `data.py` queries column names (`text`, `shitpost_id`, `timestamp`) that differ from the SQLAlchemy models (`body`, `id`, `created_at`)
3. **Feature Code Without Data**: Asset Deep Dive, Performance Metrics, and Alert System code is written but queries return empty results because the underlying data hasn't been backfilled
4. **No Integration Testing**: 973 unit tests pass, but zero end-to-end tests verify that the dashboard actually renders with real data
5. **Stale Documentation**: Planning docs report features as "Pending" that have been partially coded, and report "Known Issues" that have already been fixed

---

## Development Phases (Revised)

### Phase 0: Stabilization (CRITICAL - NOW)
**Goal**: Make the existing dashboard functional with real data

1. **Data Pipeline Repair**
   - [ ] Backfill `market_prices` for all ~187 assets with predictions
   - [ ] Run outcome calculator to populate `prediction_outcomes` for all historical predictions
   - [ ] Verify `prediction_outcomes` has sufficient data for dashboard queries

2. **Schema Alignment Audit**
   - [ ] Verify `data.py` SQL queries match actual database column names
   - [ ] Reconcile `truth_social_shitposts` column naming (SQL queries use `text`/`timestamp`, models use `body`/`created_at`)
   - [ ] Test each `data.py` function against the production database

3. **Smoke Test the Dashboard**
   - [ ] Verify each dashboard section loads with real data
   - [ ] Fix any runtime errors in callbacks
   - [ ] Confirm the post feed displays recent posts with LLM analysis

### Phase 1: Dashboard Polish (Week 1-2)
**Goal**: Complete the core dashboard experience

> **STATUS: PARTIALLY COMPLETE** - Dashboard enhancements done, data layer expansion complete, testing in progress.

1. **Dashboard Enhancements** (02_DASHBOARD_ENHANCEMENTS.md) COMPLETE
   - Loading states, error handling, chart interactivity, time period selectors, mobile responsiveness, refresh indicator

2. **Data Layer** (07_DATA_LAYER_EXPANSION.md) - COMPLETE
   - TTL caching, time-filtered queries, aggregate functions, connection pooling

3. **Testing** (08_TESTING_STRATEGY.md) - IN PROGRESS
   - 67 UI-specific tests (test_data.py: 34, test_layout.py: 33)
   - 83 alert/telegram tests added
   - **Gap**: No integration tests against real database; no E2E smoke tests

### Phase 2: Multi-Page Application (Week 3-4)
**Goal**: Add dedicated pages for deeper analysis

1. **Asset Deep Dive** (04_ASSET_DEEP_DIVE.md) - CODE WRITTEN, NEEDS DATA + TESTING
   - `/assets/{symbol}` routing implemented in `layout.py`
   - Candlestick charts, prediction overlays, related assets implemented
   - `data.py` functions exist: `get_asset_price_history()`, `get_asset_predictions()`, `get_asset_stats()`, `get_related_assets()`
   - **Blocked by**: Empty `market_prices` and `prediction_outcomes` tables

2. **Performance Page** (03_PERFORMANCE_PAGE.md) - PENDING
   - Equity curve, drawdown analysis, win/loss streaks
   - Data layer functions already built (07): `get_cumulative_pnl()`, `get_rolling_accuracy()`, `get_win_loss_streaks()`, `get_confidence_calibration()`, `get_monthly_performance()`
   - **Needs**: New `/performance` route and page components

3. **Signal Feed** (05_SIGNAL_FEED.md) - PENDING
   - Chronological signal feed with filters and pagination
   - Partial: "Recent Signals" section on main page exists (10 items)

### Phase 3: Real-Time & Alerts (Week 5-6)
**Goal**: Enable proactive user engagement

1. **Alerting System** (06_ALERTING_SYSTEM.md) - CODE WRITTEN, NEEDS E2E TESTING
   - `alerts.py` (716 lines): Email (SMTP/SendGrid), SMS (Twilio), browser notifications
   - `telegram_bot.py` (806 lines): Multi-tenant Telegram bot
   - Alert config panel in `layout.py` with localStorage persistence
   - 83 tests for alerts + telegram modules
   - **Needs**: E2E testing with real notifications; environment config for SMTP/Twilio/Telegram

2. **Real-Time Updates**
   - Auto-refresh (5min) already implemented
   - [ ] WebSocket integration (stretch goal)
   - [ ] Visual indicators for new signals

### Phase 4: Production Hardening (Week 7-8)
**Goal**: Optimize production deployment

> **NOTE**: Basic deployment is complete. Dashboard and scraping services are live on Railway with Neon PostgreSQL.

1. **Deployment** (09_DEPLOYMENT_GUIDE.md) - BASIC COMPLETE
2. **Performance Optimization** - PARTIAL (connection pooling done; CDN, query optimization pending)

---

## Tech Stack Reference

### Current Stack
```
Frontend:     Plotly Dash + Bootstrap Components (dark theme)
Styling:      Inline Python CSS (Tailwind-inspired Slate palette)
Backend:      Python 3.13 + SQLAlchemy (sync for dashboard)
Database:     Neon PostgreSQL (serverless)
Market Data:  Yahoo Finance (yfinance)
Deployment:   Railway (2 services: orchestrator + dashboard)
Testing:      pytest (973 total tests; 67 UI-specific)
```

### Key Files (Updated)
```
shitty_ui/
├── app.py              # Entry point, server config (25 lines)
├── layout.py           # Components, callbacks, styling (~3,862 lines)
├── data.py             # Database queries (20+ functions, ~1,360 lines)
├── alerts.py           # Alert dispatch logic (716 lines)
├── telegram_bot.py     # Telegram bot integration (806 lines)
└── README.md           # Module documentation

shit_tests/shitty_ui/
├── __init__.py
├── conftest.py         # Test fixtures and mocks
├── test_data.py        # Data layer tests (34 tests)
├── test_layout.py      # Layout component tests (33 tests)
├── test_alerts.py      # Alert system tests
└── test_telegram.py    # Telegram bot tests
```

### Database Tables Used
```sql
truth_social_shitposts  -- Posts from Truth Social (~28,000 rows)
predictions             -- LLM analysis results (~2,983 rows)
prediction_outcomes     -- Validated outcomes with returns (~9 rows!) <-- CRITICAL GAP
market_prices           -- Historical OHLCV data (~528 rows, 14 assets) <-- CRITICAL GAP
```

---

## Implementation Priorities (Revised)

### Must Have (P0)
- [ ] **Backfill market data pipeline** - Without this, the dashboard is empty
- [ ] **Verify SQL queries match schema** - Potential column name mismatches
- [ ] **E2E smoke test** - Verify dashboard renders with real data
- [x] Loading states for all data-dependent components
- [x] Error boundaries and graceful degradation
- [x] Mobile-responsive layout
- [x] Time period filtering (7d, 30d, 90d)
- [x] Production deployment on Railway

### Should Have (P1)
- [ ] Performance page with equity curve (data layer ready)
- [x] Asset detail pages (code written, needs data)
- [x] Click-to-filter on charts
- [ ] Data export (CSV)
- [x] Query caching (TTL cache implemented)

### Nice to Have (P2)
- [x] Signal feed with real-time updates (partial: 10 recent signals)
- [x] Browser notifications (code written)
- [ ] Dark/light theme toggle
- [ ] Shareable URLs with state

### Future (P3)
- [x] SMS alerts via Twilio (code written, needs config)
- [ ] WebSocket real-time updates
- [ ] User accounts and preferences
- [ ] API for external integrations

---

## Success Metrics

### Dashboard Quality
- Page load time < 2 seconds
- No unhandled errors in production
- **All dashboard sections render with data** (currently failing)
- Mobile usability score > 90

### Prediction Performance Visibility
- Users can see accuracy at a glance
- Users can drill into any asset
- Users can understand confidence calibration
- **Users can see actual stock performance next to predictions** (currently missing)

### User Engagement
- Time on dashboard > 2 minutes average
- Return visits > 50% of users
- Alert subscription rate > 20%

---

## Questions & Support

- **Architecture questions**: Review [01_CURRENT_STATE.md](./01_CURRENT_STATE.md)
- **Bug analysis**: Review [UI_SYSTEM_ANALYSIS.md](../UI_SYSTEM_ANALYSIS.md)
- **Implementation questions**: Check code examples in each planning doc
- **Bug reports**: Create issue in GitHub with reproduction steps
