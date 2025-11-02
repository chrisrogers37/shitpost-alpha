"""
Truth Social S3 Harvester
Harvests raw Truth Social data and stores it directly in S3.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, List
import aiohttp
import json

from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from shit.s3 import S3DataLake, S3Config
from shitposts.cli import (
    create_harvester_parser, validate_harvester_args, setup_harvester_logging,
    print_harvest_start, print_harvest_progress, print_harvest_complete,
    print_harvest_error, print_harvest_interrupted, print_s3_stats,
    HARVESTER_EXAMPLES
)

logger = logging.getLogger(__name__)


class TruthSocialS3Harvester:
    """Harvester for Truth Social posts that stores raw data in S3."""
    
    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None, max_id=None):
        """Initialize the Truth Social S3 harvester.
        
        Args:
            mode: Harvesting mode - "incremental", "backfill", "range", "from_date"
            start_date: Start date for range/from_date modes (YYYY-MM-DD)
            end_date: End date for range mode (YYYY-MM-DD)
            limit: Maximum number of posts to harvest (optional)
            max_id: Starting post ID for backfill mode (for resuming)
        """
        self.username = settings.TRUTH_SOCIAL_USERNAME
        
        # Harvesting mode configuration
        self.mode = mode
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        self.max_id = max_id
        
        # Parse dates if provided
        if start_date:
            self.start_datetime = datetime.fromisoformat(start_date).replace(tzinfo=None)
        if end_date:
            self.end_datetime = datetime.fromisoformat(end_date).replace(tzinfo=None)
        else:
            # Default end_date to today if not provided
            self.end_datetime = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # API configuration
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        
        # Trump's Truth Social user ID
        self.user_id = "107780257626128497"
        
        # Session and state
        self.session: Optional[aiohttp.ClientSession] = None
        self.s3_data_lake: Optional[S3DataLake] = None
        self.api_call_count = 0  # Track API calls per execution
        
    async def initialize(self, dry_run: bool = False):
        """Initialize the Truth Social S3 harvester."""
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"INITIALIZING HARVESTER: @{self.username}")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.debug(f"🔧 Initialize method called with dry_run: {dry_run}")
        
        if not self.api_key:
            raise ValueError("SCRAPECREATORS_API_KEY not configured. Please add it to your .env file.")
        
        try:
            logger.debug("🌐 Creating aiohttp session...")
            # Create aiohttp session
            self.session = aiohttp.ClientSession(
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'User-Agent': 'Shitpost-Alpha-S3-Harvester/1.0'
                }
            )
            
            # Test API connection
            logger.info("Testing Truth Social API connection...")
            await self._test_connection()
            logger.info("✅ API connection successful")
            logger.info("")
            
            # Initialize S3 Data Lake only if not in dry run mode
            if not dry_run:
                logger.info("Initializing S3 Data Lake...")
                # Create S3 config from settings
                s3_config = S3Config(
                    bucket_name=settings.S3_BUCKET_NAME,
                    prefix=settings.S3_PREFIX,
                    region=settings.AWS_REGION,
                    access_key_id=settings.AWS_ACCESS_KEY_ID,
                    secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                self.s3_data_lake = S3DataLake(s3_config)
                await self.s3_data_lake.initialize()
                logger.info("✅ S3 Data Lake initialized successfully")
            else:
                logger.info("Dry run mode - skipping S3 initialization")
            
            logger.info("✅ Harvester initialized successfully")
            logger.info("")
            
        except Exception as e:
            logger.error(f"Failed to initialize Truth Social S3 harvester: {e}")
            await self.cleanup()
            raise
    
    async def _test_connection(self):
        """Test the ScrapeCreators API connection."""
        try:
            # Test with a simple API call
            url = f"{self.base_url}/truthsocial/user/posts?user_id={self.user_id}&limit=1"
            logger.debug(f"Testing API connection to: {url}")
            timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout for test
            async with self.session.get(url, timeout=timeout) as response:
                logger.debug(f"API test response status: {response.status}")
                if response.status != 200:
                    raise Exception(f"API connection test failed: {response.status}")
                
                data = await response.json()
                logger.debug(f"API test response data: {data}")
                if not data.get('success'):
                    raise Exception(f"API returned error: {data}")
                
                logger.debug("ScrapeCreators API connection test successful")
                        
        except Exception as e:
            logger.error(f"ScrapeCreators API connection test failed: {e}")
            raise
    
    async def _fetch_recent_shitposts(self, next_max_id: Optional[str] = None) -> List[Dict]:
        """Fetch recent shitposts using ScrapeCreators API."""
        try:
            # Build URL with pagination
            url = f"{self.base_url}/truthsocial/user/posts"
            params = {
                'user_id': self.user_id,
                'limit': 20
            }
            
            if next_max_id:
                params['next_max_id'] = next_max_id
            
            self.api_call_count += 1
            print(f"🌐 Making API call #{self.api_call_count} to: {url}")
            logger.info(f"Making API call #{self.api_call_count} to Truth Social API")
            logger.debug(f"⏱️  Starting API call with 30 second timeout...")
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            async with self.session.get(url, params=params, timeout=timeout) as response:
                logger.debug(f"📡 API response received, status: {response.status}")
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return []
                
                data = await response.json()
                logger.debug(f"API response data: {data}")
                
                if not data.get('success'):
                    logger.error(f"API returned error: {data}")
                    return []
                
                shitposts = data.get('posts', [])  # API returns 'posts' not 'data'
                logger.info(f"Fetched {len(shitposts)} posts from Truth Social API")
                
                return shitposts
                
        except Exception as e:
            logger.error(f"Error fetching shitposts: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    async def harvest_shitposts(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest shitposts based on configured mode."""
        logger.debug(f"Starting shitpost harvest in {self.mode} mode...")
        logger.debug(f"🔍 About to enter mode-specific harvest logic for: {self.mode}")
        
        if self.mode == "backfill":
            logger.debug("🔄 Entering backfill mode")
            async for result in self._harvest_backfill(dry_run):
                yield result
        elif self.mode == "range":
            logger.debug("📅 Entering range mode")
            async for result in self._harvest_backfill(dry_run, self.start_datetime, self.end_datetime):
                yield result
        elif self.mode == "from_date":
            logger.debug("📆 Entering from_date mode (using range with end_date=today)")
            async for result in self._harvest_backfill(dry_run, self.start_datetime, self.end_datetime):
                yield result
        else:  # incremental (default)
            logger.debug("🔄 Entering incremental mode")
            async for result in self._harvest_backfill(dry_run, incremental_mode=True):
                yield result
    
    async def _harvest_backfill(self, dry_run: bool = False, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, incremental_mode: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest historical Truth Social posts to S3.
        
        Args:
            dry_run: If True, don't actually store to S3
            start_date: Optional start date filter (inclusive)
            end_date: Optional end date filter (inclusive)
            incremental_mode: If True, stop when encountering existing posts in S3
        """
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("HARVESTING POSTS")
        logger.info("═══════════════════════════════════════════════════════════")
        
        if incremental_mode:
            logger.info("Mode: Incremental (will stop when encountering existing posts in S3)")
            print("🔄 Incremental mode: Will stop when finding posts that already exist in S3")
        elif start_date and end_date:
            logger.info(f"Mode: Date Range ({start_date.date()} to {end_date.date()})")
            logger.debug("🔄 Note: API doesn't support date filtering - crawling backwards through all posts")
        else:
            logger.info("Mode: Full Backfill")
        
        # Use provided max_id or start from most recent
        max_id = self.max_id
        total_harvested = 0
        posts_processed = 0
        
        if max_id:
            logger.debug(f"Resuming backfill from post ID: {max_id}")
        else:
            logger.debug("Starting backfill from most recent posts")
        
        while True:
            try:
                logger.debug(f"Fetching batch of posts with max_id: {max_id}")
                # Fetch batch of posts from API (start with most recent, no max_id)
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                logger.debug(f"API returned {len(shitposts) if shitposts else 0} posts")
                
                if not shitposts:
                    logger.debug("No more posts to harvest in backfill")
                    break
                
                if incremental_mode:
                    print(f"📡 Processing {len(shitposts)} posts from API (checking for existing posts in S3)...")
                    logger.info(f"Processing {len(shitposts)} posts from API (checking for existing posts in S3)")
                
                # Check if we've reached the limit before processing
                if self.limit and total_harvested >= self.limit:
                    logger.debug(f"Reached harvest limit of {self.limit} posts")
                    break
                
                # Process and store each shitpost to S3
                for shitpost in shitposts:
                    try:
                        posts_processed += 1
                        
                        # Apply date filtering if specified
                        if start_date or end_date:
                            post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00')).replace(tzinfo=None)
                            
                            # Check if post is before start date (stop crawling)
                            if start_date and post_timestamp < start_date:
                                logger.debug(f"📅 Reached posts before start date {start_date.date()}, stopping crawl")
                                logger.debug(f"📈 Total posts processed: {posts_processed}, Found {total_harvested} in target range")
                                return
                            
                            # Check if post is after end date (skip this post)
                            if end_date and post_timestamp > end_date:
                                max_id = shitpost.get('id')
                                continue  # Skip this post, continue to next
                        
                        # Check for incremental mode - stop if post already exists in S3
                        if incremental_mode and not dry_run:
                            # Generate expected S3 key for this post
                            post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00')).replace(tzinfo=None)
                            expected_s3_key = self.s3_data_lake._generate_s3_key(shitpost.get('id'), post_timestamp)
                            
                            print(f"🔍 Checking if post {shitpost.get('id')} already exists in S3...")
                            print(f"🔍 S3 key: {expected_s3_key}")
                            
                            try:
                                # Check if post already exists in S3 with timeout
                                print(f"⏱️  Starting S3 existence check...")
                                exists = await asyncio.wait_for(
                                    self.s3_data_lake.check_object_exists(expected_s3_key),
                                    timeout=15  # 15 second timeout
                                )
                                print(f"✅ S3 existence check completed: {exists}")
                                
                                if exists:
                                    print(f"✅ Found existing post {shitpost.get('id')} in S3")
                                    print(f"🔄 Incremental mode: Stopping harvest (no new posts to process)")
                                    print(f"📈 Total new posts harvested: {total_harvested}")
                                    logger.info(f"Incremental harvest completed - found existing post {shitpost.get('id')}, harvested {total_harvested} new posts")
                                    return
                                else:
                                    print(f"📝 Post {shitpost.get('id')} is new - will process")
                                    logger.debug(f"Post {shitpost.get('id')} is new, processing")
                                    
                            except asyncio.TimeoutError:
                                print(f"⏰ S3 existence check timed out for post {shitpost.get('id')}")
                                print(f"🔄 Assuming post is new and continuing...")
                                # Continue processing as if it's a new post
                            except Exception as e:
                                print(f"❌ Error checking S3 existence: {e}")
                                print(f"🔄 Assuming post is new and continuing...")
                                # Continue processing as if it's a new post
                        
                        # Post passed date filtering and incremental checks - process it
                        if dry_run:
                            # In dry run mode, just create a mock result
                            s3_key = f"truth-social/raw/2024/01/01/{shitpost.get('id')}.json"
                            logger.debug(f"DRY RUN: Would store post {shitpost.get('id')}")
                        else:
                            # Store raw data to S3
                            s3_key = await self.s3_data_lake.store_raw_data(shitpost)
                            logger.info(f"Stored post {shitpost.get('id')} to S3: {s3_key}")
                        
                        # Create result object
                        result = {
                            'shitpost_id': shitpost.get('id'),
                            's3_key': s3_key,
                            'timestamp': shitpost.get('created_at'),
                            'content_preview': shitpost.get('content', '')[:100] + '...' if shitpost.get('content') else 'No content',
                            'stored_at': datetime.now().isoformat()
                        }
                        
                        yield result
                        total_harvested += 1
                        
                        # Check if we've reached the limit
                        if self.limit and total_harvested >= self.limit:
                            logger.debug(f"Reached harvest limit of {self.limit} posts")
                            return
                        
                        # Update max_id for next batch (use the last post's ID for pagination)
                        max_id = shitpost.get('id')
                        
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                logger.info(f"Progress: {total_harvested} posts harvested and stored to S3")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in backfill harvest: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                await handle_exceptions(e)
                break
        
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("HARVEST SUMMARY")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"Total posts harvested: {total_harvested}")
        logger.info(f"Total API calls made: {self.api_call_count}")
        print(f"📊 API Call Summary: Made {self.api_call_count} API calls in this execution")
    
    
    async def get_s3_stats(self) -> Dict[str, any]:
        """Get statistics about S3 storage."""
        if not self.s3_data_lake:
            return {'error': 'S3 Data Lake not initialized'}
        
        return await self.s3_data_lake.get_data_stats()
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
        if self.s3_data_lake:
            await self.s3_data_lake.cleanup()
        logger.debug("Truth Social S3 harvester cleaned up")


async def main():
    """CLI entry point for Truth Social S3 harvesting."""
    parser = create_harvester_parser(
        description="Truth Social S3 harvester - stores raw data in S3",
        epilog=HARVESTER_EXAMPLES
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    validate_harvester_args(args)
    
    # Setup logging
    setup_harvester_logging(args.verbose)
    
    # Test verbose logging
    if args.verbose:
        print("🔍 VERBOSE MODE ENABLED - Debug logs will be shown")
    
    # Print start message
    print_harvest_start(args.mode, args.limit)
    limit_text = f" (limit: {args.limit})" if args.limit else ""
    logger.info(f"Starting Truth Social S3 harvesting in {args.mode} mode{limit_text}")
    
    # Create harvester with appropriate configuration
    harvester = TruthSocialS3Harvester(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        max_id=args.max_id
    )
    
    try:
        await harvester.initialize(dry_run=args.dry_run)
        
        # Harvest shitposts
        print("🔄 Starting harvest process...")
        logger.info("Starting harvest process")
        harvested_count = 0
        
        async for result in harvester.harvest_shitposts(dry_run=args.dry_run):
            if args.dry_run:
                print(f"📝 Would store: {result['shitpost_id']} - {result['content_preview']}")
                logger.info(f"Would store post: {result['shitpost_id']}")
            else:
                print(f"✅ Stored: {result['shitpost_id']} - {result['content_preview']}")
                print(f"   S3 Key: {result['s3_key']}")
                logger.info(f"Stored post: {result['shitpost_id']} to S3 key: {result['s3_key']}")
            
            harvested_count += 1
            
            # Apply limit if specified
            if args.limit and harvested_count >= args.limit:
                print(f"🎯 Reached harvest limit of {args.limit} posts")
                logger.info(f"Reached harvest limit of {args.limit} posts")
                break
        
        # Print completion message
        print_harvest_complete(harvested_count, args.dry_run)
        
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("HARVEST COMPLETED")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"Total posts processed: {harvested_count}")
        
        if not args.dry_run:
            # Show S3 statistics
            stats = await harvester.get_s3_stats()
            print_s3_stats(stats)
            logger.info(f"S3 storage stats: {stats}")
        
    except KeyboardInterrupt:
        print_harvest_interrupted()
    except Exception as e:
        print_harvest_error(e, args.verbose)
    finally:
        await harvester.cleanup()


# CLI entry point removed - use 'python -m shitposts' instead
