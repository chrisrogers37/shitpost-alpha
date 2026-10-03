"""Test-only: 127.0.0.1:<listen> -> 127.0.0.1:<target>, each server->client chunk delayed 20 ms."""
import asyncio, sys
LISTEN, TARGET, DELAY = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])

async def pipe(r, w, delay):
    try:
        while data := await r.read(65536):
            if delay:
                await asyncio.sleep(delay)
            w.write(data); await w.drain()
    except Exception:
        pass
    finally:
        w.close()

async def handle(cr, cw):
    sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    await asyncio.gather(pipe(cr, sw, 0), pipe(sr, cw, DELAY))

async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    print("proxy ready", flush=True)
    async with server:
        await server.serve_forever()
asyncio.run(main())
