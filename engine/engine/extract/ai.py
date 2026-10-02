"""The AI picker: two models, OpenAI's and Anthropic's, say whether a post has a market
link and which instruments it names or implies; a link or an instrument counts only when
both make it.

Its version is ai.json: the prompt, the schema, the model ids, the settings and the window
start, pinned by hash like the rules, and frozen once its answers count. What can change
without changing an answer sits outside it: the models' prices (ai_models.json) and the
reason line, which has its own version (reason.json). Every client is built with its key
passed from the ENGINE_ settings, never from the old system's variables, and none is
built without its key.

Each call has a deadline (15 s). A model that errs, answers invalid JSON or misses the
deadline counts as failed, and then the post takes the rules' answer and is marked
ai_fallback. Batch runs retry rate limits and server errors with back-off; a deadline is
never retried, since live it would be missed. An error no retry can fix (a bad key, a
model id the provider doesn't know) is marked fatal, and `ai-pick` stops on it.
"""

import asyncio
import hashlib
import json
import logging
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, Literal, Protocol

import anthropic
import httpx
import openai

from engine.extract.records import Extraction
from engine.extract.rules import (
    PACKAGE_DIR,
    STRAIGHT_APOSTROPHES,
    Listed,
    Mention,
    NameBook,
    RulesFileChanged,
    RulesPick,
    post_date,
    unique_names,
)
from engine.market.instruments import (
    COINS,
    NEW_YORK,
    STOCK_SYMBOL,
    AssetClass,
    normalize_alias,
)
from engine.settings import Settings

log = logging.getLogger(__name__)

MANIFEST = Path(__file__).with_name("ai.json")
MODEL_FACTS = Path(__file__).with_name("ai_models.json")
REASON_MANIFEST = Path(__file__).with_name("reason.json")
Provider = Literal["openai", "anthropic"]
PROVIDERS: tuple[Provider, ...] = ("openai", "anthropic")
BASE_URLS: dict[Provider, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}
"""Passed to every SDK client, so an OPENAI_BASE_URL or ANTHROPIC_BASE_URL left in the
environment can never send an engine key elsewhere."""
INDEX_FUNDS = frozenset({"SPY", "QQQ", "DIA", "IWM", "VOO", "IVV", "VTI", "RSP"})
"""Broad index funds: never a named instrument (SPY and QQQ come from the market link)."""
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})
PER_MILLION = Decimal(1_000_000)
SDK_HEADER_VARIABLES = (
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "OPENAI_CUSTOM_HEADERS",
    "ANTHROPIC_CUSTOM_HEADERS",
)
"""Read by the SDKs from the environment and added to every request: the engine refuses
to build a client while any is set."""


class NotReady(RuntimeError):
    """The AI picker version isn't complete enough for real calls."""


class InvalidAnswer(ValueError):
    """A model's answer isn't the JSON the schema asks for."""


class FatalAnswer(RuntimeError):
    """A model failed in a way no retry can fix (a bad key, an unknown model id)."""


class CountCheckFailed(RuntimeError):
    """Alpaca couldn't say whether a new ticker counts (keys missing, an error after
    retries): the name is kept unmapped and the paid answers are still recorded."""


