"""The AI picker: three models, one from each provider, say whether a post has a market
link and which instruments it names or implies; a link or an instrument counts when 2 of
3 make it.

Its version is ai.json: the prompt, the schema, the model ids, the settings, the price
table and the window start, pinned by hash like the rules. Every client is built with its
key passed from the ENGINE_ settings, never from the old system's variables, and none is
built without its key.

Each call has a deadline (15 s). A model that errs, answers invalid JSON or misses the
deadline counts as failed: with one failed the other two must agree, with two or more
failed the post takes the rules' answer and is marked ai_fallback. Batch runs retry rate
limits and server errors with back-off; a deadline is never retried, since live it would
be missed.
"""

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
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
)
from engine.market.instruments import COINS, STOCK_SYMBOL, AssetClass, normalize_alias
from engine.settings import Settings

log = logging.getLogger(__name__)

MANIFEST = Path(__file__).with_name("ai.json")
Provider = Literal["openai", "xai", "anthropic"]
PROVIDERS: tuple[Provider, ...] = ("openai", "xai", "anthropic")
XAI_BASE_URL = "https://api.x.ai/v1"
INDEX_FUNDS = frozenset({"SPY", "QQQ", "DIA", "IWM", "VOO", "IVV", "VTI", "RSP"})
"""Broad index funds: never a named instrument (SPY and QQQ come from the market link)."""
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504, 529})
PER_MILLION = Decimal(1_000_000)


class NotReady(RuntimeError):
    """The AI picker version isn't complete enough for real calls."""


class InvalidAnswer(ValueError):
    """A model's answer isn't the JSON the schema asks for."""


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
    provider: Provider
    model: str | None
    """A dated snapshot, never an alias. None until chosen (B2)."""
    price: Price | None
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
    reason: ReasonSpec

    def problems(self) -> list[str]:
        """What stops real calls: unpinned models, prices not checked."""
        found = []
        for name in PROVIDERS:
            spec = self.models[name]
            if spec.model is None:
                found.append(f"{name}: no model pinned")
            if spec.price is None or spec.price.checked is None:
                found.append(f"{name}: price not checked")
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


def load_ai_config(manifest: Path = MANIFEST) -> AiConfig:
    """The AI picker version in `manifest`, after checking every file's hash."""
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
    config = json.loads(texts[data["config"]])
    settings = config["settings"]
    reason = config["reason"]
    window = config.get("window_start")
    return AiConfig(
        version=int(data["version"]),
        hash=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        instructions=texts[data["prompt"]].strip(),
        schema=config["schema"],
        models={
            name: ModelSpec(name, spec["model"], _price(spec.get("prices")), spec["temperature"])
            for name, spec in ((name, config["models"][name]) for name in PROVIDERS)
        },
        max_output_tokens=int(settings["max_output_tokens"]),
        timeout_seconds=float(settings["timeout_seconds"]),
        max_instruments=int(settings["max_instruments"]),
        why_max_chars=int(settings["why_max_chars"]),
        window_start=datetime.fromisoformat(window) if window else None,
        reason=ReasonSpec(
            version=int(reason["version"]),
            instructions=texts[reason["prompt"]].strip(),
            provider=reason["provider"],
            max_output_tokens=int(reason["max_output_tokens"]),
            max_chars=int(reason["max_chars"]),
        ),
    )


@cache
def current_ai_config() -> AiConfig:
    return load_ai_config()


# --- talking to the providers -----------------------------------------------------------


@dataclass(frozen=True)
class Reply:
    """A provider's answer: its response body (never the request or its headers), the
    text the model wrote and the tokens it billed. input_tokens includes cached ones."""

    body: dict[str, Any]
    text: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class Client(Protocol):
    provider: Provider
    model: str

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply: ...


