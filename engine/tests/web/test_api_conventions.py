import logging
import uuid
from typing import Annotated, Any, cast

import psycopg
import pytest
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    SerializerFunctionWrapHandler,
    WithJsonSchema,
    WrapSerializer,
    computed_field,
    field_serializer,
    model_serializer,
)
from pydantic.alias_generators import to_camel
from pydantic.json_schema import SkipJsonSchema
from starlette.routing import Route

from engine.web.app import create_app
from engine.web.db import make_web_engine
from engine.web.deps import StreamId
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from engine.web.stream import StreamIds
from tests.web.api_checks import assert_security_headers
from tests.web.conftest import NO_DATABASE, MakeClient
from tests.web.routes import FakeClock, Probe, ProbeRoutes


async def test_an_unknown_api_path_is_a_json_404_with_every_header(
    make_client: MakeClient,
) -> None:
    response = await make_client().get("/api/v1/x")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not found"}}
    assert_security_headers(response)
    assert response.headers["access-control-allow-origin"] == "*"
    assert "server" not in response.headers


async def test_a_trailing_slash_is_a_404_not_a_redirect(make_client: MakeClient) -> None:
    # Behind the TLS edge the app sees http, so a redirect would send visitors to http://.
    response = await make_client().get("/api/v1/openapi.json/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_errors_outside_the_api_are_plain_text(make_client: MakeClient) -> None:
    response = await make_client().get("/nothing-here")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "Not found"
    assert_security_headers(response)
    assert "access-control-allow-origin" not in response.headers


async def test_route_errors_use_the_error_shape(make_client: MakeClient) -> None:
    client = make_client(ProbeRoutes().router)

    missing = await client.get("/api/v1/test/missing")
    assert (missing.status_code, missing.json()) == (
        404,
        {"error": {"code": "not_found", "message": "No such thing"}},
    )

    wrong_method = await client.post("/api/v1/test/missing")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "bad_request"
    assert wrong_method.headers["allow"] == "GET"


async def test_an_unhandled_error_is_a_500_without_its_details(
    make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = await make_client(ProbeRoutes().router).get("/api/v1/test/boom")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal", "message": "Internal error"}}
    assert "secret" not in response.text
    assert_security_headers(response)
    assert any("secret detail" in str(r.exc_info[1]) for r in caplog.records if r.exc_info)


async def test_the_unhandled_error_line_escapes_the_path(
    make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    router = ApiRouter()

    @router.get("/signals/{public_id}", response_model=Probe)
    async def signal(public_id: str) -> Probe:
        raise RuntimeError("boom")

    await make_client(router).get("/api/v1/signals/a%0A2026-10-02 INFO engine: forged")
    (line,) = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert line == "unhandled error on GET /api/v1/signals/a\\n2026-10-02 INFO engine: forged"


async def test_cors_is_open_to_get_only(make_client: MakeClient) -> None:
    client = make_client(ProbeRoutes().router)
    origin = {"Origin": "https://elsewhere.example"}

    get = await client.get("/api/v1/test/query", headers=origin)
    assert get.status_code == 200
    assert get.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in get.headers

    for method in ("HEAD", "POST", "PUT", "DELETE", "OPTIONS"):
        other = await client.request(method, "/api/v1/test/query", headers=origin)
        assert "access-control-allow-origin" not in other.headers, method
    preflight = await client.options(
        "/api/v1/test/query", headers=origin | {"Access-Control-Request-Method": "POST"}
    )
    assert not any(name.startswith("access-control-") for name in preflight.headers)

    health = await client.get("/healthz", headers=origin)
    assert "access-control-allow-origin" not in health.headers


async def test_every_response_body_carries_the_stream_id(
    make_client: MakeClient, database_url: str
) -> None:
    client = make_client(ProbeRoutes().router)
    with psycopg.connect(database_url) as conn:
        (stream_id,) = conn.execute("SELECT stream_id FROM engine.engine_meta").fetchone() or ()

    response = await client.get("/api/v1/test/query")
    assert response.json() == {"stream_id": str(stream_id), "answer": 42}
    assert_security_headers(response)


async def test_stream_id_is_read_once_a_minute(database_url: str, web_url: str) -> None:
    clock = FakeClock()
    db = make_web_engine(WebSettings(database_url=web_url))
    stream_ids = StreamIds(db, clock=clock)
    try:
        first = await stream_ids.get()
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE engine.engine_meta SET stream_id = %s", (uuid.uuid4(),))
        clock.now += 59
        assert await stream_ids.get() == first
        clock.now += 1
        assert await stream_ids.get() != first
    finally:
        await db.dispose()


def test_every_api_route_must_declare_an_api_response() -> None:
    class Bare(BaseModel):
        answer: int

    router = ApiRouter()
    for model in (Bare, None):
        with pytest.raises(TypeError, match="must subclass ApiResponse"):
            router.add_api_route("/bare", lambda: {"answer": 1}, response_model=model)
    with pytest.raises(TypeError, match="must subclass ApiResponse"):

        @router.get("/hinted")
        async def hinted() -> dict[str, int]:
            return {"answer": 1}

    with pytest.raises(TypeError, match="includes only ApiRouters"):
        router.include_router(APIRouter())

    @router.get("/good")
    async def good() -> Probe:
        return Probe(stream_id=uuid.uuid4(), answer=1)

    assert [getattr(route, "path", None) for route in router.routes] == ["/good"]
    create_app(NO_DATABASE, [router])
    with pytest.raises(TypeError, match="ApiRouters only"):
        create_app(NO_DATABASE, [APIRouter()])  # type: ignore[list-item]


def test_every_api_route_returns_its_model() -> None:
    router = ApiRouter()
    with pytest.raises(TypeError, match="declared to return an ApiResponse"):

        @router.get("/raw", response_model=Probe)
        async def raw() -> JSONResponse:  # a Response goes out unchecked
            return JSONResponse({"close_price": 187.23})

    with pytest.raises(TypeError, match="declared to return an ApiResponse"):

        @router.get("/row", response_model=Probe)
        async def row() -> dict[str, object]:
            return {"close_price": 187.23}

    with pytest.raises(TypeError, match="not a stream"):

        @router.get("/stream", response_model=Probe)
        async def stream() -> Probe:  # type: ignore[misc]  # FastAPI streams what it yields
            yield {"close_price": 187.23}

    for documented in ({"responses": {200: {"model": Probe}}}, {"openapi_extra": {"x": 1}}):
        with pytest.raises(TypeError, match="documents its model and errors only"):

            @router.get("/documented", **documented)
            async def other() -> Probe:  # the schema would show another body than it sends
                return Probe(stream_id=uuid.uuid4(), answer=1)

    assert router.routes == []


def test_an_api_router_takes_no_other_kind_of_route() -> None:
    async def plain(request: Request) -> Response:
        return JSONResponse({"close_price": 187.23})

    router = ApiRouter()
    for add in (
        lambda: router.add_route("/plain", plain),
        lambda: router.route("/plain")(plain),
        lambda: router.mount("/static", app=plain),
        lambda: router.host("example.com", app=plain),
        lambda: router.add_websocket_route("/ws", plain),
        lambda: router.add_api_websocket_route("/ws", plain),
        lambda: router.frontend("/", directory="."),
        lambda: ApiRouter(routes=[Route("/plain", plain)]),
    ):
        with pytest.raises(TypeError, match="takes only routes added with add_api_route"):
            add()
    assert router.routes == []


async def test_an_api_router_can_include_another(make_client: MakeClient) -> None:
    inner = ApiRouter(prefix="/inner")

    @inner.get("/ok")
    async def ok(stream_id: StreamId) -> Probe:
        return Probe(stream_id=stream_id, answer=1)

    outer = ApiRouter()
    outer.include_router(inner)
    client = make_client(outer)
    response = await client.get("/api/v1/inner/ok")
    assert (response.status_code, response.json()["answer"]) == (200, 1)
    paths = (await client.get("/api/v1/openapi.json")).json()["paths"]
    assert set(paths) == {"/api/v1/inner/ok"}

    # FastAPI 0.137 and later serve whatever routes an included router has when a request
    # comes, so a route added after create_app goes live: it is checked as it is added.
    with pytest.raises(TypeError, match="declared to return an ApiResponse"):

        @inner.get("/raw", response_model=Probe)
        async def raw() -> JSONResponse:
            return JSONResponse({"close_price": 187.23})

    assert (await client.get("/api/v1/inner/raw")).status_code == 404
    with pytest.raises(TypeError, match="errors only"):
        outer.include_router(ApiRouter(), responses={200: {"model": Probe}})


def test_every_api_route_is_in_the_schema() -> None:
    router = ApiRouter()
    with pytest.raises(TypeError, match="must be in the schema"):
        router.add_api_route("/hidden", lambda: None, response_model=Probe, include_in_schema=False)
    with pytest.raises(TypeError, match="must be in the schema"):
        ApiRouter(include_in_schema=False).add_api_route(
            "/hidden", lambda: None, response_model=Probe
        )
    with pytest.raises(TypeError, match="must be in the schema"):
        router.include_router(ApiRouter(), include_in_schema=False)
    with pytest.raises(TypeError, match="must be in the schema"):
        ApiRouter(include_in_schema=False).include_router(ApiRouter())
    assert router.routes == []


def test_api_models_send_their_fields_as_listed() -> None:
    for field in (
        Field(alias="c"),
        Field(serialization_alias="c"),
        Field(validation_alias="c"),
    ):
        with pytest.raises(TypeError, match="no aliases"):

            class Quote(ApiResponse):
                close: float = field

    with pytest.raises(TypeError, match="no aliases"):

        class Camel(ApiModel):
            model_config = ConfigDict(alias_generator=to_camel)
            public_id: str

    with pytest.raises(TypeError, match="no aliases"):

        class Computed(ApiModel):
            cents: int

            @computed_field(alias="px")  # type: ignore[prop-decorator]
            @property
            def close_price(self) -> float:
                return self.cents / 100

    with pytest.raises(TypeError, match="forbid extra fields"):

        class Loose(ApiModel):
            model_config = ConfigDict(extra="allow")

    with pytest.raises(TypeError, match="keep pydantic's serializer"):

        class Serialized(ApiModel):
            cents: int

            @model_serializer(mode="wrap")
            def _out(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
                return {**handler(self), "close_price": self.cents / 100}


type Cents = Annotated[int, PlainSerializer(lambda v: {"close_price": v / 100})]


def test_api_models_keep_pydantics_serializers_and_schema() -> None:
    with pytest.raises(TypeError, match="serializers and schema"):

        class Skipped(ApiResponse):
            close_price: SkipJsonSchema[float]  # sent, but left out of the schema

    with pytest.raises(TypeError, match="serializers and schema"):

        class Relabelled(ApiResponse):
            moves: Annotated[dict[str, float], WithJsonSchema({"type": "integer"})]

    with pytest.raises(TypeError, match="serializers and schema"):

        class Wrapped(ApiResponse):
            cents: Annotated[int, WrapSerializer(lambda v, handler: handler(v))]

    with pytest.raises(TypeError, match="serializers and schema"):

        class Nested(ApiResponse):
            cents: list[Cents]  # a marker inside a type, through a type alias

    with pytest.raises(TypeError, match="serializers and schema"):

        class FieldSerialized(ApiResponse):
            cents: int

            @field_serializer("cents")
            def _cents(self, cents: int) -> int:
                return cents

    for config in (
        ConfigDict(json_schema_extra={"properties": {}}),
        ConfigDict(json_schema_mode_override="validation"),
        ConfigDict(json_encoders={int: str}),
    ):
        with pytest.raises(TypeError, match="serializers and schema"):

            class Configured(ApiResponse):
                model_config = config

    with pytest.raises(TypeError, match="serializers and schema"):

        class FieldExtra(ApiResponse):
            moves: dict[str, float] = Field(json_schema_extra={"type": "integer"})

    with pytest.raises(TypeError, match="serializers and schema"):

        class OwnSchema(ApiResponse):
            @classmethod
            def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> Any:
                return handler(schema)

    class Plain(BaseModel):  # its own rules: an extra key, a serializer
        n: int

    with pytest.raises(TypeError, match="nest only ApiModels"):

        class Holder(ApiResponse):
            plains: list[Plain] | None


async def test_a_row_with_unlisted_fields_never_passes_through(make_client: MakeClient) -> None:
    router = ApiRouter()

    @router.get("/row", response_model=Probe)
    async def row() -> Probe:  # passes a row through, as a careless route might
        return cast(Probe, {"stream_id": str(uuid.uuid4()), "answer": 1, "close_price": 1.0})

    response = await make_client(router).get("/api/v1/row")
    assert response.status_code == 500
    assert "close_price" not in response.text


async def test_schema_is_served_and_the_docs_pages_are_off(make_client: MakeClient) -> None:
    client = make_client()
    schema = await client.get("/api/v1/openapi.json")
    assert schema.status_code == 200 and schema.json()["openapi"]
    assert_security_headers(schema)
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert (await client.get(path)).status_code == 404, path


async def test_the_schema_documents_the_error_shape_not_fastapis(
    make_client: MakeClient,
) -> None:
    schema = (await make_client(ProbeRoutes().router).get("/api/v1/openapi.json")).json()
    responses = schema["paths"]["/api/v1/test/numbers"]["get"]["responses"]
    assert set(responses) == {"200", "4XX", "5XX"}  # no 422: bad parameters are a 400
    error = responses["4XX"]["content"]["application/json"]["schema"]["$ref"]
    assert error.endswith("/ErrorBody")


async def test_the_access_log_has_no_address_and_no_forged_lines(
    make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="engine.web.access")
    await make_client().get("/x%0AGET%20/forged%20200", headers={"X-Real-IP": "198.51.100.7"})
    (line,) = [r.getMessage() for r in caplog.records if r.name == "engine.web.access"]
    assert line.startswith("GET /x\\nGET /forged 200 404 ") and "\n" not in line
    assert "198.51.100.7" not in line and "203.0.113.10" not in line
