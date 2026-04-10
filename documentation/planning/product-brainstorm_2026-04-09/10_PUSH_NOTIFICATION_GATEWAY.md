# Feature 10: Push Notification Gateway

**Status:** Planning
**Date:** 2026-04-09
**Priority:** High -- sub-second delivery to phone lock screens, major UX upgrade over Telegram

---

## Overview

Add native push notifications via Firebase Cloud Messaging (FCM) as a new channel in the existing multi-channel dispatcher. Users visiting the React frontend on desktop or mobile can opt-in to push notifications. On mobile, the app can be installed as a PWA (Progressive Web App) for a native-like notification experience on lock screens.

Notifications show the sentiment emoji, ticker(s), one-line thesis, and confidence level -- all within the first glance without opening the app.

---

## Motivation

### Current State: Telegram-Only Alerts

All alerts are delivered via Telegram. This works but has drawbacks:

1. **Latency** -- Telegram API calls take 1-5 seconds per message, and the worker polls every 2-5 seconds. Total latency: 5-25 seconds from prediction to alert.
2. **Requires Telegram** -- Users must have Telegram installed and a Telegram account
3. **No lock screen** -- Telegram notifications compete with all other Telegram chats; easily missed
4. **No web integration** -- The React dashboard at `shitpost-alpha-web-production.up.railway.app` has no notification capability

### Push Notification Advantages

- **Sub-second delivery** -- FCM delivers to devices within 200-500ms
- **Lock screen presence** -- Native OS notification with custom icon, title, body
- **Web + mobile** -- Works on Chrome, Firefox, Edge, Safari (17.4+), and as PWA on Android/iOS
- **No third-party account** -- Users just click "Allow notifications" in the browser
- **Deep link** -- Clicking the notification opens the dashboard to the relevant post

---

## Architecture

### High-Level Flow

```
Prediction Created
    |
    v
Notifications Worker (event_consumer.py)
    |
    +---> Telegram Channel (existing)
    |       |
    |       v
    |     send_telegram_message()
    |
    +---> FCM Channel (NEW)
            |
            v
          send_push_notification()
            |
            v
          Firebase Cloud Messaging API
            |
            +---> Chrome Web Push
            +---> Firefox Web Push
            +---> Safari Web Push
            +---> PWA (Android/iOS)
```

### Component Diagram

```
Frontend (React)                    Backend (FastAPI)              Firebase
+-------------------+              +-------------------+          +---------+
| Service Worker    |<--- push ----|  FCM Sender       |--- API ->| FCM     |
| (sw.js)           |              |  (fcm_sender.py)  |          | Service |
|                   |              |                   |          +---------+
| Push Manager      |--- POST --->|  /api/push/       |
| (subscribe API)   |    token    |  subscribe        |
|                   |              |  unsubscribe      |
| Notification UI   |              |                   |
| (permission flow) |              | push_subscriptions|
+-------------------+              | (DB table)        |
                                   +-------------------+
```

---

## Frontend Changes

### 1. Service Worker (`frontend/public/sw.js`)

The service worker runs in the background and receives push events even when the tab is closed.

```javascript
// frontend/public/sw.js

// Listen for push events from FCM
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};

  const title = data.title || 'Shitpost Alpha Alert';
  const options = {
    body: data.body || 'New prediction available',
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-72.png',
    tag: data.tag || 'shitpost-alert',       // Deduplicate notifications
    renotify: true,                           // Vibrate even if same tag
    data: {
      url: data.click_action || '/',
      prediction_id: data.prediction_id,
    },
    actions: [
      { action: 'view', title: 'View Post' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const url = event.notification.data?.url || '/';

  if (event.action === 'dismiss') {
    return;
  }

  // Focus existing tab or open new one
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        return clients.openWindow(url);
      })
  );
});
```

### 2. Service Worker Registration (`frontend/src/utils/pushNotifications.ts`)

