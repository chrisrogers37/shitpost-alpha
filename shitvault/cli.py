"""
Database CLI (Refactored)
Command-line interface for database operations using modular architecture.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shit.s3 import S3Config, S3DataLake
from shit.logging import (
    setup_database_logging as setup_centralized_database_logging,
    print_success,
    print_error,
    print_info,
    print_warning
)
from .shitpost_operations import ShitpostOperations
from .prediction_operations import PredictionOperations
from .s3_processor import S3Processor
from .statistics import Statistics

logger = logging.getLogger(__name__)


def create_database_parser() -> argparse.ArgumentParser:
    """Create argument parser for database operations."""
    parser = argparse.ArgumentParser(
        description="Database operations for Shitpost-Alpha (Refactored)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Incremental processing (default) - only new S3 files
  python -m shitvault load-database-from-s3

  # Full backfill processing - all S3 files
  python -m shitvault load-database-from-s3 --mode backfill

  # Date range processing
  python -m shitvault load-database-from-s3 --mode range --start-date 2024-01-01 --end-date 2024-01-31

  # Load S3 data with limit
  python -m shitvault load-database-from-s3 --limit 1000

  # Get database statistics
  python -m shitvault stats

  # Get processing statistics
  python -m shitvault processing-stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process S3 data command
    process_parser = subparsers.add_parser('load-database-from-s3', help='Load S3 data into database')
    process_parser.add_argument('--mode', choices=['incremental', 'backfill', 'range'], default='incremental', help='Processing mode (default: incremental)')
    process_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    process_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    process_parser.add_argument('--limit', type=int, help='Maximum number of records to process')
    process_parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    
    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Get database statistics')
    
    # Processing statistics command
    processing_stats_parser = subparsers.add_parser('processing-stats', help='Get S3 and database processing statistics')
    
    return parser


def setup_database_logging(args):
    """Setup logging for database operations using centralized logging."""
    verbose = hasattr(args, 'verbose') and args.verbose
    setup_centralized_database_logging(verbose=verbose)


def print_database_start(args):
    """Print database operation start message."""
    print_info(f"🚀 Starting database operation: {args.command}")
    if hasattr(args, 'start_date') and args.start_date:
        print_info(f"   Start date: {args.start_date}")
    if hasattr(args, 'end_date') and args.end_date:
        print_info(f"   End date: {args.end_date}")
    if hasattr(args, 'limit') and args.limit:
        print_info(f"   Limit: {args.limit}")
    if hasattr(args, 'dry_run') and args.dry_run:
        print_info(f"   Mode: DRY RUN (no changes will be made)")


def print_database_complete(result):
    """Print database operation completion message."""
    print_success("Database operation completed successfully!")
    if isinstance(result, dict):
        for key, value in result.items():
            print_info(f"   {key}: {value}")
    else:
        print_info(f"   Result: {result}")


def print_database_error(error):
    """Print database operation error message."""
    print_error(f"Database operation failed: {error}")


def print_database_interrupted():
    """Print database operation interrupted message."""
    print_warning("Database operation interrupted by user")


async def process_s3_data(args):
    """Process S3 data to database using modular architecture."""
    try:
        print_database_start(args)
        
        # Parse dates
        start_date = None
        end_date = None
        
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
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
            
            # Process S3 data
            stats = await s3_processor.process_s3_to_database(
                start_date=start_date,
                end_date=end_date,
                limit=args.limit,
                incremental=(args.mode == 'incremental'),
                dry_run=args.dry_run
            )
            
            print_database_complete(stats)
        
        # Cleanup
        await db_client.cleanup()
        
    except Exception as e:
        print_database_error(e)
        raise


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


async def main():
    """Main CLI entry point."""
    parser = create_database_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup logging
    setup_database_logging(args)
    
    try:
        # Execute command
        if args.command == 'load-database-from-s3':
            await process_s3_data(args)
        elif args.command == 'stats':
            await get_database_stats(args)
        elif args.command == 'processing-stats':
            await get_processing_stats(args)
        else:
            print_error(f"Unknown command: {args.command}")
            parser.print_help()
            
    except KeyboardInterrupt:
        print_database_interrupted()
    except Exception as e:
        print_database_error(e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
