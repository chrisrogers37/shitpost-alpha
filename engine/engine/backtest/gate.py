"""Gate 0 version 1's numbers, in one place. `reports/gate0-v1.md` says what they mean;
every backtest run records that file's SHA-256."""

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

VERSION = "gate0-v1"
"""Also the seed text of every random draw."""
REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"
GATE_FILE = REPORTS_DIR / "gate0-v1.md"

DATA_START = date(2022, 2, 1)
ALERT_DELAY_SECONDS = 120
MIRRORS_DELAY_SECONDS = 1200
PREMARKET_MINUTES = 330
"""Pre-market entry applies from 04:00 New York time, 330 minutes before the 09:30 open."""
LOOK_BACK_MINUTES = 5
"""A price at T falls back to the close of a bar starting this many minutes before T."""
COIN_ENTRY_SECONDS = 300
"""A coin's entry bar must start within this long of the alert time."""
CLOSE_AT_LEAST_MINUTES = 30
BETA_SESSIONS = 120
BETA_MIN_RETURNS = 60

GATE_COST = 0.0020
LOW_COST = 0.0005
MIN_DAYS = 30
LAST_DAYS = 365
LAST_MIN_DAYS = 10
MAX_Q = 0.10
DRAWS = 10_000
RANDOM_TIMES = 100

MIN_MATCH_DAYS = 10
ONE_WAY = 0.60
BEAT_RANDOM = 0.0020
BURST_SECONDS = 1800

WILSON_Z = 1.959964
POWER_Z = 0.841621
"""80% power."""
ALPHA_Z = 1.644854
"""One-sided, 5% error."""


@dataclass(frozen=True)
class Pair:
    """An instrument (its slug, or "company" for the stock a post names) at one window."""

    instrument: str
    window: str

    @property
    def name(self) -> str:
        return f"{self.instrument}:{self.window}"


def pairs(text: str) -> tuple[Pair, ...]:
    return tuple(Pair(*item.split(":")) for item in text.split())


GATE_PAIRS = pairs(
    "spy:1h spy:close spy:1d qqq:1h qqq:close qqq:1d btc:1h btc:4h btc:24h company:close company:1d"
)
"""The 11 pairs per picker."""
ETH_PAIRS = pairs("eth:1h eth:4h eth:24h")
MINUTE_PAIRS = pairs("spy:5m spy:15m qqq:5m qqq:15m btc:5m btc:15m company:5m company:15m")
PREMARKET_PAIRS = pairs("spy:1h spy:close spy:1d qqq:1h qqq:close qqq:1d")
SECTOR_TOPICS = {"energy": "xle"}
"""The rules' topics that map cleanly to one sector fund."""
SECTOR_PAIRS = pairs("xle:1h xle:close xle:1d")
MARKET_SLUGS = ("spy", "qqq", "btc", "eth", "xle")
"""Instruments every market-link post is tested on (beside the companies it names)."""
EXTENDED_HOURS = frozenset({"spy", "qqq"})
"""The only instruments whose extended-hours bars are kept (for the pre-market entry)."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed(*parts: str) -> int:
    """A generator seed from text: the same text always gives the same draws."""
    digest = hashlib.sha256(":".join((VERSION, *parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")
