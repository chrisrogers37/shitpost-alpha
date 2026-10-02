"""Engine settings, read from ENGINE_* environment variables."""

from typing import Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All engine configuration. Timings are settings so tests can shrink them."""

    model_config = SettingsConfigDict(env_prefix="ENGINE_", frozen=True, populate_by_name=True)

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

    @model_validator(mode="after")
    def _check_timings(self) -> Self:
        # The holder steps down ttl - renew after its last renewal (see lease.py), which
        # leaves at least one renew interval for retries before it does.
        if self.lease_ttl_seconds < 3 * self.lease_renew_seconds:
            raise ValueError("lease_ttl_seconds must be at least 3 x lease_renew_seconds")
        if self.restart_backoff_max_seconds < self.restart_backoff_seconds:
            raise ValueError("restart_backoff_max_seconds must be >= restart_backoff_seconds")
        return self

    @property
    def db_url(self) -> str:
        return self.database_url.get_secret_value()
