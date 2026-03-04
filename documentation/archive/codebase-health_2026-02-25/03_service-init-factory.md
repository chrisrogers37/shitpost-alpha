# Phase 03 -- Service Initialization Factory + CLI Shared Arguments

| Field | Value |
|-------|-------|
| **PR Title** | `refactor: add service init factory and shared CLI arguments` |
| **Risk** | Low |
| **Effort** | Medium (~4 hours) |
| **Files Created** | 2 (`shit/services.py`, `shit/cli/shared_args.py`) |
| **Files Modified** | 4 (`shitvault/cli.py`, `shitvault/event_consumer.py`, `shitpost_ai/cli.py`, `shitposts/cli.py`) |
| **Tests Created** | 2 (`shit_tests/shit/test_services.py`, `shit_tests/shit/cli/test_shared_args.py`) |
| **Tests Modified** | 3 (`shit_tests/shitvault/test_shitvault_cli.py`, `shit_tests/events/consumers/test_s3_processor.py`, existing test import paths remain stable) |
| **Dependencies** | None |
| **Unlocks** | None |

---

## Context

The codebase has two categories of copy-pasted boilerplate:

1. **Service initialization** -- The 12-line DB+S3 init sequence (create config, create client, call `await client.initialize()`) is duplicated verbatim in `shitvault/cli.py` (3 times) and `shitvault/event_consumer.py` (1 time). Any change to initialization logic (e.g., adding connection pooling options, changing config defaults) requires updating 4+ locations.

2. **CLI argument definitions** -- The `--mode`, `--from`, `--to`, `--limit`, `--dry-run`, `--verbose` argument group is defined identically in `shitpost_ai/cli.py` and `shitposts/cli.py`, along with identical validation logic. A third file (`shitvault/cli.py`) uses a slightly different pattern (subparsers with `--start-date`/`--end-date` instead of `--from`/`--to`) that will not be refactored in this phase.

This PR creates two shared utilities in `shit/` to eliminate this duplication, then refactors consumers to use them.

---

## Dependencies

- **Must be completed first**: None -- both new files are additive.
- **This phase unlocks**: Nothing directly -- but reduces friction for any future CLI or service additions.
- **Parallel safety**: This phase modifies `shitvault/cli.py`, `shitvault/event_consumer.py`, `shitpost_ai/cli.py`, and `shitposts/cli.py`. If any other phase also modifies these files, they cannot run in parallel with this one.

---

## Detailed Implementation Plan

### Part A: Service Initialization Factory

#### Step A1: Create `shit/services.py`

Create the new file at `/Users/chris/Projects/shitpost-alpha/shit/services.py`.

**Full file content:**

```python
"""
Service Initialization Factory

Async context managers for initializing and cleaning up database and S3
services from centralized settings. Replaces the 12-line boilerplate
that was copy-pasted across CLI and event consumer modules.

Usage::

    from shit.services import db_service, s3_service, db_and_s3_service

    async with db_service() as db_client:
        async with db_client.get_session() as session:
            ...

    async with db_and_s3_service() as (db_client, s3_data_lake):
        ...
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Tuple

from shit.config.shitpost_settings import settings
from shit.db import DatabaseConfig, DatabaseClient
from shit.s3 import S3Config, S3DataLake


@asynccontextmanager
async def db_service() -> AsyncGenerator[DatabaseClient, None]:
    """Initialize and yield a DatabaseClient, cleaning up on exit.

    Reads connection settings from the global ``settings`` singleton.

    Yields:
        Initialized DatabaseClient ready for use.
    """
    db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
    db_client = DatabaseClient(db_config)
    await db_client.initialize()
    try:
        yield db_client
    finally:
        await db_client.cleanup()


@asynccontextmanager
async def s3_service() -> AsyncGenerator[S3DataLake, None]:
    """Initialize and yield an S3DataLake, cleaning up on exit.

    Reads S3 settings from the global ``settings`` singleton.

    Yields:
        Initialized S3DataLake ready for use.
    """
    s3_config = S3Config(
        bucket_name=settings.S3_BUCKET_NAME,
        access_key_id=settings.AWS_ACCESS_KEY_ID,
        secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region=settings.AWS_REGION,
    )
    s3_data_lake = S3DataLake(s3_config)
    await s3_data_lake.initialize()
    try:
        yield s3_data_lake
    finally:
        await s3_data_lake.cleanup()


@asynccontextmanager
async def db_and_s3_service() -> AsyncGenerator[Tuple[DatabaseClient, S3DataLake], None]:
    """Initialize and yield both DatabaseClient and S3DataLake.

    Both are cleaned up when the context exits, even if an error occurs.
    Database cleanup runs first, then S3 cleanup.

    Yields:
        Tuple of (DatabaseClient, S3DataLake), both initialized.
    """
    async with db_service() as db_client:
        async with s3_service() as s3_data_lake:
            yield db_client, s3_data_lake
```

**Why this design:**
- **Async context managers** guarantee cleanup even on exceptions -- no more forgetting `await db_client.cleanup()`.
- **Composition via `db_and_s3_service`** nests the two individual context managers. This means if S3 init fails, the DB client is still cleaned up.
- **No new config objects** -- reads from the existing `settings` singleton, which is the established pattern.
- The S3DataLake already has a `cleanup()` method (at `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_data_lake.py:316-319`) that delegates to `S3Client.cleanup()`.

#### Step A2: Export from `shit/__init__.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit/__init__.py`

**Before (lines 1-9):**
```python
"""
Shitpost Alpha Core Package

This package contains the core functionality for the Shitpost Alpha application,
including database operations, S3 integration, LLM processing, and logging.
"""

__version__ = "1.0.0"
__author__ = "Shitpost Alpha Team"
```

**After:**
```python
"""
Shitpost Alpha Core Package

This package contains the core functionality for the Shitpost Alpha application,
including database operations, S3 integration, LLM processing, and logging.
"""

__version__ = "1.0.0"
__author__ = "Shitpost Alpha Team"

from shit.services import db_service, s3_service, db_and_s3_service

__all__ = [
    "db_service",
    "s3_service",
    "db_and_s3_service",
]
```

**Why:** Makes the factories importable as `from shit import db_service` -- consistent with how `from shit.db import DatabaseClient` works today. The `__all__` export is additive and does not break any existing imports.

