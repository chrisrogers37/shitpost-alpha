"""
Shared CLI functionality for Truth Social harvesters.
"""

import argparse
import logging
from typing import Optional


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
    
    return parser


def validate_harvester_args(args) -> None:
    """Validate harvester command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Raises:
        SystemExit: If arguments are invalid
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")
    
    # Note: --to date is optional for range mode (defaults to today)


def setup_harvester_logging(verbose: bool = False) -> None:
    """Setup logging for harvester.
    
    Args:
        verbose: Enable verbose logging
    """
    # Configure root logger
    root_logger = logging.getLogger()
    if verbose:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)
    
    # Also configure the shitposts module logger specifically
    shitposts_logger = logging.getLogger('shitposts')
    if verbose:
        shitposts_logger.setLevel(logging.DEBUG)
    else:
        shitposts_logger.setLevel(logging.INFO)
    
    # Add console handler if none exists
    if not any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add handler to root logger
        root_logger.addHandler(console_handler)


def print_harvest_start(mode: str, limit: Optional[int] = None) -> None:
    """Print harvester start message.
    
    Args:
        mode: Harvesting mode
        limit: Harvest limit (optional)
    """
    limit_text = f" (limit: {limit})" if limit else ""
    print(f"🚀 Starting Truth Social S3 harvesting in {mode} mode{limit_text}...")


def print_harvest_progress(harvested_count: int, limit: Optional[int] = None) -> None:
    """Print harvester progress message.
    
    Args:
        harvested_count: Number of posts harvested so far
        limit: Harvest limit (optional)
    """
    if limit:
        print(f"📊 Progress: {harvested_count}/{limit} posts harvested")
    else:
        print(f"📊 Progress: {harvested_count} posts harvested")


def print_harvest_complete(harvested_count: int, dry_run: bool = False) -> None:
    """Print harvester completion message.
    
    Args:
        harvested_count: Total number of posts harvested
        dry_run: Whether this was a dry run
    """
    print(f"\n🎉 S3 harvesting completed! Total posts: {harvested_count}")
    
    if dry_run:
        print("🔍 This was a dry run - no data was stored to S3")
    else:
        print("✅ All data stored to S3 successfully")


def print_harvest_error(error: Exception, verbose: bool = False) -> None:
    """Print harvester error message.
    
    Args:
        error: Exception that occurred
        verbose: Whether to show full traceback
    """
    print(f"\n❌ Harvesting failed: {error}")
    
    if verbose:
        import traceback
        traceback.print_exc()


def print_harvest_interrupted() -> None:
    """Print harvester interruption message."""
    print("\n⏹️  Harvesting stopped by user")


def print_s3_stats(stats) -> None:
    """Print S3 storage statistics.
    
    Args:
        stats: S3 statistics (dict or S3Stats object)
    """
    print(f"\n📊 S3 Storage Statistics:")
    
    # Handle both dict and S3Stats object
    if hasattr(stats, 'total_files'):
        # S3Stats object
        print(f"   Total files: {stats.total_files}")
        print(f"   Total size: {stats.total_size_mb} MB")
        print(f"   Bucket: {stats.bucket}")
        print(f"   Prefix: {stats.prefix}")
    else:
        # Dictionary
        print(f"   Total files: {stats.get('total_files', 0)}")
        print(f"   Total size: {stats.get('total_size_mb', 0)} MB")
        print(f"   Bucket: {stats.get('bucket', 'N/A')}")
        print(f"   Prefix: {stats.get('prefix', 'N/A')}")


def print_database_stats(stats: dict) -> None:
    """Print database storage statistics.
    
    Args:
        stats: Database statistics dictionary
    """
    print(f"\n📊 Database Statistics:")
    print(f"   Total shitposts: {stats.get('total_shitposts', 0)}")
    print(f"   Total analyses: {stats.get('total_analyses', 0)}")
    print(f"   Average confidence: {stats.get('average_confidence', 0.0)}")
    print(f"   Analysis rate: {stats.get('analysis_rate', 0.0)}")


# Common CLI examples for help text
HARVESTER_EXAMPLES = """
Examples:
  # Incremental harvesting (default)
  python -m shitposts
  
  # Full historical backfill to S3
  python -m shitposts --mode backfill
  
  # Date range harvesting to S3
  python -m shitposts --mode range --from 2024-01-01 --to 2024-01-31
  
  # Harvest from specific date onwards to S3 (using range mode)
  python -m shitposts --mode range --from 2024-01-01
  
  # Limited backfill with dry run
  python -m shitposts --mode backfill --limit 100 --dry-run
  
  # Verbose logging
  python -m shitposts --verbose
  
  # Resume backfill from specific post ID
  python -m shitposts --mode backfill --max-id 114858915682735686
"""
