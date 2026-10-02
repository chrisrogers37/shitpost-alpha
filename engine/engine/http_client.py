"""HTTP for everything the engine fetches: one client with an honest User-Agent and no
redirects, and error text that never carries a key."""

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version

import httpx

from engine.settings import Settings

SECRET_HEADERS = frozenset({"x-api-key"})
"""Request headers that carry a key (lowercase). Their values never reach error text."""

KEEPALIVE_SECONDS = 75.0
"""Longer than the 15 s and 60 s poll intervals, so those feeds reuse their connection."""


def _engine_version() -> str:
    try:
        return version("shitpost-engine")
    except PackageNotFoundError:
        return "unknown"


USER_AGENT = (
    f"shitpost-alpha-engine/{_engine_version()} (+https://github.com/chrisrogers37/shitpost-alpha)"
)


def make_client(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    # No redirects: none of the engine's URLs redirect, a redirect to a login or challenge
    # page is a failure, and httpx would carry a key header to another host.
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=settings.http_timeout_seconds,
        limits=httpx.Limits(  # httpx's default caps, which a Limits without them drops
            max_connections=100, max_keepalive_connections=20, keepalive_expiry=KEEPALIVE_SECONDS
        ),
        follow_redirects=False,
        transport=transport,
    )


def request_error_text(exc: httpx.HTTPError, *sent: Mapping[str, str]) -> str:
    """`exc` as text for logs, status rows and operator messages, with the value of every
    key header in `sent` (the client's headers, the request's) blanked out: httpx's
    protocol errors quote a header value they refuse."""
    text = f"{type(exc).__name__}: {exc}"
    for headers in sent:
        for name, value in headers.items():
            if name.lower() in SECRET_HEADERS and (key := value.strip()):
                for shown in (repr(key.encode())[2:-1], key):  # as bytes, then as text
                    text = text.replace(shown, "[key]")
    return text
