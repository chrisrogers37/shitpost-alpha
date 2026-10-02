"""A short in-process cache for GET responses, keyed by path and query string."""

import math
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from engine.web.models import ApiResponse

MAX_ENTRIES = 256


class ResponseCache:
    """Serves a route's response from memory for `ttl` seconds, and tells browsers and
    proxies they may keep it until then (`Cache-Control: public, max-age=<seconds left>`).

    Only 200s are cached: `build` returns the body, and an error it raises is not kept.
    Usage: `return await cache.respond(request, lambda: load_body(db, ...))`.
    """

    def __init__(self, ttl: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl, self._clock = ttl, clock
        self._entries: OrderedDict[str, tuple[float, bytes]] = OrderedDict()

    async def respond(
        self, request: Request, build: Callable[[], Awaitable[ApiResponse]]
    ) -> Response:
        key = f"{request.url.path}?{request.url.query}"
        now = self._clock()
        hit = self._entries.get(key)
        if hit is not None and hit[0] > now:
            expires, body = hit
        else:
            expires, body = now + self._ttl, (await build()).model_dump_json().encode()
            self._entries.pop(key, None)
            self._entries[key] = (expires, body)  # oldest first
            while len(self._entries) > MAX_ENTRIES:
                self._entries.popitem(last=False)
        return Response(
            body,
            media_type="application/json",
            headers={"Cache-Control": f"public, max-age={math.ceil(expires - now)}"},
        )

    def __len__(self) -> int:
        return len(self._entries)
