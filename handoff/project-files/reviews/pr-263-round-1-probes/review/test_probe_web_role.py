"""Check (PR 263 review, round 1): after migration 0005 the web role reads the backtest
tables but not the prices schema, and 0005 downgrades and upgrades cleanly. Passing
here means "checked and dropped"."""

from collections.abc import Callable

import psycopg
import pytest
from alembic import command

from engine.migrate import alembic_config, migrate
from engine.settings import Settings
from tests.conftest import database_url, make_role, settings  # noqa: F401


def test_check_web_role_cannot_read_prices_after_0005(
    settings: Settings, make_role: Callable[[], str]
) -> None:
    url, web = settings.db_url, make_role()
    migrate(url, web)
    with psycopg.connect(url) as conn:
        conn.execute(f'SET ROLE "{web}"')
        for name in ("signal_moves", "random_baselines", "backtest_runs", "backtest_summary"):
            conn.execute(f"SELECT * FROM engine.{name}").fetchall()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM prices.market_bars")


def test_check_0005_downgrades_and_upgrades(settings: Settings) -> None:
    url = settings.db_url
    migrate(url, settings.web_role)
    config = alembic_config(url)
    command.downgrade(config, "0004")
    with psycopg.connect(url) as conn:
        left = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'engine' "
            "AND table_name IN ('signal_moves','random_baselines','backtest_runs','backtest_summary')"
        ).fetchall()
        assert left == []
    command.upgrade(config, "head")
