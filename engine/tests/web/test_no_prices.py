"""No API response may carry a price: public output is % moves only, never raw prices."""

import re
from typing import Any

from fastapi import FastAPI

from engine.web.app import create_app
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings

PRICE_TOKENS = {"price", "open", "high", "low", "close", "vwap", "volume", "bid", "ask", "ohlc"}
PRICE_TOKENS |= {"bar", "bars"}

ALLOWED = {
    "market_open": "whether the market is open now: a flag, not an opening price",
}


def tokens(name: str) -> set[str]:
    """Split on underscores and camel case: closePrice and close_price give close, price."""
    words = re.split(r"_|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", name)
    return {word.lower() for word in words if word}


def price_fields(app: FastAPI) -> set[str]:
    """Every field name in every route's response schemas that looks like a price."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    found: set[str] = set()
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref not in seen:
                seen.add(ref)
                walk(components[ref.rsplit("/", 1)[-1]])
            for name in node.get("properties", {}):
                if name not in ALLOWED and tokens(name) & PRICE_TOKENS:
                    found.add(name)
            for value in node.values():
                walk(value)

    for operations in schema["paths"].values():
        for operation in operations.values():
            walk(operation.get("responses", {}))
    return found


def test_tokens_split_both_spellings() -> None:
    assert tokens("close_price") == tokens("closePrice") == {"close", "price"}
    assert tokens("OHLCBars") == {"ohlc", "bars"}
    assert tokens("market_open") == {"market", "open"}


def test_no_response_field_is_a_price(web_settings: WebSettings) -> None:
    assert price_fields(create_app(web_settings)) == set()


def test_the_check_catches_a_price_field(web_settings: WebSettings) -> None:
    class Quote(ApiModel):
        close_price: float

    class Quotes(ApiResponse):
        quotes: list[Quote]
        lastTradeVolume: int
        market_open: bool

    router = ApiRouter()
    router.add_api_route("/quotes", lambda: None, response_model=Quotes)
    assert price_fields(create_app(web_settings, [router])) == {"close_price", "lastTradeVolume"}