#### Step A3: Refactor `shitvault/cli.py` -- `process_s3_data()` function

**File:** `/Users/chris/Projects/shitpost-alpha/shitvault/cli.py`

**Before (lines 6-8, imports at top):**
```python
from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shit.s3 import S3Config, S3DataLake
```

**After (replace the DB/S3 config imports with the factory import):**
```python
from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from shit.db import DatabaseOperations
from shit.services import db_service, s3_service, db_and_s3_service
```

Note: `DatabaseConfig`, `DatabaseClient`, `S3Config`, and `S3DataLake` are no longer imported directly since the factory handles them. `DatabaseOperations` is still needed because it is used inside the session context. Remove the now-unused imports: `DatabaseConfig`, `DatabaseClient`, `S3Config`, `S3DataLake`.

**Before `process_s3_data()` (lines 117-192):**
```python
async def process_s3_data(args):
    """Process S3 data to database using modular architecture."""
    try:
        print_database_start(args)
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("INITIALIZING DATABASE & S3 CONNECTION")
        logger.info("═══════════════════════════════════════════════════════════")

        # Parse dates
        start_date = None
        end_date = None

        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            logger.info(f"Start date: {start_date.date()}")

        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            logger.info(f"End date: {end_date.date()}")

        if args.limit:
            logger.info(f"Processing limit: {args.limit}")

        if args.dry_run:
            logger.info("Mode: DRY RUN (no changes will be made)")

        logger.info(f"Processing mode: {args.mode}")

        # Initialize database and S3 components
        db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        db_client = DatabaseClient(db_config)
        await db_client.initialize()

        s3_config = S3Config(
            bucket_name=settings.S3_BUCKET_NAME,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region=settings.AWS_REGION
        )
        s3_data_lake = S3DataLake(s3_config)
        await s3_data_lake.initialize()

        logger.info("✅ Database and S3 connections initialized successfully")
        logger.info("")

        # Create operations with proper session management
        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            s3_processor = S3Processor(db_ops, s3_data_lake)

            # Process S3 data
            stats = await s3_processor.process_s3_to_database(
                start_date=start_date,
                end_date=end_date,
                limit=args.limit,
                incremental=(args.mode == 'incremental'),
                dry_run=args.dry_run
            )

            print_database_complete(stats)
            logger.info("")
            logger.info("═══════════════════════════════════════════════════════════")
            logger.info("PROCESSING COMPLETED")
            logger.info("═══════════════════════════════════════════════════════════")
            logger.info(f"Total processed: {stats.get('total_processed', 0)}")
            logger.info(f"Successful: {stats.get('successful', 0)}")
            logger.info(f"Failed: {stats.get('failed', 0)}")
            logger.info(f"Skipped: {stats.get('skipped', 0)}")

        # Cleanup
        await db_client.cleanup()

    except Exception as e:
        print_database_error(e)
        raise
```

**After `process_s3_data()`:**
```python
async def process_s3_data(args):
    """Process S3 data to database using modular architecture."""
    try:
        print_database_start(args)
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("INITIALIZING DATABASE & S3 CONNECTION")
        logger.info("═══════════════════════════════════════════════════════════")

        # Parse dates
        start_date = None
        end_date = None

        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            logger.info(f"Start date: {start_date.date()}")

        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            logger.info(f"End date: {end_date.date()}")

        if args.limit:
            logger.info(f"Processing limit: {args.limit}")

        if args.dry_run:
            logger.info("Mode: DRY RUN (no changes will be made)")

        logger.info(f"Processing mode: {args.mode}")

        # Initialize database and S3 using factory context managers
        async with db_and_s3_service() as (db_client, s3_data_lake):
            logger.info("✅ Database and S3 connections initialized successfully")
            logger.info("")

            # Create operations with proper session management
            async with db_client.get_session() as session:
                db_ops = DatabaseOperations(session)
                s3_processor = S3Processor(db_ops, s3_data_lake)

                # Process S3 data
                stats = await s3_processor.process_s3_to_database(
                    start_date=start_date,
                    end_date=end_date,
                    limit=args.limit,
                    incremental=(args.mode == 'incremental'),
                    dry_run=args.dry_run
                )

                print_database_complete(stats)
                logger.info("")
                logger.info("═══════════════════════════════════════════════════════════")
                logger.info("PROCESSING COMPLETED")
                logger.info("═══════════════════════════════════════════════════════════")
                logger.info(f"Total processed: {stats.get('total_processed', 0)}")
                logger.info(f"Successful: {stats.get('successful', 0)}")
                logger.info(f"Failed: {stats.get('failed', 0)}")
                logger.info(f"Skipped: {stats.get('skipped', 0)}")

    except Exception as e:
        print_database_error(e)
        raise
```

**Key changes:**
- Replaced 12-line manual init + explicit `await db_client.cleanup()` with `async with db_and_s3_service() as (db_client, s3_data_lake):`.
- The `logger.info("✅ Database and S3 connections initialized successfully")` line moved inside the context manager block (after the `async with` successfully enters).
- Cleanup is automatic via context manager exit -- removed the standalone `await db_client.cleanup()` call.

#### Step A4: Refactor `shitvault/cli.py` -- `get_database_stats()` function

**Before (lines 195-219):**
```python
async def get_database_stats(args):
    """Get database statistics using modular architecture."""
    try:
        print_database_start(args)

        # Initialize database
        db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        db_client = DatabaseClient(db_config)
        await db_client.initialize()

        # Create operations with proper session management
        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            stats_ops = Statistics(db_ops)

            # Get stats
            stats = await stats_ops.get_database_stats()
            print_database_complete(stats)

        # Cleanup
        await db_client.cleanup()

    except Exception as e:
        print_database_error(e)
        raise
```

**After:**
```python
async def get_database_stats(args):
    """Get database statistics using modular architecture."""
    try:
        print_database_start(args)

        # Initialize database using factory context manager
        async with db_service() as db_client:
            # Create operations with proper session management
            async with db_client.get_session() as session:
                db_ops = DatabaseOperations(session)
                stats_ops = Statistics(db_ops)

                # Get stats
                stats = await stats_ops.get_database_stats()
                print_database_complete(stats)

    except Exception as e:
        print_database_error(e)
        raise
```

