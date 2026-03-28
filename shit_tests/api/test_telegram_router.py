"""Tests for the Telegram webhook router (api/routers/telegram.py).

Covers:
- POST /telegram/webhook
- GET /telegram/health
- Error handling

NOTE: The telegram router uses lazy imports (inside function bodies), so
mock targets point to the source modules, not api.routers.telegram.
"""

from unittest.mock import patch
from datetime import datetime


# ---------------------------------------------------------------------------
# POST /telegram/webhook — valid update returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_valid_update(client, mock_execute_query):
    """POST /telegram/webhook with a valid Telegram update returns 200 {"ok": true}."""
    update_payload = {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {"id": 789, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 789, "type": "private"},
            "date": 1711000000,
            "text": "/start",
        },
    }

    with patch("notifications.telegram_bot.process_update") as mock_process:
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_process.assert_called_once_with(update_payload)


# ---------------------------------------------------------------------------
# POST /telegram/webhook — invalid JSON returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_invalid_json(client, mock_execute_query):
    """POST /telegram/webhook with invalid JSON returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert "Invalid JSON" in response.json()["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — process_update exception still returns 200
# ---------------------------------------------------------------------------


def test_telegram_webhook_process_update_exception_returns_200(
    client, mock_execute_query
):
    """Even if process_update raises, the webhook returns 200 to prevent Telegram retries."""
    update_payload = {"update_id": 999, "message": {"text": "/crash"}}

    with patch(
        "notifications.telegram_bot.process_update",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post("/telegram/webhook", json=update_payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# GET /telegram/health — returns health info
# ---------------------------------------------------------------------------


def test_telegram_health_happy_path(client, mock_execute_query):
    """GET /telegram/health returns full health info when everything works."""
    mock_stats = {"total": 50, "active": 45, "total_alerts_sent": 1200}
    mock_last_check = datetime(2026, 3, 25, 14, 0, 0)

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch(
            "notifications.db.get_last_alert_check", return_value=mock_last_check
        ):
            with patch(
                "notifications.telegram_sender.get_bot_token",
                return_value="valid-token",
            ):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "telegram_alerts"
    assert data["bot_configured"] is True
    assert data["subscribers"]["total"] == 50
    assert data["subscribers"]["active"] == 45
    assert data["total_alerts_sent"] == 1200
    assert data["last_alert_check"] is not None


# ---------------------------------------------------------------------------
# GET /telegram/health — with missing bot token
# ---------------------------------------------------------------------------


def test_telegram_health_missing_bot_token(client, mock_execute_query):
    """GET /telegram/health reports bot_configured=False when token is missing."""
    mock_stats = {"total": 10, "active": 8, "total_alerts_sent": 50}

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch("notifications.db.get_last_alert_check", return_value=None):
            with patch(
                "notifications.telegram_sender.get_bot_token", return_value=None
            ):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["bot_configured"] is False
    assert data["last_alert_check"] is None


# ---------------------------------------------------------------------------
# GET /telegram/health — when DB stats fail returns 503
# ---------------------------------------------------------------------------


def test_telegram_health_db_failure_returns_503(client, mock_execute_query):
    """GET /telegram/health returns 503 when database calls raise."""
    with patch(
        "notifications.db.get_subscription_stats",
        side_effect=ConnectionError("DB unavailable"),
    ):
        response = client.get("/telegram/health")

    assert response.status_code == 503
    data = response.json()
    assert data["ok"] is False
    assert "error" in data
    assert "DB unavailable" in data["error"]


# ---------------------------------------------------------------------------
# POST /telegram/webhook — empty body returns 400
# ---------------------------------------------------------------------------


def test_telegram_webhook_empty_body(client, mock_execute_query):
    """POST /telegram/webhook with empty body returns 400."""
    response = client.post(
        "/telegram/webhook",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /telegram/health — last_alert_check is None when no alerts sent
# ---------------------------------------------------------------------------


def test_telegram_health_no_alerts_sent(client, mock_execute_query):
    """GET /telegram/health handles the case where no alerts have ever been sent."""
    mock_stats = {"total": 1, "active": 1, "total_alerts_sent": 0}

    with patch("notifications.db.get_subscription_stats", return_value=mock_stats):
        with patch("notifications.db.get_last_alert_check", return_value=None):
            with patch(
                "notifications.telegram_sender.get_bot_token", return_value="tok"
            ):
                response = client.get("/telegram/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["last_alert_check"] is None
    assert data["total_alerts_sent"] == 0
