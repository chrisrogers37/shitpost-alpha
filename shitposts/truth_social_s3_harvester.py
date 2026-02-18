"""
Truth Social S3 Harvester
Harvests raw Truth Social data and stores it directly in S3.
"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, List
import aiohttp

from shit.config.shitpost_settings import settings
from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvestResult
from shitposts.cli import (
    create_harvester_parser, validate_harvester_args, setup_harvester_logging,
    print_harvest_start, print_harvest_progress, print_harvest_complete,
    print_harvest_error, print_harvest_interrupted, print_s3_stats,
    HARVESTER_EXAMPLES
)
from shit.logging import get_service_logger

logger = get_service_logger("harvester")


class TruthSocialS3Harvester(SignalHarvester):
    """Harvester for Truth Social posts via ScrapeCreators API."""

    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None, max_id=None):
        """Initialize the Truth Social S3 harvester.

        Args:
            mode: Harvesting mode - "incremental", "backfill", "range", "from_date"
            start_date: Start date for range/from_date modes (YYYY-MM-DD)
            end_date: End date for range mode (YYYY-MM-DD)
            limit: Maximum number of posts to harvest (optional)
            max_id: Starting post ID for backfill mode (for resuming)
        """
        super().__init__(mode=mode, start_date=start_date, end_date=end_date, limit=limit)

        # Truth Social-specific config
        self.username = settings.TRUTH_SOCIAL_USERNAME
        self.max_id = max_id
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        self.user_id = "107780257626128497"  # Trump's Truth Social user ID

        # HTTP session (created in _test_connection)
        self.session: Optional[aiohttp.ClientSession] = None

    # ── Interface implementation ───────────────────────────────────────

    def get_source_name(self) -> str:
        return "truth_social"

    def _get_s3_prefix(self) -> str:
        """Use hyphenated form for backward compatibility with existing S3 data."""
        return "truth-social"

    async def _test_connection(self) -> None:
        """Test the ScrapeCreators API connection."""
        if not self.api_key:
            raise ValueError("SCRAPECREATORS_API_KEY not configured. Please add it to your .env file.")

        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'User-Agent': 'Shitpost-Alpha-S3-Harvester/1.0'
                }
            )

        url = f"{self.base_url}/truthsocial/user/posts?user_id={self.user_id}&limit=1"
        logger.debug(f"Testing API connection to: {url}")
        timeout = aiohttp.ClientTimeout(total=10)
        async with self.session.get(url, timeout=timeout) as response:
            logger.debug(f"API test response status: {response.status}")
            if response.status != 200:
                raise Exception(f"API connection test failed: {response.status}")
            data = await response.json(content_type=None)
            if not data.get('success'):
                raise Exception(f"API returned error: {data}")
        logger.debug("ScrapeCreators API connection test successful")

    async def _fetch_batch(self, cursor: Optional[str] = None) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of posts from ScrapeCreators API.

        Args:
            cursor: The next_max_id for ScrapeCreators pagination.

        Returns:
            (list of raw post dicts, next cursor string or None)
        """
        try:
            url = f"{self.base_url}/truthsocial/user/posts"
            params = {'user_id': self.user_id, 'limit': 20}

            if cursor:
                params['next_max_id'] = cursor

            self.api_call_count += 1
            logger.info(f"Making API call #{self.api_call_count} to Truth Social API")

            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, params=params, timeout=timeout) as response:
                logger.debug(f"API response received, status: {response.status}")
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return [], None

                data = await response.json(content_type=None)
                if not data.get('success'):
                    logger.error(f"API returned error: {data}")
                    return [], None

                posts = data.get('posts', [])
                logger.info(f"Fetched {len(posts)} posts from Truth Social API")

                # Determine next cursor: use the last post's ID
                next_cursor = posts[-1].get('id') if posts else None

                return posts, next_cursor

        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return [], None

    def _extract_item_id(self, item: Dict) -> str:
        return item.get('id', '')

    def _extract_timestamp(self, item: Dict) -> datetime:
        created_at = item.get('created_at', '')
        if created_at.endswith('Z'):
            created_at = created_at.replace('Z', '+00:00')
        return datetime.fromisoformat(created_at).replace(tzinfo=None)

    def _extract_content_preview(self, item: Dict) -> str:
        content = item.get('content', '')
        if content and len(content) > 100:
            return content[:100] + '...'
        return content or 'No content'

    # ── Lifecycle overrides ────────────────────────────────────────────

    async def cleanup(self) -> None:
        """Cleanup aiohttp session and S3 resources."""
        if self.session:
            await self.session.close()
        await super().cleanup()

    # ── Backward-compatible methods ────────────────────────────────────

    async def _fetch_recent_shitposts(self, next_max_id: Optional[str] = None) -> List[Dict]:
        """Fetch recent shitposts. Backward-compatible wrapper around _fetch_batch."""
        posts, _ = await self._fetch_batch(cursor=next_max_id)
        return posts

    async def harvest_shitposts(self, dry_run: bool = False) -> AsyncGenerator[Dict, None]:
        """Backward-compatible wrapper that delegates to harvest().

        Existing callers expect Dict yields with 'shitpost_id' key.
        This adapter translates HarvestResult to the legacy format.
        """
        async for result in self.harvest(dry_run=dry_run):
            yield {
                'shitpost_id': result.source_post_id,
                's3_key': result.s3_key,
                'timestamp': result.timestamp,
                'content_preview': result.content_preview,
                'stored_at': result.stored_at,
            }


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
        print("VERBOSE MODE ENABLED - Debug logs will be shown")

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
        print("Starting harvest process...")
        logger.info("Starting harvest process")
        harvested_count = 0
        collected_s3_keys: list[str] = []

        async for result in harvester.harvest_shitposts(dry_run=args.dry_run):
            if args.dry_run:
                print(f"Would store: {result['shitpost_id']} - {result['content_preview']}")
                logger.info(f"Would store post: {result['shitpost_id']}")
            else:
                print(f"Stored: {result['shitpost_id']} - {result['content_preview']}")
                print(f"   S3 Key: {result['s3_key']}")
                logger.info(f"Stored post: {result['shitpost_id']} to S3 key: {result['s3_key']}")
                collected_s3_keys.append(result['s3_key'])

            harvested_count += 1

            # Apply limit if specified
            if args.limit and harvested_count >= args.limit:
                print(f"Reached harvest limit of {args.limit} posts")
                logger.info(f"Reached harvest limit of {args.limit} posts")
                break

        # Print completion message
        print_harvest_complete(harvested_count, args.dry_run)

        logger.info("")
        logger.info("=" * 59)
        logger.info("HARVEST COMPLETED")
        logger.info("=" * 59)
        logger.info(f"Total posts processed: {harvested_count}")

        if not args.dry_run:
            # Show S3 statistics
            stats = await harvester.get_s3_stats()
            print_s3_stats(stats)
            logger.info(f"S3 storage stats: {stats}")

        # Emit event for downstream consumers
        if collected_s3_keys and not args.dry_run:
            try:
                from shit.events.producer import emit_event
                from shit.events.event_types import EventType

                emit_event(
                    event_type=EventType.POSTS_HARVESTED,
                    payload={
                        "s3_keys": collected_s3_keys,
                        "source": harvester.get_source_name(),
                        "count": len(collected_s3_keys),
                        "mode": args.mode,
                    },
                    source_service="harvester",
                )
            except Exception as e:
                logger.warning(f"Failed to emit posts_harvested event: {e}")

    except KeyboardInterrupt:
        print_harvest_interrupted()
    except Exception as e:
        print_harvest_error(e, args.verbose)
    finally:
        await harvester.cleanup()


# CLI entry point removed - use 'python -m shitposts' instead
