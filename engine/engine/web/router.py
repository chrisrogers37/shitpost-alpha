"""ApiRouter: every /api/v1 route is defined on one, so that the schema shows the fields
the API sends. A route must declare an ApiResponse model and return one (FastAPI checks
what it returns against the model; a Response or a stream would go out unchecked), be in
the schema, and document only errors besides its model. ApiRouter checks each route as it
is added and takes no other kind of route, so a router can include another (FastAPI keeps
an included router as a live reference) and routes added later are checked too."""

import inspect
from typing import Any, NoReturn

from fastapi import APIRouter
from fastapi.dependencies.utils import get_typed_return_annotation
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from engine.web.errors import ERROR_RESPONSES
from engine.web.models import ApiResponse

NOT_AN_API_ROUTE = "an ApiRouter takes only routes added with add_api_route or a decorator"


class ApiRouter(APIRouter):
    def __init__(self, **kwargs: Any) -> None:
        if kwargs.get("routes"):
            raise TypeError(NOT_AN_API_ROUTE)
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
        if not (self.include_in_schema and kwargs.get("include_in_schema", True)):
            raise TypeError("every /api/v1 route must be in the schema")
        if not _errors_only(kwargs.get("responses") or {}):
            raise TypeError("an include documents errors only")
        super().include_router(router, **kwargs)

    def _not_an_api_route(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise TypeError(NOT_AN_API_ROUTE)

    # Starlette's and FastAPI's other ways to add a route, none of which checks it.
    add_route = add_websocket_route = add_api_websocket_route = _not_an_api_route
    mount = host = frontend = _not_an_api_route


def _problem(route: BaseRoute) -> str | None:
    if not isinstance(route, APIRoute):
        return NOT_AN_API_ROUTE
    model = route.response_model
    if not (isinstance(model, type) and issubclass(model, ApiResponse)):
        return "an /api/v1 response_model must subclass ApiResponse"
    if not route.include_in_schema:
        return "every /api/v1 route must be in the schema"
    returns = get_typed_return_annotation(route.endpoint)
    if not (isinstance(returns, type) and issubclass(returns, ApiResponse)):
        return "an /api/v1 route must be declared to return an ApiResponse"
    endpoint = inspect.unwrap(route.endpoint)
    if inspect.isasyncgenfunction(endpoint) or inspect.isgeneratorfunction(endpoint):
        return "an /api/v1 route returns its model, not a stream"
    if not _errors_only(route.responses) or route.openapi_extra:
        return "an /api/v1 route documents its model and errors only"
    return None


def _errors_only(responses: dict[int | str, Any]) -> bool:
    """Whether `responses` documents only errors (4xx or 5xx), so the schema's success
    response is the route's own model."""
    return all(str(code)[:1] in ("4", "5") for code in responses)
