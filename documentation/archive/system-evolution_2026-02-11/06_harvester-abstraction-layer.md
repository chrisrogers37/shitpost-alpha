# Phase 06: Harvester Abstraction Layer (Multi-Source Interface)

**PR Title:** `feat: harvester abstraction layer with multi-source interface`
**Risk Level:** Medium
**Estimated Effort:** High (3-5 days)
**Branch Name:** `feature/harvester-abstraction-layer`

---

## Files Summary

### Files Created (7)
- `shitposts/base_harvester.py` -- Abstract base class `SignalHarvester`
- `shitposts/harvester_registry.py` -- Registry pattern for dynamic source management
- `shitposts/harvester_models.py` -- Shared data models for harvester results
- `shitposts/twitter_harvester.py` -- Skeleton `TwitterHarvester` template
- `shit_tests/shitposts/test_base_harvester.py` -- Tests for abstract base class
- `shit_tests/shitposts/test_harvester_registry.py` -- Tests for registry
- `shit_tests/shitposts/test_twitter_harvester.py` -- Tests for skeleton harvester

### Files Modified (7)
- `shitposts/truth_social_s3_harvester.py` -- Refactor to implement `SignalHarvester` interface
- `shitposts/cli.py` -- Generalize CLI helpers (remove "Truth Social" hardcoding)
- `shitposts/__main__.py` -- Update to support `--source` flag
- `shitpost_alpha.py` -- Update orchestrator to iterate over registered harvesters
- `shit/s3/s3_config.py` -- Support per-source prefix configuration
- `shit/config/shitpost_settings.py` -- Add multi-source settings
- `shit_tests/shitposts/test_truth_social_s3_harvester.py` -- Update tests for refactored class

### Files Deleted (0)
None. This is a pure additive refactor.

---

## 1. Context

### Why This Matters

The current system is hardwired to a single data source: Trump's Truth Social posts via the ScrapeCreators API. This creates three serious risks:

1. **Single Vendor Lock-in**: If ScrapeCreators raises prices, changes their API, or goes offline, the entire pipeline breaks with zero alternatives.
2. **Limited Signal Coverage**: Financial markets react to signals from many sources (X/Twitter, news feeds, SEC filings, press conferences). A single-source system misses most of the signal landscape.
3. **Coupling Everywhere**: The `TruthSocialS3Harvester` class hardcodes ScrapeCreators endpoints (`https://api.scrapecreators.com/v1`), Trump's user ID (`107780257626128497`), Truth Social API field names (`posts`, `created_at`), and the S3 path prefix (`truth-social/`). Adding any new source would require duplicating this entire class with no shared structure.

The abstraction layer introduces a `SignalHarvester` interface that any source can implement. The existing Truth Social harvester becomes one implementation among potentially many. A registry allows the orchestrator to discover and run all configured harvesters without knowing their internals.

### Relationship to Phase 02 (Source-Agnostic Data Model)

Phase 02 focuses on making the _database schema_ source-agnostic (renaming `truth_social_shitposts` to a generic table, adding a `source` column, etc.). Phase 06 focuses on making the _harvesting layer_ source-agnostic.

**Dependency**: Phase 02 should ideally complete first so that downstream processing (S3 processor, database storage, analysis) can handle multi-source data. However, Phase 06 can proceed independently because:
- The harvester already writes raw data to S3 (not directly to the database).
- The S3 storage format already includes a `metadata.source` field (`truth_social_api`).
- The `platform` column on `TruthSocialShitpost` already exists with value `truth_social`.

If Phase 02 is not done yet, Phase 06 works perfectly for S3 storage -- the downstream S3-to-database processing will simply continue handling only `truth_social` source data until Phase 02 makes the DB layer multi-source.

---

## 2. Dependencies

| Dependency | Status | Impact if Missing |
|---|---|---|
| Phase 02 (Source-Agnostic Data Model) | Should complete first | Phase 06 works for S3 storage; DB loading of non-TS sources blocked until Phase 02 |
| `shitposts/truth_social_s3_harvester.py` | Exists | Will be refactored |
| `shit/s3/s3_data_lake.py` | Exists | Used by all harvesters (shared) |
| `shit/s3/s3_config.py` | Exists | Will be enhanced for per-source prefixes |
| `shitpost_alpha.py` | Exists | Will be updated |

---

## 3. Detailed Implementation Plan

### Step 1: Create Harvester Data Models (`shitposts/harvester_models.py`)

**Purpose**: Define shared data structures that all harvesters produce, decoupling the rest of the system from source-specific field names.

**Create file** at `/Users/chris/Projects/shitpost-alpha/shitposts/harvester_models.py`:

```python
"""
Harvester Data Models
Shared data structures for all signal harvesters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class HarvesterMode(str, Enum):
    """Supported harvesting modes."""
    INCREMENTAL = "incremental"
    BACKFILL = "backfill"
    RANGE = "range"
    FROM_DATE = "from_date"


class HarvesterStatus(str, Enum):
    """Harvester execution status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class HarvestResult:
    """Standardized result from any harvester.
    
    Every harvester yields these through harvest(), regardless of source.
    """
    source_name: str          # e.g., "truth_social", "twitter", "sec_filings"
    source_post_id: str       # Original ID from the source platform
    s3_key: str               # Where the raw data was stored in S3
    timestamp: str            # ISO format timestamp of the original post
    content_preview: str      # First ~100 chars for logging
    stored_at: str            # ISO format timestamp of when we stored it
    metadata: Dict[str, Any] = field(default_factory=dict)  # Source-specific extras


@dataclass
class HarvestSummary:
    """Summary of a single harvester execution run."""
    source_name: str
    mode: str
    status: HarvesterStatus
    total_harvested: int
    total_api_calls: int
    started_at: str           # ISO format
    completed_at: str         # ISO format
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarvesterConfig:
    """Configuration for a harvester instance.
    
    Each harvester reads its own source-specific settings but reports
    them through this common structure for the registry.
    """
    source_name: str
    enabled: bool = True
    mode: HarvesterMode = HarvesterMode.INCREMENTAL
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: Optional[int] = None
    s3_prefix: Optional[str] = None  # Override for S3 path prefix
    extra: Dict[str, Any] = field(default_factory=dict)  # Source-specific config
```