# --- the version ---------------------------------------------------------------------


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens, and the day the provider's pricing page said so."""

    input: Decimal
    cached_input: Decimal
    output: Decimal
    checked: date | None

    def cost(self, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> Decimal:
        """`input_tokens` includes the cached ones."""
        fresh = max(input_tokens - cached_input_tokens, 0)
        total = (
            fresh * self.input
            + cached_input_tokens * self.cached_input
            + output_tokens * self.output
        )
        return (total / PER_MILLION).quantize(Decimal("0.000001"))


@dataclass(frozen=True)
class ModelSpec:
    model: str | None
    """A dated snapshot, never an alias. None while unpinned."""
    price: Price | None
    """From ai_models.json, outside the version: None until checked."""
    temperature: float | None
    """0, or None where the provider takes no temperature."""


@dataclass(frozen=True)
class ReasonSpec:
    version: int
    instructions: str
    provider: Provider
    max_output_tokens: int
    max_chars: int


@dataclass(frozen=True)
class AiConfig:
    version: int
    hash: str
    """SHA-256 over the version's file hashes: what "AI picker version N" pins."""
    instructions: str
    schema: dict[str, Any]
    models: dict[str, ModelSpec]
    max_output_tokens: int
    timeout_seconds: float
    max_instruments: int
    why_max_chars: int
    window_start: datetime | None
    """New York midnight on the window's first day."""
    reason: ReasonSpec
    """The reason line's own version (reason.json), outside this version's hash."""

    def problems(self) -> list[str]:
        """What stops real calls: unpinned models, prices not checked, no window start."""
        found = []
        for name in PROVIDERS:
            spec = self.models[name]
            if spec.model is None:
                found.append(f"{name}: no model pinned")
            if spec.price is None or spec.price.checked is None:
                found.append(f"{name}: price not checked")
        if self.window_start is None:
            found.append("no window start")
        return found


def _price(data: Mapping[str, Any] | None) -> Price | None:
    if data is None:
        return None
    checked = data.get("checked")
    return Price(
        input=Decimal(str(data["input"])),
        cached_input=Decimal(str(data["cached_input"])),
        output=Decimal(str(data["output"])),
        checked=date.fromisoformat(checked) if checked else None,
    )


def _pinned(manifest: Path) -> tuple[dict[str, Any], dict[str, str], str]:
    """`manifest`, its files' texts and its hash (the SHA-256 over its files' hashes),
    after checking every file's hash and, once the version is frozen, its hash."""
    data = json.loads(manifest.read_text("utf-8"))
    hashes: dict[str, str] = {}
    texts: dict[str, str] = {}
    for name, digest in data["files"].items():
        raw = (PACKAGE_DIR / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RulesFileChanged(
                f"{name} changed: put its new SHA-256 in {manifest.name} and raise the version"
            )
        hashes[name], texts[name] = digest, raw.decode("utf-8")
    pinned = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    if data.get("frozen", pinned) != pinned:
        raise RulesFileChanged(
            f"version {data['version']} in {manifest.name} is frozen and its files changed: "
            "a frozen version never changes, so raise the version"
        )
    return data, texts, pinned


def load_reason(manifest: Path = REASON_MANIFEST) -> ReasonSpec:
    """The reason line's version in `manifest`, after checking its files' hashes."""
    data, texts, _ = _pinned(manifest)
    return ReasonSpec(
        version=int(data["version"]),
        instructions=texts[data["prompt"]].strip(),
        provider=data["provider"],
        max_output_tokens=int(data["max_output_tokens"]),
        max_chars=int(data["max_chars"]),
    )


def load_ai_config(
    manifest: Path = MANIFEST,
    model_facts: Path = MODEL_FACTS,
    reason_manifest: Path = REASON_MANIFEST,
) -> AiConfig:
    """The AI picker version in `manifest`, after checking its files' hashes, with its
    models' prices from `model_facts` and the reason line from `reason_manifest`."""
    data, texts, pinned = _pinned(manifest)
    config = json.loads(texts[data["config"]])
    facts = json.loads(model_facts.read_text("utf-8"))
    settings = config["settings"]
    window = config.get("window_start")
    models: dict[str, ModelSpec] = {}
    for name in PROVIDERS:
        spec = config["models"][name]
        prices = facts.get(spec["model"], {}).get("prices") if spec["model"] else None
        models[name] = ModelSpec(spec["model"], _price(prices), spec["temperature"])
    return AiConfig(
        version=int(data["version"]),
        hash=pinned,
        instructions=texts[data["prompt"]].strip(),
        schema=config["schema"],
        models=models,
        max_output_tokens=int(settings["max_output_tokens"]),
        timeout_seconds=float(settings["timeout_seconds"]),
        max_instruments=int(settings["max_instruments"]),
        why_max_chars=int(settings["why_max_chars"]),
        window_start=(
            datetime.combine(date.fromisoformat(window), time(), NEW_YORK) if window else None
        ),
        reason=load_reason(reason_manifest),
    )


@cache
def current_ai_config() -> AiConfig:
    return load_ai_config()


# --- talking to the providers -----------------------------------------------------------


@dataclass(frozen=True)
class Reply:
    """A provider's answer: its response body (never the request or its headers), the
    text the model wrote and the tokens it billed. input_tokens includes cached ones.
    `problem` says why a billed reply can't be used (cut off, no content)."""

    body: dict[str, Any]
    text: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    problem: str | None = None


class Client(Protocol):
    provider: Provider
    model: str

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply: ...


class OpenAIChat:
    """OpenAI's chat completions with a strict JSON schema."""

    provider: Provider = "openai"

    def __init__(
        self,
        model: str,
        key: str,
        *,
        temperature: float | None,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.client = openai.AsyncOpenAI(
            api_key=key,
            base_url=BASE_URLS["openai"],
            timeout=timeout,
            max_retries=0,
            # A redirect is refused rather than followed with the key.
            http_client=http_client or openai.DefaultAsyncHttpxClient(follow_redirects=False),
        )

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user},
            ],
            temperature=openai.omit if self.temperature is None else self.temperature,
            max_completion_tokens=max_tokens,
            response_format=(
                {
                    "type": "json_schema",
                    "json_schema": {"name": "answer", "schema": schema, "strict": True},
                }
                if schema is not None
                else openai.omit
            ),
        )
        choice = response.choices[0] if response.choices else None
        problem = None
        if choice is None or choice.message.content is None:
            problem = f"no content (refusal: {choice.message.refusal if choice else None!r})"
        elif choice.finish_reason != "stop":
            problem = f"stopped early: {choice.finish_reason}"
        usage = response.usage
        cached = 0
        if usage and usage.prompt_tokens_details and usage.prompt_tokens_details.cached_tokens:
            cached = usage.prompt_tokens_details.cached_tokens
        return Reply(
            body=response.model_dump(mode="json"),
            text=(choice.message.content if choice else None) or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            cached_input_tokens=cached,
            output_tokens=usage.completion_tokens if usage else 0,
            problem=problem,
        )


