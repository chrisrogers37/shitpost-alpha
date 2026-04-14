"""
Shitpost Operations
Domain-specific operations for shitpost management.
Extracted from ShitpostDatabase for modularity.
"""


from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import select, and_, not_, exists
from sqlalchemy.exc import IntegrityError

import warnings

from shit.db.database_operations import DatabaseOperations
from shitvault.shitpost_models import TruthSocialShitpost, Prediction

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("shitpost_operations")
logger = db_logger.logger

_DEPRECATION_MSG = (
    "ShitpostOperations is deprecated. Use SignalOperations for new code. "
    "ShitpostOperations will be removed once all consumers are migrated."
)


class ShitpostOperations:
    """Operations for managing shitposts.

    .. deprecated::
        Use :class:`shitvault.signal_operations.SignalOperations` instead.
    """

    def __init__(self, db_ops: DatabaseOperations):
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        self.db_ops = db_ops
    
    async def store_shitpost(self, shitpost_data: Dict[str, Any]) -> Optional[str]:
        """Store a shitpost in the database."""
        try:
            # Check if shitpost already exists
            existing_shitpost = await self.db_ops.read_one(
                TruthSocialShitpost, 
                {'shitpost_id': shitpost_data.get('shitpost_id')}
            )
            
            if existing_shitpost:
                logger.debug(f"Shitpost {shitpost_data.get('shitpost_id')} already exists, skipping")
                return str(existing_shitpost.id)
            
            # Create new shitpost
            shitpost = TruthSocialShitpost(
                shitpost_id=shitpost_data.get('shitpost_id'),
                content=shitpost_data.get('content'),
                text=shitpost_data.get('text'),
                timestamp=shitpost_data.get('timestamp'),
                username=shitpost_data.get('username'),
                platform=shitpost_data.get('platform'),
                
                # Shitpost metadata
                language=shitpost_data.get('language'),
                visibility=shitpost_data.get('visibility'),
                sensitive=shitpost_data.get('sensitive'),
                spoiler_text=shitpost_data.get('spoiler_text'),
                uri=shitpost_data.get('uri'),
                url=shitpost_data.get('url'),
                
                # Engagement metrics
                replies_count=shitpost_data.get('replies_count'),
                reblogs_count=shitpost_data.get('reblogs_count'),
                favourites_count=shitpost_data.get('favourites_count'),
                upvotes_count=shitpost_data.get('upvotes_count'),
                downvotes_count=shitpost_data.get('downvotes_count'),
                
                # Account information
                account_id=shitpost_data.get('account_id'),
                account_display_name=shitpost_data.get('account_display_name'),
                account_followers_count=shitpost_data.get('account_followers_count'),
                account_following_count=shitpost_data.get('account_following_count'),
                account_statuses_count=shitpost_data.get('account_statuses_count'),
                account_verified=shitpost_data.get('account_verified'),
                account_website=shitpost_data.get('account_website'),
                
                # Media and attachments
                has_media=shitpost_data.get('has_media'),
                media_attachments=shitpost_data.get('media_attachments'),
                mentions=shitpost_data.get('mentions'),
                tags=shitpost_data.get('tags'),
                
                # Additional fields
                in_reply_to_id=shitpost_data.get('in_reply_to_id'),
                quote_id=shitpost_data.get('quote_id'),
                in_reply_to_account_id=shitpost_data.get('in_reply_to_account_id'),
                card=shitpost_data.get('card'),
                group=shitpost_data.get('group'),
                quote=shitpost_data.get('quote'),
                in_reply_to=shitpost_data.get('in_reply_to'),
                reblog=shitpost_data.get('reblog'),
                sponsored=shitpost_data.get('sponsored'),
                reaction=shitpost_data.get('reaction'),
                favourited=shitpost_data.get('favourited'),
                reblogged=shitpost_data.get('reblogged'),
                muted=shitpost_data.get('muted'),
                pinned=shitpost_data.get('pinned'),
                bookmarked=shitpost_data.get('bookmarked'),
                poll=shitpost_data.get('poll'),
                emojis=shitpost_data.get('emojis'),
                votable=shitpost_data.get('votable'),
                edited_at=shitpost_data.get('edited_at'),
                version=shitpost_data.get('version'),
                editable=shitpost_data.get('editable'),
                title=shitpost_data.get('title'),
                raw_api_data=shitpost_data.get('raw_api_data')
            )
            
            # Store in database
            self.db_ops.session.add(shitpost)
            await self.db_ops.session.commit()
            await self.db_ops.session.refresh(shitpost)
            
            logger.info(f"Stored shitpost {shitpost.shitpost_id} with ID: {shitpost.id}")
            return str(shitpost.id)
            
        except IntegrityError as e:
            await self.db_ops.session.rollback()
            logger.warning(f"Integrity error storing shitpost {shitpost_data.get('shitpost_id')}: {e}")
            return None
        except Exception as e:
            await self.db_ops.session.rollback()
            logger.error(f"Error storing shitpost {shitpost_data.get('shitpost_id')}: {e}")
            raise
    
    async def get_unprocessed_shitposts(
        self,
        launch_date: str,
        limit: int = 10,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get shitposts that need LLM analysis.

        Provider-aware: when llm_provider/llm_model are given, returns posts
        that haven't been analyzed by that specific provider+model, even if
        other providers have already analyzed them.

        Criteria:
        1. Shitpost timestamp is after system launch date
        2. Shitpost has no existing prediction (for the given provider/model)
        3. Shitpost has sufficient content for analysis
        """
        try:
            # Parse launch date
            launch_datetime = datetime.fromisoformat(launch_date.replace('Z', '+00:00'))

            # Subquery to check if prediction exists (provider-aware)
            pred_conditions = [Prediction.signal_id == TruthSocialShitpost.shitpost_id]
            if llm_provider is not None:
                pred_conditions.append(Prediction.llm_provider == llm_provider)
            if llm_model is not None:
                pred_conditions.append(Prediction.llm_model == llm_model)

            prediction_exists = select(Prediction.id).where(and_(*pred_conditions))

            # Main query - Get posts that need analysis
            # Include ALL posts (even those with no text) so they can be bypassed
            stmt = select(TruthSocialShitpost).where(
                and_(
                    TruthSocialShitpost.timestamp >= launch_datetime,
                    not_(exists(prediction_exists))
                )
            ).order_by(TruthSocialShitpost.timestamp.desc()).limit(limit)

            result = await self.db_ops.session.execute(stmt)
            shitposts = result.scalars().all()

            # Convert to dict — only fields consumed by the analyzer pipeline
            shitpost_dicts = []
            for shitpost in shitposts:
                shitpost_dicts.append({
                    'id': shitpost.id,
                    'shitpost_id': shitpost.shitpost_id,
                    'content': shitpost.content,
                    'text': shitpost.text,
                    'timestamp': shitpost.timestamp,
                    'username': shitpost.username,
                    'platform': shitpost.platform,
                    'replies_count': shitpost.replies_count,
                    'reblogs_count': shitpost.reblogs_count,
                    'favourites_count': shitpost.favourites_count,
                    'upvotes_count': shitpost.upvotes_count,
                    'account_verified': shitpost.account_verified,
                    'account_followers_count': shitpost.account_followers_count,
                    'has_media': shitpost.has_media,
                    'mentions': shitpost.mentions,
                    'tags': shitpost.tags,
                    'reblog': shitpost.reblog,
                    'is_repost': shitpost.reblog is not None,
                })

            logger.info(f"Retrieved {len(shitpost_dicts)} unprocessed shitposts")
            return shitpost_dicts

        except Exception as e:
            logger.error(f"Error retrieving unprocessed shitposts: {e}")
            raise
