# Shitpost Alpha - Quick Reference for Claude

## ⚠️ CRITICAL SAFETY RULES

**NEVER run these commands** (they hit production APIs and cost money):
- `python shitpost_alpha.py` (without --dry-run)
- `python -m shitposts` (harvests from Truth Social API)
- `python -m shitvault load-database-from-s3` (processes S3 files)
- `python -m shitpost_ai analyze` (calls OpenAI API - $$$)

**SAFE commands** (read-only):
- `python -m shitvault stats` / `processing-stats`
- `pytest` (all tests)
- `python -m shit.tests` (test framework)
- `tail -f logs/<service>.log` (view logs)

**Testing commands** (safe for development):
- `python shitpost_alpha.py --mode incremental --dry-run`
- `pytest -v`
- `ruff check .` / `ruff format .`

---

## Architecture (Modular Pipeline)

```
Truth Social API → S3 Data Lake → PostgreSQL → LLM Analysis → Database → Telegram Alerts
```

**STRICT MODULARITY**: Each directory is a self-contained module
- `shit/` - Core infrastructure (config, db, llm, s3, logging, market_data, utils)
- `shitposts/` - Harvesting (API → S3) with pluggable harvester registry
- `shitvault/` - Persistence (S3 → Database) with source-agnostic Signal model
- `shitpost_ai/` - Analysis (multi-LLM: GPT-4, Claude, Grok/xAI)
- `shitty_ui/` - 4-page dashboard (Dashboard, Signals, Trends, Assets)
- `notifications/` - Telegram alerts, subscriber management, alert engine

---

## Key Directories

| Path | Purpose |
|------|---------|
| `shit/config/` | Configuration management |
| `shit/db/` | Database client & models |
| `shit/llm/` | LLM client wrapper |
| `shit/s3/` | S3 client & data lake |
| `shit/logging/` | Centralized logging |
| `shit/content/` | Content processing (bypass service) |
| `shit/market_data/` | Market price data, outcome calculation, health monitoring |
| `shitvault/` | Database operations, models (shitpost + signal) |
| `shitposts/` | Harvesting with abstract base class & registry |
| `shitpost_ai/` | Multi-LLM analysis engine & provider comparison |
| `shitty_ui/` | 4-page dashboard (Dashboard, Signals, Trends, Assets) |
| `notifications/` | Telegram alerts, subscriber management, alert engine |
| `shit_tests/` | Comprehensive test suite (1400+ tests) |
| `logs/` | Service-specific log files |

---

## Common Tasks

| Task | Command/Action |
|------|----------------|
| Run tests | `pytest -v` |
| Check linting | `ruff check .` |
| Format code | `ruff format .` |
| Show database stats | `python -m shitvault stats` |
| Show processing stats | `python -m shitvault processing-stats` |
| View logs | `tail -f logs/<service>.log` |
| Quick commit | `/quick-commit` command |
| Full PR workflow | `/commit-push-pr` command |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `truth_social_shitposts` | All posts with full API data (legacy) |
| `signals` | Source-agnostic content model (platform-independent) |
| `predictions` | LLM analysis results (dual-FK: shitpost_id + signal_id) |
| `market_prices` | Historical OHLCV price data (yfinance + Alpha Vantage) |
| `prediction_outcomes` | Validated prediction accuracy with returns |
| `ticker_registry` | Tracked ticker symbols with lifecycle management |
| `telegram_subscriptions` | Telegram bot subscribers and preferences |
| `market_movements` | Market movements after predictions |

**Key Indexes**:
- `truth_social_shitposts`: (`shitpost_id` unique), (`timestamp`)
- `predictions`: (`shitpost_id`)
- `market_prices`: (`symbol`, `date` unique composite)

---

## Configuration Flow

**Environment Variables** (.env):
- `SCRAPECREATORS_API_KEY` - Truth Social API
- `OPENAI_API_KEY` - OpenAI GPT-4
- `ANTHROPIC_API_KEY` - Claude (optional)
- `XAI_API_KEY` - Grok/xAI (optional)
- `DATABASE_URL` - Neon PostgreSQL
- `TELEGRAM_BOT_TOKEN` - Telegram alerts (optional)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `FILE_LOGGING=true` - Enable service-specific logs

**Configuration Access**:
```python
from shit.config.shitpost_settings import settings
# Pydantic Settings singleton, auto-loaded from .env
```

---

## Key Files to Know

| File | Contains |
|------|----------|
| `shitpost_alpha.py` | Main orchestrator CLI |
| `shit/db/database_client.py` | Database session management |
| `shit/config/shitpost_settings.py` | Pydantic Settings configuration |
| `shit/llm/llm_client.py` | Multi-provider LLM client |
| `shit/llm/provider_config.py` | Provider registry & model configs |
| `shit/s3/s3_client.py` | S3 operations |
| `shit/logging/__init__.py` | Logging utilities |
| `shit/content/bypass_service.py` | Unified bypass logic |
| `shitvault/shitpost_models.py` | SQLAlchemy models |
| `shitposts/truth_social_s3_harvester.py` | Harvesting logic |
| `shitpost_ai/shitpost_analyzer.py` | Analysis orchestrator |
| `shitvault/signal_models.py` | Source-agnostic Signal model |
| `shitposts/base_harvester.py` | Abstract harvester base class |
| `shitty_ui/layout.py` | Dashboard router & callback registration |
| `notifications/alert_engine.py` | Alert check-and-dispatch loop |

---

## Logging Pattern

Entry points use centralized logging setup:
```python
from shit.logging import setup_cli_logging, print_success, print_error

# Set up logging for CLI entry points
setup_cli_logging(verbose=True)

# Or use service-specific loggers
from shit.logging import DatabaseLogger, S3Logger, LLMLogger
logger = DatabaseLogger(__name__)
```

**Log Files**:
- `logs/orchestrator.log` - Main pipeline
- `logs/harvester.log` - Truth Social harvesting
- `logs/s3_processor.log` - S3 to database
- `logs/analyzer.log` - LLM analysis

---

## CHANGELOG Reminder

Every PR must update `CHANGELOG.md` under `## [Unreleased]`

---

## Testing Pattern

```bash
# Fast unit tests only
pytest -m "not integration"

# All tests with coverage
pytest --cov=shit --cov=shitvault --cov=shitpost_ai --cov-report=html

# Specific test file
pytest shit_tests/test_db_client.py -v
```
