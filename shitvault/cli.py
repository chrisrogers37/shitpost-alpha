"""
Database CLI
Command-line interface for database operations.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from .s3_to_database_processor import S3ToDatabaseProcessor
from .shitpost_db import ShitpostDatabase

logger = logging.getLogger(__name__)


def create_database_parser() -> argparse.ArgumentParser:
    """Create argument parser for database operations."""
    parser = argparse.ArgumentParser(
        description="Database operations for Shitpost-Alpha",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all S3 data to database
  python -m shitvault.cli process-s3

  # Process S3 data with date range
  python -m shitvault.cli process-s3 --start-date 2024-01-01 --end-date 2024-01-31

  # Process S3 data with limit
  python -m shitvault.cli process-s3 --limit 1000

  # Get database statistics
  python -m shitvault.cli stats

  # Get processing statistics
  python -m shitvault.cli processing-stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process S3 data command
    process_parser = subparsers.add_parser('process-s3', help='Process S3 data to database')
    process_parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    process_parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    process_parser.add_argument('--limit', type=int, help='Maximum number of records to process')
    process_parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    
    # Database stats command
    stats_parser = subparsers.add_parser('stats', help='Get database statistics')
    
    # Processing stats command
    processing_stats_parser = subparsers.add_parser('processing-stats', help='Get S3 to database processing statistics')
    
    # Global options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Log level')
    
    return parser


def setup_database_logging(args):
    """Setup logging for database operations."""
    log_level = getattr(logging, args.log_level.upper())
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def print_database_start(args):
    """Print database operation start message."""
    print(f"\n🚀 Starting Database Operation: {args.command}")
    print(f"📊 Log Level: {args.log_level}")
    if args.verbose:
        print(f"🔍 Verbose Mode: Enabled")
    print("-" * 50)


def print_database_complete(stats: dict):
    """Print database operation completion message."""
    print("\n✅ Database Operation Completed Successfully!")
    print(f"📈 Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("-" * 50)


def print_database_error(error: Exception):
    """Print database operation error message."""
    print(f"\n❌ Database Operation Failed: {error}")
    print("-" * 50)


def print_database_interrupted():
    """Print database operation interruption message."""
    print("\n⚠️  Database Operation Interrupted")
    print("-" * 50)


async def process_s3_data(args):
    """Process S3 data to database."""
    try:
        print_database_start(args)
        
        # Parse dates
        start_date = None
        end_date = None
        
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
        # Initialize processor
        processor = S3ToDatabaseProcessor()
        await processor.initialize()
        
        if args.dry_run:
            logger.info("Dry run mode - no database writes will be performed")
            # In dry run, just get stats
            stats = await processor.get_processing_stats()
            print_database_complete(stats)
        else:
            # Process S3 data
            stats = await processor.process_s3_stream(
                start_date=start_date,
                end_date=end_date,
                limit=args.limit
            )
            print_database_complete(stats)
        
        # Cleanup
        await processor.cleanup()
        
    except Exception as e:
        print_database_error(e)
        raise


async def get_database_stats(args):
    """Get database statistics."""
    try:
        print_database_start(args)
        
        # Initialize database
        db_manager = ShitpostDatabase()
        await db_manager.initialize()
        
        # Get stats
        stats = await db_manager.get_database_stats()
        print_database_complete(stats)
        
        # Cleanup
        await db_manager.cleanup()
        
    except Exception as e:
        print_database_error(e)
        raise


async def get_processing_stats(args):
    """Get S3 to database processing statistics."""
    try:
        print_database_start(args)
        
        # Initialize processor
        processor = S3ToDatabaseProcessor()
        await processor.initialize()
        
        # Get stats
        stats = await processor.get_processing_stats()
        print_database_complete(stats)
        
        # Cleanup
        await processor.cleanup()
        
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
        if args.command == 'process-s3':
            await process_s3_data(args)
        elif args.command == 'stats':
            await get_database_stats(args)
        elif args.command == 'processing-stats':
            await get_processing_stats(args)
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
            
    except KeyboardInterrupt:
        print_database_interrupted()
    except Exception as e:
        print_database_error(e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
