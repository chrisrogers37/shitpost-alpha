"""Tests for notifications/db.py — focusing on SQL injection prevention."""

from notifications.db import update_subscription, _UPDATABLE_COLUMNS


class TestUpdatableColumnsWhitelist:
    """Verify the _UPDATABLE_COLUMNS whitelist is correct and complete."""

    def test_whitelist_has_expected_count(self):
        assert len(_UPDATABLE_COLUMNS) == 14

    def test_whitelist_contains_all_expected_columns(self):
        expected = {
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
        }
        assert _UPDATABLE_COLUMNS == expected

    def test_whitelist_is_frozen(self):
        assert isinstance(_UPDATABLE_COLUMNS, frozenset)


class TestUpdateSubscriptionInjectionPrevention:
    """Verify SQL injection via kwargs keys is blocked."""

    def test_rejects_injected_column_name(self, mock_sync_session):
        result = update_subscription(
            "12345", **{"is_active = true; DROP TABLE telegram_subscriptions": "x"}
        )
        assert result is False

    def test_rejects_column_with_sql_comment(self, mock_sync_session):
        result = update_subscription("12345", **{"is_active -- ": True})
        assert result is False

    def test_rejects_unknown_column(self, mock_sync_session):
        result = update_subscription("12345", nonexistent_column="value")
        assert result is False

    def test_accepts_valid_columns(self, mock_sync_session):
        result = update_subscription("12345", is_active=True)
        assert result is True

    def test_empty_kwargs_returns_true(self, mock_sync_session):
        result = update_subscription("12345")
        assert result is True
