"""Telegram webhook router."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shit.logging import get_service_logger

logger = get_service_logger("api_telegram")

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram updates. Always returns 200 to prevent retries."""
    try:
        update = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    try:
        from notifications.telegram_bot import process_update

        process_update(update)
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")

    return JSONResponse({"ok": True})


@router.get("/telegram/health")
def telegram_health():
    """Health check for the alert system."""
    health: dict = {"ok": True, "service": "telegram_alerts"}
    try:
        from notifications.db import get_subscription_stats, get_last_alert_check
        from notifications.telegram_sender import get_bot_token

        stats = get_subscription_stats()
        last_check = get_last_alert_check()
        has_token = bool(get_bot_token())

        health["bot_configured"] = has_token
        health["subscribers"] = {
            "total": stats.get("total", 0),
            "active": stats.get("active", 0),
        }
        health["last_alert_check"] = last_check.isoformat() if last_check else None
        health["total_alerts_sent"] = stats.get("total_alerts_sent", 0)
    except Exception as e:
        health["ok"] = False
        health["error"] = str(e)
        logger.error(f"Health check failed: {e}")

    status_code = 200 if health["ok"] else 503
    return JSONResponse(health, status_code=status_code)
