# Phase 02: Source-Agnostic Data Model

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat: introduce source-agnostic Signal model for multi-platform support` |
| **Risk Level** | Medium |
| **Estimated Effort** | High (3-5 days) |
| **Files Created** | `shitvault/signal_models.py`, `shitvault/signal_operations.py`, `shit/db/signal_utils.py`, `shit_tests/shitvault/test_signal_models.py`, `shit_tests/shitvault/test_signal_operations.py`, `shit_tests/shit/db/test_signal_utils.py` |
| **Files Modified** | `shitvault/shitpost_models.py`, `shitvault/shitpost_operations.py`, `shitvault/prediction_operations.py`, `shitvault/s3_processor.py`, `shitvault/statistics.py`, `shit/db/database_utils.py`, `shit/s3/s3_data_lake.py`, `shit/s3/s3_config.py`, `shit/s3/s3_models.py`, `shit/content/bypass_service.py`, `shitpost_ai/shitpost_analyzer.py`, `shitty_ui/data.py`, `notifications/db.py`, `notifications/alert_engine.py`, `shit/db/sync_session.py`, `CHANGELOG.md`, `CLAUDE.md` |
| **Files Deleted** | None |

---

## Context: Why This Matters

The current data model is deeply coupled to Truth Social's API structure. Every layer -- from S3 storage to database models to the analyzer to the dashboard -- uses Truth Social-specific terminology: `reblogs_count`, `upvotes_count`, `account_verified`, `reblog` (for retweets). This coupling means:

1. **Adding a new source (Twitter/X, RSS, etc.) requires touching 15+ files** rather than just writing a new adapter.
2. **The `TruthSocialShitpost` table has 40+ columns**, most of which are platform-specific metadata that should be stored as a JSON blob.
3. **Field mapping in `database_utils.py` and `shitpost_operations.py`** manually maps 40+ fields from the Truth Social API, a pattern that does not scale.
4. **The `predictions` table has a foreign key to `truth_social_shitposts.shitpost_id`**, making it impossible to create predictions for signals from other sources.
5. **S3 paths are hardcoded** to `truth-social/raw/YYYY/MM/DD/`.

A source-agnostic `Signal` model decouples the content layer from any specific platform, enabling the multi-source vision described in the project roadmap.

### ScrapeCreators Cost Removal

The ScrapeCreators API that powers Truth Social harvesting charges per request. A generic model allows the system to ingest from free or cheaper sources (RSS feeds, public APIs) with zero code changes to the analysis and prediction layers.

---

## Dependencies

### Phase 01: Ticker Registry (MUST complete first)
Phase 01 introduces a canonical asset registry. The `Signal` model's `assets` field in predictions should reference tickers from that registry.

### Phases That Depend on This
- **Phase 03: Signal-Over-Trend Dashboard View** -- Queries may reference signal table fields.
- **Phase 06: Harvester Abstraction Layer** -- Requires the generic `Signal` model as the ingestion target.

---

## Detailed Implementation Plan

### Step 1: Create the Signal SQLAlchemy Model

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/signal_models.py` (NEW)

This model captures the universal fields every signal source must provide, plus a JSON column for platform-specific data. The table is named `signals` (not `shitposts`) to be source-neutral.

```python
"""
Source-Agnostic Signal Model
SQLAlchemy model for signals from ANY social media or news source.
Platform-specific data is stored in a JSON blob.
"""

from typing import Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from shit.db.data_models import Base, TimestampMixin, IDMixin, model_to_dict


class Signal(Base, IDMixin, TimestampMixin):
    """
    Source-agnostic signal model.

    Represents a content signal from ANY platform (Truth Social, Twitter/X,
    RSS, news feeds, etc.). Platform-specific fields are stored in the
    `platform_data` JSON column.

    Universal fields capture the data every downstream consumer needs:
    text, author, timestamp, source, and normalized engagement metrics.
    """

    __tablename__ = "signals"

    # --- Universal Identifiers ---
    signal_id = Column(String(255), unique=True, index=True, nullable=False)
    source = Column(String(50), nullable=False, index=True)
    source_url = Column(String(1000), nullable=True)

    # --- Universal Content ---
    text = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    language = Column(String(10), nullable=True)

    # --- Universal Author ---
    author_id = Column(String(255), nullable=True)
    author_username = Column(String(200), nullable=False)
    author_display_name = Column(String(200), nullable=True)
    author_verified = Column(Boolean, default=False)
    author_followers = Column(Integer, default=0)

    # --- Universal Timestamps ---
    published_at = Column(DateTime, nullable=False, index=True)

    # --- Normalized Engagement (source-agnostic names) ---
    likes_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    replies_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)

    # --- Content Flags ---
    has_media = Column(Boolean, default=False)
    is_repost = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)
    is_quote = Column(Boolean, default=False)

    # --- Platform-Specific Data (JSON blob) ---
    platform_data = Column(JSON, default=dict)
    # Example for Truth Social:
    # {
    #     "upvotes_count": 250,
    #     "downvotes_count": 25,
    #     "visibility": "public",
    #     "sensitive": false,
    #     "media_attachments": [...],
    #     "mentions": [...],
    #     "tags": [...],
    #     "reblog": {...}
    # }

    # --- Raw API Response ---
    raw_api_data = Column(JSON, nullable=True)

    # --- Relationships ---
    predictions = relationship(
        "Prediction", back_populates="signal", foreign_keys="Prediction.signal_id"
    )

    # --- Indexes ---
    __table_args__ = (
        Index("ix_signals_source_published", "source", "published_at"),
        Index("ix_signals_author", "author_username"),
    )

    def __repr__(self):
        text_preview = (self.text or "")[:50]
        return f"<Signal(id={self.id}, source='{self.source}', author='{self.author_username}', text='{text_preview}...')>"

    @property
    def total_engagement(self) -> int:
        """Sum of all engagement metrics."""
        return (self.likes_count or 0) + (self.shares_count or 0) + (self.replies_count or 0)

    @property
    def engagement_rate(self) -> float:
        """Engagement rate relative to author followers."""
        if not self.author_followers or self.author_followers == 0:
            return 0.0
        return self.total_engagement / self.author_followers


def signal_to_dict(signal: Signal) -> Dict[str, Any]:
    """Convert Signal to dictionary."""
    return model_to_dict(signal)
```

