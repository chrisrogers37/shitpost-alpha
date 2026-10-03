"""Probe: one model naming a new ticker adds it to engine.instruments (map_item -> add_new,
even when the vote doesn't count it), and from then on rules version 1 matches that
ticker as a bare word in every post, with no collision-list review. "ICE"
(Intercontinental Exchange, which owns the NYSE) is the sharp case: in his posts ICE is
Immigration and Customs Enforcement. After one AI answer names ICE, an ICE-raid post is
scored by the *same frozen rules version* as a companies post with a market link.

So rules v1's answer depends on when it ran, `extract` (idempotent per version) leaves
history scored before and after the add inconsistent, and live posts get false market
links. Pure in-memory; no database, no Alpaca.

Passes while the bug is real.
"""

from datetime import UTC, datetime

from engine.extract.ai import Item, map_item
from engine.extract.rules import Listed, pick
from tests.test_rules import file_book

WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
RAID = "ICE agents arrested 300 illegal alien criminals in Chicago. Great job by ICE!"


async def test_an_ai_added_ticker_turns_into_a_rules_bare_ticker() -> None:
    book = file_book()
    before = pick(book, RAID, WHEN)
    assert before.symbols == () and before.topic == "border_crime" and not before.market_link

    async def counts_on_alpaca(ticker: str, asset: str, at: datetime) -> Listed:
        return Listed(999, ticker, ticker, "stock")  # ICE trades on the NYSE: it counts

    # One model (not the vote) names the exchange operator on some NYSE post.
    item = Item("Intercontinental Exchange", "ICE", "stock", "implied", "owns the NYSE")
    mention = await map_item(book, item, WHEN, counts_on_alpaca)
    assert mention.counted

    after = pick(book, RAID, WHEN)  # same text, same rules version 1
    assert after.version == before.version == 1
    assert after.symbols == ("ICE",)
    assert after.topic == "companies" and after.market_link
