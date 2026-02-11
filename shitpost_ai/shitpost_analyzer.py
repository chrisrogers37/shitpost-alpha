"""
Shitpost Analyzer
Business logic orchestrator for analyzing shitposts with enhanced context.
"""

import asyncio
import concurrent.futures
from typing import Dict, List, Optional
from datetime import datetime

from shit.config.shitpost_settings import settings
from shit.llm import LLMClient, get_analysis_prompt
from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
from shitvault.shitpost_operations import ShitpostOperations
from shitvault.prediction_operations import PredictionOperations
from shit.utils.error_handling import handle_exceptions
from shit.content import BypassService
from shit.logging import get_service_logger
from shit.market_data.auto_backfill_service import auto_backfill_prediction

logger = get_service_logger("analyzer")


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
        # Initialize database components
        self.db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        self.db_client = DatabaseClient(self.db_config)
        self.db_ops = None  # Will be initialized in initialize()
        self.shitpost_ops = None  # Will be initialized in initialize()
        self.prediction_ops = None  # Will be initialized in initialize()
        
        self.llm_client = LLMClient()
        self.bypass_service = BypassService()
        self.launch_date = settings.SYSTEM_LAUNCH_DATE

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
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("INITIALIZING ANALYZER")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("Initializing Shitpost Analyzer...")

        # Initialize database client
        await self.db_client.initialize()

        # Initialize operation classes with the database client
        self.db_ops = DatabaseOperations(self.db_client)
        self.shitpost_ops = ShitpostOperations(self.db_client)
        self.prediction_ops = PredictionOperations(self.db_client)

        # Initialize LLM client
        await self.llm_client.initialize()

        logger.info(f"Shitpost Analyzer initialized with launch date: {self.launch_date}")
        logger.info("✅ Analyzer initialized successfully")
        logger.info("")
    
    async def analyze_shitposts(self, dry_run: bool = False) -> int:
        """Analyze shitposts based on configured mode.
        
        Args:
            dry_run: If True, don't actually store results to database
            
        Returns:
            Number of posts analyzed
        """
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("ANALYZING SHITPOSTS")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"Starting shitpost analysis in {self.mode} mode...")
        
        if self.mode == "backfill":
            result = await self._analyze_backfill(dry_run)
        elif self.mode == "range":
            result = await self._analyze_date_range(dry_run)
        else:  # incremental (default)
            result = await self._analyze_incremental(dry_run)
        
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("ANALYSIS COMPLETED")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"Total posts analyzed: {result}")
        
        return result
    
    async def _analyze_backfill(self, dry_run: bool = False) -> int:
        """Analyze all unprocessed shitposts from launch date onwards."""
        logger.info("Starting full backfill analysis of unprocessed shitposts...")
        logger.info(f"Launch date filter: {self.launch_date}")
        
        total_analyzed = 0
        batch_number = 0
        
        while True:
            try:
                batch_number += 1
                print(f"🔄 Batch {batch_number}: Fetching {self.batch_size} unprocessed shitposts...")
                
                # Get batch of unprocessed shitposts
                shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                    launch_date=self.launch_date,
                    limit=self.batch_size
                )
                
                if not shitposts:
                    print("✅ No more unprocessed shitposts found for backfill analysis")
                    break
                
                # Show date range of this batch
                timestamps = [s.get('timestamp') for s in shitposts if s.get('timestamp')]
                if timestamps:
                    latest_date = max(timestamps)
                    earliest_date = min(timestamps)
                    print(f"📅 Batch {batch_number} date range: {earliest_date} to {latest_date}")
                
                print(f"📊 Batch {batch_number}: Processing {len(shitposts)} posts...")
                
                # Analyze batch
                batch_analyzed = await self._analyze_batch(shitposts, dry_run, batch_number)
                total_analyzed += batch_analyzed
                
                print(f"✅ Batch {batch_number} completed: {batch_analyzed}/{len(shitposts)} posts analyzed (Total: {total_analyzed})")
                
                # Check if we've reached the limit
                if self.limit and total_analyzed >= self.limit:
                    print(f"🛑 Reached analysis limit of {self.limit} posts")
                    break
                
                # Small delay to be respectful to LLM API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in backfill analysis batch {batch_number}: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"🎉 Backfill analysis completed! Total posts analyzed: {total_analyzed}")
        return total_analyzed
    
    async def _analyze_date_range(self, dry_run: bool = False) -> int:
        """Analyze shitposts within a specific date range."""
        logger.info(f"Starting date range analysis from {self.start_date} to {self.end_date}")
        logger.info(f"Launch date filter: {self.launch_date}")
        
        total_analyzed = 0
        batch_number = 0
        
        while True:
            try:
                batch_number += 1
                logger.info(f"🔄 Batch {batch_number}: Fetching {self.batch_size} unprocessed shitposts...")
                
                # Get batch of unprocessed shitposts
                shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                    launch_date=self.launch_date,
                    limit=self.batch_size
                )
                
                if not shitposts:
                    logger.info("✅ No more unprocessed shitposts found for date range analysis")
                    break
                
                # Show date range of this batch
                timestamps = [s.get('timestamp') for s in shitposts if s.get('timestamp')]
                if timestamps:
                    latest_date = max(timestamps)
                    earliest_date = min(timestamps)
                    logger.info(f"📅 Batch {batch_number} date range: {earliest_date} to {latest_date}")
                
                # Filter shitposts by date range
                filtered_shitposts = []
                for shitpost in shitposts:
                    post_timestamp = shitpost.get('timestamp')
                    if post_timestamp:
                        if isinstance(post_timestamp, str):
                            post_datetime = datetime.fromisoformat(post_timestamp.replace('Z', '+00:00'))
                        else:
                            post_datetime = post_timestamp
                        
                        # Check if post is within date range
                        if self.start_datetime <= post_datetime <= self.end_datetime:
                            filtered_shitposts.append(shitpost)
                        elif post_datetime < self.start_datetime:
                            # If we've reached posts before the start date, we can stop
                            logger.info(f"🛑 Reached posts before start date {self.start_date}, stopping analysis")
                            break
                
                if not filtered_shitposts:
                    logger.info(f"⏭️  Batch {batch_number}: No shitposts found in specified date range")
                    continue
                
                logger.info(f"📊 Batch {batch_number}: Processing {len(filtered_shitposts)} posts in date range...")
                
                # Analyze filtered batch
                batch_analyzed = await self._analyze_batch(filtered_shitposts, dry_run, batch_number)
                total_analyzed += batch_analyzed
                
                logger.info(f"✅ Batch {batch_number} completed: {batch_analyzed}/{len(filtered_shitposts)} posts analyzed (Total: {total_analyzed})")
                
                # Check if we've reached the limit
                if self.limit and total_analyzed >= self.limit:
                    logger.info(f"🛑 Reached analysis limit of {self.limit} posts")
                    break
                
                # Small delay to be respectful to LLM API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in date range analysis batch {batch_number}: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"🎉 Date range analysis completed! Total posts analyzed: {total_analyzed}")
        return total_analyzed
    
    async def _analyze_incremental(self, dry_run: bool = False) -> int:
        """Analyze only new unprocessed shitposts (incremental mode)."""
        logger.info("Starting incremental analysis of new unprocessed shitposts...")
        
        try:
            # Get batch of unprocessed shitposts
            shitposts = await self.shitpost_ops.get_unprocessed_shitposts(
                launch_date=self.launch_date,
                limit=self.batch_size
            )
            
            logger.info(f"Retrieved {len(shitposts) if shitposts else 0} unprocessed shitposts for incremental analysis")
            
            if not shitposts:
                logger.info("No new unprocessed shitposts found for incremental analysis")
                return 0
            
            # Analyze batch
            total_analyzed = await self._analyze_batch(shitposts, dry_run)
            
            logger.info(f"Incremental analysis completed. Total posts analyzed: {total_analyzed}")
            return total_analyzed
            
        except Exception as e:
            logger.error(f"Error in incremental analysis: {e}")
            await handle_exceptions(e)
            return 0
    
    async def _analyze_batch(self, shitposts: List[Dict], dry_run: bool = False, batch_number: int = 0) -> int:
        """Analyze a batch of shitposts.
        
        Args:
            shitposts: List of shitpost dictionaries
            dry_run: If True, don't actually store results to database
            batch_number: Batch number for logging
            
        Returns:
            Number of posts successfully analyzed
        """
        analyzed_count = 0
        skipped_count = 0
        bypassed_count = 0
        failed_count = 0
        
        for i, shitpost in enumerate(shitposts, 1):
            try:
                # Check if prediction already exists (deduplication)
                shitpost_id = shitpost.get('shitpost_id')
                if not shitpost_id:
                    logger.warning(f"⚠️  Post {i}/{len(shitposts)}: Missing ID, skipping")
                    skipped_count += 1
                    continue
                
                if await self.prediction_ops.check_prediction_exists(shitpost_id):
                    print(f"⏭️  Post {i}/{len(shitposts)}: {shitpost_id} already analyzed, skipping")
                    skipped_count += 1
                    continue
                
                # Show post info
                post_date = shitpost.get('timestamp', 'Unknown')
                post_text = shitpost.get('text', '')[:50] + "..." if len(shitpost.get('text', '')) > 50 else shitpost.get('text', '')
                print(f"🔍 Post {i}/{len(shitposts)}: {shitpost_id} ({post_date}) - {post_text}")
                
                # Analyze shitpost
                analysis = await self._analyze_shitpost(shitpost, dry_run)
                
                if analysis:
                    if analysis.get('analysis_status') == 'bypassed':
                        bypassed_count += 1
                        reason = analysis.get('analysis_comment', 'Unknown')
                        print(f"⏭️  Post {i}/{len(shitposts)}: {shitpost_id} bypassed - {reason}")
                    else:
                        analyzed_count += 1
                        assets = analysis.get('assets', [])
                        confidence = analysis.get('confidence', 0.0)
                        print(f"✅ Post {i}/{len(shitposts)}: {shitpost_id} analyzed - Assets: {assets}, Confidence: {confidence:.1%}")
                else:
                    failed_count += 1
                    print(f"❌ Post {i}/{len(shitposts)}: {shitpost_id} failed to analyze")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Post {i}/{len(shitposts)}: Error analyzing {shitpost.get('shitpost_id', 'unknown')}: {e}")
                continue
        
        # Summary for this batch
        print(f"📊 Batch {batch_number} summary: {analyzed_count} analyzed, {bypassed_count} bypassed, {skipped_count} skipped, {failed_count} failed")
        
        return analyzed_count
    
    async def _analyze_shitpost(self, shitpost: Dict, dry_run: bool = False) -> Optional[Dict]:
        """Analyze a single shitpost for financial implications.
        
        Args:
            shitpost: Shitpost dictionary
            dry_run: If True, don't actually store results to database
            
        Returns:
            Analysis result dictionary or None if failed
        """
        try:
            shitpost_id = shitpost.get('shitpost_id')
            if not shitpost_id:
                logger.warning("Shitpost missing ID, cannot analyze")
                return None
            
            # Check if post should be bypassed using unified bypass service
            should_bypass, bypass_reason = self.bypass_service.should_bypass_post(shitpost)

            if should_bypass:
                logger.info(f"Bypassing shitpost {shitpost_id}: {bypass_reason}")

                if not dry_run:
                    # Create bypassed prediction record
                    await self.prediction_ops.handle_no_text_prediction(shitpost_id, shitpost, bypass_reason)

                return {
                    'shitpost_id': shitpost_id,
                    'analysis_status': 'bypassed',
                    'analysis_comment': str(bypass_reason)
                }
            
            # Prepare enhanced content for LLM analysis
            enhanced_content = self._prepare_enhanced_content(shitpost)
            
            # Analyze with LLM
            analysis = await self.llm_client.analyze(enhanced_content)
            
            if not analysis:
                logger.warning(f"LLM analysis failed for shitpost {shitpost_id}")
                return None
            
            # Enhance analysis with shitpost data
            enhanced_analysis = self._enhance_analysis_with_shitpost_data(analysis, shitpost)
            
            if not dry_run:
                # Store analysis in database
                analysis_id = await self.prediction_ops.store_analysis(
                    shitpost_id,
                    enhanced_analysis,
                    shitpost
                )

                if analysis_id:
                    logger.debug(f"Stored analysis for shitpost {shitpost_id}")

                    # Reactively trigger market data backfill for new tickers
                    assets = enhanced_analysis.get("assets", [])
                    if assets:
                        try:
                            pred_id = int(analysis_id)
                        except (ValueError, TypeError):
                            pred_id = None
                        if pred_id is not None:
                            await self._trigger_reactive_backfill(pred_id, assets)
                else:
                    logger.warning(f"Failed to store analysis for shitpost {shitpost_id}")

            return enhanced_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing shitpost {shitpost.get('shitpost_id', 'unknown')}: {e}")
            return None
    
    def _prepare_enhanced_content(self, signal_data: Dict) -> str:
        """Prepare enhanced content for LLM analysis.

        Uses generic field names with fallback to legacy names for
        backward compatibility with both Signal and Shitpost dicts.

        Args:
            signal_data: Signal or shitpost dictionary

        Returns:
            Enhanced content string
        """
        content = signal_data.get('text', '')
        username = signal_data.get('author_username', signal_data.get('username', ''))
        timestamp = signal_data.get('published_at', signal_data.get('timestamp', ''))
        source = signal_data.get('source', signal_data.get('platform', 'unknown'))

        # Engagement metrics (generic names with fallback)
        replies = signal_data.get('replies_count', 0)
        shares = signal_data.get('shares_count', signal_data.get('reblogs_count', 0))
        likes = signal_data.get('likes_count', signal_data.get('favourites_count', 0))

        # Account information (generic names with fallback)
        verified = signal_data.get('author_verified', signal_data.get('account_verified', False))
        followers = signal_data.get('author_followers', signal_data.get('account_followers_count', 0))

        # Media information
        has_media = signal_data.get('has_media', False)
        mentions = signal_data.get('mentions', [])
        mentions_count = len(mentions) if isinstance(mentions, list) else 0
        tags = signal_data.get('tags', [])
        tags_count = len(tags) if isinstance(tags, list) else 0

        # Build enhanced content
        enhanced_content = f"Content: {content}\n"
        enhanced_content += f"Source: {source}\n"
        enhanced_content += f"Author: {username} (Verified: {verified}, Followers: {followers:,})\n"
        enhanced_content += f"Timestamp: {timestamp}\n"
        enhanced_content += f"Engagement: {replies} replies, {shares} shares, {likes} likes\n"
        enhanced_content += f"Media: {'Yes' if has_media else 'No'}, Mentions: {mentions_count}, Tags: {tags_count}"

        return enhanced_content
    
    def _enhance_analysis_with_shitpost_data(self, analysis: Dict, shitpost: Dict) -> Dict:
        """Enhance LLM analysis with additional shitpost data.
        
        Args:
            analysis: LLM analysis result
            shitpost: Original shitpost data
            
        Returns:
            Enhanced analysis dictionary
        """
        enhanced_analysis = analysis.copy()
        
        # Add engagement metrics
        enhanced_analysis['engagement_metrics'] = {
            'replies': shitpost.get('replies_count', 0),
            'reblogs': shitpost.get('reblogs_count', 0),
            'favourites': shitpost.get('favourites_count', 0),
            'upvotes': shitpost.get('upvotes_count', 0)
        }
        
        # Add account information
        enhanced_analysis['account_info'] = {
            'username': shitpost.get('username', ''),
            'verified': shitpost.get('account_verified', False),
            'followers': shitpost.get('account_followers_count', 0)
        }
        
        # Add content metadata
        enhanced_analysis['content_metadata'] = {
            'has_media': shitpost.get('has_media', False),
            'mentions_count': len(shitpost.get('mentions', [])),
            'tags_count': len(shitpost.get('tags', [])),
            'content_length': len(shitpost.get('text', ''))
        }
        
        return enhanced_analysis
    
    async def _trigger_reactive_backfill(self, prediction_id: int, assets: list) -> None:
        """Trigger market data backfill for new tickers found in a prediction.

        Runs the synchronous backfill service in a thread executor to avoid
        blocking the async event loop. Failures are logged but do not
        propagate -- the prediction was already stored successfully.

        Args:
            prediction_id: ID of the newly created prediction
            assets: List of ticker symbols from the prediction
        """
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor,
                    auto_backfill_prediction,
                    prediction_id,
                )

            if result:
                logger.info(
                    f"Reactive backfill completed for prediction {prediction_id}, assets: {assets}",
                    extra={"prediction_id": prediction_id, "assets": assets},
                )
            else:
                logger.debug(
                    f"Reactive backfill: no new data needed for prediction {prediction_id}",
                    extra={"prediction_id": prediction_id, "assets": assets},
                )

        except Exception as e:
            # Never let backfill failure break the analysis pipeline
            logger.warning(
                f"Reactive backfill failed for prediction {prediction_id}: {e}",
                extra={"prediction_id": prediction_id, "assets": assets, "error": str(e)},
            )

    async def cleanup(self):
        """Cleanup analyzer resources."""
        if self.db_client:
            await self.db_client.cleanup()
        logger.info("Shitpost Analyzer cleanup completed")