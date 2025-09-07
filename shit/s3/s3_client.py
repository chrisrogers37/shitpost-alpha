"""
S3 Client
S3 connection management and configuration.
"""

import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from shit.config.shitpost_settings import settings
from .s3_config import S3Config

logger = logging.getLogger(__name__)


class S3Client:
    """Manages S3 connections and provides client instances."""
    
    def __init__(self, config: Optional[S3Config] = None):
        """Initialize S3 client.
        
        Args:
            config: S3 configuration (optional, uses settings if not provided)
        """
        if config:
            self.config = config
        else:
            # Create config from settings
            self.config = S3Config(
                bucket_name=settings.S3_BUCKET_NAME,
                prefix=settings.S3_PREFIX,
                region=settings.AWS_REGION,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
        
        self._client = None
        self._resource = None
    
    async def initialize(self) -> None:
        """Initialize S3 client and verify connection."""
        try:
            logger.info(f"Initializing S3 client for bucket: {self.config.bucket_name}")
            
            # Create S3 client
            self._client = boto3.client(
                's3',
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region
            )
            
            # Create S3 resource (for higher-level operations)
            self._resource = boto3.resource(
                's3',
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region
            )
            
            # Verify connection
            await self._verify_connection()
            
            logger.info("S3 client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    async def _verify_connection(self) -> None:
        """Verify S3 connection and bucket access."""
        try:
            # Test bucket access
            self._client.head_bucket(Bucket=self.config.bucket_name)
            logger.info(f"S3 bucket {self.config.bucket_name} is accessible")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise Exception(f"S3 bucket {self.config.bucket_name} does not exist")
            elif error_code == '403':
                raise Exception(f"Access denied to S3 bucket {self.config.bucket_name}")
            else:
                raise Exception(f"Error accessing S3 bucket {self.config.bucket_name}: {e}")
    
    @property
    def client(self):
        """Get S3 client instance."""
        if not self._client:
            raise RuntimeError("S3 client not initialized. Call initialize() first.")
        return self._client
    
    @property
    def resource(self):
        """Get S3 resource instance."""
        if not self._resource:
            raise RuntimeError("S3 resource not initialized. Call initialize() first.")
        return self._resource
    
    @property
    def bucket(self):
        """Get S3 bucket instance."""
        if not self._resource:
            raise RuntimeError("S3 resource not initialized. Call initialize() first.")
        return self._resource.Bucket(self.config.bucket_name)
    
    async def cleanup(self) -> None:
        """Cleanup S3 client resources."""
        # S3 clients don't need explicit cleanup
        logger.info("S3 client cleanup completed")
