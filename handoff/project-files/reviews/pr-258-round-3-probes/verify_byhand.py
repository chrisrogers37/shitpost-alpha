"""By-hand checks of `python -m engine` from the read-only f4194b7 checkout, default timings.

Never prints a URL or password. Writes copy logs under verify-258-r3/byhand-logs/.
Usage: byhand.py DBNAME STEP
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
    "/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/pr258-r3/engine"
)
LOGS = Path(__file__).resolve().parent / "byhand-logs"
LOGS.mkdir(exist_ok=True)
PY = "/home/user/engine-venv-258r3/bin/python"
FORBIDDEN = ("DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")

DEV = urlsplit(os.environ["DEV_DATABASE_URL"])
DEV_PASSWORD = DEV.password or ""


def url_for(db: str, *, netloc: str | None = None) -> str:
    return urlunsplit(DEV._replace(path="/" + db, netloc=netloc or DEV.netloc))


def env(engine_url: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k not in FORBIDDEN and not k.startswith("ENGINE_")}
    return base | {"ENGINE_DATABASE_URL": engine_url, "PYTHONDONTWRITEBYTECODE": "1"}


def cli(engine_url: str, *args: str, timeout: float = 120) -> tuple[int, str, str, float]:
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [PY, "-m", "engine", *args], cwd=CHECKOUT_ENGINE, env=env(engine_url),
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr, time.monotonic() - t0
    except subprocess.TimeoutExpired as e:
        return -999, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), \
            (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""), time.monotonic() - t0


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


def check_secrets(paths: list[Path], extra: list[str] = ()) -> None:  # type: ignore[assignment]
    needles = [DEV_PASSWORD, *extra]
    for p in paths:
        text = p.read_text(errors="replace")
        hits = {n: text.count(n) for n in needles if n}
        urls = text.count("postgresql://") + text.count("postgres://") + text.count("postgresql+psycopg://")
        print(f"  {p.name}: password hits={sum(hits.values())} url hits={urls} lines={len(text.splitlines())}")


def blackhole() -> tuple[int, threading.Event]:
    """A local TCP port that accepts connections and never answers."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
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
    a, alog = start(u, "copyA")
    time.sleep(1.0)
    b, blog = start(u, "copyB")
    took, holder = wait_holder(db)
    print(f"first holder {holder} after {took:.2f}s; A pid={a.pid} B pid={b.pid}")
    first, other = (a, b) if holder_pid(holder) == a.pid else (b, a)
    time.sleep(14.0)  # mid renew cycle
    l = lease(db)
    print(f"before kill -9: lease {l[0] if l else None} expires in {l[1] if l else 0:.2f}s")
    print("holders running jobs/workers? registry from build_registry():",
          subprocess.run([PY, "-c", "from engine.registry import build_registry as b; r=b(); print(sorted(r.jobs), sorted(r.workers))"],
                         cwd=CHECKOUT_ENGINE, env=env(u), capture_output=True, text=True).stdout.strip())
    t_kill = time.monotonic()
    os.kill(first.pid, signal.SIGKILL)
    first.wait()
    took, holder = wait_holder(db, want_pid=other.pid, limit=90)
    print(f"kill -9 {first.pid}: other copy {other.pid} took the lease {took:.2f}s later")
    c, clog = start(u, "copyC")
    time.sleep(3.0)  # C is waiting for the lease
    t_term = time.monotonic()
    os.kill(other.pid, signal.SIGTERM)
    exited = wait_exit(other, 60)
    print(f"SIGTERM holder {other.pid}: exited after {exited if exited is None else round(exited, 2)}s rc={other.returncode}")
    took, holder = wait_holder(db, want_pid=c.pid, limit=60)
    print(f"  next copy {c.pid} held the lease {time.monotonic() - t_term:.2f}s after the SIGTERM")
    st = cli(u, "status")
    print("status while C holds:")
    for line in (st[1] + st[2]).splitlines():
        print("   ", line)
    time.sleep(2)
    os.kill(c.pid, signal.SIGTERM)
    exited = wait_exit(c, 60)
    print(f"SIGTERM last copy {c.pid}: exited after {exited if exited is None else round(exited, 2)}s rc={c.returncode}; lease row now {lease(db)}")
    check_secrets([alog, blog, clog])
    for p in (alog, blog, clog):
        print(f"--- {p.name}")
        print(p.read_text()[-1500:])


