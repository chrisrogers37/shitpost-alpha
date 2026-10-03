"""Round-2: B1 inverted with a real server process and a flood from another process."""
import os, socket, subprocess, sys, time
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import make_url

HERE = Path("/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/review-262-r2/realflood")
PROJECT = Path(__file__).resolve().parents[3]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.parametrize("path", ["/healthz", "/x", "/api/v1/test/query", None])
def test_api_latency_under_a_real_flood(web_url: str, path: str | None, tmp_path: Path) -> None:
    target = make_url(web_url)
    pport, sport = free_port(), free_port()
    proxy = subprocess.Popen([sys.executable, str(HERE / "slowproxy.py"), str(pport), str(target.port or 5432), "0.02"], stdout=subprocess.PIPE, text=True)
    assert proxy.stdout and proxy.stdout.readline().strip() == "proxy ready"
    url = target.set(host="127.0.0.1", port=pport).render_as_string(hide_password=False)
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("ENGINE_", "WEB_"))}
    environ |= {"WEB_DATABASE_URL": url, "PORT": str(sport), "PYTHONPATH": str(PROJECT)}
    log = (tmp_path / "server.log").open("wb")
    server = subprocess.Popen([sys.executable, str(HERE / "launcher.py")], cwd=PROJECT, env=environ, stdout=log, stderr=subprocess.STDOUT)
    flooder = None
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{sport}", trust_env=False, timeout=30) as c:
            deadline = time.monotonic() + 20
            while True:
                try:
                    c.get("/healthz"); break
                except httpx.TransportError:
                    assert time.monotonic() < deadline; time.sleep(0.1)
            vis = {"X-Real-IP": "198.51.100.2"}
            for _ in range(3):
                c.get("/api/v1/test/query", headers=vis)
            base = []
            for _ in range(5):
                t = time.monotonic(); r = c.get("/api/v1/test/query", headers=vis); base.append(round(time.monotonic() - t, 3)); assert r.status_code == 200
            if path:
                flooder = subprocess.Popen([sys.executable, str(HERE / "flooder.py"), str(sport), path, "200", "8"], stdout=subprocess.PIPE, text=True, env=environ)
                time.sleep(2.5)
            under = []
            for _ in range(10):
                t = time.monotonic(); r = c.get("/api/v1/test/query", headers=vis); under.append(round(time.monotonic() - t, 3)); assert r.status_code == 200
                time.sleep(0.2)
            t = time.monotonic(); h = c.get("/healthz", headers={"X-Real-IP": "192.0.2.50"}); hs = round(time.monotonic() - t, 3)
            counts = flooder.communicate(timeout=60)[0].strip() if flooder else "-"
    finally:
        server.terminate(); server.wait(timeout=20)
        proxy.kill(); proxy.wait()
        if flooder and flooder.poll() is None:
            flooder.kill()
    under.sort(); base.sort()
    print(f"\nflood {path}: {counts}; API baseline median {base[2]}s; under flood median {under[5]} max {under[-1]}; checker /healthz {h.status_code} in {hs}s")
