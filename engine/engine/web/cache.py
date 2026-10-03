"""A short in-process cache for GET response bodies, keyed by path and query string."""

import math
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from engine.web.models import ApiResponse

MAX_ENTRIES = 256


class ResponseCache[BodyT: ApiResponse]:
    """Keeps the body a route built for `ttl` seconds, and tells browsers and proxies they
    may keep it until then (`Cache-Control: public, max-age=<seconds left>`).

    Only 200s are cached: an error `build` raises is not kept. The route returns the body
    itself, so FastAPI checks a cached body against the route's model like any other.
    Usage, with the route's `request: Request` and `response: Response` parameters:

        feed_cache = ResponseCache[Feed](ttl=5)
        ...
        return await feed_cache.get(request, response, lambda: load_feed(db, ...))
    """

    def __init__(self, ttl: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl, self._clock = ttl, clock
        self._entries: OrderedDict[str, tuple[float, BodyT]] = OrderedDict()

    async def get(
        self, request: Request, response: Response, build: Callable[[], Awaitable[BodyT]]
    ) -> BodyT:
        """The body for the request's path and query string, kept or new from `build`.
        Sets Cache-Control on `response`, which FastAPI merges into the route's response."""
        key = f"{request.url.path}?{request.url.query}"
        now = self._clock()
        entry = self._entries.get(key)
        if entry is None or entry[0] <= now:
            entry = (now + self._ttl, await build())
            self._entries.pop(key, None)
            self._entries[key] = entry  # oldest first
            while len(self._entries) > MAX_ENTRIES:
                self._entries.popitem(last=False)
        expires, body = entry
        response.headers["Cache-Control"] = f"public, max-age={math.ceil(expires - now)}"
        return body

    def __len__(self) -> int:
        return len(self._entries)