class AnthropicMessages:
    """Anthropic's messages API with structured output."""

    provider: Provider = "anthropic"

    def __init__(
        self,
        model: str,
        key: str,
        *,
        temperature: float | None,
        timeout: float,
        http_client: Any = None,
    ) -> None:
        """http_client: an httpx2.AsyncClient (the SDK's HTTP library), for tests."""
        self.model = model
        self.temperature = temperature
        self.client = anthropic.AsyncAnthropic(
            api_key=key,
            base_url=BASE_URLS["anthropic"],
            timeout=timeout,
            max_retries=0,
            # The SDK's default follows a redirect to any host with x-api-key still set.
            http_client=http_client or anthropic.DefaultAsyncHttpxClient(follow_redirects=False),
        )

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply:
        # This SDK version has no temperature parameter, so it goes in the body (the API
        # takes it for claude-haiku-4-5-20251001, checked 2026-10-02).
        extra = {} if self.temperature is None else {"temperature": self.temperature}
        # No cache_control: a picker call is about 1,500 tokens, under Haiku 4.5's
        # 4,096-token minimum for a cached prefix, so a cache mark would cache nothing.
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            extra_body=extra or None,
            system=instructions,
            messages=[{"role": "user", "content": user}],
            output_config=(
                {"format": {"type": "json_schema", "schema": schema}}
                if schema is not None
                else anthropic.omit
            ),
        )
        usage = response.usage
        cached = usage.cache_read_input_tokens or 0
        written = usage.cache_creation_input_tokens or 0
        return Reply(
            body=response.model_dump(mode="json"),
            text="".join(block.text for block in response.content if block.type == "text"),
            input_tokens=usage.input_tokens + cached + written,
            cached_input_tokens=cached,
            output_tokens=usage.output_tokens,
            problem=None
            if response.stop_reason == "end_turn"
            else f"stopped early: {response.stop_reason}",
        )


