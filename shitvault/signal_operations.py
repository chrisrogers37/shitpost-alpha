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
            logger.warning(
                f"Integrity error storing signal {signal_data.get('signal_id')}: {e}"
            )
            return None
        except Exception as e:
            await self.db_ops.session.rollback()
            logger.error(
                f"Error storing signal {signal_data.get('signal_id')}: {e}"
            )
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
            launch_datetime = datetime.fromisoformat(
                launch_date.replace("Z", "+00:00")
            )

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
                    "reblog": (
                        sig.platform_data.get("reblog")
                        if sig.platform_data
                        else None
                    ),
                    "mentions": (
                        sig.platform_data.get("mentions", [])
                        if sig.platform_data
                        else []
                    ),
                    "tags": (
                        sig.platform_data.get("tags", [])
                        if sig.platform_data
                        else []
                    ),
                    "reblogs_count": sig.shares_count,
                    "favourites_count": sig.likes_count,
                    "upvotes_count": (
                        sig.platform_data.get("upvotes_count", 0)
                        if sig.platform_data
                        else 0
                    ),
                    "downvotes_count": (
                        sig.platform_data.get("downvotes_count", 0)
                        if sig.platform_data
                        else 0
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