**Rationale**: Currently, the Truth Social harvester yields raw dicts with keys like `shitpost_id`, `s3_key`, `timestamp`, `content_preview`, `stored_at`. By creating a `HarvestResult` dataclass, we formalize this contract. Every harvester must produce the same shape of output.

---

### Step 2: Create Abstract Base Class (`shitposts/base_harvester.py`)

**Purpose**: Define the interface that every harvester must implement.

**Create file** at `/Users/chris/Projects/shitpost-alpha/shitposts/base_harvester.py`:

```python
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
    HarvesterConfig,
    HarvesterMode,
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
    
    # ── Abstract methods (must be implemented by each source) ──────────
    
    @abc.abstractmethod
    def get_source_name(self) -> str:
        """Return the unique source identifier.
        
        This is used for S3 path prefixes, logging, and registry keys.
        
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
        """Extract the unique item ID from a raw API response item.
        
        Args:
            item: Single raw item from the source API.
            
        Returns:
            The source-specific unique identifier string.
        """
        ...
    
    @abc.abstractmethod
    def _extract_timestamp(self, item: Dict) -> datetime:
        """Extract the creation timestamp from a raw API response item.
        
        Args:
            item: Single raw item from the source API.
            
        Returns:
            Datetime of when the item was originally created.
        """
        ...
    
    @abc.abstractmethod
    def _extract_content_preview(self, item: Dict) -> str:
        """Extract a short text preview for logging purposes.
        
        Args:
            item: Single raw item from the source API.
            
        Returns:
            First ~100 characters of content for display.
        """
        ...
    
    # ── Concrete methods (shared by all harvesters) ────────────────────
    
    def _get_s3_prefix(self) -> str:
        """Get the S3 prefix for this harvester's data.
        
        Default pattern: {source_name}
        Combined with S3Config.raw_data_prefix to produce:
            {source_name}/raw/YYYY/MM/DD/{id}.json
            
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
        
        This is the universal harvest loop. It delegates to _fetch_batch()
        and handles mode logic (incremental, backfill, range), date filtering,
        limit enforcement, and S3 storage.
        
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
                            logger.debug(f"Reached items before start date, stopping")
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
                        logger.error(f"Error processing item {self._extract_item_id(item)}: {e}")
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
```

**Key design decisions**:

1. **`_fetch_batch()` returns `(items, next_cursor)`**: This decouples pagination from the harvest loop. ScrapeCreators uses `next_max_id`. Twitter uses cursor tokens. SEC filings might use page numbers. The base class does not care.

2. **The harvest loop lives in the base class**: Date filtering, incremental S3 checking, limit enforcement, and error handling are universal. Subclasses only implement "fetch a batch" and "extract fields."

3. **Six abstract methods**: `get_source_name()`, `_test_connection()`, `_fetch_batch()`, `_extract_item_id()`, `_extract_timestamp()`, `_extract_content_preview()`. These are the minimum a source needs to provide.

4. **S3 prefix is `{source_name}`**: Instead of hardcoding `truth-social`, each harvester uses its source name. The `S3Config.prefix` is set per harvester instance.

---

### Step 3: Refactor `TruthSocialS3Harvester` to Implement Interface

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shitposts/truth_social_s3_harvester.py`.

The key changes:
- Inherit from `SignalHarvester` instead of being a standalone class
- Move ScrapeCreators-specific logic into the abstract method implementations
- Remove the duplicated harvest loop (use the base class `harvest()` instead)
- Keep the `main()` function working unchanged for CLI

**Before** (current lines 27-68 of `truth_social_s3_harvester.py`):

```python
class TruthSocialS3Harvester:
    """Harvester for Truth Social posts that stores raw data in S3."""
    
    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None, max_id=None):
        self.username = settings.TRUTH_SOCIAL_USERNAME
        self.mode = mode
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        self.max_id = max_id
        # ... date parsing ...
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        self.user_id = "107780257626128497"
        self.session: Optional[aiohttp.ClientSession] = None
        self.s3_data_lake: Optional[S3DataLake] = None
        self.api_call_count = 0
```

**After** (refactored):

```python
from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvestResult

