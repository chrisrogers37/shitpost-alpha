"""Print every statement the engine's default Lease sends (take, renew, release), compiled
for Postgres with its parameters, so two checkouts can be diffed. No database."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.dialects import postgresql

from engine.lease import Lease


class Result:
    def first(self) -> Any:
        return ("me",)


class Conn:
    def __init__(self, out: list[str]) -> None:
        self.out = out

    async def execute(self, stmt: Any, params: Any = None) -> Result:
        compiled = stmt.compile(dialect=postgresql.dialect())
        self.out.append(f"{compiled}\n  params={dict(compiled.params) | (params or {})}")
        return Result()


class Db:
    def __init__(self) -> None:
        self.out: list[str] = []

    @asynccontextmanager
    async def begin(self):  # type: ignore[no-untyped-def]
        yield Conn(self.out)


async def main() -> None:
    db = Db()
    lease = Lease(db, "me", ttl=30.0, renew=10.0)  # type: ignore[arg-type]
    print("held:", await lease.acquire())
    await lease.release()
    for line in db.out:
        print(line)


asyncio.run(main())
