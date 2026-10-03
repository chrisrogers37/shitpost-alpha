"""Round-2 probes on check_role (web/db.py at aac1f51). Each prints what it saw."""

import asyncio
import secrets
from collections.abc import Callable

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

from engine.migrate import migrate
from engine.web.app import create_app
from engine.web.db import ROLE_CHECK, make_web_engine
from engine.web.settings import WebSettings
from tests.conftest import admin
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes


async def _extra(url: str) -> list[str]:
    db = make_web_engine(WebSettings(database_url=url))
    try:
        async with db.connect() as conn:
            return list((await conn.execute(ROLE_CHECK)).scalar_one())
    finally:
        await db.dispose()


async def _reads_prices(url: str, set_role: str | None = None) -> bool:
    db = make_web_engine(WebSettings(database_url=url))
    try:
        async with db.connect() as conn:
            if set_role:
                await conn.execute(text(f'SET ROLE "{set_role}"'))
            await conn.execute(text("SELECT * FROM prices.bars"))
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"   read failed: {type(exc).__name__}: {str(getattr(exc, 'orig', exc)).splitlines()[0]}")
        return False
    finally:
        await db.dispose()


def _db(database_url: str) -> str:
    return make_url(database_url).database or ""


@pytest.mark.parametrize(
    "case",
    [
        "table_select_without_usage",
        "inherited_usage_via_role",
        "noinherit_member_of_reader",
        "pg_write_all_data",
        "owns_prices_schema",
        "usage_to_public",
        "view_in_engine_schema",
        "createdb_only",
        "bypassrls_only",
    ],
)
async def test_what_check_role_sees(
    case: str, database_url: str, web_url: str, make_role: Callable[..., str]
) -> None:
    role = make_url(web_url).username or ""
    db = _db(database_url)
    ident = sql.Identifier(role)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE prices.bars (symbol text, close numeric)")
        conn.execute("INSERT INTO prices.bars VALUES ('SPY', 571.23)")
    set_role = None
    if case == "table_select_without_usage":
        admin(sql.SQL("GRANT SELECT ON prices.bars TO {}").format(ident), db)
    elif case in ("inherited_usage_via_role", "noinherit_member_of_reader"):
        reader = make_role()
        r = sql.Identifier(reader)
        admin(sql.SQL("GRANT USAGE ON SCHEMA prices TO {}").format(r), db)
        admin(sql.SQL("GRANT SELECT ON prices.bars TO {}").format(r), db)
        if case == "inherited_usage_via_role":
            admin(sql.SQL("GRANT {} TO {}").format(r, ident))
        else:
            admin(sql.SQL("GRANT {} TO {} WITH INHERIT FALSE").format(r, ident))
            set_role = reader
    elif case == "pg_write_all_data":
        admin(sql.SQL("GRANT pg_write_all_data TO {}").format(ident))
    elif case == "owns_prices_schema":
        admin(sql.SQL("ALTER SCHEMA prices OWNER TO {}").format(ident), db)
    elif case == "usage_to_public":
        admin(sql.SQL("GRANT USAGE ON SCHEMA prices TO PUBLIC"), db)
        admin(sql.SQL("GRANT SELECT ON prices.bars TO PUBLIC"), db)
    elif case == "view_in_engine_schema":
        admin(sql.SQL("CREATE VIEW engine.bar_view AS SELECT * FROM prices.bars"), db)
        migrate(database_url, role)  # migrate re-applies WEB_GRANTS: engine.* SELECT
    elif case == "createdb_only":
        admin(sql.SQL("ALTER ROLE {} CREATEDB").format(ident))
    elif case == "bypassrls_only":
        admin(sql.SQL("ALTER ROLE {} BYPASSRLS").format(ident))
    extra = await _extra(web_url)
    if case == "view_in_engine_schema":
        dbe = make_web_engine(WebSettings(database_url=web_url))
        try:
            async with dbe.connect() as conn:
                close = (await conn.execute(text("SELECT close FROM engine.bar_view"))).scalar_one()
            reads = f"reads prices.bars.close via engine.bar_view: {close}"
        finally:
            await dbe.dispose()
    else:
        reads = f"reads prices.bars: {await _reads_prices(web_url, set_role)}"
    print(f"\n{case}: check_role -> {extra or 'passes'}; {reads}")
    if case == "owns_prices_schema":
        admin(sql.SQL("ALTER SCHEMA prices OWNER TO CURRENT_USER"), db)


async def test_a_role_created_by_a_neon_like_owner_passes(
    database_url: str, make_role: Callable[..., str]
) -> None:
    """Neon: the console's owner role is CREATEROLE CREATEDB and a member of
    pg_read_all_data (via neon_superuser). A role it creates with plain SQL, as the README
    says, is not refused; a role made a member of the owner's group is."""
    db = _db(database_url)
    group = make_role()  # stands in for neon_superuser
    g = sql.Identifier(group)
    admin(sql.SQL("ALTER ROLE {} CREATEROLE CREATEDB").format(g))
    admin(sql.SQL("GRANT pg_read_all_data TO {} WITH ADMIN OPTION").format(g))
    owner_pw = secrets.token_hex(8)
    owner = make_role(owner_pw)
    o = sql.Identifier(owner)
    admin(sql.SQL("ALTER ROLE {} CREATEROLE CREATEDB").format(o))
    admin(sql.SQL("GRANT {} TO {}").format(g, o))
    owner_url = make_url(database_url).set(username=owner, password=owner_pw)
    web = f"web_test_{secrets.token_hex(4)}"
    web_pw = secrets.token_hex(8)
    with psycopg.connect(owner_url.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(web), sql.Literal(web_pw)))
    try:
        migrate(database_url, web)
        web_url = make_url(database_url).set(username=web, password=web_pw)
        url = web_url.render_as_string(hide_password=False)
        print(f"\nrole made by the owner with SQL: check_role -> {await _extra(url) or 'passes'}")
        admin(sql.SQL("GRANT {} TO {}").format(g, sql.Identifier(web)))
        print(f"same role made a member of the owner's group: -> {await _extra(url)}")
    finally:
        admin(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(web)), db)
        admin(sql.SQL("DROP ROLE {}").format(sql.Identifier(web)))


async def test_the_check_never_runs_again_after_a_down_start(
    database_url: str, make_client: MakeClient
) -> None:
    """Start as the SUPERUSER while the database is unreachable (warn and serve), then the
    database comes up: the role is never checked again and the API serves as superuser."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    target = make_url(database_url)
    url = target.set(host="127.0.0.1", port=port).render_as_string(hide_password=False)
    app = create_app(WebSettings(database_url=url), [ProbeRoutes().router])

    async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        sr, sw = await asyncio.open_connection(target.host or "localhost", target.port or 5432)

        async def pipe(a: asyncio.StreamReader, b: asyncio.StreamWriter) -> None:
            try:
                while data := await a.read(65536):
                    b.write(data)
                    await b.drain()
            except ConnectionError:
                pass
            finally:
                b.close()

        await asyncio.gather(pipe(r, sw), pipe(sr, w))

    from httpx import ASGITransport, AsyncClient

    async with app.router.lifespan_context(app):  # database down: warns, serves
        server = await asyncio.start_server(handle, "127.0.0.1", port)  # database comes up
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                health = await c.get("/healthz")
                api = await c.get("/api/v1/test/query")
                async with app.state.web.db.connect() as conn:
                    su = (await conn.execute(text("SHOW is_superuser"))).scalar_one()
        finally:
            server.close()
    print(f"\nafter a down start: /healthz {health.status_code}, API {api.status_code}, "
          f"connected as superuser={su}; check_role never ran again")
