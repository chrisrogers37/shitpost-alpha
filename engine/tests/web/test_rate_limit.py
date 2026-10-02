import logging

import pytest
from pydantic import ValidationError
from starlette.types import Scope

from engine.web.ratelimit import TokenBuckets, edge_address, socket_address
from engine.web.settings import WebSettings
from tests.web.conftest import NO_DATABASE, MakeClient
from tests.web.routes import FakeClock


def scope(*headers: tuple[str, str], client: tuple[str, int] | None = ("10.0.0.1", 1)) -> Scope:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers]
    return {"type": "http", "headers": raw, "client": client}


def test_the_default_header_is_railways_x_real_ip() -> None:
    settings = NO_DATABASE
    assert (settings.client_ip_header.lower(), settings.trusted_hops) == ("x-real-ip", 1)
    assert edge_address(scope(("X-Real-IP", "198.51.100.7")), "X-Real-IP", 1) == "198.51.100.7"


def test_the_address_is_the_edges_entry_never_one_the_visitor_wrote() -> None:
    edge_saw = "198.51.100.7"
    for forged in ("", "203.0.113.99", "203.0.113.99, 192.0.2.1", "garbage"):
        header = f"{forged}, {edge_saw}" if forged else edge_saw
        assert edge_address(scope(("X-Forwarded-For", header)), "x-forwarded-for", 1) == edge_saw
    # The visitor sends its own header line; the edge appends its line after it.
    two_lines = scope(("X-Forwarded-For", "203.0.113.99"), ("X-Forwarded-For", edge_saw))
    assert edge_address(two_lines, "X-Forwarded-For", 1) == edge_saw
    # Two trusted proxies: the edge's entry is second from the right.
    chain = scope(("X-Forwarded-For", f"203.0.113.99, {edge_saw}, 10.1.2.3"))
    assert edge_address(chain, "X-Forwarded-For", 2) == edge_saw


def test_an_absent_short_or_unusable_header_gives_no_edge_address() -> None:
    assert edge_address(scope(), "X-Real-IP", 1) is None
    assert edge_address(scope(("X-Real-IP", "not-an-ip")), "X-Real-IP", 1) is None
    assert edge_address(scope(("X-Real-IP", "198.51.100.7:51234")), "X-Real-IP", 1) is None
    short = scope(("X-Forwarded-For", "198.51.100.7"))
    assert edge_address(short, "X-Forwarded-For", 2) is None
    assert socket_address(scope()) == "10.0.0.1"
    assert socket_address(scope(client=None)) is None


def test_ipv6_visitors_count_per_64() -> None:
    a, b = "2001:db8:1:2::1", "2001:db8:1:2:ffff::9"
    key_a = edge_address(scope(("X-Real-IP", a)), "X-Real-IP", 1)
    assert key_a == edge_address(scope(("X-Real-IP", b)), "X-Real-IP", 1) == "2001:db8:1:2::/64"
    other = edge_address(scope(("X-Real-IP", "2001:db8:1:3::1")), "X-Real-IP", 1)
    assert other != key_a
    mapped = edge_address(scope(("X-Real-IP", "::ffff:198.51.100.7")), "X-Real-IP", 1)
    assert mapped == "198.51.100.7"


def test_a_bucket_allows_the_burst_then_the_rate() -> None:
    clock = FakeClock()
    buckets = TokenBuckets(per_minute=60, burst=3, clock=clock)
    assert [buckets.take("a") for _ in range(3)] == [0, 0, 0]
    assert buckets.take("a") == pytest.approx(1.0)
    assert buckets.take("b") == 0  # another key, another bucket
    clock.now += 1
    assert buckets.take("a") == 0
    assert buckets.take("a") == pytest.approx(1.0)


def test_the_bucket_table_stays_bounded() -> None:
    clock = FakeClock()
    buckets = TokenBuckets(per_minute=60, burst=3, max_buckets=100, clock=clock)
    for n in range(500):
        buckets.take(f"k{n}")
    assert len(buckets) == 100
    clock.now += 3  # every bucket has refilled: idle ones go on the next request
    buckets.take("new")
    assert len(buckets) == 1


