"""Test-only: assertions shared by the web tests."""

from httpx import Response

from engine.web.policy import SECURITY_HEADERS


def assert_security_headers(response: Response) -> None:
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value, name
