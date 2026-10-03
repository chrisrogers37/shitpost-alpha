"""A local TCP proxy to the dev Postgres that freezes on SIGUSR1: from then on it forwards
nothing in either direction and accepts new connections without answering (a stalled
network path or Neon proxy). Prints its port on stdout. Usage: freeze_proxy.py HOST PORT"""

import asyncio
import signal
import sys


async def main(host: str, port: int) -> None:
    frozen = asyncio.Event()

    async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
        try:
            while data := await src.read(65536):
                if frozen.is_set():
                    await asyncio.Event().wait()  # hold the bytes for ever
                dst.write(data)
                await dst.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            dst.transport.abort()

    async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        if frozen.is_set():
            await asyncio.Event().wait()
        ur, uw = await asyncio.open_connection(host, port)
        await asyncio.gather(pump(r, uw), pump(ur, w))

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, frozen.set)
    print(server.sockets[0].getsockname()[1], flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
