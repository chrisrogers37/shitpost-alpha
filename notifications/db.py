"""
Database operations for the notifications module.

Handles subscription CRUD, alert history, and last-check timestamp persistence.
Uses the project's sync session pattern from shit/db/sync_session.py.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from shit.db.sync_session import get_session

logger = logging.getLogger(__name__)


def _row_to_dict(result) -> Optional[Dict[str, Any]]:
    """Convert a single query result row to a dictionary."""
    rows = result.fetchall()
    if not rows:
        return None
    columns = result.keys()
    return dict(zip(columns, rows[0]))


def _rows_to_dicts(result) -> List[Dict[str, Any]]:
    """Convert query result rows to a list of dictionaries."""
    rows = result.fetchall()
    columns = result.keys()
    return [dict(zip(columns, row)) for row in rows]


# Whitelist of columns that can be updated via update_subscription().
# Prevents SQL injection through dynamic kwargs keys.
_UPDATABLE_COLUMNS = frozenset({
    "chat_type",
    "username",
    "first_name",
    "last_name",
    "title",
    "is_active",
    "subscribed_at",
    "unsubscribed_at",
    "alert_preferences",
    "last_alert_at",
    "alerts_sent_count",
    "consecutive_errors",
    "last_error",
    "last_interaction_at",
})


# ============================================================
# Subscription CRUD
# ============================================================


def get_subscription(chat_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a Telegram subscription by chat_id.

    Args:
        chat_id: Telegram chat ID.

    Returns:
        Subscription dict or None if not found.
    """
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    id, chat_id, chat_type, username, first_name, last_name,
                    title, is_active, subscribed_at, unsubscribed_at,
                    alert_preferences, last_alert_at, alerts_sent_count,
                    last_interaction_at, consecutive_errors, last_error,
                    created_at, updated_at
                FROM telegram_subscriptions
                WHERE chat_id = :chat_id
            """)
            result = session.execute(query, {"chat_id": str(chat_id)})
            return _row_to_dict(result)
    except Exception as e:
        logger.error(f"Error getting subscription for chat_id {chat_id}: {e}")
        return None


def get_active_subscriptions() -> List[Dict[str, Any]]:
    """
    Get all active Telegram subscriptions.

    Returns:
        List of subscription dicts.
    """
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    id, chat_id, chat_type, username, first_name, last_name,
                    title, is_active, subscribed_at, alert_preferences,
                    last_alert_at, alerts_sent_count, consecutive_errors
                FROM telegram_subscriptions
                WHERE is_active = true
                    AND consecutive_errors < 5
                ORDER BY subscribed_at ASC
            """)
            result = session.execute(query)
            return _rows_to_dicts(result)
    except Exception as e:
        logger.error(f"Error getting active subscriptions: {e}")
        return []


def create_subscription(
    chat_id: str,
    chat_type: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    title: Optional[str] = None,
) -> bool:
    """
    Create a new Telegram subscription or reactivate an existing one.

    Args:
        chat_id: Telegram chat ID.
        chat_type: Type of chat (private, group, supergroup, channel).
        username: Optional username.
        first_name: Optional first name.
        last_name: Optional last name.
        title: Optional group/channel title.

    Returns:
        True if created successfully.
    """
    try:
        existing = get_subscription(chat_id)
        if existing:
            if not existing.get("is_active"):
                return update_subscription(
                    chat_id, is_active=True, unsubscribed_at=None
                )
            return True

        default_prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }

        with get_session() as session:
            query = text("""
                INSERT INTO telegram_subscriptions (
                    chat_id, chat_type, username, first_name, last_name, title,
                    is_active, subscribed_at, alert_preferences,
                    alerts_sent_count, consecutive_errors,
                    created_at, updated_at
                ) VALUES (
                    :chat_id, :chat_type, :username, :first_name, :last_name, :title,
                    true, NOW(), :alert_preferences,
                    0, 0,
                    NOW(), NOW()
                )
            """)
            session.execute(
                query,
                {
                    "chat_id": str(chat_id),
                    "chat_type": chat_type,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "title": title,
                    "alert_preferences": json.dumps(default_prefs),
                },
            )
        logger.info(f"Created Telegram subscription for chat_id {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating subscription for chat_id {chat_id}: {e}")
        return False


