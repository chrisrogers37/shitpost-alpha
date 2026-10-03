"""Test-only: N concurrent loops GET <path> for S seconds against 127.0.0.1:<port>; prints counts."""
import asyncio, sys, time, collections
import httpx
PORT, PATH, N, S = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), float(sys.argv[4])

async def main():
    counts = collections.Counter()
    stop = time.monotonic() + S
    limits = httpx.Limits(max_connections=N, max_keepalive_connections=N)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORT}", trust_env=False, limits=limits, timeout=30) as c:
        async def loop():
            while time.monotonic() < stop:
                try:
                    r = await c.get(PATH, headers={"X-Real-IP": "203.0.113.66"})
                    counts[r.status_code] += 1
                except httpx.HTTPError as e:
                    counts[type(e).__name__] += 1
        await asyncio.gather(*(loop() for _ in range(N)))
    print(dict(counts), flush=True)
asyncio.run(main())
