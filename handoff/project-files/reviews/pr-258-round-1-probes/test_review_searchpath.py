from collections.abc import Callable

import psycopg

from engine.migrate import migrate
from engine.settings import Settings


def test_unqualified_table_lands_in_web_readable_schema_for_role_engine(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url, web = settings.database_url, make_role()
    migrate(url, web)
    # A role named "engine" gets search_path "$user", public -> engine, public.
    with psycopg.connect(url, autocommit=True, options="-c search_path=engine,public") as conn:
        conn.execute("CREATE TABLE telegram_subscribers (chat_id text)")  # schema forgotten
        conn.execute("INSERT INTO telegram_subscribers VALUES ('12345')")
        where = conn.execute(
            "SELECT schemaname FROM pg_tables WHERE tablename = 'telegram_subscribers'"
        ).fetchone()
    with psycopg.connect(url) as conn:
        conn.execute(f'SET ROLE "{web}"')
        got = conn.execute("SELECT chat_id FROM engine.telegram_subscribers").fetchall()
    print("table created in schema", where, "; web role reads:", got)
    assert got == [("12345",)]
