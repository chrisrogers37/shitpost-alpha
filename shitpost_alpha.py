#!/usr/bin/env python3
"""
Shitpost-Alpha Main Orchestrator
Coordinates the Truth Social monitoring and LLM analysis pipeline by executing sub-CLIs.
"""

import asyncio
import logging
import sys
import argparse
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def execute_harvesting_cli(args) -> bool:
    """Execute the harvesting CLI with appropriate parameters."""
    cmd = [
        sys.executable, "-m", "shitposts",
        "--mode", args.mode
    ]
    
    # Add date parameters (use same names as sub-CLI)
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if hasattr(args, 'max_id') and args.max_id:
        cmd.extend(["--max-id", args.max_id])
    
    if args.verbose:
        cmd.append("--verbose")
    
    logger.info(f"🚀 Executing harvesting CLI: {' '.join(cmd)}")
    
    try:
        # Execute harvesting CLI
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream output in real-time for progress reporting
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ Harvesting completed successfully")
            if stdout:
                print("📊 Harvesting Output:")
                print(stdout.decode())
            return True
        else:
            logger.error(f"❌ Harvesting failed with return code {process.returncode}")
            if stderr:
                print("🚨 Harvesting Errors:")
                print(stderr.decode())
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to execute harvesting CLI: {e}")
        return False


async def execute_s3_to_database_cli(args) -> bool:
    """Execute the S3 to Database CLI with appropriate parameters."""
    cmd = [
        sys.executable, "-m", "shitvault",
        "load-database-from-s3"
    ]
    
    # Add mode parameter (incremental is default, so only add if not incremental)
    if args.mode != "incremental":
        cmd.extend(["--mode", args.mode])
    
    # Add date parameters (use same names as sub-CLI)
    if args.from_date:
        cmd.extend(["--start-date", args.from_date])
    if args.to_date:
        cmd.extend(["--end-date", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    
    # Note: verbose is handled by the main parser, not subcommands
    
    logger.info(f"💾 Executing S3 to Database CLI: {' '.join(cmd)}")
    
    try:
        # Execute S3 to Database CLI
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream output in real-time for progress reporting
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ S3 to Database processing completed successfully")
            if stdout:
                print("📊 S3 to Database Output:")
                print(stdout.decode())
            return True
        else:
            logger.error(f"❌ S3 to Database processing failed with return code {process.returncode}")
            if stderr:
                print("🚨 S3 to Database Errors:")
                print(stderr.decode())
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to execute S3 to Database CLI: {e}")
        return False


async def execute_analysis_cli(args) -> bool:
    """Execute the analysis CLI with appropriate parameters."""
    cmd = [
        sys.executable, "-m", "shitpost_ai",
        "--mode", args.mode
    ]
    
    # Add date parameters (use same names as sub-CLI)
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    
    # Add analysis-specific parameters
    if args.batch_size:
        cmd.extend(["--batch-size", str(args.batch_size)])
    
    if args.verbose:
        cmd.append("--verbose")
    
    logger.info(f"🧠 Executing analysis CLI: {' '.join(cmd)}")
    
    try:
        # Execute analysis CLI
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream output in real-time for progress reporting
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ Analysis completed successfully")
            if stdout:
                print("📊 Analysis Output:")
                print(stdout.decode())
            return True
        else:
            logger.error(f"❌ Analysis failed with return code {process.returncode}")
            if stderr:
                print("🚨 Analysis Errors:")
                print(stderr.decode())
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to execute analysis CLI: {e}")
        return False


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
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate arguments
    if args.mode in ["range", "from-date"]:
        if not args.from_date:
            parser.error(f"--from date is required for {args.mode} mode")
    
    # Note: --to date is optional for range mode (defaults to today)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No commands will be executed")
        print(f"Processing Mode: {args.mode}")
        print(f"Shared Settings: from={args.from_date}, to={args.to_date}, limit={args.limit}")
        print(f"Analysis Parameters: batch_size={args.batch_size}")
        print("\n📋 Commands that would be executed:")
        
        # Show harvesting command
        harvest_cmd = [
            sys.executable, "-m", "shitposts",
            "--mode", args.mode
        ]
        if args.from_date:
            harvest_cmd.extend(["--from", args.from_date])
        if args.to_date:
            harvest_cmd.extend(["--to", args.to_date])
        if args.limit:
            harvest_cmd.extend(["--limit", str(args.limit)])
        if args.verbose:
            harvest_cmd.append("--verbose")
        print(f"  1. Harvesting: {' '.join(harvest_cmd)}")
        
        # Show S3 to Database command
        s3_cmd = [
            sys.executable, "-m", "shitvault",
            "load-database-from-s3"
        ]
        if args.mode != "incremental":
            s3_cmd.extend(["--mode", args.mode])
        if args.from_date:
            s3_cmd.extend(["--start-date", args.from_date])
        if args.to_date:
            s3_cmd.extend(["--end-date", args.to_date])
        if args.limit:
            s3_cmd.extend(["--limit", str(args.limit)])
        print(f"  2. S3 to Database: {' '.join(s3_cmd)}")
        
        # Show LLM Analysis command
        analysis_cmd = [
            sys.executable, "-m", "shitpost_ai",
            "--mode", args.mode,
            "--batch-size", str(args.batch_size)
        ]
        if args.from_date:
            analysis_cmd.extend(["--from", args.from_date])
        if args.to_date:
            analysis_cmd.extend(["--to", args.to_date])
        if args.limit:
            analysis_cmd.extend(["--limit", str(args.limit)])
        if args.verbose:
            analysis_cmd.append("--verbose")
        print(f"  3. LLM Analysis: {' '.join(analysis_cmd)}")
        
        return
    
    print(f"🎯 Starting Shitpost-Alpha pipeline in {args.mode} mode...")
    
    try:
        print("🚀 Phase 1: Truth Social Harvesting (API → S3)")
        harvest_success = await execute_harvesting_cli(args)
        
        if not harvest_success:
            print("❌ Harvesting failed! Stopping pipeline.")
            sys.exit(1)
        
        print("💾 Phase 2: S3 to Database Processing")
        s3_to_db_success = await execute_s3_to_database_cli(args)
        
        if not s3_to_db_success:
            print("❌ S3 to Database processing failed! Stopping pipeline.")
            sys.exit(1)
        
        print("🧠 Phase 3: LLM Analysis")
        analysis_success = await execute_analysis_cli(args)
        
        if analysis_success:
            print("🎉 Full pipeline completed successfully!")
            print("📊 Pipeline Summary:")
            print("  ✅ API → S3: Raw data harvested")
            print("  ✅ S3 → Database: Data loaded")
            print("  ✅ Database → LLM → Database: Analysis complete")
        else:
            print("❌ Analysis failed! Pipeline incomplete.")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⏹️  Pipeline stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
