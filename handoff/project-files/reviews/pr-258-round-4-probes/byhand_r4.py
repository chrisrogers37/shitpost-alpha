"""By-hand checks of `python -m engine` from the read-only 99fe7bb checkout, default timings.

Never prints a URL or password. Writes copy logs under review-258-r4/byhand-logs/.
Usage: byhand_r4.py DBNAME STEP [ARGS]
"""

import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg

CHECKOUT_ENGINE = Path(
    "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/pr258-r4/engine"
)
LOGS = Path(__file__).resolve().parent / "byhand-logs"
LOGS.mkdir(exist_ok=True)
PY = "/home/user/engine-venv-258r4/bin/python"
FORBIDDEN = ("DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")

DEV = urlsplit(os.environ["DEV_DATABASE_URL"])
DEV_PASSWORD = DEV.password or ""


def url_for(db: str, *, netloc: str | None = None, query: str = "") -> str:
    return urlunsplit(DEV._replace(path="/" + db, netloc=netloc or DEV.netloc, query=query))


def env(engine_url: str, **extra: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k not in FORBIDDEN and not k.startswith("ENGINE_")}
    # PYTHONDONTWRITEBYTECODE keeps the read-only checkout untouched.
    return base | {"ENGINE_DATABASE_URL": engine_url, "PYTHONDONTWRITEBYTECODE": "1"} | extra


def cli(engine_url: str, *args: str, timeout: float = 120, **extra: str) -> tuple[int, str, str, float]:
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [PY, "-m", "engine", *args], cwd=CHECKOUT_ENGINE, env=env(engine_url, **extra),
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr, time.monotonic() - t0
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -999, out, err, time.monotonic() - t0


def start(engine_url: str, name: str) -> tuple[subprocess.Popen[bytes], Path]:
    log = LOGS / f"{name}.log"
    f = log.open("wb")
    p = subprocess.Popen(
        [PY, "-m", "engine", "run"], cwd=CHECKOUT_ENGINE, env=env(engine_url),
        stdout=f, stderr=subprocess.STDOUT,
    )
    return p, log


def q(db: str, sql: str, *params: object) -> list[tuple[object, ...]]:
    with psycopg.connect(url_for(db), autocommit=True) as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else []


def lease(db: str) -> tuple[str, float] | None:
    rows = q(db, "SELECT holder, extract(epoch FROM expires_at - now())::float FROM engine.engine_lease")
    return (str(rows[0][0]), float(rows[0][1])) if rows else None  # type: ignore[arg-type]


def holder_pid(holder: str) -> int:
    return int(holder.split(":")[1])


def wait_holder(db: str, want_pid: int | None = None, limit: float = 90) -> tuple[float, str]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        l = lease(db)
        if l and l[1] > 0 and (want_pid is None or holder_pid(l[0]) == want_pid):
            return time.monotonic() - t0, l[0]
        time.sleep(0.05)
    raise SystemExit(f"no holder (want {want_pid}) within {limit}s")


def wait_exit(p: subprocess.Popen[bytes], limit: float) -> float | None:
    t0 = time.monotonic()
    try:
        p.wait(limit)
        return time.monotonic() - t0
    except subprocess.TimeoutExpired:
        return None


def fmt(x: float | None) -> str:
    return "NO EXIT" if x is None else f"{x:.2f}s"


def leaks_in(text: str, extra: list[str] = ()) -> int:  # type: ignore[assignment]
    needles = [DEV_PASSWORD, *extra, "postgresql://", "postgres://", "postgresql+psycopg://"]
    return sum(text.count(n) for n in needles if n)


def check_logs(paths: list[Path], extra: list[str] = ()) -> None:  # type: ignore[assignment]
    for p in paths:
        text = p.read_text(errors="replace")
        print(f"  {p.name}: password/url hits={leaks_in(text, extra)} lines={len(text.splitlines())}")


