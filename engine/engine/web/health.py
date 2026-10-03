"""GET /healthz: whether the database answers. Railway's health check and the engine's
outside check call it. It is never rate limited, so it has its own connection and runs one
query at a time however many call: a flood of it never reaches the API's pool. That
connection checks the role when it opens (make_web_engine), so a role that holds more
than WEB_GRANTS reads as unhealthy too."""

import asyncio
import logging
import math
import time
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.db import raise_if_cancelling
from engine.web.db import failure_line

log = logging.getLogger(__name__)

HEALTH_TIMEOUT_SECONDS = 2.0
"""Longest /healthz waits for an answer."""
FRESH_SECONDS = 1.0
"""How long an answer is reused for later callers."""


class HealthProbe:
    """SELECT 1 on `db` (a one-connection engine). Callers that arrive while a query runs
    wait on that query; an answer is reused for FRESH_SECONDS."""

    def __init__(self, db: AsyncEngine, clock: Callable[[], float] = time.monotonic) -> None:
        self.db, self._clock = db, clock
        self._query: asyncio.Task[bool] | None = None
        self._answered_at = -math.inf

    async def ok(self) -> bool:
        """Whether the database answered, within HEALTH_TIMEOUT_SECONDS of this call. A
        query the driver is still winding down (psycopg's cancel can take 10 s) keeps
        running, and callers meanwhile get False on time."""
        query = self._query
        if query is None or (query.done() and self._clock() - self._answered_at >= FRESH_SECONDS):
            query = self._query = asyncio.create_task(self._select_1())
        done, _ = await asyncio.wait({query}, timeout=HEALTH_TIMEOUT_SECONDS)
        return bool(done) and not query.cancelled() and query.result()

    async def _select_1(self) -> bool:
        try:
            async with asyncio.timeout(HEALTH_TIMEOUT_SECONDS), self.db.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            raise_if_cancelling()
            log.warning("health check failed: %s", failure_line(exc))
            return False
        finally:
            self._answered_at = self._clock()

    async def close(self) -> None:
        """Stop a query still running, then close the connection. psycopg answers a cancel
        by winding the query down for up to 10 s; a second cancel cuts that short."""
        for _ in range(2):
            if self._query is None or self._query.done():
                break
            self._query.cancel()
            await asyncio.wait({self._query}, timeout=1)
        await self.db.dispose()


def health_router(probe: HealthProbe) -> APIRouter:
    router = APIRouter()

    @router.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
    async def healthz() -> JSONResponse:  # uptime checkers often send HEAD
        """{"ok": true} (200) if the database answered SELECT 1 within 2 s, else
        {"ok": false} (503)."""
        ok = await probe.ok()
        return JSONResponse(
            {"ok": ok}, status_code=200 if ok else 503, headers={"Cache-Control": "no-store"}
        )

    return router
