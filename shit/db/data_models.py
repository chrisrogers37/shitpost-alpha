"""
Generic Database Models
Base classes and utilities for database models across the project.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import declarative_base

# Create the base class for all models
Base = declarative_base()


class TimestampMixin:
    """Mixin class to add standard timestamp fields to models."""
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class IDMixin:
    """Mixin class to add standard ID field to models."""
    
    id = Column(Integer, primary_key=True, index=True)


def model_to_dict(model_instance) -> Dict[str, Any]:
    """Convert any SQLAlchemy model instance to dictionary.
    
    Args:
        model_instance: SQLAlchemy model instance
        
    Returns:
        Dictionary representation of the model
    """
    if not model_instance:
        return {}
    
    result = {}
    for column in model_instance.__table__.columns:
        value = getattr(model_instance, column.name)
        
        # Handle datetime objects
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        # Handle other serializable types
        else:
            result[column.name] = value
    
    return result


def get_model_fields(model_class) -> list:
    """Get list of field names for a model class.
    
    Args:
        model_class: SQLAlchemy model class
        
    Returns:
        List of field names
    """
    return [column.name for column in model_class.__table__.columns]
