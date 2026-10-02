"""Error responses. Under /api/ every error is {"error": {"code", "message"}}; elsewhere
it is plain text with the same status. Never a stack trace."""

import logging
from collections.abc import Mapping
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException

from engine.web.db import failure_line

log = logging.getLogger(__name__)

ErrorCode = Literal["bad_request", "not_found", "rate_limited", "unavailable", "internal"]

STATUS: dict[ErrorCode, int] = {
    "bad_request": 400,
    "not_found": 404,
    "rate_limited": 429,
    "unavailable": 503,
    "internal": 500,
}


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorBody(BaseModel):
    """The body of every error under /api/."""

    error: ErrorDetail


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    "4XX": {"model": ErrorBody, "description": "Client error (bad_request, not_found, ...)"},
    "5XX": {"model": ErrorBody, "description": "Server error (unavailable, internal)"},
}
"""Every ApiRouter's documented errors. Declaring 4XX also stops FastAPI from listing a 422
it never sends: bad parameters are a 400."""


class ApiError(Exception):
    """Raise from a route to answer with `code`, its status and `message`."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def is_api(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def error_response(
    path: str,
    code: ErrorCode,
    message: str,
    status: int | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """The error for a request to `path`; `status` defaults to the code's."""
    status = status or STATUS[code]
    if is_api(path):
        body = {"error": {"code": code, "message": message}}
        return JSONResponse(body, status_code=status, headers=headers)
    return PlainTextResponse(message, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    """Handlers for errors raised inside the app. Anything unhandled is ResponsePolicy's."""

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> Response:
        return error_response(request.url.path, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        # Routing's own errors: unknown path (404) and wrong method (405, kept with Allow).
        if exc.status_code == 404:
            code: ErrorCode = "not_found"
        elif exc.status_code < 500:
            code = "bad_request"
        else:
            code = "internal"
        message = "Not found" if code == "not_found" else str(exc.detail)
        return error_response(request.url.path, code, message, exc.status_code, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def bad_request(request: Request, exc: RequestValidationError) -> Response:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc'][1:])) or e['loc'][0]}: {e['msg']}" for e in exc.errors()
        )
        return error_response(request.url.path, "bad_request", problems)

    @app.exception_handler(OperationalError)  # refused, lost, timed out
    @app.exception_handler(PoolTimeoutError)  # every connection busy
    async def unavailable(request: Request, exc: Exception) -> Response:
        log.warning("database unavailable on %s: %s", request.url.path, failure_line(exc))
        return error_response(request.url.path, "unavailable", "The database is unavailable")
