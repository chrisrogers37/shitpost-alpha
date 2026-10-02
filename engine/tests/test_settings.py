import functools
from datetime import time

import pytest
from pydantic import ValidationError

from engine.registry import JobContext, Registry
from engine.settings import Settings
from tests import helpers


def test_lease_and_attempt_defaults() -> None:
    s = Settings(database_url="postgresql://x")
    assert (s.lease_renew_seconds, s.lease_ttl_seconds, s.max_attempts) == (10.0, 30.0, 3)
    assert "postgresql://x" not in repr(s)


def test_feed_timing_defaults() -> None:
    s = Settings(database_url="postgresql://x")
    intervals = (
        s.direct_interval_seconds,
        s.trumpstruth_interval_seconds,
        s.cnn_interval_seconds,
        s.scrapecreators_fallback_seconds,
        s.scrapecreators_check_seconds,
    )
    assert intervals == (60, 60, 15, 120, 3600)
    assert s.feed_failures_to_block == 5
    assert (s.feed_backoff_min_seconds, s.feed_backoff_max_seconds) == (60, 1800)
    assert s.feeds_dark_after_seconds == 600


@pytest.mark.parametrize(
    "bad",
    [
        {"lease_renew_seconds": 0},
        {"lease_ttl_seconds": -1},
        {"scheduler_tick_seconds": 0},
        {"restart_backoff_seconds": 0},
        {"job_retry_seconds": -1},
        {"max_attempts": 0},
        {"lease_renew_seconds": 10, "lease_ttl_seconds": 25},  # under 3 x renew
        {"restart_backoff_seconds": 60, "restart_backoff_max_seconds": 30},
        {"database_url": ""},
        {"cnn_interval_seconds": 0},
        {"feed_tick_seconds": 0},
        {"feed_failures_to_block": 0},
        {"catchup_max_pages": 0},
        {"feed_backoff_min_seconds": 600, "feed_backoff_max_seconds": 60},
        {"sources_off": "cnn,dirct"},
    ],
)
def test_bad_settings_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"database_url": "postgresql://x"} | bad)


def test_api_keys_are_stripped_and_checked_without_showing_them() -> None:
    def key(value: str) -> str | None:
        secret = Settings(database_url="postgresql://x", scrapecreators_key=value)
        return secret.scrapecreators_key.get_secret_value() if secret.scrapecreators_key else None

    assert key(" sc-key-0123\n") == "sc-key-0123"  # pasted with a newline
    assert key(" \r\n") is None
    for bad in ("sc key 0123", "sc-key-\x000123", "sc-kéy-0123"):
        with pytest.raises(ValidationError) as caught:
            key(bad)
        [error] = caught.value.errors()  # the CLI prints only each error's place and message
        assert error["loc"] == ("scrapecreators_key",) and "0123" not in error["msg"]


def test_heavy_jobs_must_be_picklable() -> None:
    async def local(ctx: JobContext) -> None: ...

    registry = Registry()
    with pytest.raises(ValueError, match="must be picklable"):
        registry.register_job("local", time(0, 0), local, heavy=True)
    registry.register_job("partial", time(0, 0), functools.partial(helpers.record_pid), heavy=True)
    assert registry.jobs["partial"].heavy
