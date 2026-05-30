"""Shared dependencies for FastAPI endpoints."""

import hmac  # noqa: F401 — used in verify_api_key
from typing import Any

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.orm import Session

from shit.config.shitpost_settings import settings
from shit.db.sync_session import SessionLocal
from shit.logging import get_service_logger

logger = get_service_logger("api")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Verify the API key from the X-API-Key header.

    When API_KEY is not configured, all requests are allowed (open mode).
    When configured, requests must provide a matching key.
    """
    if not settings.API_KEY:
        return None
    if not api_key or not hmac.compare_digest(api_key, settings.API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


def get_db() -> Session:
    """Get a synchronous database session."""
    return SessionLocal()


def execute_query(
    query: str, params: dict[str, Any] | None = None
) -> tuple[list, list]:
    """Execute a raw SQL query and return (rows, column_names)."""
    try:
        with SessionLocal() as session:
            result = session.execute(text(query), params or {})
            return result.fetchall(), list(result.keys())
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise
