"""Engine settings, read from ENGINE_* environment variables."""

from pathlib import Path
from typing import Annotated, Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

FEED_NAMES = ("direct", "trumpstruth", "cnn", "scrapecreators")
"""The live feeds of Trump's posts, in the order status lists them."""


class Settings(BaseSettings):
    """All engine configuration. Timings are settings so tests can shrink them."""

    model_config = SettingsConfigDict(
        env_prefix="ENGINE_", frozen=True, populate_by_name=True, hide_input_in_errors=True
    )

    database_url: SecretStr = Field(min_length=1)
    """Engine database. Never the old system's DATABASE_URL. Secret, so it never prints."""

    web_role: str = "web"
    """Role the web app connects as. Granted access only if it exists."""

    code_version: str = Field(
        default="unknown",
        validation_alias=AliasChoices("ENGINE_CODE_VERSION", "RAILWAY_GIT_COMMIT_SHA"),
    )

    lease_renew_seconds: float = Field(default=10.0, gt=0)
    lease_ttl_seconds: float = Field(default=30.0, gt=0)
    scheduler_tick_seconds: float = Field(default=15.0, gt=0)
    job_retry_seconds: float = Field(default=300.0, ge=0)
    """A failed job run waits this long times its attempt count before its next try."""
    restart_backoff_seconds: float = Field(default=30.0, gt=0)
    """First wait before restarting a failed worker or the holder's work; doubles each time."""
    restart_backoff_max_seconds: float = Field(default=900.0, gt=0)
    """Longest wait. Running this long without failing ends a failure streak."""
    max_attempts: int = Field(default=3, ge=1)
    """Attempts per stage item and per scheduled job run before the final error state."""

    sources_off: Annotated[frozenset[str], NoDecode] = frozenset()
    """ENGINE_SOURCES_OFF: comma list of feeds to skip (direct, trumpstruth, cnn,
    scrapecreators). The others carry on."""

    scrapecreators_key: SecretStr | None = None
    """ScrapeCreators API key. Without it the scrapecreators feed is off."""

    direct_interval_seconds: float = Field(default=60.0, gt=0)
    trumpstruth_interval_seconds: float = Field(default=60.0, gt=0)
    cnn_interval_seconds: float = Field(default=15.0, gt=0)
    scrapecreators_fallback_seconds: float = Field(default=120.0, gt=0)
    """ScrapeCreators interval while direct is blocked or off."""
    scrapecreators_check_seconds: float = Field(default=3600.0, gt=0)
    """ScrapeCreators interval while direct is healthy: one check call, so a broken key
    shows up before it is needed."""

    feed_failures_to_block: int = Field(default=5, ge=1)
    """Failures in a row that count as a block."""
    feed_backoff_min_seconds: float = Field(default=60.0, gt=0)
    feed_backoff_max_seconds: float = Field(default=1800.0, gt=0)
    feeds_dark_after_seconds: float = Field(default=600.0, gt=0)
    """No feed has answered for this long: one operator message, and "dark since" in status."""
    feed_tick_seconds: float = Field(default=1.0, gt=0)
    """How often each feed checks whether it is due."""
    http_timeout_seconds: float = Field(default=20.0, gt=0)
    cnn_download_timeout_seconds: float = Field(default=180.0, gt=0)
    """The full CNN file (about 4 MB gzipped), read on catch-up and by the history import."""
    catchup_max_pages: int = Field(default=25, ge=1)
    """Pages a paged feed (direct, scrapecreators) reads back to fill one gap."""

    alpaca_key_id: SecretStr | None = Field(default=None, validation_alias="ALPACA_API_KEY_ID")
    alpaca_secret_key: SecretStr | None = Field(
        default=None, validation_alias="ALPACA_API_SECRET_KEY"
    )
    """Alpaca market data keys (ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, Alpaca's own names).
    Stock bars need them; coin bars don't."""
    alpaca_calls_per_minute: float = Field(default=150.0, gt=0, le=200)
    """Client-side cap on Alpaca calls, under the free plan's 200 a minute."""
    alpaca_backoff_seconds: float = Field(default=2.0, gt=0)
    """First wait before a retry (a 5xx, a dropped call, or a 429 that names no reset);
    doubles each try."""
    bars_cache_dir: Path = Path.home() / ".cache" / "shitpost-engine" / "bars"
    """Minute-bar cache (ENGINE_BARS_CACHE_DIR), outside the repo."""

    @field_validator("scrapecreators_key", "alpaca_key_id", "alpaca_secret_key", mode="before")
    @classmethod
    def _clean_keys(cls, value: object) -> object:
        """An API key as it goes in a request header: a pasted space or newline is
        stripped, blank means no key, and anything but printable ASCII is refused. The
        message names the variable, never the value."""
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if not isinstance(value, str):
            return value
        key = value.strip()
        if not key:
            return None
        if not all("!" <= char <= "~" for char in key):
            raise ValueError("must be printable ASCII with no spaces (value not shown)")
        return key

    @field_validator("sources_off", mode="before")
    @classmethod
    def _split_sources_off(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(name.strip() for name in value.split(",") if name.strip())
        return value

    @model_validator(mode="after")
    def _check_timings(self) -> Self:
        # The holder steps down ttl - renew after its last renewal (see lease.py), which
        # leaves at least one renew interval for retries before it does.
        if self.lease_ttl_seconds < 3 * self.lease_renew_seconds:
            raise ValueError("lease_ttl_seconds must be at least 3 x lease_renew_seconds")
        if self.restart_backoff_max_seconds < self.restart_backoff_seconds:
            raise ValueError("restart_backoff_max_seconds must be >= restart_backoff_seconds")
        if self.feed_backoff_max_seconds < self.feed_backoff_min_seconds:
            raise ValueError("feed_backoff_max_seconds must be >= feed_backoff_min_seconds")
        return self

    @model_validator(mode="after")
    def _check_sources_off(self) -> Self:
        unknown = self.sources_off - set(FEED_NAMES)
        if unknown:
            raise ValueError(f"unknown feeds {sorted(unknown)}; feeds are {', '.join(FEED_NAMES)}")
        return self

    @property
    def alpaca_keys(self) -> tuple[str, str] | None:
        """Both Alpaca keys, or None when either is missing."""
        if self.alpaca_key_id is None or self.alpaca_secret_key is None:
            return None
        return self.alpaca_key_id.get_secret_value(), self.alpaca_secret_key.get_secret_value()

    @property
    def db_url(self) -> str:
        """The database URL as plain text, for the driver. Never log or print it."""
        return self.database_url.get_secret_value()
