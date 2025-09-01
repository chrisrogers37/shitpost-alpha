"""
Truth Social Shitposts
Harvests shitposts from Truth Social using ScrapeCreators API.
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

logger = logging.getLogger(__name__)


class TruthSocialShitposts:
    """Harvester for Truth Social shitposts using ScrapeCreators."""
    
    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None):
        """Initialize the Truth Social shitpost harvester.
        
        Args:
            mode: Harvesting mode - "incremental", "backfill", "range", "from_date"
            start_date: Start date for range/from_date modes (YYYY-MM-DD)
            end_date: End date for range mode (YYYY-MM-DD)
            limit: Maximum number of posts to harvest (optional)
        """
        self.username = settings.TRUTH_SOCIAL_USERNAME
        self.monitor_interval = settings.TRUTH_SOCIAL_SHITPOST_INTERVAL
        
        # Harvesting mode configuration
        self.mode = mode
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        
        # Parse dates if provided
        if start_date:
            self.start_datetime = datetime.fromisoformat(start_date)
        if end_date:
            self.end_datetime = datetime.fromisoformat(end_date)
        
        # API configuration
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        
        # Trump's Truth Social user ID
        self.user_id = "107780257626128497"
        
        # Session and state
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_shitpost_id: Optional[str] = None
        self.last_check_time: Optional[datetime] = None
        
    async def initialize(self):
        """Initialize the Truth Social shitpost harvester."""
        logger.info(f"Initializing Truth Social shitpost harvester for @{self.username}")
        
        if not self.api_key:
            raise ValueError("SCRAPECREATORS_API_KEY not configured. Please add it to your .env file.")
        
        try:
            # Create aiohttp session
            self.session = aiohttp.ClientSession(
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'User-Agent': 'Shitpost-Alpha/1.0'
                }
            )
            
            # Test API connection
            await self._test_connection()
            
            # Initialize database connection for deduplication
            from shitvault.shitpost_db import ShitpostDatabase
            self.db_manager = ShitpostDatabase()
            await self.db_manager.initialize()
            
            # Get last shitpost ID from database for restart resilience
            self.last_shitpost_id = await self.db_manager.get_last_shitpost_id()
            if self.last_shitpost_id:
                logger.info(f"Resumed from last shitpost ID: {self.last_shitpost_id}")
            else:
                logger.info("No previous shitposts found, starting fresh")
            
            logger.info("Truth Social shitpost harvester initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Truth Social shitpost harvester: {e}")
            await self.cleanup()
            raise
    
    async def _test_connection(self):
        """Test the ScrapeCreators API connection."""
        try:
            # Test with a simple API call
            url = f"{self.base_url}/truthsocial/user/posts?user_id={self.user_id}&limit=1"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"API connection test failed: {response.status}")
                
                data = await response.json()
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
                params['max_id'] = next_max_id
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return []
                
                data = await response.json()
                
                if not data.get('success'):
                    logger.error(f"API returned error: {data}")
                    return []
                
                shitposts = data.get('data', [])
                logger.info(f"Fetched {len(shitposts)} shitposts from Truth Social")
                
                return shitposts
                
        except Exception as e:
            logger.error(f"Error fetching shitposts: {e}")
            return []
    
    async def harvest_shitposts(self) -> AsyncGenerator[Dict, None]:
        """Harvest shitposts based on configured mode."""
        logger.info(f"Starting shitpost harvest in {self.mode} mode...")
        
        if self.mode == "backfill":
            async for shitpost in self._harvest_backfill():
                yield shitpost
        elif self.mode == "range":
            async for shitpost in self._harvest_date_range():
                yield shitpost
        elif self.mode == "from_date":
            async for shitpost in self._harvest_from_date():
                yield shitpost
        else:  # incremental (default)
            async for shitpost in self._harvest_incremental():
                yield shitpost
    
    async def _harvest_backfill(self) -> AsyncGenerator[Dict, None]:
        """Harvest all historical Truth Social posts."""
        logger.info("Starting full backfill of Truth Social posts...")
        
        max_id = None
        total_harvested = 0
        
        while True:
            try:
                # Fetch batch of posts
                shitposts = await self._fetch_recent_shitposts(max_id)
                
                if not shitposts:
                    logger.info("No more posts to harvest in backfill")
                    break
                
                # Process each shitpost
                for shitpost in shitposts:
                    try:
                        processed_shitpost = await self._process_shitpost(shitpost)
                        if processed_shitpost:
                            yield processed_shitpost
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
                
                logger.info(f"Backfill progress: {total_harvested} posts harvested")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in backfill harvest: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Backfill completed. Total posts harvested: {total_harvested}")
    
    async def _harvest_date_range(self) -> AsyncGenerator[Dict, None]:
        """Harvest posts within a specific date range."""
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
                        post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00'))
                        
                        if post_timestamp < self.start_datetime:
                            logger.info(f"Reached posts before start date {self.start_date}, stopping")
                            return
                        
                        if post_timestamp > self.end_datetime:
                            # Skip posts after end date, continue to find older ones
                            max_id = shitpost.get('id')
                            continue
                        
                        processed_shitpost = await self._process_shitpost(shitpost)
                        if processed_shitpost:
                            yield processed_shitpost
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
                
                logger.info(f"Date range harvest progress: {total_harvested} posts harvested")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in date range harvest: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"Date range harvest completed. Total posts harvested: {total_harvested}")
    
    async def _harvest_from_date(self) -> AsyncGenerator[Dict, None]:
        """Harvest posts from a specific date onwards."""
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
                        post_timestamp = datetime.fromisoformat(shitpost.get('created_at').replace('Z', '+00:00'))
                        
                        if post_timestamp < self.start_datetime:
                            logger.info(f"Reached posts before start date {self.start_date}, stopping")
                            return
                        
                        processed_shitpost = await self._process_shitpost(shitpost)
                        if processed_shitpost:
                            yield processed_shitpost
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
                
                logger.info(f"From date harvest progress: {total_harvested} posts harvested")
                
                # Small delay to be respectful to API
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in from date harvest: {e}")
                await handle_exceptions(e)
                break
        
        logger.info(f"From date harvest completed. Total posts harvested: {total_harvested}")
    
    async def _harvest_incremental(self) -> AsyncGenerator[Dict, None]:
        """Harvest only new posts since last check (original implementation)."""
        logger.info("Starting incremental shitpost harvest from Truth Social...")
        
        while True:
            try:
                # Fetch recent shitposts
                shitposts = await self._fetch_recent_shitposts(self.last_shitpost_id)
                
                if not shitposts:
                    logger.debug("No new shitposts found")
                    await asyncio.sleep(self.monitor_interval)
                    continue
                
                # Process each shitpost
                for shitpost in shitposts:
                    try:
                        # Transform raw API data
                        processed_shitpost = await self._process_shitpost(shitpost)
                        
                        if processed_shitpost:
                            yield processed_shitpost
                            
                            # Update last shitpost ID
                            self.last_shitpost_id = shitpost.get('id')
                            
                    except Exception as e:
                        logger.error(f"Error processing shitpost {shitpost.get('id')}: {e}")
                        continue
                
                # Update last check time
                self.last_check_time = datetime.now()
                
                # Wait before next check
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in shitpost harvest loop: {e}")
                await handle_exceptions(e)
                await asyncio.sleep(self.monitor_interval)
    
    async def _process_shitpost(self, raw_shitpost: Dict) -> Optional[Dict]:
        """Process raw shitpost data from API."""
        try:
            # Extract basic shitpost data
            shitpost_id = raw_shitpost.get('id')
            content = raw_shitpost.get('content', '')
            timestamp = raw_shitpost.get('created_at')
            
            if not shitpost_id or not content:
                logger.warning(f"Invalid shitpost data: {raw_shitpost}")
                return None
            
            # Transform to our format
            processed_shitpost = {
                'id': shitpost_id,
                'content': content,
                'text': self._extract_text_content(content),
                'timestamp': timestamp,
                'username': self.username,
                'platform': 'truth_social',
                
                # Post metadata
                'language': raw_shitpost.get('language'),
                'visibility': raw_shitpost.get('visibility'),
                'sensitive': raw_shitpost.get('sensitive'),
                'spoiler_text': raw_shitpost.get('spoiler_text'),
                'uri': raw_shitpost.get('uri'),
                'url': raw_shitpost.get('url'),
                
                # Engagement metrics
                'replies_count': raw_shitpost.get('replies_count', 0),
                'reblogs_count': raw_shitpost.get('reblogs_count', 0),
                'favourites_count': raw_shitpost.get('favourites_count', 0),
                'upvotes_count': raw_shitpost.get('upvotes_count', 0),
                'downvotes_count': raw_shitpost.get('downvotes_count', 0),
                
                # Account information
                'account_id': raw_shitpost.get('account', {}).get('id'),
                'account_display_name': raw_shitpost.get('account', {}).get('display_name'),
                'account_followers_count': raw_shitpost.get('account', {}).get('followers_count', 0),
                'account_following_count': raw_shitpost.get('account', {}).get('following_count', 0),
                'account_statuses_count': raw_shitpost.get('account', {}).get('statuses_count', 0),
                'account_verified': raw_shitpost.get('account', {}).get('verified', False),
                'account_website': raw_shitpost.get('account', {}).get('website'),
                
                # Media and attachments
                'has_media': bool(raw_shitpost.get('media_attachments')),
                'media_attachments': raw_shitpost.get('media_attachments', []),
                'mentions': [mention.get('username') for mention in raw_shitpost.get('mentions', [])],
                'tags': [tag.get('name') for tag in raw_shitpost.get('tags', [])],
                
                # Additional API fields
                'in_reply_to_id': raw_shitpost.get('in_reply_to_id'),
                'quote_id': raw_shitpost.get('quote_id'),
                'in_reply_to_account_id': raw_shitpost.get('in_reply_to_account_id'),
                'card': raw_shitpost.get('card'),
                'group': raw_shitpost.get('group'),
                'quote': raw_shitpost.get('quote'),
                'in_reply_to': raw_shitpost.get('in_reply_to'),
                'reblog': raw_shitpost.get('reblog'),
                'sponsored': raw_shitpost.get('sponsored'),
                'reaction': raw_shitpost.get('reaction'),
                'favourited': raw_shitpost.get('favourited'),
                'reblogged': raw_shitpost.get('reblogged'),
                'muted': raw_shitpost.get('muted'),
                'pinned': raw_shitpost.get('pinned'),
                'bookmarked': raw_shitpost.get('bookmarked'),
                'poll': raw_shitpost.get('poll'),
                'emojis': raw_shitpost.get('emojis', []),
                'votable': raw_shitpost.get('votable'),
                'edited_at': raw_shitpost.get('edited_at'),
                'version': raw_shitpost.get('version'),
                'editable': raw_shitpost.get('editable'),
                'title': raw_shitpost.get('title'),
                
                # Raw API data for debugging/analysis
                'raw_api_data': raw_shitpost
            }
            
            logger.debug(f"Processed shitpost {shitpost_id}")
            return processed_shitpost
            
        except Exception as e:
            logger.error(f"Error processing shitpost: {e}")
            return None
    
    def _extract_text_content(self, content: str) -> str:
        """Extract plain text from HTML content."""
        if not content:
            return ""
        
        # Simple HTML tag removal
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        # Decode HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text
    
    async def get_recent_shitposts(self, limit: int = 10) -> List[Dict]:
        """Get recent shitposts for testing/debugging."""
        try:
            shitposts = await self._fetch_recent_shitposts()
            return shitposts[:limit]
        except Exception as e:
            logger.error(f"Error getting recent shitposts: {e}")
            return []
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
        logger.info("Truth Social shitpost harvester cleaned up")


async def main():
    """CLI entry point for Truth Social shitpost harvesting."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Truth Social shitpost harvester with multiple modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Incremental harvesting (default)
  python -m shitposts.truth_social_shitposts
  
  # Full historical backfill
  python -m shitposts.truth_social_shitposts --mode backfill
  
  # Date range harvesting
  python -m shitposts.truth_social_shitposts --mode range --from 2024-01-01 --to 2024-01-31
  
  # Harvest from specific date onwards
  python -m shitposts.truth_social_shitposts --mode from-date --from 2024-01-01
  
  # Harvest before specific date
  python -m shitposts.truth_social_shitposts --mode from-date --from 2024-01-01 --limit 100
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["incremental", "backfill", "range", "from-date"], 
        default="incremental", 
        help="Harvesting mode (default: incremental)"
    )
    parser.add_argument(
        "--from", 
        dest="start_date", 
        help="Start date for range/from-date modes (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", 
        dest="end_date", 
        help="End date for range mode (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Maximum number of posts to harvest (optional)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be harvested without saving to database"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mode in ["range", "from-date"] and not args.start_date:
        parser.error(f"--from date is required for {args.mode} mode")
    
    if args.mode == "range" and not args.end_date:
        parser.error("--to date is required for range mode")
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print(f"🚀 Starting Truth Social shitpost harvesting in {args.mode} mode...")
    
    # Create harvester with appropriate configuration
    harvester = TruthSocialShitposts(
        mode=args.mode,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit
    )
    
    try:
        await harvester.initialize()
        
        # Harvest shitposts
        harvested_count = 0
        async for shitpost in harvester.harvest_shitposts():
            if args.dry_run:
                print(f"📝 Would harvest: {shitpost['id']} - {shitpost['text'][:100]}...")
            else:
                print(f"✅ Harvested: {shitpost['id']} - {shitpost['text'][:100]}...")
            
            harvested_count += 1
            
            # Apply limit if specified
            if args.limit and harvested_count >= args.limit:
                print(f"🎯 Reached harvest limit of {args.limit} posts")
                break
        
        print(f"\n🎉 Harvesting completed! Total posts: {harvested_count}")
        
        if args.dry_run:
            print("🔍 This was a dry run - no posts were saved to database")
        
    except KeyboardInterrupt:
        print("\n⏹️  Harvesting stopped by user")
    except Exception as e:
        print(f"\n❌ Harvesting failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
    finally:
        await harvester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
