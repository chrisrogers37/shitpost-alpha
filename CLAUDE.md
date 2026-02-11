# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## CRITICAL SAFETY RULES

**THIS SYSTEM ACCESSES PRODUCTION DATABASES AND LIVE APIS. DO NOT TRIGGER PRODUCTION OPERATIONS WITHOUT EXPLICIT USER APPROVAL.**

### NEVER run these commands:
```bash
# DANGEROUS - Production operations
python shitpost_alpha.py --mode full  # Full pipeline execution
python -m shitposts --mode backfill   # Mass historical harvesting
python -m shitvault load-database-from-s3 --mode backfill  # Mass database loading
python -m shitpost_ai analyze --mode backfill  # Mass LLM analysis ($$$)
```

### SAFE commands you CAN run:
```bash
# Reading/inspection only - always safe
python -m shitvault stats
python -m shitvault processing-stats
pytest  # Tests
python -m shit.tests  # Test framework

# Safe development operations
python shitpost_alpha.py --mode incremental --dry-run  # Dry run only
```

### Before ANY production operation:
1. **STOP** and ask the user for explicit confirmation
2. Explain exactly what will happen (API calls, database writes, costs)
3. Wait for user to type "yes" or approve
4. Never assume "help me with the pipeline" means "run it in production"

---

## Project Overview

**Shitpost Alpha** is a real-time financial analysis system that monitors Donald Trump's Truth Social posts using LLMs to predict market movements and send trading alerts.

**Pipeline Architecture**:
```
Truth Social API → S3 Data Lake → PostgreSQL → LLM Analysis → Database
```

**Tech Stack**:
- **Language**: Python 3.13
- **Database**: Neon PostgreSQL (serverless)
- **Storage**: AWS S3
- **LLM**: OpenAI GPT-4
- **Deployment**: Railway (cron-based)
- **Testing**: pytest

**Current Status**: Live in production on Railway, checking Trump's page every 5 minutes.

---

## Architecture at a Glance

### Themed Directory Structure

```
shitpost_alpha/
├── shitpost_alpha.py       # 🎯 MAIN ENTRY POINT - Pipeline orchestrator
├── shit/                   # Core infrastructure & shared utilities
│   ├── config/             # Configuration management (Pydantic settings)
│   ├── content/            # Content processing (bypass service)
│   ├── db/                 # Database client, models & operations
│   ├── llm/                # LLM client & prompt templates
│   ├── logging/            # Centralized logging system
│   ├── market_data/        # Market price fetching & outcome calculation
│   ├── s3/                 # S3 client, data lake & models
│   └── utils/              # Error handling utilities
├── shitvault/              # Data persistence & S3 processing
│   ├── shitpost_models.py  # Domain-specific SQLAlchemy models
│   ├── shitpost_operations.py  # Shitpost CRUD operations
│   ├── prediction_operations.py  # Prediction CRUD operations
│   ├── s3_processor.py     # S3 → Database processor
│   ├── statistics.py       # Analytics & reporting
│   └── cli.py              # Database CLI
├── shitposts/              # Content harvesting
│   ├── truth_social_s3_harvester.py  # API → S3 harvester
│   └── cli.py              # Harvesting CLI
├── shitpost_ai/            # AI analysis engine
│   ├── shitpost_analyzer.py  # Analysis orchestrator
│   └── cli.py              # Analysis CLI utilities
├── shitty_ui/              # Prediction performance dashboard
│   ├── app.py              # Dash application entry point
│   ├── layout.py           # App factory, router & callback registration
│   ├── data.py             # Database query functions
│   ├── pages/              # Page modules (dashboard, assets)
│   ├── components/         # Reusable UI components
│   └── callbacks/          # Callback groups (alerts, navigation, clientside)
├── notifications/          # Alert dispatch & Telegram bot
│   ├── alert_engine.py     # Core alert dispatch logic
│   ├── dispatcher.py       # Multi-channel delivery (Telegram, Email, SMS)
│   ├── telegram_bot.py     # Telegram bot command handler
│   ├── telegram_sender.py  # Telegram API integration
│   ├── db.py               # Subscription & alert database operations
│   └── __main__.py         # CLI (check-alerts, set-webhook, test-alert, etc.)
└── shit_tests/             # Comprehensive test suite (1000+ tests)
    ├── conftest.py          # Shared fixtures & test configuration
    ├── shit/                # Core infrastructure tests
    ├── shitposts/           # Harvesting tests
    ├── shitvault/           # Database tests
    ├── shitpost_ai/         # AI analysis tests
    ├── shitty_ui/           # Dashboard tests
    ├── integration/         # End-to-end tests
    └── fixtures/            # Test data & mock responses
```