class OpenAIChat:
    """OpenAI, and xAI through the same SDK at XAI_BASE_URL: chat completions with a
    strict JSON schema."""

    def __init__(
        self,
        provider: Provider,
        model: str,
        key: str,
        *,
        temperature: float | None,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.client = openai.AsyncOpenAI(
            api_key=key,
            base_url=XAI_BASE_URL if provider == "xai" else None,
            timeout=timeout,
            max_retries=0,
            http_client=http_client,
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
        body = response.model_dump(mode="json")
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message.content is None:
            refusal = choice.message.refusal if choice else None
            raise InvalidAnswer(f"no content (refusal: {refusal!r})")
        if choice.finish_reason != "stop":
            raise InvalidAnswer(f"stopped early: {choice.finish_reason}")
        usage = response.usage
        cached = 0
        if usage and usage.prompt_tokens_details and usage.prompt_tokens_details.cached_tokens:
            cached = usage.prompt_tokens_details.cached_tokens
        return Reply(
            body=body,
            text=choice.message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            cached_input_tokens=cached,
            output_tokens=usage.completion_tokens if usage else 0,
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
            api_key=key, timeout=timeout, max_retries=0, http_client=http_client
        )

    async def ask(
        self, instructions: str, user: str, schema: dict[str, Any] | None, max_tokens: int
    ) -> Reply:
        # This SDK version has no temperature parameter, so it goes in the body (B2 checks
        # the API takes it for the pinned model).
        extra = {} if self.temperature is None else {"temperature": self.temperature}
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
        body = response.model_dump(mode="json")
        if response.stop_reason != "end_turn":
            raise InvalidAnswer(f"stopped early: {response.stop_reason}")
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        cached = usage.cache_read_input_tokens or 0
        written = usage.cache_creation_input_tokens or 0
        return Reply(
            body=body,
            text=text,
            input_tokens=usage.input_tokens + cached + written,
            cached_input_tokens=cached,
            output_tokens=usage.output_tokens,
        )


def build_clients(settings: Settings, config: AiConfig) -> dict[str, Client]:
    """A client for each provider whose ENGINE_ key is set and whose model is pinned.
    Without keys this is empty and nothing is built."""
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
                provider, spec.model, key, temperature=spec.temperature, timeout=timeout
            )
    return clients


def scrubbed(text: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[key]")
    return text


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, openai.APITimeoutError | anthropic.APITimeoutError):
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
    """One model's answer to one post. Never raises: a failure is the answer's error."""
    started = clock()
    attempt = 0
    while True:
        try:
            async with asyncio.timeout(config.timeout_seconds):
                reply = await client.ask(
                    config.instructions, user, config.schema, config.max_output_tokens
                )
            market_link, items = parse_answer(
                reply.text, config.max_instruments, config.why_max_chars
            )
        except TimeoutError:
            error = f"timeout after {config.timeout_seconds:g} s"
        except InvalidAnswer as exc:
            error = f"invalid answer: {exc}"
        except Exception as exc:
            if attempt < retries and _retryable(exc):
                attempt += 1
                await asyncio.sleep(backoff_seconds * 2 ** (attempt - 1))
                continue
            error = scrubbed(f"{type(exc).__name__}: {exc}", secrets)
        else:
            price = config.models[client.provider].price
            tokens = (reply.input_tokens, reply.cached_input_tokens, reply.output_tokens)
            cost = price.cost(*tokens) if price is not None else None
            finished = clock()
            return ModelAnswer(
                client.provider, client.model, started, finished, reply, market_link, tuple(items),
                cost=cost,
            )  # fmt: skip
        log.warning("%s (%s) failed: %s", client.provider, client.model, error)
        return ModelAnswer(client.provider, client.model, started, clock(), error=error)


# --- mapping names to instruments --------------------------------------------------------

NewTicker = Callable[[str, str, AssetClass, datetime], Awaitable[Listed | None]]
"""Adds a ticker that isn't an instrument yet if it counts at the post's time: (ticker,
name, asset class, post time) -> the new instrument, or None if it doesn't count."""


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
    if instrument_id is not None:
        if not book.rules.collisions.mention_counts(ticker, cashtag=False) and (
            instrument_id not in named
        ):
            return unmapped("collision_without_name")
        return mapped(instrument_id)
    if add_new is None:
        return unmapped("not_an_instrument")
    if not book.rules.collisions.mention_counts(ticker, cashtag=False):
        return unmapped("collision_without_name")
    listed = await add_new(ticker, item.name, item.asset, posted_at)
    if listed is None:
        return unmapped("does_not_count")
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
    """Fewer than two answered: the rules' picks stand in (ai_fallback)."""

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


NEEDED = 2
"""Models that must make a link or name an instrument for it to count."""


def vote(
    answers: Sequence[ModelAnswer], mapped: Mapping[str, Sequence[Mention]], rules: RulesPick
) -> Vote:
    """2 of 3; with one failed, the other two must agree; with two failed, the rules."""
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
    mentions = []
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
    return Vote(market_link, tuple(mentions), len(ok), fallback=False)


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
                    None
                    if not a.ok
                    else {
                        "market_link": a.market_link,
                        "instruments": [vars(item) for item in a.items],
                    }
                ),
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
    secrets: Sequence[str] = field(default_factory=tuple)
    clock: Clock = _now

    @classmethod
    def from_settings(cls, settings: Settings, config: AiConfig) -> "AiPicker | None":
        """None (the AI picker is off) when no ENGINE_ AI key is set."""
        clients = build_clients(settings, config)
        if not clients:
            return None
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
                mapped[answer.provider] = tuple(
                    [await map_item(book, item, posted_at, add_new) for item in answer.items]
                )
        result = vote(answers, mapped, rules)
        real = tuple(a for a in answers if a.provider in self.clients)
        return AiPick(real, mapped, result, started, self.clock())