class TruthSocialS3Harvester(SignalHarvester):
    """Harvester for Truth Social posts via ScrapeCreators API."""
    
    def __init__(self, mode="incremental", start_date=None, end_date=None, limit=None, max_id=None):
        super().__init__(mode=mode, start_date=start_date, end_date=end_date, limit=limit)
        
        # Truth Social-specific config
        self.username = settings.TRUTH_SOCIAL_USERNAME
        self.max_id = max_id  # ScrapeCreators-specific pagination
        self.api_key = settings.SCRAPECREATORS_API_KEY
        self.base_url = "https://api.scrapecreators.com/v1"
        self.user_id = "107780257626128497"  # Trump's Truth Social user ID
        
        # HTTP session (created in initialize)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Track current pagination cursor for _fetch_batch
        self._current_cursor: Optional[str] = max_id
    
    # ── Interface implementation ───────────────────────────────────────
    
    def get_source_name(self) -> str:
        return "truth_social"
    
    async def _test_connection(self) -> None:
        """Test the ScrapeCreators API connection."""
        if not self.api_key:
            raise ValueError("SCRAPECREATORS_API_KEY not configured. Please add it to your .env file.")
        
        # Create aiohttp session
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
            if response.status != 200:
                raise Exception(f"API connection test failed: {response.status}")
            data = await response.json()
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
                if response.status != 200:
                    logger.error(f"API request failed: {response.status}")
                    return [], None
                
                data = await response.json()
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
    
    async def initialize(self, dry_run: bool = False) -> None:
        """Initialize with Truth Social-specific connection setup."""
        # The base class calls _test_connection() which creates the session
        await super().initialize(dry_run=dry_run)
    
    async def cleanup(self) -> None:
        """Cleanup aiohttp session and S3 resources."""
        if self.session:
            await self.session.close()
        await super().cleanup()
    
    # ── Backward-compatible methods ────────────────────────────────────
    
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
```

**What changed**:

| Aspect | Before | After |
|---|---|---|
| Inheritance | `class TruthSocialS3Harvester:` | `class TruthSocialS3Harvester(SignalHarvester):` |
| Harvest loop | 150-line `_harvest_backfill()` method | Inherited from `SignalHarvester.harvest()` |
| Pagination | Manual `max_id` tracking inside loop | `_fetch_batch()` returns `(items, next_cursor)` |
| S3 init | Done inside `initialize()` | Delegated to `super().initialize()` |
| Date parsing | Manual in `__init__` | Handled by `super().__init__()` |
| Source identity | Implicit (hardcoded strings) | Explicit via `get_source_name()` return |
| API calls | `_fetch_recent_shitposts()` | `_fetch_batch()` (same logic, new name) |
| Backward compat | N/A | `harvest_shitposts()` wraps `harvest()` |

**Critical**: The `harvest_shitposts()` method is kept as a backward-compatible wrapper so the existing `main()` function at line 393 and the existing tests continue to work without changes. The `main()` function calls `harvester.harvest_shitposts()` at line 434, so this adapter is essential.

---

### Step 4: Create Harvester Registry (`shitposts/harvester_registry.py`)

**Purpose**: Config-driven discovery and management of available harvesters. The orchestrator asks "give me all enabled harvesters" rather than hardcoding `TruthSocialS3Harvester`.

**Create file** at `/Users/chris/Projects/shitpost-alpha/shitposts/harvester_registry.py`:

```python
"""
Harvester Registry
Config-driven discovery and management of signal harvesters.
"""

from typing import Dict, List, Optional, Type

from shit.logging import get_service_logger
from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvesterConfig

logger = get_service_logger("harvester_registry")


class HarvesterRegistry:
    """Registry for signal harvesters.
    
    Usage:
        registry = HarvesterRegistry()
        registry.register("truth_social", TruthSocialS3Harvester)
        registry.register("twitter", TwitterHarvester)
        
        harvesters = registry.create_all(mode="incremental")
        for harvester in harvesters:
            await harvester.initialize()
            async for result in harvester.harvest():
                process(result)
    """
    
    def __init__(self):
        self._registry: Dict[str, Type[SignalHarvester]] = {}
        self._configs: Dict[str, HarvesterConfig] = {}
    
    def register(
        self,
        source_name: str,
        harvester_class: Type[SignalHarvester],
        config: Optional[HarvesterConfig] = None,
    ) -> None:
        """Register a harvester class for a source.
        
        Args:
            source_name: Unique source identifier (e.g., "truth_social")
            harvester_class: The harvester class (not an instance)
            config: Optional configuration override
        """
        if not issubclass(harvester_class, SignalHarvester):
            raise TypeError(
                f"{harvester_class.__name__} must be a subclass of SignalHarvester"
            )
        
        self._registry[source_name] = harvester_class
        if config:
            self._configs[source_name] = config
        else:
            self._configs[source_name] = HarvesterConfig(source_name=source_name)
        
        logger.info(f"Registered harvester: {source_name} -> {harvester_class.__name__}")
    
    def unregister(self, source_name: str) -> None:
        """Remove a harvester from the registry."""
        self._registry.pop(source_name, None)
        self._configs.pop(source_name, None)
        logger.info(f"Unregistered harvester: {source_name}")
    
    def get_class(self, source_name: str) -> Optional[Type[SignalHarvester]]:
        """Get the harvester class for a source."""
        return self._registry.get(source_name)
    
    def get_config(self, source_name: str) -> Optional[HarvesterConfig]:
        """Get the configuration for a source."""
        return self._configs.get(source_name)
    
    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._registry.keys())
    
    def list_enabled_sources(self) -> List[str]:
        """List source names where the harvester is enabled."""
        return [
            name for name, config in self._configs.items()
            if config.enabled
        ]
    
    def create_harvester(
        self,
        source_name: str,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> SignalHarvester:
        """Create a harvester instance for a specific source.
        
        Args:
            source_name: Which source to create
            mode: Harvesting mode
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum items to harvest
            **kwargs: Source-specific arguments
            
        Returns:
            Configured harvester instance
            
        Raises:
            KeyError: If source_name is not registered
        """
        if source_name not in self._registry:
            raise KeyError(
                f"Unknown source: '{source_name}'. "
                f"Registered sources: {self.list_sources()}"
            )
        
        cls = self._registry[source_name]
        return cls(
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            **kwargs,
        )
    
    def create_all_enabled(
        self,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[SignalHarvester]:
        """Create harvester instances for all enabled sources.
        
        Args:
            mode: Harvesting mode (applied to all)
            start_date: Start date (applied to all)
            end_date: End date (applied to all)
            limit: Limit (applied to all)
            
        Returns:
            List of configured harvester instances
        """
        harvesters = []
        for source_name in self.list_enabled_sources():
            config = self._configs[source_name]
            extra_kwargs = config.extra if config.extra else {}
            
            harvester = self.create_harvester(
                source_name=source_name,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                **extra_kwargs,
            )
            harvesters.append(harvester)
        
        return harvesters


def create_default_registry() -> HarvesterRegistry:
    """Create the default registry with all known harvesters.
    
    This is the single place that wires up which sources are available.
    """
    from shitposts.truth_social_s3_harvester import TruthSocialS3Harvester
    
    registry = HarvesterRegistry()
    
    # Register Truth Social (always enabled - it's the primary source)
    registry.register(
        "truth_social",
        TruthSocialS3Harvester,
        HarvesterConfig(source_name="truth_social", enabled=True),
    )
    
    # Future sources will be registered here:
    # registry.register("twitter", TwitterHarvester, HarvesterConfig(..., enabled=False))
    # registry.register("sec_filings", SECHarvester, HarvesterConfig(..., enabled=False))
    
    return registry
```

**Design notes**:

- **Lazy imports** in `create_default_registry()` avoid circular imports (the registry module imports harvester classes only when called).
- **`create_all_enabled()`** is what the orchestrator will call -- it returns a list of instantiated harvesters for all sources marked `enabled=True`.
- **`HarvesterConfig.extra`** allows source-specific kwargs (e.g., `max_id` for Truth Social) to be passed through.

---

### Step 5: Update S3 Config for Per-Source Prefixes

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_config.py`.

The current `S3Config.prefix` defaults to `"truth-social"`. After refactoring, each harvester passes its own prefix based on `get_source_name()`.

**Lines 11-15, before**:

```python
@dataclass
class S3Config:
    """S3 configuration settings."""
    
    # S3 Connection
    bucket_name: str
    prefix: str = "truth-social"
```

**After**:

```python
@dataclass
class S3Config:
    """S3 configuration settings."""
    
    # S3 Connection
    bucket_name: str
    prefix: str = "truth-social"  # Default for backward compat; harvesters override this
```

No actual code change needed here -- the default remains `truth-social` for backward compatibility. The `TruthSocialS3Harvester.get_source_name()` returns `"truth_social"`, which the base class passes as `S3Config(prefix=...)`. But we must note this means the S3 prefix changes from `truth-social` (hyphen) to `truth_social` (underscore).

**IMPORTANT DECISION**: To avoid breaking existing S3 data, override `_get_s3_prefix()` in the Truth Social harvester:

```python
# In TruthSocialS3Harvester
def _get_s3_prefix(self) -> str:
    """Use hyphenated form for backward compatibility with existing S3 data."""
    return "truth-social"
```

This ensures existing S3 keys like `truth-social/raw/2025/01/15/12345.json` continue to be found. New sources will use underscored names (e.g., `twitter/raw/...`).

---

### Step 6: Update Settings for Multi-Source Configuration

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py`.

Add settings for future sources. These are optional and will be `None` by default.

**After line 103** (after `AWS_REGION`), add:

```python
    # Multi-Source Harvester Configuration
    ENABLED_HARVESTERS: str = Field(
        default="truth_social",
        env="ENABLED_HARVESTERS",
    )  # Comma-separated list of enabled harvester source names
    
    # Twitter/X Configuration (Future)
    TWITTER_API_KEY: Optional[str] = Field(default=None, env="TWITTER_API_KEY")
    TWITTER_API_SECRET: Optional[str] = Field(default=None, env="TWITTER_API_SECRET")
    TWITTER_BEARER_TOKEN: Optional[str] = Field(default=None, env="TWITTER_BEARER_TOKEN")
    TWITTER_TARGET_USERS: str = Field(
        default="", env="TWITTER_TARGET_USERS"
    )  # Comma-separated Twitter usernames to monitor
    
    def get_enabled_harvester_names(self) -> list[str]:
        """Parse ENABLED_HARVESTERS into a list of source names."""
        return [h.strip() for h in self.ENABLED_HARVESTERS.split(",") if h.strip()]
```

---

### Step 7: Update CLI Module for Multi-Source Support

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shitposts/cli.py`.

The current CLI helpers hardcode "Truth Social" strings. Generalize them while keeping backward compatibility.

**Lines 104-112, before**:

```python
def print_harvest_start(mode: str, limit: Optional[int] = None) -> None:
    limit_text = f" (limit: {limit})" if limit else ""
    print_info(f"Starting Truth Social S3 harvesting in {mode} mode{limit_text}...")
```

**After**:

```python
def print_harvest_start(mode: str, limit: Optional[int] = None, source: str = "Truth Social") -> None:
    """Print harvester start message.
    
    Args:
        mode: Harvesting mode
        limit: Harvest limit (optional)
        source: Source name for display (default: Truth Social for backward compat)
    """
    limit_text = f" (limit: {limit})" if limit else ""
    print_info(f"Starting {source} S3 harvesting in {mode} mode{limit_text}...")
```

Apply the same pattern to `print_harvest_complete`:

**Lines 128-140, before**:

```python
def print_harvest_complete(harvested_count: int, dry_run: bool = False) -> None:
    print_success(f"S3 harvesting completed! Total posts: {harvested_count}")
    ...
```

**After** -- add optional `source` parameter:

```python
def print_harvest_complete(harvested_count: int, dry_run: bool = False, source: str = "S3") -> None:
    """Print harvester completion message."""
    print_success(f"{source} harvesting completed! Total posts: {harvested_count}")
    ...
```

Add a `--source` argument to `create_harvester_parser`:

```python
# After the --max-id argument (line 74), add:
parser.add_argument(
    "--source",
    type=str,
    default=None,
    help="Harvester source name (e.g., truth_social, twitter). Default: all enabled."
)
```

---

### Step 8: Update `__main__.py` for Source Selection

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shitposts/__main__.py`.

**Before** (current, lines 1-8):

```python
"""
CLI entry point for shitposts package.
"""
import asyncio
from shitposts.truth_social_s3_harvester import main

if __name__ == "__main__":
    asyncio.run(main())
```

**After**:

```python
"""
CLI entry point for shitposts package.

Supports:
    python -m shitposts                          # Truth Social (default)
    python -m shitposts --source truth_social    # Explicit source
    python -m shitposts --source twitter         # Future: Twitter source
"""
import asyncio
from shitposts.truth_social_s3_harvester import main

if __name__ == "__main__":
    asyncio.run(main())
```

The `main()` function in `truth_social_s3_harvester.py` already handles the `--source` flag via the parser. For now, `main()` continues to create `TruthSocialS3Harvester` directly. A future enhancement can route to the registry based on `--source`. This is intentionally minimal for Phase 06 -- the main entry point for multi-source harvesting is the orchestrator, not the CLI.

---

### Step 9: Update Orchestrator for Multi-Source Harvesting

**Modify file** at `/Users/chris/Projects/shitpost-alpha/shitpost_alpha.py`.

The orchestrator currently calls `python -m shitposts` as a subprocess (line 60). For multi-source support, we need it to iterate over enabled harvesters.

**Add a new function** after `_build_harvesting_cmd` (after line 71):

```python
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
```

**Modify `execute_harvesting_cli`** (lines 102-104) to support multiple sources:

**Before**:

```python
async def execute_harvesting_cli(args) -> bool:
    """Execute the harvesting CLI with appropriate parameters."""
    return await _execute_subprocess(_build_harvesting_cmd(args), "Harvesting", "🚀")
```

**After**:

```python
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
```

**Add `--sources` argument** to the orchestrator's argument parser (after line 166):

```python
parser.add_argument(
    "--sources",
    type=str,
    default=None,
    help="Comma-separated list of harvester sources to run (e.g., truth_social,twitter). Default: all enabled."
)
```

**In `main()`**, parse the sources argument (after line 189):

```python
    # Parse sources list
    if args.sources:
        args.sources = [s.strip() for s in args.sources.split(",")]
    else:
        # Use settings to determine enabled sources
        from shit.config.shitpost_settings import settings as app_settings
        args.sources = app_settings.get_enabled_harvester_names()
```

**Update the dry run output** (around line 207) to show per-source commands:

```python
    if args.dry_run:
        print_info("DRY RUN MODE - No commands will be executed")
        print_info(f"Processing Mode: {args.mode}")
        print_info(f"Sources: {', '.join(args.sources)}")
        print_info(f"Shared Settings: from={args.from_date}, to={args.to_date}, limit={args.limit}")
        print_info(f"\nCommands that would be executed:")
        for i, source in enumerate(args.sources, 1):
            cmd = _build_harvesting_cmd_for_source(args, source)
            print_info(f"  {i}a. Harvesting ({source}): {' '.join(cmd)}")
        print_info(f"  2. S3 to Database: {' '.join(_build_s3_to_db_cmd(args))}")
        print_info(f"  3. LLM Analysis: {' '.join(_build_analysis_cmd(args))}")
        return
```

---

### Step 10: Create Skeleton Twitter Harvester

**Purpose**: Demonstrate the pattern for adding a new source. This is NOT a working implementation -- it is a template with clear `TODO` markers.

**Create file** at `/Users/chris/Projects/shitpost-alpha/shitposts/twitter_harvester.py`:

```python
"""
Twitter/X Signal Harvester (Skeleton)

This is a TEMPLATE for implementing a new signal source.
It demonstrates the SignalHarvester interface pattern.

To make this functional:
    1. Set TWITTER_BEARER_TOKEN in .env
    2. Implement _test_connection() with real Twitter API v2 calls
    3. Implement _fetch_batch() with Twitter search/timeline endpoints
    4. Register in harvester_registry.py with enabled=True
    5. Add "twitter" to ENABLED_HARVESTERS in .env

See TruthSocialS3Harvester for a complete working example.
"""

import aiohttp
from datetime import datetime
from typing import Dict, List, Optional

from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger
from shitposts.base_harvester import SignalHarvester

logger = get_service_logger("twitter_harvester")


class TwitterHarvester(SignalHarvester):
    """Skeleton harvester for Twitter/X posts.
    
    NOT YET FUNCTIONAL. This class demonstrates the SignalHarvester
    interface for future implementation.
    """
    
    def __init__(
        self,
        mode: str = "incremental",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        target_users: Optional[List[str]] = None,
    ):
        super().__init__(mode=mode, start_date=start_date, end_date=end_date, limit=limit)
        
        # Twitter-specific config
        self.bearer_token = settings.TWITTER_BEARER_TOKEN
        self.base_url = "https://api.twitter.com/2"
        self.target_users = target_users or self._parse_target_users()
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _parse_target_users(self) -> List[str]:
        """Parse target users from settings."""
        raw = getattr(settings, 'TWITTER_TARGET_USERS', '')
        return [u.strip() for u in raw.split(",") if u.strip()]
    
    # ── Interface implementation ───────────────────────────────────────
    
    def get_source_name(self) -> str:
        return "twitter"
    
    async def _test_connection(self) -> None:
        """Test Twitter API v2 connection.
        
        TODO: Implement with real Twitter API call.
        """
        if not self.bearer_token:
            raise ValueError(
                "TWITTER_BEARER_TOKEN not configured. "
                "Please add it to your .env file."
            )
        
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
                "User-Agent": "Shitpost-Alpha-Twitter-Harvester/1.0",
            }
        )
        
        # TODO: Make a real test call to Twitter API v2
        # url = f"{self.base_url}/users/me"
        # async with self.session.get(url) as response:
        #     if response.status != 200:
        #         raise Exception(f"Twitter API test failed: {response.status}")
        
        raise NotImplementedError(
            "TwitterHarvester is a skeleton. "
            "Implement _test_connection() with real API calls."
        )
    
    async def _fetch_batch(
        self, cursor: Optional[str] = None
    ) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of tweets.
        
        TODO: Implement with Twitter API v2 search or user timeline.
        
        Twitter API v2 uses pagination_token for cursor-based pagination.
        """
        # TODO: Implement real Twitter API call
        # url = f"{self.base_url}/users/{user_id}/tweets"
        # params = {"max_results": 100, "tweet.fields": "created_at,text,public_metrics"}
        # if cursor:
        #     params["pagination_token"] = cursor
        # async with self.session.get(url, params=params) as response:
        #     data = await response.json()
        #     tweets = data.get("data", [])
        #     next_token = data.get("meta", {}).get("next_token")
        #     return tweets, next_token
        
        raise NotImplementedError(
            "TwitterHarvester is a skeleton. "
            "Implement _fetch_batch() with real API calls."
        )
    
    def _extract_item_id(self, item: Dict) -> str:
        """Extract tweet ID."""
        return item.get("id", "")
    
    def _extract_timestamp(self, item: Dict) -> datetime:
        """Extract tweet creation timestamp.
        
        Twitter API v2 uses ISO 8601 format: 2024-01-15T10:30:00.000Z
        """
        created_at = item.get("created_at", "")
        if created_at.endswith("Z"):
            created_at = created_at.replace("Z", "+00:00")
        return datetime.fromisoformat(created_at).replace(tzinfo=None)
    
    def _extract_content_preview(self, item: Dict) -> str:
        """Extract tweet text preview."""
        text = item.get("text", "")
        if len(text) > 100:
            return text[:100] + "..."
        return text or "No content"
    
    async def cleanup(self) -> None:
        """Cleanup aiohttp session."""
        if self.session:
            await self.session.close()
        await super().cleanup()
```

---

### Step 11: Create `shitposts/__init__.py`

This file does not currently exist (confirmed by glob search). Create it to make the package properly importable.

**Create file** at `/Users/chris/Projects/shitpost-alpha/shitposts/__init__.py`:

```python
"""
Shitposts Package
Signal harvesting from multiple data sources.
"""

from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_registry import HarvesterRegistry, create_default_registry
from shitposts.harvester_models import HarvestResult, HarvestSummary, HarvesterConfig

__all__ = [
    "SignalHarvester",
    "HarvesterRegistry",
    "create_default_registry",
    "HarvestResult",
    "HarvestSummary",
    "HarvesterConfig",
]
```

---

## 4. Test Plan

### New Test Files

#### `shit_tests/shitposts/test_base_harvester.py` (approx. 25-30 tests)

```python
"""
Tests for SignalHarvester abstract base class.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Optional

