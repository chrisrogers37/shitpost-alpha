"""Command line: `python -m engine migrate | run | status | import-history | backfill-bars |
sync-names | extract | fetch-model | embed | ai-pick | review-list | build-moves |
backtest`."""

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

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
    """Run one command. `registry` replaces build_registry() for `run` (tests use it)."""
    parser = argparse.ArgumentParser(prog="python -m engine")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="upgrade the engine database to the latest schema")
    commands.add_parser("run", help="run the engine; one copy at a time holds the lease")
    commands.add_parser("status", help="print the engine status row")
    commands.add_parser(
        "import-history", help="import Trump's past posts (CC0 archive, then CNN's live file)"
    )
    commands.add_parser(
        "backfill-bars", help="fetch every instrument's missing daily bars from Alpaca"
    )
    commands.add_parser(
        "sync-names", help="add aliases.json's instruments and names to the database"
    )
    commands.add_parser("extract", help="run the rules picker over every text post")
    commands.add_parser("fetch-model", help="download the pinned similarity model files")
    commands.add_parser("embed", help="make the similarity vector of every text post")
    ai_pick = commands.add_parser("ai-pick", help="run the AI picker over chosen posts")
    ai_pick.add_argument(
        "--keys", type=Path, help="file of signal keys, one per line (truth_social:<id>)"
    )
    ai_pick.add_argument("--from", dest="start", type=date.fromisoformat, help="first day")
    ai_pick.add_argument("--to", dest="end", type=date.fromisoformat, help="last day")
    ai_pick.add_argument(
        "--run", type=int, default=1, choices=(1, 2), help="2: a stability rerun, kept apart"
    )
    ai_pick.add_argument(
        "--max-usd", type=_dollars, default=Decimal(5), help="stop this run past this spend"
    )
    ai_pick.add_argument(
        "--max-total-usd",
        type=_dollars,
        help="stop past this spend by every AI answer recorded so far, this run included",
    )
    commands.add_parser(
        "review-list", help="names the AI vote counted that the rules missed, for review"
    )
    build_moves = commands.add_parser(
        "build-moves", help="fill signal_moves and random_baselines for the sample to --to"
    )
    build_moves.add_argument(
        "--to", dest="end", type=date.fromisoformat, required=True, help="the last day"
    )
    backtest = commands.add_parser("backtest", help="run Gate 0 v1 and write the report")
    which = backtest.add_mutually_exclusive_group()
    which.add_argument(
        "--to", dest="end", type=date.fromisoformat, help="the last day (default: latest built)"
    )
    which.add_argument(
        "--rebuild",
        action="store_true",
        help="write the report again from saved data and check it matches the last run",
    )
    backtest.add_argument("--out", type=Path, help="where the report goes (engine/reports)")
    backtest.add_argument(
        "--divergent-days",
        type=Path,
        help="PR 3's cross-check output: also print BTC without those days (sandbox only)",
    )
    args = parser.parse_args(argv)

    configure_logging()
    try:
        settings = Settings()
    except ValidationError as exc:
        # Print field names and messages only: the error's input values can hold the URL.
        problems = "; ".join(f"{_variable(e['loc'])}: {e['msg']}" for e in exc.errors())
        print(f"invalid engine settings: {problems}", file=sys.stderr)
        return 2

    if args.command == "run":  # it retries database errors itself
        asyncio.run(_run(settings, registry or build_registry()))
        return 0
    try:
        if args.command == "migrate":
            migrate(settings.db_url, settings.web_role)
            return 0
        if args.command == "import-history":
            asyncio.run(run_import(settings))
            return 0
        if args.command == "backfill-bars":
            from engine.market.bars import run_backfill  # pandas loads only for this command

            return asyncio.run(run_backfill(settings))
        if args.command in EXTRACT_COMMANDS:
            return _extract_command(args, settings)
        if args.command in ("build-moves", "backtest"):
            return _backtest_command(args, settings)
        return asyncio.run(_status(settings))
    except OperationalError as exc:
        print(database_error_line(exc), file=sys.stderr)
        return 1


def _dollars(text: str) -> Decimal:
    """A spend limit: a finite amount of 0 or more."""
    try:
        amount = Decimal(text)
    except InvalidOperation:
        amount = Decimal("NaN")
    if not amount.is_finite() or amount < 0:
        raise argparse.ArgumentTypeError(f"not an amount of 0 or more: {text!r}")
    return amount


def _variable(loc: tuple[int | str, ...]) -> str:
    """The environment variable a settings error is about. A field read under its own
    name (ALPACA_API_SECRET_KEY) is located at that name, in capitals."""
    name = "_".join(map(str, loc))
    return name if name.isupper() else f"ENGINE_{name.upper() or 'SETTINGS'}"


def database_error_line(exc: OperationalError) -> str:
    """One line from the driver. It names the host and user; it shows part of the password
    only if the URL is malformed (an unescaped "@" in the password)."""
    reason = (str(exc.orig or exc).splitlines() or [type(exc).__name__])[0]
    unreachable = reason.startswith(("connection", "failed to resolve host"))
    return f"{'could not reach' if unreachable else 'error from'} the engine database: {reason}"


EXTRACT_COMMANDS = ("sync-names", "extract", "fetch-model", "embed", "ai-pick", "review-list")


def _extract_command(args: argparse.Namespace, settings: Settings) -> int:
    """The extraction commands. Expected operator errors (names not synced, a changed
    rules file, Alpaca refusing, a failed download, a missing keys file) print one line."""
    from engine.extract import batch, names, similarity
    from engine.extract.rules import NamesNotSynced, RulesFileChanged
    from engine.market.alpaca import AlpacaError

    try:
        if args.command == "sync-names":
            return asyncio.run(names.run_sync_names(settings))
        if args.command == "extract":
            return asyncio.run(batch.run_extract(settings))
        if args.command == "fetch-model":
            hosts = similarity.fetch_model(settings)
            print(f"downloaded through: {', '.join(sorted(hosts)) or 'nothing new'}")
            return 0
        if args.command == "embed":
            return asyncio.run(batch.run_embed(settings))
        if args.command == "review-list":
            return asyncio.run(batch.run_review_list(settings))
        chosen = batch.Selection(_keys(args.keys), args.start, args.end)
        return asyncio.run(
            batch.run_ai_pick(
                settings,
                chosen,
                max_usd=args.max_usd,
                max_total_usd=args.max_total_usd,
                run=args.run,
            )
        )
    except (similarity.ModelMissing, NamesNotSynced, RulesFileChanged, AlpacaError) as exc:
        print(exc, file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:  # a refused host, a 404, a dropped line
        print(f"{args.command} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:  # the --keys file
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1


def _backtest_command(args: argparse.Namespace, settings: Settings) -> int:
    """build-moves and backtest (numpy and pandas load only for these)."""
    from engine.backtest import build, gate, run
    from engine.extract import similarity
    from engine.extract.rules import RulesFileChanged
    from engine.market.alpaca import AlpacaError

    try:
        if args.command == "build-moves":
            return asyncio.run(build.run_build_moves(settings, args.end))
        return asyncio.run(
            run.run_backtest_command(
                settings, args.end, args.rebuild, args.out or gate.REPORTS_DIR, args.divergent_days
            )
        )
    except (similarity.ModelMissing, RulesFileChanged, AlpacaError) as exc:
        print(exc, file=sys.stderr)
        return 1
    except OSError as exc:  # the cache directory, the report directory, --divergent-days
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1


def _keys(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    return [line.strip() for line in path.read_text("utf-8").splitlines() if line.strip()]


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
