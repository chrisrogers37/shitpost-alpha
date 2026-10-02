import uuid

import psycopg
import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from engine.web.app import create_app
from engine.web.db import make_web_engine
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from engine.web.stream import StreamIds
from tests.web.api_checks import assert_security_headers
from tests.web.conftest import MakeClient
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


def test_every_api_route_must_declare_an_api_response(web_settings: WebSettings) -> None:
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
    create_app(web_settings, [router])


async def test_a_row_with_unlisted_fields_never_passes_through(make_client: MakeClient) -> None:
    router = ApiRouter()

    @router.get("/row", response_model=Probe)
    async def row() -> dict[str, object]:
        return {"stream_id": str(uuid.uuid4()), "answer": 1, "close_price": 1.0}

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
