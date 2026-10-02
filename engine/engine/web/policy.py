"""The outermost layer of the web app: what every response gets, whatever made it."""

import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from engine.web.errors import error_response

log = logging.getLogger("engine.web.access")

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

OPEN_CORS = {"Access-Control-Allow-Origin": "*"}
"""Any site may read /api/v1 with GET, without credentials. Other methods get no CORS."""


class ResponsePolicy:
    """ASGI middleware. Every response gets SECURITY_HEADERS, plus OPEN_CORS for a GET
    under /api/v1/. An exception nothing handled becomes a 500 `internal` error (its
    traceback goes to the log, never to the visitor). Each response is logged with
    method, path, status and duration, never the visitor's address."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, path = scope["method"], scope["path"]
        headers = SECURITY_HEADERS
        if method == "GET" and path.startswith("/api/v1/"):
            headers = SECURITY_HEADERS | OPEN_CORS
        status, started = 0, time.perf_counter()

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).update(headers)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            log.exception("unhandled error on %s %s", method, path)
            if status:  # the response already began; the server closes the connection
                raise
            response = error_response(path, "internal", "Internal error")
            await response(scope, receive, send_with_headers)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            printable = path.encode("unicode_escape").decode()  # no forged log lines
            log.info("%s %s %s %.0fms", method, printable, status or "-", elapsed_ms)
