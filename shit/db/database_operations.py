"""
Database Operations
Generic CRUD operations for database models.
"""

import logging
from typing import Dict, List, Optional, Any, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("database_operations")
logger = db_logger.logger

class DatabaseOperations:
    """Generic database operations for any SQLAlchemy model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, model_class: Type[DeclarativeBase], data: Dict[str, Any]) -> Any:
        """Create a new record."""
        try:
            instance = model_class(**data)
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)
            logger.debug(f"Created {model_class.__name__} with ID: {instance.id}")
            return instance
        except Exception as e:
            try:
                if self.session.in_transaction():
                    await self.session.rollback()
            except Exception:
                # Ignore rollback errors - session might already be committed
                pass
            logger.error(f"Error creating {model_class.__name__}: {e}")
            raise
    
    async def read(self, model_class: Type[DeclarativeBase], 
                   filters: Dict[str, Any] = None, 
                   limit: Optional[int] = None,
                   offset: Optional[int] = None) -> List[Any]:
        """Read records with optional filtering."""
        try:
            stmt = select(model_class)
            
            if filters:
                for key, value in filters.items():
                    if hasattr(model_class, key):
                        stmt = stmt.where(getattr(model_class, key) == value)
            
            if offset is not None:
                stmt = stmt.offset(offset)
            
            if limit is not None:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error reading {model_class.__name__}: {e}")
            raise
    
    async def read_one(self, model_class: Type[DeclarativeBase], 
                      filters: Dict[str, Any]) -> Optional[Any]:
        """Read a single record."""
        try:
            stmt = select(model_class)
            
            for key, value in filters.items():
                if hasattr(model_class, key):
                    stmt = stmt.where(getattr(model_class, key) == value)
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error reading {model_class.__name__}: {e}")
            raise
    
    async def update(self, model_class: Type[DeclarativeBase], 
                    record_id: int, data: Dict[str, Any]) -> bool:
        """Update a record by ID."""
        try:
            stmt = update(model_class).where(model_class.id == record_id).values(**data)
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            if result.rowcount > 0:
                logger.debug(f"Updated {model_class.__name__} with ID: {record_id}")
                return True
            return False
        except Exception as e:
            try:
                if self.session.in_transaction():
                    await self.session.rollback()
            except Exception:
                # Ignore rollback errors - session might already be committed
                pass
            logger.error(f"Error updating {model_class.__name__}: {e}")
            raise
    
    async def delete(self, model_class: Type[DeclarativeBase], record_id: int) -> bool:
        """Delete a record by ID."""
        try:
            stmt = delete(model_class).where(model_class.id == record_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            if result.rowcount > 0:
                logger.debug(f"Deleted {model_class.__name__} with ID: {record_id}")
                return True
            return False
        except Exception as e:
            try:
                if self.session.in_transaction():
                    await self.session.rollback()
            except Exception:
                # Ignore rollback errors - session might already be committed
                pass
            logger.error(f"Error deleting {model_class.__name__}: {e}")
            raise
    
    async def exists(self, model_class: Type[DeclarativeBase], 
                    filters: Dict[str, Any]) -> bool:
        """Check if a record exists."""
        try:
            stmt = select(model_class)
            
            for key, value in filters.items():
                if hasattr(model_class, key):
                    stmt = stmt.where(getattr(model_class, key) == value)
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Error checking existence of {model_class.__name__}: {e}")
            raise