from shitposts.base_harvester import SignalHarvester
from shitposts.harvester_models import HarvestResult


# Concrete test implementation
class MockHarvester(SignalHarvester):
    """Minimal concrete implementation for testing the base class."""
    
    def __init__(self, items=None, **kwargs):
        super().__init__(**kwargs)
        self._items = items or []
        self._batch_index = 0
        self._connection_tested = False
    
    def get_source_name(self) -> str:
        return "mock_source"
    
    async def _test_connection(self) -> None:
        self._connection_tested = True
    
    async def _fetch_batch(self, cursor=None):
        if self._batch_index >= len(self._items):
            return [], None
        batch = self._items[self._batch_index]
        self._batch_index += 1
        next_cursor = str(self._batch_index) if self._batch_index < len(self._items) else None
        return batch, next_cursor
    
    def _extract_item_id(self, item):
        return item.get("id", "")
    
    def _extract_timestamp(self, item):
        return datetime.fromisoformat(item.get("created_at", "2024-01-01T00:00:00"))
    
    def _extract_content_preview(self, item):
        return item.get("text", "")[:100]


class TestSignalHarvesterInterface:
    """Test that abstract interface is enforced."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            SignalHarvester()  # Missing abstract methods

    def test_concrete_implementation_instantiates(self):
        harvester = MockHarvester()
        assert harvester.get_source_name() == "mock_source"

    def test_default_parameters(self):
        harvester = MockHarvester()
        assert harvester.mode == "incremental"
        assert harvester.start_date is None
        assert harvester.end_date is None
        assert harvester.limit is None

    def test_custom_parameters(self):
        harvester = MockHarvester(
            mode="range",
            start_date="2024-01-01",
            end_date="2024-12-31",
            limit=100
        )
        assert harvester.mode == "range"
        assert harvester.start_datetime == datetime(2024, 1, 1)
        assert harvester.limit == 100

    def test_s3_prefix_default(self):
        harvester = MockHarvester()
        assert harvester._get_s3_prefix() == "mock_source"


class TestSignalHarvesterInitialize:
    """Test the initialize() method."""

    @pytest.mark.asyncio
    async def test_initialize_dry_run(self):
        harvester = MockHarvester()
        await harvester.initialize(dry_run=True)
        assert harvester._connection_tested is True
        assert harvester.s3_data_lake is None

    @pytest.mark.asyncio
    async def test_initialize_creates_s3(self):
        harvester = MockHarvester()
        with patch('shitposts.base_harvester.S3DataLake') as mock_s3_class, \
             patch('shitposts.base_harvester.settings') as mock_settings:
            mock_settings.S3_BUCKET_NAME = "test-bucket"
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "key"
            mock_settings.AWS_SECRET_ACCESS_KEY = "secret"
            mock_s3 = AsyncMock()
            mock_s3_class.return_value = mock_s3
            
            await harvester.initialize(dry_run=False)
            
            assert harvester.s3_data_lake is not None
            mock_s3.initialize.assert_called_once()


class TestSignalHarvesterHarvest:
    """Test the harvest() generator."""

    @pytest.mark.asyncio
    async def test_harvest_yields_results(self):
        items = [[
            {"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Hello"},
            {"id": "002", "created_at": "2024-01-15T11:00:00", "text": "World"},
        ]]
        harvester = MockHarvester(items=items)
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="mock/raw/2024/01/15/001.json")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="mock/raw/2024/01/15/001.json")
        
        results = []
        async for result in harvester.harvest():
            results.append(result)
        
        assert len(results) == 2
        assert isinstance(results[0], HarvestResult)
        assert results[0].source_name == "mock_source"
        assert results[0].source_post_id == "001"

    @pytest.mark.asyncio
    async def test_harvest_respects_limit(self):
        items = [[
            {"id": "001", "created_at": "2024-01-15T10:00:00", "text": "A"},
            {"id": "002", "created_at": "2024-01-15T11:00:00", "text": "B"},
            {"id": "003", "created_at": "2024-01-15T12:00:00", "text": "C"},
        ]]
        harvester = MockHarvester(items=items, limit=2)
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.store_raw_data = AsyncMock(return_value="key")
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")
        
        results = []
        async for result in harvester.harvest():
            results.append(result)
        
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_harvest_dry_run_skips_s3(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Test"}]]
        harvester = MockHarvester(items=items)
        
        results = []
        async for result in harvester.harvest(dry_run=True):
            results.append(result)
        
        assert len(results) == 1
        assert harvester.s3_data_lake is None

    @pytest.mark.asyncio
    async def test_harvest_incremental_stops_on_existing(self):
        items = [[{"id": "001", "created_at": "2024-01-15T10:00:00", "text": "Exists"}]]
        harvester = MockHarvester(items=items, mode="incremental")
        harvester.s3_data_lake = AsyncMock()
        harvester.s3_data_lake.check_object_exists = AsyncMock(return_value=True)
        harvester.s3_data_lake._generate_s3_key = MagicMock(return_value="key")
        
        results = []
        async for result in harvester.harvest():
            results.append(result)
        
        assert len(results) == 0  # Should stop, not yield
```

#### `shit_tests/shitposts/test_harvester_registry.py` (approx. 15-20 tests)

Test cases should cover:
- `register()` with valid and invalid classes
- `unregister()` removes entries
- `list_sources()` and `list_enabled_sources()` correctness
- `create_harvester()` with known and unknown source names
- `create_all_enabled()` returns only enabled harvesters
- `create_default_registry()` includes Truth Social
- `TypeError` when registering a non-`SignalHarvester` class

#### `shit_tests/shitposts/test_twitter_harvester.py` (approx. 5-8 tests)

Test cases for the skeleton:
- Instantiation succeeds with mock settings
- `get_source_name()` returns `"twitter"`
- `_test_connection()` raises `NotImplementedError`
- `_fetch_batch()` raises `NotImplementedError`
- `_extract_item_id()`, `_extract_timestamp()`, `_extract_content_preview()` work with sample tweet dicts
- `cleanup()` closes session

### Updated Test File

#### `shit_tests/shitposts/test_truth_social_s3_harvester.py`

Most existing tests should continue working because `harvest_shitposts()` is kept as a backward-compatible wrapper. The specific changes needed:

1. **`test_initialization_defaults`** (line 64): Must still pass. The `__init__` signature is unchanged.

2. **`test_initialize`** (line 134): The patching changes slightly because `initialize()` now calls `super().initialize()`. The mock path for `S3DataLake` changes from `shitposts.truth_social_s3_harvester.S3DataLake` to `shitposts.base_harvester.S3DataLake`. Update the `patch` target:

   **Before** (line 156):
   ```python
   with patch('aiohttp.ClientSession', ...), \
        patch('shitposts.truth_social_s3_harvester.S3DataLake') as mock_s3_class:
   ```
   
   **After**:
   ```python
   with patch('aiohttp.ClientSession', ...), \
        patch('shitposts.base_harvester.S3DataLake') as mock_s3_class:
   ```

3. **Tests that directly test `_harvest_backfill`**: These methods are removed from `TruthSocialS3Harvester`. Tests like `test_harvest_backfill_success` (line 413), `test_harvest_backfill_with_limit` (line 460), etc. need to be updated to either:
   - Test through `harvest_shitposts()` (which calls `harvest()` from base)
   - Or test `_fetch_batch()` directly for the Truth Social-specific API logic

4. **`test_harvest_shitposts_incremental_mode`** (line 332): Should work as-is since `harvest_shitposts()` still exists.

**Estimated test impact**: ~8-10 tests need patch path updates, ~5 tests that directly tested `_harvest_backfill` need rewriting to test `_fetch_batch` or `harvest()` instead.

---

## 5. Documentation Updates

### `shitposts/README.md`

Create or update this file to document:
- The `SignalHarvester` interface and its abstract methods
- How to add a new source (step-by-step using Twitter skeleton as example)
- The registry pattern and `create_default_registry()`
- S3 path conventions: `{source}/raw/YYYY/MM/DD/{id}.json`
- CLI usage with `--source` flag

### `CHANGELOG.md`

Add under `## [Unreleased]`:

```markdown
### Added
- **Harvester Abstraction Layer** - Multi-source harvesting interface
  - `SignalHarvester` abstract base class with standardized lifecycle
  - `HarvesterRegistry` for config-driven source management
  - Shared data models (`HarvestResult`, `HarvestSummary`, `HarvesterConfig`)
  - Skeleton `TwitterHarvester` as template for future sources
  - `--source` CLI flag and `--sources` orchestrator flag
  - `ENABLED_HARVESTERS` environment variable for source selection

### Changed
- **TruthSocialS3Harvester** now implements `SignalHarvester` interface
  - Backward-compatible: `harvest_shitposts()` still works for existing callers
  - Harvest loop logic moved to shared base class
  - ScrapeCreators-specific code isolated in abstract method implementations
- **Orchestrator** updated to support running multiple harvesters sequentially
```

### `CLAUDE.md`

Add to the "Core Services Reference" section:

```markdown
### Signal Harvesting Architecture (`shitposts/`)

**Base Class**: `SignalHarvester` (abstract)
- `get_source_name()` -> str
- `initialize(dry_run)` -> verify API, init S3
- `harvest(dry_run)` -> yields `HarvestResult`
- `cleanup()` -> release resources

**Implementations**:
- `TruthSocialS3Harvester` - Truth Social via ScrapeCreators API
- `TwitterHarvester` - Twitter/X (skeleton, not yet functional)

**Registry**: `create_default_registry()` returns configured registry.
```

---

## 6. Stress Testing and Edge Cases

### Source-Specific Failure Isolation

**Scenario**: Truth Social API goes down but Twitter API works.
**Expected behavior**: The orchestrator logs the Truth Social failure, continues to harvest from Twitter, and reports partial success.
**Where to test**: `shitpost_alpha.py` `execute_harvesting_cli()` -- the multi-source loop uses `all_success` tracking and continues on failure.

### Mixed S3 Prefix Handling

**Scenario**: Existing S3 data uses `truth-social/raw/...` (hyphenated). New Truth Social data must use the same prefix.
**Solution**: `TruthSocialS3Harvester._get_s3_prefix()` returns `"truth-social"` (not `"truth_social"`). New sources use their own prefix (e.g., `twitter/raw/...`).
**Risk**: If someone changes `get_source_name()` to return `"truth-social"` and removes the `_get_s3_prefix()` override, the S3 keys change and incremental mode breaks (it can't find existing objects).

### Backward Compatibility

**Scenario**: The `main()` function in `truth_social_s3_harvester.py` calls `harvester.harvest_shitposts()`.
**Solution**: `harvest_shitposts()` is a wrapper that delegates to `harvest()` and converts `HarvestResult` back to the legacy dict format.
**Test**: All existing tests that call `harvest_shitposts()` must pass without modification.

### Registry Duplicate Registration

**Scenario**: Someone registers the same source name twice.
**Expected behavior**: The second registration overwrites the first (last-write-wins). This is logged via `logger.info()`.
**Test**: Register "foo" twice with different classes, verify the second class is returned by `get_class("foo")`.

### Empty Batch from API

**Scenario**: `_fetch_batch()` returns `([], None)` on the first call.
**Expected behavior**: `harvest()` exits the while loop immediately, yields zero results.
**Test**: Create `MockHarvester(items=[])` and verify zero yields.

### Concurrent Harvester Initialization Failures

**Scenario**: `_test_connection()` raises for one source during `initialize()`.
**Expected behavior**: The exception propagates to the caller. The orchestrator catches it and skips that source.
**Where it matters**: The orchestrator runs sources sequentially (not concurrently), so one failure does not affect others.

---

## 7. Verification Checklist

Before merging this PR, verify all of the following:

- [ ] `SignalHarvester` cannot be instantiated directly (abstract class enforcement)
- [ ] `TruthSocialS3Harvester` passes all existing tests without functional changes
- [ ] `harvest_shitposts()` backward-compatible method yields the same dict structure as before
- [ ] S3 keys for Truth Social data remain `truth-social/raw/YYYY/MM/DD/{id}.json` (no path change)
- [ ] `create_default_registry()` includes Truth Social and returns it from `list_enabled_sources()`
- [ ] The orchestrator `--dry-run` shows per-source commands
- [ ] `TwitterHarvester._test_connection()` raises `NotImplementedError`
- [ ] `TwitterHarvester._fetch_batch()` raises `NotImplementedError`
- [ ] No new settings are required to run the system (all new settings have defaults)
- [ ] `python -m shitposts --mode incremental --dry-run` still works
- [ ] `python shitpost_alpha.py --dry-run` shows the correct commands
- [ ] All new code has type hints on function signatures
- [ ] All new public functions have Google-style docstrings
- [ ] `ruff check .` passes with no new errors
- [ ] `ruff format .` produces no changes
- [ ] Test count increases by at least 45 new tests
- [ ] CHANGELOG.md is updated
- [ ] No imports of `truth_social_s3_harvester` from the base class (would cause circular imports)

---

## 8. What NOT To Do

1. **Do NOT change the S3 path for existing Truth Social data.** The current path is `truth-social/raw/YYYY/MM/DD/{id}.json`. The `_get_s3_prefix()` override in `TruthSocialS3Harvester` MUST return `"truth-social"` (hyphenated), not `"truth_social"` (underscored). Changing this breaks incremental mode because it cannot find existing S3 objects.

2. **Do NOT remove `harvest_shitposts()` from `TruthSocialS3Harvester`.** The `main()` function at line 434 calls it. The existing CLI and tests depend on it. Keep it as a backward-compatible wrapper.

3. **Do NOT make the Twitter harvester functional.** It is a skeleton only. It must raise `NotImplementedError` in `_test_connection()` and `_fetch_batch()`. A working Twitter integration is a separate future PR.

4. **Do NOT run harvesters in parallel (concurrently).** The orchestrator runs them sequentially. Parallel execution introduces race conditions in S3 writes, rate limit contention, and makes error reporting confusing. Keep it sequential.

5. **Do NOT change the database schema.** Phase 06 is about the harvester layer only. The `TruthSocialShitpost` model, `platform` column, and all database tables remain unchanged. Database schema changes belong in Phase 02.

6. **Do NOT add the `--source` flag to the `main()` function yet.** The `main()` in `truth_social_s3_harvester.py` is the Truth Social-specific CLI. Multi-source routing belongs in the orchestrator. The CLI flag is added to the parser for forward compatibility but does not change behavior yet.

7. **Do NOT register disabled harvesters in `create_default_registry()` with `enabled=True`.** Only Truth Social should be enabled by default. Future sources should be registered with `enabled=False` until they are implemented.

8. **Do NOT import `TruthSocialS3Harvester` at the top of `harvester_registry.py`.** Use lazy imports inside `create_default_registry()` to avoid circular import chains (`registry -> harvester -> base -> registry`).

9. **Do NOT modify `shit/s3/s3_data_lake.py`.** The `S3DataLake` class is shared infrastructure. It works with whatever `S3Config.prefix` is passed to it. No changes needed.

10. **Do NOT modify `shitvault/s3_processor.py`.** The S3-to-database processor reads from S3 using the data lake. It does not need to know about multiple sources yet. That is Phase 02's concern (making the DB schema source-agnostic).

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitposts/base_harvester.py` - Core abstract base class to create (the heart of this phase)
- `/Users/chris/Projects/shitpost-alpha/shitposts/truth_social_s3_harvester.py` - Must refactor to implement SignalHarvester interface while keeping backward compatibility
- `/Users/chris/Projects/shitpost-alpha/shitposts/harvester_registry.py` - Registry pattern to create for dynamic source management
- `/Users/chris/Projects/shitpost-alpha/shitpost_alpha.py` - Orchestrator to update for multi-source harvesting loop
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitposts/test_truth_social_s3_harvester.py` - Existing tests to update (patch paths change from direct to base class)