"""Review probe (PR 3): 0003 downgrades and upgrades again on a throwaway database."""

from alembic import command

from engine.migrate import alembic_config, migrate
from engine.settings import Settings
from tests.test_migrate import rows


def test_probe_0003_downgrade_roundtrip(settings: Settings) -> None:
    migrate(settings.db_url, settings.web_role)
    command.downgrade(alembic_config(settings.db_url), "0002")
    left = rows(
        settings.db_url,
        "SELECT table_schema || '.' || table_name FROM information_schema.tables "
        "WHERE table_name IN ('instruments', 'instrument_aliases', 'market_bars')",
    )
    print(f"\nafter downgrade: {left}")
    assert left == []
    migrate(settings.db_url, settings.web_role)
    assert rows(settings.db_url, "SELECT count(*) FROM engine.instruments") == [(4,)]