**Rationale for field choices**:
- `signal_id` replaces `shitpost_id` -- universally identifies content from any platform.
- `source` replaces the hardcoded `platform = "truth_social"` -- an indexed column for filtering.
- `likes_count` normalizes `favourites_count` (Truth Social) and `likes` (Twitter) into one column.
- `shares_count` normalizes `reblogs_count` (Truth Social) and `retweets` (Twitter).
- `is_repost` replaces checking `reblog IS NOT NULL` -- a boolean flag that works across platforms.
- `platform_data` JSON column holds all 30+ Truth Social-specific fields that do not need their own columns.
- `published_at` replaces `timestamp` for clarity.

---

### Step 2: Update the Prediction Model to Support Both Tables

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_models.py`

The `Prediction` model currently has a foreign key to `truth_social_shitposts.shitpost_id`. During the transition, it needs to support both the legacy table and the new `signals` table via a **dual-FK** strategy.

**Changes to lines 107-108:**

```python
# BEFORE:
shitpost_id = Column(
    String(255), ForeignKey("truth_social_shitposts.shitpost_id"), nullable=False
)

# AFTER:
# Legacy FK -- nullable now, will be removed after full migration
shitpost_id = Column(
    String(255), ForeignKey("truth_social_shitposts.shitpost_id"), nullable=True
)
# New FK -- points to the source-agnostic signals table
signal_id = Column(
    String(255), ForeignKey("signals.signal_id"), nullable=True
)
```

Add a new relationship (after line 155):

```python
signal = relationship("Signal", back_populates="predictions", foreign_keys=[signal_id])
```

Add a property for backward compatibility:

```python
@property
def content_id(self) -> str:
    """Return the signal or shitpost ID, whichever is set."""
    return self.signal_id or self.shitpost_id
```

**Important constraint**: At least one of `shitpost_id` or `signal_id` must be non-null. This is enforced at the application layer.

---

### Step 3: Create the Truth Social Source Adapter (Field Mapping)

**File**: `/Users/chris/Projects/shitpost-alpha/shit/db/signal_utils.py` (NEW)

This module provides a pluggable transformer framework. Each source gets a `transform_*_to_signal()` function.

```python
"""
Signal Transformation Utilities
Transforms raw API data from any source into the generic Signal format.
"""

import logging
from typing import Dict, Any

from shit.db.database_utils import DatabaseUtils
from shit.logging.service_loggers import DatabaseLogger

db_logger = DatabaseLogger("signal_utils")
logger = db_logger.logger


