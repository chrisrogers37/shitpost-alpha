"""Command line: `python -m engine migrate | run | status | import-history`."""

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from engine.db import db_now, make_engine
from engine.feeds.history import run_import
from engine.feeds.status import status_lines
from engine.lease import LEASE_NAME
from engine.logs import configure_logging
from engine.migrate import migrate
from engine.registry import Registry, build_registry
from engine.runtime import run_engine
from engine.settings import Settings
from engine.tables import engine_lease, engine_meta

STATUS_FIELDS = ("stream_id", "started_at", "last_heartbeat_at", "lease_holder", "code_version")


def main(argv: Sequence[str] | None = None, registry: Registry | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="upgrade the engine database to the latest schema")
    commands.add_parser("run", help="run the engine; one copy at a time holds the lease")
    commands.add_parser("status", help="print the engine status row")
    commands.add_parser(
        "import-history", help="import Trump's past posts (CC0 archive, then CNN's live file)"
    )
    args = parser.parse_args(argv)

    configure_logging()
    try:
        settings = Settings()
    except ValidationError as exc:
        # Print field names and messages only: the error's input values can hold the URL.
        problems = "; ".join(
            f"ENGINE_{'_'.join(map(str, e['loc'])).upper() or 'SETTINGS'}: {e['msg']}"
            for e in exc.errors()
        )
        print(f"invalid engine settings: {problems}", file=sys.stderr)
        return 2

    if args.command == "migrate":
        migrate(settings.database_url, settings.web_role)
        return 0
    if args.command == "run":
        asyncio.run(_run(settings, registry or build_registry()))
        return 0
    if args.command == "import-history":
        asyncio.run(run_import(settings))
        return 0
    return asyncio.run(_status(settings))


async def _run(settings: Settings, registry: Registry) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run_engine(settings, registry, stop)


async def _status(settings: Settings) -> int:
    db = make_engine(settings.database_url)
    try:
        async with db.connect() as conn:
            meta = (await conn.execute(select(engine_meta))).one_or_none()
            lease = (
                await conn.execute(select(engine_lease).where(engine_lease.c.name == LEASE_NAME))
            ).one_or_none()
            now = await db_now(conn)
            feeds = await status_lines(conn)
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
    for line in feeds:
        print(line)
    return 0
