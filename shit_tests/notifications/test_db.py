"""Tests for notifications/db.py — full coverage of all 13 functions."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from notifications.db import (
    _row_to_dict,
    _rows_to_dicts,
    _UPDATABLE_COLUMNS,
    get_subscription,
    get_active_subscriptions,
    create_subscription,
    update_subscription,
    deactivate_subscription,
    record_alert_sent,
    record_error,
    get_subscription_stats,
    get_new_predictions_since,
    get_prediction_stats,
    get_latest_predictions,
    get_last_alert_check,
)


# ============================================================
# _row_to_dict / _rows_to_dicts helpers
# ============================================================


class TestRowToDict:
    """Tests for the _row_to_dict helper function."""

    def test_returns_dict_for_single_row(self):
        """A result with one row returns a dict mapping column names to values."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("chat_123", "private", True)]
        mock_result.keys.return_value = ["chat_id", "chat_type", "is_active"]

        result = _row_to_dict(mock_result)

        assert result == {"chat_id": "chat_123", "chat_type": "private", "is_active": True}

    def test_returns_first_row_when_multiple_rows(self):
        """When multiple rows exist, only the first row is returned."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("chat_1", "private", True),
            ("chat_2", "group", False),
        ]
        mock_result.keys.return_value = ["chat_id", "chat_type", "is_active"]

        result = _row_to_dict(mock_result)

        assert result == {"chat_id": "chat_1", "chat_type": "private", "is_active": True}

    def test_returns_none_for_empty_result(self):
        """An empty result set returns None."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        result = _row_to_dict(mock_result)

        assert result is None

    def test_handles_none_values_in_row(self):
        """None values in the row are preserved in the dict."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("chat_123", None, None)]
        mock_result.keys.return_value = ["chat_id", "username", "last_error"]

        result = _row_to_dict(mock_result)

        assert result == {"chat_id": "chat_123", "username": None, "last_error": None}


class TestRowsToDicts:
    """Tests for the _rows_to_dicts helper function."""

    def test_returns_list_of_dicts(self):
        """Multiple rows are converted to a list of dicts."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("chat_1", True),
            ("chat_2", False),
        ]
        mock_result.keys.return_value = ["chat_id", "is_active"]

        result = _rows_to_dicts(mock_result)

        assert result == [
            {"chat_id": "chat_1", "is_active": True},
            {"chat_id": "chat_2", "is_active": False},
        ]

    def test_returns_empty_list_for_no_rows(self):
        """An empty result set returns an empty list."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = ["chat_id", "is_active"]

        result = _rows_to_dicts(mock_result)

        assert result == []

    def test_single_row_returns_single_element_list(self):
        """A single row returns a list with one dict."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("chat_1", 5)]
        mock_result.keys.return_value = ["chat_id", "alerts_sent_count"]

        result = _rows_to_dicts(mock_result)

        assert result == [{"chat_id": "chat_1", "alerts_sent_count": 5}]


# ============================================================
# get_subscription
# ============================================================


class TestGetSubscription:
    """Tests for get_subscription()."""

    def test_returns_subscription_dict_when_found(self, mock_sync_session):
        """Returns a dict when a matching subscription exists."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, "12345", "private", "testuser", "Test", "User",
             None, True, None, None, "{}", None, 5, None, 0, None, None, None)
        ]
        mock_result.keys.return_value = [
            "id", "chat_id", "chat_type", "username", "first_name", "last_name",
            "title", "is_active", "subscribed_at", "unsubscribed_at",
            "alert_preferences", "last_alert_at", "alerts_sent_count",
            "last_interaction_at", "consecutive_errors", "last_error",
            "created_at", "updated_at",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_subscription("12345")

        assert result is not None
        assert result["chat_id"] == "12345"
        assert result["username"] == "testuser"
        assert result["is_active"] is True

    def test_returns_none_when_not_found(self, mock_sync_session):
        """Returns None when no subscription matches the chat_id."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sync_session.execute.return_value = mock_result

        result = get_subscription("nonexistent")

        assert result is None

    def test_returns_none_on_database_error(self, mock_sync_session):
        """Returns None when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Connection refused")

        result = get_subscription("12345")

        assert result is None

    def test_passes_chat_id_as_string(self, mock_sync_session):
        """chat_id is always converted to string before passing to the query."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sync_session.execute.return_value = mock_result

        get_subscription(12345)  # Pass as int

        # Verify the params dict has chat_id as a string
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]  # second positional arg is params dict
        assert params["chat_id"] == "12345"


