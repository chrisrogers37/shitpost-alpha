"""GET /healthz: whether the web process can query its database. Railway's health check
and the engine's outside check call it; it is never rate limited."""

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from engine.db import raise_if_cancelling
from engine.web.deps import Db

log = logging.getLogger(__name__)

HEALTH_TIMEOUT_SECONDS = 2.0

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
async def healthz(db: Db) -> JSONResponse:
    """{"ok": true} (200) if SELECT 1 answers within 2 s, else {"ok": false} (503)."""
    try:
        async with asyncio.timeout(HEALTH_TIMEOUT_SECONDS), db.connect() as conn:
            await conn.execute(text("SELECT 1"))
        ok = True
    except (TimeoutError, SQLAlchemyError) as exc:
        raise_if_cancelling()
        log.warning("health check failed: %s", type(exc).__name__)
        ok = False
    return JSONResponse(
        {"ok": ok}, status_code=200 if ok else 503, headers={"Cache-Control": "no-store"}
    )
