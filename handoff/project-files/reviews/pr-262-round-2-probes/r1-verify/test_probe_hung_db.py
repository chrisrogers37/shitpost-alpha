"""Probe (not part of the PR): /healthz against a database that stops answering after the
pool already holds a connection. Uses the verify pass's pgproxy.py as the database."""

import socket
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy.engine import make_url

from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient

PROXY = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-262-r2/r1-verify") / "pgproxy.py"


async def test_healthz_on_a_database_that_goes_silent(make_client: MakeClient, web_url: str, tmp_path: Path) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    mode = tmp_path / "mode"
    mode.write_text("forward")
    proxy = subprocess.Popen([sys.executable, str(PROXY), str(port), str(mode)], stdout=subprocess.PIPE, text=True)
    try:
        assert proxy.stdout is not None and proxy.stdout.readline().strip() == "proxy ready"
        url = make_url(web_url).set(host="127.0.0.1", port=port).render_as_string(hide_password=False)
        client = make_client(settings=WebSettings(database_url=url))
        assert (await client.get("/healthz")).status_code == 200  # the pool now holds a connection
        mode.write_text("silent")
        started = time.monotonic()
        response = await client.get("/healthz")
        elapsed = time.monotonic() - started
        print(f"healthz on a silent database: {response.status_code} after {elapsed:.2f}s")
        assert response.status_code == 503
        assert elapsed < 3.5, f"took {elapsed:.2f}s"
    finally:
        mode.write_text("forward")
        proxy.kill()
        proxy.wait()
