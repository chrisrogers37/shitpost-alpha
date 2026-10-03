"""Reproduce the rules' precision table offline (verify only): run the committed rules
picker on the text in the builder's spot-check file (precision-sample.csv), compare its
answers with that file's "rules v1" columns, then score them against the committed labels
and groups with scripts/precision.py's own score() and print the table."""

import csv
import sys
from collections import defaultdict
from pathlib import Path

from engine.extract.rules import AliasRow, Listed, NameBook, current_rules, pick
from engine.feeds.posts import status_time
from scripts.precision import Answer, Tally, read_groups, read_labels, score

SPOT = Path(sys.argv[1])
RULES = current_rules()


def book() -> NameBook:
    """aliases.json's instruments and names, plus the seeded SPY and QQQ (as sync-names
    makes them; BTC and ETH are seeded too and come from the file)."""
    listed = [Listed(1, "SPY", "SPDR S&P 500 ETF", "etf"), Listed(2, "QQQ", "Invesco QQQ", "etf")]
    rows = []
    for number, spec in enumerate(RULES.aliases, start=10):
        listed.append(Listed(number, spec.symbol, spec.name, spec.asset_class))
        rows += [AliasRow(n, number, "name", spec.valid_from, None) for n in spec.names]
        rows += [AliasRow(o.ticker, number, "old_ticker", None, o.to) for o in spec.old_tickers]
    return NameBook.build(RULES, listed, rows)


def names_text(names: dict[str, str]) -> str:
    return ";".join(f"{s}:{k}" for s, k in sorted(names.items()))


def main() -> None:
    names = book()
    labels = read_labels()
    groups = read_groups()
    picked: dict[str, Answer] = {}
    differ = 0
    with SPOT.open(newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        key = row["key"]
        at = status_time(key.split(":", 1)[1])
        result = pick(names, row["text"], at)
        counted = {names.instruments[m.instrument_id].symbol: "e" for m in result.mentions
                   if m.counted and m.instrument_id}  # fmt: skip
        picked[key] = Answer(result.market_link, result.topic, counted)
        theirs = (row["rules v1 market_link"], row["rules v1 topic"], row["rules v1 names"])
        mine = (str(result.market_link), result.topic, names_text(counted))
        if theirs != mine:
            differ += 1
            print("DIFFERS", key, theirs, mine)
        if row["group"] != groups[key]:
            print("GROUP DIFFERS", key, row["group"], groups[key])
        label = labels[key]
        if (row["label_market_link"], row["label_topic"], row["label_names"]) != (
            str(label.market_link), label.topic, names_text(label.names)
        ):
            print("LABEL DIFFERS", key)
    print(f"{len(rows)} posts in the spot-check file; {differ} rules answers differ from it")
    by_group: dict[str, list[str]] = defaultdict(list)
    for key in sorted(labels):
        by_group[groups[key]].append(key)
    tally = Tally()
    for group, keys in sorted(by_group.items(), key=lambda item: item[0] != "window"):
        score(labels, picked, keys, f"{group} ({len(keys)})", tally)
    print("| Group | Measure | Precision | Recall |")
    print("| --- | --- | --- | --- |")
    for line in tally.lines:
        print("| " + " | ".join(line) + " |")


if __name__ == "__main__":
    main()
