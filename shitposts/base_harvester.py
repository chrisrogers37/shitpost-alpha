"""
Signal Harvester Base Class
Abstract interface for all data source harvesters.
"""

import abc
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, List

from shit.s3 import S3DataLake, S3Config
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger
from shitposts.harvester_models import (
    HarvestResult,
    HarvestSummary,
    HarvesterStatus,
)

logger = get_service_logger("harvester")


class SignalHarvester(abc.ABC):
    """Abstract base class for all signal harvesters.

    Every data source (Truth Social, Twitter, SEC filings, news feeds, etc.)
    implements this interface. The orchestrator and registry interact only
    through these methods.

    Lifecycle:
        1. __init__(config) -- configure mode, dates, limits
        2. initialize(dry_run) -- establish connections, verify API access
        3. harvest(dry_run) -- yield HarvestResult items
        4. cleanup() -- release resources
    """

    def __init__(
        self,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """Initialize the harvester with common parameters.

        Args:
            mode: Harvesting mode - "incremental", "backfill", "range", "from_date"
            start_date: Start date for range/from_date modes (YYYY-MM-DD)
            end_date: End date for range mode (YYYY-MM-DD)
            limit: Maximum number of posts to harvest (optional)
        """
        self.mode = mode
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit

        # Parse dates if provided
        self.start_datetime: Optional[datetime] = None
        self.end_datetime: Optional[datetime] = None

        if start_date:
            self.start_datetime = datetime.fromisoformat(start_date).replace(tzinfo=None)
        if end_date:
            self.end_datetime = datetime.fromisoformat(end_date).replace(tzinfo=None)
        else:
            self.end_datetime = datetime.now().replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

        # S3 Data Lake (initialized in initialize())
        self.s3_data_lake: Optional[S3DataLake] = None

        # Tracking
        self.api_call_count = 0
        self._start_time: Optional[str] = None

    # -- Abstract methods (must be implemented by each source) --

    @abc.abstractmethod
    def get_source_name(self) -> str:
        """Return the unique source identifier.

        Returns:
            Source name string, e.g. "truth_social", "twitter", "sec_filings"
        """
        ...

    @abc.abstractmethod
    async def _test_connection(self) -> None:
        """Test connectivity to the source API.

        Raises:
            Exception: If connection test fails.
        """
        ...

    @abc.abstractmethod
    async def _fetch_batch(self, cursor: Optional[str] = None) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of items from the source API.

        Args:
            cursor: Pagination cursor (source-specific). None for first page.

        Returns:
            Tuple of (list of raw items, next cursor or None if done).
        """
        ...

    @abc.abstractmethod
    def _extract_item_id(self, item: Dict) -> str:
        """Extract the unique item ID from a raw API response item."""
        ...

    @abc.abstractmethod
    def _extract_timestamp(self, item: Dict) -> datetime:
        """Extract the creation timestamp from a raw API response item."""
        ...

    @abc.abstractmethod
    def _extract_content_preview(self, item: Dict) -> str:
        """Extract a short text preview for logging purposes."""
        ...

    # -- Concrete methods (shared by all harvesters) --

    def _get_s3_prefix(self) -> str:
        """Get the S3 prefix for this harvester's data.

        Returns:
            S3 prefix string for this source.
        """
        return self.get_source_name()

    async def initialize(self, dry_run: bool = False) -> None:
        """Initialize the harvester: verify API access and prepare S3.

        Args:
            dry_run: If True, skip S3 initialization.
        """
        logger.info("")
        logger.info("=" * 59)
        logger.info(f"INITIALIZING HARVESTER: {self.get_source_name()}")
        logger.info("=" * 59)

        self._start_time = datetime.now().isoformat()

        # Source-specific connection test
        await self._test_connection()
        logger.info(f"API connection successful for {self.get_source_name()}")

        # Initialize S3 Data Lake
        if not dry_run:
            logger.info("Initializing S3 Data Lake...")
            s3_config = S3Config(
                bucket_name=settings.S3_BUCKET_NAME,
                prefix=self._get_s3_prefix(),
                region=settings.AWS_REGION,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            self.s3_data_lake = S3DataLake(s3_config)
            await self.s3_data_lake.initialize()
            logger.info("S3 Data Lake initialized successfully")
        else:
            logger.info("Dry run mode - skipping S3 initialization")

        logger.info(f"Harvester {self.get_source_name()} initialized successfully")

    async def harvest(self, dry_run: bool = False) -> AsyncGenerator[HarvestResult, None]:
        """Harvest items from the source. Main entry point.

        Args:
            dry_run: If True, do not store to S3.

        Yields:
            HarvestResult for each successfully processed item.
        """
        logger.info("")
        logger.info("=" * 59)
        logger.info(f"HARVESTING FROM {self.get_source_name().upper()}")
        logger.info("=" * 59)

        incremental_mode = (self.mode == "incremental")
        start_date = self.start_datetime if self.mode in ("range", "from_date") else None
        end_date = self.end_datetime if self.mode in ("range", "from_date") else None

        if incremental_mode:
            logger.info("Mode: Incremental (will stop when encountering existing items in S3)")
        elif start_date and end_date:
            logger.info(f"Mode: Date Range ({start_date.date()} to {end_date.date()})")
        else:
            logger.info("Mode: Full Backfill")

        cursor: Optional[str] = None
        total_harvested = 0

        while True:
            try:
                items, next_cursor = await self._fetch_batch(cursor)

                if not items:
                    logger.debug("No more items to harvest")
                    break

                if self.limit and total_harvested >= self.limit:
                    break

                for item in items:
                    try:
                        item_id = self._extract_item_id(item)
                        item_timestamp = self._extract_timestamp(item)

                        # Date filtering
                        if start_date and item_timestamp < start_date:
                            logger.debug("Reached items before start date, stopping")
                            return
                        if end_date and item_timestamp > end_date:
                            cursor = next_cursor
                            continue

                        # Incremental check: stop if item already in S3
                        if incremental_mode and not dry_run and self.s3_data_lake:
                            expected_key = self.s3_data_lake._generate_s3_key(
                                item_id, item_timestamp
                            )
                            try:
                                exists = await asyncio.wait_for(
                                    self.s3_data_lake.check_object_exists(expected_key),
                                    timeout=15,
                                )
                                if exists:
                                    logger.info(
                                        f"Incremental: found existing item {item_id}, "
                                        f"stopping. Harvested {total_harvested} new items."
                                    )
                                    return
                            except asyncio.TimeoutError:
                                logger.warning(f"S3 check timed out for {item_id}, assuming new")
                            except Exception as e:
                                logger.warning(f"S3 check failed for {item_id}: {e}, assuming new")

                        # Store to S3
                        if dry_run:
                            s3_key = f"{self._get_s3_prefix()}/raw/{item_timestamp.strftime('%Y/%m/%d')}/{item_id}.json"
                        else:
                            s3_key = await self.s3_data_lake.store_raw_data(item)
                            logger.info(f"Stored {item_id} to S3: {s3_key}")

                        result = HarvestResult(
                            source_name=self.get_source_name(),
                            source_post_id=item_id,
                            s3_key=s3_key,
                            timestamp=item_timestamp.isoformat() if isinstance(item_timestamp, datetime) else str(item_timestamp),
                            content_preview=self._extract_content_preview(item),
                            stored_at=datetime.now().isoformat(),
                        )

                        yield result
                        total_harvested += 1

                        if self.limit and total_harvested >= self.limit:
                            logger.debug(f"Reached limit of {self.limit}")
                            return

                    except Exception as e:
                        logger.error(f"Error processing item: {e}")
                        continue

                cursor = next_cursor
                if cursor is None:
                    break

                logger.info(f"Progress: {total_harvested} items harvested from {self.get_source_name()}")
                await asyncio.sleep(1)  # Rate limiting

            except Exception as e:
                logger.error(f"Error in harvest loop: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                break

        logger.info("")
        logger.info("=" * 59)
        logger.info(f"HARVEST SUMMARY ({self.get_source_name()})")
        logger.info("=" * 59)
        logger.info(f"Total items harvested: {total_harvested}")
        logger.info(f"Total API calls made: {self.api_call_count}")

    async def get_s3_stats(self) -> Dict:
        """Get S3 storage statistics for this source."""
        if not self.s3_data_lake:
            return {"error": "S3 Data Lake not initialized"}
        return await self.s3_data_lake.get_data_stats()

    async def cleanup(self) -> None:
        """Release all resources held by this harvester.

        Subclasses should override to close API sessions, then call super().
        """
        if self.s3_data_lake:
            await self.s3_data_lake.cleanup()
        logger.debug(f"{self.get_source_name()} harvester cleaned up")

    def get_summary(self, total_harvested: int, status: HarvesterStatus, error: Optional[str] = None) -> HarvestSummary:
        """Build a HarvestSummary for this run."""
        return HarvestSummary(
            source_name=self.get_source_name(),
            mode=self.mode,
            status=status,
            total_harvested=total_harvested,
            total_api_calls=self.api_call_count,
            started_at=self._start_time or datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            error_message=error,
        )