def update_subscription(chat_id: str, **kwargs: Any) -> bool:
    """
    Update a Telegram subscription.

    Args:
        chat_id: Telegram chat ID.
        **kwargs: Fields to update.

    Returns:
        True if updated successfully.
    """
    try:
        if not kwargs:
            return True

        set_clauses = []
        params: Dict[str, Any] = {"chat_id": str(chat_id)}

        for key, value in kwargs.items():
            if key not in _UPDATABLE_COLUMNS:
                raise ValueError(f"Invalid column name for subscription update: {key}")
            if key == "alert_preferences" and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        set_clauses.append("updated_at = NOW()")

        with get_session() as session:
            query = text(f"""
                UPDATE telegram_subscriptions
                SET {", ".join(set_clauses)}
                WHERE chat_id = :chat_id
            """)
            session.execute(query, params)
        logger.info(f"Updated Telegram subscription for chat_id {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating subscription for chat_id {chat_id}: {e}")
        return False


def deactivate_subscription(chat_id: str) -> bool:
    """Deactivate (unsubscribe) a Telegram subscription."""
    return update_subscription(
        chat_id, is_active=False, unsubscribed_at=datetime.utcnow()
    )


def record_alert_sent(chat_id: str) -> bool:
    """Record that an alert was sent to this subscription."""
    try:
        with get_session() as session:
            query = text("""
                UPDATE telegram_subscriptions
                SET last_alert_at = NOW(),
                    alerts_sent_count = alerts_sent_count + 1,
                    consecutive_errors = 0,
                    updated_at = NOW()
                WHERE chat_id = :chat_id
            """)
            session.execute(query, {"chat_id": str(chat_id)})
        return True
    except Exception as e:
        logger.error(f"Error recording alert sent for chat_id {chat_id}: {e}")
        return False


def record_error(chat_id: str, error_message: str) -> bool:
    """Record an error for this subscription."""
    try:
        with get_session() as session:
            query = text("""
                UPDATE telegram_subscriptions
                SET consecutive_errors = consecutive_errors + 1,
                    last_error = :error_message,
                    updated_at = NOW()
                WHERE chat_id = :chat_id
            """)
            session.execute(
                query, {"chat_id": str(chat_id), "error_message": error_message}
            )
        return True
    except Exception as e:
        logger.error(f"Error recording error for chat_id {chat_id}: {e}")
        return False


def get_subscription_stats() -> Dict[str, Any]:
    """Get statistics about Telegram subscriptions."""
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_active = true THEN 1 END) as active,
                    COUNT(CASE WHEN chat_type = 'private' THEN 1 END) as private_chats,
                    COUNT(CASE WHEN chat_type IN ('group', 'supergroup') THEN 1 END) as groups,
                    COUNT(CASE WHEN chat_type = 'channel' THEN 1 END) as channels,
                    SUM(alerts_sent_count) as total_alerts_sent
                FROM telegram_subscriptions
            """)
            result = session.execute(query)
            return _row_to_dict(result) or {}
    except Exception as e:
        logger.error(f"Error getting subscription stats: {e}")
        return {}


# ============================================================
# Alert queries
# ============================================================


def get_new_predictions_since(since: datetime) -> List[Dict[str, Any]]:
    """
    Get new completed predictions created after the given timestamp.

    Args:
        since: Only return predictions created after this timestamp.

    Returns:
        List of prediction dicts with associated shitpost data.
    """
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    tss.timestamp,
                    tss.text,
                    tss.shitpost_id,
                    p.id as prediction_id,
                    p.assets,
                    p.market_impact,
                    p.confidence,
                    p.thesis,
                    p.analysis_status,
                    p.created_at as prediction_created_at
                FROM predictions p
                INNER JOIN truth_social_shitposts tss
                    ON tss.shitpost_id = p.shitpost_id
                WHERE p.analysis_status = 'completed'
                    AND p.created_at > :since
                    AND p.confidence IS NOT NULL
                    AND p.assets IS NOT NULL
                    AND p.assets::jsonb <> '[]'::jsonb
                ORDER BY p.created_at DESC
                LIMIT 50
            """)
            result = session.execute(query, {"since": since})
            results = _rows_to_dicts(result)
            for row_dict in results:
                if isinstance(row_dict.get("timestamp"), datetime):
                    row_dict["timestamp"] = row_dict["timestamp"].isoformat()
                if isinstance(row_dict.get("prediction_created_at"), datetime):
                    row_dict["prediction_created_at"] = row_dict[
                        "prediction_created_at"
                    ].isoformat()
            return results
    except Exception as e:
        logger.error(f"Error loading new predictions: {e}")
        return []


