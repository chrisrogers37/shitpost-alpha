"""ApiRouter: every /api/v1 route is defined on one, so that the schema shows every field
the API sends. A route must declare an ApiResponse model, return one (FastAPI checks it
against the model; a Response the route returned would go out unchecked) and be in the
schema. add_api_route (which the method decorators use) refuses a route that breaks this,
and create_app checks every route of each router, however it was added."""

from typing import Any

from fastapi import APIRouter
from fastapi.dependencies.utils import get_typed_return_annotation
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

    def check(self) -> None:
        """Raise TypeError if any route breaks the rules, add_route's and routes=[...]'s
        included."""
        for route in self.routes:
            problem = _problem(route)
            if problem:
                raise TypeError(f"{getattr(route, 'path', route)}: {problem}")


def _problem(route: BaseRoute) -> str | None:
    if not isinstance(route, APIRoute):
        return "an /api/v1 route must be added with add_api_route or a method decorator"
    model = route.response_model
    if not (isinstance(model, type) and issubclass(model, ApiResponse)):
        return "an /api/v1 response_model must subclass ApiResponse"
    if not route.include_in_schema:
        return "every /api/v1 route must be in the schema"
    returns = get_typed_return_annotation(route.endpoint)
    if not (isinstance(returns, type) and issubclass(returns, ApiResponse)):
        return "an /api/v1 route must be declared to return an ApiResponse"
    return None