# ============================================================
# get_active_subscriptions
# ============================================================


class TestGetActiveSubscriptions:
    """Tests for get_active_subscriptions()."""

    def test_returns_list_of_active_subscriptions(self, mock_sync_session):
        """Returns a list of dicts for active subscriptions."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, "chat_1", "private", "user1", "Alice", None, None, True, None, "{}", None, 3, 0),
            (2, "chat_2", "group", None, None, None, "My Group", True, None, "{}", None, 7, 1),
        ]
        mock_result.keys.return_value = [
            "id", "chat_id", "chat_type", "username", "first_name", "last_name",
            "title", "is_active", "subscribed_at", "alert_preferences",
            "last_alert_at", "alerts_sent_count", "consecutive_errors",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_active_subscriptions()

        assert len(result) == 2
        assert result[0]["chat_id"] == "chat_1"
        assert result[1]["chat_id"] == "chat_2"

    def test_returns_empty_list_when_no_active_subs(self, mock_sync_session):
        """Returns empty list when there are no active subscriptions."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = [
            "id", "chat_id", "chat_type", "username", "first_name", "last_name",
            "title", "is_active", "subscribed_at", "alert_preferences",
            "last_alert_at", "alerts_sent_count", "consecutive_errors",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_active_subscriptions()

        assert result == []

    def test_returns_empty_list_on_database_error(self, mock_sync_session):
        """Returns empty list when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Connection timeout")

        result = get_active_subscriptions()

        assert result == []


# ============================================================
# create_subscription
# ============================================================


class TestCreateSubscription:
    """Tests for create_subscription()."""

    def test_creates_new_subscription(self, mock_sync_session):
        """Creates a new subscription when none exists for the chat_id."""
        # First call: get_subscription returns None (no existing sub)
        mock_result_select = MagicMock()
        mock_result_select.fetchall.return_value = []

        # Second call: INSERT succeeds
        mock_result_insert = MagicMock()

        mock_sync_session.execute.side_effect = [mock_result_select, mock_result_insert]

        result = create_subscription("99999", "private", username="newuser", first_name="New")

        assert result is True
        # Verify INSERT was called (second execute call)
        assert mock_sync_session.execute.call_count == 2
        insert_params = mock_sync_session.execute.call_args_list[1][0][1]
        assert insert_params["chat_id"] == "99999"
        assert insert_params["chat_type"] == "private"
        assert insert_params["username"] == "newuser"
        assert insert_params["first_name"] == "New"
        # Verify default preferences are JSON-encoded
        prefs = json.loads(insert_params["alert_preferences"])
        assert prefs["min_confidence"] == 0.7
        assert prefs["assets_of_interest"] == []

    def test_reactivates_inactive_subscription(self, mock_sync_session):
        """Reactivates an existing inactive subscription instead of creating a new one."""
        # get_subscription returns an inactive sub
        mock_result_select = MagicMock()
        mock_result_select.fetchall.return_value = [
            (1, "12345", "private", "user", "Test", None,
             None, False, None, None, "{}", None, 0, None, 0, None, None, None)
        ]
        mock_result_select.keys.return_value = [
            "id", "chat_id", "chat_type", "username", "first_name", "last_name",
            "title", "is_active", "subscribed_at", "unsubscribed_at",
            "alert_preferences", "last_alert_at", "alerts_sent_count",
            "last_interaction_at", "consecutive_errors", "last_error",
            "created_at", "updated_at",
        ]

        # update_subscription (called internally for reactivation)
        mock_result_update = MagicMock()

        mock_sync_session.execute.side_effect = [mock_result_select, mock_result_update]

        result = create_subscription("12345", "private")

        assert result is True

    def test_returns_true_for_already_active_subscription(self, mock_sync_session):
        """Returns True immediately if subscription already exists and is active."""
        mock_result_select = MagicMock()
        mock_result_select.fetchall.return_value = [
            (1, "12345", "private", "user", "Test", None,
             None, True, None, None, "{}", None, 5, None, 0, None, None, None)
        ]
        mock_result_select.keys.return_value = [
            "id", "chat_id", "chat_type", "username", "first_name", "last_name",
            "title", "is_active", "subscribed_at", "unsubscribed_at",
            "alert_preferences", "last_alert_at", "alerts_sent_count",
            "last_interaction_at", "consecutive_errors", "last_error",
            "created_at", "updated_at",
        ]
        mock_sync_session.execute.return_value = mock_result_select

        result = create_subscription("12345", "private")

        assert result is True
        # Only the SELECT was executed (no INSERT)
        assert mock_sync_session.execute.call_count == 1

    def test_returns_false_on_database_error(self, mock_sync_session):
        """Returns False when the database raises an exception."""
        # get_subscription raises (first execute call)
        mock_sync_session.execute.side_effect = Exception("DB error")

        result = create_subscription("12345", "private")

        assert result is False

    def test_optional_params_default_to_none(self, mock_sync_session):
        """Optional parameters (username, first_name, last_name, title) default to None."""
        mock_result_select = MagicMock()
        mock_result_select.fetchall.return_value = []
        mock_result_insert = MagicMock()
        mock_sync_session.execute.side_effect = [mock_result_select, mock_result_insert]

        result = create_subscription("99999", "channel")

        assert result is True
        insert_params = mock_sync_session.execute.call_args_list[1][0][1]
        assert insert_params["username"] is None
        assert insert_params["first_name"] is None
        assert insert_params["last_name"] is None
        assert insert_params["title"] is None


# ============================================================
# update_subscription (existing tests preserved + new tests)
# ============================================================


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


class TestUpdateSubscription:
    """Additional update_subscription tests beyond injection prevention."""

    def test_serializes_alert_preferences_dict_to_json(self, mock_sync_session):
        """When alert_preferences is a dict, it is JSON-serialized before query."""
        prefs = {"min_confidence": 0.9, "assets_of_interest": ["AAPL"]}

        result = update_subscription("12345", alert_preferences=prefs)

        assert result is True
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        # The value should be a JSON string, not a dict
        assert isinstance(params["alert_preferences"], str)
        assert json.loads(params["alert_preferences"]) == prefs

    def test_alert_preferences_string_passed_as_is(self, mock_sync_session):
        """When alert_preferences is already a string, it is not double-serialized."""
        prefs_str = '{"min_confidence": 0.8}'

        result = update_subscription("12345", alert_preferences=prefs_str)

        assert result is True
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["alert_preferences"] == prefs_str

    def test_multiple_columns_updated(self, mock_sync_session):
        """Multiple valid columns can be updated in a single call."""
        result = update_subscription(
            "12345", username="newname", first_name="NewFirst", is_active=True
        )

        assert result is True
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["username"] == "newname"
        assert params["first_name"] == "NewFirst"
        assert params["is_active"] is True
        assert params["chat_id"] == "12345"

    def test_returns_false_on_database_error(self, mock_sync_session):
        """Returns False when the database raises an exception during UPDATE."""
        mock_sync_session.execute.side_effect = Exception("Connection lost")

        result = update_subscription("12345", username="new")

        assert result is False

    def test_invalid_column_raises_and_returns_false(self, mock_sync_session):
        """An invalid column name causes ValueError which is caught, returning False."""
        result = update_subscription("12345", drop_table="malicious")

        assert result is False


# ============================================================
# deactivate_subscription
# ============================================================


class TestDeactivateSubscription:
    """Tests for deactivate_subscription()."""

    def test_calls_update_with_is_active_false(self, mock_sync_session):
        """Deactivation sets is_active=False and unsubscribed_at to a datetime."""
        result = deactivate_subscription("12345")

        assert result is True
        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["is_active"] is False
        assert params["chat_id"] == "12345"
        # unsubscribed_at should be a datetime (from datetime.utcnow())
        assert "unsubscribed_at" in params

    def test_returns_false_on_error(self, mock_sync_session):
        """Returns False when the underlying update fails."""
        mock_sync_session.execute.side_effect = Exception("DB down")

        result = deactivate_subscription("12345")

        assert result is False


# ============================================================
# record_alert_sent
# ============================================================


class TestRecordAlertSent:
    """Tests for record_alert_sent()."""

    def test_returns_true_on_success(self, mock_sync_session):
        """Returns True when the update succeeds."""
        result = record_alert_sent("12345")

        assert result is True
        mock_sync_session.execute.assert_called_once()

    def test_passes_chat_id_as_string(self, mock_sync_session):
        """chat_id is passed as a string to the query params."""
        record_alert_sent(12345)  # Pass int

        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["chat_id"] == "12345"

    def test_returns_false_on_database_error(self, mock_sync_session):
        """Returns False when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Timeout")

        result = record_alert_sent("12345")

        assert result is False


