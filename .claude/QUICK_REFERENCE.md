# Shitpost Alpha - Quick Reference for Claude

## ⚠️ CRITICAL SAFETY RULES

**NEVER run these commands** (they hit production APIs and cost money):
- `python shitpost_alpha.py` (without --dry-run)
- `python -m shitposts` (harvests from Truth Social API)
- `python -m shitvault load-database-from-s3` (processes S3 files)
- `python -m shitpost_ai analyze` (calls OpenAI API - $$$)

**SAFE commands** (read-only):
- `python -m shitvault show-stats` / `show-latest` / `show-post <id>`
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
Truth Social API → S3 Data Lake → PostgreSQL → GPT-4 Analysis → Database
```

**STRICT MODULARITY**: Each directory is a self-contained module
- `shit/` - Core infrastructure (config, db, llm, s3, logging, utils)
- `shitposts/` - Harvesting (API → S3)
- `shitvault/` - Persistence (S3 → Database)
- `shitpost_ai/` - Analysis (LLM processing)

---

## Key Directories

| Path | Purpose |
|------|---------|
| `shit/config/` | Configuration management |
| `shit/db/` | Database client & models |
| `shit/llm/` | LLM client wrapper |
| `shit/s3/` | S3 client & data lake |
| `shit/logging/` | Centralized logging |
| `shitvault/` | Database operations & models |
| `shitposts/` | Truth Social harvesting |
| `shitpost_ai/` | LLM analysis engine |
| `shit_tests/` | Core unit tests |
| `logs/` | Service-specific log files |

---

## Common Tasks

| Task | Command/Action |
|------|----------------|
| Run tests | `pytest -v` |
| Check linting | `ruff check .` |
| Format code | `ruff format .` |
| Show database stats | `python -m shitvault show-stats` |
| Show latest posts | `python -m shitvault show-latest --limit 10` |
| Show specific post | `python -m shitvault show-post <id>` |
| View logs | `tail -f logs/<service>.log` |
| Quick commit | `/quick-commit` command |
| Full PR workflow | `/commit-push-pr` command |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `shitposts` | All posts (originals and retruths) |
| `predictions` | LLM analysis results |
| `statistics` | Aggregate metrics |

**Key Indexes**:
- `shitposts`: (created_at), (analyzed), (bypassed)
- `predictions`: (shitpost_id), (created_at), (assets_mentioned)

---

## Configuration Flow

**Environment Variables** (.env):
- `SCRAPECREATORS_API_KEY` - Truth Social API
- `OPENAI_API_KEY` - OpenAI GPT-4
- `DATABASE_URL` - Neon PostgreSQL
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `FILE_LOGGING=true` - Enable service-specific logs

**Configuration Access**:
```python
from shit.config.config import Config
config = Config.load()
```

---

## Key Files to Know

| File | Contains |
|------|----------|
| `shitpost_alpha.py` | Main orchestrator CLI |
| `shit/db/db_client.py` | Database session management |
| `shit/llm/llm_client.py` | OpenAI API wrapper |
| `shit/s3/s3_client.py` | S3 operations |
| `shit/logging/__init__.py` | Logging utilities |
| `shitvault/shitpost_models.py` | SQLAlchemy models |
| `shitposts/truth_social_s3_harvester.py` | Harvesting logic |
| `shitpost_ai/shitpost_analyzer.py` | Analysis orchestrator |

---

## Logging Pattern

Every service logs to its own file:
```python
from shit.logging import setup_service_logging

logger = setup_service_logging("my_service")  # Creates logs/my_service.log
logger.info("Operation started")
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
