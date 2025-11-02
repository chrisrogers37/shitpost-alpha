"""
CLI entry point for shitpost analysis.
"""

import asyncio
import logging
import sys

from shitpost_ai.cli import (
    create_analyzer_parser, validate_analyzer_args, setup_analyzer_logging,
    print_analysis_start, print_analysis_progress, print_analysis_complete,
    print_analysis_error, print_analysis_interrupted, print_analysis_stats,
    print_batch_progress, print_analysis_result, print_bypass_result, print_analysis_error_result,
    ANALYZER_EXAMPLES
)
from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer


async def main():
    """CLI entry point for shitpost analysis."""
    parser = create_analyzer_parser(
        description="Shitpost AI analyzer with multiple modes",
        epilog=ANALYZER_EXAMPLES
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    validate_analyzer_args(args)
    
    # Setup logging
    setup_analyzer_logging(args.verbose)
    
    # Print start message
    print_analysis_start(args.mode, args.limit, args.batch_size)
    
    # Create analyzer with appropriate configuration
    analyzer = ShitpostAnalyzer(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        batch_size=args.batch_size
    )
    
    try:
        await analyzer.initialize()
        
        # Use session as context manager for proper cleanup
        async with analyzer.db_client.get_session() as session:
            # Re-initialize operations with session context
            from shit.db import DatabaseOperations
            from shitvault.shitpost_operations import ShitpostOperations
            from shitvault.prediction_operations import PredictionOperations
            
            analyzer.db_ops = DatabaseOperations(session)
            analyzer.shitpost_ops = ShitpostOperations(analyzer.db_ops)
            analyzer.prediction_ops = PredictionOperations(analyzer.db_ops)
            
            if args.dry_run:
                print("🔍 DRY RUN MODE - No analysis will be saved to database")
                print("📝 Would analyze unprocessed shitposts based on current configuration")
                print(f"   Mode: {args.mode}")
                if args.start_date:
                    print(f"   From: {args.start_date}")
                if args.end_date:
                    print(f"   To: {args.end_date}")
                if args.limit:
                    print(f"   Limit: {args.limit}")
                print(f"   Batch Size: {args.batch_size}")
            else:
                # Run actual analysis
                analyzed_count = await analyzer.analyze_shitposts(dry_run=args.dry_run)
                print_analysis_complete(analyzed_count, args.dry_run)
        
    except KeyboardInterrupt:
        print_analysis_interrupted()
    except Exception as e:
        print_analysis_error(e, args.verbose)
        sys.exit(1)
    finally:
        await analyzer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
