"""Test-only: stand-ins for the similarity model, the AI providers and Alpaca's "what
counts" check, and a quick way to fill the name tables."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import PROVIDERS, AiConfig, Client, Provider, Reply, current_ai_config
from engine.extract.names import sync_aliases
from engine.extract.rules import current_rules
from engine.extract.similarity import Embedded, normalized
from engine.market.instruments import AssetClass, Listings

FIXTURES = Path(__file__).parent / "fixtures"


class CountsAll(Listings):
    """Every stock counts, except those in `not_listed` (no Alpaca calls)."""

    def __init__(self, not_listed: Sequence[str] = ()) -> None:
        self.not_listed = {s.upper() for s in not_listed}
        self.asked: list[str] = []

    async def counts(self, symbol: str, asset_class: AssetClass, at: datetime) -> bool:
        self.asked.append(symbol.upper())
        if asset_class == "coin":
            return symbol.upper() in ("BTC", "ETH")
        return symbol.upper() not in self.not_listed


async def sync_names(db: AsyncEngine) -> None:
    """aliases.json's instruments and names, as `sync-names` writes them."""
    async with db.begin() as conn:
        await sync_aliases(conn, CountsAll(), current_rules(), datetime(2026, 10, 1))


class StubEmbedder:
    """Deterministic vectors from the text's hash; texts sharing a first word score
    higher together than unrelated ones."""

    version = "stub@0"
    dims = 8

    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[Embedded]:
        self.texts.extend(texts)
        rows = []
        for text in texts:
            first = text.split()[0].lower() if text.split() else ""
            seeds = [hashlib.sha256(part.encode()).digest() for part in (first, text)]
            row = np.frombuffer(seeds[0][: self.dims], dtype=np.uint8).astype(np.float32) * 4
            row += np.frombuffer(seeds[1][: self.dims], dtype=np.uint8).astype(np.float32)
            rows.append(row)
        vectors = normalized(np.array(rows))
        return [Embedded(v, len(t) > 2000) for v, t in zip(vectors, texts, strict=True)]


def answer(market_link: bool, *items: tuple[str, str | None, str, str]) -> str:
    """A model's JSON answer: items are (name, ticker, asset, link)."""
    instruments = [
        {"name": n, "ticker": t, "asset": a, "link": link, "why": f"names {n}"}
        for n, t, a, link in items
    ]
    return json.dumps({"market_link": market_link, "instruments": instruments})


@dataclass
class StubClient:
    """A provider that answers from a table (post words -> answer text), or with
    `default`; `fail` raises it instead, `delay` waits first."""

    provider: Provider
    model: str = "stub-model"
    answers: dict[str, str] = field(default_factory=dict)
    default: str = '{"market_link": false, "instruments": []}'
    fail: Exception | None = None
    delay: float = 0.0
    output_tokens: int = 100
    asked: list[str] = field(default_factory=list)

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply:
        import asyncio

        self.asked.append(user)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail is not None:
            raise self.fail
        words = user.removeprefix("Post:\n").split("\n\nQuoted post:\n")[0]
        text = self.answers.get(words, self.default)
        body = {"id": "stub", "content": text}
        return Reply(body, text, 1000, cached_input_tokens=0, output_tokens=self.output_tokens)


def stub_clients(**answers: dict[str, str]) -> dict[str, Client]:
    return {name: StubClient(name, answers=table) for name, table in answers.items()}  # type: ignore[arg-type]


def ready_config(**changes: Any) -> AiConfig:
    """The AI picker version with models and checked prices filled in, as B2 will."""
    from dataclasses import replace
    from datetime import date
    from decimal import Decimal

    from engine.extract.ai import ModelSpec, Price

    base = current_ai_config()
    price = Price(Decimal(2), Decimal("0.5"), Decimal(8), date(2026, 10, 2))
    models: dict[str, ModelSpec] = {
        name: ModelSpec(name, f"{name}-test-2025", price, 0.0) for name in PROVIDERS
    }
    return replace(base, models=models, **changes)
