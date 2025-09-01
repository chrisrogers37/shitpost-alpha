#!/usr/bin/env python3
"""
Shitpost-Alpha Main Orchestrator
Coordinates the Truth Social monitoring, LLM analysis, and alert pipeline.
"""

import asyncio
import logging
from typing import Optional

from shit.config.shitpost_settings import Settings
from shitposts.truth_social_shitposts import TruthSocialShitposts
from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer
from shitvault.shitpost_db import ShitpostDatabase
from shit.utils.error_handling import handle_exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShitpostAlpha:
    """Main orchestrator for the Shitpost-Alpha pipeline."""
    
    def __init__(self, harvest_mode="incremental", start_date=None, end_date=None, limit=None):
        self.settings = Settings()
        self.db_manager = ShitpostDatabase()
        self.truth_monitor = TruthSocialShitposts(
            mode=harvest_mode,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        self.llm_analyzer = ShitpostAnalyzer()
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Shitpost-Alpha...")
        
        # Initialize database
        await self.db_manager.initialize()
        
        # Initialize Truth Social monitor
        await self.truth_monitor.initialize()
        
        # Initialize LLM analyzer
        await self.llm_analyzer.initialize()
        
        logger.info("Shitpost-Alpha initialized successfully")
    
    async def run_ingestion_only(self):
        """Run only the shitpost harvesting pipeline."""
        logger.info("Starting Truth Social shitpost harvesting pipeline...")
        
        try:
            await self.db_manager.initialize()
            await self.truth_monitor.initialize()
            
            # Start harvesting shitposts
            async for shitpost in self.truth_monitor.harvest_shitposts():
                # Store shitposts directly in database
                shitpost_id = await self.db_manager.store_shitpost(shitpost)
                if shitpost_id:
                    logger.info(f"Stored shitpost {shitpost_id} in database")
                
        except KeyboardInterrupt:
            logger.info("Ingestion stopped by user...")
        except Exception as e:
            logger.error(f"Fatal error in ingestion: {e}")
            await handle_exceptions(e)
        finally:
            await self.cleanup()
    
    async def run_analysis_only(self):
        """Run only the shitpost analysis pipeline."""
        logger.info("Starting shitpost analysis pipeline...")
        
        try:
            await self.llm_analyzer.initialize()
            
            # Run continuous shitpost analysis
            await self.llm_analyzer.run_continuous_analysis(interval_seconds=300)
            
        except KeyboardInterrupt:
            logger.info("Analysis stopped by user...")
        except Exception as e:
            logger.error(f"Fatal error in analysis: {e}")
            await handle_exceptions(e)
        finally:
            await self.llm_analyzer.cleanup()
    
    async def run_full_pipeline(self):
        """Run both shitpost harvesting and analysis in parallel."""
        logger.info("Starting full Shitpost-Alpha pipeline...")
        
        try:
            await self.initialize()
            
            # Run shitpost harvesting and analysis concurrently
            harvesting_task = asyncio.create_task(self._run_harvesting())
            analysis_task = asyncio.create_task(self._run_analysis())
            
            # Wait for both tasks
            await asyncio.gather(harvesting_task, analysis_task)
            
        except KeyboardInterrupt:
            logger.info("Full pipeline stopped by user...")
        except Exception as e:
            logger.error(f"Fatal error in full pipeline: {e}")
            await handle_exceptions(e)
        finally:
            await self.cleanup()
    
    async def _run_harvesting(self):
        """Internal shitpost harvesting task."""
        try:
            async for shitpost in self.truth_monitor.harvest_shitposts():
                shitpost_id = await self.db_manager.store_shitpost(shitpost)
                if shitpost_id:
                    logger.info(f"Stored shitpost {shitpost_id} in database")
        except Exception as e:
            logger.error(f"Error in shitpost harvesting task: {e}")
    
    async def _run_analysis(self):
        """Internal analysis task."""
        try:
            await self.llm_analyzer.run_continuous_analysis(interval_seconds=300)
        except Exception as e:
            logger.error(f"Error in analysis task: {e}")
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        await self.truth_monitor.cleanup()
        await self.db_manager.cleanup()


async def main():
    """Main entry point."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Shitpost-Alpha: Truth Social monitoring and analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline (default)
  python main.py
  
  # Run ingestion only
  python main.py --mode ingestion
  
  # Run analysis only
  python main.py --mode analysis
  
  # Run with specific harvesting mode
  python main.py --harvest-mode backfill --limit 100
  
  # Run with date range
  python main.py --harvest-mode range --from 2024-01-01 --to 2024-01-31
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["ingestion", "analysis", "full"], 
        default="full", 
        help="Pipeline mode (default: full)"
    )
    parser.add_argument(
        "--harvest-mode", 
        choices=["incremental", "backfill", "range", "from-date"], 
        default="incremental", 
        help="Truth Social harvesting mode (default: incremental)"
    )
    parser.add_argument(
        "--from", 
        dest="start_date", 
        help="Start date for range/from-date harvest modes (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", 
        dest="end_date", 
        help="End date for range harvest mode (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Maximum number of posts to harvest (optional)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.harvest_mode in ["range", "from-date"] and not args.start_date:
        parser.error(f"--from date is required for {args.harvest_mode} harvest mode")
    
    if args.harvest_mode == "range" and not args.end_date:
        parser.error("--to date is required for range harvest mode")
    
    app = ShitpostAlpha(
        harvest_mode=args.harvest_mode,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit
    )
    
    if args.mode == "ingestion":
        print("🚀 Running Truth Social shitpost harvesting only...")
        await app.run_ingestion_only()
    elif args.mode == "analysis":
        print("🧠 Running shitpost analysis only...")
        await app.run_analysis_only()
    elif args.mode == "full":
        print("🎯 Running full pipeline (shitpost harvesting + analysis)...")
        await app.run_full_pipeline()
    else:
        print("Usage: python main.py [--mode ingestion|analysis|full]")
        print("  --mode ingestion: Run only Truth Social shitpost harvesting")
        print("  --mode analysis:  Run only shitpost analysis")
        print("  --mode full:      Run both shitpost harvesting and analysis (default)")
        print("\nHarvesting options:")
        print("  --harvest-mode: incremental, backfill, range, from-date")
        print("  --from: Start date (YYYY-MM-DD)")
        print("  --to: End date (YYYY-MM-DD)")
        print("  --limit: Maximum posts to harvest")


if __name__ == "__main__":
    asyncio.run(main())
