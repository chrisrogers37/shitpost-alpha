"""Engine settings, read from ENGINE_* environment variables."""

from typing import Annotated, Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

FEED_NAMES = ("direct", "trumpstruth", "cnn", "scrapecreators")
"""The live feeds of Trump's posts, in the order status lists them."""


class Settings(BaseSettings):
    """All engine configuration. Timings are settings so tests can shrink them."""

    model_config = SettingsConfigDict(env_prefix="ENGINE_", frozen=True, populate_by_name=True)

    database_url: str = Field(min_length=1)
    """Engine database. Never the old system's DATABASE_URL."""

    web_role: str = "web"
    """Role the web app connects as. Granted access only if it exists."""

    code_version: str = Field(
        default="unknown",
        validation_alias=AliasChoices("ENGINE_CODE_VERSION", "RAILWAY_GIT_COMMIT_SHA"),
    )

    lease_renew_seconds: float = 10.0
    lease_ttl_seconds: float = 30.0
    scheduler_tick_seconds: float = 15.0
    worker_restart_seconds: float = 30.0
    max_attempts: int = 3
    """Attempts per stage item and per scheduled job run before the final error state."""

    sources_off: Annotated[frozenset[str], NoDecode] = frozenset()
    """ENGINE_SOURCES_OFF: comma list of feeds to skip (direct, trumpstruth, cnn,
    scrapecreators). The others carry on."""

    scrapecreators_key: SecretStr | None = None
    """ScrapeCreators API key. Without it the scrapecreators feed is off."""

    direct_interval_seconds: float = 60.0
    trumpstruth_interval_seconds: float = 60.0
    cnn_interval_seconds: float = 15.0
    scrapecreators_fallback_seconds: float = 120.0
    """ScrapeCreators interval while direct is blocked or off."""
    scrapecreators_check_seconds: float = 3600.0
    """ScrapeCreators interval while direct is healthy: one check call, so a broken key
    shows up before it is needed."""

    feed_failures_to_block: int = 5
    """Failures in a row that count as a block."""
    feed_backoff_min_seconds: float = 60.0
    feed_backoff_max_seconds: float = 1800.0
    feeds_dark_after_seconds: float = 600.0
    """No feed has answered for this long: one operator message, and "dark since" in status."""
    feed_tick_seconds: float = 1.0
    """How often each feed checks whether it is due."""
    http_timeout_seconds: float = 20.0
    cnn_download_timeout_seconds: float = 180.0
    """The full CNN file (about 4 MB gzipped), read on catch-up and by the history import."""
    catchup_max_pages: int = 25
    """Pages a paged feed (direct, scrapecreators) reads back to fill one gap."""

    @field_validator("scrapecreators_key", mode="before")
    @classmethod
    def _empty_key_is_no_key(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("sources_off", mode="before")
    @classmethod
    def _split_sources_off(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(name.strip() for name in value.split(",") if name.strip())
        return value

    @model_validator(mode="after")
    def _check_lease_timings(self) -> Self:
        # The holder steps down ttl - renew after its last renewal (see lease.py), which
        # leaves at least one renew interval for retries before it does.
        if self.lease_ttl_seconds < 3 * self.lease_renew_seconds:
            raise ValueError("lease_ttl_seconds must be at least 3 x lease_renew_seconds")
        return self

    @model_validator(mode="after")
    def _check_sources_off(self) -> Self:
        unknown = self.sources_off - set(FEED_NAMES)
        if unknown:
            raise ValueError(f"unknown feeds {sorted(unknown)}; feeds are {', '.join(FEED_NAMES)}")
        return self
