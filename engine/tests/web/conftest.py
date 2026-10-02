"""The web tests connect as a real login role holding only what `migrate` grants it
(WEB_GRANTS), never as the superuser."""

import secrets
from collections.abc import AsyncIterator, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url

from engine.migrate import migrate
from engine.web.app import create_app
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings

VISITOR = ("203.0.113.10", 50000)  # the socket address requests come from by default

MakeClient = Callable[..., AsyncClient]


@pytest.fixture
def web_url(database_url: str, make_role: Callable[..., str]) -> str:
    """The migrated test database, as the web role."""
    password = secrets.token_hex(8)
    role = make_role(password)
    migrate(database_url, role)
    url = make_url(database_url).set(username=role, password=password)
    return url.render_as_string(hide_password=False)


@pytest.fixture
def web_settings(web_url: str) -> WebSettings:
    return WebSettings(database_url=web_url)


@pytest.fixture
async def make_client(web_settings: WebSettings) -> AsyncIterator[MakeClient]:
    """`make_client(*routers, settings=..., client=(host, port))` builds the app with those
    /api/v1 routers and a client for it. Apps and clients are closed after the test."""
    made: list[tuple[FastAPI, AsyncClient]] = []

    def make(
        *routers: ApiRouter,
        settings: WebSettings | None = None,
        client: tuple[str, int] = VISITOR,
    ) -> AsyncClient:
        app = create_app(settings or web_settings, routers)
        http = AsyncClient(transport=ASGITransport(app=app, client=client), base_url="http://test")
        made.append((app, http))
        return http

    yield make
    for app, http in made:
        await http.aclose()
        await app.state.web.db.dispose()