class SignalTransformer:
    """Transforms raw API data from various sources into Signal format."""

    @staticmethod
    def transform_truth_social(s3_data: Dict) -> Dict[str, Any]:
        """
        Transform Truth Social S3 data into Signal format.

        Maps Truth Social API fields to universal Signal fields.
        Platform-specific fields are stored in platform_data JSON.

        Args:
            s3_data: Raw S3 storage data (contains raw_api_data key)

        Returns:
            Dictionary matching Signal model fields
        """
        raw_api_data = s3_data.get("raw_api_data", {})
        account_data = raw_api_data.get("account", {})

        # Determine content flags
        reblog_data = raw_api_data.get("reblog")
        is_repost = reblog_data is not None
        is_reply = raw_api_data.get("in_reply_to_id") is not None
        is_quote = raw_api_data.get("quote_id") is not None

        # Build platform_data with all Truth Social-specific fields
        platform_data = {
            "upvotes_count": raw_api_data.get("upvotes_count", 0),
            "downvotes_count": raw_api_data.get("downvotes_count", 0),
            "account_following_count": account_data.get("following_count", 0),
            "account_statuses_count": account_data.get("statuses_count", 0),
            "account_website": account_data.get("website", ""),
            "visibility": raw_api_data.get("visibility", "public"),
            "sensitive": raw_api_data.get("sensitive", False),
            "spoiler_text": raw_api_data.get("spoiler_text", ""),
            "uri": raw_api_data.get("uri", ""),
            "card": raw_api_data.get("card"),
            "group": raw_api_data.get("group"),
            "quote": raw_api_data.get("quote"),
            "in_reply_to": raw_api_data.get("in_reply_to"),
            "reblog": raw_api_data.get("reblog"),
            "sponsored": raw_api_data.get("sponsored", False),
            "reaction": raw_api_data.get("reaction"),
            "favourited": raw_api_data.get("favourited", False),
            "reblogged": raw_api_data.get("reblogged", False),
            "muted": raw_api_data.get("muted", False),
            "pinned": raw_api_data.get("pinned", False),
            "bookmarked": raw_api_data.get("bookmarked", False),
            "poll": raw_api_data.get("poll"),
            "emojis": raw_api_data.get("emojis", []),
            "votable": raw_api_data.get("votable", False),
            "editable": raw_api_data.get("editable", False),
            "version": raw_api_data.get("version", ""),
            "media_attachments": raw_api_data.get("media_attachments", []),
            "mentions": raw_api_data.get("mentions", []),
            "tags": raw_api_data.get("tags", []),
            "in_reply_to_id": raw_api_data.get("in_reply_to_id"),
            "quote_id": raw_api_data.get("quote_id"),
            "in_reply_to_account_id": raw_api_data.get("in_reply_to_account_id"),
            "edited_at": raw_api_data.get("edited_at"),
        }

        return {
            # Universal identifiers
            "signal_id": str(raw_api_data.get("id")),
            "source": "truth_social",
            "source_url": raw_api_data.get("url", ""),
            # Universal content
            "text": raw_api_data.get("text", ""),
            "content_html": raw_api_data.get("content", ""),
            "title": raw_api_data.get("title", ""),
            "language": raw_api_data.get("language", ""),
            # Universal author
            "author_id": str(account_data.get("id", "")),
            "author_username": account_data.get("username", ""),
            "author_display_name": account_data.get("display_name", ""),
            "author_verified": account_data.get("verified", False),
            "author_followers": account_data.get("followers_count", 0),
            # Universal timestamp
            "published_at": DatabaseUtils.parse_timestamp(raw_api_data.get("created_at", "")),
            # Normalized engagement
            "likes_count": raw_api_data.get("favourites_count", 0),
            "shares_count": raw_api_data.get("reblogs_count", 0),
            "replies_count": raw_api_data.get("replies_count", 0),
            "views_count": 0,  # Truth Social does not expose views
            # Content flags
            "has_media": len(raw_api_data.get("media_attachments", [])) > 0,
            "is_repost": is_repost,
            "is_reply": is_reply,
            "is_quote": is_quote,
            # Platform-specific data
            "platform_data": platform_data,
            "raw_api_data": raw_api_data,
        }

    @staticmethod
    def get_transformer(source: str):
        """
        Get the appropriate transformer function for a given source.

        Args:
            source: Source platform name ("truth_social", "twitter", "rss", etc.)

        Returns:
            Transformer function

        Raises:
            ValueError: If source is not supported
        """
        transformers = {
            "truth_social": SignalTransformer.transform_truth_social,
            # Future sources:
            # "twitter": SignalTransformer.transform_twitter,
            # "rss": SignalTransformer.transform_rss,
        }

        transformer = transformers.get(source)
        if transformer is None:
            raise ValueError(
                f"Unsupported source: {source}. "
                f"Supported sources: {list(transformers.keys())}"
            )
        return transformer
```

---

### Step 4: Create Signal Operations

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/signal_operations.py` (NEW)

This replaces `shitpost_operations.py` as the primary operations class. The API is similar but uses generic field names. **Key design decision**: The `get_unprocessed_signals` method returns dictionaries that include backward-compatible aliases (`shitpost_id`, `timestamp`, `username`, `reblogs_count`, etc.). This means the `ShitpostAnalyzer`, `PredictionOperations`, and `BypassService` can consume this data with ZERO changes initially.

