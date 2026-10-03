"""Round-2: PageParams (a query model) next to another query parameter."""
import uuid
from typing import Annotated

from fastapi import Depends, Query

from engine.web.models import ApiModel
from engine.web.paging import Page, PageParams, PageQuery, take_page
from engine.web.router import ApiRouter
from tests.web.conftest import MakeClient


class N(ApiModel):
    n: int


async def test_pageparams_with_another_query_parameter(make_client: MakeClient) -> None:
    router = ApiRouter()

    @router.get("/alone", response_model=Page[N])
    async def alone(page: PageParams) -> Page[N]:
        return Page[N](stream_id=uuid.uuid4(), items=[N(n=page.limit)], next_before=None)

    @router.get("/filtered", response_model=Page[N])
    async def filtered(page: PageParams, ticker: str | None = None) -> Page[N]:
        return Page[N](stream_id=uuid.uuid4(), items=[N(n=page.limit)], next_before=ticker)

    class FeedQuery(PageQuery):
        after: int | None = None

    @router.get("/feed", response_model=Page[N])
    async def feed(q: Annotated[FeedQuery, Query()]) -> Page[N]:
        return Page[N](stream_id=uuid.uuid4(), items=[N(n=q.limit)], next_before=str(q.after))

    @router.get("/feed_and_filter", response_model=Page[N])
    async def feed_and_filter(q: Annotated[FeedQuery, Query()], ticker: str = "x") -> Page[N]:
        return Page[N](stream_id=uuid.uuid4(), items=[N(n=q.limit)], next_before=ticker)

    client = make_client(router)
    for path in ("/alone?limit=5", "/filtered?limit=5", "/filtered?limit=5&ticker=SPY",
                 "/filtered", "/feed?limit=5&after=3", "/feed_and_filter?limit=5"):
        r = await client.get("/api/v1" + path)
        print(f"\n{path}: {r.status_code} {r.text[:160]}")
    schema = (await client.get("/api/v1/openapi.json")).json()
    params = schema["paths"]["/api/v1/filtered"]["get"].get("parameters")
    print("\n/filtered parameters in the schema:", [(p["name"], p["in"]) for p in params or []])
    body = schema["paths"]["/api/v1/filtered"]["get"].get("requestBody")
    print("/filtered requestBody:", body)
