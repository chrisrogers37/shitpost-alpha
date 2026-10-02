"""The AI picker: parsing each provider's answer, mapping names, the vote, keys."""

import json
import logging
import re
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import httpx2
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import (
    MANIFEST,
    SDK_HEADER_VARIABLES,
    AiPick,
    AiPicker,
    AnthropicMessages,
    Item,
    ModelAnswer,
    NotReady,
    OpenAIChat,
    PostText,
    Price,
    ask_model,
    build_clients,
    current_ai_config,
    load_ai_config,
    map_item,
    parse_answer,
    vote,
)
from engine.extract.names import load_book
from engine.extract.rules import Listed, Mention, RulesFileChanged, current_rules, pick
from engine.extract.score import new_ticker_adder
from engine.market.alpaca import AlpacaError
from engine.market.instruments import AssetClass
from engine.settings import Settings
from tests.extract_helpers import FIXTURES, CountsAll, StubClient, answer, ready_config, sync_names
from tests.test_rules import file_book

BOOK = file_book()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
CONFIG = ready_config()
OPENAI_KEY = "sk-test-openai-DO-NOT-LOG-1234567890"
XAI_KEY = "xai-test-DO-NOT-LOG-0987654321"
ANTHROPIC_KEY = "sk-ant-test-DO-NOT-LOG-1122334455"


def ai_fixture(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / "ai" / name).read_text("utf-8"))
    return loaded


def symbols(mentions: tuple[Mention, ...] | list[Mention]) -> set[str]:
    return {
        BOOK.instruments[m.instrument_id].symbol for m in mentions if m.counted and m.instrument_id
    }


# --- the version and the answer -----------------------------------------------------


def test_the_picker_version_loads_with_dated_models_and_checked_prices() -> None:
    config = current_ai_config()
    assert config.version == 1
    assert len(config.hash) == 64
    assert "market_link" in config.instructions
    assert set(config.schema["required"]) == {"market_link", "instruments"}
    assert not config.problems()
    for spec in config.models.values():
        assert re.search(r"\d{4}", spec.model or "")  # a dated snapshot, not an alias
    unpinned = replace(
        config, models={**config.models, "xai": replace(config.models["xai"], model=None)}
    )
    assert unpinned.problems() == ["xai: no model pinned"]


def test_cost_counts_cached_input_apart() -> None:
    price = Price(Decimal(2), Decimal("0.5"), Decimal(8), None)
    assert price.cost(1_000_000, 0, 0) == Decimal(2)
    assert price.cost(1_000_000, 1_000_000, 1_000_000) == Decimal("8.5")


def test_an_answer_is_checked_field_by_field() -> None:
    link, items = parse_answer(answer(True, ("Nvidia", "$nvda", "stock", "explicit")), 8, 100)
    assert link and items == [Item("Nvidia", "NVDA", "stock", "explicit", "names Nvidia")]
    many = answer(False, *[(f"Co {n}", None, "stock", "implied") for n in range(10)])
    assert len(parse_answer(many, 8, 100)[1]) == 8
    for bad in (
        "not json",
        '{"market_link": "yes", "instruments": []}',
        '{"market_link": true}',
        '{"market_link": true, "instruments": [{"name": "X"}]}',
        answer(True, ("X", "X", "bond", "explicit")),
    ):
        with pytest.raises(ValueError):
            parse_answer(bad, 8, 100)


# --- the providers, through their SDKs with hand-made answers -------------------------