**Key change:** 3-line DB init + explicit cleanup replaced with `async with db_service() as db_client:`.

#### Step A5: Refactor `shitvault/cli.py` -- `get_processing_stats()` function

**Before (lines 222-255):**
```python
async def get_processing_stats(args):
    """Get processing statistics using modular architecture."""
    try:
        print_database_start(args)

        # Initialize database and S3 components
        db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        db_client = DatabaseClient(db_config)
        await db_client.initialize()

        s3_config = S3Config(
            bucket_name=settings.S3_BUCKET_NAME,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region=settings.AWS_REGION
        )
        s3_data_lake = S3DataLake(s3_config)
        await s3_data_lake.initialize()

        # Create operations with proper session management
        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            s3_processor = S3Processor(db_ops, s3_data_lake)

            # Get processing stats
            stats = await s3_processor.get_s3_processing_stats()
            print_database_complete(stats)

        # Cleanup
        await db_client.cleanup()

    except Exception as e:
        print_database_error(e)
        raise
```

**After:**
```python
async def get_processing_stats(args):
    """Get processing statistics using modular architecture."""
    try:
        print_database_start(args)

        # Initialize database and S3 using factory context managers
        async with db_and_s3_service() as (db_client, s3_data_lake):
            # Create operations with proper session management
            async with db_client.get_session() as session:
                db_ops = DatabaseOperations(session)
                s3_processor = S3Processor(db_ops, s3_data_lake)

                # Get processing stats
                stats = await s3_processor.get_s3_processing_stats()
                print_database_complete(stats)

    except Exception as e:
        print_database_error(e)
        raise
```

#### Step A6: Refactor `shitvault/event_consumer.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shitvault/event_consumer.py`

**Before (lines 1-102, full file):**
```python
"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import sys

from shit.config.shitpost_settings import settings
from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

logger = get_service_logger("s3_processor_worker")


class S3ProcessorWorker(EventWorker):
    """Processes posts_harvested events by loading S3 data into the database."""

    consumer_group = ConsumerGroup.S3_PROCESSOR

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a posts_harvested event.
        ...
        """
        import asyncio
        from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
        from shit.s3 import S3Config, S3DataLake
        from shitvault.s3_processor import S3Processor

        s3_keys = payload.get("s3_keys", [])
        source = payload.get("source", "truth_social")

        if not s3_keys:
            logger.info("No S3 keys in event payload, skipping")
            return {"total_processed": 0, "successful": 0}

        async def _process():
            db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
            db_client = DatabaseClient(db_config)
            await db_client.initialize()

            s3_config = S3Config(
                bucket_name=settings.S3_BUCKET_NAME,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region=settings.AWS_REGION,
            )
            s3_data_lake = S3DataLake(s3_config)
            await s3_data_lake.initialize()

            try:
                async with db_client.get_session() as session:
                    db_ops = DatabaseOperations(session)
                    processor = S3Processor(db_ops, s3_data_lake, source=source)

                    stats = {
                        "total_processed": 0,
                        "successful": 0,
                        "failed": 0,
                        "skipped": 0,
                        "signal_ids": [],
                    }

                    for s3_key in s3_keys:
                        stats["total_processed"] += 1
                        s3_data = await s3_data_lake.get_raw_data(s3_key)
                        if s3_data:
                            await processor._process_single_s3_data(
                                s3_data, stats, dry_run=False
                            )

                    # Emit downstream event
                    signal_ids = stats.pop("signal_ids", [])
                    if signal_ids:
                        from shit.events.producer import emit_event

                        emit_event(
                            event_type=EventType.SIGNALS_STORED,
                            payload={
                                "signal_ids": signal_ids,
                                "source": source,
                                "count": len(signal_ids),
                            },
                            source_service="s3_processor",
                        )

                    return stats
            finally:
                await db_client.cleanup()

        return asyncio.run(_process())
```

**After:**
```python
"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

logger = get_service_logger("s3_processor_worker")


class S3ProcessorWorker(EventWorker):
    """Processes posts_harvested events by loading S3 data into the database."""

    consumer_group = ConsumerGroup.S3_PROCESSOR

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a posts_harvested event.

        Runs the S3 processor for the specific keys in the event payload,
        then emits a signals_stored event with the resulting signal IDs.

        Args:
            event_type: Should be EventType.POSTS_HARVESTED.
            payload: Contains s3_keys, source, count, mode.

        Returns:
            Processing statistics dict.
        """
        import asyncio
        from shit.db import DatabaseOperations
        from shit.services import db_and_s3_service
        from shitvault.s3_processor import S3Processor

        s3_keys = payload.get("s3_keys", [])
        source = payload.get("source", "truth_social")

        if not s3_keys:
            logger.info("No S3 keys in event payload, skipping")
            return {"total_processed": 0, "successful": 0}

        async def _process():
            async with db_and_s3_service() as (db_client, s3_data_lake):
                async with db_client.get_session() as session:
                    db_ops = DatabaseOperations(session)
                    processor = S3Processor(db_ops, s3_data_lake, source=source)

                    stats = {
                        "total_processed": 0,
                        "successful": 0,
                        "failed": 0,
                        "skipped": 0,
                        "signal_ids": [],
                    }

                    for s3_key in s3_keys:
                        stats["total_processed"] += 1
                        s3_data = await s3_data_lake.get_raw_data(s3_key)
                        if s3_data:
                            await processor._process_single_s3_data(
                                s3_data, stats, dry_run=False
                            )

                    # Emit downstream event
                    signal_ids = stats.pop("signal_ids", [])
                    if signal_ids:
                        from shit.events.producer import emit_event

                        emit_event(
                            event_type=EventType.SIGNALS_STORED,
                            payload={
                                "signal_ids": signal_ids,
                                "source": source,
                                "count": len(signal_ids),
                            },
                            source_service="s3_processor",
                        )

                    return stats

        return asyncio.run(_process())
```

