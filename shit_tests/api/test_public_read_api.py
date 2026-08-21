"""Tests for the read-only data API access model.

The feed/prices/calibration/echoes routers serve the public predictions
dashboard and are public by design: no API-key gate is applied, per-IP rate
limiting is the abuse control. These tests pin that contract so that
re-introducing an auth gate on a read router fails loudly.
"""

from fastapi.routing import APIRoute

READ_PREFIXES = ("/api/feed", "/api/prices", "/api/calibration", "/api/echoes")


def test_read_routes_have_no_route_dependency():
    """Read routers carry no route-level dependency (public by design).

    Structural pin covering calibration/echoes too (whose bodies need DB
    fixtures): re-adding `dependencies=[Depends(verify_api_key)]` to any read
    router makes this fail. The routes have no route-level dependency today, so
    this also flags an unrelated `Depends(...)` added later — update the test if
    a legitimate one is introduced.
    """
    from api.main import app

    covered = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(READ_PREFIXES):
            deps = route.dependant.dependencies
            assert deps == [], f"{route.path} has route dependencies: {deps}"
            covered.add(next(p for p in READ_PREFIXES if route.path.startswith(p)))
    assert covered == set(READ_PREFIXES), (
        f"missing read routers: {set(READ_PREFIXES) - covered}"
    )


def test_feed_reachable_without_api_key(client, mock_execute_query):
    """A keyless request to a read route passes (no 401/403); the endpoint runs."""
    mock_execute_query.return_value = ([], [])
    for path in ("/api/feed/at?offset=0", "/api/prices/SPY"):
        response = client.get(path)
        assert response.status_code not in (401, 403), (
            f"{path} returned {response.status_code}; read routes must be public"
        )


def test_verify_api_key_helper_is_removed():
    """The fail-open verify_api_key gate is gone; do not reintroduce it."""
    import api.dependencies as deps

    assert not hasattr(deps, "verify_api_key")


def test_cors_does_not_send_credentials():
    """CORS uses no credentials, so a wildcard dev origin cannot be reflected back."""
    from starlette.middleware.cors import CORSMiddleware

    from api.main import app

    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "CORS middleware not configured"
    assert cors[0].kwargs["allow_credentials"] is False
