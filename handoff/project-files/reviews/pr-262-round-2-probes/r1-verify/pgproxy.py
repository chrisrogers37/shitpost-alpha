"""Test-only TCP forwarder: 127.0.0.1:<listen> -> 127.0.0.1:5432.
Mode file (argv[2]) holds 'forward' or 'silent' (accept, never answer, stop forwarding).
Killing this process stands in for stopping Postgres: every connection drops, new ones are refused."""
import asyncio, sys
from pathlib import Path

LISTEN = int(sys.argv[1]); MODE = Path(sys.argv[2])

def mode() -> str:
    try:
        return MODE.read_text().strip()
    except OSError:
        return "forward"

async def pipe(r, w):
    try:
        while data := await r.read(65536):
            while mode() == "silent":
                await asyncio.sleep(0.05)
            w.write(data); await w.drain()
    except Exception:
        pass
    finally:
        w.close()

async def handle(cr, cw):
    if mode() == "silent":
        await asyncio.sleep(3600); return
    sr, sw = await asyncio.open_connection("127.0.0.1", 5432)
    await asyncio.gather(pipe(cr, sw), pipe(sr, cw))

async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    print("proxy ready", flush=True)
    async with server:
        await server.serve_forever()

asyncio.run(main())
