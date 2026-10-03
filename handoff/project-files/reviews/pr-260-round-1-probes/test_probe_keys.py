"""Review probes (PR 3): can the Alpaca keys reach an exception text or a log line?

Talks only to a local server on 127.0.0.1 (DATA_URL monkeypatched); fake keys only.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

import pytest

import engine.market.alpaca as alpaca_mod
from engine.market.alpaca import Alpaca, AlpacaError
from tests.market_helpers import market_settings

FAKE_ID = "PKPROBEFAKEID00000001"
FAKE_SECRET = "probe-fake-secret-0123456789"
BODY = b'{"bars": {"BTC/USD": []}, "next_page_token": null}'


@pytest.fixture
async def local_server() -> AsyncIterator[str]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(BODY)).encode()
                + b"\r\n\r\n"
                + BODY
            )
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.close()
    await server.wait_closed()


@pytest.mark.parametrize("bad", ["\n", " ", "\r\n"])
async def test_probe_a_key_with_stray_whitespace_leaks_into_the_error(
    local_server: str, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setattr(alpaca_mod, "DATA_URL", local_server)
    settings = market_settings(alpaca_key_id=FAKE_ID, alpaca_secret_key=FAKE_SECRET + bad)
    async with Alpaca(settings) as alpaca:
        try:
            await alpaca.coin_bars(
                "BTC/USD",
                "1Day",
                *(alpaca_mod.datetime(2024, 1, d, tzinfo=alpaca_mod.UTC) for d in (2, 3)),
            )
        except AlpacaError as exc:
            text = str(exc)
            print(f"\nwhitespace {bad!r}: AlpacaError: {text}")
            assert FAKE_SECRET in text, "secret not in error text"
            return
        except Exception as exc:  # anything else
            print(f"\nwhitespace {bad!r}: {type(exc).__name__}: {exc}")
            assert FAKE_SECRET not in str(exc)
            return
    print(f"\nwhitespace {bad!r}: request succeeded")


async def test_probe_debug_logging_of_a_real_request_shows_no_key(
    local_server: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(alpaca_mod, "DATA_URL", local_server)
    settings = market_settings(alpaca_key_id=FAKE_ID, alpaca_secret_key=FAKE_SECRET)
    async with Alpaca(settings) as alpaca:
        await alpaca.coin_bars(
            "BTC/USD",
            "1Day",
            *(alpaca_mod.datetime(2024, 1, d, tzinfo=alpaca_mod.UTC) for d in (2, 3)),
        )
    messages = [r.getMessage() for r in caplog.records]
    print(f"\n{len(messages)} log records, e.g. {messages[:6]}")
    assert not [m for m in messages if FAKE_SECRET in m or FAKE_ID in m]
