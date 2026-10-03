"""What routes get from the app: the database and the stream_id. Use them as parameter
types, for example `async def route(db: Db, stream_id: StreamId) -> SomeResponse`."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.web.health import HealthProbe
from engine.web.stream import StreamIds


@dataclass(frozen=True)
class WebState:
    db: AsyncEngine
    stream_ids: StreamIds
    health: HealthProbe

    async def close(self) -> None:
        await self.health.close()
        await self.db.dispose()


def web_state(request: Request) -> WebState:
    state = request.app.state.web
    assert isinstance(state, WebState)
    return state


async def _db(request: Request) -> AsyncEngine:  # async: no worker thread
    return web_state(request).db


async def _stream_id(request: Request) -> UUID:
    return await web_state(request).stream_ids.get()


Db = Annotated[AsyncEngine, Depends(_db)]
StreamId = Annotated[UUID, Depends(_stream_id)]