def build_clients(settings: Settings, config: AiConfig) -> dict[str, Client]:
    """A client for each provider whose ENGINE_ key is set and whose model is pinned.
    Without keys this is empty and nothing is built."""
    if found := [name for name in SDK_HEADER_VARIABLES if os.environ.get(name) is not None]:
        raise NotReady(f"{', '.join(found)} set: the SDKs would send it to every provider")
    clients: dict[str, Client] = {}
    keys = settings.ai_keys
    for provider in PROVIDERS:
        spec = config.models[provider]
        if (key := keys.get(provider)) is None or spec.model is None:
            continue
        timeout = config.timeout_seconds
        if provider == "anthropic":
            clients[provider] = AnthropicMessages(
                spec.model, key, temperature=spec.temperature, timeout=timeout
            )
        else:
            clients[provider] = OpenAIChat(
                spec.model, key, temperature=spec.temperature, timeout=timeout
            )
    return clients


def scrubbed(text: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[key]")
    return text


FATAL = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.BadRequestError,
    openai.UnprocessableEntityError,
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.BadRequestError,
    anthropic.UnprocessableEntityError,
)
"""Errors no retry can fix: a wrong or revoked key, a model id the provider doesn't
know, a request it refuses. Every post would fail the same way."""


def _fatal(exc: BaseException) -> bool:
    """FATAL, or OpenAI's empty balance: a 429 whose code is `insufficient_quota`, which no
    wait lifts. (Anthropic's low balance is a 400, already FATAL.)"""
    out_of_credit = isinstance(exc, openai.RateLimitError) and "insufficient_quota" in (
        exc.code,
        exc.type,
    )
    return out_of_credit or isinstance(exc, FATAL)


def _retryable(exc: BaseException) -> bool:
    if _fatal(exc) or isinstance(exc, openai.APITimeoutError | anthropic.APITimeoutError):
        return False
    if isinstance(exc, openai.APIStatusError | anthropic.APIStatusError):
        return exc.status_code in RETRY_STATUSES
    return isinstance(exc, openai.APIConnectionError | anthropic.APIConnectionError)


# --- one model's answer ----------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    name: str
    ticker: str | None
    asset: AssetClass
    link: Literal["explicit", "implied"]
    why: str


@dataclass(frozen=True)
class ModelAnswer:
    provider: Provider
    model: str
    started_at: datetime
    finished_at: datetime
    reply: Reply | None = None
    market_link: bool | None = None
    items: tuple[Item, ...] = ()
    error: str | None = None
    cost: Decimal | None = None
    """Whenever a reply was billed, valid or not."""
    fatal: bool = False
    """The error is one no retry can fix (FATAL, or OpenAI out of credit)."""

    @property
    def ok(self) -> bool:
        return self.error is None


ITEM_FIELDS = ("name", "ticker", "asset", "link", "why")


def parse_answer(text: str, max_instruments: int, why_max_chars: int) -> tuple[bool, list[Item]]:
    """The schema's answer, checked field by field. Instruments past the limit are
    dropped and a long `why` is cut; anything else off-schema is an invalid answer."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAnswer(f"not JSON: {exc}") from None
    if not isinstance(data, dict) or set(data) != {"market_link", "instruments"}:
        raise InvalidAnswer("expected exactly market_link and instruments")
    if not isinstance(data["market_link"], bool) or not isinstance(data["instruments"], list):
        raise InvalidAnswer("market_link must be a boolean and instruments a list")
    items = []
    for raw in data["instruments"][:max_instruments]:
        if not isinstance(raw, dict) or set(raw) != set(ITEM_FIELDS):
            raise InvalidAnswer("each instrument has exactly name, ticker, asset, link, why")
        name, ticker, asset, link, why = (raw[k] for k in ITEM_FIELDS)
        if not isinstance(name, str) or not name.strip():
            raise InvalidAnswer("an instrument without a name")
        if ticker is not None and not isinstance(ticker, str):
            raise InvalidAnswer("ticker must be a string or null")
        if asset not in ("stock", "etf", "coin") or link not in ("explicit", "implied"):
            raise InvalidAnswer(f"bad asset or link: {asset!r}, {link!r}")
        if not isinstance(why, str):
            raise InvalidAnswer("why must be a string")
        ticker = (ticker or "").strip().lstrip("$").upper() or None
        items.append(Item(name.strip(), ticker, asset, link, why.strip()[:why_max_chars]))
    return data["market_link"], items


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(UTC)


async def ask_model(
    client: Client,
    config: AiConfig,
    user: str,
    *,
    retries: int = 0,
    secrets: Sequence[str] = (),
    clock: Clock = _now,
    backoff_seconds: float = 2.0,
) -> ModelAnswer:
    """One model's answer to one post. Never raises: a failure is the answer's error. A
    billed reply keeps its body, tokens and cost even when it can't be used."""
    started = clock()
    attempt = 0
    fatal = False
    while True:
        try:
            async with asyncio.timeout(config.timeout_seconds):
                reply = await client.ask(
                    config.instructions, user, config.schema, config.max_output_tokens
                )
        except TimeoutError:
            error = f"timeout after {config.timeout_seconds:g} s"
        except Exception as exc:
            if attempt < retries and _retryable(exc):
                attempt += 1
                await asyncio.sleep(backoff_seconds * 2 ** (attempt - 1))
                continue
            error = scrubbed(f"{type(exc).__name__}: {exc}", secrets)
            fatal = _fatal(exc)
        else:
            return _answered(client, config, reply, started, clock())
        log.warning("%s (%s) failed: %s", client.provider, client.model, error)
        return ModelAnswer(
            client.provider, client.model, started, clock(), error=error, fatal=fatal
        )