### Key Design Principles

1. **Modular Architecture**: Each directory is a self-contained module with clear responsibilities
2. **Centralized Utilities**: All shared code lives in `shit/` (config, db, llm, s3, logging)
3. **CLI-First Design**: Each module has a CLI for independent execution
4. **Service Logging**: Every service logs to its own file in `logs/` (e.g., `harvester.log`, `analyzer.log`)
5. **Database Models**: SQLAlchemy models with proper relationships and indexes

---

## Essential Commands

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (DO NOT COMMIT .env)

# Verify setup
python -m shit.tests
pytest
```

### Common Development Tasks

```bash
# Run the orchestrator (DRY RUN - safe for testing)
python shitpost_alpha.py --mode incremental --dry-run

# Show database statistics
python -m shitvault stats

# Show processing statistics
python -m shitvault processing-stats

# Run tests
pytest                          # All tests
pytest shit_tests/              # Core tests
pytest -v                       # Verbose output
pytest --cov=shit --cov-report=html  # With coverage

# Check code style
ruff check .                    # Lint
ruff format .                   # Format

# View logs
tail -f logs/orchestrator.log   # Main orchestrator
tail -f logs/harvester.log      # Harvesting service
tail -f logs/analyzer.log       # Analysis service
tail -f logs/s3_processor.log   # S3 processing
```

### Production Operations (REQUIRE USER APPROVAL)

```bash
# Incremental update (safe, only new posts)
python shitpost_alpha.py --mode incremental

# Full pipeline (safe, comprehensive)
python shitpost_alpha.py --mode full

# Backfill historical data (expensive, use with caution)
python -m shitposts --mode backfill --from 2024-01-01 --to 2024-12-31
```

---

## Core Services Reference

### Truth Social Harvesting (`shitposts/`)

**Purpose**: Fetch posts from Truth Social API and store in S3

**Key Class**: `TruthSocialS3Harvester`

**Modes**:
- `incremental`: Fetch only new posts since last run
- `backfill`: Fetch historical posts (expensive)
- `range`: Fetch posts within date range

**Output**: JSON files in S3 (`s3://shitpost-alpha/truth-social/posts/YYYY-MM-DD/`)

### S3 to Database Processing (`shitvault/`)

**Purpose**: Load posts from S3 into PostgreSQL

**Key Class**: `S3Processor`

**Modes**:
- `incremental`: Process only new S3 files
- `backfill`: Process all S3 files
- `range`: Process files within date range

**Database Tables**:
- `shitposts` - All posts (original content and retruths)
- `predictions` - LLM analysis results
- `statistics` - Aggregate metrics

### LLM Analysis (`shitpost_ai/`)

**Purpose**: Analyze posts for financial market implications

**Key Class**: `ShitpostAnalyzer`

**Analysis Flow**:
1. Fetch unanalyzed posts from database
2. Check if post is analyzable (skip retruths)
3. Send to GPT-4 with financial analysis prompt
4. Parse structured response (sentiment, assets, timeframes, confidence)
5. Store predictions in database

**Bypass Logic**: Retruths and non-financial posts are marked as bypassed to avoid wasting LLM tokens

---

## Database Architecture

### Key Tables

**`truth_social_shitposts`** - All Truth Social posts (field names match API structure)
- `id` (integer, auto-increment primary key)
- `shitpost_id` (string, unique) -- Original Truth Social post ID
- `content` (text) -- HTML content of the post
- `text` (text) -- Plain text content
- `timestamp` (datetime) -- When the post was created
- `username` (string) -- Author username
- `platform` (string) -- Always "truth_social"
- Engagement: `replies_count`, `reblogs_count`, `favourites_count`, `upvotes_count`, `downvotes_count`
- Account: `account_id`, `account_display_name`, `account_verified`, `account_followers_count`
- Media: `has_media`, `media_attachments` (JSON), `mentions` (JSON), `tags` (JSON)
- Repost data: `reblog` (JSON, non-null means this is a retruth)
- `raw_api_data` (JSON) -- Complete API response for debugging

