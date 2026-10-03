"""Round 2, offline: the rules picker over the CC0 archive copy's text posts (and the 300
held-out posts from the spot-check file), with the name book sync-names makes (aliases.json
plus the seeded SPY, QQQ, BTC, ETH), optionally plus instruments an AI run could add.

Run from a checkout's engine/ with PYTHONPATH set; writes one JSON of answers.

    history_identity.py OUT.json [AI-ADDED,TICKERS]
"""

import csv
import json
import sys
from pathlib import Path

from engine.extract.rules import AliasRow, Listed, NameBook, current_rules, pick
from engine.feeds.cnn import cnn_post
from engine.feeds.posts import status_time

CC0 = Path(
    "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/"
    "review-259/cc0/data/truth_archive.json"
)
SPOT = Path("/mnt/project-files/engine/pr4/precision-sample.csv")
RULES = current_rules()


def book(added: list[str]) -> NameBook:
    listed = [
        Listed(1, "SPY", "SPDR S&P 500 ETF Trust", "etf"),
        Listed(2, "BTC", "Bitcoin", "coin"),
        Listed(3, "QQQ", "Invesco QQQ Trust", "etf"),
        Listed(4, "ETH", "Ether", "coin"),
    ]
    ids = {i.symbol: i.id for i in listed}
    rows = []
    for number, spec in enumerate(RULES.aliases, start=10):
        if spec.symbol not in ids:
            listed.append(Listed(number, spec.symbol, spec.name, spec.asset_class))
            ids[spec.symbol] = number
        iid = ids[spec.symbol]
        rows += [AliasRow(n, iid, "name", spec.valid_from, None) for n in spec.names]
        rows += [AliasRow(o.ticker, iid, "old_ticker", None, o.to) for o in spec.old_tickers]
    for number, symbol in enumerate(added, start=900):
        listed.append(Listed(number, symbol, symbol, "stock"))  # as the adder names it
    return NameBook.build(RULES, listed, rows)


def main() -> None:
    out = Path(sys.argv[1])
    added = [s for s in (sys.argv[2] if len(sys.argv) > 2 else "").split(",") if s]
    names = book(added)
    posts: dict[str, tuple[str, object]] = {}
    for item in json.loads(CC0.read_text("utf-8")):
        post = cnn_post(item)
        if post.not_scored is None:
            posts[post.key] = (post.text, post.posted_at)
    with SPOT.open(newline="") as file:
        for row in csv.DictReader(file):
            key = row["key"]
            posts.setdefault(key, (row["text"], status_time(key.split(":", 1)[1])))
    answers = {}
    for key, (text, at) in posts.items():
        result = pick(names, text, at)  # type: ignore[arg-type]
        answers[key] = [
            result.market_link,
            result.topic,
            list(result.symbols),
            sorted(
                (m.normalized, m.found_by, m.counted, names.instruments[m.instrument_id].symbol
                 if m.instrument_id else None)
                for m in result.mentions
            ),
        ]  # fmt: skip
    out.write_text(json.dumps(answers, sort_keys=True))
    print(f"{len(answers)} text posts; added={added}")


if __name__ == "__main__":
    main()
