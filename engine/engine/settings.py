"""Engine settings, read from ENGINE_* environment variables."""

from typing import Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @model_validator(mode="after")
    def _check_lease_timings(self) -> Self:
        # The holder steps down ttl - renew after its last renewal (see lease.py), which
        # leaves at least one renew interval for retries before it does.
        if self.lease_ttl_seconds < 3 * self.lease_renew_seconds:
            raise ValueError("lease_ttl_seconds must be at least 3 x lease_renew_seconds")
        return self
