"""
S3 to Database Processor
Processes raw data from S3 and loads it into the database.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
import json

from shit.s3 import S3DataLake, S3Config
from shit.config.shitpost_settings import settings
from shit.utils.error_handling import handle_exceptions
from .shitpost_db import ShitpostDatabase
from .shitpost_models import TruthSocialShitpost

logger = logging.getLogger(__name__)


class S3ToDatabaseProcessor:
    """Processes raw data from S3 and loads it into the database."""
    
    def __init__(self, s3_config: Optional[S3Config] = None):
        """Initialize S3 to Database processor.
        
        Args:
            s3_config: S3 configuration (optional, uses settings if not provided)
        """
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
        self.db_manager = ShitpostDatabase()
        
    async def initialize(self):
        """Initialize S3 and database connections."""
        try:
            logger.info("Initializing S3 to Database processor...")
            
            # Initialize S3 Data Lake
            await self.s3_data_lake.initialize()
            logger.info("S3 Data Lake initialized successfully")
            
            # Initialize database
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")
            
            logger.info("S3 to Database processor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 to Database processor: {e}")
            raise
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object.
        
        Args:
            timestamp_str: ISO format timestamp string
            
        Returns:
            datetime object
        """
        try:
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
            # Extract raw API data
            raw_api_data = s3_data.get('raw_api_data', {})
            account_data = raw_api_data.get('account', {})
            
            # Transform to database format (matching database field names)
            transformed_data = {
                'id': raw_api_data.get('id'),  # This is the shitpost_id
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
    
    async def process_s3_data(self, s3_data: Dict) -> bool:
        """Process a single S3 data record and store in database.
        
        Args:
            s3_data: Raw data from S3
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Transform S3 data to database format
            transformed_data = self._transform_s3_data_to_shitpost(s3_data)
            
            # Store in database (deduplication handled by database)
            await self.db_manager.store_shitpost(transformed_data)
            
            logger.debug(f"Successfully processed S3 data for shitpost {transformed_data['shitpost_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing S3 data: {e}")
            return False
    
    async def process_s3_stream(self, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               limit: Optional[int] = None) -> Dict[str, int]:
        """Process a stream of S3 data and load into database.
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of records to process (optional)
            
        Returns:
            Dictionary with processing statistics
        """
        try:
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
                    # Process the data
                    success = await self.process_s3_data(s3_data)
                    
                    if success:
                        stats['successful'] += 1
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing S3 data: {e}")
                    stats['failed'] += 1
                
                # Log progress
                if stats['total_processed'] % 100 == 0:
                    logger.info(f"Processed {stats['total_processed']} records...")
            
            logger.info(f"S3 to Database processing completed:")
            logger.info(f"  Total processed: {stats['total_processed']}")
            logger.info(f"  Successful: {stats['successful']}")
            logger.info(f"  Failed: {stats['failed']}")
            logger.info(f"  Skipped: {stats['skipped']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in S3 to Database processing: {e}")
            raise
    
    async def get_processing_stats(self) -> Dict[str, any]:
        """Get statistics about S3 and database data.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get S3 stats
            s3_stats = await self.s3_data_lake.get_data_stats()
            
            # Get database stats
            db_stats = await self.db_manager.get_database_stats()
            
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
            logger.error(f"Error getting processing stats: {e}")
            return {
                's3_stats': {},
                'db_stats': {},
                'processing_summary': {}
            }
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.s3_data_lake.cleanup()
            await self.db_manager.cleanup()
            logger.info("S3 to Database processor cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
