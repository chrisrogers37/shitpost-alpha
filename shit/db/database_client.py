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
        logger.info(f"Initializing database connection: {self.config.database_url}")
        
        if self.config.is_sqlite:
            async_url = self.config.database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
            self.engine = create_async_engine(
                async_url,
                echo=self.config.echo,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False}
            )
        else:
            self.engine = create_async_engine(
                self.config.database_url,
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
    
    async def cleanup(self):
        """Cleanup database resources."""
        if self.engine:
            await self.engine.dispose()
        logger.info("Database client cleanup completed")