**Key changes:**
- Removed `from shit.config.shitpost_settings import settings` (no longer needed at module level).
- Inside `process_event`, replaced `from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations` with `from shit.db import DatabaseOperations` and added `from shit.services import db_and_s3_service`.
- Removed `from shit.s3 import S3Config, S3DataLake`.
- The 12-line manual init + `try/finally` cleanup replaced with `async with db_and_s3_service() as (db_client, s3_data_lake):`.
- **Net: 12 lines removed, 1 line added.**

---

### Part B: Shared CLI Arguments

#### Step B1: Create `shit/cli/` package

Create the package directory and its `__init__.py`.

**File:** `/Users/chris/Projects/shitpost-alpha/shit/cli/__init__.py`

```python
"""
Shared CLI utilities for Shitpost-Alpha.

Provides reusable argument definitions and validation logic used by
multiple CLI modules (shitpost_ai, shitposts, shitvault).
"""

from .shared_args import add_standard_arguments, validate_standard_args

__all__ = [
    "add_standard_arguments",
    "validate_standard_args",
]
```

#### Step B2: Create `shit/cli/shared_args.py`

**File:** `/Users/chris/Projects/shitpost-alpha/shit/cli/shared_args.py`

**Full file content:**

```python
"""
Shared CLI Arguments

Provides reusable argparse argument definitions shared across CLI modules.
Each module can add these standard arguments to its own parser, then layer
on module-specific extras.

Usage::

    import argparse
    from shit.cli.shared_args import add_standard_arguments, validate_standard_args

    parser = argparse.ArgumentParser(description="My CLI")
    add_standard_arguments(parser)
    # Add module-specific args here...

    args = parser.parse_args()
    validate_standard_args(args)
"""

import argparse


def add_standard_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the standard set of CLI arguments to a parser.

    Adds the following arguments:
        --mode: choices=["incremental", "backfill", "range"], default="incremental"
        --from / dest=start_date: Start date for range mode (YYYY-MM-DD)
        --to / dest=end_date: End date for range mode (YYYY-MM-DD)
        --limit: Maximum number of records to process (int)
        --dry-run: Show what would be done without making changes
        --verbose / -v: Enable verbose logging

    Args:
        parser: The ArgumentParser (or subparser) to add arguments to.
    """
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "range"],
        default="incremental",
        help="Processing mode (default: incremental)",
    )
    parser.add_argument(
        "--from",
        dest="start_date",
        help="Start date for range mode (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="end_date",
        help="End date for range mode (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of records to process (optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )


def validate_standard_args(args: argparse.Namespace) -> None:
    """Validate standard CLI arguments.

    Checks that ``--from`` is provided when ``--mode range`` is selected.
    The ``--to`` date is always optional (defaults to today).

    Args:
        args: Parsed command line arguments.

    Raises:
        SystemExit: If ``--mode range`` is used without ``--from``.
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")
```

**Design decision:** The help text uses generic language ("Processing mode", "records to process") rather than domain-specific language ("Analysis mode", "posts to harvest"). Each CLI module's `description` and `epilog` provide the domain context. The generic help text is correct because the same argument serves the same purpose across all modules.

#### Step B3: Refactor `shitpost_ai/cli.py` to use shared args

**File:** `/Users/chris/Projects/shitpost-alpha/shitpost_ai/cli.py`

**Before `create_analyzer_parser()` (lines 18-77):**
```python
def create_analyzer_parser(description: str, epilog: str = None) -> argparse.ArgumentParser:
    """Create a standardized argument parser for Truth Social analyzers.
    ...
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )

    # Analysis mode
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "range"],
        default="incremental",
        help="Analysis mode (default: incremental)"
    )

    # Date range options
    parser.add_argument(
        "--from",
        dest="start_date",
        help="Start date for range mode (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="end_date",
        help="End date for range mode (YYYY-MM-DD)"
    )

    # Limits and options
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of posts to analyze (optional)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of posts to analyze per batch (default: 5)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be analyzed without storing results to database"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser
```

**After `create_analyzer_parser()`:**
```python
def create_analyzer_parser(description: str, epilog: str = None) -> argparse.ArgumentParser:
    """Create a standardized argument parser for Truth Social analyzers.

    Args:
        description: Description for the analyzer
        epilog: Additional help text (optional)

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )

    # Standard arguments shared across all CLIs
    add_standard_arguments(parser)

    # Analyzer-specific arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of posts to analyze per batch (default: 5)"
    )

    return parser
```

**Before `validate_analyzer_args()` (lines 80-93):**
```python
def validate_analyzer_args(args) -> None:
    """Validate analyzer command line arguments.
    ...
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")

    # Note: --to date is optional for range mode (defaults to today)
```

**After `validate_analyzer_args()`:**
```python
def validate_analyzer_args(args) -> None:
    """Validate analyzer command line arguments.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If arguments are invalid
    """
    validate_standard_args(args)
```

**Import changes at top of file (lines 1-15):**

**Before:**
```python
"""
Shared CLI functionality for Truth Social analyzers.
"""

import argparse
import logging
from typing import Optional

from shit.logging import (
    setup_analyzer_logging as setup_centralized_analyzer_logging,
    print_success,
    print_error,
    print_info,
    print_warning
)
```

**After:**
```python
"""
Shared CLI functionality for Truth Social analyzers.
"""

import argparse
import logging
from typing import Optional

from shit.cli.shared_args import add_standard_arguments, validate_standard_args
from shit.logging import (
    setup_analyzer_logging as setup_centralized_analyzer_logging,
    print_success,
    print_error,
    print_info,
    print_warning
)
```

**Note:** The `logging` import is unused in the current code but is kept because removing unused imports is outside this PR's scope. The `print_success`, `print_error`, `print_info`, `print_warning` imports are also unused in the current `cli.py` file but are kept for the same reason.

#### Step B4: Refactor `shitposts/cli.py` to use shared args

**File:** `/Users/chris/Projects/shitpost-alpha/shitposts/cli.py`

**Import changes at top (lines 1-15):**

**Before:**
```python
"""
Shared CLI functionality for Truth Social harvesters.
"""

import argparse
import logging
from typing import Optional

from shit.logging import (
    setup_harvester_logging as setup_centralized_harvester_logging,
    print_success,
    print_error,
    print_info,
    print_warning
)
```