**`predictions`** - LLM analysis results
- `id` (integer, auto-increment primary key)
- `shitpost_id` (string, foreign key → truth_social_shitposts.shitpost_id)
- `assets` (JSON) -- List of asset tickers, e.g. ["AAPL", "TSLA"]
- `market_impact` (JSON) -- Dict of asset → sentiment, e.g. {"AAPL": "bullish"}
- `confidence` (float, nullable) -- 0.0-1.0, null for bypassed posts
- `thesis` (text) -- Investment thesis / LLM reasoning
- `analysis_status` (string) -- 'completed', 'bypassed', 'error', 'pending'
- `analysis_comment` (string, nullable) -- Reason for bypass/error
- Enhanced scores: `engagement_score`, `viral_score`, `sentiment_score`, `urgency_score` (all float)
- Content metadata: `has_media`, `mentions_count`, `hashtags_count`, `content_length`
- Engagement at analysis: `replies_at_analysis`, `reblogs_at_analysis`, `favourites_at_analysis`, `upvotes_at_analysis`
- LLM metadata: `llm_provider`, `llm_model`, `analysis_timestamp`

**`market_movements`** - Tracks actual market movements after predictions
- `id`, `prediction_id` (FK → predictions.id)
- `asset`, `price_at_prediction`, `price_after_24h`, `price_after_72h`
- `movement_24h`, `movement_72h` (percentage changes)
- `prediction_correct_24h`, `prediction_correct_72h` (boolean)

**`market_prices`** - Historical OHLCV price data (from yfinance)
- `id`, `symbol`, `date` (unique together)
- OHLCV: `open`, `high`, `low`, `close`, `volume`, `adjusted_close`
- Metadata: `source`, `last_updated`, `is_market_open`, `has_split`, `has_dividend`

**`prediction_outcomes`** - Validated prediction accuracy with returns
- `id`, `prediction_id` (FK → predictions.id), `symbol`
- Prediction snapshot: `prediction_date`, `prediction_sentiment`, `prediction_confidence`
- Price evolution: `price_at_prediction`, `price_t1`, `price_t3`, `price_t7`, `price_t30`
- Returns: `return_t1`, `return_t3`, `return_t7`, `return_t30` (percentage change)
- Accuracy: `correct_t1`, `correct_t3`, `correct_t7`, `correct_t30` (boolean)
- P&L simulation: `pnl_t1`, `pnl_t3`, `pnl_t7`, `pnl_t30` ($1000 position)
- `is_complete` (boolean) -- All timeframes tracked?

**`subscribers`** - SMS alert subscribers (schema defined, not yet active)
**`llm_feedback`** - LLM performance feedback (schema defined, not yet active)

**Indexes**:
- `truth_social_shitposts`: (`shitpost_id` unique), (`timestamp`)
- `predictions`: (`shitpost_id`)
- `market_prices`: (`symbol`, `date` unique composite)
- `prediction_outcomes`: (`prediction_id`), (`symbol`, `prediction_date`)

---

## Development Workflow

Give Claude verification loops for 2-3x quality improvement:

1. Make changes
2. Run tests: `pytest -v`
3. Check linting: `ruff check .`
4. Format code: `ruff format .`
5. Before committing: Review logs for any errors
6. Before creating PR: Run full test suite with coverage

---

## Code Style & Conventions

### Python Standards
- Use **type hints** for all function signatures
- Prefer **async/await** for I/O operations
- Use **dataclasses** or **Pydantic** for data structures
- Write **docstrings** for all public functions (Google style)
- Keep functions **small and focused** (< 50 lines)
- Handle errors explicitly with proper logging

### Logging Standards
```python
from shit.logging import setup_cli_logging, print_success, print_error

# Set up CLI logging (for entry points)
setup_cli_logging(verbose=True)

# Or use service-specific loggers
from shit.logging import DatabaseLogger, S3Logger, LLMLogger

db_logger = DatabaseLogger(__name__)

# Use structured logging with context
logger.info("Processing post", extra={"post_id": post_id})
logger.warning("Rate limit approaching", extra={"remaining": 10})
logger.error("Failed to fetch", exc_info=True)

# Use beautiful CLI output
print_success("✅ Processing complete")
print_error("❌ Failed to connect to database")
```

### Database Operations
```python
# ✅ CORRECT: Use SQLAlchemy models
from shitvault.shitpost_models import TruthSocialShitpost, Prediction

shitpost = TruthSocialShitpost(
    shitpost_id=post_id,
    content=html_content,
    text=plain_text,
    timestamp=timestamp,
    username="realDonaldTrump"
)
session.add(shitpost)
session.commit()

# ❌ WRONG: Raw SQL without type safety
session.execute("INSERT INTO shitposts VALUES (...)")
```

### LLM Operations
```python
# ✅ CORRECT: Use LLMClient wrapper
from shit.llm import LLMClient

client = LLMClient()
await client.initialize()
analysis = await client.analyze(content)

# ❌ WRONG: Direct OpenAI API calls without error handling
import openai
response = openai.ChatCompletion.create(...)  # No retries, no logging
```

