import pytest

from engine.web.errors import ApiError
from engine.web.paging import decode_cursor, encode_cursor, take_page
from tests.web.conftest import MakeClient
from tests.web.routes import ProbeRoutes


def test_a_cursor_round_trips_and_is_url_safe() -> None:
    for key in [(1,), (2**63 - 1, -(2**63)), (1_700_000_000_000_000, 42)]:
        cursor = encode_cursor(key)
        assert cursor.isascii() and not set(cursor) & set("+/=")
        assert decode_cursor(cursor, len(key)) == key


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "not base64!",
        encode_cursor((1,)) + "=",  # another spelling of a good cursor
        encode_cursor((1, 2)),  # wrong size
        "WyJhIl0",  # ["a"]
        "W3RydWVd",  # [true]
        "WzEuNV0",  # [1.5]
        encode_cursor((2**63,)),  # past bigint
        "e30",  # {}
    ],
)
def test_a_bad_cursor_is_a_bad_request(cursor: str) -> None:
    with pytest.raises(ApiError) as caught:
        decode_cursor(cursor, 1)
    assert caught.value.code == "bad_request"


def test_take_page_gives_a_cursor_only_when_more_rows_exist() -> None:
    assert take_page([5, 4, 3], 2, lambda n: (n,)) == ([5, 4], encode_cursor((4,)))
    assert take_page([5, 4], 2, lambda n: (n,)) == ([5, 4], None)
    assert take_page([], 2, lambda n: (n,)) == ([], None)


async def test_a_list_pages_through_every_row(make_client: MakeClient) -> None:
    client = make_client(ProbeRoutes().router)
    seen: list[int] = []
    params: dict[str, str | int] = {"limit": 20}
    while True:
        body = (await client.get("/api/v1/test/numbers", params=params)).json()
        assert set(body) == {"stream_id", "items", "next_before"}
        seen += [item["n"] for item in body["items"]]
        if body["next_before"] is None:
            break
        params["before"] = body["next_before"]
    assert seen == list(range(50, 0, -1))

    default = (await client.get("/api/v1/test/numbers")).json()
    assert len(default["items"]) == 20


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"limit": "x"}, {"before": "nope"}, {"before": "x" * 201}],
)
async def test_bad_paging_parameters_are_a_400(
    make_client: MakeClient, params: dict[str, str | int]
) -> None:
    response = await make_client(ProbeRoutes().router).get("/api/v1/test/numbers", params=params)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "bad_request"
    assert ("before" if "before" in params else "limit") in error["message"]


async def test_the_cache_serves_a_second_hit_without_building_and_expires(
    make_client: MakeClient,
) -> None:
    routes = ProbeRoutes()
    client = make_client(routes.router)

    first = await client.get("/api/v1/test/cached?a=1")
    assert first.headers["cache-control"] == "public, max-age=5"
    second = await client.get("/api/v1/test/cached?a=1")
    assert second.json() == first.json() and second.headers["cache-control"] == "public, max-age=5"
    assert routes.builds == 1

    await client.get("/api/v1/test/cached?a=2")  # another query string, another entry
    assert routes.builds == 2

    routes.clock.now += 5
    assert (await client.get("/api/v1/test/cached?a=1")).json()["answer"] == 3


async def test_the_cache_keeps_only_200s(make_client: MakeClient) -> None:
    routes = ProbeRoutes()
    client = make_client(routes.router)
    for _ in range(2):
        response = await client.get("/api/v1/test/cached?fail=true")
        assert response.status_code == 404 and "cache-control" not in response.headers
    assert routes.builds == 2