```python
"""
Signal Operations
Source-agnostic operations for managing signals from any platform.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import select, and_, not_, exists
from sqlalchemy.exc import IntegrityError

from shit.db.database_operations import DatabaseOperations
from shitvault.signal_models import Signal
from shitvault.shitpost_models import Prediction

from shit.logging.service_loggers import DatabaseLogger

db_logger = DatabaseLogger("signal_operations")
logger = db_logger.logger


class SignalOperations:
    """CRUD operations for source-agnostic signals."""

    def __init__(self, db_ops: DatabaseOperations):
        self.db_ops = db_ops

    async def store_signal(self, signal_data: Dict[str, Any]) -> Optional[str]:
        """Store a signal in the database.

        Args:
            signal_data: Dictionary matching Signal model fields.

        Returns:
            String ID of stored signal, or None on integrity error.
        """
        try:
            signal_id = signal_data.get("signal_id")

            existing = await self.db_ops.read_one(Signal, {"signal_id": signal_id})
            if existing:
                logger.debug(f"Signal {signal_id} already exists, skipping")
                return str(existing.id)

            signal = Signal(**signal_data)
            self.db_ops.session.add(signal)
            await self.db_ops.session.commit()
            await self.db_ops.session.refresh(signal)

            logger.info(
                f"Stored signal {signal.signal_id} (source={signal.source}) with ID: {signal.id}"
            )
            return str(signal.id)

        except IntegrityError as e:
            await self.db_ops.session.rollback()
            logger.warning(f"Integrity error storing signal {signal_data.get('signal_id')}: {e}")
            return None
        except Exception as e:
            await self.db_ops.session.rollback()
            logger.error(f"Error storing signal {signal_data.get('signal_id')}: {e}")
            raise

    async def get_unprocessed_signals(
        self, launch_date: str, limit: int = 10, source: Optional[str] = None
    ) -> List[Dict]:
        """
        Get signals that need LLM analysis.

        Criteria:
        1. Signal published_at is after launch date
        2. No existing prediction for this signal
        3. Optionally filtered by source

        Args:
            launch_date: ISO date string for minimum timestamp
            limit: Maximum signals to return
            source: Optional source filter

        Returns:
            List of signal dictionaries (includes backward-compatible aliases)
        """
        try:
            launch_datetime = datetime.fromisoformat(launch_date.replace("Z", "+00:00"))

            prediction_exists = select(Prediction.id).where(
                Prediction.signal_id == Signal.signal_id
            )

            conditions = [
                Signal.published_at >= launch_datetime,
                not_(exists(prediction_exists)),
            ]

            if source:
                conditions.append(Signal.source == source)

            stmt = (
                select(Signal)
                .where(and_(*conditions))
                .order_by(Signal.published_at.desc())
                .limit(limit)
            )

            result = await self.db_ops.session.execute(stmt)
            signals = result.scalars().all()

            signal_dicts = []
            for sig in signals:
                signal_dict = {
                    # Universal fields
                    "id": sig.id,
                    "signal_id": sig.signal_id,
                    "source": sig.source,
                    "source_url": sig.source_url,
                    "text": sig.text,
                    "content_html": sig.content_html,
                    "title": sig.title,
                    "language": sig.language,
                    "author_id": sig.author_id,
                    "author_username": sig.author_username,
                    "author_display_name": sig.author_display_name,
                    "author_verified": sig.author_verified,
                    "author_followers": sig.author_followers,
                    "published_at": sig.published_at,
                    "likes_count": sig.likes_count,
                    "shares_count": sig.shares_count,
                    "replies_count": sig.replies_count,
                    "views_count": sig.views_count,
                    "has_media": sig.has_media,
                    "is_repost": sig.is_repost,
                    "is_reply": sig.is_reply,
                    "is_quote": sig.is_quote,
                    "platform_data": sig.platform_data,
                    "raw_api_data": sig.raw_api_data,
                    "created_at": sig.created_at,
                    "updated_at": sig.updated_at,
                    # Backward-compatible aliases (for analyzer, bypass service, etc.)
                    "shitpost_id": sig.signal_id,
                    "timestamp": sig.published_at,
                    "username": sig.author_username,
                    "platform": sig.source,
                    "content": sig.content_html,
                    "reblog": sig.platform_data.get("reblog") if sig.platform_data else None,
                    "mentions": sig.platform_data.get("mentions", []) if sig.platform_data else [],
                    "tags": sig.platform_data.get("tags", []) if sig.platform_data else [],
                    "reblogs_count": sig.shares_count,
                    "favourites_count": sig.likes_count,
                    "upvotes_count": (
                        sig.platform_data.get("upvotes_count", 0) if sig.platform_data else 0
                    ),
                    "downvotes_count": (
                        sig.platform_data.get("downvotes_count", 0) if sig.platform_data else 0
                    ),
                    "account_verified": sig.author_verified,
                    "account_followers_count": sig.author_followers,
                    "account_display_name": sig.author_display_name,
                }
                signal_dicts.append(signal_dict)

            logger.info(f"Retrieved {len(signal_dicts)} unprocessed signals")
            return signal_dicts

        except Exception as e:
            logger.error(f"Error retrieving unprocessed signals: {e}")
            raise
```

