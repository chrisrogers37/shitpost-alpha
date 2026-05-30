"""Tests for Telegram webhook secret token verification (api/routers/telegram.py).

Covers:
- Requests without secret are rejected when TELEGRAM_WEBHOOK_SECRET is configured
- Requests with wrong secret are rejected
- Requests with correct secret succeed
- When no secret is configured, all requests pass (backward-compatible)
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


WEBHOOK_SECRET = "test-webhook-secret-xyz789"


def _make_client():
    from api.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Secret enforcement
# ---------------------------------------------------------------------------


def test_webhook_rejects_missing_secret(mock_execute_query):
    """POST /telegram/webhook returns 403 when secret is configured but not provided."""
    with patch("api.routers.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = WEBHOOK_SECRET
        client = _make_client()
        response = client.post(
            "/telegram/webhook",
            json={"update_id": 1, "message": {"text": "/start"}},
        )
    assert response.status_code == 403
    assert response.json()["ok"] is False


def test_webhook_rejects_wrong_secret(mock_execute_query):
    """POST /telegram/webhook returns 403 when the wrong secret is provided."""
    with patch("api.routers.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = WEBHOOK_SECRET
        client = _make_client()
        response = client.post(
            "/telegram/webhook",
            json={"update_id": 1, "message": {"text": "/start"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
    assert response.status_code == 403


def test_webhook_accepts_correct_secret(mock_execute_query):
    """POST /telegram/webhook returns 200 when the correct secret is provided."""
    with patch("api.routers.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = WEBHOOK_SECRET
        client = _make_client()
        with patch("notifications.telegram_bot.process_update"):
            response = client.post(
                "/telegram/webhook",
                json={"update_id": 1, "message": {"text": "/start"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
            )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_webhook_open_when_no_secret_configured(client, mock_execute_query):
    """POST /telegram/webhook accepts all requests when no secret is configured."""
    with patch("notifications.telegram_bot.process_update"):
        response = client.post(
            "/telegram/webhook",
            json={"update_id": 1, "message": {"text": "/start"}},
        )
    assert response.status_code == 200
    assert response.json()["ok"] is True


# ---------------------------------------------------------------------------
# Secret check does not interfere with other error handling
# ---------------------------------------------------------------------------


def test_webhook_invalid_json_after_secret_check(mock_execute_query):
    """Invalid JSON still returns 400 after passing the secret check."""
    with patch("api.routers.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = WEBHOOK_SECRET
        client = _make_client()
        response = client.post(
            "/telegram/webhook",
            content=b"not json{{{",
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
            },
        )
    assert response.status_code == 400
