"""Verify only, offline: load the CC0 archive copy already on disk (cloned by an earlier
review, commit 40a8834) into the throwaway database as imported history, then, after
`sync-names` (stub listings) and `python -m engine extract`, compare the rules' recorded
answers for the labelled posts it holds with the builder's spot-check file.

    cc0_probe.py import
    cc0_probe.py compare SPOT_CSV
"""

import asyncio
import csv
import json
import sys
from pathlib import Path

from engine.db import make_engine
from engine.extract.rules import current_rules
from engine.feeds.history import import_part
from engine.settings import Settings
from scripts.precision import answers, names_text, read_labels

CC0 = Path(
    "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/"
    "review-259/cc0/data/truth_archive.json"
)


async def load() -> None:
    db = make_engine(Settings().db_url)
    try:
        part = await import_part(db, "cc0 (local copy)", "cc0_archive", json.loads(CC0.read_text()))
        print(part.line())
    finally:
        await db.dispose()


async def compare(spot: Path) -> None:
    labels = read_labels()
    with spot.open(newline="") as file:
        rows = {row["key"]: row for row in csv.DictReader(file)}
    db = make_engine(Settings().db_url)
    try:
        async with db.connect() as conn:
            found = await answers(conn, "rules", current_rules().version, labels)
            from sqlalchemy import select

            from engine.tables import signals

            texts = dict(
                (await conn.execute(select(signals.c.key, signals.c.text).where(
                    signals.c.key.in_(list(labels))))).all()
            )  # fmt: skip
    finally:
        await db.dispose()
    same = differ = text_differs = 0
    for key, answer in found.items():
        row = rows[key]
        theirs = (row["rules v1 market_link"], row["rules v1 topic"], row["rules v1 names"])
        mine = (str(answer.market_link), answer.topic, names_text(answer.names))
        if texts[key] != row["text"]:
            text_differs += 1
        if theirs == mine:
            same += 1
        else:
            differ += 1
            print("DIFFERS", key, row["group"], theirs, mine)
    print(f"labelled posts in this database: {len(found)}; same answer {same}, differ {differ}; "
          f"text differs from the spot-check file: {text_differs}")  # fmt: skip


if __name__ == "__main__":
    if sys.argv[1] == "import":
        asyncio.run(load())
    else:
        asyncio.run(compare(Path(sys.argv[2])))
