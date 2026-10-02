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


def test_heavy_jobs_must_be_picklable() -> None:
    async def local(ctx: JobContext) -> None: ...

    registry = Registry()
    with pytest.raises(ValueError, match="must be picklable"):
        registry.register_job("local", time(0, 0), local, heavy=True)
    registry.register_job("partial", time(0, 0), functools.partial(helpers.record_pid), heavy=True)
    assert registry.jobs["partial"].heavy