```typescript
// frontend/src/utils/pushNotifications.ts

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;
const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * Check if push notifications are supported in this browser.
 */
export function isPushSupported(): boolean {
  return (
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

/**
 * Get current notification permission state.
 */
export function getPermissionState(): NotificationPermission {
  return Notification.permission;
}

/**
 * Request notification permission and subscribe to push.
 * Returns the subscription endpoint or null on failure.
 */
export async function subscribeToPush(): Promise<string | null> {
  if (!isPushSupported()) {
    console.warn('Push notifications not supported');
    return null;
  }

  // Request permission
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    console.warn('Notification permission denied');
    return null;
  }

  // Register service worker
  const registration = await navigator.serviceWorker.register('/sw.js');
  await navigator.serviceWorker.ready;

  // Subscribe to push
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  // Send subscription to backend
  const response = await fetch(`${API_BASE}/api/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      subscription: subscription.toJSON(),
      user_agent: navigator.userAgent,
    }),
  });

  if (!response.ok) {
    console.error('Failed to register push subscription');
    return null;
  }

  return subscription.endpoint;
}

/**
 * Unsubscribe from push notifications.
 */
export async function unsubscribeFromPush(): Promise<boolean> {
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return false;

  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return false;

  // Unsubscribe locally
  await subscription.unsubscribe();

  // Remove from backend
  await fetch(`${API_BASE}/api/push/unsubscribe`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint: subscription.endpoint }),
  });

  return true;
}

/**
 * Convert a VAPID key from base64 to Uint8Array.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return Uint8Array.from(rawData, (char) => char.charCodeAt(0));
}
```

### 3. Push Permission UI Component (`frontend/src/components/PushOptIn.tsx`)

```typescript
// frontend/src/components/PushOptIn.tsx

import { useState, useEffect } from 'react';
import {
  isPushSupported,
  getPermissionState,
  subscribeToPush,
  unsubscribeFromPush,
} from '../utils/pushNotifications';

export function PushOptIn() {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setSupported(isPushSupported());
    setPermission(getPermissionState());
  }, []);

  if (!supported) return null;

  const handleSubscribe = async () => {
    setLoading(true);
    const endpoint = await subscribeToPush();
    if (endpoint) {
      setPermission('granted');
    }
    setLoading(false);
  };

  const handleUnsubscribe = async () => {
    setLoading(true);
    await unsubscribeFromPush();
    setPermission('default');
    setLoading(false);
  };

  if (permission === 'denied') {
    return (
      <div style={{ padding: '8px 16px', color: '#94a3b8', fontSize: '13px' }}>
        Notifications blocked. Enable in browser settings.
      </div>
    );
  }

  if (permission === 'granted') {
    return (
      <button
        onClick={handleUnsubscribe}
        disabled={loading}
        style={{
          background: 'transparent',
          border: '1px solid #475569',
          color: '#94a3b8',
          padding: '6px 12px',
          borderRadius: '6px',
          cursor: 'pointer',
          fontSize: '13px',
        }}
      >
        {loading ? 'Updating...' : 'Notifications On (tap to disable)'}
      </button>
    );
  }

  return (
    <button
      onClick={handleSubscribe}
      disabled={loading}
      style={{
        background: '#1e40af',
        border: 'none',
        color: '#fff',
        padding: '8px 16px',
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '14px',
        fontWeight: 600,
      }}
    >
      {loading ? 'Enabling...' : 'Enable Alert Notifications'}
    </button>
  );
}
```

### 4. PWA Manifest (`frontend/public/manifest.json`)

The app already has a basic setup. Enhance the manifest for installability:

```json
{
  "name": "Shitpost Alpha",
  "short_name": "ShitpostA",
  "description": "Real-time trading signals from Truth Social",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#1e40af",
  "icons": [
    { "src": "/icons/icon-72.png", "sizes": "72x72", "type": "image/png" },
    { "src": "/icons/icon-96.png", "sizes": "96x96", "type": "image/png" },
    { "src": "/icons/icon-128.png", "sizes": "128x128", "type": "image/png" },
    { "src": "/icons/icon-144.png", "sizes": "144x144", "type": "image/png" },
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

---

## Backend Changes

### 1. FCM Sender Module (`notifications/fcm_sender.py`)

```python
# notifications/fcm_sender.py

"""
Firebase Cloud Messaging sender for Shitpost Alpha.

Uses the FCM HTTP v1 API with a service account for authentication.
Sends Web Push notifications to subscribed browsers and PWAs.
"""

import json
from typing import Any, Dict, Optional, Tuple

import google.auth.transport.requests
import google.oauth2.service_account
import requests

from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("fcm_sender")

FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

# Scopes required for FCM
_FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


def _get_access_token() -> Optional[str]:
    """Get an OAuth2 access token for the FCM API.

    Uses the service account credentials from settings.

    Returns:
        Access token string, or None on failure.
    """
    sa_key_json = settings.FIREBASE_SERVICE_ACCOUNT_KEY
    if not sa_key_json:
        logger.error("FIREBASE_SERVICE_ACCOUNT_KEY not configured")
        return None

    try:
        if isinstance(sa_key_json, str):
            sa_key = json.loads(sa_key_json)
        else:
            sa_key = sa_key_json

        credentials = google.oauth2.service_account.Credentials.from_service_account_info(
            sa_key, scopes=_FCM_SCOPES
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token

    except Exception as e:
        logger.error(f"Failed to get FCM access token: {e}")
        return None


def send_push_notification(
    subscription_token: str,
    title: str,
    body: str,
    icon: str = "/icons/icon-192.png",
    click_action: str = "/",
    tag: str = "shitpost-alert",
    data: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Optional[str]]:
    """Send a push notification via FCM.

    Args:
        subscription_token: The FCM registration token (from browser PushSubscription).
        title: Notification title.
        body: Notification body text.
        icon: URL to the notification icon.
        click_action: URL to open when notification is clicked.
        tag: Notification tag for deduplication.
        data: Optional custom data payload.

    Returns:
        Tuple of (success, error_message).
    """
    access_token = _get_access_token()
    if not access_token:
        return False, "Failed to get FCM access token"

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        return False, "FIREBASE_PROJECT_ID not configured"

    url = FCM_SEND_URL.format(project_id=project_id)

    message = {
        "message": {
            "token": subscription_token,
            "notification": {
                "title": title,
                "body": body,
            },
            "webpush": {
                "notification": {
                    "icon": icon,
                    "tag": tag,
                    "renotify": True,
                },
                "fcm_options": {
                    "link": click_action,
                },
            },
        }
    }

    if data:
        message["message"]["data"] = {k: str(v) for k, v in data.items()}

    try:
        response = requests.post(
            url,
            json=message,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if response.status_code == 200:
            return True, None
        elif response.status_code == 404:
            # Token is invalid/expired -- caller should clean up
            return False, "TOKEN_EXPIRED"
        else:
            error = response.json().get("error", {}).get("message", response.text)
            logger.error(f"FCM API error: {response.status_code} - {error}")
            return False, error

    except requests.exceptions.Timeout:
        return False, "FCM request timeout"
    except Exception as e:
        logger.error(f"FCM send error: {e}")
        return False, str(e)


def format_push_notification(alert: Dict[str, Any]) -> Dict[str, str]:
    """Format an alert dict into push notification title and body.

    Args:
        alert: Alert dict with prediction data.

    Returns:
        Dict with 'title', 'body', 'tag', 'click_action' keys.
    """
    sentiment = alert.get("sentiment", "neutral").upper()
    confidence = alert.get("confidence", 0)
    assets = alert.get("assets", [])
    thesis = alert.get("thesis", "")
    prediction_id = alert.get("prediction_id")

    # Sentiment emoji
    emoji = {"BULLISH": "\U0001f7e2", "BEARISH": "\U0001f534"}.get(sentiment, "\u26aa")

    # Title: emoji + sentiment + tickers
    assets_str = ", ".join(assets[:3])
    title = f"{emoji} {sentiment} - {assets_str}" if assets_str else f"{emoji} {sentiment}"
    if confidence:
        title += f" ({confidence:.0%})"

    # Body: thesis (truncated to fit lock screen)
    body = thesis[:120] if thesis else "New prediction available"

    # Deep link to the post
    click_action = f"/?prediction={prediction_id}" if prediction_id else "/"

    # Tag: deduplicate by prediction_id
    tag = f"prediction-{prediction_id}" if prediction_id else "shitpost-alert"

    return {
        "title": title,
        "body": body,
        "tag": tag,
        "click_action": click_action,
    }
```

### 2. Push Subscriptions Table

```sql
CREATE TABLE push_subscriptions (
    id SERIAL PRIMARY KEY,

    -- Subscription endpoint (unique identifier from browser)
    endpoint VARCHAR(500) UNIQUE NOT NULL,

    -- Web Push encryption keys (from PushSubscription.toJSON())
    p256dh VARCHAR(200) NOT NULL,        -- Public key
    auth VARCHAR(100) NOT NULL,          -- Auth secret

    -- FCM registration token (derived from endpoint for FCM API)
    fcm_token VARCHAR(500),

    -- Device metadata
    user_agent TEXT,
    device_type VARCHAR(20),             -- desktop, mobile, tablet
    browser VARCHAR(50),                 -- chrome, firefox, safari, edge

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    consecutive_errors INTEGER DEFAULT 0,
    last_error VARCHAR(500),

    -- Usage tracking
    last_push_at TIMESTAMP,
    pushes_sent_count INTEGER DEFAULT 0,

    -- Alert preferences (mirrors telegram_subscriptions structure)
    alert_preferences JSONB DEFAULT '{
        "min_confidence": 0.7,
        "assets_of_interest": [],
        "sentiment_filter": "all"
    }'::jsonb,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_push_subscriptions_active ON push_subscriptions (is_active)
    WHERE is_active = true;
CREATE INDEX idx_push_subscriptions_endpoint ON push_subscriptions (endpoint);
```

### SQLAlchemy Model

```python
# notifications/models.py (add to existing file)

class PushSubscription(Base, IDMixin, TimestampMixin):
    """Model for Web Push notification subscriptions."""

    __tablename__ = "push_subscriptions"

    endpoint = Column(String(500), unique=True, nullable=False, index=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    fcm_token = Column(String(500), nullable=True)

    user_agent = Column(Text, nullable=True)
    device_type = Column(String(20), nullable=True)  # desktop, mobile, tablet
    browser = Column(String(50), nullable=True)       # chrome, firefox, safari

    is_active = Column(Boolean, default=True, index=True)
    consecutive_errors = Column(Integer, default=0)
    last_error = Column(String(500), nullable=True)

    last_push_at = Column(DateTime, nullable=True)
    pushes_sent_count = Column(Integer, default=0)

    alert_preferences = Column(
        JSON,
        default=lambda: {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        },
    )
```

### 3. API Endpoints (`api/routers/push.py`)

```python
# api/routers/push.py

"""
Push notification subscription management endpoints.

POST /api/push/subscribe   -- Register a new push subscription
DELETE /api/push/unsubscribe -- Remove a push subscription
GET /api/push/status       -- Check subscription status for current endpoint
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from notifications.push_db import (
    create_push_subscription,
    delete_push_subscription,
    get_push_subscription_by_endpoint,
)
from shit.logging import get_service_logger

logger = get_service_logger("push_api")

router = APIRouter(prefix="/api/push", tags=["push"])


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionData(BaseModel):
    endpoint: str
    expirationTime: Optional[int] = None
    keys: PushSubscriptionKeys


class SubscribeRequest(BaseModel):
    subscription: PushSubscriptionData
    user_agent: Optional[str] = None


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/subscribe")
def subscribe(request: SubscribeRequest):
    """Register a push notification subscription.

    The frontend sends the PushSubscription object (from
    pushManager.subscribe()) to this endpoint for persistence.
    """
    sub = request.subscription
    user_agent = request.user_agent or ""

    # Parse device type from user agent
    device_type = _parse_device_type(user_agent)
    browser = _parse_browser(user_agent)

    success = create_push_subscription(
        endpoint=sub.endpoint,
        p256dh=sub.keys.p256dh,
        auth=sub.keys.auth,
        user_agent=user_agent,
        device_type=device_type,
        browser=browser,
    )

    if success:
        return {"status": "subscribed", "endpoint": sub.endpoint[:50] + "..."}
    else:
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.delete("/unsubscribe")
def unsubscribe(request: UnsubscribeRequest):
    """Remove a push notification subscription."""
    success = delete_push_subscription(endpoint=request.endpoint)
    if success:
        return {"status": "unsubscribed"}
    else:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/status")
def status(endpoint: str):
    """Check if an endpoint is subscribed."""
    sub = get_push_subscription_by_endpoint(endpoint)
    if sub:
        return {"subscribed": True, "is_active": sub.get("is_active", False)}
    return {"subscribed": False}


def _parse_device_type(user_agent: str) -> str:
    ua = user_agent.lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    elif "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "desktop"


def _parse_browser(user_agent: str) -> str:
    ua = user_agent.lower()
    if "firefox" in ua:
        return "firefox"
    elif "edg/" in ua:
        return "edge"
    elif "safari" in ua and "chrome" not in ua:
        return "safari"
    elif "chrome" in ua:
        return "chrome"
    return "unknown"
```

### 4. Push Database Operations (`notifications/push_db.py`)

```python
# notifications/push_db.py

"""Database operations for push notification subscriptions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from notifications.db import _execute_read, _execute_write, _row_to_dict, _rows_to_dicts
from shit.logging import get_service_logger

logger = get_service_logger("push_db")


def create_push_subscription(
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
    device_type: str = "desktop",
    browser: str = "unknown",
) -> bool:
    """Create or reactivate a push subscription."""
    # Upsert: if endpoint already exists, reactivate and update keys
    return _execute_write(
        """
        INSERT INTO push_subscriptions
            (endpoint, p256dh, auth, user_agent, device_type, browser,
             is_active, consecutive_errors, created_at, updated_at)
        VALUES
            (:endpoint, :p256dh, :auth, :user_agent, :device_type, :browser,
             true, 0, NOW(), NOW())
        ON CONFLICT (endpoint) DO UPDATE SET
            p256dh = EXCLUDED.p256dh,
            auth = EXCLUDED.auth,
            user_agent = EXCLUDED.user_agent,
            device_type = EXCLUDED.device_type,
            browser = EXCLUDED.browser,
            is_active = true,
            consecutive_errors = 0,
            updated_at = NOW()
        """,
        params={
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
            "device_type": device_type,
            "browser": browser,
        },
        context="create_push_subscription",
    )


def delete_push_subscription(endpoint: str) -> bool:
    """Deactivate a push subscription."""
    return _execute_write(
        """
        UPDATE push_subscriptions
        SET is_active = false, updated_at = NOW()
        WHERE endpoint = :endpoint
        """,
        params={"endpoint": endpoint},
        context="delete_push_subscription",
    )


def get_active_push_subscriptions() -> List[Dict[str, Any]]:
    """Get all active push subscriptions."""
    return _execute_read(
        """
        SELECT id, endpoint, p256dh, auth, fcm_token,
               device_type, browser, alert_preferences,
               pushes_sent_count
        FROM push_subscriptions
        WHERE is_active = true
            AND consecutive_errors < 5
        ORDER BY created_at ASC
        """,
        default=[],
        context="get_active_push_subscriptions",
    )


def get_push_subscription_by_endpoint(endpoint: str) -> Optional[Dict[str, Any]]:
    """Look up a subscription by its endpoint URL."""
    return _execute_read(
        """
        SELECT id, endpoint, is_active, device_type, browser,
               alert_preferences, pushes_sent_count, created_at
        FROM push_subscriptions
        WHERE endpoint = :endpoint
        """,
        params={"endpoint": endpoint},
        processor=_row_to_dict,
        default=None,
        context="get_push_subscription_by_endpoint",
    )


def record_push_sent(endpoint: str) -> bool:
    """Record a successful push notification."""
    return _execute_write(
        """
        UPDATE push_subscriptions
        SET last_push_at = NOW(),
            pushes_sent_count = pushes_sent_count + 1,
            consecutive_errors = 0,
            updated_at = NOW()
        WHERE endpoint = :endpoint
        """,
        params={"endpoint": endpoint},
        context="record_push_sent",
    )


def record_push_error(endpoint: str, error: str) -> bool:
    """Record a push notification failure."""
    return _execute_write(
        """
        UPDATE push_subscriptions
        SET consecutive_errors = consecutive_errors + 1,
            last_error = :error,
            updated_at = NOW()
        WHERE endpoint = :endpoint
        """,
        params={"endpoint": endpoint, "error": error},
        context="record_push_error",
    )


def deactivate_expired_token(endpoint: str) -> bool:
    """Deactivate a subscription with an expired/invalid token."""
    return _execute_write(
        """
        UPDATE push_subscriptions
        SET is_active = false,
            last_error = 'Token expired or invalid',
            updated_at = NOW()
        WHERE endpoint = :endpoint
        """,
        params={"endpoint": endpoint},
        context="deactivate_expired_token",
    )
```

---

## Dispatcher Integration

### Add FCM Channel to Notifications Worker

The `NotificationsWorker.process_event()` already dispatches to Telegram subscribers. Add a parallel dispatch to push subscribers:

```python
# notifications/event_consumer.py (modified)

class NotificationsWorker(EventWorker):
    consumer_group = ConsumerGroup.NOTIFICATIONS

    def process_event(self, event_type: str, payload: dict) -> dict:
        analysis_status = payload.get("analysis_status", "")
        if analysis_status != "completed":
            return {"skipped": True}

        alert = self._build_alert(payload)
        results = {
            "telegram_sent": 0, "telegram_failed": 0,
            "push_sent": 0, "push_failed": 0,
            "filtered": 0,
        }

        # === Telegram Channel (existing) ===
        telegram_results = self._dispatch_telegram(alert)
        results.update(telegram_results)

        # === Push Channel (NEW) ===
        push_results = self._dispatch_push(alert)
        results.update(push_results)

        return results

    def _dispatch_push(self, alert: dict) -> dict:
        """Dispatch alert to all matching push subscribers.

        Args:
            alert: Alert dict with prediction data.

        Returns:
            Dict with push_sent, push_failed counts.
        """
        from notifications.push_db import (
            get_active_push_subscriptions,
            record_push_sent,
            record_push_error,
            deactivate_expired_token,
        )
        from notifications.fcm_sender import (
            format_push_notification,
            send_push_notification,
        )
        from notifications.alert_engine import filter_predictions_by_preferences

        results = {"push_sent": 0, "push_failed": 0}

        subscriptions = get_active_push_subscriptions()
        if not subscriptions:
            return results

        # Format once, send to all
        push_data = format_push_notification(alert)

        for sub in subscriptions:
            prefs = sub.get("alert_preferences", {})
            matched = filter_predictions_by_preferences([alert], prefs)
            if not matched:
                continue

            token = sub.get("fcm_token") or sub.get("endpoint")
            success, error = send_push_notification(
                subscription_token=token,
                title=push_data["title"],
                body=push_data["body"],
                click_action=push_data["click_action"],
                tag=push_data["tag"],
                data={"prediction_id": str(alert.get("prediction_id", ""))},
            )

            if success:
                record_push_sent(sub["endpoint"])
                results["push_sent"] += 1
            else:
                if error == "TOKEN_EXPIRED":
                    deactivate_expired_token(sub["endpoint"])
                else:
                    record_push_error(sub["endpoint"], error or "Unknown")
                results["push_failed"] += 1

        return results
```

---

## Notification Payload

### What Users See on Lock Screen

```
+-----------------------------------------------+
| [icon] Shitpost Alpha                    12:03 |
|                                                 |
| Title:  BULLISH - TSLA, XLE (85%)        |
| Body:   Tesla praised, energy policy      |
|         boosted. Strong buy signal for     |
|         electric vehicles and domestic oil.|
|                                                 |
| [View Post]  [Dismiss]                          |
+-----------------------------------------------+
```

### Payload Structure (FCM)

```json
{
  "message": {
    "token": "fcm_registration_token_here",
    "notification": {
      "title": "BULLISH - TSLA, XLE (85%)",
      "body": "Tesla praised, energy policy boosted. Strong buy signal..."
    },
    "webpush": {
      "notification": {
        "icon": "/icons/icon-192.png",
        "badge": "/icons/badge-72.png",
        "tag": "prediction-12345",
        "renotify": true,
        "actions": [
          { "action": "view", "title": "View Post" },
          { "action": "dismiss", "title": "Dismiss" }
        ]
      },
      "fcm_options": {
        "link": "/?prediction=12345"
      }
    },
    "data": {
      "prediction_id": "12345",
      "sentiment": "bullish",
      "confidence": "0.85",
      "assets": "TSLA,XLE"
    }
  }
}
```

---

## Token Lifecycle Management

### Registration Flow

```
1. User clicks "Enable Notifications" in React UI
2. Browser prompts for permission
3. If granted: PushManager.subscribe() generates endpoint + keys
4. Frontend POSTs subscription to /api/push/subscribe
5. Backend stores in push_subscriptions table
6. User starts receiving push notifications
```

### Token Refresh

Browser push subscriptions can expire. The service worker should re-subscribe periodically:

```javascript
// frontend/public/sw.js (add to service worker)

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    self.registration.pushManager.subscribe(event.oldSubscription.options)
      .then((newSubscription) => {
        return fetch('/api/push/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subscription: newSubscription.toJSON(),
            old_endpoint: event.oldSubscription.endpoint,
          }),
        });
      })
  );
});
```

### Stale Token Cleanup

When FCM returns a 404 (token invalid/expired), the sender automatically deactivates the subscription via `deactivate_expired_token()`. Additionally, a weekly cleanup job removes subscriptions with `consecutive_errors >= 5`:

```python
# Could run as a Railway cron or be part of the event-cleanup service
def cleanup_stale_push_subscriptions():
    """Remove push subscriptions that have been failing consistently."""
    _execute_write(
        """
        UPDATE push_subscriptions
        SET is_active = false, updated_at = NOW()
        WHERE consecutive_errors >= 5 AND is_active = true
        """,
        context="cleanup_stale_push_subscriptions",
    )
```

---

## iOS / Safari Considerations

### Safari Web Push (macOS + iOS 16.4+)

Safari supports Web Push as of macOS Ventura and iOS 16.4, but with caveats:

1. **PWA required on iOS** -- Web Push only works on iOS if the user has added the site to their home screen ("Add to Home Screen")
2. **No background sync** -- Safari doesn't support the Background Sync API
3. **VAPID required** -- Safari requires VAPID authentication (which FCM uses)
4. **Permission UI differs** -- Safari shows a system-level permission dialog, not a browser bar

### Implementation Impact

The code above works for Safari with one addition: the PWA manifest must include the correct icons and `display: standalone` to enable the "Add to Home Screen" prompt. The service worker and push subscription code are identical across browsers.

### Recommendation

Add a banner/prompt on the React frontend for iOS Safari users: "Add to Home Screen for push notifications." This can be detected via `navigator.standalone === undefined && /iPad|iPhone/.test(navigator.userAgent)`.

---

## Cost Analysis

### Firebase Cloud Messaging Pricing

FCM is **completely free** for:
- Unlimited push notifications
- Unlimited devices
- No per-message cost

The only costs are:
- **Google Cloud project** -- free tier (no charges for FCM alone)
- **Service account** -- free
- **Bandwidth** -- negligible (a few KB per notification)

### VAPID Key Generation

VAPID keys are generated once and reused:

```bash
# Generate VAPID keys (one-time setup)
npx web-push generate-vapid-keys
```

Output:
```
Public Key: BNhQ4GH...
Private Key: Txnz...
```

Store as environment variables:
- `VITE_VAPID_PUBLIC_KEY` (frontend, public)
- `VAPID_PRIVATE_KEY` (backend, secret)

---

## Security Considerations

### Token Validation

- Push subscription endpoints are unique URLs generated by the browser's push service
- They cannot be guessed or fabricated
- The backend validates the subscription structure (endpoint, keys) on registration

### Origin Checks

- The service worker only accepts push events from the registered push service
- The FCM API requires authenticated service account credentials
- CORS on `/api/push/*` endpoints restricts to the production origin

### Data Minimization

- Push notification payloads should not contain sensitive data (just sentiment, tickers, confidence)
- The full thesis is truncated to 120 chars
- No user data is sent to Firebase -- only the notification content

---

## Testing Strategy

### Unit Tests

```python
# shit_tests/notifications/test_fcm_sender.py

class TestFCMSender:
    def test_format_push_notification_bullish(self):
        alert = {"sentiment": "bullish", "confidence": 0.85, "assets": ["TSLA"], "thesis": "Strong buy"}
        result = format_push_notification(alert)
        assert "BULLISH" in result["title"]
        assert "TSLA" in result["title"]
        assert "85%" in result["title"]

    def test_format_push_notification_no_assets(self):
        alert = {"sentiment": "neutral", "confidence": 0.5, "assets": [], "thesis": ""}
        result = format_push_notification(alert)
        assert result["body"] == "New prediction available"

    def test_send_push_token_expired(self, mock_fcm_api):
        mock_fcm_api.return_value = MockResponse(status_code=404)
        success, error = send_push_notification("expired_token", "title", "body")
        assert success is False
        assert error == "TOKEN_EXPIRED"


# shit_tests/notifications/test_push_db.py

class TestPushDB:
    def test_create_subscription(self, mock_sync_session):
        success = create_push_subscription(
            endpoint="https://fcm.googleapis.com/fcm/send/xxx",
            p256dh="key123", auth="auth456",
        )
        assert success is True

    def test_upsert_reactivates(self, mock_sync_session):
        """Creating a subscription that already exists reactivates it."""
        ...

    def test_deactivate_after_errors(self, mock_sync_session):
        """Subscriptions with 5+ errors are not returned by get_active."""
        ...
```

### Frontend Tests

```typescript
// frontend/src/__tests__/pushNotifications.test.ts

describe('Push Notifications', () => {
  it('detects push support', () => {
    expect(isPushSupported()).toBe(true);
  });

  it('returns null when permission denied', async () => {
    mockNotification.requestPermission.mockResolvedValue('denied');
    const result = await subscribeToPush();
    expect(result).toBeNull();
  });
});
```

### Integration Test

```python
class TestPushDispatchIntegration:
    def test_push_sent_alongside_telegram(self, mock_sync_session, mock_fcm, mock_telegram):
        """Both channels fire when a prediction event arrives."""
        worker = NotificationsWorker()
        result = worker.process_event("prediction_created", make_payload())
        assert result["telegram_sent"] >= 0
        assert result["push_sent"] >= 0
```

---

## Files to Create/Modify

### New Files
- `notifications/fcm_sender.py` -- FCM API integration
- `notifications/push_db.py` -- Push subscription database operations
- `api/routers/push.py` -- FastAPI endpoints for subscribe/unsubscribe
- `frontend/public/sw.js` -- Service worker for push events
- `frontend/src/utils/pushNotifications.ts` -- Push subscription helpers
- `frontend/src/components/PushOptIn.tsx` -- Permission UI component
- `frontend/public/manifest.json` -- PWA manifest (update existing if present)
- `shit_tests/notifications/test_fcm_sender.py` -- FCM sender tests
- `shit_tests/notifications/test_push_db.py` -- Push DB tests
- `shit_tests/api/routers/test_push.py` -- Push API endpoint tests

### Modified Files
- `notifications/models.py` -- Add PushSubscription model
- `notifications/event_consumer.py` -- Add `_dispatch_push()` to process_event
- `api/main.py` -- Register push router: `app.include_router(push.router)`
- `shit/config/shitpost_settings.py` -- Add Firebase settings (FIREBASE_PROJECT_ID, FIREBASE_SERVICE_ACCOUNT_KEY, VAPID_PRIVATE_KEY)
- `requirements.txt` -- Add `google-auth` and `google-auth-oauthlib`
- `frontend/src/App.tsx` -- Add `<PushOptIn />` component

### Environment Variables (New)
- `FIREBASE_PROJECT_ID` -- Firebase project identifier
- `FIREBASE_SERVICE_ACCOUNT_KEY` -- JSON service account key (stored as env var string)
- `VAPID_PRIVATE_KEY` -- VAPID private key for Web Push
- `VITE_VAPID_PUBLIC_KEY` -- VAPID public key (frontend, not secret)

---

## Migration Plan

### Phase 1: Backend + DB
1. Create `push_subscriptions` table
2. Add PushSubscription model
3. Implement `fcm_sender.py` and `push_db.py`
4. Add push router to FastAPI

### Phase 2: Frontend
1. Add service worker
2. Add push subscription utilities
3. Add PushOptIn component
4. Update PWA manifest

### Phase 3: Dispatch Integration
1. Add `_dispatch_push()` to notifications worker
2. Deploy and test with a single test subscription
3. Monitor FCM error rates

### Rollback

Push notifications can be disabled by:
- Removing the push router from `api/main.py`
- Skipping `_dispatch_push()` in the worker (behind `PUSH_NOTIFICATIONS_ENABLED` env var)
- No impact on existing Telegram functionality

---

## Open Questions

1. **VAPID vs FCM token** -- Should we use raw Web Push (VAPID) directly or go through FCM? FCM adds a dependency but handles token management and multi-platform delivery. Raw VAPID is simpler but requires implementing the encryption ourselves. Recommendation: FCM.
2. **Alert preferences** -- Should push subscribers share the same preference system as Telegram (min_confidence, assets_of_interest)? Or start with a simpler "all or nothing"? Recommendation: Share the same system for consistency.
3. **Batching integration** -- If Smart Alert Batching (Feature 09) is active, should push notifications also be batched? Or should push always be immediate (since it's meant to be fast)? Recommendation: Push is immediate; batching only applies to Telegram.
4. **Notification sound** -- Should we include a custom notification sound? FCM supports it but it adds complexity. Recommendation: Use default OS sound initially.
5. **Anonymous subscriptions** -- Push subscriptions are anonymous (no chat_id, no username). Should we add optional identification (e.g., ask for a nickname)? Recommendation: Keep anonymous; add identification later if needed for leaderboards.
6. **Rate limiting** -- Should there be a per-device rate limit? FCM has its own limits (~240 messages/minute per project). Recommendation: Rely on FCM limits initially.
