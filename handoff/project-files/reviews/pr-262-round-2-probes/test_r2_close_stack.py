import asyncio, io, time
from engine.web.db import make_web_engine
from engine.web.health import FRESH_SECONDS, HealthProbe
from engine.web.settings import WebSettings
from tests.web.proxy import db_proxy


async def test_where_close_waits(web_url: str) -> None:
    async with db_proxy(web_url) as proxy:
        probe = HealthProbe(make_web_engine(WebSettings(database_url=proxy.url), pool_size=1))
        assert await probe.ok() is True
        proxy.go_silent()
        await asyncio.sleep(FRESH_SECONDS)
        t0 = time.monotonic()
        assert await probe.ok() is False
        task = probe._query
        assert task is not None
        for delay in (0.5, 4.0):
            await asyncio.sleep(delay)
            buf = io.StringIO(); task.print_stack(file=buf)
            print(f"\n--- t={time.monotonic()-t0:.1f}s before cancel, task stack:\n" + buf.getvalue()[-1500:])
        task.cancel()
        await asyncio.sleep(1.0)
        buf = io.StringIO(); task.print_stack(file=buf)
        print(f"\n--- t={time.monotonic()-t0:.1f}s, 1 s after cancel, done={task.done()}:\n" + buf.getvalue()[-2500:])
        await asyncio.wait({task})
        print(f"\ntask done at t={time.monotonic()-t0:.1f}s")
        await probe.db.dispose()
