"""By-hand verification driver for PR #262 (site D0). Test-only; localhost only.

argv: <engine dir> <web-role URL through the proxy> <admin URL of the throwaway db> <proxy port>
Runs the real `python -m engine web` (phase A) and the launcher with the PR's test routes
(phase B), each against a local TCP proxy to the sandbox Postgres that can be killed
("Postgres stopped") or frozen ("silent"). Prints what it sees."""

import base64
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import psycopg

V = Path(__file__).resolve().parent
W = Path(sys.argv[1])
WEB_URL = sys.argv[2]
ADMIN_URL = sys.argv[3]
PROXY_PORT = int(sys.argv[4])
PW = (V / "pw").read_text().strip()
PY = "/home/user/engine-venv-262/bin/python"
MODE = V / "proxy_mode"

EXPECTED = {
    "content-security-policy": "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "strict-transport-security": "max-age=31536000",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}


def out(*a: object) -> None:
    print(*a, flush=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def env(extra: dict[str, str]) -> dict[str, str]:
    e = {k: v for k, v in os.environ.items() if not k.startswith(("ENGINE_", "WEB_")) and k != "PORT"}
    e["PYTHONPATH"] = str(W)
    return e | extra


def headers_ok(r: httpx.Response) -> str:
    bad = [k for k, v in EXPECTED.items() if r.headers.get(k) != v]
    return "sec-headers OK" if not bad else f"sec-headers MISSING/WRONG {bad}"


def show(label: str, r: httpx.Response, extra: tuple[str, ...] = ()) -> None:
    body = r.text if len(r.text) < 300 else r.text[:300] + "..."
    hs = {h: r.headers.get(h) for h in ("content-type", "cache-control", "access-control-allow-origin", "allow", "retry-after", "server", *extra) if h in r.headers}
    out(f"  [{label}] {r.status_code} {headers_ok(r)} {hs} body={body!r}")


def start_proxy() -> subprocess.Popen[str]:
    MODE.write_text("forward")
    p = subprocess.Popen([PY, str(V / "pgproxy.py"), str(PROXY_PORT), str(MODE)], stdout=subprocess.PIPE, text=True)
    assert p.stdout is not None and p.stdout.readline().strip() == "proxy ready"
    return p


def stop_proxy(p: subprocess.Popen[str]) -> None:
    p.kill()
    p.wait()


def start_server(args: list[str], extra: dict[str, str], log_name: str) -> tuple[subprocess.Popen[bytes], httpx.Client, Path]:
    port = free_port()
    log_path = V / log_name
    log = log_path.open("wb")
    p = subprocess.Popen([PY, *args], cwd=W, env=env({"WEB_DATABASE_URL": WEB_URL, "PORT": str(port)} | extra), stdout=log, stderr=subprocess.STDOUT)
    c = httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=40)
    deadline = time.monotonic() + 20
    while True:
        try:
            c.get("/healthz")
            break
        except httpx.TransportError:
            if p.poll() is not None or time.monotonic() > deadline:
                raise SystemExit(f"server did not start: {log_path.read_text()}")
            time.sleep(0.1)
    return p, c, log_path


def sigterm(p: subprocess.Popen[bytes], label: str) -> float:
    t = time.monotonic()
    p.send_signal(signal.SIGTERM)
    try:
        code = p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
        code = "KILLED after 60s"
    dt = time.monotonic() - t
    out(f"  [SIGTERM {label}] exit={code} after {dt:.2f}s")
    return dt


def timed(c: httpx.Client, label: str, path: str, **kw: object) -> httpx.Response | None:
    t = time.monotonic()
    try:
        r = c.get(path, **kw)  # type: ignore[arg-type]
    except httpx.TimeoutException:
        out(f"  [{label}] CLIENT TIMEOUT after {time.monotonic() - t:.2f}s")
        return None
    out(f"  [{label}] {r.status_code} in {time.monotonic() - t:.2f}s body={r.text[:120]!r} {headers_ok(r)}")
    return r


def stream_id_in_db() -> str:
    with psycopg.connect(ADMIN_URL) as conn:
        row = conn.execute("SELECT stream_id FROM engine.engine_meta").fetchone()
        assert row is not None
        return str(row[0])


def phase_a() -> None:
    out("== Phase A: python -m engine web (no /api/v1 routes but openapi.json)")
    proxy = start_proxy()
    p, c, log_path = start_server(["-m", "engine", "web"], {}, "phaseA.log")
    show("GET /healthz", c.get("/healthz"))
    show("GET /api/v1/openapi.json", c.get("/api/v1/openapi.json", headers={"Origin": "https://evil.example"}))
    show("GET /api/v1/x", c.get("/api/v1/x"))
    show("GET /api/v1", c.get("/api/v1"))
    show("GET /api/nope", c.get("/api/nope"))
    show("GET /x (outside /api)", c.get("/x"))
    for path in ("/docs", "/redoc", "/openapi.json"):
        show(f"GET {path}", c.get(path))
    show("POST /api/v1/openapi.json (405)", c.post("/api/v1/openapi.json"))
    show("DELETE /api/v1/openapi.json (405)", c.delete("/api/v1/openapi.json"))
    show("POST /healthz (405 outside api)", c.post("/healthz"))
    show("HEAD /healthz", c.head("/healthz"))
    for origin in ("https://shitpostalpha.com", "https://evil.example", "null"):
        show(f"OPTIONS preflight GET Origin={origin}", c.options("/api/v1/openapi.json", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}))
        show(f"OPTIONS preflight POST Origin={origin}", c.options("/api/v1/openapi.json", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}))
        show(f"GET with Origin={origin}", c.get("/api/v1/openapi.json", headers={"Origin": origin}), ("access-control-allow-credentials", "vary"))

    out("-- rate limit (defaults 120/min + burst 30), on GET /api/v1/x")
    def burst(label: str, n: int, headers: object = None) -> list[int]:
        statuses = [c.get("/api/v1/x", headers=headers).status_code for _ in range(n)]  # type: ignore[arg-type]
        out(f"  [{label}] {n} requests: {statuses.count(404)}x404 {statuses.count(429)}x429 first429_at={statuses.index(429) if 429 in statuses else None}")
        return statuses
    burst("X-Real-IP A=198.51.100.1", 32, {"X-Real-IP": "198.51.100.1"})
    r = c.get("/api/v1/x", headers={"X-Real-IP": "198.51.100.1"})
    show("A again", r)
    burst("X-Real-IP B=198.51.100.2 (separate bucket)", 3, {"X-Real-IP": "198.51.100.2"})
    burst("A + forged X-Forwarded-For", 2, {"X-Real-IP": "198.51.100.1", "X-Forwarded-For": "203.0.113.9"})
    burst("two X-Real-IP lines [C, A] (last line wins)", 2, [("X-Real-IP", "198.51.100.3"), ("X-Real-IP", "198.51.100.1")])
    burst("X-Real-IP 'C, A' (rightmost entry wins)", 2, {"X-Real-IP": "198.51.100.3, 198.51.100.1"})
    burst("X-Real-IP 'A, C' (rightmost=C, a fresh bucket)", 2, {"X-Real-IP": "198.51.100.1, 198.51.100.3"})
    burst("garbage X-Real-IP -> socket address", 2, {"X-Real-IP": "garbage"})
    burst("no header -> socket address 127.0.0.1 (shared with garbage)", 32)
    burst("spoofed X-Real-IP D (no edge locally, so it is honoured)", 2, {"X-Real-IP": "192.0.2.77"})
    burst("IPv6 a in /64", 31, {"X-Real-IP": "2001:db8:1:2::1"})
    burst("IPv6 b same /64 (shares a's bucket)", 1, {"X-Real-IP": "2001:db8:1:2::ffff"})
    hz = [c.get("/healthz", headers={"X-Real-IP": "198.51.100.1"}).status_code for _ in range(40)]
    out(f"  [healthz x40 from limited A] statuses={set(hz)}")
    r = c.get("/api/v1/openapi.json", headers={"X-Real-IP": "198.51.100.1"})
    show("429 has every header", r)
    r = c.get("/x", headers={"X-Real-IP": "198.51.100.1"})
    show("429 outside /api is plain text", r)

    out("-- database stopped (proxy killed)")
    stop_proxy(proxy)
    timed(c, "healthz, db down", "/healthz")
    timed(c, "healthz, db down again", "/healthz")
    out("-- database back")
    proxy = start_proxy()
    timed(c, "healthz, db back", "/healthz")
    out("-- database silent (accepts, never answers)")
    MODE.write_text("silent")
    timed(c, "healthz, db silent", "/healthz")
    timed(c, "healthz, db silent again", "/healthz")
    MODE.write_text("forward")
    time.sleep(0.5)
    timed(c, "healthz, db forwarding again", "/healthz")
    timed(c, "healthz, db forwarding again (2)", "/healthz")

    out("-- SIGTERM with an idle keep-alive connection open")
    c.get("/healthz")
    sigterm(p, "idle, keep-alive open")
    c.close()
    stop_proxy(proxy)
    text = log_path.read_text()
    out("  log lines:", len(text.splitlines()))
    for line in text.splitlines()[:6] + ["..."] + text.splitlines()[-6:]:
        out("   |", line)
    out("  log has 127.0.0.1:", "127.0.0.1" in text, "| has 198.51.100:", "198.51.100" in text, "| has 2001:db8:", "2001:db8" in text, "| has password:", PW in text, "| has Traceback:", "Traceback" in text)


