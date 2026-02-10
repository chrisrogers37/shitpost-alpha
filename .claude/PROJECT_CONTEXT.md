# Shitpost Alpha - Project Context

**Copy this into Claude web/phone sessions for context.**

---

## What This Project Does

Shitpost Alpha monitors Donald Trump's Truth Social posts in real-time, analyzes them with GPT-4 to predict financial market impacts, and provides trading alerts.

**Pipeline Flow**:
1. Truth Social API fetches new posts every 5 minutes (Railway cron)
2. Posts are stored in S3 data lake (organized by date)
3. S3 processor loads posts into PostgreSQL (Neon serverless)
4. LLM analyzer processes posts for financial sentiment
5. Predictions are stored back in database with confidence scores

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
│  • GPT-4 financial sentiment        │
│  • Structured predictions           │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shit/ (Core Infrastructure)        │
│  • config/ - Environment management │
│  • content/ - Bypass service        │
│  • db/ - Database client & models   │
│  • llm/ - OpenAI API wrapper        │
│  • logging/ - Service-specific logs │
│  • market_data/ - Price tracking    │
│  • s3/ - AWS S3 operations          │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  shitty_ui/ (Dashboard)             │
│  • Dash + Plotly + Bootstrap        │
│  • Performance metrics & charts     │
│  • Asset deep dive & signal feed    │
└─────────────────────────────────────┘
```

**CRITICAL RULE**: Each module is self-contained. Don't cross boundaries.

---

## Key Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `truth_social_shitposts` | All posts (source of truth) | `shitpost_id` (unique), `content`, `text`, `timestamp`, `username`, `reblog` (JSON) |
| `predictions` | LLM analysis results | `shitpost_id` (FK), `assets` (JSON), `market_impact` (JSON), `confidence` (float), `thesis`, `analysis_status` |
| `market_prices` | Historical OHLCV price data | `symbol`, `date`, `close`, `volume` |
| `prediction_outcomes` | Validated prediction accuracy | `prediction_id` (FK), `symbol`, `return_t7`, `correct_t7`, `pnl_t7` |
| `market_movements` | Market movements after predictions | `prediction_id` (FK), `asset`, `movement_24h`, `movement_72h` |

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
| `shit/llm/llm_client.py` | OpenAI API wrapper with retries |
| `shit/s3/s3_client.py` | S3 upload/download operations |
| `shit/content/bypass_service.py` | Unified bypass logic for post filtering |
| `shit/market_data/client.py` | Market price data fetcher (yfinance) |
| `shitvault/shitpost_models.py` | SQLAlchemy models (TruthSocialShitpost, Prediction) |
| `shitposts/truth_social_s3_harvester.py` | API harvesting logic |
| `shitpost_ai/shitpost_analyzer.py` | LLM analysis orchestrator |
| `shitty_ui/app.py` | Dashboard entry point (Dash + Plotly) |

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

- **Deployment**: Railway cron job (every 5 minutes)
- **Database**: Neon PostgreSQL (serverless, auto-scaling)
- **Storage**: AWS S3 (organized by date)
- **LLM**: OpenAI GPT-4 (financial analysis)
- **Posts Processed**: ~28,000+ historical
- **Analyzed Posts**: ~700+ with LLM
- **Version**: v0.18.0 (Comprehensive Test Coverage)

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

**Recently completed**:
- Market data module (`shit/market_data/`) with yfinance integration
- Prediction outcome tracking and accuracy calculation at T+1/3/7/30
- Dashboard redesign (`shitty_ui/`) with performance metrics focus
- 973+ passing tests with comprehensive coverage

**In progress**:
- Full asset price backfill for all 187+ predicted assets
- Dashboard loading states, time period filtering, mobile responsiveness

**Planned**:
- Real-time alerting system (Telegram bot)
- Multi-source signal aggregation
- Monetization features

See [CHANGELOG.md](../CHANGELOG.md) for full roadmap.
