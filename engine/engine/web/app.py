"""The web app: /healthz and the /api/v1 routers, behind the rate limit and ResponsePolicy."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine.web.db import check_role, make_web_engine
from engine.web.deps import WebState
from engine.web.errors import install_error_handlers
from engine.web.health import HealthProbe, health_router
from engine.web.policy import ResponsePolicy
from engine.web.ratelimit import RateLimit, TokenBuckets
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from engine.web.stream import StreamIds

API_PREFIX = "/api/v1"

API_ROUTERS: tuple[ApiRouter, ...] = ()
"""The /api/v1 routers, mounted under API_PREFIX. Each PR that adds routes adds its own."""


def create_app(settings: WebSettings, routers: Sequence[ApiRouter] = API_ROUTERS) -> FastAPI:
    db = make_web_engine(settings)  # both connect on first use
    state = WebState(db, StreamIds(db), HealthProbe(make_web_engine(settings, pool_size=1)))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await check_role(db)
            yield
        finally:
            await state.close()

    app = FastAPI(
        title="shitpost-alpha",
        version="1",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,  # the docs pages load scripts from a CDN
        redoc_url=None,
        redirect_slashes=False,  # behind the edge it would redirect to http://; a 404 instead
        lifespan=lifespan,
    )
    app.state.web = state
    install_error_handlers(app)
    app.include_router(health_router(state.health))
    for router in routers:
        if not isinstance(router, ApiRouter):  # its routes could return anything
            raise TypeError("create_app mounts ApiRouters only")
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
