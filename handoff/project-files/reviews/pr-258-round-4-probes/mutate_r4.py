"""Round-4 mutation harness for PR 258 at 99fe7bb. Applies one mutation at a time to the
review copy, runs the named tests, restores the file with git and checks the tree is clean.
Usage: mutate_r4.py NAME [NAME ...]  (or "all")."""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENG = ROOT / "engine"
PY = "/home/user/engine-venv-258r4/bin/python"
OUT = ROOT / "out" / "mutations"
OUT.mkdir(parents=True, exist_ok=True)

LEASE, DB, RT, SCH, STG, CLI, ENV = (
    "engine/lease.py",
    "engine/db.py",
    "engine/runtime.py",
    "engine/scheduler.py",
    "engine/stages.py",
    "engine/cli.py",
    "engine/migrations/env.py",
)
COMMITTED_LEASE = ["tests/test_lease.py"]
COMMITTED_RT = ["tests/test_runtime.py"]

MUTATIONS: dict[str, tuple[list[tuple[str, str, str]], list[str]]] = {
    "S1-async-connect-timeout": (
        [(DB, "create_async_engine(\n        sqlalchemy_url(url), pool_pre_ping=True, connect_args=_connect_args(url), **pool",
          "create_async_engine(\n        sqlalchemy_url(url), pool_pre_ping=True, **pool")],
        ["tests/test_db.py", "tests/test_processes.py",
         "tests/test_runtime.py::test_a_copy_stopped_while_the_database_never_answers_stops_at_once"],
    ),
    "S1-sync-connect-timeout": (
        [(DB, "create_engine(\n        sqlalchemy_url(url), pool_pre_ping=True, connect_args=_connect_args(url), **pool",
          "create_engine(\n        sqlalchemy_url(url), pool_pre_ping=True, **pool")],
        ["tests/test_db.py", "tests/test_processes.py"],
    ),
    "S1-migration-env-connect-timeout": (
        [(ENV, "from sqlalchemy import text", "from sqlalchemy import create_engine, text"),
         (ENV, "from engine.db import make_sync_engine", "from engine.db import sqlalchemy_url"),
         (ENV, "pin_search_path(make_sync_engine(url, poolclass=NullPool))",
          "pin_search_path(create_engine(sqlalchemy_url(url), poolclass=NullPool))")],
        ["tests/test_db.py", "tests/test_processes.py", "tests/test_migrate.py"],
    ),
    "S1-release-never-held-return": (
        [(LEASE, "        if not self._ever_held:\n            return\n", "")],
        COMMITTED_LEASE + COMMITTED_RT,
    ),
    "S1-release-timeout": (
        [(LEASE, "            async with asyncio.timeout(self._answer_within):\n                if self._renewal",
          "            if True:\n                if self._renewal")],
        COMMITTED_LEASE + COMMITTED_RT,
    ),
    "S1-release-bound-statements": (
        [(LEASE, "                async with self._db.begin() as conn:\n                    await self._bound_statements(conn)\n                    await conn.execute(\n                        delete(",
          "                async with self._db.begin() as conn:\n                    await conn.execute(\n                        delete(")],
        COMMITTED_LEASE + COMMITTED_RT,
    ),
    "N2-release-raise-if-cancelling": (
        [(LEASE, "        except (SQLAlchemyError, OSError, TimeoutError) as exc:\n            raise_if_cancelling()\n",
          "        except (SQLAlchemyError, OSError, TimeoutError) as exc:\n")],
        COMMITTED_LEASE + COMMITTED_RT + ["tests/test_r4_probes.py::test_release_reraises_a_cancel_the_driver_turned_into_an_error"],
    ),
    "S2-pool-timeout-permanent": (
        [(DB, "if isinstance(exc, DataError | IntegrityError | ProgrammingError):",
          "if isinstance(exc, DataError | IntegrityError | ProgrammingError | __import__('sqlalchemy').exc.TimeoutError):")],
        ["tests/test_db.py", "tests/test_scheduler.py"],
    ),
    "S2-nothing-permanent": (
        [(SCH, "                if is_permanent(exc):", "                if False:")],
        ["tests/test_db.py", "tests/test_scheduler.py"],
    ),
    "N1-backslashreplace": (
        [(DB, '    return text.encode("utf-8", "backslashreplace").decode()[:limit]', "    return text[:limit]")],
        ["tests/test_db.py", "tests/test_scheduler.py", "tests/test_stages.py"],
    ),
    "N3-always-could-not-reach": (
        [(CLI, '        what = "could not reach" if reason.startswith("connection") else "error from"',
          '        what = "could not reach"')],
        ["tests/test_processes.py"],
    ),
    "N3-no-empty-fallback": (
        [(CLI, "        reason = (str(exc.orig or exc).splitlines() or [type(exc).__name__])[0]",
          "        reason = str(exc.orig or exc).splitlines()[0]")],
        ["tests/test_processes.py"],
    ),
    "N5-record-raise-if-cancelling": (
        [(SCH, "            except (SQLAlchemyError, OSError) as exc:\n                raise_if_cancelling()\n                if is_permanent(exc):",
          "            except (SQLAlchemyError, OSError) as exc:\n                if is_permanent(exc):")],
        ["tests/test_scheduler.py"],
    ),
    "N5-execute-raise-if-cancelling": (
        [(SCH, '            raise_if_cancelling()  # interrupted, not failed: the row stays "running"\n', "")],
        ["tests/test_scheduler.py"],
    ),
    "N5-hold-raise-if-cancelling": (
        [(RT, '    except Exception as exc:\n        raise_if_cancelling()\n        log.exception("engine work failed; stepping down")',
          '    except Exception as exc:\n        log.exception("engine work failed; stepping down")')],
        COMMITTED_RT + ["tests/test_processes.py",
                        "tests/test_r4_probes.py::test_cancelling_the_copy_is_not_reported_as_an_engine_failure"],
    ),
    "N5-unknown-stage-scan-every-pass": (
        [(STG, "            if not self._checked_unknown:\n                await self._log_unknown_stages(conn)",
          "            if True:\n                await self._log_unknown_stages(conn)")],
        ["tests/test_stages.py"],
    ),
    "N5-renewal-cadence-flat-sleep": (
        [(LEASE, "await asyncio.sleep(max(0.0, self._renewed_at + self._renew - loop.time()))",
          "await asyncio.sleep(self._renew)")],
        COMMITTED_LEASE + COMMITTED_RT + ["tests/test_processes.py",
         "tests/test_r4_probes.py::test_renewals_start_every_renew_seconds_even_when_each_answer_is_slow"],
    ),
    "R2-S1-keep-awaits-cancelled-renewal": (
        [(LEASE, "                self._renewal.cancel()  # without waiting: the driver can take 10 s to give up",
          "                self._renewal.cancel()\n                await asyncio.wait({self._renewal})  # mutated")],
        COMMITTED_LEASE,
    ),
}


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def apply(edits: list[tuple[str, str, str]]) -> None:
    for rel, old, new in edits:
        path = ENG / rel
        source = path.read_text()
        assert source.count(old) == 1, f"{rel}: expected exactly one match for {old[:60]!r}"
        path.write_text(source.replace(old, new))


