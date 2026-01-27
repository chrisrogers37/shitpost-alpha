# CLI Usage Guide for Shitpost Alpha

## Overview

Each module can be run as a standalone CLI using Python's `-m` flag:

```bash
python -m <module_name> [arguments]
```

## Module CLIs

### 1. Shitposts (Harvesting) - `python -m shitposts`

Harvests Truth Social posts and stores them in S3.

**Basic Usage:**
```bash
# Incremental mode (default - only new posts)
python -m shitposts --mode incremental --limit 10

# Backfill mode (historical data)
python -m shitposts --mode backfill --limit 100

# Date range mode
python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31 --limit 50

# Verbose logging
python -m shitposts --mode incremental --limit 5 --verbose
```

**Common Options:**
- `--mode`: incremental, backfill, or range
- `--limit`: Maximum number of posts to harvest
- `--from`: Start date (YYYY-MM-DD) for range mode
- `--to`: End date (YYYY-MM-DD) for range mode
- `--verbose`: Enable debug logging

---

### 2. Shitpost AI (Analysis) - `python -m shitpost_ai`

Analyzes harvested posts using LLMs to extract market signals.

**Basic Usage:**
```bash
# Incremental mode (default - only unprocessed posts)
python -m shitpost_ai --mode incremental --limit 10

# Backfill mode (historical analysis)
python -m shitpost_ai --mode backfill --limit 100

# Date range mode
python -m shitpost_ai --mode range --from 2024-01-01 --to 2024-01-31 --limit 50

# Custom batch size
python -m shitpost_ai --mode incremental --batch-size 3 --limit 15
```

**Common Options:**
- `--mode`: incremental, backfill, or range
- `--limit`: Maximum number of posts to analyze
- `--batch-size`: Number of posts to process in each batch (default: 5)
- `--from`: Start date (YYYY-MM-DD) for range mode
- `--to`: End date (YYYY-MM-DD) for range mode
- `--verbose`: Enable debug logging

---

### 3. Shitvault (Database) - `python -m shitvault`

Manages database operations, loads data from S3, and provides statistics.

**Subcommands:**

#### Load Database from S3
```bash
# Incremental mode
python -m shitvault load-database-from-s3 --mode incremental --limit 10

# Backfill mode
python -m shitvault load-database-from-s3 --mode backfill --limit 100

# Date range mode
python -m shitvault load-database-from-s3 --mode range --start-date 2024-01-01 --end-date 2024-01-31
```

#### Get Statistics
```bash
# Database statistics
python -m shitvault get-statistics

# Processing statistics
python -m shitvault get-processing-stats
```

---

### 4. Main Orchestrator - `python shitpost_alpha.py`

Runs the complete pipeline: Harvesting → S3→Database → Analysis

**Basic Usage:**
```bash
# Dry run (preview commands)
python shitpost_alpha.py --dry-run --mode incremental --limit 10

# Full pipeline execution
python shitpost_alpha.py --mode incremental --limit 10

# With verbose logging
python shitpost_alpha.py --mode incremental --limit 10 --verbose
```

**Common Options:**
- `--mode`: incremental, backfill, or range
- `--limit`: Maximum number of posts to process
- `--batch-size`: Batch size for analysis (default: 5)
- `--from`: Start date for range mode
- `--to`: End date for range mode
- `--verbose`: Enable debug logging
- `--dry-run`: Preview commands without executing

---

## Typical Workflows

### 1. Daily Monitoring (Incremental)
```bash
# Check for new posts and analyze them
python shitpost_alpha.py --mode incremental --limit 50
```

### 2. Historical Backfill
```bash
# Harvest historical posts
python -m shitposts --mode backfill --limit 1000

# Load into database
python -m shitvault load-database-from-s3 --mode backfill --limit 1000

# Analyze historical posts
python -m shitpost_ai --mode backfill --limit 1000
```

### 3. Specific Date Range
```bash
# Process posts from a specific period
python shitpost_alpha.py --mode range --from 2024-10-01 --to 2024-10-31 --limit 200
```

### 4. Debug/Development
```bash
# Verbose logging for troubleshooting
python -m shitposts --mode incremental --limit 5 --verbose

# Check database stats
python -m shitvault get-statistics

# Check processing stats
python -m shitvault get-processing-stats
```

---

## Help Commands

Get help for any CLI:

```bash
python -m shitposts --help
python -m shitpost_ai --help
python -m shitvault --help
python shitpost_alpha.py --help
```

---

## Notes

- All CLIs support `--verbose` for detailed debug logging
- Use `--limit` to control how many posts are processed
- Date formats are always YYYY-MM-DD
- The main orchestrator (`shitpost_alpha.py`) runs the complete pipeline
- Individual CLIs can be run separately for debugging or manual operations
