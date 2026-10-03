"""Probe: map_item maps by "an alias appears in the model's name" before it looks at the
model's ticker, so a different company whose name contains an alias word is mapped to the
alias's instrument even when the model gave the right, different ticker. In-memory book;
the ticker the model gave is simply ignored.

Passes while the name wins over a conflicting ticker.
"""

from datetime import UTC, datetime

from engine.extract.ai import Item, map_item
from tests.test_rules import file_book

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)


async def test_a_longer_name_with_an_alias_word_beats_the_given_ticker() -> None:
    book = file_book()
    cases = {
        Item("Apple Hospitality REIT", "APLE", "stock", "explicit", ""): "AAPL",
        Item("Meta Materials", "MMAT", "stock", "explicit", ""): "META",
        Item("Ford Motor Credit", "F", "stock", "explicit", ""): "F",  # fine: same company
    }
    for item, symbol in cases.items():
        mention = await map_item(book, item, WHEN, None)
        assert mention.counted and book.instruments[mention.instrument_id or 0].symbol == symbol