**After:**
```python
"""
Shared CLI functionality for Truth Social harvesters.
"""

import argparse
import logging
from typing import Optional

from shit.cli.shared_args import add_standard_arguments, validate_standard_args
from shit.logging import (
    setup_harvester_logging as setup_centralized_harvester_logging,
    print_success,
    print_error,
    print_info,
    print_warning
)
```

**Before `create_harvester_parser()` (lines 18-82):**
```python
def create_harvester_parser(description: str, epilog: str = None) -> argparse.ArgumentParser:
    """Create a standardized argument parser for Truth Social S3 harvesters.
    ...
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )

    # Harvesting mode
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "range"],
        default="incremental",
        help="Harvesting mode (default: incremental)"
    )

    # Date range options
    parser.add_argument(
        "--from",
        dest="start_date",
        help="Start date for range mode (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="end_date",
        help="End date for range mode (YYYY-MM-DD)"
    )

    # Limits and options
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of posts to harvest (optional)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be harvested without storing data to S3"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--max-id",
        type=str,
        help="Start harvesting from this post ID (for resuming backfill)"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Harvester source name (e.g., truth_social, twitter). Default: all enabled."
    )

    return parser
```

**After `create_harvester_parser()`:**
```python
def create_harvester_parser(description: str, epilog: str = None) -> argparse.ArgumentParser:
    """Create a standardized argument parser for Truth Social S3 harvesters.

    Args:
        description: Description for the harvester
        epilog: Additional help text (optional)

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )

    # Standard arguments shared across all CLIs
    add_standard_arguments(parser)

    # Harvester-specific arguments
    parser.add_argument(
        "--max-id",
        type=str,
        help="Start harvesting from this post ID (for resuming backfill)"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Harvester source name (e.g., truth_social, twitter). Default: all enabled."
    )

    return parser
```

**Before `validate_harvester_args()` (lines 85-97):**
```python
def validate_harvester_args(args) -> None:
    """Validate harvester command line arguments.
    ...
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")

    # Note: --to date is optional for range mode (defaults to today)
```

**After `validate_harvester_args()`:**
```python
def validate_harvester_args(args) -> None:
    """Validate harvester command line arguments.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If arguments are invalid
    """
    validate_standard_args(args)
```

#### Decision: `shitvault/cli.py` is NOT refactored for Part B

The `shitvault/cli.py` uses a **subparser** pattern with different argument names (`--start-date`/`--end-date` instead of `--from`/`--to`). Forcing it to use the shared args would require changing the CLI interface (breaking change) or adding complexity to `add_standard_arguments` (conditional arg names). Neither is worth it for one file. Leave it as-is for Part B.

---

## Test Plan

### New Test File 1: `shit_tests/shit/test_services.py`

Create `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/test_services.py`:

```python
"""
Tests for shit/services.py — Service Initialization Factory.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDbService:
    """Tests for the db_service() async context manager."""

    @pytest.mark.asyncio
    async def test_db_service_initializes_and_cleans_up(self):
        """Verify db_service creates a DatabaseClient, initializes it,
        yields it, and calls cleanup on exit."""
        mock_db_client = AsyncMock()

        with patch("shit.services.DatabaseConfig") as mock_config_cls, \
             patch("shit.services.DatabaseClient", return_value=mock_db_client) as mock_client_cls, \
             patch("shit.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"

            from shit.services import db_service

            async with db_service() as client:
                assert client is mock_db_client
                mock_db_client.initialize.assert_awaited_once()

            mock_db_client.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_service_cleans_up_on_exception(self):
        """Verify cleanup is called even when the body raises."""
        mock_db_client = AsyncMock()

        with patch("shit.services.DatabaseConfig"), \
             patch("shit.services.DatabaseClient", return_value=mock_db_client), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"

            from shit.services import db_service

            with pytest.raises(RuntimeError, match="boom"):
                async with db_service() as client:
                    raise RuntimeError("boom")

            mock_db_client.cleanup.assert_awaited_once()


class TestS3Service:
    """Tests for the s3_service() async context manager."""

    @pytest.mark.asyncio
    async def test_s3_service_initializes_and_cleans_up(self):
        """Verify s3_service creates an S3DataLake, initializes it,
        yields it, and calls cleanup on exit."""
        mock_s3 = AsyncMock()

        with patch("shit.services.S3Config"), \
             patch("shit.services.S3DataLake", return_value=mock_s3), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            from shit.services import s3_service

            async with s3_service() as lake:
                assert lake is mock_s3
                mock_s3.initialize.assert_awaited_once()

            mock_s3.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_s3_service_cleans_up_on_exception(self):
        """Verify cleanup is called even when the body raises."""
        mock_s3 = AsyncMock()

        with patch("shit.services.S3Config"), \
             patch("shit.services.S3DataLake", return_value=mock_s3), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            from shit.services import s3_service

            with pytest.raises(RuntimeError, match="boom"):
                async with s3_service() as lake:
                    raise RuntimeError("boom")

            mock_s3.cleanup.assert_awaited_once()


class TestDbAndS3Service:
    """Tests for the db_and_s3_service() async context manager."""

    @pytest.mark.asyncio
    async def test_db_and_s3_yields_both_clients(self):
        """Verify db_and_s3_service yields a (db_client, s3_data_lake) tuple."""
        mock_db = AsyncMock()
        mock_s3 = AsyncMock()

        with patch("shit.services.DatabaseConfig"), \
             patch("shit.services.DatabaseClient", return_value=mock_db), \
             patch("shit.services.S3Config"), \
             patch("shit.services.S3DataLake", return_value=mock_s3), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            from shit.services import db_and_s3_service

            async with db_and_s3_service() as (db_client, s3_data_lake):
                assert db_client is mock_db
                assert s3_data_lake is mock_s3

            mock_db.cleanup.assert_awaited_once()
            mock_s3.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_and_s3_cleans_up_both_on_exception(self):
        """Verify both clients are cleaned up when the body raises."""
        mock_db = AsyncMock()
        mock_s3 = AsyncMock()

        with patch("shit.services.DatabaseConfig"), \
             patch("shit.services.DatabaseClient", return_value=mock_db), \
             patch("shit.services.S3Config"), \
             patch("shit.services.S3DataLake", return_value=mock_s3), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            from shit.services import db_and_s3_service

            with pytest.raises(RuntimeError, match="boom"):
                async with db_and_s3_service() as (db_client, s3_data_lake):
                    raise RuntimeError("boom")

            mock_db.cleanup.assert_awaited_once()
            mock_s3.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_cleanup_called_when_s3_init_fails(self):
        """Verify DB is cleaned up even if S3 initialization fails."""
        mock_db = AsyncMock()
        mock_s3 = AsyncMock()
        mock_s3.initialize.side_effect = RuntimeError("S3 init failed")

        with patch("shit.services.DatabaseConfig"), \
             patch("shit.services.DatabaseClient", return_value=mock_db), \
             patch("shit.services.S3Config"), \
             patch("shit.services.S3DataLake", return_value=mock_s3), \
             patch("shit.services.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.AWS_REGION = "us-east-1"

            from shit.services import db_and_s3_service

            with pytest.raises(RuntimeError, match="S3 init failed"):
                async with db_and_s3_service() as _:
                    pass  # Should not reach here

            # DB was initialized and should be cleaned up
            mock_db.cleanup.assert_awaited_once()
```