def _answered(
    client: Client, config: AiConfig, reply: Reply, started: datetime, finished: datetime
) -> ModelAnswer:
    price = config.models[client.provider].price
    tokens = (reply.input_tokens, reply.cached_input_tokens, reply.output_tokens)
    cost = price.cost(*tokens) if price is not None else None
    try:
        if reply.problem:
            raise InvalidAnswer(reply.problem)
        market_link, items = parse_answer(reply.text, config.max_instruments, config.why_max_chars)
    except InvalidAnswer as exc:
        error = f"invalid answer: {exc}"
        log.warning("%s (%s) failed: %s", client.provider, client.model, error)
        return ModelAnswer(
            client.provider, client.model, started, finished, reply, error=error, cost=cost
        )
    return ModelAnswer(
        client.provider, client.model, started, finished, reply, market_link, tuple(items),
        cost=cost,
    )  # fmt: skip


# --- mapping names to instruments --------------------------------------------------------

NewTicker = Callable[[str, AssetClass, datetime], Awaitable[Listed | None]]
"""Checks with Alpaca that a ticker counts at the post's time (PR 3's rule) and returns its
instrument, adding it if it isn't one yet: (ticker, asset class, post time) -> the
instrument, or None if it doesn't count. Raises CountCheckFailed when Alpaca can't say."""


async def map_item(
    book: NameBook, item: Item, posted_at: datetime, add_new: NewTicker | None
) -> Mention:
    """A model's name, mapped through the same aliases and collision list as the rules."""
    on = post_date(posted_at)
    found_by: Literal["ai_explicit", "ai_implied"] = (
        "ai_explicit" if item.link == "explicit" else "ai_implied"
    )
    normalized = normalize_alias(item.name)

    def mapped(instrument_id: int) -> Mention:
        return Mention(item.name, normalized, found_by, item.ticker, instrument_id, counted=True)

    def unmapped(reason: str) -> Mention:
        return Mention(item.name, normalized, found_by, item.ticker, unmapped=reason)

    named = _instruments_named(book, item.name, on)
    if len(named) == 1:
        return mapped(named.pop())
    ticker = item.ticker
    if ticker is None:
        return unmapped("no_ticker")
    if ticker in INDEX_FUNDS:
        return unmapped("index_fund")
    if item.asset == "coin" and ticker not in COINS:
        return unmapped("coin_not_counted")
    if item.asset != "coin" and not STOCK_SYMBOL.fullmatch(ticker):
        return unmapped("not_a_us_ticker")
    instrument_id = book.ticker(ticker, on)
    if instrument_id is None and book.knows_ticker(ticker):
        return unmapped("not_listed_then")  # an instrument's ticker, but not on that day
    collision = not book.rules.collisions.mention_counts(ticker, cashtag=False)
    if instrument_id is not None and instrument_id in book.reviewed:
        if collision and instrument_id not in named:
            return unmapped("collision_without_name")
        return mapped(instrument_id)
    # A ticker no rules version has reviewed: it counts only if Alpaca says it does on
    # the post's day, whether or not an earlier post made it an instrument.
    if add_new is None:
        return unmapped("not_an_instrument" if instrument_id is None else "not_checked")
    if collision:
        return unmapped("collision_without_name")
    try:
        listed = await add_new(ticker, item.asset, posted_at)
    except CountCheckFailed as exc:
        log.warning("%s: %s", ticker, exc)
        return unmapped("count_check_failed")
    if listed is None:
        return unmapped("does_not_count")
    if instrument_id is None:
        book.add(listed)
    return mapped(listed.id)


