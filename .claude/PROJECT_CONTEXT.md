# Shitpost Alpha - Project Context

**Copy this into Claude web/phone sessions for context.**

---

## What This Project Does

Shitpost Alpha monitors Donald Trump's Truth Social posts in real-time, analyzes them with LLMs (GPT-4, Claude, Grok/xAI) to predict financial market impacts, and sends trading alerts via Telegram.

**Pipeline Flow**:
1. Truth Social API fetches new posts every 5 minutes (Railway cron)
2. Posts are stored in S3 data lake (organized by date)
3. S3 processor loads posts into PostgreSQL (Neon serverless) — dual-writes to both `truth_social_shitposts` and `signals` tables
4. LLM analyzer processes posts for financial sentiment
5. Predictions stored in database; reactive ticker lifecycle auto-backfills market prices
6. Telegram alerts dispatched to subscribers (Railway cron every 2 minutes)

**Real-world use case**: Catching market-moving posts like "CHINA TARIFFS!" or "BIG ANNOUNCEMENT!" in real-time to trade ahead of the crowd.

---

## Architecture (4-Module Pipeline)

```
┌─────────────────────────────────────┐
│  shitposts/ (Harvesting)            │
│  • TruthSocialS3Harvester           │
│  • Fetches from Truth Social API    │
│  • Stores raw JSON in S3            │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shitvault/ (Persistence)           │
│  • S3Processor                      │
│  • Loads S3 files to PostgreSQL     │
│  • Manages database CRUD            │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shitpost_ai/ (Analysis)            │
│  • ShitpostAnalyzer                 │
│  • Multi-LLM (GPT-4/Claude/Grok)   │
│  • Structured predictions           │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shit/ (Core Infrastructure)        │
│  • config/ - Environment management │
│  • content/ - Bypass service        │
│  • db/ - Database client & models   │
│  • llm/ - Multi-provider LLM client │
│  • logging/ - Service-specific logs │
│  • market_data/ - Price tracking,   │
│    outcome calc, health monitoring  │
│  • s3/ - AWS S3 operations          │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shitty_ui/ (Dashboard)             │
│  • 4-page Dash app (Dashboard,      │
│    Signals, Trends, Assets)         │
│  • Signal-over-trend charts         │
│  • Telegram alert integration       │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  notifications/ (Alerts)            │
│  • Telegram bot & sender            │
│  • Alert engine & dispatcher        │
│  • Subscriber management            │
└─────────────────────────────────────┘
```

**CRITICAL RULE**: Each module is self-contained. Don't cross boundaries.

---

## Key Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `truth_social_shitposts` | All posts (legacy, source of truth) | `shitpost_id` (unique), `content`, `text`, `timestamp`, `username`, `reblog` (JSON) |
| `signals` | Source-agnostic content model | `signal_id` (unique), `source`, `author_username`, `published_at`, `platform_data` (JSON) |
| `predictions` | LLM analysis results | `shitpost_id` (FK, nullable), `signal_id` (FK, nullable), `assets` (JSON), `market_impact` (JSON), `confidence`, `thesis`, `analysis_status` |
| `market_prices` | Historical OHLCV price data | `symbol`, `date`, `close`, `volume` |
| `prediction_outcomes` | Validated prediction accuracy | `prediction_id` (FK), `symbol`, `return_t7`, `correct_t7`, `pnl_t7` |
| `ticker_registry` | Tracked ticker symbols | `symbol` (unique), `status`, `first_seen_date`, `source_prediction_id` (FK) |
| `market_movements` | Market movements after predictions | `prediction_id` (FK), `asset`, `movement_24h`, `movement_72h` |
| `telegram_subscriptions` | Telegram bot subscribers | `chat_id` (unique), `is_active`, `alert_preferences` (JSON) |

**Important Indexes**:
- Posts by ID: `truth_social_shitposts(shitpost_id)` unique
- Posts by date: `truth_social_shitposts(timestamp)`
- Predictions by post: `predictions(shitpost_id)`
- Prices: `market_prices(symbol, date)` unique composite

---

## Configuration Management

**Environment Variables** (.env - NEVER commit):
```bash
# API Keys
SCRAPECREATORS_API_KEY=xxx  # Truth Social
OPENAI_API_KEY=xxx          # OpenAI GPT-4

# AWS S3
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_BUCKET_NAME=shitpost-alpha

# Database
DATABASE_URL=postgresql://...  # Neon PostgreSQL

# Feature Flags
FILE_LOGGING=true  # Service-specific log files
```

**Configuration Access**:
```python
from shit.config.shitpost_settings import settings
# Pydantic Settings singleton, auto-loaded from .env
api_key = settings.OPENAI_API_KEY
```

---

## Key Files

