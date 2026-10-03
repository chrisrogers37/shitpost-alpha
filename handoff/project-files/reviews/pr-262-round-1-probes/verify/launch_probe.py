"""Test-only launcher: the real `python -m engine web` CLI path, plus the PR's test routes
(tests/web/routes.py) and one slow route, so a real uvicorn process serves /api/v1 routes."""
import sys

from sqlalchemy import text

from engine import cli
from engine.web.app import create_app
from engine.web.deps import Db, StreamId
from engine.web.router import ApiRouter
from tests.web.routes import Probe, ProbeRoutes

extra = ApiRouter(prefix="/vt")


@extra.get("/sleep", response_model=Probe)
async def sleep(db: Db, stream_id: StreamId, s: float = 8.0) -> Probe:
    async with db.connect() as conn:
        await conn.execute(text("SELECT pg_sleep(:s)"), {"s": s})
    return Probe(stream_id=stream_id, answer=1)


probe = ProbeRoutes()
cli.create_app = lambda settings: create_app(settings, [probe.router, extra])  # type: ignore[assignment]
sys.exit(cli.main(["web"]))
