# Shitpost Alpha Dashboard - Development Planning Overview

## Executive Summary

This document outlines the development roadmap for the Shitpost Alpha prediction performance dashboard. The project analyzes Trump's Truth Social posts using LLMs to generate market predictions, then tracks those predictions against actual market outcomes.

**Current State**: Phase 0.2 complete - core dashboard redesigned with performance focus. **Already deployed to Railway with Neon PostgreSQL database.**

**Goal**: Enhance the production dashboard to enable users to understand prediction performance, drill into specific assets, and receive actionable trading signals.

---

## Document Index

| Document | Purpose | Priority | Estimated Effort |
|----------|---------|----------|------------------|
| [01_CURRENT_STATE.md](./01_CURRENT_STATE.md) | Architecture reference | Reference | - |
| [02_DASHBOARD_ENHANCEMENTS.md](./02_DASHBOARD_ENHANCEMENTS.md) | Immediate UI improvements | P0 | 2-3 days |
| [03_PERFORMANCE_PAGE.md](./03_PERFORMANCE_PAGE.md) | New /performance route | P1 | 3-4 days |
| [04_ASSET_DEEP_DIVE.md](./04_ASSET_DEEP_DIVE.md) | New /assets/{symbol} pages | P1 | 3-4 days |
| [05_SIGNAL_FEED.md](./05_SIGNAL_FEED.md) | Real-time signal feed | P2 | 2-3 days |
| [06_ALERTING_SYSTEM.md](./06_ALERTING_SYSTEM.md) | Push notifications | P2 | 4-5 days |
| [07_DATA_LAYER_EXPANSION.md](./07_DATA_LAYER_EXPANSION.md) | New queries & caching | P1 | 2-3 days |
| [08_TESTING_STRATEGY.md](./08_TESTING_STRATEGY.md) | Test coverage plan | P0 | Ongoing |
| [09_DEPLOYMENT_GUIDE.md](./09_DEPLOYMENT_GUIDE.md) | Railway deployment | ✅ COMPLETE | - |

---

## Development Phases

### Phase 1: Dashboard Polish (Week 1-2)
**Goal**: Complete the core dashboard experience

1. **Dashboard Enhancements** (02_DASHBOARD_ENHANCEMENTS.md)
   - Add loading states and error handling
   - Improve chart interactivity (click to filter)
   - Add time period selectors (7d, 30d, 90d, All)
   - Mobile responsiveness improvements

2. **Data Layer** (07_DATA_LAYER_EXPANSION.md)
   - Add caching for expensive queries
   - Create time-filtered query variants
   - Add aggregate statistics functions

3. **Testing** (08_TESTING_STRATEGY.md)
   - Achieve 80%+ test coverage
   - Add integration tests
   - Set up CI pipeline

### Phase 2: Multi-Page Application (Week 3-4)
**Goal**: Add dedicated pages for deeper analysis

1. **Performance Page** (03_PERFORMANCE_PAGE.md)
   - Detailed backtesting results
   - Equity curve visualization
   - Drawdown analysis
   - Win/loss streaks

2. **Asset Deep Dive** (04_ASSET_DEEP_DIVE.md)
   - Individual asset pages (/assets/AAPL)
   - Price chart with prediction overlays
   - Historical prediction timeline
   - Asset-specific accuracy metrics

3. **Signal Feed** (05_SIGNAL_FEED.md)
   - Chronological signal list
   - Real-time updates via polling
   - Filtering by confidence/sentiment
   - Export functionality

### Phase 3: Real-Time & Alerts (Week 5-6)
**Goal**: Enable proactive user engagement

1. **Alerting System** (06_ALERTING_SYSTEM.md)
   - Browser push notifications
   - Email alerts (optional)
   - SMS alerts via Twilio (premium)
   - Alert configuration UI

2. **Real-Time Updates**
   - WebSocket integration (stretch goal)
   - More frequent polling
   - Visual indicators for new signals

### Phase 4: Production Hardening (Week 7-8)
**Goal**: Optimize production deployment

