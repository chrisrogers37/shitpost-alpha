"""Instruments, their aliases, and what counts as an instrument at a post's time.

A US-listed stock or ETF counts if Alpaca has a daily bar for it on the post's trading
date (the session on or after the post). For a live post, whose session may have no bar
yet, the latest session with a bar decides. BTC and ETH always count; no other coin does.
Asset class is given when an instrument is added: Alpaca's data API doesn't say whether a
symbol is an ETF.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Row, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from engine.market.alpaca import SIP_DELAY, Alpaca, Bar
from engine.market.calendar import session_on_or_after, session_open, trading_days_after
from engine.tables import instrument_aliases, instruments

AssetClass = Literal["stock", "etf", "coin"]
AliasKind = Literal["name", "old_ticker"]

COINS = frozenset({"BTC", "ETH"})
"""The only coins that count."""
BENCHMARKS: dict[AssetClass, str] = {"stock": "spy", "etf": "spy", "coin": "btc"}
"""Benchmark slug by asset class. SPY and BTC have none."""
HISTORY_START = datetime(2016, 1, 1, tzinfo=UTC)
"""Where price history starts (each coin's first bar, if later)."""
STOCK_SYMBOL = re.compile(r"[A-Z]{1,5}(\.[A-Z]{1,2})?")
"""A US ticker as Alpaca writes it, such as SPY or BRK.B."""
NEW_YORK = ZoneInfo("America/New_York")


class DoesNotCount(ValueError):
    """The symbol isn't a listed instrument at that time."""


@dataclass(frozen=True)
class Instrument:
    id: int
    slug: str
    symbol: str
    name: str
    asset_class: AssetClass
    calendar: str
    alpaca_symbol: str
    benchmark_id: int | None
    rebased_at: datetime | None
    """When the daily bars were last fetched whole (see engine.instruments)."""

    @classmethod
    def from_row(cls, row: Row[Any]) -> "Instrument":
        return cls(
            id=row.id,
            slug=row.slug,
            symbol=row.symbol,
            name=row.name,
            asset_class=row.asset_class,
            calendar=row.calendar,
            alpaca_symbol=row.alpaca_symbol,
            benchmark_id=row.benchmark_id,
            rebased_at=row.rebased_at,
        )

    @property
    def is_coin(self) -> bool:
        return self.asset_class == "coin"


def alpaca_symbol(symbol: str, asset_class: AssetClass) -> str:
    """What Alpaca calls a symbol: coins trade against the dollar (BTC/USD)."""
    return f"{symbol}/USD" if asset_class == "coin" else symbol


def normalize_alias(text: str) -> str:
    """Aliases are stored lowercase with single spaces."""
    return " ".join(text.lower().split())


def latest_session_with_data(now: datetime) -> date:
    """The newest session Alpaca can show a stock bar for: one that opened at least 16
    minutes ago."""
    available = now - SIP_DELAY
    session = session_on_or_after(available)
    if session_open(session) <= available:
        return session
    return trading_days_after(session, -1)


def last_settled_session(now: datetime) -> date:
    """The newest session whose daily bar can no longer appear: its New York day ended
    at least 16 minutes ago."""
    today = (now - SIP_DELAY).astimezone(NEW_YORK).date()
    sessions_from_today = session_on_or_after(datetime.combine(today, time(), NEW_YORK))
    return trading_days_after(sessions_from_today, -1)


class Listings:
    """Decides whether a symbol counts at a time. Each stock's trading days come from one
    call for its whole daily history, kept for the life of this object and read only for
    settled sessions (whose New York day has ended). The session in progress is asked
    about again each time, since a stock that hasn't traded yet today may trade later."""

    def __init__(self, alpaca: Alpaca) -> None:
        self.alpaca = alpaca
        self._days: dict[str, tuple[date, frozenset[date]]] = {}
        """symbol -> (the last settled session at the fetch, sessions with a bar). Read only
        for sessions up to that settled one."""

    async def counts(self, symbol: str, asset_class: AssetClass, at: datetime) -> bool:
        """Whether `symbol` counts for a post at `at`.

        A stock or ETF needs a daily bar on the session on or after `at`. A post whose
        session hasn't opened yet (a live pre-market or weekend post) is checked against
        the latest session with data instead, and so is a post in a session that has no
        bar yet.
        """
        symbol = symbol.upper()
        if asset_class == "coin":
            return symbol in COINS
        if not STOCK_SYMBOL.fullmatch(symbol):
            return False
        now = self.alpaca.clock()
        session = min(session_on_or_after(at), latest_session_with_data(now))
        settled = last_settled_session(now)
        if session <= settled:
            return session in await self._settled_days(symbol, settled)
        if session in await self._recent_days(symbol, session):
            return True
        return trading_days_after(session, -1) in await self._settled_days(symbol, settled)

    async def _settled_days(self, symbol: str, settled: date) -> frozenset[date]:
        cached = self._days.get(symbol)
        if cached and cached[0] >= settled:
            return cached[1]
        now = self.alpaca.clock()
        bars = await self.alpaca.stock_bars(symbol, "1Day", HISTORY_START, now - SIP_DELAY)
        days = _sessions(bars)
        self._days[symbol] = (settled, days)
        return days

    async def _recent_days(self, symbol: str, session: date) -> frozenset[date]:
        """Sessions with a bar from `session` on, fetched now and not kept."""
        since = session_open(trading_days_after(session, -1))  # after the day before's bar
        now = self.alpaca.clock()
        return _sessions(await self.alpaca.stock_bars(symbol, "1Day", since, now - SIP_DELAY))


def _sessions(bars: list[Bar]) -> frozenset[date]:
    # A daily bar starts at midnight New York time; mapping its start to the session on or
    # after it holds whether Alpaca stamps midnight New York or midnight UTC.
    return frozenset(session_on_or_after(bar.start) for bar in bars)


async def all_instruments(conn: AsyncConnection) -> list[Instrument]:
    """Every instrument, in the order they were added."""
    rows = await conn.execute(select(instruments).order_by(instruments.c.id))
    return [Instrument.from_row(row) for row in rows]


async def instrument_by_slug(conn: AsyncConnection, slug: str) -> Instrument | None:
    """The instrument with this slug, if any."""
    row = (await conn.execute(select(instruments).where(instruments.c.slug == slug))).first()
    return None if row is None else Instrument.from_row(row)


async def add_instrument(
    conn: AsyncConnection,
    listings: Listings,
    symbol: str,
    name: str,
    asset_class: AssetClass,
    at: datetime,
) -> Instrument:
    """Add an instrument, after checking it counts at `at`. Adding one that exists
    returns it unchanged. The slug is the lowercase symbol, or, if an instrument that has
    since changed its ticker holds that slug, the symbol with -2, -3 and so on.

    A new symbol is checked with Alpaca inside `conn`'s transaction, which can take
    minutes while Alpaca rate-limits, so pass a connection whose transaction holds no
    locks the worker needs."""
    symbol = symbol.upper()
    by_symbol = select(instruments).where(instruments.c.symbol == symbol)
    if existing := (await conn.execute(by_symbol)).first():
        return Instrument.from_row(existing)
    if not await listings.counts(symbol, asset_class, at):
        raise DoesNotCount(f"{symbol} ({asset_class}) doesn't count at {at.isoformat()}")
    benchmark = (
        select(instruments.c.id)
        .where(instruments.c.slug == BENCHMARKS[asset_class])
        .scalar_subquery()
    )
    await conn.execute(
        insert(instruments)
        .values(
            slug=await _free_slug(conn, symbol.lower()),
            symbol=symbol,
            name=name,
            asset_class=asset_class,
            calendar="24/7" if asset_class == "coin" else "XNYS",
            alpaca_symbol=alpaca_symbol(symbol, asset_class),
            benchmark_id=benchmark,
        )
        .on_conflict_do_nothing(index_elements=[instruments.c.symbol])
    )
    return Instrument.from_row((await conn.execute(by_symbol)).one())


async def _free_slug(conn: AsyncConnection, base: str) -> str:
    taken = set(
        (
            await conn.execute(
                select(instruments.c.slug).where(
                    or_(instruments.c.slug == base, instruments.c.slug.startswith(f"{base}-"))
                )
            )
        ).scalars()
    )
    number = 2
    slug = base
    while slug in taken:
        slug, number = f"{base}-{number}", number + 1
    return slug


async def add_alias(
    conn: AsyncConnection,
    instrument_id: int,
    alias: str,
    kind: AliasKind,
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> None:
    """Record another way posts name an instrument, from `valid_from` to `valid_to` (both
    inclusive; None is open). Adding it again with the same start sets the new end."""
    if valid_from and valid_to and valid_from > valid_to:
        raise ValueError(f"alias {alias!r} would end on {valid_to}, before it starts")
    stmt = insert(instrument_aliases).values(
        alias=normalize_alias(alias),
        instrument_id=instrument_id,
        kind=kind,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    await conn.execute(
        stmt.on_conflict_do_update(
            constraint="instrument_aliases_key", set_={"valid_to": stmt.excluded.valid_to}
        )
    )


async def change_symbol(
    conn: AsyncConnection, instrument_id: int, new_symbol: str, on: date
) -> None:
    """A ticker change taking effect on `on`: the symbol changes, the slug stays, and the
    old ticker becomes an alias from the previous change (if any) to the day before.
    Running it again with the same new symbol only corrects that day."""
    current = (
        await conn.execute(
            select(instruments.c.symbol, instruments.c.asset_class).where(
                instruments.c.id == instrument_id
            )
        )
    ).one()
    new_symbol = new_symbol.upper()
    if current.asset_class == "coin":
        raise ValueError("a coin's symbol doesn't change")
    if not STOCK_SYMBOL.fullmatch(new_symbol):
        raise ValueError(f"{new_symbol!r} isn't a US ticker")
    a = instrument_aliases.c
    previous = (
        await conn.execute(
            select(a.alias, a.valid_from, a.valid_to)
            .where(
                a.instrument_id == instrument_id,
                a.kind == "old_ticker",
                a.valid_to.is_not(None),
            )
            .order_by(a.valid_to.desc())
            .limit(1)
        )
    ).first()
    day_before = on - timedelta(days=1)
    if new_symbol == current.symbol:
        if previous is not None:
            await add_alias(
                conn, instrument_id, previous.alias, "old_ticker", previous.valid_from, day_before
            )
        return
    holder = (
        await conn.execute(select(instruments.c.slug).where(instruments.c.symbol == new_symbol))
    ).scalar()
    if holder is not None:
        raise ValueError(f"{new_symbol} is already the symbol of {holder}")
    await conn.execute(
        update(instruments)
        .where(instruments.c.id == instrument_id)
        .values(symbol=new_symbol, alpaca_symbol=alpaca_symbol(new_symbol, current.asset_class))
    )
    since = None if previous is None else previous.valid_to + timedelta(days=1)
    await add_alias(conn, instrument_id, current.symbol, "old_ticker", since, day_before)


async def resolve_alias(conn: AsyncConnection, alias: str, on: date) -> list[Instrument]:
    """The instruments `alias` named on `on`."""
    a = instrument_aliases.c
    rows = await conn.execute(
        select(instruments)
        .join(instrument_aliases, a.instrument_id == instruments.c.id)
        .where(
            a.alias == normalize_alias(alias),
            or_(a.valid_from.is_(None), a.valid_from <= on),
            or_(a.valid_to.is_(None), a.valid_to >= on),
        )
        .order_by(instruments.c.id)
        .distinct()
    )
    return [Instrument.from_row(row) for row in rows]
