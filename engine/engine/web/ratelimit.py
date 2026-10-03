"""Per-visitor rate limit: an in-memory token bucket for each visitor address."""

import ipaddress
import logging
import math
import time
from collections import OrderedDict
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from engine.web.errors import error_response

log = logging.getLogger(__name__)

UNLIMITED_PATHS = frozenset({"/healthz"})
MAX_BUCKETS = 50_000
WARN_EVERY_SECONDS = 300.0


class TokenBuckets:
    """`per_minute` tokens a minute per key, holding at most `burst`. Buckets idle long
    enough to have refilled are dropped (a full bucket is the same as none), and past
    `max_buckets` the least recently used goes, so the table stays bounded."""

    def __init__(
        self,
        per_minute: float,
        burst: int,
        max_buckets: int = MAX_BUCKETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate, self._burst = per_minute / 60, float(burst)
        self._max_buckets, self._clock = max_buckets, clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()  # tokens, at

    def take(self, key: str) -> float:
        """Spend a token for `key`: 0 if it had one, else the seconds until it will."""
        now = self._clock()
        refill_seconds = self._burst / self._rate
        while self._buckets:  # least recently used first
            oldest, (_, at) = next(iter(self._buckets.items()))
            if now - at < refill_seconds:
                break
            del self._buckets[oldest]
        tokens, at = self._buckets.pop(key, (self._burst, now))
        tokens = min(self._burst, tokens + (now - at) * self._rate)
        if tokens >= 1:
            tokens, wait = tokens - 1, 0.0
        else:
            wait = (1 - tokens) / self._rate
        self._buckets[key] = (tokens, now)  # now the most recently used
        if len(self._buckets) > self._max_buckets:
            self._buckets.popitem(last=False)
        return wait

    def __len__(self) -> int:
        return len(self._buckets)


def edge_address(scope: Scope, header: str, trusted_hops: int) -> str | None:
    """The visitor's address as the edge proxy saw it: the entry `trusted_hops` from the
    right of `header` (all its lines, comma-separated), never one the visitor wrote to its
    left. None when the header is absent, short or not an address. IPv6 addresses count
    per /64, the block one subscriber usually holds."""
    name = header.lower().encode("latin-1")
    entries = [
        entry.strip()
        for key, value in scope["headers"]
        if key == name
        for entry in value.decode("latin-1").split(",")
    ]
    return _parse(entries[-trusted_hops]) if len(entries) >= trusted_hops else None


def socket_address(scope: Scope) -> str | None:
    client = scope.get("client")
    return _parse(client[0]) if client else None


def _parse(text: str) -> str | None:
    try:
        address = ipaddress.ip_address(text)
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped is not None:
                return str(address.ipv4_mapped)
            return str(ipaddress.IPv6Network((address, 64), strict=False))
    except ValueError:
        return None
    return str(address)


class RateLimit:
    """ASGI middleware: 429 with Retry-After once a visitor's bucket is empty. Requests
    that reach it from another machine without a usable header entry count by the socket
    address, which behind a proxy is the proxy's, so every visitor shares one bucket: it
    logs a warning about that at most every WARN_EVERY_SECONDS."""

    def __init__(
        self,
        app: ASGIApp,
        buckets: TokenBuckets,
        header: str,
        trusted_hops: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.app, self.buckets = app, buckets
        self.header, self.trusted_hops = header, trusted_hops
        self._clock, self._warned_at = clock, -math.inf

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] not in UNLIMITED_PATHS:
            wait = self.buckets.take(self._address(scope))
            if wait > 0:
                retry_after = {"Retry-After": str(math.ceil(wait))}
                response = error_response(
                    scope["path"], "rate_limited", "Too many requests", headers=retry_after
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

    def _address(self, scope: Scope) -> str:
        """The edge's entry in the header, else the socket address."""
        address = edge_address(scope, self.header, self.trusted_hops)
        if address is None:
            address = socket_address(scope) or "unknown"
            if not _from_this_machine(scope):
                self._warn_no_header()
        return address

    def _warn_no_header(self) -> None:
        if self._clock() - self._warned_at >= WARN_EVERY_SECONDS:
            self._warned_at = self._clock()
            log.warning(
                "a request had no usable %s entry (%d from the right); counting it by the "
                "socket address, which behind a proxy puts every visitor in one bucket",
                self.header,
                self.trusted_hops,
            )


def _from_this_machine(scope: Scope) -> bool:
    client = scope.get("client")
    try:
        return client is None or ipaddress.ip_address(client[0]).is_loopback
    except ValueError:
        return False
