import asyncio, time
import pytest
from engine.web.db import make_web_engine
from engine.web.health import FRESH_SECONDS, HealthProbe
from engine.web.settings import WebSettings
from tests.web.proxy import db_proxy


@pytest.mark.parametrize("close_after", [0.0, 0.01, 0.2, 3.0, 8.0, -1.0])
async def test_close_timing(web_url: str, close_after: float) -> None:
    """close_after: seconds after ok() returned False (at the 2 s mark); -1 means close
    1 s into the query, before any timeout."""
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        assert await probe.ok() is True
        proxy.go_silent()
        await asyncio.sleep(FRESH_SECONDS)
        if close_after < 0:
            caller = asyncio.create_task(probe.ok())
            await asyncio.sleep(1.0)
        else:
            assert await probe.ok() is False
            if close_after:
                await asyncio.sleep(close_after)
        started = time.monotonic()
        await probe.close()
        print(f"\nclose {close_after}s after the caller's answer: took {time.monotonic() - started:.2f}s")
        if close_after < 0:
            print(f"  waiting caller got {await caller}")