def _instruments_named(book: NameBook, name: str, on: date) -> set[int]:
    """Instruments whose alias appears in the model's name ("Ford Motor Co." -> ford)."""
    if book.name_pattern is None:
        return set()
    found = set()
    for match in book.name_pattern.finditer(name.translate(STRAIGHT_APOSTROPHES)):
        if (instrument_id := book.name(match.group(0), on)) is not None:
            found.add(instrument_id)
    return found


# --- the vote ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Vote:
    market_link: bool
    mentions: tuple[Mention, ...]
    answered: int
    """Models with a valid answer."""
    fallback: bool
    """A model failed: the rules' picks stand in (ai_fallback)."""

    def result(self, book: NameBook, config: AiConfig) -> dict[str, Any]:
        symbols = sorted(
            {book.instruments[m.instrument_id].symbol for m in self.mentions if m.counted
             and m.instrument_id}
        )  # fmt: skip
        return {
            "market_link": self.market_link,
            "symbols": symbols,
            "answered": self.answered,
            "ai_fallback": self.fallback,
            "picker_hash": config.hash,
        }


NEEDED = len(PROVIDERS)
"""Models that must make a link or name an instrument for it to count: both."""


def vote(
    answers: Sequence[ModelAnswer], mapped: Mapping[str, Sequence[Mention]], rules: RulesPick
) -> Vote:
    """Both models must make a link or name an instrument for it to count; if either
    failed, the rules' picks stand in."""
    ok = [a for a in answers if a.ok]
    if len(ok) < NEEDED:
        return Vote(rules.market_link, rules.mentions, len(ok), fallback=True)
    market_link = sum(bool(a.market_link) for a in ok) >= NEEDED
    by_instrument: dict[int, list[Mention]] = {}
    by_name: dict[str, list[Mention]] = {}
    for answer in ok:
        seen: set[object] = set()
        for mention in mapped.get(answer.provider, ()):
            key: object = mention.instrument_id or mention.normalized
            if key in seen:
                continue
            seen.add(key)
            if mention.instrument_id is not None:
                by_instrument.setdefault(mention.instrument_id, []).append(mention)
            else:
                by_name.setdefault(mention.normalized, []).append(mention)
    mentions: list[Mention] = []
    for instrument_id, named in by_instrument.items():
        explicit = sum(m.found_by == "ai_explicit" for m in named)
        first = named[0]
        mentions.append(
            Mention(
                name=first.name,
                normalized=first.normalized,
                found_by="ai_explicit" if 2 * explicit >= len(named) else "ai_implied",
                ticker=first.ticker,
                instrument_id=instrument_id,
                counted=len(named) >= NEEDED,
                models=len(named),
            )
        )
    for normalized, named in by_name.items():
        first = named[0]
        mentions.append(
            Mention(
                first.name, normalized, first.found_by, first.ticker, unmapped=first.unmapped,
                models=len(named),
            )
        )  # fmt: skip
    # One mention per name: a model that gave a counted name without its ticker must not
    # replace the counted mention with its unmapped one; among uncounted ones, the name
    # most models gave stays (review-list reads it).
    mentions.sort(key=lambda m: (not m.counted, -(m.models or 0), m.instrument_id is None))
    return Vote(market_link, unique_names(mentions), len(ok), fallback=False)


# --- one post ------------------------------------------------------------------------------


@dataclass(frozen=True)
class PostText:
    """What the AI picker reads: the post's words and, when the engine has it, the words
    of the post it quotes. No date, engagement or prices."""

    words: str
    quoted: str | None = None

    def user_message(self) -> str:
        message = f"Post:\n{self.words}"
        if self.quoted:
            message += f"\n\nQuoted post:\n{self.quoted}"
        return message


