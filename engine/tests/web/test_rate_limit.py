import pytest
from starlette.types import Scope

from engine.web.ratelimit import TokenBuckets, client_address
from engine.web.settings import WebSettings
from tests.web.conftest import MakeClient
from tests.web.routes import FakeClock


def scope(*headers: tuple[str, str], client: tuple[str, int] | None = ("10.0.0.1", 1)) -> Scope:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers]
    return {"type": "http", "headers": raw, "client": client}


def test_the_default_header_is_railways_x_real_ip() -> None:
    settings = WebSettings(database_url="postgresql://x")
    assert (settings.client_ip_header.lower(), settings.trusted_hops) == ("x-real-ip", 1)
    assert client_address(scope(("X-Real-IP", "198.51.100.7")), "X-Real-IP", 1) == "198.51.100.7"


def test_the_address_is_the_edges_entry_never_one_the_visitor_wrote() -> None:
    edge_saw = "198.51.100.7"
    for forged in ("", "203.0.113.99", "203.0.113.99, 192.0.2.1", "garbage"):
        header = f"{forged}, {edge_saw}" if forged else edge_saw
        assert client_address(scope(("X-Forwarded-For", header)), "x-forwarded-for", 1) == edge_saw
    # The visitor sends its own header line; the edge appends its line after it.
    two_lines = scope(("X-Forwarded-For", "203.0.113.99"), ("X-Forwarded-For", edge_saw))
    assert client_address(two_lines, "X-Forwarded-For", 1) == edge_saw
    # Two trusted proxies: the edge's entry is second from the right.
    chain = scope(("X-Forwarded-For", f"203.0.113.99, {edge_saw}, 10.1.2.3"))
    assert client_address(chain, "X-Forwarded-For", 2) == edge_saw


def test_without_a_usable_header_the_socket_address_counts() -> None:
    assert client_address(scope(), "X-Real-IP", 1) == "10.0.0.1"
    assert client_address(scope(("X-Real-IP", "not-an-ip")), "X-Real-IP", 1) == "10.0.0.1"
    short = scope(("X-Forwarded-For", "198.51.100.7"))
    assert client_address(short, "X-Forwarded-For", 2) == "10.0.0.1"
    assert client_address(scope(client=None), "X-Real-IP", 1) == "unknown"


def test_ipv6_visitors_count_per_64() -> None:
    a, b = "2001:db8:1:2::1", "2001:db8:1:2:ffff::9"
    key_a = client_address(scope(("X-Real-IP", a)), "X-Real-IP", 1)
    assert key_a == client_address(scope(("X-Real-IP", b)), "X-Real-IP", 1) == "2001:db8:1:2::/64"
    other = client_address(scope(("X-Real-IP", "2001:db8:1:3::1")), "X-Real-IP", 1)
    assert other != key_a
    mapped = client_address(scope(("X-Real-IP", "::ffff:198.51.100.7")), "X-Real-IP", 1)
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
