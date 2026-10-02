"""ApiRouter: every /api/v1 route is defined on one. It refuses a route whose response
model is not an ApiResponse, so every body lists its fields and carries stream_id, and a
route left out of the schema, so the schema shows every field the API sends."""

from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from engine.web.errors import ERROR_RESPONSES
from engine.web.models import ApiResponse


class ApiRouter(APIRouter):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("responses", ERROR_RESPONSES)
        super().__init__(**kwargs)

    def add_api_route(self, path: str, endpoint: Any, **kwargs: Any) -> None:
        super().add_api_route(path, endpoint, **kwargs)
        problem = _problem(self.routes[-1])  # with its response_model resolved
        if problem:
            self.routes.pop()
            raise TypeError(f"{path}: {problem}")

    def include_router(self, router: APIRouter, **kwargs: Any) -> None:
        if not isinstance(router, ApiRouter):
            raise TypeError("an ApiRouter includes only ApiRouters")
        if not kwargs.get("include_in_schema", True):
            raise TypeError("every /api/v1 route must be in the schema")
        super().include_router(router, **kwargs)


def _problem(route: BaseRoute) -> str | None:
    model = route.response_model if isinstance(route, APIRoute) else None
    if not (isinstance(model, type) and issubclass(model, ApiResponse)):
        return "an /api/v1 response_model must subclass ApiResponse"
    if isinstance(route, APIRoute) and not route.include_in_schema:
        return "every /api/v1 route must be in the schema"
    return None