# ============================================================
# record_error
# ============================================================


class TestRecordError:
    """Tests for record_error()."""

    def test_returns_true_on_success(self, mock_sync_session):
        """Returns True when the error is recorded successfully."""
        result = record_error("12345", "Connection timeout")

        assert result is True
        mock_sync_session.execute.assert_called_once()

    def test_passes_error_message_to_query(self, mock_sync_session):
        """The error_message is passed to the query params."""
        record_error("12345", "Rate limited")

        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["error_message"] == "Rate limited"
        assert params["chat_id"] == "12345"

    def test_returns_false_on_database_error(self, mock_sync_session):
        """Returns False when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("DB error")

        result = record_error("12345", "Some error")

        assert result is False


# ============================================================
# get_subscription_stats
# ============================================================


class TestGetSubscriptionStats:
    """Tests for get_subscription_stats()."""

    def test_returns_stats_dict(self, mock_sync_session):
        """Returns aggregated stats as a dict."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(10, 8, 6, 2, 2, 150)]
        mock_result.keys.return_value = [
            "total", "active", "private_chats", "groups", "channels", "total_alerts_sent"
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_subscription_stats()

        assert result["total"] == 10
        assert result["active"] == 8
        assert result["private_chats"] == 6
        assert result["groups"] == 2
        assert result["channels"] == 2
        assert result["total_alerts_sent"] == 150

    def test_returns_empty_dict_when_no_subscriptions(self, mock_sync_session):
        """Returns empty dict when _row_to_dict returns None (no rows)."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sync_session.execute.return_value = mock_result

        result = get_subscription_stats()

        # _row_to_dict returns None, function returns {} via `or {}`
        assert result == {}

    def test_returns_empty_dict_on_database_error(self, mock_sync_session):
        """Returns empty dict when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Connection refused")

        result = get_subscription_stats()

        assert result == {}


# ============================================================
# get_new_predictions_since
# ============================================================


class TestGetNewPredictionsSince:
    """Tests for get_new_predictions_since()."""

    def test_returns_predictions_list(self, mock_sync_session):
        """Returns a list of prediction dicts with joined shitpost data."""
        since = datetime(2026, 1, 1)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (
                datetime(2026, 3, 15, 10, 0, 0),  # timestamp
                "Big news about tariffs!",         # text
                "post_123",                        # shitpost_id
                42,                                # prediction_id
                '["SPY", "DIA"]',                  # assets
                '{"SPY": "bearish"}',              # market_impact
                0.85,                              # confidence
                "Tariffs likely to impact...",      # thesis
                "completed",                       # analysis_status
                datetime(2026, 3, 15, 10, 5, 0),  # prediction_created_at
            ),
        ]
        mock_result.keys.return_value = [
            "timestamp", "text", "shitpost_id", "prediction_id", "assets",
            "market_impact", "confidence", "thesis", "analysis_status",
            "prediction_created_at",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_new_predictions_since(since)

        assert len(result) == 1
        assert result[0]["shitpost_id"] == "post_123"
        assert result[0]["confidence"] == 0.85

    def test_serializes_datetime_fields_to_iso(self, mock_sync_session):
        """datetime fields (timestamp, prediction_created_at) are converted to ISO strings."""
        since = datetime(2026, 1, 1)
        ts = datetime(2026, 3, 15, 10, 0, 0)
        created = datetime(2026, 3, 15, 10, 5, 0)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (ts, "text", "post_1", 1, "[]", "{}", 0.9, "thesis", "completed", created),
        ]
        mock_result.keys.return_value = [
            "timestamp", "text", "shitpost_id", "prediction_id", "assets",
            "market_impact", "confidence", "thesis", "analysis_status",
            "prediction_created_at",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_new_predictions_since(since)

        assert result[0]["timestamp"] == "2026-03-15T10:00:00"
        assert result[0]["prediction_created_at"] == "2026-03-15T10:05:00"

    def test_non_datetime_timestamp_not_converted(self, mock_sync_session):
        """If timestamp is already a string, it is left as-is."""
        since = datetime(2026, 1, 1)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("2026-03-15T10:00:00", "text", "post_1", 1, "[]", "{}", 0.9, "thesis", "completed", "2026-03-15T10:05:00"),
        ]
        mock_result.keys.return_value = [
            "timestamp", "text", "shitpost_id", "prediction_id", "assets",
            "market_impact", "confidence", "thesis", "analysis_status",
            "prediction_created_at",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_new_predictions_since(since)

        assert result[0]["timestamp"] == "2026-03-15T10:00:00"

    def test_returns_empty_list_when_no_predictions(self, mock_sync_session):
        """Returns empty list when no predictions match the criteria."""
        since = datetime(2026, 1, 1)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = [
            "timestamp", "text", "shitpost_id", "prediction_id", "assets",
            "market_impact", "confidence", "thesis", "analysis_status",
            "prediction_created_at",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_new_predictions_since(since)

        assert result == []

    def test_returns_empty_list_on_database_error(self, mock_sync_session):
        """Returns empty list when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Query timeout")

        result = get_new_predictions_since(datetime(2026, 1, 1))

        assert result == []


# ============================================================
# get_prediction_stats
# ============================================================


class TestGetPredictionStats:
    """Tests for get_prediction_stats()."""

    def test_returns_computed_stats(self, mock_sync_session):
        """Returns a dict with computed win_rate and total_return_pct."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(100, 60, 80, 0.15)]
        mock_result.keys.return_value = [
            "total_predictions", "correct_count", "evaluated_count", "total_return",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_prediction_stats()

        assert result["total_predictions"] == 100
        assert result["evaluated"] == 80
        assert result["correct"] == 60
        assert result["win_rate"] == 75.0  # 60/80 * 100
        assert result["total_return_pct"] == 15.0  # 0.15 * 100

    def test_zero_evaluated_avoids_division_by_zero(self, mock_sync_session):
        """When evaluated_count is 0, win_rate is 0.0 (no ZeroDivisionError)."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(5, 0, 0, 0)]
        mock_result.keys.return_value = [
            "total_predictions", "correct_count", "evaluated_count", "total_return",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_prediction_stats()

        assert result["win_rate"] == 0.0
        assert result["total_predictions"] == 5

    def test_handles_none_values_from_db(self, mock_sync_session):
        """None values from SUM/COUNT are treated as 0."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(None, None, None, None)]
        mock_result.keys.return_value = [
            "total_predictions", "correct_count", "evaluated_count", "total_return",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_prediction_stats()

        assert result["total_predictions"] == 0
        assert result["win_rate"] == 0.0
        assert result["total_return_pct"] == 0.0

    def test_returns_empty_dict_when_no_rows(self, mock_sync_session):
        """Returns empty dict when _row_to_dict returns None."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_sync_session.execute.return_value = mock_result

        result = get_prediction_stats()

        assert result == {}

    def test_returns_empty_dict_on_database_error(self, mock_sync_session):
        """Returns empty dict when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Connection refused")

        result = get_prediction_stats()

        assert result == {}


# ============================================================
# get_latest_predictions
# ============================================================


class TestGetLatestPredictions:
    """Tests for get_latest_predictions()."""

    def test_returns_list_of_predictions_with_outcomes(self, mock_sync_session):
        """Returns prediction dicts with LEFT JOINed outcome data."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, '["AAPL"]', 0.9, '{"AAPL": "bullish"}', "Strong buy",
             datetime(2026, 3, 15), "bullish", True, 0.05, "AAPL"),
        ]
        mock_result.keys.return_value = [
            "prediction_id", "assets", "confidence", "market_impact", "thesis",
            "created_at", "prediction_sentiment", "correct_t7", "return_t7", "symbol",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_latest_predictions(limit=5)

        assert len(result) == 1
        assert result[0]["prediction_id"] == 1
        assert result[0]["confidence"] == 0.9
        # created_at should be serialized to ISO string
        assert result[0]["created_at"] == "2026-03-15T00:00:00"

    def test_serializes_created_at_to_iso(self, mock_sync_session):
        """datetime created_at is converted to ISO string."""
        dt = datetime(2026, 3, 20, 14, 30, 0)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, "[]", 0.8, "{}", "thesis", dt, None, None, None, None),
        ]
        mock_result.keys.return_value = [
            "prediction_id", "assets", "confidence", "market_impact", "thesis",
            "created_at", "prediction_sentiment", "correct_t7", "return_t7", "symbol",
        ]
        mock_sync_session.execute.return_value = mock_result

        result = get_latest_predictions(limit=1)

        assert result[0]["created_at"] == "2026-03-20T14:30:00"

    def test_passes_limit_to_query(self, mock_sync_session):
        """The limit parameter is passed through to the SQL query."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = [
            "prediction_id", "assets", "confidence", "market_impact", "thesis",
            "created_at", "prediction_sentiment", "correct_t7", "return_t7", "symbol",
        ]
        mock_sync_session.execute.return_value = mock_result

        get_latest_predictions(limit=10)

        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 10

    def test_default_limit_is_five(self, mock_sync_session):
        """Default limit is 5 when not specified."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = [
            "prediction_id", "assets", "confidence", "market_impact", "thesis",
            "created_at", "prediction_sentiment", "correct_t7", "return_t7", "symbol",
        ]
        mock_sync_session.execute.return_value = mock_result

        get_latest_predictions()

        call_args = mock_sync_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 5

    def test_returns_empty_list_on_database_error(self, mock_sync_session):
        """Returns empty list when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Timeout")

        result = get_latest_predictions()

        assert result == []


# ============================================================
# get_last_alert_check
# ============================================================


class TestGetLastAlertCheck:
    """Tests for get_last_alert_check()."""

    def test_returns_datetime_when_found(self, mock_sync_session):
        """Returns a datetime when active subscriptions have a last_alert_at."""
        expected_dt = datetime(2026, 3, 25, 15, 30, 0)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (expected_dt,)
        mock_sync_session.execute.return_value = mock_result

        result = get_last_alert_check()

        assert result == expected_dt

    def test_returns_none_when_no_alerts_sent(self, mock_sync_session):
        """Returns None when MAX(last_alert_at) is NULL (no alerts ever sent)."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (None,)
        mock_sync_session.execute.return_value = mock_result

        result = get_last_alert_check()

        assert result is None

    def test_returns_none_when_no_rows(self, mock_sync_session):
        """Returns None when fetchone returns None (no rows at all)."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_sync_session.execute.return_value = mock_result

        result = get_last_alert_check()

        assert result is None

    def test_returns_none_on_database_error(self, mock_sync_session):
        """Returns None when the database raises an exception."""
        mock_sync_session.execute.side_effect = Exception("Connection refused")

        result = get_last_alert_check()

        assert result is None
