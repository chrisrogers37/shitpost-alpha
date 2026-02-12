#!/usr/bin/env python3
"""
Shitpost-Alpha Main Orchestrator
Coordinates the Truth Social monitoring and LLM analysis pipeline by executing sub-CLIs.
"""

import asyncio
import sys
import argparse
from typing import List, Optional

# Use centralized logging for beautiful output
from shit.logging import setup_cli_logging, get_service_logger, print_success, print_error, print_info, print_warning

# Configure logging will be set up in main() based on args
logger = get_service_logger("orchestrator")


async def _execute_subprocess(cmd: list[str], phase_name: str, emoji: str) -> bool:
    """Execute a subprocess and return whether it succeeded.

    Args:
        cmd: Command and arguments to execute.
        phase_name: Human-readable name for logging (e.g., "Harvesting").
        emoji: Emoji prefix for log messages.

    Returns:
        True if subprocess exited with code 0.
    """
    logger.info(f"{emoji} Executing {phase_name} CLI: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ {phase_name} completed successfully")
            if stdout:
                print(f"📊 {phase_name} Output:")
                print(stdout.decode())
            return True
        else:
            logger.error(f"❌ {phase_name} failed with return code {process.returncode}")
            if stderr:
                print(f"🚨 {phase_name} Errors:")
                print(stderr.decode())
            return False

    except Exception as e:
        logger.error(f"❌ Failed to execute {phase_name} CLI: {e}")
        return False


