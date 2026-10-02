"""Table definitions (SQLAlchemy Core). Migrations create them; code queries through them.

Schemas:
- engine: what the web app may read.
- prices: raw prices, engine only.
- app: tables other plans add later.
"""

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Double,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, REAL

from engine.stages import stage_columns

SCHEMAS = ("engine", "prices", "app")

metadata = MetaData()

# One row. stream_id is made by the first migration and never changes. started_at,
# lease_holder and code_version describe the last holder, even after it stops;
# last_heartbeat_at (written every renew interval while holding) shows whether it is alive.
engine_meta = Table(
    "engine_meta",
    metadata,
    Column("id", SmallInteger, primary_key=True, autoincrement=False),
    Column("stream_id", Uuid, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("last_heartbeat_at", DateTime(timezone=True)),
    Column("lease_holder", Text),
    Column("code_version", Text),
    Column("feeds_dark_since", DateTime(timezone=True)),
    CheckConstraint("id = 1", name="engine_meta_single_row"),
    schema="engine",
)

engine_lease = Table(
    "engine_lease",
    metadata,
    Column("name", Text, primary_key=True),
    Column("holder", Text, nullable=False),
    Column("acquired_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    schema="engine",
)

job_runs = Table(
    "job_runs",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("job", Text, nullable=False),
    Column("scheduled_for", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("error", Text),
    UniqueConstraint("job", "scheduled_for", name="job_runs_job_scheduled_for_key"),
    CheckConstraint(
        "status IN ('running', 'retry', 'succeeded', 'failed')", name="job_runs_status_check"
    ),
    schema="engine",
)

sources = Table(
    "sources",
    metadata,
    Column("id", SmallInteger, Identity(), primary_key=True),
    Column("platform", Text, nullable=False),
    Column("account_id", Text, nullable=False),
    Column("handle", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("avatar_url", Text),
    Column("profile_url", Text, nullable=False),
    UniqueConstraint("platform", "account_id", name="sources_platform_account_id_key"),
    schema="engine",
)
"""Who we follow (one row for Trump), not the feeds we read them through."""

SIGNAL_KINDS = ("post", "reply", "quote", "repost")
NOT_SCORED = ("repost", "no_text", "imported")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(f"'{value}'" for value in values)})"


signals = Table(
    "signals",
    metadata,
    Column("key", Text, primary_key=True),
    Column("source_id", SmallInteger, ForeignKey("engine.sources.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("points_to", Text),
    Column("url", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("posted_at", DateTime(timezone=True), nullable=False),
    Column("has_media", Boolean),
    Column("raw", JSONB, nullable=False),
    Column("raw_via", Text, nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("first_seen_via", Text, nullable=False),
    Column("not_scored", Text),
    *stage_columns(),
    CheckConstraint(_one_of("kind", SIGNAL_KINDS), name="signals_kind_check"),
    CheckConstraint(_one_of("not_scored", NOT_SCORED), name="signals_not_scored_check"),
    Index("signals_source_id_posted_at_idx", "source_id", "posted_at"),
    Index("signals_unfinished_idx", "key", postgresql_where=text("stage NOT IN ('done', 'error')")),
    Index(
        "signals_text_search_idx",
        func.to_tsvector(literal_column("'english'::regconfig"), literal_column("text")),
        postgresql_using="gin",
    ),
    schema="engine",
)
"""One row per post, written once from the first copy any feed or import delivered.

key: "<platform>:<id>", e.g. truth_social:117371353802794328. points_to: the key of the
post a reply, quote or repost points to, when the feed says. has_media: NULL when the
first copy's feed doesn't report media (trumpstruth). raw/raw_via: that first copy and
the feed (or import part) it came from. first_seen_*: the earliest sighting. not_scored:
why the post skips live scoring (it is saved at stage done); NULL for posts that go
through the live stages, starting at "score".
"""

signal_sightings = Table(
    "signal_sightings",
    metadata,
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("feed", Text, nullable=False),
    Column("seen_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("signal_key", "feed", name="signal_sightings_pkey"),
    schema="engine",
)
"""When each live feed first showed each post (database clock)."""

source_stats = Table(
    "source_stats",
    metadata,
    Column("feed", Text, nullable=False),
    Column("hour", DateTime(timezone=True), nullable=False),
    Column("polls", Integer, nullable=False, server_default="0"),
    Column("not_modified", Integer, nullable=False, server_default="0"),
    Column("errors", Integer, nullable=False, server_default="0"),
    Column("blocks", Integer, nullable=False, server_default="0"),
    Column("posts_seen", Integer, nullable=False, server_default="0"),
    Column("posts_first", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("feed", "hour", name="source_stats_pkey"),
    schema="engine",
)
"""Hourly counters per feed. posts_seen: posts the feed showed for the first time;
posts_first: posts whose signal row came from this feed's copy."""

feed_status = Table(
    "feed_status",
    metadata,
    Column("feed", Text, primary_key=True),
    Column("state", Text, nullable=False),
    Column("last_ok_at", DateTime(timezone=True)),
    Column("blocked_since", DateTime(timezone=True)),
    Column("backoff_seconds", Float),
    Column("caught_up_to", DateTime(timezone=True)),
    Column("last_error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("state IN ('up', 'blocked', 'off')", name="feed_status_state_check"),
    schema="engine",
)
"""Each feed's current state, for `python -m engine status` and for the next copy to
pick up from. backoff_seconds: the wait before the next try while blocked (counted from
updated_at, the last poll). caught_up_to: the newest post time this feed has read back to
without a gap; a read that doesn't reach back to it starts a catch-up."""

ASSET_CLASSES = ("stock", "etf", "coin")
CALENDARS = ("XNYS", "24/7")
ALIAS_KINDS = ("name", "old_ticker")
TIMEFRAMES = ("1Min", "1Day")

instruments = Table(
    "instruments",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("slug", Text, nullable=False, unique=True),
    Column("symbol", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("asset_class", Text, nullable=False),
    Column("calendar", Text, nullable=False),
    Column("alpaca_symbol", Text, nullable=False, unique=True),
    Column("benchmark_id", Integer, ForeignKey("engine.instruments.id")),
    Column("rebased_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_one_of("asset_class", ASSET_CLASSES), name="instruments_asset_class_check"),
    CheckConstraint(_one_of("calendar", CALENDARS), name="instruments_calendar_check"),
    CheckConstraint(
        "(asset_class = 'coin') = (calendar = '24/7')", name="instruments_coin_calendar_check"
    ),
    schema="engine",
)
"""What prices are kept for. slug: the lowercase symbol at creation, never changed (pages
link to it). symbol: the current ticker; a ticker change updates it and adds an old_ticker
alias. alpaca_symbol: what Alpaca calls it (BTC/USD for coins). benchmark: SPY for stocks
and ETFs, BTC for coins, none for SPY and BTC. rebased_at: when the backfill last fetched
its whole daily history (the first time, or after a split or dividend moved stored
prices); cached minute bars fetched before then are on an older basis and are refetched."""

instrument_aliases = Table(
    "instrument_aliases",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("alias", Text, nullable=False),
    Column("instrument_id", Integer, ForeignKey("engine.instruments.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("valid_from", Date),
    Column("valid_to", Date),
    UniqueConstraint(
        "alias",
        "instrument_id",
        "kind",
        "valid_from",
        name="instrument_aliases_key",
        postgresql_nulls_not_distinct=True,
    ),
    CheckConstraint(_one_of("kind", ALIAS_KINDS), name="instrument_aliases_kind_check"),
    CheckConstraint("alias = lower(alias)", name="instrument_aliases_lowercase_check"),
    CheckConstraint("valid_from <= valid_to", name="instrument_aliases_valid_check"),
    schema="engine",
)
"""Other ways posts name an instrument: company names (PR 4) and old tickers (fb is META
up to 2022-06-08). valid_from/valid_to: the dates the alias held, both inclusive; NULL is
open-ended."""

market_bars = Table(
    "market_bars",
    metadata,
    Column("instrument_id", Integer, ForeignKey("engine.instruments.id"), nullable=False),
    Column("timeframe", Text, nullable=False),
    Column("bar_start", DateTime(timezone=True), nullable=False),
    Column("open", Double, nullable=False),
    Column("high", Double, nullable=False),
    Column("low", Double, nullable=False),
    Column("close", Double, nullable=False),
    Column("volume", Double, nullable=False),
    Column("vwap", Double),
    Column("trades", Integer),
    Column("feed", Text, nullable=False),
    Column("adjustment", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("instrument_id", "timeframe", "bar_start", name="market_bars_pkey"),
    CheckConstraint(_one_of("timeframe", TIMEFRAMES), name="market_bars_timeframe_check"),
    schema="prices",
)
"""Raw prices, engine only: the web role can't read the prices schema. Daily bars from the
backfill; minute bars only for alert windows (PR 7). Prices are Alpaca's, adjusted for
splits and dividends (adjustment 'all'; coins have nothing to adjust, 'raw'). feed: 'sip'
for stocks and ETFs, 'crypto_us' for coins. fetched_at: when these values were fetched."""

EXTRACTION_METHODS = ("rules", "ai:openai", "ai:anthropic", "ai:vote")
FOUND_BY = ("cashtag", "ticker", "alias", "ai_explicit", "ai_implied")

extractions = Table(
    "extractions",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("method", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("run", SmallInteger, nullable=False, server_default="1"),
    Column("model", Text),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    Column("response", JSONB),
    Column("result", JSONB),
    Column("market_link", Boolean),
    Column("topic", Text),
    Column("input_tokens", Integer),
    Column("cached_input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cost_usd", Numeric(12, 6)),
    Column("error", Text),
    UniqueConstraint("signal_key", "method", "version", "run", name="extractions_key"),
    CheckConstraint(_one_of("method", EXTRACTION_METHODS), name="extractions_method_check"),
    CheckConstraint("run >= 1", name="extractions_run_check"),
    schema="engine",
)
"""What a picker said about a post: one row per signal, method and version (rules: the
rules version; ai:*: the AI picker version). run 1 is the answer; a stability rerun is
run 2, so a rerun never overwrites. model: the pinned model id (ai:openai,
ai:anthropic). response: the provider's response body (no request headers), result: the
normalised answer; market_link and topic (rules only) as columns. Tokens and cost_usd come
from the response and the AI picker's price table. error: why a model's answer is missing
(an error, an invalid answer, a timeout); the vote then takes the rules' picks."""

signal_mentions = Table(
    "signal_mentions",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "extraction_id",
        BigInteger,
        ForeignKey("engine.extractions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("name", Text, nullable=False),
    Column("normalized", Text, nullable=False),
    Column("ticker", Text),
    Column("instrument_id", Integer, ForeignKey("engine.instruments.id")),
    Column("unmapped", Text),
    Column("found_by", Text, nullable=False),
    Column("models", SmallInteger),
    Column("counted", Boolean, nullable=False),
    Column("posted_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("extraction_id", "normalized", name="signal_mentions_key"),
    CheckConstraint(_one_of("found_by", FOUND_BY), name="signal_mentions_found_by_check"),
    CheckConstraint(
        "(instrument_id IS NULL) = (unmapped IS NOT NULL)", name="signal_mentions_mapped_check"
    ),
    CheckConstraint(
        "NOT counted OR instrument_id IS NOT NULL", name="signal_mentions_counted_check"
    ),
    Index("signal_mentions_instrument_id_posted_at_idx", "instrument_id", "posted_at"),
    schema="engine",
)
"""The names in a picker's answer (run 1 only): one row per name per extraction. name: as
written in the post or as the model gave it; normalized: lowercase, single spaces
($aapl for a cashtag). instrument_id, or unmapped with the reason. found_by: cashtag,
ticker or alias (rules), ai_explicit or ai_implied (AI). models: how many models named it
(ai:vote). counted: it counts for this answer. posted_at: the signal's, for the index."""

signal_embeddings = Table(
    "signal_embeddings",
    metadata,
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("model_version", Text, nullable=False),
    Column("text_sha256", Text, nullable=False),
    Column("dims", SmallInteger, nullable=False),
    Column("vector", LargeBinary, nullable=False),
    Column("truncated", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("signal_key", "model_version", name="signal_embeddings_pkey"),
    CheckConstraint("octet_length(vector) = 4 * dims", name="signal_embeddings_dims_check"),
    schema="engine",
)
"""One similarity vector per text post per model version. vector: dims little-endian
float32, normalised to length 1. text_sha256: of the normalised text it was made from.
truncated: the text was longer than the model's 512 tokens."""

MOVE_WINDOWS = ("5m", "15m", "1h", "4h", "24h", "close", "1d", "3d", "5d", "7d")
"""Every window a move is kept for. Stocks and ETFs use 5m, 15m, 1h, close, 1d, 3d and 5d
(d: trading days, each ending at a regular close); coins use 5m, 15m, 1h, 4h, 24h, 3d and
7d (d: 24 hours). The others are NULL."""
ENTRY_RULES = ("main", "premarket", "mirrors")


def _window_columns() -> list[Column[Any]]:
    columns: list[Column[Any]] = []
    for window in MOVE_WINDOWS:
        columns += [
            Column(f"move_{window}", REAL),
            Column(f"adjusted_{window}", REAL),
            Column(f"matured_{window}", DateTime(timezone=True)),
        ]
    return columns


signal_moves = Table(
    "signal_moves",
    metadata,
    Column("instrument_id", Integer, ForeignKey("engine.instruments.id"), nullable=False),
    Column("entry", Text, nullable=False),
    Column("signal_key", Text, ForeignKey("engine.signals.key"), nullable=False),
    Column("entered_at", DateTime(timezone=True)),
    *_window_columns(),
    Column("adjustment", Text, nullable=False),
    Column("basis_at", DateTime(timezone=True)),
    Column("built_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("instrument_id", "entry", "signal_key", name="signal_moves_pkey"),
    CheckConstraint(_one_of("entry", ENTRY_RULES), name="signal_moves_entry_check"),
    schema="engine",
)
"""Each text post's % move per instrument, entry rule and window (Gate 0 v1's rules; no
prices). entry: main (post + 2 min), premarket (SPY and QQQ, alert 04:00-09:30 New York)
or mirrors (post + 20 min). entered_at: the entry bar's time, NULL without an entry.
move_*: exit over entry minus 1. adjusted_*: the move minus beta times the benchmark's
(SPY for stocks and ETFs, BTC for ETH; NULL for SPY and BTC, or without a beta).
matured_*: when the window ended; set with a NULL move when the window was skipped (no
bar), NULL when it ends after the data the row was built from. adjustment: the price basis
('all' for stocks and ETFs, 'raw' for coins); basis_at: the instrument's rebased_at when it
was built. Written by `python -m engine build-moves`."""

random_baselines = Table(
    "random_baselines",
    metadata,
    Column("data_to", Date, nullable=False),
    Column("instrument_id", Integer, ForeignKey("engine.instruments.id"), nullable=False),
    Column("entry", Text, nullable=False),
    Column("window", Text, nullable=False),
    Column("weekday", SmallInteger, nullable=False),
    Column("hour", SmallInteger, nullable=False),
    Column("moves", Integer, nullable=False),
    Column("median_move", REAL),
    Column("adjusted", Integer, nullable=False),
    Column("median_adjusted", REAL),
    PrimaryKeyConstraint(
        "data_to",
        "instrument_id",
        "entry",
        "window",
        "weekday",
        "hour",
        name="random_baselines_pkey",
    ),
    CheckConstraint(_one_of("entry", ENTRY_RULES), name="random_baselines_entry_check"),
    CheckConstraint(_one_of('"window"', MOVE_WINDOWS), name="random_baselines_window_check"),
    CheckConstraint("weekday BETWEEN 0 AND 6", name="random_baselines_weekday_check"),
    CheckConstraint("hour BETWEEN 0 AND 23", name="random_baselines_hour_check"),
    schema="engine",
)
"""The random-time medians the send rule's "better than random" test compares against:
per instrument, entry rule and window, and New York weekday (0 is Monday) and hour, over
the 100 random times of every post in that weekday and hour (Gate 0 v1). data_to: the
sample's last day, which the backtest run records too. moves/median_move: the raw moves;
adjusted/median_adjusted: the benchmark-adjusted ones."""

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("id", Integer, Identity(), primary_key=True),
    Column("code_commit", Text, nullable=False),
    Column("gate_sha256", Text, nullable=False),
    Column("rules_sha256", Text, nullable=False),
    Column("ai_picker_sha256", Text, nullable=False),
    Column("match_rule_sha256", Text, nullable=False),
    Column("model_version", Text, nullable=False),
    Column("data_from", Date, nullable=False),
    Column("data_to", Date, nullable=False),
    Column("report_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    schema="engine",
)
"""One row per backtest: the code, the frozen inputs' hashes (Gate 0 file, rules.json,
the AI picker version's hash, match_rule.json), the data range and the JSON report's
SHA-256."""

backtest_summary = Table(
    "backtest_summary",
    metadata,
    Column("run_id", Integer, ForeignKey("engine.backtest_runs.id"), nullable=False),
    Column("picker", Text, nullable=False),
    Column("view", Text, nullable=False),
    Column("pair", Text, nullable=False),
    Column("calls", Integer, nullable=False),
    Column("days", Integer, nullable=False),
    Column("mean_5bp", Double),
    Column("mean_20bp", Double),
    Column("hit_rate", Double),
    Column("hit_low", Double),
    Column("hit_high", Double),
    Column("p_value", Double),
    Column("q_value", Double),
    Column("last12_mean", Double),
    Column("last12_days", Integer, nullable=False),
    Column("enough_days", Boolean, nullable=False),
    Column("entry_2min", Boolean, nullable=False),
    Column("above_costs", Boolean, nullable=False),
    Column("beats_random", Boolean, nullable=False),
    Column("last12_holds", Boolean, nullable=False),
    Column("passes", Boolean, nullable=False),
    Column("counts", JSONB, nullable=False),
    PrimaryKeyConstraint("run_id", "picker", "view", "pair", name="backtest_summary_pkey"),
    schema="engine",
)
"""One row per run, picker, view and pair with Gate 0's numbers: moves are fractions
(0.001 is 10 bp), days are New York dates with calls. q_value only for the 22 gate tests;
passes is false outside them. counts: the calls each filter dropped and each skip."""
