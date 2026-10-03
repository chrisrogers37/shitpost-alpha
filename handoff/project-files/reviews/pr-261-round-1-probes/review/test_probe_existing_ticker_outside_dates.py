"""Probe (coordinator's lead): a model's ticker for an instrument that exists but isn't
that ticker's holder on the post's date skips the date window. book.ticker() says no
(the hold starts later), so map_item calls add_new; add_instrument finds the existing row
by symbol and returns it *without* the "counts at the post's time" check; book.add() then
gives it a hold with no start or end, and the mention is counted.

PSKY's ticker and its "paramount" name hold from 2025-08-07 in aliases.json (Paramount
Global before the merger is listed as delisted/unmapped), yet a 2024 post's "PSKY" maps.
Same for VG (Venture Global listed 2025-01-24) on a January 2024 post about the LNG
export pause, and META before 2022-06-09 (when "META" was another fund's ticker). Within that book
the ticker then maps on every date. The rules don't see it: Scorer.handle and run_ai_pick
pick the rules from a separate book loaded before record_ai, and the book is reloaded per
post, so the damage stays inside that post's AI mentions.

Passes while the window is skipped.
"""

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import Item, map_item
from engine.extract.names import load_book
from engine.extract.rules import current_rules
from engine.extract.score import new_ticker_adder
from tests.extract_helpers import CountsAll, sync_names


async def test_an_existing_ticker_maps_before_its_hold_starts(db: AsyncEngine) -> None:
    await sync_names(db)
    cases = [
        (Item("Paramount Skydance", "PSKY", "stock", "explicit", ""), datetime(2024, 5, 1, 15, tzinfo=UTC)),
        (Item("Zuckerberg's company", "META", "stock", "implied", ""), datetime(2022, 5, 2, 15, tzinfo=UTC)),
        # Biden's LNG export pause, Jan 2024: Venture Global only listed on 2025-01-24
        (Item("Venture Global LNG", "VG", "stock", "implied", ""), datetime(2024, 1, 27, 15, tzinfo=UTC)),
    ]  # fmt: skip
    for item, at in cases:
        listings = CountsAll()
        async with db.begin() as conn:
            book = await load_book(conn, current_rules())
            assert book.ticker(item.ticker or "", at.date()) is None  # not its ticker that day
            mention = await map_item(book, item, at, new_ticker_adder(conn, listings))
            assert mention.counted and mention.unmapped is None
            assert book.instruments[mention.instrument_id or 0].symbol == item.ticker
            assert listings.asked == []  # the "counts at the post's time" check never ran
            # and now the ticker holds on any date in this book:
            assert book.ticker(item.ticker or "", date(2000, 1, 3)) == mention.instrument_id