def phase_b() -> None:
    out("== Phase B: launcher = real CLI + the PR's test routes + /api/v1/vt/sleep")
    proxy = start_proxy()
    p, c, log_path = start_server([str(V / "launch_probe.py")], {}, "phaseB.log")
    sid = stream_id_in_db()
    r = c.get("/api/v1/test/query", headers={"Origin": "https://evil.example"})
    show("GET /api/v1/test/query", r)
    out("   stream_id matches engine_meta:", r.json().get("stream_id") == sid)

    out("-- paging")
    seen, params, pages = [], {"limit": "20"}, 0
    while True:
        r = c.get("/api/v1/test/numbers", params=params)
        body = r.json()
        pages += 1
        seen += [i["n"] for i in body["items"]]
        if pages == 1:
            show("first page", r)
            out("   keys:", sorted(body), "next_before:", body["next_before"], "decoded:", base64.urlsafe_b64decode(body["next_before"] + "==").decode())
        if body["next_before"] is None:
            break
        params["before"] = body["next_before"]
    out(f"   walked {pages} pages, {len(seen)} items, in order: {seen == list(range(50, 0, -1))}")
    good = base64.urlsafe_b64encode(b"[31]").rstrip(b"=").decode()
    cases = {
        "default limit": {},
        "limit=100": {"limit": "100"},
        "limit=0": {"limit": "0"},
        "limit=101": {"limit": "101"},
        "limit=abc (FastAPI's 422)": {"limit": "abc"},
        "limit=-1": {"limit": "-1"},
        "limit=1.5": {"limit": "1.5"},
        f"good cursor {good}": {"before": good},
        "cursor 'nope'": {"before": "nope"},
        "tampered cursor (char flipped)": {"before": "WzMx" + "XQ"},
        "cursor with = padding": {"before": good + "="},
        "cursor [1.5]": {"before": base64.urlsafe_b64encode(b"[1.5]").decode().rstrip("=")},
        "cursor [1,2]": {"before": base64.urlsafe_b64encode(b"[1,2]").decode().rstrip("=")},
        "cursor ['a']": {"before": base64.urlsafe_b64encode(b'["a"]').decode().rstrip("=")},
        "cursor 2**63": {"before": base64.urlsafe_b64encode(b"[9223372036854775808]").decode().rstrip("=")},
        "cursor 201 chars": {"before": "A" * 201},
        "cursor non-utf8": {"before": base64.urlsafe_b64encode(b"\xff\xfe").decode().rstrip("=")},
        "cursor [ 31] (other spelling)": {"before": base64.urlsafe_b64encode(b"[ 31]").decode().rstrip("=")},
        "empty before=": {"before": ""},
    }
    for label, q in cases.items():
        r = c.get("/api/v1/test/numbers", params=q)
        items = r.json().get("items") if r.status_code == 200 else None
        summary = f"{len(items)} items, first={items[0]['n'] if items else None}" if items is not None else r.text[:160]
        out(f"  [{label}] {r.status_code} {headers_ok(r)} {summary}")

    out("-- cache")
    a = c.get("/api/v1/test/cached?k=1")
    b = c.get("/api/v1/test/cached?k=1")
    d = c.get("/api/v1/test/cached?k=2")
    out(f"  [cached k=1 x2, k=2] {a.status_code},{b.status_code},{d.status_code} cache-control={a.headers.get('cache-control')!r}/{b.headers.get('cache-control')!r} answers={a.json()['answer']},{b.json()['answer']},{d.json()['answer']} {headers_ok(b)}")
    f = c.get("/api/v1/test/cached?fail=true")
    out(f"  [cached fail] {f.status_code} cache-control={f.headers.get('cache-control')!r} body={f.text}")
    q = c.get("/api/v1/test/query")
    out(f"  [uncached route] cache-control={q.headers.get('cache-control')!r}")

    out("-- unhandled error")
    show("GET /api/v1/test/boom", c.get("/api/v1/test/boom"))
    show("GET /api/v1/test/missing (ApiError)", c.get("/api/v1/test/missing"))
    show("POST /api/v1/test/query (405)", c.post("/api/v1/test/query"))

    out("-- statement timeout (5 s) and pool (5)")
    timed(c, "pg_sleep(8) -> statement timeout", "/api/v1/vt/sleep", params={"s": "8"})
    timed(c, "pg_sleep(1) -> fine", "/api/v1/vt/sleep", params={"s": "1"})
    results: list[str] = []

    def slow(i: int) -> None:
        cc = httpx.Client(base_url=c.base_url, trust_env=False, timeout=40)
        t = time.monotonic()
        r = cc.get("/api/v1/vt/sleep", params={"s": "4"}, headers={"X-Real-IP": f"198.51.100.{100 + i}"})
        results.append(f"{r.status_code}@{time.monotonic() - t:.1f}s")
        cc.close()

    threads = [threading.Thread(target=slow, args=(i,)) for i in range(7)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    timed(c, "healthz while 5 connections are busy and 2 wait", "/healthz")
    for t in threads:
        t.join()
    out(f"  [7 concurrent pg_sleep(4) on pool 5] {sorted(results)}")

    out("-- database stopped (proxy killed)")
    stop_proxy(proxy)
    timed(c, "api query, db down (stream_id cached)", "/api/v1/test/query")
    timed(c, "healthz, db down", "/healthz")
    proxy = start_proxy()
    timed(c, "api query, db back", "/api/v1/test/query")
    out("-- database silent")
    MODE.write_text("silent")
    timed(c, "healthz, silent", "/healthz")
    timed(c, "api query, silent (pooled conn, pre-ping)", "/api/v1/test/query")
    MODE.write_text("forward")
    time.sleep(0.5)
    timed(c, "api query, forwarding again", "/api/v1/test/query")

    out("-- SIGTERM with a request in flight (pg_sleep 3)")
    box: list[str] = []

    def inflight() -> None:
        cc = httpx.Client(base_url=c.base_url, trust_env=False, timeout=40)
        try:
            r = cc.get("/api/v1/vt/sleep", params={"s": "3"})
            box.append(f"{r.status_code}")
        except httpx.HTTPError as e:
            box.append(f"error {type(e).__name__}")

    t = threading.Thread(target=inflight)
    t.start()
    time.sleep(0.5)
    sigterm(p, "in-flight 3 s request")
    t.join()
    out("  in-flight request got:", box)
    c.close()
    stop_proxy(proxy)
    text = log_path.read_text()
    tb = text.count("Traceback")
    out("  log: tracebacks:", tb, "| 'secret detail' in log:", "secret detail" in text, "| password in log:", PW in text, "| 198.51.100 in log:", "198.51.100" in text)
    for line in text.splitlines():
        if "WARNING" in line or "ERROR" in line or "Finished" in line or "Shutting" in line or "Waiting" in line:
            out("   |", line[:220])


def phase_c() -> None:
    out("== Phase C: SIGTERM while a healthz waits on a silent database")
    proxy = start_proxy()
    p, c, _ = start_server(["-m", "engine", "web"], {}, "phaseC.log")
    MODE.write_text("silent")
    box: list[str] = []

    def inflight() -> None:
        cc = httpx.Client(base_url=c.base_url, trust_env=False, timeout=40)
        t0 = time.monotonic()
        try:
            r = cc.get("/healthz")
            box.append(f"{r.status_code} after {time.monotonic() - t0:.2f}s")
        except httpx.HTTPError as e:
            box.append(f"error {type(e).__name__}")

    t = threading.Thread(target=inflight)
    t.start()
    time.sleep(0.3)
    sigterm(p, "healthz in flight on a silent db")
    t.join()
    out("  in-flight healthz got:", box)
    c.close()
    MODE.write_text("forward")
    stop_proxy(proxy)


if __name__ == "__main__":
    which = sys.argv[5] if len(sys.argv) > 5 else "ABC"
    if "A" in which:
        phase_a()
    if "B" in which:
        phase_b()
    if "C" in which:
        phase_c()
    out(json.dumps({"done": True}))


def phase_d() -> None:
    out("== Phase D: launcher with WEB_RATE_LIMIT_BURST=1000 (re-run of the rate-limited checks)")
    proxy = start_proxy()
    p, c, log_path = start_server([str(V / "launch_probe.py")], {"WEB_RATE_LIMIT_BURST": "1000"}, "phaseD.log")
    show("POST /api/v1/test/query (405)", c.post("/api/v1/test/query"))
    show("OPTIONS /api/v1/test/query preflight", c.options("/api/v1/test/query", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}))
    show("GET /api/v1/test/numbers?limit=abc", c.get("/api/v1/test/numbers?limit=abc"))
    show("GET /api/v1/test/numbers?limit=1&limit=2 (repeated)", c.get("/api/v1/test/numbers?limit=1&limit=2"))
    timed(c, "pg_sleep(8) -> statement timeout", "/api/v1/vt/sleep", params={"s": "8"})
    timed(c, "pg_sleep(1) -> fine", "/api/v1/vt/sleep", params={"s": "1"})
    out("-- database goes silent while a query runs (pg_sleep 2, silent at +0.5 s)")
    box: list[str] = []

    def inflight() -> None:
        cc = httpx.Client(base_url=c.base_url, trust_env=False, timeout=45)
        t0 = time.monotonic()
        try:
            r = cc.get("/api/v1/vt/sleep", params={"s": "2"})
            box.append(f"{r.status_code} after {time.monotonic() - t0:.1f}s {r.text[:80]}")
        except httpx.HTTPError as e:
            box.append(f"client gave up: {type(e).__name__} after {time.monotonic() - t0:.1f}s")

    t = threading.Thread(target=inflight)
    t.start()
    time.sleep(0.5)
    MODE.write_text("silent")
    t.join()
    out("  in-flight request:", box)
    MODE.write_text("forward")
    time.sleep(1)
    timed(c, "api query after forwarding resumes", "/api/v1/test/query")
    sigterm(p, "end of phase D")
    c.close()
    stop_proxy(proxy)


if __name__ == "__main__" and len(sys.argv) > 5 and "D" in sys.argv[5]:
    phase_d()