async def test_openai_answer_through_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://elsewhere.example/v1")
    sent: list[httpx.Request] = []

    def route(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=ai_fixture("openai_chat_completion.unverified.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat(
            "openai", "gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http
        )
        result = await ask_model(client, CONFIG, PostText("Nvidia will spend").user_message())
    assert result.ok and result.market_link
    assert [i.ticker for i in result.items] == ["NVDA"]
    assert (result.reply and result.reply.cached_input_tokens) == 1024
    assert result.cost == Decimal("0.001240")  # 156 fresh x 2 + 1024 x 0.5 + 52 x 8, per million
    body = json.loads(sent[0].content)
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["strict"] is True
    assert sent[0].url.host == "api.openai.com"


async def test_xai_goes_through_the_openai_sdk_at_its_own_host() -> None:
    hosts: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(200, json=ai_fixture("xai_chat_completion.unverified.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat(
            "xai", "grok-test", XAI_KEY, temperature=0, timeout=15, http_client=http
        )
        result = await ask_model(client, CONFIG, "Post:\nNvidia")
    assert result.ok and hosts == ["api.x.ai"]


async def test_anthropic_answer_through_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://elsewhere.example")
    sent: list[httpx2.Request] = []

    def route(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json=ai_fixture("anthropic_message.unverified.json"))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(route)) as http:
        client = AnthropicMessages(
            "claude-test", ANTHROPIC_KEY, temperature=0, timeout=15, http_client=http
        )
        result = await ask_model(client, CONFIG, "Post:\nNvidia")
    assert result.ok and [i.name for i in result.items] == ["Nvidia"]
    assert sent[0].url.host == "api.anthropic.com"  # never a base URL from the environment
    body = json.loads(sent[0].content)
    assert body["temperature"] == 0
    assert body["output_config"]["format"]["type"] == "json_schema"


async def test_keys_never_reach_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    def route(request: httpx.Request) -> httpx.Response:
        message = f"Incorrect API key provided: {OPENAI_KEY}"
        return httpx.Response(401, json={"error": {"message": message, "type": "auth"}})

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat(
            "openai", "gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http
        )
        result = await ask_model(client, CONFIG, "Post:\nx", secrets=[OPENAI_KEY])
    assert result.error and "[key]" in result.error
    assert OPENAI_KEY not in result.error
    assert OPENAI_KEY not in caplog.text


def with_keys(settings: Settings, **keys: str) -> Settings:
    """Settings with ENGINE_ AI keys, put through the same checks as the environment's."""
    return Settings.model_validate(settings.model_dump() | keys)


ALL_KEYS = {"openai_key": OPENAI_KEY, "xai_key": XAI_KEY, "anthropic_key": ANTHROPIC_KEY}


def test_no_picker_without_all_three_keys_or_a_ready_version(settings: Settings) -> None:
    assert build_clients(settings, CONFIG) == {}
    with pytest.raises(NotReady, match="not set: ENGINE_OPENAI_KEY, ENGINE_XAI_KEY, ENGINE_ANT"):
        AiPicker.from_settings(settings, CONFIG)
    with pytest.raises(NotReady, match=r"not set: ENGINE_XAI_KEY, ENGINE_ANTHROPIC_KEY$"):
        AiPicker.from_settings(with_keys(settings, openai_key=OPENAI_KEY), CONFIG)
    unpinned = replace(
        CONFIG, models={**CONFIG.models, "xai": replace(CONFIG.models["xai"], model=None)}
    )
    with pytest.raises(NotReady, match=r"isn.t ready: xai: no model pinned$"):
        AiPicker.from_settings(with_keys(settings, **ALL_KEYS), unpinned)


def test_ai_keys_must_be_safe_in_a_header(settings: Settings) -> None:
    assert with_keys(settings, xai_key=f"  {XAI_KEY}\n").ai_keys == {"xai": XAI_KEY}
    for bad in ("xai-a b", "xai-a\nb", "xai-\u00e9"):
        with pytest.raises(ValidationError, match="xai_key") as caught:
            with_keys(settings, xai_key=bad)
        assert bad not in str(caught.value)


@pytest.mark.parametrize("variable", SDK_HEADER_VARIABLES)
def test_sdk_header_variables_are_refused(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "org-someone-else")
    with pytest.raises(NotReady, match=f"{variable} set"):
        build_clients(with_keys(settings, **ALL_KEYS), CONFIG)


def test_no_client_follows_a_redirect() -> None:
    sdks: list[Any] = [
        OpenAIChat("openai", "m", OPENAI_KEY, temperature=0, timeout=15).client,
        OpenAIChat("xai", "m", XAI_KEY, temperature=0, timeout=15).client,
        AnthropicMessages("m", ANTHROPIC_KEY, temperature=0, timeout=15).client,
    ]
    assert [sdk._client.follow_redirects for sdk in sdks] == [False, False, False]


async def test_the_picker_from_settings_hides_its_keys(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    picker = AiPicker.from_settings(with_keys(settings, **ALL_KEYS), CONFIG)
    assert not any(key in repr(picker) for key in ALL_KEYS.values())

    def route(request: httpx.Request) -> httpx.Response:
        echoed = f"Incorrect API key provided: {request.headers['authorization']}"
        return httpx.Response(401, json={"error": {"message": echoed, "type": "auth"}})

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        openai_client = OpenAIChat(
            "openai", "gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http
        )
        mocked = replace(picker, clients=picker.clients | {"openai": openai_client})
        result = await mocked.pick(BOOK, PostText("Nvidia"), WHEN, RULES_PICK, None)
    (failed_answer,) = [a for a in result.answers if a.provider == "openai"]
    assert failed_answer.fatal and "[key]" in (failed_answer.error or "")
    shown = repr(result) + caplog.text
    assert not any(key in shown for key in ALL_KEYS.values())


@pytest.mark.parametrize("name", list(json.loads(MANIFEST.read_text("utf-8"))["files"]))
def test_a_changed_picker_file_is_refused(tmp_path: Path, name: str) -> None:
    pinned = json.loads(MANIFEST.read_text("utf-8"))
    pinned["files"][name] = "0" * 64
    changed = tmp_path / MANIFEST.name
    changed.write_text(json.dumps(pinned), "utf-8")
    with pytest.raises(RulesFileChanged, match=f"{name} changed"):
        load_ai_config(changed)


def test_clients_get_the_engine_keys_passed_in(settings: Settings) -> None:
    keyed = settings.model_copy(
        update={
            "openai_key": OPENAI_KEY,
            "xai_key": XAI_KEY,
            "anthropic_key": ANTHROPIC_KEY,
        }
    )
    keyed = Settings.model_validate(keyed.model_dump())
    clients = build_clients(keyed, CONFIG)
    assert set(clients) == {"openai", "xai", "anthropic"}
    assert [getattr(c, "client").api_key for c in clients.values()] == [  # noqa: B009
        OPENAI_KEY,
        XAI_KEY,
        ANTHROPIC_KEY,
    ]
    assert OPENAI_KEY not in repr(keyed)
    unpinned = replace(
        CONFIG, models={**CONFIG.models, "xai": replace(CONFIG.models["xai"], model=None)}
    )
    assert "xai" not in build_clients(keyed, unpinned)


# --- mapping --------------------------------------------------------------------------------


async def mapped(item: Item, at: datetime = WHEN) -> Mention:
    return await map_item(BOOK, item, at, None)


async def test_mapping_by_alias_and_by_ticker() -> None:
    by_name = await mapped(Item("Nvidia Corporation", None, "stock", "explicit", ""))
    by_ticker = await mapped(Item("Some Chip Firm", "NVDA", "stock", "implied", ""))
    assert symbols([by_name, by_ticker]) == {"NVDA"}
    assert (by_name.found_by, by_ticker.found_by) == ("ai_explicit", "ai_implied")


async def test_a_collision_ticker_needs_its_name() -> None:
    wrong = await mapped(Item("Delta Air Lines", "DE", "stock", "explicit", ""))
    assert (wrong.counted, wrong.unmapped) == (False, "collision_without_name")
    right = await mapped(Item("Deere & Company", "DE", "stock", "explicit", ""))
    assert symbols([right]) == {"DE"}


async def test_unmapped_names_keep_their_reason() -> None:
    cases = {
        Item("SpaceX", None, "stock", "explicit", ""): "no_ticker",
        Item("SPDR S&P 500", "SPY", "etf", "implied", ""): "index_fund",
        Item("Dogecoin", "DOGE", "coin", "explicit", ""): "coin_not_counted",
        Item("Nucor", "NUE", "stock", "implied", ""): "not_an_instrument",
    }
    for item, reason in cases.items():
        mention = await mapped(item)
        assert (mention.instrument_id, mention.unmapped, mention.name) == (None, reason, item.name)


async def test_a_new_ticker_is_added_only_when_it_counts(db: AsyncEngine) -> None:
    await sync_names(db)
    listings = CountsAll(not_listed=["XYZQ"])
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        adder = new_ticker_adder(conn, listings)
        nucor = await map_item(book, Item("Nucor", "NUE", "stock", "implied", ""), WHEN, adder)
        fake = await map_item(book, Item("Fake Co", "XYZQ", "stock", "explicit", ""), WHEN, adder)
        again = await load_book(conn, current_rules())
    assert nucor.counted and book.instruments[nucor.instrument_id or 0].symbol == "NUE"
    assert (fake.instrument_id, fake.unmapped) == (None, "does_not_count")
    assert "NUE" in {i.symbol for i in again.instruments.values()}
    assert "XYZQ" not in {i.symbol for i in again.instruments.values()}


async def test_a_new_ticker_must_count_on_the_posts_day(db: AsyncEngine) -> None:
    await sync_names(db)
    early = datetime(2024, 6, 3, 15, tzinfo=UTC)
    listings = CountsAll(listed_from={"NUE": datetime(2025, 1, 2, tzinfo=UTC)})
    nucor = Item("Nucor", "NUE", "stock", "implied", "")
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        adder = new_ticker_adder(conn, listings)
        before = await map_item(book, nucor, early, adder)
        after = await map_item(book, nucor, WHEN, adder)
        # NUE is an instrument now, but no rules version reviewed it: still checked by day
        again = await map_item(book, nucor, early, adder)
    assert (before.unmapped, after.counted, again.unmapped) == (
        "does_not_count",
        True,
        "does_not_count",
    )
    assert {at for _, at in listings.asked} == {early, WHEN}
    assert listings.asked[-1] == ("NUE", early)


async def test_a_reviewed_ticker_outside_its_dates_is_not_listed_then(db: AsyncEngine) -> None:
    await sync_names(db)
    listings = CountsAll()
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        adder = new_ticker_adder(conn, listings)
        on_day = datetime(2025, 9, 2, 15, tzinfo=UTC)
        early = datetime(2024, 5, 1, 15, tzinfo=UTC)
        item = Item("Paramount Skydance", "PSKY", "stock", "explicit", "")
        later = await map_item(book, item, on_day, adder)
        before = await map_item(book, item, early, adder)
    assert later.counted
    assert (before.instrument_id, before.unmapped) == (None, "not_listed_then")
    assert listings.asked == []
    assert book.ticker("PSKY", early.date()) is None


async def test_a_collision_ticker_needs_its_name_before_alpaca_is_asked(db: AsyncEngine) -> None:
    await sync_names(db)
    listings = CountsAll()
    collision = next(t for t in sorted(BOOK.rules.collisions.symbols) if not BOOK.knows_ticker(t))
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        item = Item("Some Company", collision, "stock", "implied", "")
        mention = await map_item(book, item, WHEN, new_ticker_adder(conn, listings))
    assert mention.unmapped == "collision_without_name" and listings.asked == []


class AlpacaDown(CountsAll):
    async def counts(self, symbol: str, asset_class: AssetClass, at: datetime) -> bool:
        raise AlpacaError("/v2/stocks/bars: still failing after 5 tries: HTTP 503")


async def test_when_alpaca_cant_say_the_name_stays_unmapped(db: AsyncEngine) -> None:
    await sync_names(db)
    async with db.begin() as conn:
        book = await load_book(conn, current_rules())
        item = Item("Nucor", "NUE", "stock", "implied", "")
        mention = await map_item(book, item, WHEN, new_ticker_adder(conn, AlpacaDown()))
    assert (mention.instrument_id, mention.unmapped) == (None, "count_check_failed")


async def test_an_ai_added_ticker_counts_in_the_rules_only_as_a_cashtag() -> None:
    book = file_book()
    raid = "ICE agents arrested 300 illegal alien criminals in Chicago. Great job by ICE!"
    before = pick(book, raid, WHEN)

    async def counts(ticker: str, asset: AssetClass, at: datetime) -> Listed:
        return Listed(999, ticker, ticker, "stock")

    item = Item("Intercontinental Exchange", "ICE", "stock", "implied", "owns the NYSE")
    assert (await map_item(book, item, WHEN, counts)).counted
    assert pick(book, raid, WHEN) == before
    assert pick(book, "Look at $ICE today", WHEN).symbols == ("ICE",)


# --- the vote ---------------------------------------------------------------------------------

RULES_PICK = pick(BOOK, "Tariffs on Ford", WHEN)


def ok(provider: str, market_link: bool) -> ModelAnswer:
    return ModelAnswer(provider, "m", WHEN, WHEN, None, market_link)  # type: ignore[arg-type]


def failed(provider: str, error: str = "timeout after 15 s") -> ModelAnswer:
    return ModelAnswer(provider, "m", WHEN, WHEN, error=error)  # type: ignore[arg-type]


async def names(*items: tuple[str, str]) -> tuple[Mention, ...]:
    return tuple([await mapped(Item(n, t, "stock", "explicit", "")) for n, t in items])


async def test_all_three_agree() -> None:
    each = await names(("Nvidia", "NVDA"))
    result = vote([ok(p, True) for p in ("openai", "xai", "anthropic")], dict.fromkeys(
        ("openai", "xai", "anthropic"), each), RULES_PICK)  # fmt: skip
    assert result.market_link and not result.fallback
    assert symbols(result.mentions) == {"NVDA"}
    assert [m.models for m in result.mentions] == [3]


async def test_two_of_three_count_and_one_does_not() -> None:
    answers = [ok("openai", True), ok("xai", True), ok("anthropic", False)]
    mapped_names = {
        "openai": await names(("Nvidia", "NVDA"), ("Apple", "AAPL")),
        "xai": await names(("NVIDIA Corp", "NVDA")),
        "anthropic": await names(("Apple Inc.", "AAPL"), ("Tesla", "TSLA")),
    }
    result = vote(answers, mapped_names, RULES_PICK)
    assert result.market_link
    assert symbols(result.mentions) == {"NVDA", "AAPL"}
    tesla = next(m for m in result.mentions if m.models == 1)
    assert not tesla.counted


async def test_a_model_naming_it_without_a_ticker_does_not_lose_the_counted_name() -> None:
    answers = [ok(p, True) for p in ("openai", "xai", "anthropic")]
    with_ticker = await names(("Some Chip Firm", "NVDA"))
    no_ticker = (await mapped(Item("Some Chip Firm", None, "stock", "implied", "")),)
    assert no_ticker[0].unmapped == "no_ticker"
    for order in (("openai", "xai", "anthropic"), ("anthropic", "openai", "xai")):
        mapped_names = dict.fromkeys(order[:2], with_ticker) | {order[2]: no_ticker}
        result = vote(answers, {p: mapped_names[p] for p in order}, RULES_PICK)
        assert [(m.normalized, m.counted, m.models) for m in result.mentions] == [
            ("some chip firm", True, 2)
        ]
        assert symbols(result.mentions) == {"NVDA"}


async def test_one_name_given_two_tickers_keeps_the_counted_one() -> None:
    answers = [ok(p, True) for p in ("openai", "xai", "anthropic")]
    lone = await names(("Some Chip Firm", "NVDA"))
    agreed = await names(("Some Chip Firm", "AAPL"))
    mapped_names = {"openai": lone, "xai": agreed, "anthropic": agreed}
    result = vote(answers, mapped_names, RULES_PICK)
    assert [(m.normalized, m.counted, m.models) for m in result.mentions] == [
        ("some chip firm", True, 2)
    ]
    assert symbols(result.mentions) == {"AAPL"}


async def test_with_one_failed_the_other_two_must_agree() -> None:
    answers = [ok("openai", True), ok("xai", False), failed("anthropic")]
    mapped_names = {"openai": await names(("Nvidia", "NVDA")), "xai": ()}
    result = vote(answers, mapped_names, RULES_PICK)
    assert not result.market_link and not result.fallback and result.answered == 2
    assert symbols(result.mentions) == set()


async def test_with_two_failed_the_rules_stand_in() -> None:
    answers = [ok("openai", True), failed("xai", "invalid answer"), failed("anthropic")]
    result = vote(answers, {"openai": await names(("Nvidia", "NVDA"))}, RULES_PICK)
    assert result.fallback and result.answered == 1
    assert result.market_link == RULES_PICK.market_link
    assert symbols(result.mentions) == {"F"}


async def test_a_timeout_counts_as_missed() -> None:
    from dataclasses import replace

    quick = replace(CONFIG, timeout_seconds=0.05)
    slow = StubClient("anthropic", default=answer(True), delay=1.0)
    result = await ask_model(slow, quick, "Post:\nx", retries=3)
    assert result.error == "timeout after 0.05 s"
    assert len(slow.asked) == 1  # never retried


async def test_rate_limits_are_retried_in_batch() -> None:
    import openai

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    limited = openai.RateLimitError(
        "slow down", response=httpx.Response(429, request=request), body=None
    )
    client = StubClient("openai", fail=limited)
    result = await ask_model(client, CONFIG, "Post:\nx", retries=2, backoff_seconds=0)
    assert len(client.asked) == 3 and result.error and "RateLimitError" in result.error


def api_error(kind: type[Exception], status: int) -> Exception:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return kind("refused", response=httpx.Response(status, request=request), body=None)  # type: ignore[call-arg]


async def test_errors_no_retry_can_fix_are_fatal_and_not_retried() -> None:
    import anthropic
    import openai

    cases = [
        (api_error(openai.AuthenticationError, 401), True),
        (api_error(openai.PermissionDeniedError, 403), True),
        (api_error(openai.NotFoundError, 404), True),
        (api_error(openai.BadRequestError, 400), True),
        (api_error(openai.RateLimitError, 429), False),
        (api_error(openai.InternalServerError, 500), False),
    ]
    request2 = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    revoked = anthropic.PermissionDeniedError(
        "revoked", response=httpx2.Response(403, request=request2), body=None
    )
    cases.append((revoked, True))
    for error, fatal in cases:
        client = StubClient("openai", fail=error)
        result = await ask_model(client, CONFIG, "Post:\nx", retries=2, backoff_seconds=0)
        assert result.fatal is fatal, error
        assert len(client.asked) == (1 if fatal else 3), error


async def test_an_sdk_timeout_is_not_retried() -> None:
    import openai

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client = StubClient("openai", fail=openai.APITimeoutError(request=request))
    result = await ask_model(client, CONFIG, "Post:\nx", retries=3, backoff_seconds=0)
    assert len(client.asked) == 1 and not result.fatal
    assert result.error and "APITimeoutError" in result.error


async def openai_reply(changes: dict[str, Any]) -> ModelAnswer:
    body = ai_fixture("openai_chat_completion.unverified.json")
    body["choices"][0] |= changes.get("choice", {})
    body["choices"][0]["message"] |= changes.get("message", {})

    def route(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        client = OpenAIChat(
            "openai", "gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http
        )
        return await ask_model(client, CONFIG, "Post:\nNvidia")


async def test_a_billed_reply_that_cant_be_used_keeps_its_body_tokens_and_cost() -> None:
    cut_off = await openai_reply({"choice": {"finish_reason": "length"}})
    garbled = await openai_reply({"message": {"content": '{"market_link": tr'}})
    refused = await openai_reply({"message": {"content": None, "refusal": "I can't"}})
    assert cut_off.error == "invalid answer: stopped early: length"
    assert (garbled.error or "").startswith("invalid answer: not JSON")
    assert refused.error == 'invalid answer: no content (refusal: "I can\'t")'
    for billed in (cut_off, garbled, refused):
        assert billed.cost == Decimal("0.001240") and billed.reply is not None
        assert billed.reply.output_tokens == 52 and billed.reply.body["choices"]
    picked = AiPick((cut_off,), {}, vote([cut_off], {}, RULES_PICK), WHEN, WHEN)
    (row, _) = picked.extractions(BOOK, CONFIG)
    assert (row.cost_usd, row.output_tokens, row.error) == (cut_off.cost, 52, cut_off.error)
    assert row.response is not None


async def test_an_anthropic_reply_cut_off_keeps_its_cost() -> None:
    body = ai_fixture("anthropic_message.unverified.json") | {"stop_reason": "max_tokens"}

    def route(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=body)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(route)) as http:
        client = AnthropicMessages(
            "claude-test", ANTHROPIC_KEY, temperature=0, timeout=15, http_client=http
        )
        result = await ask_model(client, CONFIG, "Post:\nNvidia")
    assert result.error == "invalid answer: stopped early: max_tokens"
    assert result.cost and result.cost > 0 and result.reply is not None


async def test_the_picker_asks_all_three_and_votes() -> None:
    words = "Nvidia will invest 500 billion dollars in America"
    said = answer(True, ("Nvidia", "NVDA", "stock", "explicit"))
    clients = {p: StubClient(p, answers={words: said}) for p in ("openai", "xai", "anthropic")}
    picker = AiPicker(CONFIG, clients)  # type: ignore[arg-type]
    result = await picker.pick(BOOK, PostText(words), WHEN, pick(BOOK, words, WHEN), None)
    assert len(result.answers) == 3 and result.vote.market_link
    assert symbols(result.vote.mentions) == {"NVDA"}
    methods = [e.method for e in result.extractions(BOOK, CONFIG)]
    assert methods == ["ai:openai", "ai:xai", "ai:anthropic", "ai:vote"]


async def test_a_post_of_only_links_asks_no_model() -> None:
    client = StubClient("openai")
    picker = AiPicker(CONFIG, {"openai": client})
    result = await picker.pick(BOOK, PostText(""), WHEN, pick(BOOK, "", WHEN), None)
    assert client.asked == [] and result.skipped == "no_words"
    assert not result.vote.market_link


async def test_the_quoted_post_goes_in_the_message() -> None:
    assert PostText("Wow!", "Tariffs on China").user_message() == (
        "Post:\nWow!\n\nQuoted post:\nTariffs on China"
    )
