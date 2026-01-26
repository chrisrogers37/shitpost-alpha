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
python -m shitvault show-stats
python -m shitvault show-latest
python -m shitvault show-post <id>
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
│   ├── config/             # Configuration management
│   ├── db/                 # Database models, client & operations
│   ├── llm/                # LLM client & prompts
│   ├── s3/                 # S3 client, data lake & models
│   ├── logging/            # Centralized logging system
│   ├── tests/              # Testing framework
│   └── utils/              # Utility functions & error handling
├── shitvault/              # Data persistence & S3 processing
│   ├── s3_processor.py     # S3 → Database processor
│   ├── shitpost_models.py  # Database models
│   ├── shitpost_operations.py  # Database CRUD
│   └── statistics.py       # Analytics & reporting
├── shitposts/              # Content harvesting
│   ├── truth_social_s3_harvester.py  # API → S3 harvester
│   └── cli.py              # Harvesting CLI
└── shitpost_ai/            # AI analysis engine
    ├── shitpost_analyzer.py  # Analysis orchestrator
    ├── llm_client.py       # OpenAI API wrapper
    └── prompts.py          # Analysis prompts
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
python -m shitvault show-stats

# Show latest posts
python -m shitvault show-latest --limit 10

# Show specific post with analysis
python -m shitvault show-post <post-id>

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

**`shitposts`** - All Truth Social posts
```sql
id (text, primary key)
created_at (timestamp)
body (text)  -- Post content
retruth (boolean)  -- Is this a retruth?
analyzed (boolean)  -- Has this been analyzed by LLM?
bypassed (boolean)  -- Was this bypassed (e.g., retruth)?
analyzed_at (timestamp)
s3_location (text)
```

**`predictions`** - LLM analysis results
```sql
id (uuid, primary key)
shitpost_id (text, foreign key)
sentiment (text)  -- 'bullish', 'bearish', 'neutral'
predicted_market_impact (text)
assets_mentioned (text[])  -- Array of ticker symbols
timeframe_days (integer)
confidence (text)  -- 'high', 'medium', 'low'
reasoning (text)
bypass_reason (text, nullable)  -- Why was this bypassed?
created_at (timestamp)
```

**Indexes**:
- `shitposts`: (created_at), (analyzed), (bypassed)
- `predictions`: (shitpost_id), (created_at), (assets_mentioned)

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
from shit.logging import setup_service_logging, print_success, print_error

# Set up service-specific logging
logger = setup_service_logging("my_service")

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
from shitvault.shitpost_models import Shitpost, Prediction

shitpost = Shitpost(
    id=post_id,
    body=content,
    created_at=timestamp
)
session.add(shitpost)
session.commit()

# ❌ WRONG: Raw SQL without type safety
session.execute("INSERT INTO shitposts VALUES (...)")
```

### LLM Operations
```python
# ✅ CORRECT: Use LLMClient wrapper
from shit.llm.llm_client import LLMClient

client = LLMClient()
response = await client.generate(prompt=prompt, temperature=0.1)

# ❌ WRONG: Direct OpenAI API calls without error handling
import openai
response = openai.ChatCompletion.create(...)  # No retries, no logging
```

---

## Testing Guidelines

### Test Structure (mirrors source structure)

```
shit_tests/
├── test_config.py
├── test_db_client.py
├── test_llm_client.py
├── test_s3_client.py
└── integration/
    └── test_full_pipeline.py
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
# ✅ CORRECT: Use centralized config
from shit.config.config import Config

config = Config.load()
api_key = config.openai_api_key

# ❌ WRONG: Direct os.getenv() without validation
import os
api_key = os.getenv("OPENAI_API_KEY")  # May be None, no validation
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

Always use context managers for database sessions:

```python
from shit.db.db_client import get_session

with get_session() as session:
    posts = session.query(Shitpost).filter_by(analyzed=False).all()
    # Session automatically commits on success, rolls back on error
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
if post.retruth:
    mark_bypassed(post, reason="retruth_detected")
    return None

analysis = await llm_client.analyze(post)
```

### 5. Incremental Processing

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
- Test connection: `python -m shit.db.test_connection`

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
- Show stats: `python -m shitvault show-stats`
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
