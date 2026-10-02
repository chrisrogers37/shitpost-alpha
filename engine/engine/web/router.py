"""ApiRouter: every /api/v1 route is defined on one. It refuses a route whose response
model is not an ApiResponse, so every body lists its fields and carries stream_id."""

from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute

from engine.web.errors import ERROR_RESPONSES
from engine.web.models import ApiResponse


class ApiRouter(APIRouter):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("responses", ERROR_RESPONSES)
        super().__init__(**kwargs)

    def add_api_route(self, path: str, endpoint: Any, **kwargs: Any) -> None:
        super().add_api_route(path, endpoint, **kwargs)
        route = self.routes[-1]  # with its response_model resolved (or read from the hint)
        model = route.response_model if isinstance(route, APIRoute) else None
        if not (isinstance(model, type) and issubclass(model, ApiResponse)):
            self.routes.pop()
            raise TypeError(f"{path}: an /api/v1 response_model must subclass ApiResponse")

    def include_router(self, router: APIRouter, **kwargs: Any) -> None:
        if not isinstance(router, ApiRouter):
            raise TypeError("an ApiRouter includes only ApiRouters")
        super().include_router(router, **kwargs)
