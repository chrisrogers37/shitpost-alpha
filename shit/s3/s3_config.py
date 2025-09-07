"""
S3 Configuration
S3-specific configuration and constants.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class S3Config:
    """S3 configuration settings."""
    
    # S3 Connection
    bucket_name: str
    prefix: str = "truth-social"
    region: str = "us-east-1"
    
    # AWS Credentials
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    
    # S3 Operations
    timeout_seconds: int = 30
    max_retries: int = 3
    chunk_size: int = 8192
    
    # Data Organization
    raw_data_prefix: str = "raw"
    processed_data_prefix: str = "processed"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.bucket_name:
            raise ValueError("S3 bucket name is required")
        
        if not self.prefix:
            raise ValueError("S3 prefix is required")
    
    @property
    def raw_prefix(self) -> str:
        """Get the full prefix for raw data."""
        return f"{self.prefix}/{self.raw_data_prefix}"
    
    @property
    def processed_prefix(self) -> str:
        """Get the full prefix for processed data."""
        return f"{self.prefix}/{self.processed_data_prefix}"
