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
from shitposts.s3_data_lake import S3DataLake
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
        
        # API configuration
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        
        # Trump's Truth Social user ID
        self.user_id = "107780257626128497"
        
        # Session and state
        self.session: Optional[aiohttp.ClientSession] = None
        self.s3_data_lake: Optional[S3DataLake] = None
        
    async def initialize(self, dry_run: bool = False):
        """Initialize the Truth Social S3 harvester."""
        logger.info(f"Initializing Truth Social S3 harvester for @{self.username}")
        
        if not self.api_key:
            raise ValueError("SCRAPECREATORS_API_KEY not configured. Please add it to your .env file.")
        
        try:
            # Create aiohttp session
            self.session = aiohttp.ClientSession(
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'User-Agent': 'Shitpost-Alpha-S3-Harvester/1.0'
                }
            )
            
            # Test API connection
            await self._test_connection()
            
            # Initialize S3 Data Lake only if not in dry run mode
            if not dry_run:
                self.s3_data_lake = S3DataLake()
                await self.s3_data_lake.initialize()
                logger.info("S3 Data Lake initialized successfully")
            else:
                logger.info("Dry run mode - skipping S3 initialization")
            
            logger.info("Truth Social S3 harvester initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Truth Social S3 harvester: {e}")
            await self.cleanup()
            raise
    
    async def _test_connection(self):
        """Test the ScrapeCreators API connection."""
        try:
            # Test with a simple API call
            url = f"{self.base_url}/truthsocial/user/posts?user_id={self.user_id}&limit=1"
            logger.info(f"Testing API connection to: {url}")
            async with self.session.get(url) as response:
                logger.info(f"API test response status: {response.status}")
                if response.status != 200:
                    raise Exception(f"API connection test failed: {response.status}")
                
                data = await response.json()
                logger.info(f"API test response data: {data}")
                if not data.get('success'):
                    raise Exception(f"API returned error: {data}")
                
                logger.info("ScrapeCreators API connection test successful")
                        
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
            
            logger.info(f"Making API request to: {url} with params: {params}")
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            async with self.session.get(url, params=params, timeout=timeout) as response:
                logger.info(f"API response status: {response.status}")
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return []
                
                data = await response.json()
                logger.info(f"API response data: {data}")
                
                if not data.get('success'):
                    logger.error(f"API returned error: {data}")
                    return []
                
                shitposts = data.get('posts', [])  # API returns 'posts' not 'data'
                logger.info(f"Fetched {len(shitposts)} shitposts from Truth Social")
                
                return shitposts
                
        except Exception as e:
            logger.error(f"Error fetching shitposts: {e}")
            return []
    
    async def harvest_shitposts(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest shitposts based on configured mode."""
        logger.info(f"Starting shitpost harvest in {self.mode} mode...")
        
        if self.mode == "backfill":
            async for result in self._harvest_backfill(dry_run):
                yield result
        elif self.mode == "range":
            async for result in self._harvest_date_range(dry_run):
                yield result
        elif self.mode == "from_date":
            async for result in self._harvest_from_date(dry_run):
                yield result
        else:  # incremental (default)
            async for result in self._harvest_incremental(dry_run):
                yield result
    
    async def _harvest_backfill(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest all historical Truth Social posts to S3."""
        logger.info("Starting full backfill of Truth Social posts to S3...")
        
        # Use provided max_id or start from most recent
        max_id = self.max_id
        total_harvested = 0
        
        if max_id:
            logger.info(f"Resuming backfill from post ID: {max_id}")
        else:
            logger.info("Starting backfill from most recent posts")
        
        while True:
            try:
                logger.info(f"Fetching batch of posts with max_id: {max_id}")
                # Fetch batch of posts from API (start with most recent, no max_id)
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                logger.info(f"API returned {len(shitposts) if shitposts else 0} posts")
                
                if not shitposts:
                    logger.info("No more posts to harvest in backfill")
                    break
                
                # Check if we've reached the limit before processing
                if self.limit and total_harvested >= self.limit:
                    logger.info(f"Reached harvest limit of {self.limit} posts")
                    break
                
                # Process and store each shitpost to S3
                for shitpost in shitposts:
                    try:
                        if dry_run:
                            # In dry run mode, just create a mock result
                            s3_key = f"truth-social/raw/2024/01/01/{shitpost.get('id')}.json"
                        else:
                            # Store raw data to S3
                            s3_key = await self.s3_data_lake.store_raw_data(shitpost)
                        
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
                            logger.info(f"Reached harvest limit of {self.limit} posts")
                            return
                        
                        # Update max_id for next batch (use the last post's ID for pagination)
                        max_id = shitpost.get('id')
                        
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                logger.info(f"Backfill progress: {total_harvested} posts harvested and stored to S3")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in backfill harvest: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Backfill completed. Total posts harvested and stored to S3: {total_harvested}")
    
    async def _harvest_date_range(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest posts within a specific date range to S3."""
        logger.info(f"Starting date range harvest from {self.start_date} to {self.end_date}")
        
        max_id = None
        total_harvested = 0
        
        while True:
            try:
                # Fetch batch of posts
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                if not shitposts:
                    logger.info("No more posts to harvest in date range")
                    break
                
                # Process each shitpost
                for shitpost in shitposts:
                    try:
                        # Check if post is within date range
                        post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00')).replace(tzinfo=None)
                        
                        if post_timestamp < self.start_datetime:
                            logger.info(f"Reached posts before start date {self.start_date}, stopping")
                            return
                        
                        if post_timestamp > self.end_datetime:
                            # Skip posts after end date, continue to find older ones
                            max_id = shitpost.get('id')
                            continue
                        
                        if dry_run:
                            # In dry run mode, just create a mock result
                            s3_key = f"truth-social/raw/2024/01/01/{shitpost.get('id')}.json"
                        else:
                            # Store raw data to S3
                            s3_key = await self.s3_data_lake.store_raw_data(shitpost)
                        
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
                            logger.info(f"Reached harvest limit of {self.limit} posts")
                            return
                        
                        # Update max_id for next batch
                        max_id = shitpost.get('id')
                        
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                logger.info(f"Date range harvest progress: {total_harvested} posts harvested to S3")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in date range harvest: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Date range harvest completed. Total posts harvested to S3: {total_harvested}")
    
    async def _harvest_from_date(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest posts from a specific date onwards to S3."""
        logger.info(f"Starting harvest from date {self.start_date} onwards")
        
        max_id = None
        total_harvested = 0
        
        while True:
            try:
                # Fetch batch of posts
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                if not shitposts:
                    logger.info("No more posts to harvest from date")
                    break
                
                # Process each shitpost
                for shitpost in shitposts:
                    try:
                        # Check if post is from start date onwards
                        post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00')).replace(tzinfo=None)
                        
                        if post_timestamp < self.start_datetime:
                            logger.info(f"Reached posts before start date {self.start_date}, stopping")
                            return
                        
                        if dry_run:
                            # In dry run mode, just create a mock result
                            s3_key = f"truth-social/raw/2024/01/01/{shitpost.get('id')}.json"
                        else:
                            # Store raw data to S3
                            s3_key = await self.s3_data_lake.store_raw_data(shitpost)
                        
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
                            logger.info(f"Reached harvest limit of {self.limit} posts")
                            return
                        
                        # Update max_id for next batch
                        max_id = shitpost.get('id')
                        
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                logger.info(f"From date harvest progress: {total_harvested} posts harvested to S3")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in from date harvest: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"From date harvest completed. Total posts harvested to S3: {total_harvested}")
    
    async def _harvest_incremental(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Harvest only new posts since last check (incremental mode)."""
        logger.info("Starting incremental shitpost harvest from Truth Social to S3...")
        
        # For incremental mode, we'll start from the most recent posts
        # In a production system, you'd want to track the last processed post
        max_id = None
        
        while True:
            try:
                # Fetch recent shitposts
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                if not shitposts:
                    logger.debug("No new shitposts found")
                    await asyncio.sleep(30)  # Wait 30 seconds before next check
                    continue
                
                # Process each shitpost
                for shitpost in shitposts:
                    try:
                        if dry_run:
                            # In dry run mode, just create a mock result
                            s3_key = f"truth-social/raw/2024/01/01/{shitpost.get('id')}.json"
                        else:
                            # Store raw data to S3
                            s3_key = await self.s3_data_lake.store_raw_data(shitpost)
                        
                        # Create result object
                        result = {
                            'shitpost_id': shitpost.get('id'),
                            's3_key': s3_key,
                            'timestamp': shitpost.get('created_at'),
                            'content_preview': shitpost.get('content', '')[:100] + '...' if shitpost.get('content') else 'No content',
                            'stored_at': datetime.now().isoformat()
                        }
                        
                        yield result
                        
                        # Update max_id for next batch
                        max_id = shitpost.get('id')
                        
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                # Wait before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in shitpost harvest loop: {e}")
                await handle_exceptions(e)
                await asyncio.sleep(30)
    
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
        logger.info("Truth Social S3 harvester cleaned up")


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
    
    # Print start message
    print_harvest_start(args.mode, args.limit)
    
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
        harvested_count = 0
        
        async for result in harvester.harvest_shitposts(dry_run=args.dry_run):
            if args.dry_run:
                print(f"📝 Would store: {result['shitpost_id']} - {result['content_preview']}")
            else:
                print(f"✅ Stored: {result['shitpost_id']} - {result['content_preview']}")
                print(f"   S3 Key: {result['s3_key']}")
            
            harvested_count += 1
            
            # Apply limit if specified
            if args.limit and harvested_count >= args.limit:
                print(f"🎯 Reached harvest limit of {args.limit} posts")
                break
        
        # Print completion message
        print_harvest_complete(harvested_count, args.dry_run)
        
        if not args.dry_run:
            # Show S3 statistics
            stats = await harvester.get_s3_stats()
            print_s3_stats(stats)
        
    except KeyboardInterrupt:
        print_harvest_interrupted()
    except Exception as e:
        print_harvest_error(e, args.verbose)
    finally:
        await harvester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
