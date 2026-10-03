"""Round-2: ways a price field reaches a client while ApiRouter, ApiModel and the
no-prices walk (tests/web/test_no_prices.py) all pass."""
import uuid
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import computed_field, model_serializer
from starlette.routing import Route

from engine.web.app import create_app
from engine.web.cache import ResponseCache
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from tests.web.conftest import NO_DATABASE, MakeClient
from tests.web.routes import Probe
from tests.web.test_no_prices import price_fields


async def _show(client: Any, router: ApiRouter, path: str, label: str) -> None:
    r = await client.get("/api/v1" + path)
    walk = price_fields(create_app(NO_DATABASE, [router]))
    print(f"\n{label}: {r.status_code} {r.text[:120]} | walk finds {walk or 'nothing'}")


async def test_bypasses(make_client: MakeClient) -> None:
    sid = uuid.uuid4()

    # 1. A route that declares an ApiResponse but returns a Response of its own.
    r1 = ApiRouter()

    @r1.get("/raw", response_model=Probe)
    async def raw() -> Response:
        return JSONResponse({"stream_id": str(sid), "close_price": 187.23})

    # 2. The cache helper: build returns another ApiResponse than the declared model.
    class Detail(ApiResponse):
        entry_close_price: float

    cache = ResponseCache(ttl=5)
    r2 = ApiRouter()

    @r2.get("/cached", response_model=Probe)
    async def cached(request: Request) -> Response:
        async def build() -> Detail:
            return Detail(stream_id=sid, entry_close_price=187.23)

        return await cache.respond(request, build)

    # 3. A plain Starlette route added to an ApiRouter.
    r3 = ApiRouter()

    async def starlette_endpoint(request: Request) -> Response:
        return JSONResponse({"close_price": 187.23})

    r3.add_route("/starlette", starlette_endpoint)

    # 3b. Routes given to the constructor.
    r3b = ApiRouter(routes=[Route("/ctor", starlette_endpoint)])

    # 4. computed_field with an alias.
    class Computed(ApiResponse):
        cents: int

        @computed_field(alias="px")  # type: ignore[prop-decorator]
        @property
        def close_price(self) -> float:
            return self.cents / 100

    r4 = ApiRouter()
    cache4 = ResponseCache(ttl=5)

    @r4.get("/computed", response_model=Computed)
    async def computed() -> Computed:
        return Computed(stream_id=sid, cents=18723)

    @r4.get("/computed_cached", response_model=Computed)
    async def computed_cached(request: Request) -> Response:
        async def build() -> Computed:
            return Computed(stream_id=sid, cents=18723)

        return await cache4.respond(request, build)

    # 5. A model_serializer that adds a key.
    class Serialized(ApiResponse):
        cents: int

        @model_serializer(mode="wrap")
        def _out(self, handler: Any) -> Any:
            body = handler(self)
            body["close_price"] = self.cents / 100
            return body

    r5 = ApiRouter()

    @r5.get("/serialized", response_model=Serialized)
    async def serialized() -> Serialized:
        return Serialized(stream_id=sid, cents=18723)

    client = make_client(r1, r2, r3, r3b, r4, r5)
    await _show(client, r1, "/raw", "1 Response returned")
    await _show(client, r2, "/cached", "2 cache builds another model")
    await _show(client, r3, "/starlette", "3 ApiRouter.add_route")
    await _show(client, r3b, "/ctor", "3b ApiRouter(routes=...)")
    await _show(client, r4, "/computed", "4 computed_field alias (route)")
    await _show(client, r4, "/computed_cached", "4 computed_field alias (cache)")
    await _show(client, r5, "/serialized", "5 model_serializer adds a key")
