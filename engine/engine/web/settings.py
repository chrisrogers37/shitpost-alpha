"""Web settings, read from WEB_* environment variables (and Railway's PORT)."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

POSTGRES_DRIVERS = ("postgres", "postgresql", "postgresql+psycopg")


class WebSettings(BaseSettings):
    """Everything the web process reads. It never reads the engine's ENGINE_* settings."""

    model_config = SettingsConfigDict(
        env_prefix="WEB_", frozen=True, populate_by_name=True, hide_input_in_errors=True
    )

    database_url: SecretStr = Field(min_length=1)
    """The web role's URL: reads what `migrate` grants it (WEB_GRANTS), nothing else. Use
    Neon's direct endpoint: a transaction pooler drops the per-connection statement timeout."""

    rate_limit_per_minute: float = Field(default=120.0, gt=0)
    """Requests a minute each visitor address may keep up."""
    rate_limit_burst: int = Field(default=30, ge=1)
    """Requests a visitor may make at once on top of that, from a rested bucket."""

    client_ip_header: str = Field(default="X-Real-IP", pattern=r"^[A-Za-z0-9-]+$")
    """Header that carries the visitor's address, as written by Railway's edge proxy:
    https://docs.railway.com/networking/public-networking/specs-and-limits ("X-Real-IP for
    identifying client's remote IP"). Without the header, the socket address is used."""
    trusted_hops: int = Field(default=1, ge=1)
    """Proxies in front of the app that each append to that header. The address used is
    this many entries from the right, so entries a visitor sends (on the left) never count."""

    pool_size: int = Field(default=5, ge=1)
    """Database connections the API keeps open at most; /healthz keeps one more of its own."""

    port: int = Field(default=8000, ge=1, le=65535, validation_alias="PORT")
    """Port to listen on; Railway sets PORT."""

    @field_validator("database_url")
    @classmethod
    def _is_postgres_url(cls, url: SecretStr) -> SecretStr:
        # Never echo the value: it has the password.
        raw = url.get_secret_value()
        try:
            parsed = make_url(raw)
        except (ArgumentError, ValueError):  # not a URL, or a port that isn't a number
            parsed = None
        if parsed is None or parsed.drivername not in POSTGRES_DRIVERS:
            raise ValueError("not a postgresql:// URL")
        # An "@" only ends the user and password. Another, if it was in the password, would
        # put the password's tail in the host or database name, which the driver's errors
        # (and so the logs) show; anywhere else it is safe to write as %40 too.
        if raw.count("@") > (0 if parsed.username is None else 1):
            raise ValueError('write each "@" in the URL as %40, except the one before the host')
        return url

    @property
    def db_url(self) -> str:
        """The database URL as plain text, for the driver. Never log or print it."""
        return self.database_url.get_secret_value()
