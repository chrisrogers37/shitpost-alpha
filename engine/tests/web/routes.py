"""Test-only: /api/v1 routes that exercise the conventions. No real route exists yet."""

from fastapi import Request, Response
from sqlalchemy import text

from engine.web.cache import ResponseCache
from engine.web.deps import Db, StreamId
from engine.web.errors import ApiError
from engine.web.models import ApiModel, ApiResponse
from engine.web.paging import Page, PageParams, take_page
from engine.web.router import ApiRouter

NUMBERS = list(range(50, 0, -1))  # a list of 50 rows, newest (highest) first


class Probe(ApiResponse):
    answer: int


class Number(ApiModel):
    n: int


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class ProbeRoutes:
    """A fresh router per test, with its own cache, clock and count of cache builds."""

    def __init__(self) -> None:
        self.clock = FakeClock()
        self.cache = ResponseCache(ttl=5, clock=self.clock)
        self.builds = 0
        self.router = router = ApiRouter(prefix="/test")

        @router.get("/query", response_model=Probe)
        async def query(db: Db, stream_id: StreamId) -> Probe:
            async with db.connect() as conn:
                answer = (await conn.execute(text("SELECT 42"))).scalar_one()
            return Probe(stream_id=stream_id, answer=answer)

        @router.get("/boom", response_model=Probe)
        async def boom() -> Probe:
            raise RuntimeError("secret detail that must not reach the visitor")

        @router.get("/missing", response_model=Probe)
        async def missing() -> Probe:
            raise ApiError("not_found", "No such thing")

        @router.get("/numbers", response_model=Page[Number])
        async def numbers(stream_id: StreamId, page: PageParams) -> Page[Number]:
            key = page.before_key(1)
            rows = [n for n in NUMBERS if key is None or n < key[0]][: page.limit + 1]
            items, next_before = take_page(rows, page.limit, lambda n: (n,))
            numbers = [Number(n=n) for n in items]
            return Page[Number](stream_id=stream_id, items=numbers, next_before=next_before)

        @router.get("/cached", response_model=Probe)
        async def cached(
            request: Request, db: Db, stream_id: StreamId, fail: bool = False
        ) -> Response:
            async def build() -> Probe:
                self.builds += 1
                if fail:
                    raise ApiError("not_found", "Not cached")
                async with db.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return Probe(stream_id=stream_id, answer=self.builds)

            return await self.cache.respond(request, build)
