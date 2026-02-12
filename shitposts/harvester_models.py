"""
Harvester Data Models
Shared data structures for all signal harvesters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any


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
