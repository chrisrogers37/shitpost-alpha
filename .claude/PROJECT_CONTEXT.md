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
│  • db/ - Database client & models   │
│  • llm/ - OpenAI API wrapper        │
│  • s3/ - AWS S3 operations          │
│  • logging/ - Service-specific logs │
└─────────────────────────────────────┘
```

**CRITICAL RULE**: Each module is self-contained. Don't cross boundaries.

---

## Key Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `shitposts` | All posts (source of truth) | `id`, `body`, `created_at`, `retruth`, `analyzed`, `bypassed` |
| `predictions` | LLM analysis results | `shitpost_id`, `sentiment`, `assets_mentioned`, `confidence`, `reasoning` |
| `statistics` | Aggregate metrics | Various counters and summaries |

**Important Indexes**:
- Posts by date: `shitposts(created_at)`
- Unanalyzed posts: `shitposts(analyzed)`
- Asset mentions: `predictions(assets_mentioned)` (GIN index for array search)

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
from shit.config.config import Config
config = Config.load()  # Validates and loads all settings
```

---

## Key Files

| File | Purpose |
|------|---------|
| `shitpost_alpha.py` | Main orchestrator (CLI entry point) |
| `shit/db/db_client.py` | Database session management |
| `shit/llm/llm_client.py` | OpenAI API wrapper with retries |
| `shit/s3/s3_client.py` | S3 upload/download operations |
| `shitvault/shitpost_models.py` | SQLAlchemy models (Shitpost, Prediction) |
| `shitposts/truth_social_s3_harvester.py` | API harvesting logic |
| `shitpost_ai/shitpost_analyzer.py` | LLM analysis orchestrator |

---

## Safety Rules

**NEVER suggest running** (production operations):
- `python shitpost_alpha.py` (without --dry-run)
- `python -m shitposts` (hits Truth Social API)
- `python -m shitvault load-database-from-s3` (processes files)
- `python -m shitpost_ai analyze` (calls OpenAI - costs money)

**SAFE to suggest** (read-only):
- `python -m shitvault show-stats` - Database statistics
- `python -m shitvault show-latest` - Latest posts
- `python -m shitvault show-post <id>` - Specific post details
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
- **Version**: v0.14.0 (Enhanced Logging)

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
2. Query database: `python -m shitvault show-stats`
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

## Next Phase: Market Data Integration

**Planned features**:
- Stock price data integration (Yahoo Finance / Alpha Vantage)
- Outcome calculation (did predictions come true?)
- Performance metrics (hit rate, accuracy, ROI)
- SMS alerting system (Twilio)
- Subscriber management

See [CHANGELOG.md](../CHANGELOG.md) for full roadmap.
