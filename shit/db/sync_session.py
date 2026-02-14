"""
Synchronous Session Management
Provides synchronous database sessions for non-async operations like CLI commands and data processing.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from shit.config.shitpost_settings import settings

# Create synchronous engine based on database type
DATABASE_URL = settings.DATABASE_URL.strip('"').strip("'")

if DATABASE_URL.startswith("sqlite"):
    # SQLite - use synchronous SQLAlchemy
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    # PostgreSQL - convert async URL to sync
    sync_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
    # Strip SSL parameters that cause issues with psycopg2
    sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")

    # Try psycopg2 driver
    if not sync_url.startswith("postgresql+psycopg2://"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")

    engine = create_engine(
        sync_url,
        echo=False,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )

# Create session factory
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get a synchronous database session.

    Usage:
        with get_session() as session:
            results = session.query(Model).all()

    Yields:
        Session: SQLAlchemy session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables():
    """Create all tables in the database."""
    from shit.db.data_models import Base
    # Import all models to ensure they're registered
    from shitvault.shitpost_models import (
        TruthSocialShitpost,
        Prediction,
        MarketMovement,
        Subscriber,
        LLMFeedback,
        TelegramSubscription,
    )
    from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
    from shitvault.signal_models import Signal
    from shit.events.models import Event  # noqa: F401

    Base.metadata.create_all(engine)
