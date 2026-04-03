"""Shared dependencies for FastAPI endpoints."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from shit.db.sync_session import SessionLocal
from shit.logging import get_service_logger

logger = get_service_logger("api")


def get_db() -> Session:
    """Get a synchronous database session."""
    return SessionLocal()


def execute_query(
    query: str, params: dict[str, Any] | None = None
) -> tuple[list, list]:
    """Execute a raw SQL query and return (rows, column_names).

    """
    try:
        with SessionLocal() as session:
            result = session.execute(text(query), params or {})
            return result.fetchall(), list(result.keys())
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise
