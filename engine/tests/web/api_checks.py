"""Test-only: assertions shared by the web tests."""

from httpx import Response

SECURITY_HEADERS = {  # the brief's values, written out so a change to policy.py shows
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def assert_security_headers(response: Response) -> None:
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value, name
