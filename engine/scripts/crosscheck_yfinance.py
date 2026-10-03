"""Cross-check Alpaca's daily closes against Yahoo's, through yfinance.

Run from engine/, with the Alpaca keys set (it reads no database):

    pip install -e ".[crosscheck]"
    python scripts/crosscheck_yfinance.py

It compares closes adjusted for splits and dividends on the days both sources have since
2022-02-01, for the four seeded instruments plus AAPL, NVDA and META, and lists the days
more than 0.5% apart. Coins are compared only if Alpaca's coin day starts at midnight UTC,
as Yahoo's does. Yahoo's terms are personal and non-commercial: its numbers stay in this
report and never reach anything public. Nothing in the engine imports this.
"""

import argparse
import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from engine.market.alpaca import SIP_DELAY, Alpaca, Bar
from engine.market.bars import is_final_day
from engine.market.calendar import session_on_or_after
from engine.market.instruments import COINS, alpaca_symbol
from engine.settings import Settings

SINCE = date(2022, 2, 1)
TOLERANCE = 0.005
CHECKS = ("SPY", "QQQ", "BTC", "ETH", "AAPL", "NVDA", "META")


@dataclass(frozen=True)
class Comparison:
    symbol: str
    days: int
    apart: list[tuple[date, float, float]]
    only_alpaca: int
    only_yahoo: int

    def lines(self) -> list[str]:
        worst = max((abs(a / y - 1) for _, a, y in self.apart), default=0.0)
        head = (
            f"{self.symbol}: {self.days:,} days in both; {len(self.apart):,} over "
            f"{TOLERANCE:.1%} apart (worst {worst:.2%}); only Alpaca {self.only_alpaca:,}, "
            f"only Yahoo {self.only_yahoo:,}"
        )
        return [head] + [f"  {day}: alpaca {a:.4f}, yahoo {y:.4f}" for day, a, y in self.apart]


def compare(symbol: str, alpaca: dict[date, float], yahoo: dict[date, float]) -> Comparison:
    """The days both sources have, and those more than TOLERANCE apart."""
    both = sorted(alpaca.keys() & yahoo.keys())
    apart = [
        (day, alpaca[day], yahoo[day])
        for day in both
        if not math.isclose(alpaca[day], yahoo[day], rel_tol=TOLERANCE)
    ]
    only_alpaca, only_yahoo = len(alpaca.keys() - yahoo.keys()), len(yahoo.keys() - alpaca.keys())
    return Comparison(symbol, len(both), apart, only_alpaca, only_yahoo)


def bar_day(bar: Bar, coin: bool) -> date:
    """Coins by UTC date (as Yahoo dates them); stocks by trading session."""
    return bar.start.date() if coin else session_on_or_after(bar.start)


async def alpaca_bars(alpaca: Alpaca, symbol: str, coin: bool) -> list[Bar]:
    """Alpaca's final daily bars since SINCE."""
    start = datetime.combine(SINCE, time(), UTC)
    now = alpaca.clock()
    if coin:
        bars = await alpaca.coin_bars(alpaca_symbol(symbol, "coin"), "1Day", start, now)
    else:
        bars = await alpaca.stock_bars(symbol, "1Day", start, now - SIP_DELAY)
    return [bar for bar in bars if is_final_day(bar, now)]


def yahoo_closes(symbol: str) -> dict[date, float]:
    import yfinance  # the crosscheck extra; never a runtime dependency

    history: Any = yfinance.Ticker(symbol).history(
        start=SINCE.isoformat(), auto_adjust=True, actions=False
    )
    today = datetime.now(UTC).date()
    closes = {stamp.date(): float(close) for stamp, close in history["Close"].items()}
    return {day: close for day, close in closes.items() if day < today}


async def main() -> int:
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args()
    settings = Settings.model_validate({"database_url": "unused: this reads no database"})
    async with Alpaca(settings) as alpaca:
        for symbol in CHECKS:
            coin = symbol in COINS
            bars = await alpaca_bars(alpaca, symbol, coin)
            starts = sorted({bar.start.timetz() for bar in bars} - {time(tzinfo=UTC)})
            if coin and starts:
                print(f"{symbol}: skipped: Alpaca's coin days start at {starts[0]} UTC, not 00:00")
                continue
            ours = {bar_day(bar, coin): bar.close for bar in bars}
            theirs = await asyncio.to_thread(yahoo_closes, f"{symbol}-USD" if coin else symbol)
            print("\n".join(compare(symbol, ours, theirs).lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
