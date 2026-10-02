import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from engine.web.db import make_web_engine
from engine.web.settings import WebSettings


async def test_the_web_role_reads_engine_meta_and_nothing_else(
    database_url: str, web_settings: WebSettings
) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:  # the engine's own tables
        conn.execute("CREATE TABLE prices.bars (symbol text)")
        conn.execute("CREATE TABLE app.private (x int)")

    db = make_web_engine(web_settings)
    try:
        async with db.connect() as conn:
            user = (await conn.execute(text("SELECT current_user"))).scalar_one()
            superuser = (await conn.execute(text("SHOW is_superuser"))).scalar_one()
            assert user.startswith("web_test_") and superuser == "off"
            assert (await conn.execute(text("SHOW statement_timeout"))).scalar_one() == "5s"
            rows = await conn.execute(text("SELECT stream_id FROM engine.engine_meta"))
            assert len(rows.all()) == 1

        denied = [
            "SELECT * FROM prices.bars",
            "SELECT * FROM app.private",
            "UPDATE engine.engine_meta SET code_version = 'x'",
            "INSERT INTO engine.job_runs (job, scheduled_for, started_at, status, attempts)"
            " VALUES ('x', now(), now(), 'running', 1)",
            "DELETE FROM engine.engine_lease",
            "CREATE TABLE engine.mine (x int)",
            "CREATE TABLE app.mine (x int)",
            "CREATE TABLE public.mine (x int)",
        ]
        for statement in denied:
            async with db.connect() as conn:
                with pytest.raises(ProgrammingError, match="permission denied"):
                    await conn.execute(text(statement))
    finally:
        await db.dispose()
