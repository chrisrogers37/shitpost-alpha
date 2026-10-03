"""Probe (not part of the PR): which price-like names does the PR's no-prices walk miss?"""
from engine.web.app import create_app
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from tests.web.test_no_prices import price_fields

NAMES = ["prices", "closes", "highs", "lows", "opens", "volumes", "bids", "asks", "closePrices",
         "price_usd", "lastPx", "quote", "ohlcv", "candles", "close_px", "PRICE", "vwapUSD", "askSize", "Price2", "price2"]
fields = {n: (float, 0.0) for n in NAMES}
from pydantic import create_model
Item = create_model("Item", __base__=ApiModel, **fields)  # type: ignore[call-overload]
Body = create_model("Body", __base__=ApiResponse, items=(list[Item], []))  # type: ignore[call-overload]
router = ApiRouter()
router.add_api_route("/p", lambda: None, response_model=Body)
found = price_fields(create_app(WebSettings(database_url="postgresql://x@127.0.0.1:1/x"), [router]))
print("caught:", sorted(found))
print("missed:", sorted(set(NAMES) - found))
