"""Verify-only: create or drop a throwaway database on DEV_DATABASE_URL's server and write
its URL to a file (never printed)."""
import os
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

dev = make_url(os.environ["DEV_DATABASE_URL"])
admin = dev.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
action, name = sys.argv[1], sys.argv[2]
assert name.startswith("verify263_"), name
with psycopg.connect(admin, autocommit=True) as conn:
    if action == "create":
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        url = dev.set(database=name).render_as_string(hide_password=False)
        with open(sys.argv[3], "w") as f:
            f.write(url)
        os.chmod(sys.argv[3], 0o600)
    elif action == "drop":
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    elif action == "role":
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))
    elif action == "droprole":
        db = sys.argv[3]
        url = dev.set(database=db).render_as_string(hide_password=False)
        with psycopg.connect(url, autocommit=True) as c2:
            c2.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
        conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))
print(action, name, "done")