### New Test File 2: `shit_tests/shit/cli/__init__.py` and `shit_tests/shit/cli/test_shared_args.py`

Create `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/cli/__init__.py` (empty file).

Create `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/cli/test_shared_args.py`:

```python
"""
Tests for shit/cli/shared_args.py — Shared CLI Arguments.
"""

import argparse
import pytest

from shit.cli.shared_args import add_standard_arguments, validate_standard_args


class TestAddStandardArguments:
    """Tests for add_standard_arguments()."""

    def _make_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        add_standard_arguments(parser)
        return parser

    def test_mode_default_is_incremental(self):
        parser = self._make_parser()
        args = parser.parse_args([])
        assert args.mode == "incremental"

    def test_mode_choices(self):
        parser = self._make_parser()
        for mode in ["incremental", "backfill", "range"]:
            args = parser.parse_args(["--mode", mode])
            assert args.mode == mode

    def test_from_maps_to_start_date(self):
        parser = self._make_parser()
        args = parser.parse_args(["--from", "2024-01-01"])
        assert args.start_date == "2024-01-01"

    def test_to_maps_to_end_date(self):
        parser = self._make_parser()
        args = parser.parse_args(["--to", "2024-12-31"])
        assert args.end_date == "2024-12-31"

    def test_limit_is_int(self):
        parser = self._make_parser()
        args = parser.parse_args(["--limit", "50"])
        assert args.limit == 50

    def test_limit_default_is_none(self):
        parser = self._make_parser()
        args = parser.parse_args([])
        assert args.limit is None

    def test_dry_run_flag(self):
        parser = self._make_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_dry_run_default_false(self):
        parser = self._make_parser()
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_verbose_flag(self):
        parser = self._make_parser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_verbose_short_flag(self):
        parser = self._make_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_verbose_default_false(self):
        parser = self._make_parser()
        args = parser.parse_args([])
        assert args.verbose is False

    def test_all_arguments_together(self):
        parser = self._make_parser()
        args = parser.parse_args([
            "--mode", "range",
            "--from", "2024-01-01",
            "--to", "2024-06-30",
            "--limit", "100",
            "--dry-run",
            "--verbose",
        ])
        assert args.mode == "range"
        assert args.start_date == "2024-01-01"
        assert args.end_date == "2024-06-30"
        assert args.limit == 100
        assert args.dry_run is True
        assert args.verbose is True

    def test_can_add_extra_args_after_standard(self):
        """Verify module-specific args can be added after standard ones."""
        parser = self._make_parser()
        parser.add_argument("--batch-size", type=int, default=5)
        args = parser.parse_args(["--mode", "backfill", "--batch-size", "10"])
        assert args.mode == "backfill"
        assert args.batch_size == 10


class TestValidateStandardArgs:
    """Tests for validate_standard_args()."""

    def test_incremental_mode_passes(self):
        args = argparse.Namespace(mode="incremental", start_date=None)
        validate_standard_args(args)  # Should not raise

    def test_backfill_mode_passes(self):
        args = argparse.Namespace(mode="backfill", start_date=None)
        validate_standard_args(args)  # Should not raise

    def test_range_mode_with_start_date_passes(self):
        args = argparse.Namespace(mode="range", start_date="2024-01-01")
        validate_standard_args(args)  # Should not raise

    def test_range_mode_without_start_date_raises(self):
        args = argparse.Namespace(mode="range", start_date=None)
        with pytest.raises(SystemExit, match="--from date is required for range mode"):
            validate_standard_args(args)

    def test_range_mode_with_empty_start_date_raises(self):
        args = argparse.Namespace(mode="range", start_date="")
        with pytest.raises(SystemExit, match="--from date is required for range mode"):
            validate_standard_args(args)
```

### Existing Test Modifications

#### `shit_tests/shitvault/test_shitvault_cli.py`

The existing tests mock `shitvault.cli.DatabaseConfig`, `shitvault.cli.DatabaseClient`, `shitvault.cli.S3Config`, and `shitvault.cli.S3DataLake`. After the refactor, these classes are no longer imported directly in `shitvault/cli.py` -- the factory handles them. The test patches must change.

**For `test_process_s3_data_success` and `test_process_s3_data_with_dates` and `test_process_s3_data_error`:**

Replace patches of individual config/client classes with a patch of the `db_and_s3_service` context manager.

**Before (example from `test_process_s3_data_success`, lines 214-251):**
```python
with patch('shitvault.cli.print_database_start'), \
     patch('shitvault.cli.print_database_complete'), \
     patch('shitvault.cli.settings') as mock_settings, \
     patch('shitvault.cli.DatabaseConfig'), \
     patch('shitvault.cli.DatabaseClient') as mock_db_client_class, \
     patch('shitvault.cli.S3Config'), \
     patch('shitvault.cli.S3DataLake') as mock_s3_class, \
     patch('shitvault.cli.DatabaseOperations'), \
     patch('shitvault.cli.S3Processor') as mock_processor_class:

    # Setup mocks
    mock_db_client = AsyncMock()
    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)
    mock_db_client.get_session = MagicMock(return_value=mock_session_cm)
    mock_db_client_class.return_value = mock_db_client

    mock_s3 = AsyncMock()
    mock_s3_class.return_value = mock_s3

    mock_processor = AsyncMock()
    mock_processor.process_s3_to_database.return_value = {
        'total_processed': 10,
        'successful': 8,
        'failed': 2
    }
    mock_processor_class.return_value = mock_processor

    await process_s3_data(mock_args)

    mock_db_client.initialize.assert_called_once()
    mock_s3.initialize.assert_called_once()
    mock_processor.process_s3_to_database.assert_called_once()
    mock_db_client.cleanup.assert_called_once()
```

