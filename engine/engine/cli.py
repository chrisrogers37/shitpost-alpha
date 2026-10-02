"""Command line: `python -m engine migrate | run | status | web`."""

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence

import uvicorn
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from engine.db import db_now, make_engine
from engine.lease import LEASE_NAME
from engine.logs import configure_logging
from engine.migrate import migrate
from engine.registry import Registry, build_registry
from engine.runtime import run_engine
from engine.settings import Settings
from engine.tables import engine_lease, engine_meta
from engine.web.app import create_app
from engine.web.settings import WebSettings

STATUS_FIELDS = ("stream_id", "started_at", "last_heartbeat_at", "lease_holder", "code_version")


def main(argv: Sequence[str] | None = None, registry: Registry | None = None) -> int:
    """Run one command. `registry` replaces build_registry() for `run` (tests use it)."""
    parser = argparse.ArgumentParser(prog="python -m engine")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="upgrade the engine database to the latest schema")
    commands.add_parser("run", help="run the engine; one copy at a time holds the lease")
    commands.add_parser("status", help="print the engine status row")
    commands.add_parser("web", help="serve the website and its API (WEB_* settings only)")
    args = parser.parse_args(argv)

    configure_logging()
    if args.command == "web":
        web_settings = load_settings(WebSettings, "web")
        if web_settings is None:
            return 2
        serve_web(web_settings)
        return 0
    settings = load_settings(Settings, "engine")
    if settings is None:
        return 2

    if args.command == "run":  # it retries database errors itself
        asyncio.run(_run(settings, registry or build_registry()))
        return 0
    try:
        if args.command == "migrate":
            migrate(settings.db_url, settings.web_role)
            return 0
        return asyncio.run(_status(settings))
    except OperationalError as exc:
        print(database_error_line(exc), file=sys.stderr)
        return 1


def load_settings[S: BaseSettings](cls: type[S], what: str) -> S | None:
    """`cls()` from the environment, or None after printing what is wrong with it."""
    try:
        return cls()
    except ValidationError as exc:
        # Print variable names and messages only: the error's input values can hold the URL.
        prefix = cls.model_config.get("env_prefix") or ""
        problems = "; ".join(f"{_variable(prefix, e['loc'])}: {e['msg']}" for e in exc.errors())
        print(f"invalid {what} settings: {problems}", file=sys.stderr)
        return None


def _variable(prefix: str, loc: tuple[int | str, ...]) -> str:
    name = "_".join(map(str, loc))
    if name.isupper():  # an alias, already the variable's full name (PORT)
        return name
    return f"{prefix}{name.upper() or 'SETTINGS'}"


def serve_web(settings: WebSettings) -> None:
    """One uvicorn process on 0.0.0.0:PORT. Proxy headers stay off: the rate limit reads
    the edge's header itself. No server header; ResponsePolicy writes the access log."""
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=False,
        server_header=False,
        access_log=False,
        log_config=None,  # keep configure_logging's format
    )


def database_error_line(exc: OperationalError) -> str:
    """One line from the driver. It names the host and user; it shows part of the password
    only if the URL is malformed (an unescaped "@" in the password)."""
    reason = (str(exc.orig or exc).splitlines() or [type(exc).__name__])[0]
    unreachable = reason.startswith(("connection", "failed to resolve host"))
    return f"{'could not reach' if unreachable else 'error from'} the engine database: {reason}"


async def _run(settings: Settings, registry: Registry) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run_engine(settings, registry, stop)


async def _status(settings: Settings) -> int:
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            meta = (await conn.execute(select(engine_meta))).one_or_none()
            lease = (
                await conn.execute(select(engine_lease).where(engine_lease.c.name == LEASE_NAME))
            ).one_or_none()
            now = await db_now(conn)
    except ProgrammingError:
        meta = None
    finally:
        await db.dispose()
    if meta is None:
        print("the engine database is not migrated; run `python -m engine migrate`")
        return 1
    for field in STATUS_FIELDS:
        print(f"{field}: {getattr(meta, field)}")
    if lease is None or lease.expires_at <= now:
        print("lease: free")
    else:
        left = (lease.expires_at - now).total_seconds()
        print(f"lease: held by {lease.holder}, expires in {left:.0f}s")
    return 0
