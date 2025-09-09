"""
Database Client
Database connection management and session handling.
Extracted from ShitpostDatabase for reusability.
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typing import Optional

from .database_config import DatabaseConfig
from .data_models import Base

logger = logging.getLogger(__name__)

class DatabaseClient:
    """Manages database connections and provides session instances."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.SessionLocal = None
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        # Hide sensitive information in logs
        safe_url = self._mask_database_url(self.config.database_url)
        logger.info(f"Initializing database connection: {safe_url}")
        
        if self.config.is_sqlite:
            async_url = self.config.database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
            self.engine = create_async_engine(
                async_url,
                echo=self.config.echo,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False}
            )
        else:
            # For PostgreSQL, ensure we use the async psycopg driver
            postgres_url = self.config.database_url
            if postgres_url.startswith('postgresql://'):
                # Replace postgresql:// with postgresql+psycopg:// for async support
                postgres_url = postgres_url.replace('postgresql://', 'postgresql+psycopg://')
            
            self.engine = create_async_engine(
                postgres_url,
                echo=self.config.echo,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle
            )
        
        self.SessionLocal = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database connection initialized and tables created successfully")
    
    def get_session(self) -> AsyncSession:
        """Get database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database client not initialized. Call initialize() first.")
        return self.SessionLocal()
    
    def _mask_database_url(self, url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        if not url:
            return "None"
        
        # For SQLite, just show the path
        if url.startswith('sqlite'):
            return f"sqlite:///{url.split('/')[-1]}" if '/' in url else url
        
        # For PostgreSQL, mask password and sensitive parts
        if url.startswith('postgresql'):
            try:
                # Parse the URL to extract components
                if '@' in url:
                    # Extract the part before @ (contains user:password)
                    auth_part = url.split('@')[0]
                    if '://' in auth_part:
                        protocol = auth_part.split('://')[0] + '://'
                        user_pass = auth_part.split('://')[1]
                        if ':' in user_pass:
                            user = user_pass.split(':')[0]
                            masked_auth = f"{user}:***"
                        else:
                            masked_auth = user_pass
                        
                        # Reconstruct with masked password
                        rest_of_url = url.split('@')[1]
                        return f"{protocol}{masked_auth}@{rest_of_url}"
                
                return url
            except Exception:
                # If parsing fails, return a generic masked version
                return "postgresql://***:***@***"
        
        # For other URLs, just return as-is
        return url
    
    async def cleanup(self):
        """Cleanup database resources."""
        if self.engine:
            await self.engine.dispose()
        logger.info("Database client cleanup completed")