**After:**
```python
from contextlib import asynccontextmanager

mock_db_client = AsyncMock()
mock_session = AsyncMock()
mock_session_cm = MagicMock()
mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
mock_session_cm.__aexit__ = AsyncMock(return_value=False)
mock_db_client.get_session = MagicMock(return_value=mock_session_cm)

mock_s3 = AsyncMock()

@asynccontextmanager
async def fake_db_and_s3():
    yield mock_db_client, mock_s3

mock_processor = AsyncMock()
mock_processor.process_s3_to_database.return_value = {
    'total_processed': 10,
    'successful': 8,
    'failed': 2
}

with patch('shitvault.cli.print_database_start'), \
     patch('shitvault.cli.print_database_complete'), \
     patch('shitvault.cli.db_and_s3_service', side_effect=fake_db_and_s3), \
     patch('shitvault.cli.DatabaseOperations'), \
     patch('shitvault.cli.S3Processor', return_value=mock_processor):

    await process_s3_data(mock_args)

    mock_processor.process_s3_to_database.assert_called_once()
```

Apply the same pattern to `test_process_s3_data_with_dates`, `test_process_s3_data_error`, `test_get_database_stats_success` (use `fake_db_service`), and `test_get_processing_stats_success` (use `fake_db_and_s3`).

**For `test_get_database_stats_success`** -- replace `DatabaseConfig`/`DatabaseClient` patches with `db_service`:

```python
@asynccontextmanager
async def fake_db():
    yield mock_db_client

with patch('shitvault.cli.print_database_start'), \
     patch('shitvault.cli.print_database_complete'), \
     patch('shitvault.cli.db_service', side_effect=fake_db), \
     patch('shitvault.cli.DatabaseOperations'), \
     patch('shitvault.cli.Statistics', return_value=mock_stats):
    ...
```

**Update imports in the test file** -- add `from contextlib import asynccontextmanager` at the top, and update the import from `shitvault.cli` to remove `DatabaseConfig`, `DatabaseClient`, `S3Config`, `S3DataLake` (these are no longer exported by `shitvault/cli.py`). The import list should remain:

```python
from shitvault.cli import (
    create_database_parser,
    setup_database_logging,
    print_database_start,
    print_database_complete,
    print_database_error,
    print_database_interrupted,
    process_s3_data,
    get_database_stats,
    get_processing_stats,
    main
)
```

(This import list is unchanged from the current test file.)

#### `shit_tests/events/consumers/test_s3_processor.py`

The `test_process_event_iterates_all_s3_keys`, `test_process_event_emits_signals_stored_when_signal_ids_present`, `test_process_event_no_emit_when_no_signal_ids`, and `test_db_client_cleanup_called_on_success_and_failure` tests all mock `shit.db.DatabaseConfig`, `shit.db.DatabaseClient`, `shit.s3.S3Config`, `shit.s3.S3DataLake`, and `shitvault.event_consumer.settings`.

After the refactor, `shitvault/event_consumer.py` no longer imports these directly. Instead it imports `shit.services.db_and_s3_service`. The tests must patch `shit.services.db_and_s3_service` instead.

**Example change for `test_process_event_iterates_all_s3_keys`:**

**Before (lines 80-138):**
```python
with (
    patch("shitvault.event_consumer.settings") as mock_settings,
    patch("shit.db.DatabaseConfig"),
    patch("shit.db.DatabaseClient", return_value=mock_db_client),
    patch("shit.s3.S3Config"),
    patch("shit.s3.S3DataLake", return_value=mock_s3),
    patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
    patch("shit.events.producer.emit_event"),
):
    mock_settings.DATABASE_URL = "sqlite:///test.db"
    mock_settings.S3_BUCKET_NAME = "test-bucket"
    mock_settings.AWS_ACCESS_KEY_ID = "test"
    mock_settings.AWS_SECRET_ACCESS_KEY = "test"
    mock_settings.AWS_REGION = "us-east-1"
    ...
```

**After:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def fake_db_and_s3():
    yield mock_db_client, mock_s3

with (
    patch("shit.services.db_and_s3_service", side_effect=fake_db_and_s3),
    patch("shitvault.s3_processor.S3Processor", return_value=mock_processor),
    patch("shit.events.producer.emit_event"),
):
    ...
```

The mock setup for `mock_db_client` and `mock_s3` remains exactly the same (same mock objects). Only the patching target changes.

**For `test_db_client_cleanup_called_on_success_and_failure`** -- this test currently verifies `mock_db_client.cleanup.assert_awaited_once()`. With the factory, cleanup is handled by the context manager. The test should now verify that the exception still propagates (which it does). The `mock_db_client.cleanup` assertion is no longer meaningful since the mock won't have `cleanup` called on it directly -- the factory handles that. This test should be updated to verify the exception propagates and processing still ran correctly. The assertion `mock_db_client.cleanup.assert_awaited_once()` should be removed.

---

## Documentation Updates

### `shit/README.md`

Add a new section after the existing service descriptions:

```markdown
### Service Initialization Factory (`shit/services.py`)

Async context managers that eliminate boilerplate when initializing DB and S3 services:

```python
from shit.services import db_service, s3_service, db_and_s3_service

# Database only
async with db_service() as db_client:
    async with db_client.get_session() as session:
        ...

# S3 only
async with s3_service() as s3_data_lake:
    ...

# Both (most common)
async with db_and_s3_service() as (db_client, s3_data_lake):
    async with db_client.get_session() as session:
        ...
```

All services are automatically cleaned up when the context manager exits, even on exceptions.
```

### `CHANGELOG.md`

Add under `## [Unreleased]`:

