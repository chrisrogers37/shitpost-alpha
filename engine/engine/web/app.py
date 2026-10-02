"""The web app: /healthz and the /api/v1 routers, behind the rate limit and ResponsePolicy."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine.web import health
from engine.web.db import make_web_engine
from engine.web.deps import WebState
from engine.web.errors import install_error_handlers
from engine.web.policy import ResponsePolicy
from engine.web.ratelimit import RateLimit, TokenBuckets
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from engine.web.stream import StreamIds

API_PREFIX = "/api/v1"

API_ROUTERS: tuple[ApiRouter, ...] = ()
"""The /api/v1 routers, mounted under API_PREFIX. Each PR that adds routes adds its own."""


def create_app(settings: WebSettings, routers: Sequence[ApiRouter] = API_ROUTERS) -> FastAPI:
    db = make_web_engine(settings)  # connects on first use

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await db.dispose()

    app = FastAPI(
        title="shitpost-alpha",
        version="1",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,  # the docs pages load scripts from a CDN
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.web = WebState(db=db, stream_ids=StreamIds(db))
    install_error_handlers(app)
    app.include_router(health.router)
    for router in routers:
        app.include_router(router, prefix=API_PREFIX)

    buckets = TokenBuckets(settings.rate_limit_per_minute, settings.rate_limit_burst)
    app.add_middleware(
        RateLimit,
        buckets=buckets,
        header=settings.client_ip_header,
        trusted_hops=settings.trusted_hops,
    )
    app.add_middleware(ResponsePolicy)  # added last, so it wraps the rate limit too
    return app