@dataclass(frozen=True)
class AiPick:
    answers: tuple[ModelAnswer, ...]
    mapped: dict[str, tuple[Mention, ...]]
    vote: Vote
    started_at: datetime
    finished_at: datetime
    skipped: str | None = None
    """Why no model was asked (no_words: the post is only links)."""

    def extractions(self, book: NameBook, config: AiConfig, run: int = 1) -> list[Extraction]:
        rows = [
            Extraction(
                method=f"ai:{a.provider}",
                version=config.version,
                run=run,
                model=a.model,
                started_at=a.started_at,
                finished_at=a.finished_at,
                response=a.reply.body if a.reply else None,
                result=(
                    {"market_link": a.market_link, "instruments": [vars(i) for i in a.items]}
                    if a.ok
                    else {}
                )
                | {"picker_hash": config.hash},
                market_link=a.market_link,
                input_tokens=a.reply.input_tokens if a.reply else None,
                cached_input_tokens=a.reply.cached_input_tokens if a.reply else None,
                output_tokens=a.reply.output_tokens if a.reply else None,
                cost_usd=a.cost,
                error=a.error,
                mentions=self.mapped.get(a.provider, ()),
            )
            for a in self.answers
        ]
        result = self.vote.result(book, config)
        if self.skipped:
            result["skipped"] = self.skipped
        rows.append(
            Extraction(
                method="ai:vote",
                version=config.version,
                run=run,
                started_at=self.started_at,
                finished_at=self.finished_at,
                result=result,
                market_link=self.vote.market_link,
                mentions=self.vote.mentions,
            )
        )
        return rows


@dataclass
class AiPicker:
    config: AiConfig
    clients: dict[str, Client]
    secrets: Sequence[str] = field(default_factory=tuple, repr=False)
    clock: Clock = _now

    @classmethod
    def from_settings(cls, settings: Settings, config: AiConfig) -> "AiPicker":
        """The picker with both models. NotReady says why there is none: the version isn't
        complete, or a key is missing (with one model every post would fall back to the
        rules, and still be paid for)."""
        if problems := config.problems():
            raise NotReady(f"AI picker version {config.version} isn't ready: {'; '.join(problems)}")
        clients = build_clients(settings, config)
        if missing := [f"ENGINE_{p.upper()}_KEY" for p in PROVIDERS if p not in clients]:
            raise NotReady(f"not set: {', '.join(missing)}")
        return cls(config, clients, tuple(settings.ai_keys.values()))

    async def pick(
        self,
        book: NameBook,
        post: PostText,
        posted_at: datetime,
        rules: RulesPick,
        add_new: NewTicker | None,
        *,
        retries: int = 0,
    ) -> AiPick:
        """Ask the models side by side, map their names, and vote. A provider without a
        client counts as failed."""
        started = self.clock()
        if not post.words.strip():
            nothing = Vote(False, (), 0, fallback=False)
            return AiPick((), {}, nothing, started, self.clock(), skipped="no_words")
        user = post.user_message()
        asked = [
            ask_model(client, self.config, user, retries=retries, secrets=self.secrets,
                      clock=self.clock)
            for client in self.clients.values()
        ]  # fmt: skip
        answers = list(await asyncio.gather(*asked))
        missing = [p for p in PROVIDERS if p not in self.clients]
        for provider in missing:
            now = self.clock()
            answers.append(
                ModelAnswer(provider, self.config.models[provider].model or "", now, now,
                            error="no client (key or model missing)")
            )  # fmt: skip
        mapped: dict[str, tuple[Mention, ...]] = {}
        for answer in answers:
            if answer.ok:
                said = [await map_item(book, item, posted_at, add_new) for item in answer.items]
                said.sort(key=lambda m: m.instrument_id is None)  # a name given twice: mapped
                mapped[answer.provider] = unique_names(said)
        result = vote(answers, mapped, rules)
        real = tuple(a for a in answers if a.provider in self.clients)
        return AiPick(real, mapped, result, started, self.clock())