def silent_port(host: str = "127.0.0.1") -> tuple[int, threading.Event]:
    """A local TCP port that accepts connections and never answers."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, 0))
    srv.listen(64)
    done = threading.Event()
    held: list[socket.socket] = []

    def serve() -> None:
        srv.settimeout(0.2)
        while not done.is_set():
            try:
                conn, _ = srv.accept()
                held.append(conn)
            except TimeoutError:
                pass
        for c in held:
            c.close()
        srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1], done


def step_basic(db: str) -> None:
    u = url_for(db)
    for args in (["status"], ["migrate"], ["status"], ["migrate"], ["status"]):
        rc, out, err, secs = cli(u, *args)
        print(f"$ python -m engine {' '.join(args)} -> rc={rc} ({secs:.2f}s)")
        for line in (out + err).splitlines():
            print("   ", line)
    print("stream_id rows:", q(db, "SELECT stream_id::text FROM engine.engine_meta"))


def step_copies(db: str) -> None:
    u = url_for(db)
    q(db, "DELETE FROM engine.engine_lease")
    a, alog = start(u, "copyA")
    time.sleep(1.0)
    b, blog = start(u, "copyB")
    took, holder = wait_holder(db)
    print(f"first holder {holder} after {took:.2f}s; A pid={a.pid} B pid={b.pid}")
    first, other = (a, b) if holder_pid(holder) == a.pid else (b, a)
    time.sleep(14.0)  # mid renew cycle
    l = lease(db)
    print(f"before kill -9: lease {l[0] if l else None} expires in {l[1] if l else 0:.2f}s")
    os.kill(first.pid, signal.SIGKILL)
    first.wait()
    took, holder = wait_holder(db, want_pid=other.pid, limit=90)
    print(f"kill -9 {first.pid}: other copy {other.pid} took the lease {took:.2f}s later")
    c, clog = start(u, "copyC")
    time.sleep(3.0)  # C is waiting for the lease
    t_term = time.monotonic()
    os.kill(other.pid, signal.SIGTERM)
    exited = wait_exit(other, 60)
    print(f"SIGTERM holder {other.pid}: exited after {fmt(exited)} rc={other.returncode}")
    took, holder = wait_holder(db, want_pid=c.pid, limit=60)
    print(f"  next copy {c.pid} held the lease {time.monotonic() - t_term:.2f}s after the SIGTERM")
    st = cli(u, "status")
    print("status while C holds:")
    for line in (st[1] + st[2]).splitlines():
        print("   ", line)
    time.sleep(2)
    os.kill(c.pid, signal.SIGTERM)
    exited = wait_exit(c, 60)
    print(f"SIGTERM last copy {c.pid}: exited after {fmt(exited)} rc={c.returncode}; lease row now {lease(db)}")
    check_logs([alog, blog, clog])
    for p in (alog, blog, clog):
        print(f"--- {p.name}")
        print(p.read_text()[-1500:])


def step_lock_held(db: str) -> None:
    """SIGTERM the holder while another session holds a lock on its lease row."""
    u = url_for(db)
    q(db, "DELETE FROM engine.engine_lease")
    e, elog = start(u, "copyE_lockheld")
    took, holder = wait_holder(db, want_pid=e.pid)
    print(f"E holds after {took:.2f}s")
    time.sleep(1.0)
    with psycopg.connect(u) as locker:
        locker.execute("UPDATE engine.engine_lease SET expires_at = expires_at")  # held open
        time.sleep(1.0)
        t0 = time.monotonic()
        os.kill(e.pid, signal.SIGTERM)
        exited = wait_exit(e, 45)
        print(f"SIGTERM holder E while its lease row is locked elsewhere: exited after {fmt(exited)} (cap 45s) rc={e.returncode}")
        print("lease row while still locked (holder, s left):", q(db, "SELECT holder, round(extract(epoch FROM expires_at - now())::numeric, 1) FROM engine.engine_lease"))
        locker.rollback()
        if exited is None:
            e.kill()
            e.wait()
    print("lease row after the locker rolled back:", lease(db))
    print(elog.read_text()[-1500:])


def step_silent(db: str) -> None:
    """SIGTERM a copy whose first connection goes to a port that accepts and never answers;
    then status and migrate against such a port."""
    port, done = silent_port()
    fake = url_for("x", netloc=f"verify_bh:BhSecret_7Qx@127.0.0.1:{port}")
    f, flog = start(fake, "copyF_silent")
    time.sleep(4.0)
    print("F still running after 4s:", f.poll() is None)
    os.kill(f.pid, signal.SIGTERM)
    exited = wait_exit(f, 45)
    print(f"SIGTERM F (first connection to a silent port): exited after {fmt(exited)} (cap 45s) rc={f.returncode}")
    if exited is None:
        f.kill()
        f.wait()
        print("  killed with SIGKILL")
    # Once more, with the SIGTERM landing 12 s in (after the first acquire gave up).
    g, glog = start(fake, "copyG_silent_late")
    time.sleep(12.0)
    os.kill(g.pid, signal.SIGTERM)
    exited = wait_exit(g, 45)
    print(f"SIGTERM G 12s in (silent port): exited after {fmt(exited)} rc={g.returncode}")
    if exited is None:
        g.kill()
        g.wait()
    done.set()
    check_logs([flog, glog], ["BhSecret_7Qx"])
    print(flog.read_text()[-1500:])
    print(glog.read_text()[-1500:])
    for cmd in ("status", "migrate"):
        port2, done2 = silent_port()
        fake2 = url_for("x", netloc=f"verify_bh:BhSecret_7Qx@127.0.0.1:{port2}")
        rc, out, err, secs = cli(fake2, cmd, timeout=60)
        text = out + err
        print(f"$ {cmd} against a silent port -> rc={rc} after {secs:.1f}s; lines={len(text.splitlines())} leaks={leaks_in(text, ['BhSecret_7Qx'])}")
        print("   ", text.strip()[-400:].replace("\n", "\n    "))
        done2.set()


def step_silent_extra(db: str) -> None:
    """Default timeout with a two-address host, and PGCONNECT_TIMEOUT."""
    p1, d1 = silent_port()
    p2, d2 = silent_port()
    two = url_for("x", netloc="verify_bh:BhSecret_7Qx@", query=f"host=127.0.0.1:{p1}&host=127.0.0.1:{p2}")
    rc, out, err, secs = cli(two, "status", timeout=90)
    text = out + err
    print(f"$ status, two silent addresses, default timeout -> rc={rc} after {secs:.1f}s; lines={len(text.splitlines())} leaks={leaks_in(text, ['BhSecret_7Qx'])}")
    print("   ", text.strip()[-300:].replace("\n", "\n    "))
    one = url_for("x", netloc=f"verify_bh:BhSecret_7Qx@127.0.0.1:{p1}")
    rc, out, err, secs = cli(one, "status", timeout=90, PGCONNECT_TIMEOUT="3")
    print(f"$ status, silent port, PGCONNECT_TIMEOUT=3 -> rc={rc} after {secs:.1f}s: {(out + err).strip()[-120:]}")
    d1.set()
    d2.set()


def step_n9(db: str) -> None:
    role = f"verify258d_pw_{secrets.token_hex(3)}"
    good_pw = "GoodPw_" + secrets.token_hex(6)
    bad_pw = "WrongPw_" + secrets.token_hex(6)
    q("postgres", f"CREATE ROLE {role} LOGIN PASSWORD '{good_pw}'")
    try:
        cases = {
            "refused port 127.0.0.1:1": url_for(db, netloc=f"{role}:{good_pw}@127.0.0.1:1"),
            "wrong password": url_for(db, netloc=f"{role}:{bad_pw}@127.0.0.1:{DEV.port or 5432}"),
            "right password (control)": url_for(db, netloc=f"{role}:{good_pw}@127.0.0.1:{DEV.port or 5432}"),
        }
        for label, u in cases.items():
            for cmd in (("status",) if "control" in label else ("migrate", "status")):
                rc, out, err, secs = cli(u, cmd, timeout=60)
                text = out + err
                print(f"[{label}] {cmd}: rc={rc} {secs:.2f}s lines={len(text.splitlines())} leaks={leaks_in(text, [good_pw, bad_pw])}")
                print("    " + text.strip().replace("\n", "\n    ")[:400])
    finally:
        q(db, f"DROP OWNED BY {role}")
        q("postgres", f"DROP ROLE {role}")
        print("role dropped:", q("postgres", "SELECT count(*) FROM pg_roles WHERE rolname = %s", role))




def start_proxy() -> tuple[subprocess.Popen[str], int]:
    p = subprocess.Popen(
        [PY, str(Path(__file__).resolve().parent / "freeze_proxy.py"), DEV.hostname or "localhost", str(DEV.port or 5432)],
        stdout=subprocess.PIPE, text=True,
    )
    assert p.stdout is not None
    return p, int(p.stdout.readline())


def step_frozen_holder(db: str, freeze_after: str, term_after: str) -> None:
    """A holder whose network path freezes `freeze_after` s after it takes the lease; SIGTERM
    `term_after` s after it took it. Another copy (direct path) waits for the lease."""
    q(db, "DELETE FROM engine.engine_lease")
    proxy, port = start_proxy()
    try:
        via = url_for(db, netloc=f"{DEV.username}:{DEV_PASSWORD}@127.0.0.1:{port}")
        h, hlog = start(via, f"copyH_frozen_{freeze_after}_{term_after}")
        took, holder = wait_holder(db, want_pid=h.pid)
        t_held = time.monotonic()
        b, blog = start(url_for(db), f"copyB_frozen_{freeze_after}_{term_after}")
        time.sleep(max(0.0, float(freeze_after) - (time.monotonic() - t_held)))
        os.kill(proxy.pid, signal.SIGUSR1)
        t_frozen = time.monotonic()
        time.sleep(max(0.0, float(term_after) - (time.monotonic() - t_held)))
        t_term = time.monotonic()
        print(f"H held; froze its network {t_frozen - t_held:.1f}s after; SIGTERM {t_term - t_held:.1f}s after; lease row {lease(db)}")
        os.kill(h.pid, signal.SIGTERM)
        exited = wait_exit(h, 60)
        print(f"  H exited {fmt(exited)} after SIGTERM rc={h.returncode}; lease row then {lease(db)}")
        if exited is None:
            h.kill()
            h.wait()
        took_b, _ = wait_holder(db, want_pid=b.pid, limit=60)
        print(f"  B (direct path) held the lease {time.monotonic() - t_term:.1f}s after the SIGTERM")
        os.kill(b.pid, signal.SIGTERM)
        print(f"  B exited {fmt(wait_exit(b, 30))} after SIGTERM")
        check_logs([hlog, blog])
        print(hlog.read_text()[-2500:])
    finally:
        proxy.kill()
        proxy.wait()


if __name__ == "__main__":
    db, step = sys.argv[1], sys.argv[2]
    globals()[f"step_{step}"](db, *sys.argv[3:])