> **NOTE**: Basic deployment is already complete. Dashboard and scraping services are live on Railway with Neon PostgreSQL.

1. **Deployment Enhancements** (09_DEPLOYMENT_GUIDE.md) - ✅ BASIC COMPLETE
   - ✅ Railway configuration
   - ✅ Environment management
   - [ ] Monitoring setup (optional enhancement)
   - [ ] Error tracking (optional enhancement)

2. **Performance Optimization**
   - Query optimization
   - Connection pooling
   - Response caching
   - CDN for static assets

---

## Tech Stack Reference

### Current Stack
```
Frontend:     Plotly Dash + Bootstrap Components
Styling:      Custom CSS (Tailwind-inspired color palette)
Backend:      Python 3.13 + SQLAlchemy
Database:     Neon PostgreSQL (serverless)
Deployment:   Railway
Testing:      pytest
```

### Key Files
```
shitty_ui/
├── app.py          # Entry point, server config
├── layout.py       # Components, callbacks, styling
├── data.py         # Database queries
└── README.md       # Module documentation

shit_tests/shitty_ui/
├── conftest.py     # Test fixtures
├── test_data.py    # Data layer tests (28 tests)
└── test_layout.py  # Layout component tests (21 tests)
```

### Database Tables Used
```sql
truth_social_shitposts  -- Posts from Truth Social
predictions             -- LLM analysis results
prediction_outcomes     -- Validated outcomes with returns
market_prices           -- Historical OHLCV data
```

---

## Implementation Priorities

### Must Have (P0)
- [ ] Loading states for all data-dependent components
- [ ] Error boundaries and graceful degradation
- [ ] Mobile-responsive layout
- [ ] Time period filtering (7d, 30d, 90d)
- [ ] 80%+ test coverage
- [x] Production deployment on Railway ✅

### Should Have (P1)
- [ ] Performance page with equity curve
- [ ] Asset detail pages
- [ ] Click-to-filter on charts
- [ ] Data export (CSV)
- [ ] Query caching

### Nice to Have (P2)
- [ ] Signal feed with real-time updates
- [ ] Browser notifications
- [ ] Dark/light theme toggle
- [ ] Shareable URLs with state

### Future (P3)
- [ ] SMS alerts via Twilio
- [ ] WebSocket real-time updates
- [ ] User accounts and preferences
- [ ] API for external integrations

---

## Getting Started

### For New Developers

1. **Read the current state document first**: [01_CURRENT_STATE.md](./01_CURRENT_STATE.md)
2. **Set up local development**:
   ```bash
   cd /home/user/shitpost-alpha
   pip install -r requirements.txt
   cp .env.example .env  # Configure DATABASE_URL
   cd shitty_ui && python app.py
   ```
3. **Run tests**:
   ```bash
   cd shit_tests/shitty_ui && python3 -m pytest . -v
   ```
4. **Pick a task** from the appropriate planning document based on current phase

### Code Style
- Follow existing patterns in `layout.py` and `data.py`
- Use type hints for all function signatures
- Write tests for all new functions
- Update CHANGELOG.md for all changes

### PR Process
1. Create feature branch from `main`
2. Implement feature with tests
3. Run `ruff check .` and `ruff format .`
4. Update CHANGELOG.md
5. Create PR with description of changes

---

## Success Metrics

### Dashboard Quality
- Page load time < 2 seconds
- No unhandled errors in production
- Mobile usability score > 90

### Prediction Performance Visibility
- Users can see accuracy at a glance
- Users can drill into any asset
- Users can understand confidence calibration

### User Engagement
- Time on dashboard > 2 minutes average
- Return visits > 50% of users
- Alert subscription rate > 20%

---

## Questions & Support

- **Architecture questions**: Review [01_CURRENT_STATE.md](./01_CURRENT_STATE.md)
- **Implementation questions**: Check code examples in each planning doc
- **Bug reports**: Create issue in GitHub with reproduction steps
- **Feature requests**: Discuss in planning documents before implementing
