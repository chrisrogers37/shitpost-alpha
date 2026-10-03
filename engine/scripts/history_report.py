"""What the rules picker found over all history (run from engine/ after
`python -m engine extract`):

    python scripts/history_report.py

Prints posts per topic with each topic's share of all text posts, the share with a market
link, and the most-named instruments (posts naming each, by how the name was found).
"""

import argparse
import asyncio

from sqlalchemy import func, select

from engine.db import make_engine
from engine.extract.rules import current_rules
from engine.settings import Settings
from engine.tables import extractions, instruments, signal_mentions

TOP = 25


async def report(settings: Settings) -> None:
    version = current_rules().version
    ruled = (extractions.c.method == "rules") & (extractions.c.version == version)
    db = make_engine(settings.db_url)
    try:
        async with db.connect() as conn:
            total, linked = (
                await conn.execute(
                    select(func.count(), func.count().filter(extractions.c.market_link)).where(
                        ruled
                    )
                )
            ).one()
            topics = await conn.execute(
                select(extractions.c.topic, func.count())
                .where(ruled)
                .group_by(extractions.c.topic)
                .order_by(func.count().desc())
            )
            print(f"rules v{version}: {total:,} text posts; market link {linked / total:.1%}\n")
            print("| Topic | Posts | Share |\n| --- | ---: | ---: |")
            for topic, n in topics:
                print(f"| {topic} | {n:,} | {n / total:.1%} |")
            posts = func.count(func.distinct(signal_mentions.c.signal_key))
            named = await conn.execute(
                select(instruments.c.symbol, posts, signal_mentions.c.found_by)
                .select_from(signal_mentions.join(extractions).join(instruments))
                .where(ruled, signal_mentions.c.counted)
                .group_by(instruments.c.symbol, signal_mentions.c.found_by)
            )
            by_symbol: dict[str, dict[str, int]] = {}
            for symbol, n, found_by in named:
                by_symbol.setdefault(symbol, {})[found_by] = n
            any_way = await conn.execute(
                select(instruments.c.symbol, posts)
                .select_from(signal_mentions.join(extractions).join(instruments))
                .where(ruled, signal_mentions.c.counted)
                .group_by(instruments.c.symbol)
                .order_by(posts.desc(), instruments.c.symbol)
                .limit(TOP)
            )
            print("\n| Instrument | Posts | Found by |\n| --- | ---: | --- |")
            for symbol, n in any_way:
                how = ", ".join(f"{k} {v:,}" for k, v in sorted(by_symbol[symbol].items()))
                print(f"| {symbol} | {n:,} | {how} |")
    finally:
        await db.dispose()


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    asyncio.run(report(Settings()))


if __name__ == "__main__":
    main()