---

### Step 5: Update the S3 Processor (Dual-Write Strategy)

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/s3_processor.py`

The S3 processor needs to accept a `source` parameter and use `SignalTransformer`. During the transition, it **dual-writes** to both `signals` and `truth_social_shitposts`.

**Changes at line 14** (add imports):
```python
from shitvault.signal_operations import SignalOperations
from shit.db.signal_utils import SignalTransformer
```

**Changes at line 27-30** (constructor):
```python
# BEFORE:
def __init__(self, db_ops: DatabaseOperations, s3_data_lake: S3DataLake):
    self.db_ops = db_ops
    self.s3_data_lake = s3_data_lake
    self.shitpost_ops = ShitpostOperations(db_ops)

# AFTER:
def __init__(self, db_ops: DatabaseOperations, s3_data_lake: S3DataLake, source: str = "truth_social"):
    self.db_ops = db_ops
    self.s3_data_lake = s3_data_lake
    self.source = source
    self.signal_ops = SignalOperations(db_ops)
    self.shitpost_ops = ShitpostOperations(db_ops)  # Keep for backward compat
    self._transformer = SignalTransformer.get_transformer(source)
```

**Changes at lines 174-200** (`_process_single_s3_data`):
```python
# BEFORE:
async def _process_single_s3_data(self, s3_data: Dict, stats: Dict, dry_run: bool):
    try:
        if dry_run:
            stats['successful'] += 1
        else:
            transformed_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
            result = await self.shitpost_ops.store_shitpost(transformed_data)
            ...

# AFTER:
async def _process_single_s3_data(self, s3_data: Dict, stats: Dict, dry_run: bool):
    try:
        if dry_run:
            stats['successful'] += 1
        else:
            # Transform using source-specific transformer
            signal_data = self._transformer(s3_data)
            result = await self.signal_ops.store_signal(signal_data)

            # Also store in legacy table for backward compatibility
            # TODO: Remove after full migration is complete
            legacy_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
            await self.shitpost_ops.store_shitpost(legacy_data)

            if result:
                stats['successful'] += 1
            else:
                stats['skipped'] += 1
    except Exception as e:
        logger.error(f"Error processing S3 data: {e}")
        stats['failed'] += 1
```

**Dual-write strategy**: During the transition period, every new signal is written to BOTH `signals` and `truth_social_shitposts`. This ensures zero downtime -- the dashboard, alert engine, and outcome calculator continue to work against the legacy table while consumers are migrated one at a time.

---

### Step 6: Update the Prediction Operations

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/prediction_operations.py`

**Changes at line 31** (method signature):
```python
# BEFORE:
async def store_analysis(self, shitpost_id: str, analysis_data: Dict[str, Any], shitpost_data: Dict[str, Any] = None) -> Optional[str]:

# AFTER:
async def store_analysis(self, content_id: str, analysis_data: Dict[str, Any], content_data: Dict[str, Any] = None, *, use_signal: bool = False) -> Optional[str]:
```

**Changes at lines 36-50** (engagement score calculation -- use generic names with fallback):
```python
# Use generic field names (backward-compatible aliases present in both dicts)
replies = content_data.get('replies_count', 0)
shares = content_data.get('shares_count', content_data.get('reblogs_count', 0))
likes = content_data.get('likes_count', content_data.get('favourites_count', 0))
followers = content_data.get('author_followers', content_data.get('account_followers_count', 0))
```

**Changes at lines 52-85** (Prediction creation):
```python
prediction = Prediction(
    # Dual-FK: set whichever is appropriate
    shitpost_id=content_id if not use_signal else None,
    signal_id=content_id if use_signal else None,
    ...
)
```

The same pattern is applied to `handle_no_text_prediction`.

---

### Step 7: Update the Bypass Service

**File**: `/Users/chris/Projects/shitpost-alpha/shit/content/bypass_service.py`

**Changes at lines 131-143** (`_is_retruth` method):
```python
# BEFORE:
def _is_retruth(self, post_data: Dict[str, Any]) -> bool:
    reblog_data = post_data.get('reblog')
    if reblog_data is not None:
        return True
    text_content = post_data.get('text', '').strip()
    if text_content.startswith('RT ') or text_content.startswith('RT:'):
        return True
    return False

# AFTER:
def _is_retruth(self, post_data: Dict[str, Any]) -> bool:
    # Check source-agnostic flag first (Signal model)
    if post_data.get('is_repost', False):
        return True

    # Legacy: check reblog field (Truth Social API)
    reblog_data = post_data.get('reblog')
    if reblog_data is not None:
        return True

    # Fallback: check text prefix (works for any platform)
    text_content = post_data.get('text', '').strip()
    if text_content.startswith('RT ') or text_content.startswith('RT:'):
        return True

    return False
```

