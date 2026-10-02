import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    StatementError,
)
from sqlalchemy.exc import TimeoutError as PoolTimeout

from engine import db
from engine.migrate import migrate
from engine.settings import Settings
from tests import helpers


def silent_url(settings: Settings, port: int) -> str:
    url = make_url(settings.db_url).set(host="127.0.0.1", port=port)
    return url.render_as_string(hide_password=False)


async def test_new_connections_time_out(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "CONNECT_TIMEOUT_SECONDS", 2)  # libpq's minimum

    async def connect_async(url: str) -> None:
        engine = db.make_engine(url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    def connect_sync(url: str) -> None:
        engine = db.make_sync_engine(url)
        try:
            with engine.connect():
                pass
        finally:
            engine.dispose()

    with helpers.silent_port() as port:
        url = silent_url(settings, port)
        attempts = [
            connect_async(url),
            asyncio.to_thread(connect_sync, url),
            asyncio.to_thread(migrate, url, settings.web_role),  # through migrations/env.py
        ]
        for attempt in attempts:
            with pytest.raises(OperationalError, match="timeout"):
                await asyncio.wait_for(attempt, timeout=8)  # without one it would wait for ever


def test_only_errors_no_retry_can_fix_are_permanent() -> None:
    def error(kind: type[Exception]) -> Exception:
        return kind("UPDATE", {}, Exception("x"))

    for kind in (DataError, IntegrityError, ProgrammingError):
        assert db.is_permanent(error(kind))
    assert db.is_permanent(StatementError("bad parameter", "UPDATE", {}, TypeError("x")))
    assert not db.is_permanent(error(OperationalError))
    assert not db.is_permanent(PoolTimeout("QueuePool limit reached"))
    assert not db.is_permanent(OSError("connection reset"))


def test_error_text_is_safe_for_a_text_column() -> None:
    lone_surrogate = b"caf\xff".decode("utf-8", "surrogateescape")
    text_ = db.error_text(RuntimeError(f"bad\x00 {lone_surrogate}"))
    assert text_ == "RuntimeError: bad caf\\udcff"
    text_.encode("utf-8")  # no lone surrogates left
    assert len(db.error_text(RuntimeError("x" * 5000))) == 2000
