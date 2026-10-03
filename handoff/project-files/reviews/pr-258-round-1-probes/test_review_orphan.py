import os, signal, subprocess, sys, time
from pathlib import Path

import psycopg

from engine.settings import Settings
from tests.test_processes import env, wait_for

PROJECT = Path(__file__).resolve().parent.parent


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # zombie counts as dead
    with open(f"/proc/{pid}/stat") as f:
        return f.read().split()[2] != "Z"


def test_heavy_child_dies_with_kill_9_parent(migrated: Settings, tmp_path: Path) -> None:
    url = migrated.database_url
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE TABLE job_pids (pid int NOT NULL)")
    log = (tmp_path / "copy.log").open("wb")
    p = subprocess.Popen([sys.executable, "-m", "tests.review_probe_heavy"], cwd=PROJECT,
                         env=env(migrated), stdout=log, stderr=subprocess.STDOUT)
    try:
        def child() -> int | None:
            with psycopg.connect(url) as conn:
                r = conn.execute("SELECT pid FROM job_pids").fetchall()
            return int(r[0][0]) if r else None
        pid = wait_for(child, timeout=20)
        assert isinstance(pid, int) and alive(pid)
        p.send_signal(signal.SIGKILL)
        p.wait()
        t0 = time.monotonic()
        while alive(pid) and time.monotonic() - t0 < 5:
            time.sleep(0.1)
        print("heavy child alive after parent kill -9:", alive(pid), "waited", round(time.monotonic() - t0, 2))
        assert not alive(pid)
    finally:
        p.kill(); p.wait(); log.close()
