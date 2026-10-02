"""The PR 3 claims about Alpaca, one test each, on answers recorded 2 Oct 2026
(tests/fixtures/alpaca_claims/). Bar numbers there are stand-ins; the rest is Alpaca's."""

from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from engine.market.alpaca import SIP_DELAY, Bar, TooRecent
from engine.market.bars import is_final_day
from engine.settings import Settings
from tests.feeds_helpers import fixture_json
from tests.market_helpers import FakeAlpaca, market_settings

NEW_YORK = ZoneInfo("America/New_York")


def claim(name: str) -> dict[str, Any]:
    recorded: dict[str, Any] = fixture_json(f"alpaca_claims/{name}.json")
    return recorded


def bars(body: dict[str, Any]) -> list[Bar]:
    (series,) = body["bars"].values()
    return [Bar.parse(item) for item in series]


def window(recorded: dict[str, Any]) -> tuple[datetime, datetime]:
    params = recorded["request"]["params"]
    return datetime.fromisoformat(params["start"]), datetime.fromisoformat(params["end"])


def test_a_minute_history_reaches_2016() -> None:
    recorded = claim("a_spy_minutes_2016-01-04")
    spy = bars(recorded["body"])
    assert recorded["status"] == 200 and recorded["bars_returned"] > 390  # with extended hours
    assert spy[0].start == datetime(2016, 1, 4, 9, tzinfo=UTC)  # 04:00 New York
    assert spy[-1].start == datetime(2016, 1, 5, tzinfo=UTC)  # a bar at `end` is included


async def test_b_alpaca_refuses_what_the_client_refuses() -> None:
    allowed, refused = claim("b_sip_ending_16_minutes_ago"), claim("b_sip_ending_5_minutes_ago")
    assert allowed["status"] == 200 and allowed["bars_returned"] > 0
    assert refused["status"] == 403 and refused["body"] == fixture_json("alpaca_error.json")
    now = datetime.fromisoformat(allowed["recorded_at"])
    fake = FakeAlpaca()
    async with fake.client(market_settings(), now=now) as alpaca:
        await alpaca.stock_bars("SPY", "1Min", *window(allowed))
        with pytest.raises(TooRecent):
            await alpaca.stock_bars("SPY", "1Min", *window(refused))
    assert len(fake.requests) == 1


def test_c_the_limit_is_200_a_minute_and_the_client_stays_under_it() -> None:
    recorded = claim("a_spy_minutes_2016-01-04")
    assert recorded["headers"]["x-ratelimit-limit"] == "200"
    reset = float(recorded["headers"]["x-ratelimit-reset"])  # epoch seconds, as the retry reads it
    assert 0 < reset - datetime.fromisoformat(recorded["recorded_at"]).timestamp() <= 120
    assert Settings.model_fields["alpaca_calls_per_minute"].default < 200


@pytest.mark.parametrize("coin", ["btc", "eth"])
def test_d_coins_have_minutes_from_february_2022_and_days_from_2021(coin: str) -> None:
    minutes = claim(f"d_{coin}_minutes_2022-02-01")
    assert minutes["bars_returned"] > 1400
    assert bars(minutes["body"])[0].start == datetime(2022, 2, 1, tzinfo=UTC)
    daily = bars(claim(f"d_{coin}_first_daily")["body"])  # asked from 2010
    assert daily[0].start == datetime(2021, 1, 1, tzinfo=UTC)
    assert {bar.start.time() for bar in daily} == {time(0)}  # coin days are UTC days


def test_e_meta_serves_the_bars_from_when_it_traded_as_fb() -> None:
    meta = [bar.start.date() for bar in bars(claim("e_meta_june_2022")["body"])]
    fb = [bar.start.date() for bar in bars(claim("e_fb_june_2022")["body"])]
    assert meta[0] == date(2022, 6, 1) and meta[-1] == date(2022, 6, 15)
    assert fb == [day for day in meta if day < date(2022, 6, 9)]  # FB stops at the rename


def test_f_adjustment_all_takes_out_the_nvda_split() -> None:
    adjusted = bars(claim("f_nvda_split_all")["body"])
    raw = bars(claim("f_nvda_split_raw")["body"])
    ratios = {a.start.date(): r.close / a.close for a, r in zip(adjusted, raw, strict=True)}
    split = date(2024, 6, 10)
    assert all(ratio == pytest.approx(10, rel=0.01) for d, ratio in ratios.items() if d < split)
    assert all(ratio == pytest.approx(1, rel=0.01) for d, ratio in ratios.items() if d >= split)


def test_g_a_session_in_progress_has_a_bar_that_is_not_final() -> None:
    recorded = claim("g_spy_daily_during_a_session")
    now = datetime.fromisoformat(recorded["recorded_at"])
    today = bars(recorded["body"])[-1]
    assert window(recorded)[1] == now - SIP_DELAY
    assert today.start.astimezone(NEW_YORK).date() == now.astimezone(NEW_YORK).date()
    assert not is_final_day(today, now)


def test_h_fb_still_returns_facebook_s_bars() -> None:
    fb = [bar.start.date() for bar in bars(claim("h_fb_january_2021")["body"])]
    assert fb == [date(2021, 1, day) for day in (4, 5, 6, 7, 8)]


def test_stock_days_start_at_midnight_new_york() -> None:
    summer = bars(claim("f_nvda_split_all")["body"])
    winter = bars(fixture_json("alpaca_stock_bars_page1.json"))
    assert {bar.start.astimezone(NEW_YORK).time() for bar in summer + winter} == {time(0)}
    assert winter[0].start.hour == 5 and summer[0].start.hour == 4
