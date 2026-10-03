"""No API response may carry a price: public output is % moves only, never raw prices.

The walk reads every field name in every route's response schemas, and refuses an object
whose keys the schema doesn't list (a dict, an Any, a model that allows extra fields), as
a price could hide under such a key. The API sends what the schema shows: ApiRouter takes
only routes that declare and return an ApiResponse and are in the schema (create_app
checks every route), FastAPI checks each returned body against the route's model (a
cached body too, as the route returns it), and ApiModel forbids extra fields, aliases and
custom model serializers. test_api_conventions.py tests those rules."""

import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, computed_field

from engine.web.app import create_app
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from tests.web.conftest import NO_DATABASE

PRICE_TOKENS = {"price", "open", "high", "low", "close", "vwap", "volume", "bid", "ask", "bar"}
PRICE_TOKENS |= {"ohlc", "ohlcv"}

ALLOWED = {
    "market_open": "whether the market is open now: a flag, not an opening price",
}

TYPED = {"type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const"}
"""A schema with none of these keys accepts anything."""


def tokens(name: str) -> set[str]:
    """Split on underscores and camel case (closePrice and close_price give close, price),
    drop trailing digits, and give each plural's singular too (prices gives price)."""
    words = re.split(r"_|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", name)
    found: set[str] = set()
    for word in words:
        word = word.lower().rstrip("0123456789")
        if word:
            found |= {word, word.removesuffix("s")}
    return found


def walk_responses(app: FastAPI) -> tuple[set[str], set[str]]:
    """Every field name in every route's response schemas, and where an object there
    doesn't list its keys."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    names: set[str] = set()
    open_objects: set[str] = set()
    seen: set[str] = set()

    def walk(node: dict[str, Any], where: str) -> None:
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if name not in seen:
                seen.add(name)
                walk(components[name], name)
            return
        if not TYPED & node.keys() or (
            node.get("type") == "object" and node.get("additionalProperties") is not False
        ):
            open_objects.add(where)
        for name, field in node.get("properties", {}).items():
            names.add(name)
            walk(field, f"{where}.{name}")
        for key in ("items", "additionalProperties"):
            if isinstance(node.get(key), dict):
                walk(node[key], where)
        for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
            for option in node.get(key, []):
                walk(option, where)

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status, response in operation.get("responses", {}).items():
                for media in response.get("content", {}).values():
                    walk(media["schema"], f"{method.upper()} {path} {status}")
    return names, open_objects


def price_fields(app: FastAPI) -> set[str]:
    names, _ = walk_responses(app)
    return {name for name in names if name not in ALLOWED and tokens(name) & PRICE_TOKENS}


def test_tokens_split_both_spellings() -> None:
    assert tokens("close_price") == tokens("closePrice") == {"close", "price"}
    assert tokens("OHLCBars") == {"ohlc", "bars", "bar"}
    assert tokens("market_open") == {"market", "open"}
    assert tokens("prices") == {"prices", "price"} and tokens("price2") == {"price"}


def test_no_response_field_is_a_price() -> None:
    app = create_app(NO_DATABASE)
    assert price_fields(app) == set()
    assert walk_responses(app)[1] == set()


def test_the_check_catches_a_price_field() -> None:
    class Quote(ApiModel):
        close_price: float

    class Candle(ApiModel):
        ohlcv: list[float]
        highs: list[float]

    class Quotes(ApiResponse):
        quotes: list[Quote]
        candles: list[Candle]
        lastTradeVolume: int
        prices: list[float]
        closes: list[float]
        price2: float
        market_open: bool

        @computed_field  # type: ignore[prop-decorator]
        @property
        def closing_bid(self) -> float:
            return 0.0

    router = ApiRouter()

    @router.get("/quotes")
    async def quotes() -> Quotes:
        raise NotImplementedError

    found = price_fields(create_app(NO_DATABASE, [router]))
    assert found == {
        "close_price",
        "ohlcv",
        "highs",
        "lastTradeVolume",
        "prices",
        "closes",
        "price2",
        "closing_bid",
    }


def test_the_check_catches_an_object_that_does_not_list_its_keys() -> None:
    class Loose(BaseModel):  # not an ApiModel: extra keys are ignored, not refused
        n: int

    class Open(ApiResponse):
        by_ticker: dict[str, float]  # the keys are data: {"close": 187.23} would pass
        anything: Any
        maybe: list[Any] | None
        loose: Loose

    router = ApiRouter()

    @router.get("/open")
    async def open_() -> Open:
        raise NotImplementedError

    _, open_objects = walk_responses(create_app(NO_DATABASE, [router]))
    assert open_objects == {"Open.by_ticker", "Open.anything", "Open.maybe", "Loose"}