def get_prediction_stats() -> Dict[str, Any]:
    """
    Get overall prediction accuracy statistics from prediction_outcomes.

    Returns:
        Dict with accuracy, win_rate, total_pnl, total_predictions.
    """
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    COUNT(*) as total_predictions,
                    COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_count,
                    COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_count,
                    COALESCE(SUM(return_t7), 0) as total_return
                FROM prediction_outcomes
            """)
            result = session.execute(query)
            row = _row_to_dict(result)
            if row:
                total = row.get("total_predictions", 0) or 0
                correct = row.get("correct_count", 0) or 0
                evaluated = row.get("evaluated_count", 0) or 0
                total_return = float(row.get("total_return", 0) or 0)

                win_rate = (correct / evaluated * 100) if evaluated > 0 else 0.0
                return {
                    "total_predictions": total,
                    "evaluated": evaluated,
                    "correct": correct,
                    "win_rate": round(win_rate, 1),
                    "total_return_pct": round(total_return * 100, 2),
                }
            return {}
    except Exception as e:
        logger.error(f"Error getting prediction stats: {e}")
        return {}


def get_latest_predictions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent completed predictions with outcome data.

    Args:
        limit: Number of predictions to return.

    Returns:
        List of prediction dicts with outcome status.
    """
    try:
        with get_session() as session:
            query = text("""
                SELECT
                    p.id as prediction_id,
                    p.assets,
                    p.confidence,
                    p.market_impact,
                    p.thesis,
                    p.created_at,
                    po.prediction_sentiment,
                    po.correct_t7,
                    po.return_t7,
                    po.symbol
                FROM predictions p
                LEFT JOIN prediction_outcomes po ON po.prediction_id = p.id
                WHERE p.analysis_status = 'completed'
                    AND p.confidence IS NOT NULL
                ORDER BY p.created_at DESC
                LIMIT :limit
            """)
            result = session.execute(query, {"limit": limit})
            results = _rows_to_dicts(result)
            for row_dict in results:
                if isinstance(row_dict.get("created_at"), datetime):
                    row_dict["created_at"] = row_dict["created_at"].isoformat()
            return results
    except Exception as e:
        logger.error(f"Error getting latest predictions: {e}")
        return []


# ============================================================
# Last check timestamp persistence
# ============================================================


def get_last_alert_check() -> Optional[datetime]:
    """
    Get the timestamp of the last alert check from the database.

    Uses a simple key-value approach in a notification_state table,
    falling back to None if the table doesn't exist yet.
    """
    try:
        with get_session() as session:
            # Use the most recent alert sent across all subscriptions as a proxy
            query = text("""
                SELECT MAX(last_alert_at) as last_check
                FROM telegram_subscriptions
                WHERE is_active = true
            """)
            result = session.execute(query)
            row = result.fetchone()
            if row and row[0]:
                return row[0]
            return None
    except Exception as e:
        logger.error(f"Error getting last alert check: {e}")
        return None
