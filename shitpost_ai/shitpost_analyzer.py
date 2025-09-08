#!/usr/bin/env python3
"""
Shitpost Analyzer
Business logic orchestrator for analyzing shitposts with enhanced context.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from shit.config.shitpost_settings import Settings
from shitpost_ai.llm_client import LLMClient
from shitvault.shitpost_db import ShitpostDatabase
from shit.utils.error_handling import handle_exceptions

logger = logging.getLogger(__name__)


class ShitpostAnalyzer:
    """Analyzes shitposts for financial implications with enhanced context."""
    
    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None, batch_size=5):
        """Initialize the shitpost analyzer.
        
        Args:
            mode: Analysis mode - "incremental", "backfill", "range"
            start_date: Start date for range mode (YYYY-MM-DD)
            end_date: End date for range mode (YYYY-MM-DD)
            limit: Maximum number of posts to analyze (optional)
            batch_size: Number of posts to process in each batch
        """
        self.settings = Settings()
        self.db_manager = ShitpostDatabase()
        self.llm_client = LLMClient()
        self.launch_date = self.settings.SYSTEM_LAUNCH_DATE
        
        # Analysis mode configuration
        self.mode = mode
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        self.batch_size = batch_size
        
        # Parse dates if provided
        if start_date:
            self.start_datetime = datetime.fromisoformat(start_date)
        if end_date:
            self.end_datetime = datetime.fromisoformat(end_date)
        elif mode == "range" and start_date:
            # Default end_date to today for range mode
            self.end_datetime = datetime.now()
            self.end_date = self.end_datetime.strftime("%Y-%m-%d")
        
    async def initialize(self):
        """Initialize the shitpost analyzer."""
        logger.info("Initializing Shitpost Analyzer...")
        
        await self.db_manager.initialize()
        await self.llm_client.initialize()
        
        logger.info(f"Shitpost Analyzer initialized with launch date: {self.launch_date}")
    
    async def analyze_shitposts(self) -> int:
        """Analyze shitposts based on configured mode."""
        logger.info(f"Starting shitpost analysis in {self.mode} mode...")
        
        if self.mode == "backfill":
            return await self._analyze_backfill()
        elif self.mode == "range":
            return await self._analyze_date_range()
        else:  # incremental (default)
            return await self._analyze_incremental()
    
    async def _analyze_backfill(self) -> int:
        """Analyze all unprocessed shitposts from launch date onwards."""
        logger.info("Starting full backfill analysis of unprocessed shitposts...")
        
        total_analyzed = 0
        
        while True:
            try:
                logger.info(f"Fetching batch of unprocessed shitposts (batch_size: {self.batch_size})...")
                # Get batch of unprocessed shitposts
                shitposts = await self.db_manager.get_unprocessed_shitposts(
                    launch_date=self.launch_date,
                    limit=self.batch_size
                )
                
                logger.info(f"Retrieved {len(shitposts) if shitposts else 0} unprocessed shitposts")
                
                if not shitposts:
                    logger.info("No more unprocessed shitposts found for backfill analysis")
                    break
                
                # Analyze batch
                batch_analyzed = await self._analyze_batch(shitposts)
                total_analyzed += batch_analyzed
                
                # Check if we've reached the limit
                if self.limit and total_analyzed >= self.limit:
                    logger.info(f"Reached analysis limit of {self.limit} posts")
                    break
                
                logger.info(f"Backfill analysis progress: {total_analyzed} posts analyzed")
                
                # Small delay to be respectful to LLM APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in backfill analysis: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Backfill analysis completed. Total posts analyzed: {total_analyzed}")
        return total_analyzed
    
    async def _analyze_date_range(self) -> int:
        """Analyze shitposts within a specific date range."""
        logger.info(f"Starting date range analysis from {self.start_date} to {self.end_date}")
        
        total_analyzed = 0
        
        while True:
            try:
                # Get batch of unprocessed shitposts
                shitposts = await self.db_manager.get_unprocessed_shitposts(
                    launch_date=self.launch_date,
                    limit=self.batch_size
                )
                
                if not shitposts:
                    logger.info("No more unprocessed shitposts found for date range analysis")
                    break
                
                # Filter shitposts by date range
                filtered_shitposts = []
                for shitpost in shitposts:
                    try:
                        # Handle both ISO format with 'Z' and standard datetime format
                        timestamp_str = shitpost.get('timestamp')
                        if timestamp_str.endswith('Z'):
                            post_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            # Handle standard datetime format from database
                            post_timestamp = datetime.fromisoformat(timestamp_str)
                        
                        if post_timestamp < self.start_datetime:
                            logger.info(f"Reached posts before start date {self.start_date}, stopping")
                            return total_analyzed
                        
                        if post_timestamp > self.end_datetime:
                            # Skip posts after end date, continue to find older ones
                            continue
                        
                        filtered_shitposts.append(shitpost)
                        
                    except Exception as e:
                        logger.error(f"Error parsing timestamp for shitpost {shitpost.get('id')}: {e}")
                        continue
                
                if filtered_shitposts:
                    # Analyze filtered batch
                    batch_analyzed = await self._analyze_batch(filtered_shitposts)
                    total_analyzed += batch_analyzed
                    
                    # Check if we've reached the limit
                    if self.limit and total_analyzed >= self.limit:
                        logger.info(f"Reached analysis limit of {self.limit} posts")
                        break
                
                logger.info(f"Date range analysis progress: {total_analyzed} posts analyzed")
                
                # Small delay to be respectful to LLM APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in date range analysis: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Date range analysis completed. Total posts analyzed: {total_analyzed}")
        return total_analyzed
    
    
    async def _analyze_incremental(self) -> int:
        """Analyze only new unprocessed shitposts (original implementation)."""
        logger.info("Starting incremental shitpost analysis...")
        
        try:
            # Get unprocessed shitposts
            shitposts = await self.db_manager.get_unprocessed_shitposts(
                launch_date=self.launch_date,
                limit=self.batch_size
            )
            
            if not shitposts:
                logger.info("No unprocessed shitposts found for analysis")
                return 0
            
            logger.info(f"Found {len(shitposts)} unprocessed shitposts to analyze")
            
            # Analyze batch
            analyzed_count = await self._analyze_batch(shitposts)
            
            logger.info(f"Incremental analysis completed: {analyzed_count} shitposts analyzed")
            return analyzed_count
            
        except Exception as e:
            logger.error(f"Error in incremental analysis: {e}")
            await handle_exceptions(e)
            return 0
    
    async def _analyze_batch(self, shitposts: List[Dict]) -> int:
        """Analyze a batch of shitposts."""
        analyzed_count = 0
        
        for shitpost in shitposts:
            try:
                # Check if prediction already exists (double-check)
                if await self.db_manager.check_prediction_exists(shitpost['shitpost_id']):
                    logger.info(f"Prediction already exists for shitpost {shitpost['shitpost_id']}, skipping")
                    continue
                
                # Analyze the shitpost
                analysis = await self._analyze_shitpost(shitpost)
                
                if analysis:
                    # Store enhanced analysis with shitpost data
                    prediction_id = await self.db_manager.store_analysis(
                        shitpost_id=str(shitpost['shitpost_id']),  # Use Truth Social API post ID
                        analysis_data=analysis,
                        shitpost_data=shitpost
                    )
                    
                    if prediction_id:
                        analyzed_count += 1
                        logger.info(f"Successfully analyzed shitpost {shitpost['id']} -> prediction {prediction_id}")
                    else:
                        logger.error(f"Failed to store analysis for shitpost {shitpost['id']}")
                else:
                    logger.warning(f"No analysis generated for shitpost {shitpost['id']}")
                    
            except Exception as e:
                logger.error(f"Error analyzing shitpost {shitpost['id']}: {e}")
                await handle_exceptions(e)
                continue
        
        return analyzed_count
    
    async def analyze_unprocessed_shitposts(self, batch_size: int = 5) -> int:
        """
        Analyze unprocessed shitposts from the database (legacy method for backward compatibility).
        
        Args:
            batch_size: Number of shitposts to process in one batch
            
        Returns:
            Number of shitposts successfully analyzed
        """
        # Use the new mode-based analysis
        return await self.analyze_shitposts()
    
    async def _analyze_shitpost(self, shitpost: Dict) -> Optional[Dict]:
        """
        Analyze a single shitpost with enhanced context.
        
        Args:
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced analysis results
        """
        try:
            # Check if post has analyzable content BEFORE sending to LLM
            if self._should_bypass_post(shitpost):
                # Create bypassed prediction record immediately
                await self.db_manager.handle_no_text_prediction(
                    shitpost_id=shitpost['shitpost_id'],
                    shitpost_data=shitpost
                )
                logger.info(f"Bypassed shitpost {shitpost['shitpost_id']} - no analyzable content")
                return None  # Skip LLM entirely
            
            logger.info(f"Preparing enhanced content for shitpost {shitpost.get('id')}...")
            # Prepare enhanced content for analysis
            enhanced_content = self._prepare_enhanced_content(shitpost)
            
            logger.info(f"Calling LLM client for analysis...")
            # Analyze with LLM
            analysis = await self.llm_client.analyze(enhanced_content)
            
            logger.info(f"LLM analysis result: {analysis is not None}")
            
            if not analysis:
                return None
            
            logger.info(f"Enhancing analysis with shitpost data...")
            # Enhance analysis with Truth Social data
            enhanced_analysis = self._enhance_analysis_with_shitpost_data(analysis, shitpost)
            
            return enhanced_analysis
            
        except Exception as e:
            logger.error(f"Error in shitpost analysis: {e}")
            return None
    
    def _should_bypass_post(self, shitpost: Dict) -> bool:
        """Determine if a post should be bypassed for analysis."""
        text_content = shitpost.get('text', '').strip()
        
        # Check for various bypass conditions
        if not text_content:
            return True  # No text at all
        
        # Check if it's just a URL with no context
        if text_content.startswith('http') and len(text_content.split()) <= 2:
            return True
        
        # Check if it's just emojis/symbols
        if all(ord(char) < 128 for char in text_content) and len(text_content.strip()) < 3:
            return True
        
        # Check if it's just media (has media but no text)
        if shitpost.get('has_media', False) and not text_content:
            return True
        
        return False  # Post has analyzable content
    
    def _prepare_enhanced_content(self, shitpost: Dict) -> str:
        """
        Prepare enhanced content for LLM analysis.
        
        Args:
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced content string
        """
        content_parts = []
        
        # Main content
        content_parts.append(f"SHITPOST CONTENT: {shitpost.get('text', '')}")
        
        # Engagement context
        replies = shitpost.get('replies_count', 0)
        reblogs = shitpost.get('reblogs_count', 0)
        favourites = shitpost.get('favourites_count', 0)
        upvotes = shitpost.get('upvotes_count', 0)
        
        if any([replies, reblogs, favourites, upvotes]):
            content_parts.append(f"ENGAGEMENT: {replies} replies, {reblogs} reblogs, {favourites} favourites, {upvotes} upvotes")
        
        # Account context
        followers = shitpost.get('account_followers_count', 0)
        verified = shitpost.get('account_verified', False)
        
        if followers > 0:
            content_parts.append(f"ACCOUNT: {followers:,} followers, verified: {verified}")
        
        # Media context
        if shitpost.get('has_media', False):
            content_parts.append("MEDIA: Shitpost contains media attachments")
        
        # Mentions and hashtags
        mentions = shitpost.get('mentions', [])
        tags = shitpost.get('tags', [])
        
        if mentions:
            content_parts.append(f"MENTIONS: {', '.join(mentions)}")
        
        if tags:
            content_parts.append(f"HASHTAGS: {', '.join(tags)}")
        
        return "\n".join(content_parts)
    
    def _enhance_analysis_with_shitpost_data(self, analysis: Dict, shitpost: Dict) -> Dict:
        """
        Enhance LLM analysis with Truth Social shitpost data.
        
        Args:
            analysis: Original LLM analysis
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced analysis
        """
        enhanced = analysis.copy()
        
        # Calculate engagement-based scores
        replies = shitpost.get('replies_count', 0)
        reblogs = shitpost.get('reblogs_count', 0)
        favourites = shitpost.get('favourites_count', 0)
        upvotes = shitpost.get('upvotes_count', 0)
        followers = shitpost.get('account_followers_count', 0)
        
        # Engagement score
        if followers > 0:
            engagement_rate = (replies + reblogs + favourites) / followers
            enhanced['engagement_score'] = min(engagement_rate * 100, 1.0)  # Normalize to 0-1
        
        # Viral score
        if favourites > 0:
            viral_ratio = reblogs / favourites
            enhanced['viral_score'] = min(viral_ratio, 1.0)
        
        # Urgency indicators
        urgency_indicators = []
        if '!' in shitpost.get('text', ''):
            urgency_indicators.append('exclamation_marks')
        if any(word in shitpost.get('text', '').upper() for word in ['URGENT', 'IMMEDIATE', 'NOW', 'ASAP']):
            urgency_indicators.append('urgency_keywords')
        if replies > 1000:
            urgency_indicators.append('high_engagement')
        
        enhanced['urgency_indicators'] = urgency_indicators
        enhanced['urgency_score'] = len(urgency_indicators) / 3.0  # Normalize to 0-1
        
        # Add shitpost metadata
        enhanced['shitpost_metadata'] = {
            'has_media': shitpost.get('has_media', False),
            'mentions_count': len(shitpost.get('mentions', [])),
            'hashtags_count': len(shitpost.get('tags', [])),
            'content_length': len(shitpost.get('text', '')),
            'engagement_metrics': {
                'replies': replies,
                'reblogs': reblogs,
                'favourites': favourites,
                'upvotes': upvotes
            }
        }
        
        return enhanced
    
    async def run_continuous_analysis(self, interval_seconds: int = 300):
        """
        Run continuous analysis of unprocessed shitposts.
        
        Args:
            interval_seconds: Seconds between analysis runs
        """
        logger.info(f"Starting continuous shitpost analysis (interval: {interval_seconds}s)")
        
        while True:
            try:
                analyzed_count = await self.analyze_shitposts()
                
                if analyzed_count > 0:
                    logger.info(f"Analyzed {analyzed_count} shitposts in this cycle")
                else:
                    logger.debug("No shitposts analyzed in this cycle")
                
                # Wait before next cycle
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Continuous shitpost analysis stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous shitpost analysis: {e}")
                await handle_exceptions(e)
                await asyncio.sleep(interval_seconds)
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.db_manager.cleanup()
        logger.info("Shitpost Analyzer cleaned up")


async def main():
    """CLI entry point for shitpost analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Shitpost AI analyzer with multiple modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Incremental analysis (default)
  python -m shitpost_ai.shitpost_analyzer
  
  # Full historical backfill analysis
  python -m shitpost_ai.shitpost_analyzer --mode backfill
  
  # Date range analysis
  python -m shitpost_ai.shitpost_analyzer --mode range --from 2024-01-01 --to 2024-01-31
  
  # Date range analysis (from date to today)
  python -m shitpost_ai.shitpost_analyzer --mode range --from 2024-01-01
  
  # Analysis with custom batch size
  python -m shitpost_ai.shitpost_analyzer --mode backfill --batch-size 10
  
  # Analysis with limit
  python -m shitpost_ai.shitpost_analyzer --mode backfill --limit 100
  
  # Dry run mode
  python -m shitpost_ai.shitpost_analyzer --mode backfill --dry-run --limit 10
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["incremental", "backfill", "range"], 
        default="incremental", 
        help="Analysis mode (default: incremental)"
    )
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
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Maximum number of posts to analyze (optional)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=5,
        help="Number of posts to process in each batch (default: 5)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be analyzed without saving to database"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mode == "range" and not args.start_date:
        parser.error("--from date is required for range mode")
    
    # Note: --to date is optional for range mode (defaults to today)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print(f"🧠 Starting shitpost analysis in {args.mode} mode...")
    
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
        
        if args.dry_run:
            print("🔍 DRY RUN MODE - No analysis will be saved to database")
            # For dry run, we'll just show what would be analyzed
            # This would require additional implementation to show unprocessed posts
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
            analyzed_count = await analyzer.analyze_shitposts()
            print(f"\n🎉 Analysis completed! Total posts analyzed: {analyzed_count}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Analysis stopped by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
    finally:
        await analyzer.cleanup()
    

if __name__ == "__main__":
    asyncio.run(main())
