"""
Database Utilities
Helper functions and utilities for database operations.
Extracted from ShitpostDatabase for reusability.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import json

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("database_utils")
logger = db_logger.logger

class DatabaseUtils:
    """Utility functions for database operations."""
    
    @staticmethod
    def parse_timestamp(timestamp_str: str) -> datetime:
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
    
    @staticmethod
    def transform_s3_data_to_shitpost(s3_data: Dict) -> Dict:
        """Transform S3 data to shitpost format.
        
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
                'shitpost_id': raw_api_data.get('id'),  # This is the shitpost_id
                'content': raw_api_data.get('content', ''),
                'text': raw_api_data.get('text', ''),
                'timestamp': DatabaseUtils.parse_timestamp(raw_api_data.get('created_at', '')),
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
                'edited_at': DatabaseUtils.parse_timestamp(raw_api_data.get('edited_at', '')) if raw_api_data.get('edited_at') else None,
                'version': raw_api_data.get('version', ''),
                'editable': raw_api_data.get('editable', False),
                'title': raw_api_data.get('title', ''),
                'raw_api_data': json.dumps(raw_api_data),
                'created_at': DatabaseUtils.parse_timestamp(raw_api_data.get('created_at', '')),
                'updated_at': DatabaseUtils.parse_timestamp(raw_api_data.get('edited_at', '')) if raw_api_data.get('edited_at') else DatabaseUtils.parse_timestamp(raw_api_data.get('created_at', ''))
            }
            
            return transformed_data
            
        except Exception as e:
            logger.error(f"Error transforming S3 data to shitpost format: {e}")
            raise