def _build_harvesting_cmd(args) -> list[str]:
    """Build command for harvesting CLI."""
    cmd = [sys.executable, "-m", "shitposts", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if hasattr(args, "max_id") and args.max_id:
        cmd.extend(["--max-id", args.max_id])
    if args.verbose:
        cmd.append("--verbose")
    return cmd


def _build_harvesting_cmd_for_source(args, source_name: str) -> list[str]:
    """Build command for a specific source's harvesting CLI."""
    cmd = [sys.executable, "-m", "shitposts", "--mode", args.mode, "--source", source_name]
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if hasattr(args, "max_id") and args.max_id:
        cmd.extend(["--max-id", args.max_id])
    if args.verbose:
        cmd.append("--verbose")
    return cmd


def _build_s3_to_db_cmd(args) -> list[str]:
    """Build command for S3-to-database CLI."""
    cmd = [sys.executable, "-m", "shitvault", "load-database-from-s3", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--start-date", args.from_date])
    if args.to_date:
        cmd.extend(["--end-date", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    return cmd


def _build_analysis_cmd(args) -> list[str]:
    """Build command for analysis CLI."""
    cmd = [sys.executable, "-m", "shitpost_ai", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.batch_size:
        cmd.extend(["--batch-size", str(args.batch_size)])
    if args.verbose:
        cmd.append("--verbose")
    return cmd


async def execute_harvesting_cli(args) -> bool:
    """Execute harvesting CLI for all enabled sources.

    If args has a 'sources' attribute, iterate over each source.
    Otherwise, fall back to the default single-source behavior.
    """
    sources = getattr(args, 'sources', None)

    if not sources:
        # Legacy single-source mode
        return await _execute_subprocess(_build_harvesting_cmd(args), "Harvesting", "🚀")

    # Multi-source mode
    all_success = True
    for source_name in sources:
        cmd = _build_harvesting_cmd_for_source(args, source_name)
        success = await _execute_subprocess(
            cmd, f"Harvesting ({source_name})", "🚀"
        )
        if not success:
            logger.warning(f"Harvesting failed for source: {source_name}")
            all_success = False
            # Continue with other sources even if one fails

    return all_success


async def execute_s3_to_database_cli(args) -> bool:
    """Execute the S3 to Database CLI with appropriate parameters."""
    return await _execute_subprocess(_build_s3_to_db_cmd(args), "S3 to Database", "💾")


async def execute_analysis_cli(args) -> bool:
    """Execute the analysis CLI with appropriate parameters."""
    return await _execute_subprocess(_build_analysis_cmd(args), "Analysis", "🧠")


async def main():
    """Main entry point for orchestrating the Shitpost-Alpha pipeline."""
    parser = argparse.ArgumentParser(
        description="Shitpost-Alpha: Orchestrates Truth Social monitoring and LLM analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Steady state monitoring (default)
  python shitpost_alpha.py

  # Full historical backfill
  python shitpost_alpha.py --mode backfill --limit 1000

  # Date range processing (with end date)
  python shitpost_alpha.py --mode range --from 2024-01-01 --to 2024-01-31 --limit 100

  # Date range processing (from date to today)
  python shitpost_alpha.py --mode range --from 2024-01-01 --limit 100

  # Custom analysis parameters
  python shitpost_alpha.py --mode backfill --batch-size 10

  # Complete pipeline: API → S3 → Database → LLM → Database
  python shitpost_alpha.py --mode incremental --limit 50
        """
    )

    # Pipeline mode (mirrors sub-CLI exactly)
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "range"],
        default="incremental",
        help="Processing mode for both harvesting and analysis (default: incremental)"
    )

    # Shared parameters (apply to both phases)
    parser.add_argument(
        "--from",
        dest="from_date",
        help="Start date for both phases (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        help="End date for both phases (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit for both phases"
    )

    # Analysis-specific parameters
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of posts to process in each analysis batch (default: 5)"
    )

    # General options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running"
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=None,
        help="Comma-separated list of harvester sources to run (e.g., truth_social,twitter). Default: all enabled."
    )

    args = parser.parse_args()

    # Setup centralized logging
    setup_cli_logging(verbose=args.verbose)

    # Validate arguments
    if args.mode in ["range", "from-date"]:
        if not args.from_date:
            parser.error(f"--from date is required for {args.mode} mode")

    # Note: --to date is optional for range mode (defaults to today)

    # Parse sources list
    if args.sources:
        args.sources = [s.strip() for s in args.sources.split(",")]
    else:
        from shit.config.shitpost_settings import settings as app_settings
        args.sources = app_settings.get_enabled_harvester_names()

    if args.dry_run:
        print_info("DRY RUN MODE - No commands will be executed")
        print_info(f"Processing Mode: {args.mode}")
        print_info(f"Sources: {', '.join(args.sources)}")
        print_info(f"Shared Settings: from={args.from_date}, to={args.to_date}, limit={args.limit}")
        print_info(f"Analysis Parameters: batch_size={args.batch_size}")
        print_info("\nCommands that would be executed:")
        for i, source in enumerate(args.sources, 1):
            cmd = _build_harvesting_cmd_for_source(args, source)
            print_info(f"  {i}a. Harvesting ({source}): {' '.join(cmd)}")
        print_info(f"  2. S3 to Database: {' '.join(_build_s3_to_db_cmd(args))}")
        print_info(f"  3. LLM Analysis: {' '.join(_build_analysis_cmd(args))}")
        return

    print_info(f"🎯 Starting Shitpost-Alpha pipeline in {args.mode} mode...")

    try:
        print_info("🚀 Phase 1: Truth Social Harvesting (API → S3)")
        harvest_success = await execute_harvesting_cli(args)

        if not harvest_success:
            print_error("Harvesting failed! Stopping pipeline.")
            sys.exit(1)

        print_info("💾 Phase 2: S3 to Database Processing")
        s3_to_db_success = await execute_s3_to_database_cli(args)

        if not s3_to_db_success:
            print_error("S3 to Database processing failed! Stopping pipeline.")
            sys.exit(1)

        print_info("🧠 Phase 3: LLM Analysis")
        analysis_success = await execute_analysis_cli(args)

        if analysis_success:
            print_success("Full pipeline completed successfully!")
            print_info("📊 Pipeline Summary:")
            print_success("  API → S3: Raw data harvested")
            print_success("  S3 → Database: Data loaded")
            print_success("  Database → LLM → Database: Analysis complete")
        else:
            print_error("Analysis failed! Pipeline incomplete.")
            sys.exit(1)

    except KeyboardInterrupt:
        print_warning("\nPipeline stopped by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
