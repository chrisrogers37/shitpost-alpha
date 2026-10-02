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
from engine.market.instruments import NEW_YORK, AssetClass
from engine.settings import Settings
from tests.extract_helpers import FIXTURES, CountsAll, StubClient, answer, ready_config, sync_names
from tests.test_rules import file_book

BOOK = file_book()
WHEN = datetime(2026, 3, 2, 15, tzinfo=UTC)
CONFIG = ready_config()
OPENAI_KEY = "sk-test-openai-DO-NOT-LOG-1234567890"
ANTHROPIC_KEY = "sk-ant-test-DO-NOT-LOG-1122334455"


def ai_fixture(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / "ai" / name).read_text("utf-8"))
    return loaded


def symbols(mentions: tuple[Mention, ...] | list[Mention]) -> set[str]:
    return {
        BOOK.instruments[m.instrument_id].symbol for m in mentions if m.counted and m.instrument_id
    }


# --- the version and the answer -----------------------------------------------------


def test_version_1_is_two_dated_models_with_checked_prices_and_its_window() -> None:
    config = current_ai_config()
    assert config.version == 1
    assert len(config.hash) == 64
    assert "market_link" in config.instructions
    assert set(config.schema["required"]) == {"market_link", "instruments"}
    assert not config.problems()
    assert {p: s.model for p, s in config.models.items()} == {
        "openai": "gpt-4.1-2025-04-14",
        "anthropic": "claude-haiku-4-5-20251001",
    }
    for spec in config.models.values():
        assert re.search(r"\d{4}", spec.model or "")  # a dated snapshot, not an alias
    assert config.window_start == datetime(2025, 11, 1, tzinfo=NEW_YORK)
    unpinned = replace(
        config,
        models={**config.models, "anthropic": replace(config.models["anthropic"], model=None)},
    )
    assert unpinned.problems() == ["anthropic: no model pinned"]


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
        client = OpenAIChat("gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http)
        result = await ask_model(client, CONFIG, PostText("Nvidia will spend").user_message())
    assert result.ok and result.market_link
    assert [i.ticker for i in result.items] == ["NVDA"]
    assert (result.reply and result.reply.cached_input_tokens) == 1024
    assert result.cost == Decimal("0.001240")  # 156 fresh x 2 + 1024 x 0.5 + 52 x 8, per million
    body = json.loads(sent[0].content)
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["strict"] is True
    assert sent[0].url.host == "api.openai.com"


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
        client = OpenAIChat("gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http)
        result = await ask_model(client, CONFIG, "Post:\nx", secrets=[OPENAI_KEY])
    assert result.error and "[key]" in result.error
    assert OPENAI_KEY not in result.error
    assert OPENAI_KEY not in caplog.text


def with_keys(settings: Settings, **keys: str) -> Settings:
    """Settings with ENGINE_ AI keys, put through the same checks as the environment's."""
    return Settings.model_validate(settings.model_dump() | keys)


ALL_KEYS = {"openai_key": OPENAI_KEY, "anthropic_key": ANTHROPIC_KEY}


def test_no_picker_without_both_keys_or_a_ready_version(settings: Settings) -> None:
    assert build_clients(settings, CONFIG) == {}
    with pytest.raises(NotReady, match=r"not set: ENGINE_OPENAI_KEY, ENGINE_ANTHROPIC_KEY$"):
        AiPicker.from_settings(settings, CONFIG)
    with pytest.raises(NotReady, match=r"not set: ENGINE_ANTHROPIC_KEY$"):
        AiPicker.from_settings(with_keys(settings, openai_key=OPENAI_KEY), CONFIG)
    unpinned = replace(
        CONFIG,
        models={**CONFIG.models, "anthropic": replace(CONFIG.models["anthropic"], model=None)},
    )
    with pytest.raises(NotReady, match=r"isn.t ready: anthropic: no model pinned$"):
        AiPicker.from_settings(with_keys(settings, **ALL_KEYS), unpinned)


def test_ai_keys_must_be_safe_in_a_header(settings: Settings) -> None:
    assert with_keys(settings, anthropic_key=f"  {ANTHROPIC_KEY}\n").ai_keys == {
        "anthropic": ANTHROPIC_KEY
    }
    for bad in ("sk-ant-a b", "sk-ant-a\nb", "sk-ant-\u00e9"):
        with pytest.raises(ValidationError, match="anthropic_key") as caught:
            with_keys(settings, anthropic_key=bad)
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
        OpenAIChat("m", OPENAI_KEY, temperature=0, timeout=15).client,
        AnthropicMessages("m", ANTHROPIC_KEY, temperature=0, timeout=15).client,
    ]
    assert [sdk._client.follow_redirects for sdk in sdks] == [False, False]


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
            "gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http
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
    keyed = settings.model_copy(update={"openai_key": OPENAI_KEY, "anthropic_key": ANTHROPIC_KEY})
    keyed = Settings.model_validate(keyed.model_dump())
    clients = build_clients(keyed, CONFIG)
    assert [type(c) for c in clients.values()] == [OpenAIChat, AnthropicMessages]
    assert [getattr(c, "client").api_key for c in clients.values()] == [  # noqa: B009
        OPENAI_KEY,
        ANTHROPIC_KEY,
    ]
    assert OPENAI_KEY not in repr(keyed)
    unpinned = replace(
        CONFIG,
        models={**CONFIG.models, "anthropic": replace(CONFIG.models["anthropic"], model=None)},
    )
    assert set(build_clients(keyed, unpinned)) == {"openai"}


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


async def test_both_agree() -> None:
    result = vote(
        [ok("openai", True), ok("anthropic", True)],
        {"openai": await names(("Nvidia", "NVDA")), "anthropic": await names(("NVIDIA", "NVDA"))},
        RULES_PICK,
    )
    assert result.market_link and not result.fallback and result.answered == 2
    assert symbols(result.mentions) == {"NVDA"}
    assert [m.models for m in result.mentions] == [2]


async def test_a_link_or_a_name_counts_only_when_both_make_it() -> None:
    answers = [ok("openai", True), ok("anthropic", False)]
    mapped_names = {
        "openai": await names(("Nvidia", "NVDA"), ("Apple", "AAPL")),
        "anthropic": await names(("Apple Inc.", "AAPL"), ("Tesla", "TSLA")),
    }
    result = vote(answers, mapped_names, RULES_PICK)
    assert not result.market_link and not result.fallback
    assert symbols(result.mentions) == {"AAPL"}
    alone = {m.name for m in result.mentions if m.models == 1}
    assert alone == {"Nvidia", "Tesla"}
    assert not any(m.counted for m in result.mentions if m.models == 1)


async def test_a_name_also_given_without_a_ticker_does_not_lose_the_counted_name() -> None:
    answers = [ok(p, True) for p in ("openai", "anthropic")]
    with_ticker = await names(("Some Chip Firm", "NVDA"))
    no_ticker = (await mapped(Item("Some Chip Firm", None, "stock", "implied", "")),)
    assert no_ticker[0].unmapped == "no_ticker"
    for first, second in ((with_ticker, no_ticker), (no_ticker, with_ticker)):
        mapped_names = {"openai": first + second, "anthropic": second + first}
        result = vote(answers, mapped_names, RULES_PICK)
        assert [(m.normalized, m.counted, m.models) for m in result.mentions] == [
            ("some chip firm", True, 2)
        ]
        assert symbols(result.mentions) == {"NVDA"}
    alone = vote(answers, {"openai": with_ticker, "anthropic": no_ticker}, RULES_PICK)
    assert [(m.counted, m.models, m.unmapped) for m in alone.mentions] == [(False, 1, None)]


async def test_one_name_given_two_tickers_keeps_the_counted_one() -> None:
    answers = [ok(p, True) for p in ("openai", "anthropic")]
    lone = await names(("Some Chip Firm", "NVDA"))
    agreed = await names(("Some Chip Firm", "AAPL"))
    result = vote(answers, {"openai": lone + agreed, "anthropic": agreed}, RULES_PICK)
    assert [(m.normalized, m.counted, m.models) for m in result.mentions] == [
        ("some chip firm", True, 2)
    ]
    assert symbols(result.mentions) == {"AAPL"}


@pytest.mark.parametrize(
    "error", ["timeout after 15 s", "invalid answer: not JSON", "APIConnectionError: reset"]
)
async def test_if_either_model_fails_the_rules_stand_in(error: str) -> None:
    for answers in ([ok("openai", True), failed("anthropic", error)],
                    [failed("openai", error), ok("anthropic", True)]):  # fmt: skip
        said: dict[str, tuple[Mention, ...]] = {
            a.provider: await names(("Nvidia", "NVDA")) for a in answers if a.ok
        }
        result = vote(answers, said, RULES_PICK)
        assert result.fallback and result.answered == 1
        assert result.market_link == RULES_PICK.market_link
        assert symbols(result.mentions) == {"F"}
    both = vote([failed("openai", error), failed("anthropic", error)], {}, RULES_PICK)
    assert both.fallback and both.answered == 0 and symbols(both.mentions) == {"F"}


async def test_a_timeout_counts_as_missed() -> None:
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
        client = OpenAIChat("gpt-test", OPENAI_KEY, temperature=0, timeout=15, http_client=http)
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


async def test_the_picker_asks_both_and_votes() -> None:
    words = "Nvidia will invest 500 billion dollars in America"
    said = answer(True, ("Nvidia", "NVDA", "stock", "explicit"))
    clients = {p: StubClient(p, answers={words: said}) for p in ("openai", "anthropic")}
    picker = AiPicker(CONFIG, clients)  # type: ignore[arg-type]
    result = await picker.pick(BOOK, PostText(words), WHEN, pick(BOOK, words, WHEN), None)
    assert len(result.answers) == 2 and result.vote.market_link
    assert symbols(result.vote.mentions) == {"NVDA"}
    rows = result.extractions(BOOK, CONFIG)
    assert [e.method for e in rows] == ["ai:openai", "ai:anthropic", "ai:vote"]
    assert rows[-1].result and rows[-1].result["ai_fallback"] is False


async def test_a_model_past_the_deadline_sends_the_post_to_the_rules() -> None:
    words = "Nvidia will invest 500 billion dollars in America"
    said = answer(True, ("Nvidia", "NVDA", "stock", "explicit"))
    clients = {
        "openai": StubClient("openai", answers={words: said}),
        "anthropic": StubClient("anthropic", answers={words: said}, delay=1.0),
    }
    picker = AiPicker(replace(CONFIG, timeout_seconds=0.05), clients)  # type: ignore[arg-type]
    rules = pick(BOOK, words, WHEN)
    result = await picker.pick(BOOK, PostText(words), WHEN, rules, None)
    assert result.vote.fallback and result.vote.mentions == rules.mentions
    vote_row = result.extractions(BOOK, CONFIG)[-1]
    assert vote_row.result and vote_row.result["ai_fallback"] is True


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
