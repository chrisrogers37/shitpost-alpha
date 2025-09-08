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
from shit.s3 import S3DataLake, S3Config

logger = logging.getLogger(__name__)


class ShitpostDatabase:
    """Manages shitpost database connections and operations."""
    
    def __init__(self, s3_config: Optional[S3Config] = None):
        self.database_url = settings.DATABASE_URL
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        
        # S3 configuration for S3 → Database processing
        if s3_config:
            self.s3_config = s3_config
        else:
            # Create config from settings
            self.s3_config = S3Config(
                bucket_name=settings.S3_BUCKET_NAME,
                prefix=settings.S3_PREFIX,
                region=settings.AWS_REGION,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
        
        self.s3_data_lake = S3DataLake(self.s3_config)
        
    async def initialize(self, init_s3: bool = False):
        """Initialize shitpost database connection and create tables.
        
        Args:
            init_s3: Whether to initialize S3 Data Lake (for S3 → Database processing)
        """
        try:
            logger.info(f"Initializing shitpost database: {self.database_url}")
            
            # Create engine
            if self.database_url.startswith('sqlite'):
                # Use async SQLite
                async_url = self.database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
                self.engine = create_async_engine(
                    async_url,
                    echo=False,  # Disable SQL echo for cleaner output
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                # Use async PostgreSQL
                self.engine = create_async_engine(
                    self.database_url,
                    echo=False  # Disable SQL echo for cleaner output
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
            
            # Initialize S3 Data Lake if requested
            if init_s3:
                await self.s3_data_lake.initialize()
                logger.info("S3 Data Lake initialized successfully")
            
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
                stmt = select(TruthSocialShitpost).where(TruthSocialShitpost.shitpost_id == shitpost_data.get('shitpost_id'))
                result = await session.execute(stmt)
                existing_shitpost = result.scalar_one_or_none()
                
                if existing_shitpost:
                    logger.debug(f"Shitpost {shitpost_data.get('shitpost_id')} already exists, skipping")
                    return str(existing_shitpost.id)
                
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
                
                logger.debug(f"Stored new shitpost with ID: {shitpost.id}")
                return str(shitpost.id)
                
        except IntegrityError:
            logger.debug(f"Shitpost {shitpost_data.get('id')} already exists (integrity constraint)")
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
                
                logger.debug(f"Stored enhanced analysis with ID: {prediction.id}")
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
                
                # Main query - Get posts that need analysis
                # Include ALL posts (even those with no text) so they can be bypassed
                stmt = select(TruthSocialShitpost).where(
                    and_(
                        TruthSocialShitpost.timestamp >= launch_datetime,
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
    
    # S3 → Database Processing Methods (consolidated from S3ToDatabaseProcessor)
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object.
        
        Args:
            timestamp_str: ISO format timestamp string
            
        Returns:
            datetime object
        """
        try:
            if not timestamp_str:
                return datetime.now()
                
            # Handle ISO format with 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str.replace('Z', '+00:00')
            
            # Parse and convert to timezone-naive
            dt = datetime.fromisoformat(timestamp_str)
            return dt.replace(tzinfo=None)
            
        except Exception as e:
            logger.warning(f"Could not parse timestamp {timestamp_str}: {e}")
            return datetime.now()
    
    def _transform_s3_data_to_shitpost(self, s3_data: Dict) -> Dict:
        """Transform S3 data to database format.
        
        Args:
            s3_data: Raw data from S3
            
        Returns:
            Transformed data for database storage
        """
        try:
            import json
            
            # Extract raw API data
            raw_api_data = s3_data.get('raw_api_data', {})
            account_data = raw_api_data.get('account', {})
            
            # Transform to database format (matching database field names)
            transformed_data = {
                'shitpost_id': raw_api_data.get('id'),  # This is the shitpost_id
                'content': raw_api_data.get('content', ''),
                'text': raw_api_data.get('text', ''),
                'timestamp': self._parse_timestamp(raw_api_data.get('created_at', '')),
                'username': account_data.get('username', ''),
                'platform': 'truth_social',
                
                # Shitpost metadata
                'language': raw_api_data.get('language', ''),
                'visibility': raw_api_data.get('visibility', ''),
                'sensitive': raw_api_data.get('sensitive', False),
                'spoiler_text': raw_api_data.get('spoiler_text', ''),
                'uri': raw_api_data.get('uri', ''),
                'url': raw_api_data.get('url', ''),
                
                # Engagement metrics
                'replies_count': raw_api_data.get('replies_count', 0),
                'reblogs_count': raw_api_data.get('reblogs_count', 0),
                'favourites_count': raw_api_data.get('favourites_count', 0),
                'upvotes_count': raw_api_data.get('upvotes_count', 0),
                'downvotes_count': raw_api_data.get('downvotes_count', 0),
                
                # Account information
                'account_id': account_data.get('id'),
                'account_display_name': account_data.get('display_name', ''),
                'account_followers_count': account_data.get('followers_count', 0),
                'account_following_count': account_data.get('following_count', 0),
                'account_statuses_count': account_data.get('statuses_count', 0),
                'account_verified': account_data.get('verified', False),
                'account_website': account_data.get('website', ''),
                
                # Media and attachments
                'has_media': len(raw_api_data.get('media_attachments', [])) > 0,
                'media_attachments': json.dumps(raw_api_data.get('media_attachments', [])),
                'mentions': json.dumps(raw_api_data.get('mentions', [])),
                'tags': json.dumps(raw_api_data.get('tags', [])),
                
                # Additional fields
                'in_reply_to_id': raw_api_data.get('in_reply_to_id'),
                'quote_id': raw_api_data.get('quote_id'),
                'in_reply_to_account_id': raw_api_data.get('in_reply_to_account_id'),
                'card': json.dumps(raw_api_data.get('card')) if raw_api_data.get('card') else None,
                'group': json.dumps(raw_api_data.get('group')) if raw_api_data.get('group') else None,
                'quote': json.dumps(raw_api_data.get('quote')) if raw_api_data.get('quote') else None,
                'in_reply_to': json.dumps(raw_api_data.get('in_reply_to')) if raw_api_data.get('in_reply_to') else None,
                'reblog': json.dumps(raw_api_data.get('reblog')) if raw_api_data.get('reblog') else None,
                'sponsored': raw_api_data.get('sponsored', False),
                'reaction': json.dumps(raw_api_data.get('reaction')) if raw_api_data.get('reaction') else None,
                'favourited': raw_api_data.get('favourited', False),
                'reblogged': raw_api_data.get('reblogged', False),
                'muted': raw_api_data.get('muted', False),
                'pinned': raw_api_data.get('pinned', False),
                'bookmarked': raw_api_data.get('bookmarked', False),
                'poll': json.dumps(raw_api_data.get('poll')) if raw_api_data.get('poll') else None,
                'emojis': json.dumps(raw_api_data.get('emojis', [])),
                'votable': raw_api_data.get('votable', False),
                'edited_at': self._parse_timestamp(raw_api_data.get('edited_at', '')) if raw_api_data.get('edited_at') else None,
                'version': raw_api_data.get('version', ''),
                'editable': raw_api_data.get('editable', False),
                'title': raw_api_data.get('title', ''),
                'raw_api_data': json.dumps(raw_api_data),
                'created_at': self._parse_timestamp(raw_api_data.get('created_at', '')),
                'updated_at': self._parse_timestamp(raw_api_data.get('edited_at', '')) if raw_api_data.get('edited_at') else self._parse_timestamp(raw_api_data.get('created_at', ''))
            }
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error transforming S3 data to shitpost format: {e}")
            raise
    
    async def process_s3_to_database(self, start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None,
                                   limit: Optional[int] = None,
                                   dry_run: bool = False) -> Dict[str, int]:
        """Process S3 data and load into database (consolidated method).
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of records to process (optional)
            dry_run: If True, don't actually store to database
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            if dry_run:
                logger.info(f"Starting S3 to Database processing (DRY RUN - no database writes)...")
            else:
                logger.info(f"Starting S3 to Database processing...")
            logger.info(f"Date range: {start_date} to {end_date}")
            logger.info(f"Limit: {limit}")
            
            stats = {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
            
            # Stream data from S3
            async for s3_data in self.s3_data_lake.stream_raw_data(start_date, end_date, limit):
                stats['total_processed'] += 1
                
                try:
                    if dry_run:
                        # In dry run, just count what would be processed
                        stats['successful'] += 1
                    else:
                        # Transform S3 data to database format
                        transformed_data = self._transform_s3_data_to_shitpost(s3_data)
                        
                        # Store in database (deduplication handled by store_shitpost)
                        result = await self.store_shitpost(transformed_data)
                        
                        if result:
                            stats['successful'] += 1
                        else:
                            stats['skipped'] += 1  # Already exists
                            
                except Exception as e:
                    logger.error(f"Error processing S3 data: {e}")
                    stats['failed'] += 1
                
                # Log progress (less frequently)
                if stats['total_processed'] % 500 == 0:
                    logger.info(f"Processed {stats['total_processed']} records...")
            
            if dry_run:
                logger.info(f"S3 to Database processing completed (DRY RUN):")
                logger.info(f"  Total processed: {stats['total_processed']}")
                logger.info(f"  Would be successful: {stats['successful']}")
                logger.info(f"  Would fail: {stats['failed']}")
                logger.info(f"  Would be skipped: {stats['skipped']}")
            else:
                logger.info(f"S3 to Database processing completed:")
                logger.info(f"  Total processed: {stats['total_processed']}")
                logger.info(f"  Successful: {stats['successful']}")
                logger.info(f"  Failed: {stats['failed']}")
                logger.info(f"  Skipped: {stats['skipped']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in S3 to Database processing: {e}")
            raise
    
    async def get_s3_processing_stats(self) -> Dict[str, any]:
        """Get statistics about S3 and database data.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get S3 stats
            s3_stats = await self.s3_data_lake.get_data_stats()
            
            # Get database stats
            db_stats = await self.get_database_stats()
            
            return {
                's3_stats': s3_stats.__dict__,
                'db_stats': db_stats,
                'processing_summary': {
                    's3_files': s3_stats.total_files,
                    'db_records': db_stats.get('total_shitposts', 0),
                    'processing_ratio': round(
                        db_stats.get('total_shitposts', 0) / max(s3_stats.total_files, 1) * 100, 2
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting S3 processing stats: {e}")
            return {
                's3_stats': {},
                'db_stats': {},
                'processing_summary': {}
            }
    
    async def cleanup(self):
        """Cleanup shitpost database resources."""
        if self.engine:
            await self.engine.dispose()
        if hasattr(self, 's3_data_lake'):
            await self.s3_data_lake.cleanup()
        logger.info("Shitpost database cleanup completed")