---

## Testing Guidelines

### Test Structure (mirrors source structure)

```
shit_tests/
├── conftest.py                    # Shared fixtures & test configuration
├── test_shitpost_alpha.py         # Main orchestrator tests (20 tests)
├── test_performance.py            # Performance benchmarks (8 tests)
├── shit/                          # Core infrastructure tests (619 tests)
│   ├── config/                    # Settings tests
│   ├── db/                        # Database layer tests
│   ├── llm/                       # LLM client tests
│   ├── logging/                   # Logging system tests
│   ├── s3/                        # S3 operations tests
│   └── utils/                     # Error handling tests
├── shitposts/                     # Harvesting tests (79 tests)
├── shitpost_ai/                   # AI analysis tests (102 tests)
├── shitvault/                     # Database tests (153 tests)
├── shitty_ui/                     # Dashboard tests (49 tests)
├── content/                       # Bypass service tests
├── integration/                   # End-to-end tests (16 tests)
└── fixtures/                      # Test data & mock responses
```

### Writing Tests

```python
# Unit test example
def test_parse_post_date():
    """Test that post date parsing handles timezone correctly."""
    timestamp = "2024-01-26T12:00:00Z"
    result = parse_post_date(timestamp)
    assert result.hour == 12
    assert result.tzinfo is not None

# Integration test example (requires database)
@pytest.mark.integration
def test_store_and_retrieve_post():
    """Test storing and retrieving a post from database."""
    # This test actually hits the test database
    post = create_test_post()
    store_post(post)
    retrieved = get_post(post.id)
    assert retrieved.body == post.body
```

### Running Tests

```bash
# Fast unit tests only
pytest -m "not integration"

# All tests including integration
pytest

# With coverage report
pytest --cov=shit --cov=shitvault --cov=shitpost_ai --cov-report=html
```

---

## Configuration Management

### Environment Variables (.env)

**CRITICAL**: Never commit `.env` to git. It contains sensitive credentials.

```bash
# API Keys
SCRAPECREATORS_API_KEY=xxx  # Truth Social API key
OPENAI_API_KEY=xxx          # OpenAI API key

# AWS S3
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
S3_BUCKET_NAME=shitpost-alpha
S3_PREFIX=truth-social

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://user:pass@host/db

# Feature Flags
FILE_LOGGING=true  # Enable service-specific log files
```

### Configuration Access

```python
# ✅ CORRECT: Use Pydantic settings singleton
from shit.config.shitpost_settings import settings

api_key = settings.OPENAI_API_KEY
database_url = settings.DATABASE_URL

# ❌ WRONG: Direct os.getenv() without validation
import os
api_key = os.getenv("OPENAI_API_KEY")  # May be None, no type safety
```

---

## Things Claude Should NOT Do

<!-- Add mistakes Claude makes so it learns -->

- Don't run production operations without explicit user approval
- Don't commit sensitive credentials or API keys
- Don't skip error handling in async operations
- Don't make LLM API calls in loops without rate limiting
- Don't bypass type hints "just to make it work"
- Don't create raw SQL queries instead of using SQLAlchemy models
- Don't ignore logging - all operations should be logged
- Don't skip tests when adding new functionality
- Don't modify database schema without creating migration documentation
- Don't assume all posts should be analyzed - respect the bypass logic

---

## Project-Specific Patterns

### 1. Service Logging Pattern

Every service logs to its own file:

```python
from shit.logging import setup_service_logging

logger = setup_service_logging("harvester")  # Creates logs/harvester.log
logger.info("Starting harvest")
```

### 2. Database Session Management

Always use the async database client:

```python
from shit.db import DatabaseConfig, DatabaseClient

db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
db_client = DatabaseClient(db_config)
await db_client.initialize()

# Use async sessions via the database client
# Domain operations are accessed through operation classes:
from shitvault.shitpost_operations import ShitpostOperations
shitpost_ops = ShitpostOperations(db_ops)
unprocessed = await shitpost_ops.get_unprocessed_shitposts(launch_date="2025-01-01", limit=10)
```

### 3. S3 Data Lake Organization

S3 files are organized by date for easy querying:

```
s3://shitpost-alpha/truth-social/posts/
├── 2024-01-26/
│   ├── post_123456.json
│   ├── post_123457.json
│   └── ...
├── 2024-01-27/
│   └── ...
```

### 4. LLM Analysis Bypass

