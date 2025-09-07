"""
Shitpost Database Manager
Handles database connections and operations for shitpost storage using SQLAlchemy.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shit.config.shitpost_settings import settings
from shitvault.shitpost_models import Base

logger = logging.getLogger(__name__)


class ShitpostDatabase:
    """Manages shitpost database connections and operations."""
    
    def __init__(self):
        self.database_url = settings.DATABASE_URL
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        
    async def initialize(self):
        """Initialize shitpost database connection and create tables."""
        try:
            logger.info(f"Initializing shitpost database: {self.database_url}")
            
            # Create engine
            if self.database_url.startswith('sqlite'):
                # Use async SQLite
                async_url = self.database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
                self.engine = create_async_engine(
                    async_url,
                    echo=settings.DEBUG,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                # Use async PostgreSQL
                self.engine = create_async_engine(
                    self.database_url,
                    echo=settings.DEBUG
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Shitpost database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize shitpost database: {e}")
            raise
    
    def get_session(self) -> AsyncSession:
        """Get a shitpost database session."""
        if not self.SessionLocal:
            raise RuntimeError("Shitpost database not initialized")
        
        return self.SessionLocal()
    
    async def store_shitpost(self, shitpost_data: Dict[str, Any]) -> Optional[str]:
        """Store a shitpost in the database."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost
            from sqlalchemy.exc import IntegrityError
            
            async with self.get_session() as session:
                # Check if shitpost already exists
                from sqlalchemy import select
                stmt = select(TruthSocialShitpost).where(TruthSocialShitpost.shitpost_id == shitpost_data.get('id'))
                result = await session.execute(stmt)
                existing_shitpost = result.scalar_one_or_none()
                
                if existing_shitpost:
                    logger.info(f"Shitpost {shitpost_data.get('id')} already exists, skipping")
                    return str(existing_shitpost.id)
                
                shitpost = TruthSocialShitpost(
                    shitpost_id=shitpost_data.get('id'),
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
                    
                    # Additional API fields
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
                    
                    # Raw API data
                    raw_api_data=shitpost_data.get('raw_api_data'),
                    
                    # Legacy fields
                    original_length=shitpost_data.get('original_length'),
                    cleaned_length=shitpost_data.get('cleaned_length'),
                    hashtags=shitpost_data.get('hashtags')
                )
                
                session.add(shitpost)
                await session.commit()
                await session.refresh(shitpost)
                
                logger.info(f"Stored new shitpost with ID: {shitpost.id}")
                return str(shitpost.id)
                
        except IntegrityError:
            logger.info(f"Shitpost {shitpost_data.get('id')} already exists (integrity constraint)")
            return None
        except Exception as e:
            logger.error(f"Error storing shitpost: {e}")
            return None
    
    async def store_analysis(self, shitpost_id: str, analysis_data: Dict[str, Any], shitpost_data: Dict[str, Any] = None) -> Optional[str]:
        """Store LLM analysis results in the database with enhanced shitpost data."""
        try:
            from shitvault.shitpost_models import Prediction
            
            async with self.get_session() as session:
                # Calculate engagement scores
                engagement_score = None
                viral_score = None
                if shitpost_data:
                    replies = shitpost_data.get('replies_count', 0)
                    reblogs = shitpost_data.get('reblogs_count', 0)
                    favourites = shitpost_data.get('favourites_count', 0)
                    upvotes = shitpost_data.get('upvotes_count', 0)
                    followers = shitpost_data.get('account_followers_count', 0)
                    
                    # Engagement score based on interaction rate
                    if followers > 0:
                        engagement_score = (replies + reblogs + favourites) / followers
                    
                    # Viral score based on reblog/favourite ratio
                    if favourites > 0:
                        viral_score = reblogs / favourites
                
                prediction = Prediction(
                    shitpost_id=shitpost_id,
                    assets=analysis_data.get('assets', []),
                    market_impact=analysis_data.get('market_impact', {}),
                    confidence=analysis_data.get('confidence', 0.0),
                    thesis=analysis_data.get('thesis', ''),
                    
                    # Set analysis status for successful analyses
                    analysis_status='completed',
                    analysis_comment=None,
                    
                    # Enhanced analysis scores
                    engagement_score=engagement_score,
                    viral_score=viral_score,
                    sentiment_score=analysis_data.get('sentiment_score'),
                    urgency_score=analysis_data.get('urgency_score'),
                    
                    # Content analysis
                    has_media=shitpost_data.get('has_media', False) if shitpost_data else False,
                    mentions_count=len(shitpost_data.get('mentions', [])) if shitpost_data else 0,
                    hashtags_count=len(shitpost_data.get('tags', [])) if shitpost_data else 0,
                    content_length=len(shitpost_data.get('text', '')) if shitpost_data else 0,
                    
                    # Engagement metrics at analysis time
                    replies_at_analysis=shitpost_data.get('replies_count', 0) if shitpost_data else 0,
                    reblogs_at_analysis=shitpost_data.get('reblogs_count', 0) if shitpost_data else 0,
                    favourites_at_analysis=shitpost_data.get('favourites_count', 0) if shitpost_data else 0,
                    upvotes_at_analysis=shitpost_data.get('upvotes_count', 0) if shitpost_data else 0,
                    
                    # LLM metadata
                    llm_provider=analysis_data.get('llm_provider'),
                    llm_model=analysis_data.get('llm_model'),
                    analysis_timestamp=self._parse_timestamp(analysis_data.get('analysis_timestamp'))
                )
                
                session.add(prediction)
                await session.commit()
                await session.refresh(prediction)
                
                logger.info(f"Stored enhanced analysis with ID: {prediction.id}")
                return str(prediction.id)
                
        except Exception as e:
            logger.error(f"Error storing analysis: {e}")
            return None
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object."""
        try:
            if isinstance(timestamp_str, str):
                # Handle ISO format with or without timezone
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str.replace('Z', '+00:00')
                return datetime.fromisoformat(timestamp_str)
            elif isinstance(timestamp_str, datetime):
                return timestamp_str
            else:
                return datetime.now()
        except Exception as e:
            logger.warning(f"Could not parse timestamp {timestamp_str}, using current time: {e}")
            return datetime.now()
    
    async def handle_no_text_prediction(self, shitpost_id: str, shitpost_data: Dict[str, Any]) -> Optional[str]:
        """Create a prediction record for posts that can't be analyzed."""
        try:
            from shitvault.shitpost_models import Prediction
            
            # Determine the bypass reason based on content
            reason = self._get_bypass_reason(shitpost_data)
            
            async with self.get_session() as session:
                prediction = Prediction(
                    shitpost_id=shitpost_id,
                    analysis_status='bypassed',
                    analysis_comment=reason,
                    # Set minimal required fields for bypassed posts
                    confidence=None,
                    thesis=None,
                    assets=[],
                    market_impact={},
                    engagement_score=None,
                    viral_score=None,
                    sentiment_score=None,
                    urgency_score=None,
                    has_media=shitpost_data.get('has_media', False),
                    mentions_count=len(shitpost_data.get('mentions', [])),
                    hashtags_count=len(shitpost_data.get('hashtags', [])),
                    content_length=len(shitpost_data.get('text', '')),
                    replies_at_analysis=shitpost_data.get('replies_count', 0),
                    reblogs_at_analysis=shitpost_data.get('reblogs_count', 0),
                    favourites_at_analysis=shitpost_data.get('favourites_count', 0),
                    upvotes_at_analysis=shitpost_data.get('upvotes_count', 0),
                    llm_provider=None,
                    llm_model=None,
                    analysis_timestamp=datetime.now()
                )
                
                session.add(prediction)
                await session.commit()
                await session.refresh(prediction)
                
                logger.info(f"Created bypassed prediction for {shitpost_id}: {reason}")
                return str(prediction.id)
                
        except Exception as e:
            logger.error(f"Error creating bypassed prediction: {e}")
            return None
    
    def _get_bypass_reason(self, shitpost_data: Dict[str, Any]) -> str:
        """Determine why a post should be bypassed for analysis."""
        text_content = shitpost_data.get('text', '').strip()
        
        # Check for various bypass conditions
        if not text_content:
            return 'no_text'
        
        # Check if it's just a URL with no context
        if text_content.startswith('http') and len(text_content.split()) <= 2:
            return 'url_only'
        
        # Check if it's just emojis/symbols
        if all(ord(char) < 128 for char in text_content) and len(text_content.strip()) < 3:
            return 'symbols_only'
        
        # Check if it's just media (has media but no text)
        if shitpost_data.get('has_media', False) and not text_content:
            return 'media_only'
        
        # Default fallback
        return 'unanalyzable_content'
    
    async def get_recent_shitposts(self, limit: int = 10) -> list:
        """Get recent shitposts."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost
            
            async with self.get_session() as session:
                from sqlalchemy import select
                stmt = select(TruthSocialShitpost).order_by(TruthSocialShitpost.timestamp.desc()).limit(limit)
                result = await session.execute(stmt)
                shitposts = result.scalars().all()
                
                return [
                    {
                        'id': shitpost.id,
                        'shitpost_id': shitpost.shitpost_id,
                        'content': shitpost.content,
                        'text': shitpost.text,
                        'timestamp': shitpost.timestamp,
                        'username': shitpost.username,
                        'platform': shitpost.platform,
                        'language': shitpost.language,
                        'visibility': shitpost.visibility,
                        'sensitive': shitpost.sensitive,
                        'uri': shitpost.uri,
                        'url': shitpost.url,
                        'replies_count': shitpost.replies_count,
                        'reblogs_count': shitpost.reblogs_count,
                        'favourites_count': shitpost.favourites_count,
                        'upvotes_count': shitpost.upvotes_count,
                        'downvotes_count': shitpost.downvotes_count,
                        'account_id': shitpost.account_id,
                        'account_display_name': shitpost.account_display_name,
                        'account_verified': shitpost.account_verified,
                        'has_media': shitpost.has_media,
                        'media_attachments': shitpost.media_attachments,
                        'mentions': shitpost.mentions,
                        'tags': shitpost.tags,
                        'raw_api_data': shitpost.raw_api_data
                    }
                    for shitpost in shitposts
                ]
                
        except Exception as e:
            logger.error(f"Error fetching recent shitposts: {e}")
            return []
    
    async def get_last_shitpost_id(self) -> Optional[str]:
        """Get the most recent shitpost ID from the database."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost
            
            async with self.get_session() as session:
                from sqlalchemy import select
                stmt = select(TruthSocialShitpost.shitpost_id).order_by(TruthSocialShitpost.timestamp.desc()).limit(1)
                result = await session.execute(stmt)
                last_shitpost = result.scalar_one_or_none()
                
                if last_shitpost:
                    logger.info(f"Found last shitpost ID in database: {last_shitpost}")
                    return last_shitpost
                else:
                    logger.info("No shitposts found in database")
                    return None
                
        except Exception as e:
            logger.error(f"Error fetching last shitpost ID: {e}")
            return None
    
    async def get_unprocessed_shitposts(self, launch_date: str, limit: int = 10) -> List[Dict]:
        """
        Get shitposts that need LLM analysis.
        
        Criteria:
        1. Shitpost timestamp is after system launch date
        2. Shitpost has no existing prediction
        3. Shitpost has sufficient content for analysis
        """
        try:
            from shitvault.shitpost_models import TruthSocialShitpost, Prediction
            from datetime import datetime
            from sqlalchemy import select, and_, not_, exists
            
            # Parse launch date
            launch_datetime = datetime.fromisoformat(launch_date.replace('Z', '+00:00'))
            
            async with self.get_session() as session:
                # Subquery to check if prediction exists
                prediction_exists = select(Prediction.id).where(Prediction.shitpost_id == TruthSocialShitpost.shitpost_id)
                
                # Main query - TEMPORARILY REMOVED LAUNCH DATE FILTER FOR TESTING
                # Include ALL posts (even those with no text) so they can be bypassed
                stmt = select(TruthSocialShitpost).where(
                    and_(
                        # TruthSocialShitpost.timestamp >= launch_datetime,  # TEMPORARILY COMMENTED OUT
                        not_(exists(prediction_exists))
                        # Removed text filters so posts with no text can be processed and bypassed
                    )
                ).order_by(TruthSocialShitpost.timestamp.desc()).limit(limit)
                
                result = await session.execute(stmt)
                shitposts = result.scalars().all()
                
                # Convert to dict format
                shitpost_dicts = []
                for shitpost in shitposts:
                    shitpost_dict = {
                        'id': shitpost.id,
                        'shitpost_id': shitpost.shitpost_id,
                        'content': shitpost.content,
                        'text': shitpost.text,
                        'timestamp': shitpost.timestamp,
                        'username': shitpost.username,
                        'platform': shitpost.platform,
                        'language': shitpost.language,
                        'visibility': shitpost.visibility,
                        'sensitive': shitpost.sensitive,
                        'uri': shitpost.uri,
                        'url': shitpost.url,
                        'replies_count': shitpost.replies_count,
                        'reblogs_count': shitpost.reblogs_count,
                        'favourites_count': shitpost.favourites_count,
                        'upvotes_count': shitpost.upvotes_count,
                        'downvotes_count': shitpost.downvotes_count,
                        'account_id': shitpost.account_id,
                        'account_display_name': shitpost.account_display_name,
                        'account_verified': shitpost.account_verified,
                        'has_media': shitpost.has_media,
                        'media_attachments': shitpost.media_attachments,
                        'mentions': shitpost.mentions,
                        'tags': shitpost.tags,
                        'raw_api_data': shitpost.raw_api_data
                    }
                    shitpost_dicts.append(shitpost_dict)
                
                logger.info(f"Found {len(shitpost_dicts)} unprocessed shitposts for analysis")
                return shitpost_dicts
                
        except Exception as e:
            logger.error(f"Error fetching unprocessed shitposts: {e}")
            return []
    
    async def check_prediction_exists(self, shitpost_id: str) -> bool:
        """Check if a prediction already exists for a shitpost."""
        try:
            from shitvault.shitpost_models import Prediction
            
            async with self.get_session() as session:
                from sqlalchemy import select
                stmt = select(Prediction.id).where(Prediction.shitpost_id == shitpost_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none() is not None
                
        except Exception as e:
            logger.error(f"Error checking prediction existence: {e}")
            return False
    
    async def get_shitpost_analysis(self, shitpost_id: str) -> Optional[Dict]:
        """Get analysis for a specific shitpost."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost, Prediction
            
            async with self.get_session() as session:
                # Get shitpost
                shitpost_result = await session.execute(
                    session.query(TruthSocialShitpost)
                    .filter(TruthSocialShitpost.id == shitpost_id)
                )
                shitpost = shitpost_result.scalar_one_or_none()
                
                if not shitpost:
                    return None
                
                # Get analysis
                analysis_result = await session.execute(
                    session.query(Prediction)
                    .filter(Prediction.shitpost_id == shitpost_id)
                )
                analysis = analysis_result.scalar_one_or_none()
                
                return {
                    'shitpost': {
                        'id': shitpost.id,
                        'content': shitpost.content,
                        'timestamp': shitpost.timestamp,
                        'username': shitpost.username
                    },
                    'analysis': {
                        'assets': analysis.assets if analysis else [],
                        'market_impact': analysis.market_impact if analysis else {},
                        'confidence': analysis.confidence if analysis else 0.0,
                        'thesis': analysis.thesis if analysis else ''
                    } if analysis else None
                }
                
        except Exception as e:
            logger.error(f"Error fetching shitpost analysis: {e}")
            return None
    
    async def get_analysis_stats(self) -> Dict[str, Any]:
        """Get basic statistics about stored shitpost data."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost, Prediction
            from sqlalchemy import func
            
            async with self.get_session() as session:
                # Count shitposts
                shitpost_count_result = await session.execute(
                    func.count(TruthSocialShitpost.id)
                )
                shitpost_count = shitpost_count_result.scalar()
                
                # Count analyses
                analysis_count_result = await session.execute(
                    func.count(Prediction.id)
                )
                analysis_count = analysis_count_result.scalar()
                
                # Average confidence
                avg_confidence_result = await session.execute(
                    func.avg(Prediction.confidence)
                )
                avg_confidence = avg_confidence_result.scalar() or 0.0
                
                return {
                    'total_shitposts': shitpost_count,
                    'total_analyses': analysis_count,
                    'average_confidence': round(avg_confidence, 3),
                    'analysis_rate': round(analysis_count / max(shitpost_count, 1), 3)
                }
                
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {
                'total_shitposts': 0,
                'total_analyses': 0,
                'average_confidence': 0.0,
                'analysis_rate': 0.0
            }
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            from shitvault.shitpost_models import TruthSocialShitpost, Prediction
            from sqlalchemy import func, select
            
            async with self.get_session() as session:
                # Count shitposts
                shitpost_count_result = await session.execute(
                    select(func.count(TruthSocialShitpost.id))
                )
                shitpost_count = shitpost_count_result.scalar()
                
                # Count analyses
                analysis_count_result = await session.execute(
                    select(func.count(Prediction.id))
                )
                analysis_count = analysis_count_result.scalar()
                
                # Count by analysis status
                status_counts = {}
                for status in ['analyzed', 'bypassed', 'error', 'pending']:
                    status_result = await session.execute(
                        select(func.count(Prediction.id)).where(Prediction.analysis_status == status)
                    )
                    status_counts[f'{status}_count'] = status_result.scalar()
                
                # Average confidence
                avg_confidence_result = await session.execute(
                    select(func.avg(Prediction.confidence))
                )
                avg_confidence = avg_confidence_result.scalar() or 0.0
                
                # Date range
                date_range_result = await session.execute(
                    select(func.min(TruthSocialShitpost.created_at))
                )
                min_date = date_range_result.scalar()
                
                date_range_result = await session.execute(
                    select(func.max(TruthSocialShitpost.created_at))
                )
                max_date = date_range_result.scalar()
                
                return {
                    'total_shitposts': shitpost_count,
                    'total_analyses': analysis_count,
                    'average_confidence': round(avg_confidence, 3),
                    'analysis_rate': round(analysis_count / max(shitpost_count, 1), 3),
                    'earliest_post': min_date.isoformat() if min_date else None,
                    'latest_post': max_date.isoformat() if max_date else None,
                    **status_counts
                }
                
        except Exception as e:
            logger.error(f"Error fetching database stats: {e}")
            return {
                'total_shitposts': 0,
                'total_analyses': 0,
                'average_confidence': 0.0,
                'analysis_rate': 0.0,
                'earliest_post': None,
                'latest_post': None,
                'analyzed_count': 0,
                'bypassed_count': 0,
                'error_count': 0,
                'pending_count': 0
            }
    
    async def cleanup(self):
        """Cleanup shitpost database resources."""
        if self.engine:
            await self.engine.dispose()
        logger.info("Shitpost database cleanup completed")
