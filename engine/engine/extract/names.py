"""The name aliases in the database: `python -m engine sync-names` writes aliases.json's
instruments and names there, and load_book() reads them back as a NameBook."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.db import make_engine
from engine.extract.rules import AliasRow, Listed, NameBook, Rules, current_rules
from engine.market.alpaca import Alpaca
from engine.market.instruments import Listings, add_alias, add_instrument
from engine.settings import Settings
from engine.tables import instrument_aliases, instruments


async def load_book(conn: AsyncConnection, rules: Rules, *, check: bool = True) -> NameBook:
    """The NameBook from the database. With `check`, every name in aliases.json must be
    there (NamesNotSynced otherwise), so a deploy that skipped the sync shows up."""
    listed = [
        Listed(row.id, row.symbol, row.name, row.asset_class)
        for row in await conn.execute(select(instruments).order_by(instruments.c.id))
    ]
    aliases = [
        AliasRow(row.alias, row.instrument_id, row.kind, row.valid_from, row.valid_to)
        for row in await conn.execute(select(instrument_aliases).order_by(instrument_aliases.c.id))
    ]
    book = NameBook.build(rules, listed, aliases)
    if check:
        book.check_synced()
    return book


@dataclass(frozen=True)
class Synced:
    instruments: int
    aliases: int


async def sync_aliases(
    conn: AsyncConnection, listings: Listings, rules: Rules, at: datetime
) -> Synced:
    """Add aliases.json's instruments (each checked to count at `at`) and their names and
    old tickers. Running it again changes nothing. Names dropped from the file stay in
    the database; a later rules version that drops one removes it here."""
    aliases = 0
    for spec in rules.aliases:
        instrument = await add_instrument(
            conn, listings, spec.symbol, spec.name, spec.asset_class, at
        )
        for name in spec.names:
            await add_alias(conn, instrument.id, name, "name", spec.valid_from)
            aliases += 1
        for old in spec.old_tickers:
            await add_alias(conn, instrument.id, old.ticker, "old_ticker", None, old.to)
            aliases += 1
    return Synced(len(rules.aliases), aliases)


async def run_sync_names(settings: Settings, say: Callable[[str], None] = print) -> int:
    """`python -m engine sync-names`. Stocks need the Alpaca keys: each is checked to
    count before it is added."""
    rules = current_rules()
    db = make_engine(settings.db_url)
    try:
        async with Alpaca(settings) as alpaca, db.begin() as conn:
            synced = await sync_aliases(conn, Listings(alpaca), rules, datetime.now(UTC))
            book = await load_book(conn, rules)
    finally:
        await db.dispose()
    say(
        f"rules version {rules.version}: {synced.instruments} instruments and "
        f"{synced.aliases} names and old tickers in sync; "
        f"{len(book.instruments)} instruments in the database"
    )
    return 0
