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


def validate_analyzer_args(args) -> None:
    """Validate analyzer command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Raises:
        SystemExit: If arguments are invalid
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")
    
    # Note: --to date is optional for range mode (defaults to today)


def setup_analyzer_logging(verbose: bool = False) -> None:
    """Setup logging for analyzer.
    
    Args:
        verbose: Enable verbose logging
    """
    # Use centralized logging system
    setup_centralized_analyzer_logging(verbose=verbose)


def print_analysis_start(mode: str, limit: Optional[int] = None, batch_size: int = 5) -> None:
    """Print analyzer start message.
    
    Args:
        mode: Analysis mode
        limit: Analysis limit (optional)
        batch_size: Batch size for analysis
    """
    limit_text = f" (limit: {limit})" if limit else ""
    print(f"🚀 Starting Truth Social analysis in {mode} mode{limit_text}...")
    print(f"📊 Batch size: {batch_size}")


def print_analysis_progress(analyzed_count: int, limit: Optional[int] = None) -> None:
    """Print analyzer progress message.
    
    Args:
        analyzed_count: Number of posts analyzed so far
        limit: Analysis limit (optional)
    """
    if limit:
        print(f"📊 Progress: {analyzed_count}/{limit} posts analyzed")
    else:
        print(f"📊 Progress: {analyzed_count} posts analyzed")


def print_analysis_complete(analyzed_count: int, dry_run: bool = False) -> None:
    """Print analyzer completion message.
    
    Args:
        analyzed_count: Total number of posts analyzed
        dry_run: Whether this was a dry run
    """
    print(f"\n🎉 Analysis completed! Total posts: {analyzed_count}")
    
    if dry_run:
        print("🔍 This was a dry run - no results were stored to database")
    else:
        print("✅ All analysis results stored to database successfully")


def print_analysis_error(error: Exception, verbose: bool = False) -> None:
    """Print analyzer error message.
    
    Args:
        error: Exception that occurred
        verbose: Whether to show full traceback
    """
    print(f"\n❌ Analysis failed: {error}")
    
    if verbose:
        import traceback
        traceback.print_exc()


def print_analysis_interrupted() -> None:
    """Print analyzer interruption message."""
    print("\n⏹️  Analysis stopped by user")


def print_analysis_stats(stats: dict) -> None:
    """Print analysis statistics.
    
    Args:
        stats: Analysis statistics dictionary
    """
    print(f"\n📊 Analysis Statistics:")
    print(f"   Total shitposts: {stats.get('total_shitposts', 0)}")
    print(f"   Total analyses: {stats.get('total_analyses', 0)}")
    print(f"   Average confidence: {stats.get('average_confidence', 0.0)}")
    print(f"   Analysis rate: {stats.get('analysis_rate', 0.0)}")


def print_batch_progress(batch_num: int, batch_size: int, total_analyzed: int) -> None:
    """Print batch processing progress.
    
    Args:
        batch_num: Current batch number
        batch_size: Size of current batch
        total_analyzed: Total posts analyzed so far
    """
    print(f"🔄 Processing batch {batch_num} ({batch_size} posts) - Total analyzed: {total_analyzed}")


def print_analysis_result(shitpost_id: str, analysis: dict, dry_run: bool = False) -> None:
    """Print individual analysis result.
    
    Args:
        shitpost_id: ID of the analyzed shitpost
        analysis: Analysis result dictionary
        dry_run: Whether this was a dry run
    """
    assets = analysis.get('assets', [])
    confidence = analysis.get('confidence', 0.0)
    status = "Would analyze" if dry_run else "Analyzed"
    
    print(f"✅ {status}: {shitpost_id} - Assets: {', '.join(assets) if assets else 'None'} (Confidence: {confidence:.1%})")


def print_bypass_result(shitpost_id: str, reason: str, dry_run: bool = False) -> None:
    """Print bypass result for unanalyzable posts.
    
    Args:
        shitpost_id: ID of the bypassed shitpost
        reason: Reason for bypass
        dry_run: Whether this was a dry run
    """
    status = "Would bypass" if dry_run else "Bypassed"
    print(f"⏭️  {status}: {shitpost_id} - {reason}")


def print_analysis_error_result(shitpost_id: str, error: str, dry_run: bool = False) -> None:
    """Print error result for failed analysis.
    
    Args:
        shitpost_id: ID of the shitpost that failed analysis
        error: Error message
        dry_run: Whether this was a dry run
    """
    status = "Would fail" if dry_run else "Failed"
    print(f"❌ {status}: {shitpost_id} - {error}")


# Common CLI examples for help text
ANALYZER_EXAMPLES = """
Examples:
  # Incremental analysis (default)
  python -m shitpost_ai
  
  # Full historical backfill analysis
  python -m shitpost_ai --mode backfill
  
  # Date range analysis
  python -m shitpost_ai --mode range --from 2024-01-01 --to 2024-01-31
  
  # Analysis from specific date onwards (using range mode)
  python -m shitpost_ai --mode range --from 2024-01-01
  
  # Limited backfill with custom batch size
  python -m shitpost_ai --mode backfill --limit 100 --batch-size 10
  
  # Dry run to see what would be analyzed
  python -m shitpost_ai --mode backfill --limit 10 --dry-run
  
  # Verbose logging
  python -m shitpost_ai --verbose
"""
