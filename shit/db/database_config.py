"""
Database Configuration
Database-specific configuration and constants.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    
    # Database Connection
    database_url: str
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # Connection Options
    connect_args: Optional[dict] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.database_url:
            raise ValueError("Database URL is required")
    
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith('sqlite')
    
    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return self.database_url.startswith('postgresql')
