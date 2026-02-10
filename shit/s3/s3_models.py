"""
S3 Data Models
S3 data types, response models, and validation schemas.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class S3StorageData:
    """Model for data stored in S3."""
    
    shitpost_id: str
    post_timestamp: str
    raw_api_data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate data after initialization."""
        if not self.shitpost_id:
            raise ValueError("shitpost_id is required")
        
        if not self.post_timestamp:
            raise ValueError("post_timestamp is required")
        
        if not self.raw_api_data:
            raise ValueError("raw_api_data is required")
        
        if not self.metadata:
            raise ValueError("metadata is required")


@dataclass
class S3Stats:
    """Model for S3 storage statistics."""
    
    total_files: int
    total_size_bytes: int
    total_size_mb: float
    bucket: str
    prefix: str
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.total_size_mb = round(self.total_size_bytes / (1024 * 1024), 2)


@dataclass
class S3KeyInfo:
    """Model for S3 key information."""
    
    key: str
    size: int
    last_modified: datetime
    etag: str
    
    @property
    def is_raw_data(self) -> bool:
        """Check if this is a raw data file."""
        return "/raw/" in self.key and self.key.endswith(".json")
    
    @property
    def is_processed_data(self) -> bool:
        """Check if this is a processed data file."""
        return "/processed/" in self.key and self.key.endswith(".json")
    
    @property
    def date_path(self) -> Optional[str]:
        """Extract date path from S3 key."""
        try:
            # Extract YYYY/MM/DD from key like "truth-social/raw/2024/01/15/post_id.json"
            parts = self.key.split("/")
            if len(parts) >= 4:
                return "/".join(parts[-4:-1])  # YYYY/MM/DD
        except (IndexError, ValueError):
            pass
        return None
    
    @property
    def post_id(self) -> Optional[str]:
        """Extract post ID from S3 key."""
        try:
            # Extract post_id from key like "truth-social/raw/2024/01/15/post_id.json"
            filename = self.key.split("/")[-1]
            return filename.replace(".json", "")
        except (IndexError, ValueError):
            pass
        return None


@dataclass
class S3ProcessingResult:
    """Model for S3 processing results."""
    
    success: bool
    s3_key: str
    post_id: str
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    
    def __post_init__(self):
        """Validate result after initialization."""
        if not self.s3_key:
            raise ValueError("s3_key is required")
        
        if not self.post_id:
            raise ValueError("post_id is required")