| File | Purpose |
|------|---------|
| `shitpost_alpha.py` | Main orchestrator (CLI entry point) |
| `shit/db/database_client.py` | Database session management |
| `shit/config/shitpost_settings.py` | Pydantic Settings configuration |
| `shit/llm/llm_client.py` | Multi-provider LLM client (GPT-4/Claude/Grok) |
| `shit/llm/provider_config.py` | Provider registry and model configurations |
| `shit/s3/s3_client.py` | S3 upload/download operations |
| `shit/content/bypass_service.py` | Unified bypass logic for post filtering |
| `shit/market_data/client.py` | Market price data fetcher (yfinance + Alpha Vantage) |
| `shit/market_data/ticker_registry.py` | Reactive ticker lifecycle management |
| `shit/market_data/health.py` | Market data health monitoring |
| `shitvault/shitpost_models.py` | SQLAlchemy models (TruthSocialShitpost, Prediction, etc.) |
| `shitvault/signal_models.py` | Source-agnostic Signal model |
| `shitvault/signal_operations.py` | Signal CRUD operations |
| `shitposts/base_harvester.py` | Abstract SignalHarvester base class |
| `shitposts/harvester_registry.py` | Config-driven harvester management |
| `shitposts/truth_social_s3_harvester.py` | Truth Social harvesting logic |
| `shitpost_ai/shitpost_analyzer.py` | LLM analysis orchestrator |
| `shitty_ui/app.py` | Dashboard entry point (Dash + Plotly) |
| `notifications/alert_engine.py` | Alert check-and-dispatch loop |
| `notifications/telegram_bot.py` | Telegram bot command handlers |

---

## Safety Rules

**NEVER suggest running** (production operations):
- `python shitpost_alpha.py` (without --dry-run)
- `python -m shitposts` (hits Truth Social API)
- `python -m shitvault load-database-from-s3` (processes files)
- `python -m shitpost_ai analyze` (calls OpenAI - costs money)

**SAFE to suggest** (read-only):
- `python -m shitvault stats` - Database statistics
- `python -m shitvault processing-stats` - Processing statistics
- `pytest` - Run tests
- `tail -f logs/<service>.log` - View logs

**For testing** (dry run mode):
- `python shitpost_alpha.py --mode incremental --dry-run`

---

## Current Status: Production on Railway

- **Deployment**: Railway cron jobs (orchestrator every 5 min, market data every 15 min, alerts every 2 min)
- **Database**: Neon PostgreSQL (serverless, auto-scaling)
- **Storage**: AWS S3 (organized by date)
- **LLM**: Multi-provider (GPT-4, Claude, Grok/xAI) with comparison CLI
- **Alerts**: Telegram bot with subscriber management
- **Dashboard**: 4-page Dash app (Dashboard, Signals, Trends, Assets)
- **Version**: v1.0.0

---

## Common Development Patterns

### Adding a new feature:
1. Update relevant module (shitposts/, shitvault/, shitpost_ai/)
2. Add tests in shit_tests/
3. Update CHANGELOG.md
4. Run pytest and ruff
5. Create PR with /commit-push-pr

### Debugging production issues:
1. Check logs: `tail -f logs/<service>.log`
2. Query database: `python -m shitvault stats`
3. Test locally: `python shitpost_alpha.py --dry-run`

### Testing:
- Unit tests: `pytest -m "not integration"`
- Integration tests: `pytest`
- Coverage: `pytest --cov=shit --cov-report=html`

---

## Key Design Decisions

1. **S3 as Data Lake**: All raw data stored in S3 for auditability and replay
2. **Bypass Logic**: Retruths are automatically skipped to save LLM costs
3. **Service Logging**: Each service logs to its own file for debugging
4. **Modular Architecture**: Each module can run independently via CLI
5. **Type Safety**: All functions use type hints for maintainability
6. **Error Handling**: All operations have proper try/except with logging

---

## What Makes This Project Unique

- **Real-time monitoring**: 5-minute polling interval
- **Cost optimization**: Smart bypass logic to avoid unnecessary LLM calls
- **Structured predictions**: Not just sentiment, but specific assets and timeframes
- **Audit trail**: Every post stored in S3 + database for historical analysis
- **Modular design**: Easy to swap components (different LLM, different social platform)

---

## Current Development Focus

**Completed (v1.0.0)**:
- Multi-provider LLM support (GPT-4, Claude, Grok/xAI) with comparison CLI
- Source-agnostic Signal model with dual-FK migration
- Harvester abstraction layer with registry and skeleton Twitter template
- Market data resilience (yfinance + Alpha Vantage fallback, health monitoring)
- Reactive ticker lifecycle with auto-backfill on prediction creation
- Telegram alert system deployed to production
- Dashboard UI overhaul (11 phases: signals page, trends page, tabbed analytics, smart empty states, etc.)
- 1400+ tests with comprehensive coverage

**Planned**:
- Multi-source signal aggregation (Twitter/X, RSS)
- Ensemble models with multiple LLMs
- Monetization features

See [CHANGELOG.md](../CHANGELOG.md) for version history.
