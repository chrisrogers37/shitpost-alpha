"""alert.v1: the public alert document, as stored on engine.alerts.doc and in revision 1.

Every field is public: % moves, counts, times, flags and text only, never a price, an
entry price or a minute series, and no link. engine/alerts/public.py lists every field
with its unit and checks each document before it is written.

Moves and shares are percent (-0.42 is -0.42%), rounded to 2 decimals.
"""

from typing import Final, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

FORMAT: Final = "alert.v1"
Direction = Literal["up", "down"]
Window = Literal["5m", "15m", "1h", "4h", "24h", "close", "1d", "3d", "5d", "7d"]
FyiReason = Literal["no_passing_pair", "few_matches", "not_better_than_random", "late", "burst"]
EXCERPT_CHARS = 200


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Example(Strict):
    """A similar past post and how this call's instrument moved after it."""

    public_id: str
    """The past post's own short id (its page is /s/<public_id>)."""
    posted_at: AwareDatetime
    excerpt: str = Field(max_length=EXCERPT_CHARS)
    """Its words, links removed."""
    move: float
    """The instrument's move over the call's window after that post."""
    vs_benchmark: float | None
    """The move net of beta times the benchmark; None without one (or without a beta)."""


class Evidence(Strict):
    """Similar past posts and how the call's instrument moved over its window after them
    (Gate 0 v1's method): matches by match rule v1 among earlier text posts whose window
    had closed by the alert, at most 50."""

    matches: int = Field(ge=0)
    """Similar past posts with a known move, at most 50."""
    match_days: int = Field(ge=0)
    """The matches' New York dates, counted once each (send rule v1's rule 3)."""
    share_in_direction: float | None = Field(ge=0, le=100)
    """The share of matches that moved the call's way, judged as rule 4 judges (net of the
    benchmark for a company or ETH); None without a direction."""
    median_move: float | None
    """The matches' median move; None without matches."""
    median_vs_benchmark: float | None
    """Their median move net of beta times the benchmark; None without one."""
    benchmark: str | None
    """The benchmark's slug: spy for stocks and ETFs, btc for ETH; None for SPY and BTC."""
    random_median: float | None
    """The instrument's median move over the window at random times in this post's New York
    weekday and hour (engine.random_baselines), judged as rule 4 judges; None without a
    stored baseline."""
    backtest_hit_rate: float | None = Field(ge=0, le=100)
    """Gate 0's hit rate for this pair and picker in the latest backtest run (the share of
    its days the call was right): the backtest's, not live results. None before a run."""
    backtest_days: int | None = Field(ge=0)
    """The days that hit rate is over."""
    low_sample: bool
    """Fewer match days than rule 3 needs."""
    text: str
    """The evidence in one line, e.g. "Like 14 past posts: SPY fell after 64% of them
    within 1 hour (median -0.4% vs random 0.0%)"."""
    examples: list[Example] = Field(max_length=3)
    """The best matches, best first."""


class Call(Strict):
    instrument: str
    """The instrument's slug."""
    window: Window
    direction: Direction | None
    """The way most matches moved; None without matches or on a tie."""
    gate_passed: bool
    """The pair is listed as passing Gate 0 in the send rule."""
    sent: bool
    """The alert was sent on this call."""
    fyi_reason: FyiReason | None
    """The first send rule this call fails; None when sent."""
    evidence: Evidence


class Instrument(Strict):
    slug: str
    symbol: str
    asset_class: Literal["stock", "etf", "coin"]
    market_open: bool
    """Stocks and ETFs: inside the regular session at the alert time; coins: always."""


class AlertV1(Strict):
    format: Literal["alert.v1"] = FORMAT
    public_id: str
    """Its post's short id; its page is /s/<public_id>."""
    signal_key: str
    posted_at: AwareDatetime
    alerted_at: AwareDatetime
    send_until: AwareDatetime
    """posted_at plus 15 minutes: later, nothing is sent (rule 5)."""
    excerpt: str = Field(max_length=EXCERPT_CHARS)
    """The post's words, links removed."""
    topic: str
    picker: str
    """The picker that made it and its version, e.g. "rules v1"."""
    send_rule: str
    """The send rule's version, e.g. "v1"."""
    reason: str | None
    """One line on why the post may matter (engine/extract/reason.py), or None."""
    market_open: bool
    """The lead call's market; without calls, whether US stocks trade at the alert time."""
    disposition: Literal["sent", "fyi"]
    fyi_reason: FyiReason | None
    """The furthest any call got through the send rule; None when sent."""
    lead: str | None
    """The call it leads with, as instrument:window: the one that got furthest through the
    send rule (a sent call first), then one with a direction, then the most match days."""
    instruments: list[Instrument]
    calls: list[Call]
