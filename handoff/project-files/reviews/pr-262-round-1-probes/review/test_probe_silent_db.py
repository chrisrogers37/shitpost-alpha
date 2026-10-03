"""Probe: against a database that accepts and never answers, /healthz gives up in 2 s but
an /api/v1 request waits out the engine's 10 s connect timeout before its 503. The web
engine inherits CONNECT_TIMEOUT_SECONDS = 10 from engine/db.py. PASSES while true."""

import time

from sqlalchemy.engine import make_url

from engine.web.settings import WebSettings
from tests import helpers
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes


async def test_an_api_request_waits_10s_on_a_silent_database(
    make_client: MakeClient, web_url: str
) -> None:
    with helpers.silent_port() as port:
        silent = make_url(web_url).set(host="127.0.0.1", port=port)
        settings = WebSettings(database_url=silent.render_as_string(hide_password=False))
        client = make_client(ProbeRoutes().router, settings=settings)
        started = time.monotonic()
        response = await client.get("/api/v1/test/query")
        elapsed = time.monotonic() - started
    print(f"\n/api/v1 on a silent database: {response.status_code} after {elapsed:.1f}s")
    assert response.status_code == 503
    assert elapsed > 9.5
