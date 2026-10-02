"""Tickers that are also words (GOLD, TAX, WAR, ...), kept as versioned data in
collisions.json. A symbol on the list counts only as a cashtag ($GOLD) or through a name
alias. PR 4 extends the list from what posts say."""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from engine.market.instruments import STOCK_SYMBOL

COLLISIONS_FILE = Path(__file__).with_name("collisions.json")


@dataclass(frozen=True)
class Collisions:
    version: int
    symbols: frozenset[str]

    def mention_counts(self, symbol: str, *, cashtag: bool) -> bool:
        """Whether a ticker written in a post counts: a cashtag always does, a bare word
        only if it isn't on the list."""
        return cashtag or symbol.upper() not in self.symbols


def parse_collisions(text: str) -> Collisions:
    """The list from collisions.json's text, refused unless its version is a positive
    integer and its symbols are uppercase tickers, sorted and unique."""
    data = json.loads(text)
    version, symbols = data["version"], data["symbols"]
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"collisions version must be a positive integer, not {version!r}")
    bad = [s for s in symbols if not isinstance(s, str) or not STOCK_SYMBOL.fullmatch(s)]
    if bad:
        raise ValueError(f"collisions: not uppercase tickers: {bad}")
    if symbols != sorted(set(symbols)):
        raise ValueError("collisions: keep symbols sorted and unique")
    return Collisions(version, frozenset(symbols))


@cache
def load_collisions(path: Path = COLLISIONS_FILE) -> Collisions:
    """The list in `path` (collisions.json), read once."""
    return parse_collisions(path.read_text("utf-8"))
