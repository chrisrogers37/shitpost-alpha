import time

from sqlalchemy.engine import make_url

from engine.web.settings import WebSettings
from tests import helpers
from tests.web.api_checks import assert_security_headers
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes


async def test_healthz_answers_ok(make_client: MakeClient) -> None:
    response = await make_client().get("/healthz")
    assert (response.status_code, response.json()) == (200, {"ok": True})
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response)


async def test_a_refused_database_is_a_503(make_client: MakeClient, web_url: str) -> None:
    refused = make_url(web_url).set(host="127.0.0.1", port=1)
    settings = WebSettings(database_url=refused.render_as_string(hide_password=False))
    client = make_client(ProbeRoutes().router, settings=settings)

    health = await client.get("/healthz")
    assert (health.status_code, health.json()) == (503, {"ok": False})
    assert health.headers["cache-control"] == "no-store"
    assert_security_headers(health)

    api = await client.get("/api/v1/test/query")
    assert api.status_code == 503
    assert api.json() == {
        "error": {"code": "unavailable", "message": "The database is unavailable"}
    }
    assert_security_headers(api)
    assert str(refused.password) not in api.text


async def test_a_database_that_never_answers_fails_healthz_within_2s(
    make_client: MakeClient, web_url: str
) -> None:
    with helpers.silent_port() as port:  # accepts and never answers
        silent = make_url(web_url).set(host="127.0.0.1", port=port)
        settings = WebSettings(database_url=silent.render_as_string(hide_password=False))
        client = make_client(settings=settings)
        started = time.monotonic()
        response = await client.get("/healthz")
        elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert 1.9 < elapsed < 3.5
