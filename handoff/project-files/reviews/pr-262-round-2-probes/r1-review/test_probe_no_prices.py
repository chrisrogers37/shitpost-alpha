"""Probe: the no-prices guard (tests/web/test_no_prices.py) misses common price field names
and routes left out of the OpenAPI schema. Each test PASSES while the gap is real."""

from engine.web.app import create_app
from engine.web.models import ApiModel, ApiResponse
from engine.web.router import ApiRouter
from engine.web.settings import WebSettings
from engine.web.deps import StreamId
from tests.web.conftest import MakeClient
from tests.web.test_no_prices import price_fields


def test_plural_and_ohlcv_price_fields_pass_the_guard(web_settings: WebSettings) -> None:
    class Candle(ApiModel):
        ohlcv: list[float]  # "ohlc" is a token, "ohlcv" is not
        highs: list[float]
        lows: list[float]

    class Chart(ApiResponse):
        prices: list[float]  # the most natural name for a list of prices
        closes: list[float]
        opens: list[float]
        volumes: list[int]
        bids: list[float]
        asks: list[float]
        candles: list[Candle]

    router = ApiRouter()
    router.add_api_route("/chart", lambda: None, response_model=Chart)
    # Every one of these names is a raw price or volume, and the guard flags none.
    assert price_fields(create_app(web_settings, [router])) == set()


async def test_a_route_left_out_of_the_schema_is_never_walked(
    web_settings: WebSettings, make_client: MakeClient
) -> None:
    class Quote(ApiResponse):
        close_price: float

    router = ApiRouter()

    @router.get("/quote", response_model=Quote, include_in_schema=False)
    async def quote(stream_id: StreamId) -> Quote:
        return Quote(stream_id=stream_id, close_price=187.23)

    # ApiRouter accepts it, and the guard does not see it...
    assert price_fields(create_app(web_settings, [router])) == set()
    # ...while the route is live under /api/v1 and serves the raw price.
    response = await make_client(router).get("/api/v1/quote")
    assert response.status_code == 200 and response.json()["close_price"] == 187.23


def test_a_serialization_alias_hides_a_price_field(web_settings: WebSettings) -> None:
    from pydantic import Field

    class Quote(ApiResponse):
        close_price: float = Field(serialization_alias="c")

    router = ApiRouter()
    router.add_api_route("/quote", lambda: None, response_model=Quote)
    assert price_fields(create_app(web_settings, [router])) == set()