---

### Step 8: Update the Analyzer

**File**: `/Users/chris/Projects/shitpost-alpha/shitpost_ai/shitpost_analyzer.py`

**Changes at lines 13-14** (imports):
```python
from shitvault.signal_operations import SignalOperations
```

**Changes at lines 76-77** (in `initialize`):
```python
self.signal_ops = SignalOperations(self.db_client)
```

**Changes at line 400** (`_prepare_enhanced_content` -- use fallback pattern for both old and new field names):
```python
def _prepare_enhanced_content(self, signal_data: Dict) -> str:
    content = signal_data.get('text', '')
    username = signal_data.get('author_username', signal_data.get('username', ''))
    timestamp = signal_data.get('published_at', signal_data.get('timestamp', ''))
    source = signal_data.get('source', signal_data.get('platform', 'unknown'))

    replies = signal_data.get('replies_count', 0)
    shares = signal_data.get('shares_count', signal_data.get('reblogs_count', 0))
    likes = signal_data.get('likes_count', signal_data.get('favourites_count', 0))

    verified = signal_data.get('author_verified', signal_data.get('account_verified', False))
    followers = signal_data.get('author_followers', signal_data.get('account_followers_count', 0))

    has_media = signal_data.get('has_media', False)
    mentions = signal_data.get('mentions', [])
    mentions_count = len(mentions) if isinstance(mentions, list) else 0
    tags = signal_data.get('tags', [])
    tags_count = len(tags) if isinstance(tags, list) else 0

    enhanced_content = f"Content: {content}\n"
    enhanced_content += f"Source: {source}\n"
    enhanced_content += f"Author: {username} (Verified: {verified}, Followers: {followers:,})\n"
    enhanced_content += f"Timestamp: {timestamp}\n"
    enhanced_content += f"Engagement: {replies} replies, {shares} shares, {likes} likes\n"
    enhanced_content += f"Media: {'Yes' if has_media else 'No'}, Mentions: {mentions_count}, Tags: {tags_count}"

    return enhanced_content
```

---

### Step 9: Update Dashboard Data Queries (Configurable Table Reference)

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

Rather than updating all 20+ raw SQL queries immediately, add a configurable table reference that makes the cutover a single-line edit later:

At the top of `data.py`, add:
```python
# Table reference -- will be changed to "signals" after full migration
SIGNALS_TABLE = "truth_social_shitposts"
```

Then update `FROM truth_social_shitposts tss` references to use `FROM {SIGNALS_TABLE} tss` via f-strings.

---

### Step 10: Update S3 Config for Source-Agnostic Paths

**File**: `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_config.py`

The default prefix `"truth-social"` is already a parameter. No code change needed. A new source would pass `prefix="twitter"` or `prefix="rss"`.

**File**: `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_data_lake.py`

**Changes at lines 93-103** (store_raw_data metadata):
```python
# BEFORE:
metadata={
    'stored_at': datetime.now().isoformat(),
    'source': 'truth_social_api',
    'version': '1.0',
    'harvester': 'truth_social_s3_harvester'
}

# AFTER:
metadata={
    'stored_at': datetime.now().isoformat(),
    'source': self.config.prefix,  # Dynamic based on config
    'version': '1.0',
    'harvester': f'{self.config.prefix}_harvester'
}
```

---

### Step 11: Update sync_session.py

**File**: `/Users/chris/Projects/shitpost-alpha/shit/db/sync_session.py`

**Changes at lines 72-78** (import the new model):
```python
from shitvault.signal_models import Signal
```

---

### Step 12: Data Migration Plan

The migration is performed as a one-time backfill script, NOT an Alembic migration (the project does not use Alembic).

**Migration script** -- add to `shitvault/cli.py` as a new subcommand `migrate-to-signals`:

