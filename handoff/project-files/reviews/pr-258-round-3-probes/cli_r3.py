"""R3 CLI probe: one-line errors for migrate/status, never the password or URL.
Uses a throwaway database for the wrong-password and statement-timeout cases."""
import os, secrets, subprocess, sys
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

PY = "/home/user/engine-venv-258r3/bin/python"
ENG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine")
dev = make_url(os.environ["DEV_DATABASE_URL"]).set(drivername="postgresql")
real_pw = dev.password
FAKE = "S3cretPw_r3probe"

def admin(stmt, db="postgres"):
    with psycopg.connect(dev.set(database=db).render_as_string(hide_password=False), autocommit=True) as c:
        c.execute(stmt)

def run(label, url, command):
    base = {k: v for k, v in os.environ.items() if not k.startswith("ENGINE_") and k != "DATABASE_URL"}
    base.update(ENGINE_DATABASE_URL=url, ENGINE_WEB_ROLE="absent_r3", PYTHONPATH=ENG)
    r = subprocess.run([PY, "-m", "engine", command], cwd=ENG, env=base, capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    pw = make_url(url).password or ""
    leaks = []
    for name, s in (("password", pw), ("real password", real_pw), ("url", url)):
        if s and s in out:
            leaks.append(name)
    shown = r.stderr.strip().splitlines()
    shown = [l.replace(real_pw, "<REAL-PW>") if real_pw else l for l in shown]
    print(f"[{label}] {command}: exit={r.returncode} stderr_lines={len(shown)} leaks={leaks or 'none'}")
    for l in (shown[:2] if len(shown) <= 2 else shown[:1] + ["...", shown[-1]]):
        print("     ", l[:230])

name = f"engine_r3cli_{secrets.token_hex(4)}"
admin(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
try:
    good = dev.set(database=name)
    cases = {
        "bad host": good.set(host="no-such-host.invalid", password=FAKE),
        "bad port": good.set(port=1, password=FAKE),
        "wrong password": good.set(password=FAKE),
        "missing db": good.set(database="no_such_db_r3"),
    }
    for label, u in cases.items():
        for command in ("status", "migrate"):
            run(label, u.render_as_string(hide_password=False), command)
    # an '@' in the password, not percent-encoded (a common copy-paste mistake)
    raw = f"postgresql://{good.username}:pa55@word{FAKE}@{good.host}:{good.port}/{name}"
    for command in ("status", "migrate"):
        run("unescaped @ in password", raw, command)
    # a reachable database that cancels a statement (role/database statement_timeout)
    admin(sql.SQL("ALTER DATABASE {} SET statement_timeout = '1ms'").format(sql.Identifier(name)))
    for command in ("migrate",):
        run("statement timeout", good.render_as_string(hide_password=False), command)
finally:
    admin(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