Not all posts are worth analyzing. Skip retruths and non-financial posts:

```python
from shit.content import BypassService

bypass_service = BypassService()
should_bypass, reason = bypass_service.should_bypass_post(post_data)

if should_bypass:
    await prediction_ops.handle_no_text_prediction(shitpost_id, post_data, reason)
    return None

analysis = await llm_client.analyze(enhanced_content)
```

### 5. Documentation Archiving

When the user says to "archive" a document, move it from its current location to `documentation/archive/`:

```bash
# Example: archive a completed planning doc
mv documentation/planning/SOME_DOC.md documentation/archive/SOME_DOC.md
```

Do NOT delete archived documents. They remain in `documentation/archive/` for reference.

### 6. Incremental Processing

Always default to incremental processing to avoid duplicate work:

```python
# ✅ CORRECT: Process only new items
last_processed = get_last_processed_timestamp()
new_items = fetch_items_since(last_processed)

# ❌ WRONG: Reprocess everything
all_items = fetch_all_items()  # Expensive!
```

---

## Error Handling

### Standard Error Pattern

```python
import logging
from shit.utils.errors import handle_error

logger = logging.getLogger(__name__)

try:
    result = perform_operation()
except SpecificError as e:
    handle_error(e, logger, context={"operation": "fetch_posts"})
    raise  # Re-raise if critical
except Exception as e:
    handle_error(e, logger, context={"operation": "fetch_posts"})
    # Decide whether to continue or fail
```

### Async Error Handling

```python
import asyncio

async def safe_operation():
    try:
        result = await async_operation()
        return result
    except asyncio.TimeoutError:
        logger.error("Operation timed out")
        return None
    except Exception as e:
        handle_error(e, logger)
        return None
```

---

## Changelog Maintenance (CRITICAL)

**ALWAYS update CHANGELOG.md when creating PRs.** The changelog is the user-facing record of all changes.

**Format**: This project uses [Keep a Changelog](https://keepachangelog.com/) with [Semantic Versioning](https://semver.org/).

**When to update**:
- **Every PR** must include a CHANGELOG.md entry
- Add entries under `## [Unreleased]` section
- Move entries to a versioned section when releasing

**Entry categories** (use as applicable):
- `### Added` - New features or capabilities
- `### Changed` - Changes to existing functionality
- `### Deprecated` - Features that will be removed
- `### Removed` - Features that were removed
- `### Fixed` - Bug fixes
- `### Security` - Security-related changes

**Entry format**:
```markdown
## [Unreleased]

### Added
- **Feature Name** - Brief description of what was added
  - Sub-bullet with implementation detail
  - Another detail if needed

### Fixed
- **Bug Name** - What was broken and how it was fixed
```

---

## Troubleshooting Guide

### Common Issues

**Import errors**:
- Ensure virtual environment is activated
- Verify all dependencies installed: `pip install -r requirements.txt`

**Database connection errors**:
- Check `DATABASE_URL` in `.env`
- Verify Neon database is accessible (not paused)
- Test connection: Verify DATABASE_URL in .env and check Neon dashboard

**S3 access errors**:
- Check AWS credentials in `.env`
- Verify bucket name and region
- Check IAM permissions for the bucket

**LLM API errors**:
- Check `OPENAI_API_KEY` in `.env`
- Verify API key is valid and has credits
- Check rate limits (20 requests/min for GPT-4)

**Tests failing**:
- Ensure test database is set up
- Check that `.env` has test credentials
- Run `pytest -v` for detailed output

---

## Summary

**Key Principles**:
1. ✅ Always ask for approval before production operations
2. ✅ Write tests for ALL new functionality
3. ✅ Use centralized logging for all services
4. ✅ Handle errors gracefully with proper logging
5. ✅ Respect the modular architecture (don't cross boundaries)
6. ✅ Use type hints for all function signatures
7. ✅ Keep functions small and focused
8. ✅ Update CHANGELOG.md for every PR

**Quick Reference**:
- Main orchestrator: `python shitpost_alpha.py --mode incremental`
- Show stats: `python -m shitvault stats`
- Run tests: `pytest -v`
- Check code: `ruff check .`
- Format code: `ruff format .`
- View logs: `tail -f logs/<service>.log`

**Full Documentation**:
- [Project README](README.md)
- [Version History](CHANGELOG.md)
- [Harvesting Guide](shitposts/README.md)
- [Database Guide](shitvault/README.md)
- [AI Analysis Guide](shitpost_ai/README.md)

---

_Update this file continuously. Every mistake Claude makes is a learning opportunity._