```python
async def migrate_to_signals(limit: int = None, dry_run: bool = False):
    """Backfill the signals table from truth_social_shitposts."""
    from shitvault.signal_models import Signal
    from shitvault.shitpost_models import TruthSocialShitpost

    stmt = select(TruthSocialShitpost).where(
        not_(exists(
            select(Signal.id).where(Signal.signal_id == TruthSocialShitpost.shitpost_id)
        ))
    ).order_by(TruthSocialShitpost.timestamp.asc())

    if limit:
        stmt = stmt.limit(limit)

    result = await db_ops.session.execute(stmt)
    shitposts = result.scalars().all()

    migrated = 0
    for sp in shitposts:
        signal = Signal(
            signal_id=sp.shitpost_id,
            source="truth_social",
            source_url=sp.url,
            text=sp.text,
            content_html=sp.content,
            title=sp.title,
            language=sp.language,
            author_id=sp.account_id,
            author_username=sp.username,
            author_display_name=sp.account_display_name,
            author_verified=sp.account_verified or False,
            author_followers=sp.account_followers_count or 0,
            published_at=sp.timestamp,
            likes_count=sp.favourites_count or 0,
            shares_count=sp.reblogs_count or 0,
            replies_count=sp.replies_count or 0,
            views_count=0,
            has_media=sp.has_media or False,
            is_repost=sp.reblog is not None,
            is_reply=getattr(sp, 'in_reply_to_id', None) is not None,
            is_quote=getattr(sp, 'quote_id', None) is not None,
            platform_data={
                "upvotes_count": sp.upvotes_count or 0,
                "downvotes_count": sp.downvotes_count or 0,
                "visibility": sp.visibility,
                "sensitive": sp.sensitive,
                "spoiler_text": sp.spoiler_text,
                "uri": sp.uri,
                "mentions": sp.mentions,
                "tags": sp.tags,
                "media_attachments": sp.media_attachments,
                "card": sp.card,
                "reblog": sp.reblog,
                "poll": sp.poll,
                "emojis": sp.emojis,
            },
            raw_api_data=sp.raw_api_data,
            created_at=sp.created_at,
            updated_at=sp.updated_at,
        )
        if not dry_run:
            db_ops.session.add(signal)
        migrated += 1

    if not dry_run:
        await db_ops.session.commit()

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrated {migrated} shitposts to signals")
```

**Also backfill Prediction.signal_id** for existing predictions:

```sql
UPDATE predictions p
SET signal_id = p.shitpost_id
WHERE p.shitpost_id IS NOT NULL
  AND p.signal_id IS NULL
  AND EXISTS (SELECT 1 FROM signals s WHERE s.signal_id = p.shitpost_id);
```

---

### Step 13: Deprecate ShitpostOperations

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_operations.py`

The existing `ShitpostOperations` class is NOT deleted. A deprecation notice is added:

**Add at line 23:**
```python
import warnings

_DEPRECATION_MSG = (
    "ShitpostOperations is deprecated. Use SignalOperations for new code. "
    "ShitpostOperations will be removed once all consumers are migrated."
)
```

**Add at line 26** (in `__init__`):
```python
def __init__(self, db_ops: DatabaseOperations):
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    self.db_ops = db_ops
```

---

## Test Plan

### New Test Files

**`shit_tests/shitvault/test_signal_models.py`** (~10 tests):
- `test_signal_creation_minimal`
- `test_signal_creation_all_fields`
- `test_signal_default_values`
- `test_signal_to_dict`
- `test_signal_total_engagement`
- `test_signal_engagement_rate`
- `test_signal_engagement_rate_zero_followers`
- `test_signal_repr`
- `test_signal_table_name`
- `test_signal_platform_data_json`

**`shit_tests/shitvault/test_signal_operations.py`** (~8 tests):
- `test_store_signal_success`
- `test_store_signal_duplicate`
- `test_store_signal_integrity_error`
- `test_get_unprocessed_signals_basic`
- `test_get_unprocessed_signals_filters_by_date`
- `test_get_unprocessed_signals_filters_by_source`
- `test_get_unprocessed_signals_excludes_predicted`
- `test_get_unprocessed_signals_backward_compat_aliases`

**`shit_tests/shit/db/test_signal_utils.py`** (~10 tests):
- `test_transform_truth_social_basic`
- `test_transform_truth_social_full`
- `test_transform_truth_social_repost`
- `test_transform_truth_social_reply`
- `test_transform_truth_social_quote`
- `test_transform_truth_social_platform_data`
- `test_transform_truth_social_engagement_mapping`
- `test_get_transformer_valid_source`
- `test_get_transformer_invalid_source`
- `test_transform_truth_social_null_fields`

### Existing Tests to Update

| Test File | Changes Needed |
|---|---|
| `test_shitpost_models.py` | Add tests for `Prediction.signal_id`, `Prediction.content_id` |
| `test_shitpost_operations.py` | Verify deprecation warning; tests still pass |
| `test_prediction_operations.py` | Add tests for `use_signal=True` path |
| `test_s3_processor.py` | Test dual-write behavior; test `source` parameter |

**Total new tests: ~28**

---

## Documentation Updates

### CHANGELOG.md

```markdown
## [Unreleased]

### Added
- **Source-Agnostic Signal Model** - New `signals` table that can represent content from any platform
  - Universal fields: text, author, timestamp, normalized engagement metrics
  - Platform-specific data stored as JSON (`platform_data` column)
  - Content flags: `is_repost`, `is_reply`, `is_quote` for cross-platform bypass logic
- **Signal Operations** - New `SignalOperations` class for source-agnostic CRUD
- **Signal Transformer** - `SignalTransformer` with pluggable per-source field mapping
- **Dual-FK on Predictions** - `Prediction.signal_id` added alongside legacy `shitpost_id`
- **Data migration CLI** - `migrate-to-signals` subcommand for backfilling signals table