def restore(edits: list[tuple[str, str, str]]) -> None:
    for rel in {rel for rel, _, _ in edits}:
        r = git("checkout", "--", f"engine/{rel}")
        assert r.returncode == 0, r.stderr
    clean = git("diff", "--quiet")
    assert clean.returncode == 0, "tracked files not clean after restore"


def run(name: str) -> str:
    edits, targets = MUTATIONS[name]
    apply(edits)
    try:
        env = {k: v for k, v in os.environ.items()
               if k not in ("DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(ENG)
        started = time.monotonic()
        try:
            r = subprocess.run(
                [PY, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-s", *targets],
                cwd=ENG, env=env, capture_output=True, text=True, errors="replace", timeout=900,
            )
            out, rc = r.stdout + r.stderr, r.returncode
        except subprocess.TimeoutExpired as exc:
            out, rc = str(exc.stdout or "") + "\nHARNESS TIMEOUT", -9
        took = time.monotonic() - started
    finally:
        restore(edits)
    (OUT / f"{name}.txt").write_text(out)
    summary = [line for line in out.splitlines() if re.search(r"\d+ (passed|failed)", line)]
    failed = sorted({m.group(1) for m in re.finditer(r"^FAILED (\S+)", out, re.M)})
    verdict = "CAUGHT" if failed or rc not in (0,) else "NOT CAUGHT"
    line = f"{name}: {verdict} rc={rc} {took:.0f}s | {summary[-1] if summary else '?'}"
    for f in failed:
        line += f"\n    FAILED {f}"
    return line


if __name__ == "__main__":
    names = list(MUTATIONS) if sys.argv[1:] == ["all"] else sys.argv[1:]
    for name in names:
        print(run(name), flush=True)
