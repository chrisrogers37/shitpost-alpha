"""Tests for API key authentication (api/dependencies.py verify_api_key).

Covers:
- Requests without API key are rejected when API_KEY is configured
- Requests with wrong API key are rejected
- Requests with correct API key succeed
- All authenticated routers are protected (feed, prices, calibration, echoes)
- Health endpoints remain public
- Telegram endpoints remain public (separate auth)
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


TEST_API_KEY = "test-secret-key-abc123"


def _make_client():
    """Create a TestClient after patching settings — must be called inside a patch context."""
    # Re-import to pick up patched settings in dependency resolution
    from api.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# API key enforcement — feed router
# ---------------------------------------------------------------------------


def test_feed_rejects_missing_api_key(mock_execute_query):
    """GET /api/feed/latest returns 403 when API_KEY is set but no key provided."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/feed/latest")
    assert response.status_code == 403


def test_feed_rejects_wrong_api_key(mock_execute_query):
    """GET /api/feed/latest returns 403 when the wrong API key is provided."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/feed/latest", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 403


def test_feed_accepts_correct_api_key(client, mock_execute_query):
    """GET /api/feed/latest succeeds with the correct API key (or no key configured)."""
    # With API_KEY unset (default in test conftest), requests pass through
    mock_execute_query.return_value = ([], [])
    response = client.get("/api/feed/latest")
    assert response.status_code in (200, 404)  # 404 = no posts, but auth passed


def test_feed_accepts_correct_api_key_when_configured(mock_execute_query):
    """GET /api/feed/latest succeeds with the correct API key."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        mock_execute_query.return_value = ([], [])
        response = client.get("/api/feed/latest", headers={"X-API-Key": TEST_API_KEY})
    assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# API key enforcement — prices router
# ---------------------------------------------------------------------------


def test_prices_rejects_missing_api_key(mock_execute_query):
    """GET /api/prices/SPY returns 403 when API_KEY is set but no key provided."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/prices/SPY")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# API key enforcement — calibration router
# ---------------------------------------------------------------------------


def test_calibration_rejects_missing_api_key(mock_execute_query):
    """GET /api/calibration/curve returns 403 when API_KEY is set but no key provided."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/calibration/curve")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# API key enforcement — echoes router
# ---------------------------------------------------------------------------


def test_echoes_rejects_missing_api_key(mock_execute_query):
    """GET /api/echoes/for-prediction/1 returns 403 when API_KEY is set but no key provided."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/echoes/for-prediction/1")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Health and Telegram remain public
# ---------------------------------------------------------------------------


def test_health_endpoint_always_public(mock_execute_query):
    """GET /api/health is always accessible regardless of API_KEY config."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        client = _make_client()
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_telegram_webhook_not_gated_by_api_key(mock_execute_query):
    """POST /telegram/webhook is not gated by API key auth."""
    with patch("api.dependencies.settings") as mock_settings:
        mock_settings.API_KEY = TEST_API_KEY
        mock_settings.TELEGRAM_WEBHOOK_SECRET = None
        with patch("api.routers.telegram.settings", mock_settings):
            client = _make_client()
            with patch("notifications.telegram_bot.process_update"):
                response = client.post(
                    "/telegram/webhook",
                    json={"update_id": 1, "message": {"text": "hi"}},
                )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Open mode — no API_KEY configured
# ---------------------------------------------------------------------------


def test_open_mode_allows_all_requests(client, mock_execute_query):
    """When API_KEY is not configured, all API requests are allowed."""
    mock_execute_query.return_value = ([], [])
    # These should all pass auth (may 404 on empty data, but not 403)
    for path in ["/api/feed/latest", "/api/health"]:
        response = client.get(path)
        assert response.status_code != 403, f"{path} returned 403 in open mode"
