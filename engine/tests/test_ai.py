"""The AI picker: parsing each provider's answer, mapping names, the vote, keys."""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from engine.extract.ai import (
    AiPicker,
    AnthropicMessages,
    Item,
    ModelAnswer,
    OpenAIChat,
    PostText,
    Price,
    ask_model,
    build_clients,
    current_ai_config,
    map_item,
    parse_answer,
    vote,
)
from engine.extract.names import load_book
from engine.extract.rules import Mention, current_rules, pick
from engine.extract.score import new_ticker_adder
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


def test_the_picker_version_loads_and_says_what_b2_must_fill() -> None:
    config = current_ai_config()
    assert config.version == 1
    assert len(config.hash) == 64
    assert "market_link" in config.instructions
    assert set(config.schema["required"]) == {"market_link", "instruments"}
    assert not CONFIG.problems()


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


async def test_openai_answer_through_the_sdk() -> None:
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


async def test_anthropic_answer_through_the_sdk() -> None:
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


def test_no_engine_keys_means_no_client_and_no_picker(settings: Settings) -> None:
    assert build_clients(settings, CONFIG) == {}
    assert AiPicker.from_settings(settings, CONFIG) is None


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
    unpinned = build_clients(keyed, current_ai_config())  # xAI's model isn't chosen yet
    assert "xai" not in unpinned


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