def step_lock_first(db: str) -> None:
    """SIGTERM a copy whose first acquire is blocked on a locked lease row."""
    u = url_for(db)
    with psycopg.connect(u) as stuck:
        stuck.execute("DELETE FROM engine.engine_lease")
        stuck.execute("INSERT INTO engine.engine_lease VALUES ('engine', 'frozen', now() - interval '1 hour', now() - interval '1 second')")
        stuck.commit()
        stuck.execute("UPDATE engine.engine_lease SET expires_at = expires_at")  # held open
        d, dlog = start(u, "copyD_lockfirst")
        time.sleep(4.0)
        print("D blocked? lease:", q(db, "SELECT holder FROM engine.engine_lease"), "running:", d.poll() is None)
        os.kill(d.pid, signal.SIGTERM)
        exited = wait_exit(d, 60)
        print(f"SIGTERM D (first acquire blocked on a row lock): exited after {exited if exited is None else round(exited, 2)}s rc={d.returncode}")
        if exited is None:
            d.kill(); d.wait()
        stuck.rollback()
    q(db, "DELETE FROM engine.engine_lease")
    print(dlog.read_text()[-1200:])


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
        print(f"SIGTERM holder E while its lease row is locked elsewhere: exited after {exited if exited is None else round(exited, 2)}s (cap 45s)")
        locker.rollback()
        if exited is None:
            exited2 = wait_exit(e, 30)
            print(f"  after the lock was released: exited {exited2 if exited2 is None else round(exited2, 2)}s later (total {time.monotonic() - t0:.2f}s) rc={e.returncode}")
            if exited2 is None:
                e.kill(); e.wait()
    print("lease row after:", lease(db))
    print(elog.read_text()[-1500:])


def step_blackhole(db: str) -> None:
    """SIGTERM a copy whose first connection goes to a port that accepts but never answers."""
    port, done = blackhole()
    fake = url_for("x", netloc=f"verify_bh:BhSecret_7Qx@127.0.0.1:{port}")
    f, flog = start(fake, "copyF_blackhole")
    time.sleep(4.0)
    print("F still running after 4s:", f.poll() is None)
    os.kill(f.pid, signal.SIGTERM)
    exited = wait_exit(f, 45)
    print(f"SIGTERM F (first connection to a silent port): exited after {exited if exited is None else round(exited, 2)}s (cap 45s) rc={f.returncode}")
    if exited is None:
        f.kill(); f.wait()
        print("  killed with SIGKILL")
    done.set()
    check_secrets([flog], ["BhSecret_7Qx"])
    print(flog.read_text()[-2500:])
    for cmd in ("status", "migrate"):
        port2, done2 = blackhole()
        fake2 = url_for("x", netloc=f"verify_bh:BhSecret_7Qx@127.0.0.1:{port2}")
        rc, out, err, secs = cli(fake2, cmd, timeout=40)
        print(f"$ {cmd} against a silent port -> rc={rc} after {secs:.1f}s (cap 40s); lines={len((out + err).splitlines())}")
        print("   ", (out + err)[-400:].replace("\n", "\n    "))
        done2.set()


def step_n9(db: str, role: str, good_pw: str) -> None:
    bad_pw = "WrongPw_" + secrets.token_hex(4)
    cases = {
        "refused port 127.0.0.1:1": url_for(db, netloc=f"{role}:{good_pw}@127.0.0.1:1"),
        "unreachable host 127.0.0.254:5432": url_for(db, netloc=f"{role}:{good_pw}@127.0.0.254:5432"),
        "wrong password": url_for(db, netloc=f"{role}:{bad_pw}@127.0.0.1:{DEV.port or 5432}"),
        "right password (control)": url_for(db, netloc=f"{role}:{good_pw}@127.0.0.1:{DEV.port or 5432}"),
    }
    for label, u in cases.items():
        for cmd in (("status",) if "control" in label else ("migrate", "status")):
            rc, out, err, secs = cli(u, cmd, timeout=60)
            text = out + err
            leaks = {n: text.count(n) for n in (good_pw, bad_pw, DEV_PASSWORD, "postgresql://", "postgresql+psycopg://", u)}
            print(f"[{label}] {cmd}: rc={rc} {secs:.2f}s lines={len(text.splitlines())} leaks={sum(leaks.values())}")
            print("    " + text.strip().replace("\n", "\n    ")[:600])
    # failed `run`: 6 s each, then SIGTERM, scan the log
    for label in ("refused port 127.0.0.1:1", "wrong password"):
        p, log = start(cases[label], "run_" + label.split()[0] + "_" + label.split()[1])
        time.sleep(6.0)
        os.kill(p.pid, signal.SIGTERM)
        exited = wait_exit(p, 30)
        text = log.read_text()
        leaks = {n: text.count(n) for n in (good_pw, bad_pw, DEV_PASSWORD, "postgresql://", "postgresql+psycopg://")}
        print(f"[run, {label}] SIGTERM exit after {exited if exited is None else round(exited, 2)}s rc={p.returncode} lines={len(text.splitlines())} leaks={sum(leaks.values())}")
        print("    " + text.strip().replace("\n", "\n    ")[:1500])
        if exited is None:
            p.kill(); p.wait()


if __name__ == "__main__":
    db, step = sys.argv[1], sys.argv[2]
    globals()[f"step_{step}"](db, *sys.argv[3:])