```markdown
### Changed
- **Service Initialization Factory** — Created `shit/services.py` with `db_service()`, `s3_service()`, and `db_and_s3_service()` async context managers, replacing 12-line copy-pasted init blocks in `shitvault/cli.py` and `shitvault/event_consumer.py`
- **Shared CLI Arguments** — Created `shit/cli/shared_args.py` with `add_standard_arguments()` and `validate_standard_args()`, replacing duplicated `--mode`/`--from`/`--to`/`--limit`/`--dry-run`/`--verbose` definitions in `shitpost_ai/cli.py` and `shitposts/cli.py`
```

---

## Stress Testing and Edge Cases

1. **Context manager exception safety** -- The nested `async with db_service()` / `async with s3_service()` pattern in `db_and_s3_service()` ensures that if S3 init fails after DB init succeeds, the DB client is still cleaned up. This is verified by the `test_db_cleanup_called_when_s3_init_fails` test.

2. **Settings singleton** -- The factory reads from the global `settings` singleton. This is the established pattern throughout the codebase. Tests mock `shit.services.settings` to control values.

3. **Import order** -- The factory imports `settings` at module level. This is consistent with how every other module in the project does it. No circular import risk because `shit/services.py` only depends on `shit/config/`, `shit/db/`, and `shit/s3/`.

4. **Thread safety** -- `asyncio.run()` in event consumers creates a new event loop. The context manager works correctly in this scenario since each `asyncio.run()` call gets a fresh context.

5. **CLI argument conflicts** -- `add_standard_arguments()` adds `--mode`, `--from`, `--to`, `--limit`, `--dry-run`, `--verbose`. If a module tries to add any of these again after calling `add_standard_arguments`, argparse will raise a conflict error at parser construction time (not at runtime). This is the desired behavior -- it catches duplicate definitions immediately.

---

## Verification Checklist

1. Run `ruff check shit/services.py shit/cli/shared_args.py` -- verify no lint errors in new files.
2. Run `ruff check shitvault/cli.py shitvault/event_consumer.py shitpost_ai/cli.py shitposts/cli.py` -- verify no lint errors in modified files.
3. Run `ruff format .` -- verify formatting.
4. Run `source venv/bin/activate && pytest shit_tests/shit/test_services.py -v` -- all new factory tests pass.
5. Run `source venv/bin/activate && pytest shit_tests/shit/cli/test_shared_args.py -v` -- all new shared args tests pass.
6. Run `source venv/bin/activate && pytest shit_tests/shitvault/test_shitvault_cli.py -v` -- all existing CLI tests pass with updated mocks.
7. Run `source venv/bin/activate && pytest shit_tests/events/consumers/test_s3_processor.py -v` -- all existing event consumer tests pass with updated mocks.
8. Run `source venv/bin/activate && pytest shit_tests/shitpost_ai/test_shitpost_ai_cli.py -v` -- all existing analyzer CLI tests pass (argument behavior unchanged).
9. Run `source venv/bin/activate && pytest shit_tests/shitposts/test_shitposts_cli.py -v` -- all existing harvester CLI tests pass (argument behavior unchanged).
10. Run `source venv/bin/activate && pytest` -- full suite passes, no regressions.
11. Manually verify: `python -m shitvault --help` still shows all subcommands.
12. Manually verify: `python -m shitpost_ai --help` still shows all arguments including `--batch-size`.
13. Manually verify: `python -m shitposts --help` still shows all arguments including `--max-id` and `--source`.

---

## What NOT To Do

1. **Do NOT refactor `shitvault/cli.py` argument parsing for Part B.** It uses subparsers with `--start-date`/`--end-date` (different from `--from`/`--to`). Forcing it into the shared pattern would either break the CLI interface or add conditional complexity that defeats the purpose.

2. **Do NOT refactor the other event consumers** (`shitpost_ai/event_consumer.py`, `notifications/event_consumer.py`, `shit/market_data/event_consumer.py`). These do not use the same DB+S3 init boilerplate -- they either delegate to higher-level services (`ShitpostAnalyzer`, `AutoBackfillService`) or have no direct DB/S3 init at all. Refactoring them would be scope creep with minimal benefit.

3. **Do NOT make the context managers accept custom config parameters.** The whole point is to eliminate boilerplate by reading from `settings`. If a caller needs custom config, they should use `DatabaseConfig`/`DatabaseClient` directly.

4. **Do NOT add the print helper functions to shared CLI.** The research noted that print helpers are duplicated too, but they are domain-specific (different labels, different stat keys). Extracting them would require a templating abstraction that adds complexity without reducing maintenance burden. Leave them as-is.

5. **Do NOT change `--mode` choices or defaults** in the shared args. The choices (`incremental`, `backfill`, `range`) and default (`incremental`) are identical across all three CLIs. Changing them would alter behavior.

6. **Do NOT remove the domain-specific `validate_*_args()` wrapper functions** from `shitpost_ai/cli.py` and `shitposts/cli.py`. Even though they now just delegate to `validate_standard_args()`, keeping the wrapper preserves the public API. Future domain-specific validation can be added to the wrapper without touching the shared code.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shit/services.py` - "New file: async context managers for DB/S3 initialization"
- `/Users/chris/Projects/shitpost-alpha/shit/cli/shared_args.py` - "New file: reusable argparse argument definitions"
- `/Users/chris/Projects/shitpost-alpha/shitvault/cli.py` - "Primary refactor target: 3 instances of init boilerplate to replace"
- `/Users/chris/Projects/shitpost-alpha/shitvault/event_consumer.py` - "Refactor target: DB+S3 init boilerplate in event worker"
- `/Users/chris/Projects/shitpost-alpha/shitpost_ai/cli.py` - "Refactor target: CLI argument deduplication pattern"

---

**Metadata Summary:**

- Wrote: /Users/chris/Projects/shitpost-alpha/documentation/planning/tech_debt/codebase-health_2026-02-25/03_service-init-factory.md (content provided above -- file creation not possible in read-only mode)
- PR title: `refactor: add service init factory and shared CLI arguments`
- Effort: Medium (~4 hours)
- Risk: Low
- Files modified: 4 | Files created: 4 (2 source + 2 test files, plus 1 `__init__.py` each for `shit/cli/` and `shit_tests/shit/cli/`)
- Dependencies: None
- Unlocks: None