"""Probe: does create_app refuse a plain APIRouter whose route returns a bare dict with a price?"""
import asyncio
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from engine.web.app import create_app
from engine.web.settings import WebSettings
from tests.web.test_no_prices import price_fields

plain = APIRouter()

@plain.get("/raw")
async def raw() -> dict[str, float]:
    return {"close_price": 101.5}

app = create_app(WebSettings(database_url="postgresql://x@127.0.0.1:1/x"), [plain])  # type: ignore[list-item]
print("create_app accepted a plain APIRouter")
print("no-prices walk finds:", price_fields(app))

async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/raw")
        print("GET /api/v1/raw ->", r.status_code, r.text)
asyncio.run(main())