### Changed
- **S3 Processor** - Now supports `source` parameter and writes to both tables (dual-write)
- **Bypass Service** - `_is_retruth()` now checks `is_repost` flag before legacy `reblog` field
- **Analyzer** - `_prepare_enhanced_content()` uses generic field names with fallback

### Deprecated
- **ShitpostOperations** - Deprecated in favor of `SignalOperations`
- **TruthSocialShitpost model** - Retained for backward compatibility
```

### CLAUDE.md Updates

Add to "Key Tables":

```markdown
**`signals`** - Source-agnostic content signals (NEW - replaces truth_social_shitposts)
- `id` (integer, auto-increment primary key)
- `signal_id` (string, unique) -- Platform-specific content ID
- `source` (string) -- Platform: "truth_social", "twitter", "rss"
- `text` (text) -- Plain text content
- `published_at` (datetime) -- When content was published
- `author_username` (string) -- Author display name
- `likes_count`, `shares_count`, `replies_count` (integer) -- Normalized engagement
- `is_repost`, `is_reply`, `is_quote` (boolean) -- Content flags
- `platform_data` (JSON) -- All platform-specific fields
- `raw_api_data` (JSON) -- Complete API response
```

---

## Stress Testing & Edge Cases

| Scenario | Handling |
|---|---|
| **Null `shitpost_id` during migration** | Migration skips records where `shitpost_id IS NULL` and logs them |
| **Duplicate IDs across sources** | `signal_id` includes source prefix if needed, or use composite uniqueness |
| **JSON double-serialization** | SQLAlchemy `JSON` column auto-serializes; never call `json.dumps()` |
| **Partial migration crash** | Re-running is safe -- `store_signal` checks existing `signal_id` |
| **`text` is NULL** | Signal model allows nullable text; bypass service handles it |
| **`published_at` is NULL** | Migration falls back to `created_at` |
| **`platform_data` is NULL** | Model defaults to `{}`; all access uses `.get()` with defaults |
| **Existing predictions still work** | `Prediction.shitpost_id` FK retained; legacy queries unchanged |
| **Dual-write overhead** | Negligible at current throughput (few posts per 5 min) |

---

## Verification Checklist

- [ ] `source venv/bin/activate && pytest -v` passes (27 pre-existing failures acceptable)
- [ ] New test files created and passing:
  - [ ] `test_signal_models.py` (10+ tests)
  - [ ] `test_signal_operations.py` (8+ tests)
  - [ ] `test_signal_utils.py` (10+ tests)
- [ ] `python3 -m ruff check .` passes
- [ ] `python3 -m ruff format .` applies no changes
- [ ] `Signal` model can be instantiated with Truth Social data
- [ ] `SignalTransformer.transform_truth_social()` produces valid Signal dicts
- [ ] `SignalOperations.store_signal()` stores and deduplicates correctly
- [ ] `SignalOperations.get_unprocessed_signals()` returns backward-compatible dicts
- [ ] `Prediction` model accepts both `shitpost_id` and `signal_id`
- [ ] `BypassService._is_retruth()` works with `is_repost` flag
- [ ] Analyzer `_prepare_enhanced_content()` works with both old and new field names
- [ ] `S3Processor` dual-writes to both tables
- [ ] Legacy `ShitpostOperations` still works (emits deprecation warning)
- [ ] Dashboard queries still work against legacy table
- [ ] Notification queries still work against legacy table
- [ ] CHANGELOG.md and CLAUDE.md updated

---

## What NOT To Do

1. **DO NOT delete `TruthSocialShitpost` model or `truth_social_shitposts` table.** The legacy table must remain during transition.

2. **DO NOT change `Prediction.shitpost_id` to NOT NULL -> nullable in a single step without dual-write.** The dual-write ensures both columns are populated.

3. **DO NOT update all 20+ SQL queries in `shitty_ui/data.py` in this PR.** Use the configurable `SIGNALS_TABLE` variable and flip it after migration backfill completes.

4. **DO NOT create an Alembic migration framework.** The project does not use Alembic. Follow existing `Base.metadata.create_all()` pattern.

5. **DO NOT remove backward-compatible aliases from `get_unprocessed_signals()`.** The aliases are critical for the analyzer and prediction operations.

6. **DO NOT hardcode `"truth_social"` in the Signal model or operations classes.** The `source` field should always come from data or constructor parameter.

7. **DO NOT run the migration script in production without `--dry-run` first.**

8. **DO NOT modify `shitpost_alpha.py` (the orchestrator).** It delegates to sub-CLIs and does not need to know about the data model.

9. **DO NOT skip writing tests for the transformer.** The field mapping is the most error-prone part.

10. **DO NOT use `json.dumps()` when storing `platform_data`.** SQLAlchemy's `JSON` column handles serialization automatically.
