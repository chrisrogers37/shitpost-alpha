"""GET /healthz (fix sketch from the verify pass, not part of the PR)."""

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.web.deps import Db

log = logging.getLogger(__name__)

HEALTH_TIMEOUT_SECONDS = 2.0

router = APIRouter()


async def _select_1(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        await conn.execute(text("SELECT 1"))


def _log_failure(task: "asyncio.Task[None]") -> None:
    if not task.cancelled() and task.exception() is not None:
        log.warning("health check failed: %s", type(task.exception()).__name__)


@router.get("/healthz", include_in_schema=False)
async def healthz(db: Db) -> JSONResponse:
    probe = asyncio.create_task(_select_1(db))
    probe.add_done_callback(_log_failure)
    done, _ = await asyncio.wait({probe}, timeout=HEALTH_TIMEOUT_SECONDS)
    ok = bool(done) and not probe.cancelled() and probe.exception() is None
    if not done:
        log.warning("health check failed: no answer in %ss", HEALTH_TIMEOUT_SECONDS)
        probe.cancel()  # the driver's cancel and cleanup carry on without holding the answer
    return JSONResponse(
        {"ok": ok}, status_code=200 if ok else 503, headers={"Cache-Control": "no-store"}
    )