async def test_two_addresses_get_separate_buckets(make_client: MakeClient, web_url: str) -> None:
    settings = WebSettings(database_url=web_url, rate_limit_per_minute=1, rate_limit_burst=2)
    client = make_client(settings=settings)

    def visitor(address: str) -> dict[str, str]:
        return {"X-Real-IP": address}

    for _ in range(2):
        assert (await client.get("/x", headers=visitor("198.51.100.1"))).status_code == 404
    limited = await client.get("/api/v1/x", headers=visitor("198.51.100.1"))
    assert limited.status_code == 429
    assert limited.json() == {"error": {"code": "rate_limited", "message": "Too many requests"}}
    assert 1 <= int(limited.headers["retry-after"]) <= 60
    assert limited.headers["access-control-allow-origin"] == "*"
    assert limited.headers["access-control-expose-headers"] == "Retry-After"
    assert limited.headers["x-content-type-options"] == "nosniff"
    page = await client.get("/x", headers=visitor("198.51.100.1"))
    assert (page.status_code, page.text) == (429, "Too many requests")

    assert (await client.get("/x", headers=visitor("198.51.100.2"))).status_code == 404


async def test_a_forged_forwarded_for_entry_cannot_change_buckets(
    make_client: MakeClient, web_url: str
) -> None:
    settings = WebSettings(
        database_url=web_url,
        rate_limit_per_minute=1,
        rate_limit_burst=2,
        client_ip_header="X-Forwarded-For",
    )
    client = make_client(settings=settings)
    edge_saw = "198.51.100.1"
    statuses = [
        (
            await client.get("/x", headers={"X-Forwarded-For": f"203.0.113.{n}, {edge_saw}"})
        ).status_code
        for n in range(4)
    ]
    assert statuses == [404, 404, 429, 429]


async def test_healthz_is_never_limited(make_client: MakeClient, web_url: str) -> None:
    settings = WebSettings(database_url=web_url, rate_limit_per_minute=1, rate_limit_burst=1)
    client = make_client(settings=settings)
    for _ in range(5):
        assert (await client.get("/healthz")).status_code == 200
    assert (await client.get("/x")).status_code == 404
    assert (await client.get("/x")).status_code == 429


async def test_a_remote_request_without_the_header_is_counted_by_socket_with_a_warning(
    make_client: MakeClient, web_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    settings = WebSettings(database_url=web_url, rate_limit_per_minute=1, rate_limit_burst=2)
    client = make_client(settings=settings)  # one socket address, as behind a proxy
    caplog.set_level(logging.WARNING, logger="engine.web.ratelimit")
    unusable = {"X-Real-IP": "198.51.100.1:51234"}
    statuses = [(await client.get("/x", headers=unusable)).status_code for _ in range(2)]
    other_visitor = await client.get("/x")  # no header at all: the same socket, same bucket
    assert [*statuses, other_visitor.status_code] == [404, 404, 429]
    warnings = [r.getMessage() for r in caplog.records]
    assert len(warnings) == 1  # at most one every WARN_EVERY_SECONDS
    assert "no usable X-Real-IP entry" in warnings[0]
    assert "198.51.100" not in warnings[0] and "203.0.113" not in warnings[0]


async def test_a_local_request_without_the_header_is_not_warned_about(
    make_client: MakeClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="engine.web.ratelimit")
    for host in ("127.0.0.1", "::1"):
        assert (await make_client(client=(host, 1)).get("/x")).status_code == 404
    assert not caplog.records


@pytest.mark.parametrize("header", ["X-Real-Ip ", "X-Réal-IP", "X Real IP", ""])
def test_the_header_setting_must_be_a_header_name(header: str) -> None:
    with pytest.raises(ValidationError, match="client_ip_header"):
        WebSettings(database_url="postgresql://unused", client_ip_header=header)
