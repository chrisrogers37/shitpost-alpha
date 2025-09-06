"""
S3 Data Lake for Raw Truth Social Data
Handles storage and retrieval of raw API data in S3.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
import boto3
from botocore.exceptions import ClientError

from shit.config.shitpost_settings import settings

logger = logging.getLogger(__name__)


class S3DataLake:
    """Manages raw shitpost data storage and retrieval in S3."""
    
    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME
        self.prefix = settings.S3_PREFIX
        self.s3_client = None
        
    async def initialize(self):
        """Initialize S3 client and verify bucket access."""
        try:
            # Initialize S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            # Verify bucket exists and is accessible
            await self._verify_bucket_access()
            
            logger.info(f"S3 Data Lake initialized successfully. Bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 Data Lake: {e}")
            raise
    
    async def _verify_bucket_access(self):
        """Verify S3 bucket exists and is accessible."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket {self.bucket_name} is accessible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise Exception(f"S3 bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                raise Exception(f"Access denied to S3 bucket {self.bucket_name}")
            else:
                raise Exception(f"Error accessing S3 bucket {self.bucket_name}: {e}")
    
    def _generate_s3_key(self, shitpost_id: str, post_timestamp: datetime) -> str:
        """Generate S3 key for raw shitpost data.
        
        Format: truth-social/raw/YYYY/MM/DD/post_id.json
        """
        date_str = post_timestamp.strftime("%Y/%m/%d")
        return f"{self.prefix}/raw/{date_str}/{shitpost_id}.json"
    
    async def store_raw_data(self, raw_data: Dict) -> str:
        """Store raw shitpost data in S3.
        
        Args:
            raw_data: Raw API response data
            
        Returns:
            S3 key where data was stored
        """
        try:
            shitpost_id = raw_data.get('id')
            if not shitpost_id:
                raise ValueError("Raw data must have an 'id' field")
            
            # Parse post timestamp from API data
            created_at = raw_data.get('created_at')
            if not created_at:
                raise ValueError("Raw data must have a 'created_at' field")
            
            # Convert API timestamp to datetime
            try:
                # Handle ISO format with 'Z' suffix
                if created_at.endswith('Z'):
                    created_at = created_at.replace('Z', '+00:00')
                post_timestamp = datetime.fromisoformat(created_at)
            except Exception as e:
                logger.warning(f"Could not parse timestamp {created_at}, using current time: {e}")
                post_timestamp = datetime.now()
            
            # Generate S3 key
            s3_key = self._generate_s3_key(shitpost_id, post_timestamp)
            
            # Always proceed with upload (no file existence check)
            logger.info(f"Storing data to S3: {s3_key}")
            
            # Prepare data for storage
            storage_data = {
                'shitpost_id': shitpost_id,
                'post_timestamp': post_timestamp.isoformat(),
                'raw_api_data': raw_data,
                'metadata': {
                    'stored_at': datetime.now().isoformat(),
                    'source': 'truth_social_api',
                    'version': '1.0',
                    'harvester': 'truth_social_s3_harvester'
                }
            }
            
            # Upload to S3 with timeout
            logger.info(f"Uploading data to S3: {s3_key}")
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.s3_client.put_object(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            Body=json.dumps(storage_data, indent=2),
                            ContentType='application/json',
                            Metadata={
                                'shitpost_id': shitpost_id,
                                'post_timestamp': post_timestamp.isoformat(),
                                'source': 'truth_social_api'
                            }
                        )
                    ),
                    timeout=30.0  # 30 second timeout
                )
                logger.info(f"S3 upload completed successfully: {s3_key}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout uploading to S3: {s3_key}")
                raise
            except Exception as e:
                logger.error(f"Error uploading to S3 {s3_key}: {e}")
                raise
            
            logger.info(f"Stored raw data for shitpost {shitpost_id} in S3: {s3_key}")
            return s3_key
            
        except Exception as e:
            logger.error(f"Error storing raw data in S3: {e}")
            raise
    
    async def get_raw_data(self, s3_key: str) -> Optional[Dict]:
        """Retrieve raw shitpost data from S3.
        
        Args:
            s3_key: S3 key to retrieve
            
        Returns:
            Raw data dictionary or None if not found
        """
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            )
            
            data = json.loads(response['Body'].read().decode('utf-8'))
            logger.debug(f"Retrieved raw data from S3: {s3_key}")
            return data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"Raw data not found in S3: {s3_key}")
                return None
            else:
                logger.error(f"Error retrieving raw data from S3: {e}")
                raise
        except Exception as e:
            logger.error(f"Error retrieving raw data from S3: {e}")
            raise
    
    async def list_raw_data(self, start_date: Optional[datetime] = None, 
                          end_date: Optional[datetime] = None,
                          limit: Optional[int] = None) -> List[str]:
        """List S3 keys for raw data within date range.
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of keys to return (optional)
            
        Returns:
            List of S3 keys
        """
        try:
            # Build prefix for date range
            if start_date:
                date_prefix = start_date.strftime("%Y/%m/%d")
            else:
                date_prefix = ""
            
            prefix = f"{self.prefix}/raw/{date_prefix}"
            
            # List objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            s3_keys = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        s3_keys.append(obj['Key'])
                        
                        if limit and len(s3_keys) >= limit:
                            break
                
                if limit and len(s3_keys) >= limit:
                    break
            
            logger.info(f"Found {len(s3_keys)} raw data files in S3")
            return s3_keys
            
        except Exception as e:
            logger.error(f"Error listing raw data in S3: {e}")
            return []
    
    async def stream_raw_data(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None,
                            limit: Optional[int] = None) -> AsyncGenerator[Dict, None]:
        """Stream raw shitpost data from S3.
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of records to stream (optional)
            
        Yields:
            Raw data dictionaries
        """
        try:
            s3_keys = await self.list_raw_data(start_date, end_date, limit)
            
            for s3_key in s3_keys:
                raw_data = await self.get_raw_data(s3_key)
                if raw_data:
                    yield raw_data
                    
        except Exception as e:
            logger.error(f"Error streaming raw data from S3: {e}")
            raise
    
    async def get_data_stats(self) -> Dict[str, any]:
        """Get statistics about stored raw data.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            # Count total objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            total_count = 0
            total_size = 0
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=f"{self.prefix}/raw/"):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_count += 1
                        total_size += obj['Size']
            
            return {
                'total_files': total_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'bucket': self.bucket_name,
                'prefix': self.prefix
            }
            
        except Exception as e:
            logger.error(f"Error getting S3 data stats: {e}")
            return {
                'total_files': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0,
                'bucket': self.bucket_name,
                'prefix': self.prefix
            }
    
    async def cleanup(self):
        """Cleanup S3 resources."""
        # S3 client doesn't need explicit cleanup
        logger.info("S3 Data Lake cleanup completed")
