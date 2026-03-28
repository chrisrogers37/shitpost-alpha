# Phase 02 — Notifications DB Test Coverage + Query Dedup

**Status:** ✅ COMPLETE
**Started:** 2026-03-28
**Completed:** 2026-03-28
**PR:** #114

| Field | Value |
|---|---|
| **PR Title** | `feat: notifications DB test coverage + query dedup` |
| **Risk** | Low |
| **Effort** | Medium |
| **Files Modified** | 2 (`notifications/db.py`, `shit_tests/notifications/test_db.py`) |
| **Files Created** | 0 |
| **Dependencies** | None |
| **Unlocks** | None |

---

## Context

`notifications/db.py` has 13 public/helper functions but only 9 tests, all focused on the `_UPDATABLE_COLUMNS` whitelist and `update_subscription` SQL injection prevention. The remaining 12 functions (`_row_to_dict`, `_rows_to_dicts`, `get_subscription`, `get_active_subscriptions`, `create_subscription`, `deactivate_subscription`, `record_alert_sent`, `record_error`, `get_subscription_stats`, `get_new_predictions_since`, `get_prediction_stats`, `get_latest_predictions`, `get_last_alert_check`) have zero test coverage.

Additionally, 11 of the 13 functions follow an identical pattern:

```python
def some_function(args):
    try:
        with get_session() as session:
            query = text("...")
            result = session.execute(query, params)
            return _rows_to_dicts(result)  # or _row_to_dict, or commit
    except Exception as e:
        logger.error(f"Error ...: {e}")
        return []  # or None, False, {}
```

This phase:
1. Extracts `_execute_read` and `_execute_write` helpers to eliminate the duplicated try/session/except boilerplate
2. Adds comprehensive tests for all 13 functions (55+ new tests)
3. Uses the existing `mock_sync_session` autouse fixture from conftest

The refactor is safe because we write tests first against the current API, then refactor, then re-run. The public API of every function is unchanged.

---

## Dependencies

None. This phase touches only `notifications/db.py` and its test file. No other phase modifies these files.

---

## Detailed Implementation Plan

### Step 1: Add comprehensive tests FIRST (before refactoring)

Write all new tests in `shit_tests/notifications/test_db.py`. The existing conftest at `shit_tests/notifications/conftest.py` provides:
- `mock_sync_session` (autouse) — patches `notifications.db.get_session` to return a MagicMock
- `sample_subscription` — a dict representing a subscription row
- `sample_alert` — a dict representing an alert
- `sample_preferences` — a dict representing alert preferences

The `mock_sync_session` fixture yields the mock session object itself. When `get_session()` is called in the source code as a context manager (`with get_session() as session:`), the mock's `__enter__` returns the same mock, so `session.execute(...)` calls are captured on the yielded mock.

#### File: `shit_tests/notifications/test_db.py`

**Replace the entire file** with the content below. The existing 9 tests are preserved (classes `TestUpdatableColumnsWhitelist` and `TestUpdateSubscriptionInjectionPrevention`) and new test classes are added.

```python
"""Tests for notifications/db.py — full coverage of all 13 functions."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch, call

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
```

**Total test count**: 62 tests (8 existing + 54 new).

### Step 2: Run the tests and verify they all pass

Run:
```bash
./venv/bin/python -m pytest shit_tests/notifications/test_db.py -v
```

All 62 tests must pass before proceeding to the refactor step.

### Step 3: Extract query helper functions in `notifications/db.py`

Now that we have a comprehensive test safety net, refactor the duplicated try/session/except blocks.

#### 3a. Add `_execute_read` and `_execute_write` helpers

**Add after line 33** (after `_rows_to_dicts`), before the `_UPDATABLE_COLUMNS` declaration:

```python
def _execute_read(
    query_str: str,
    params: Optional[Dict[str, Any]] = None,
    processor=_rows_to_dicts,
    default: Any = None,
    context: str = "",
) -> Any:
    """
    Execute a read query with standard error handling.

    Args:
        query_str: SQL query string.
        params: Optional query parameters.
        processor: Function to process the result (default: _rows_to_dicts).
                   Use _row_to_dict for single-row queries.
        default: Value to return on error or empty result.
        context: Descriptive label for error logging (e.g. "get_subscription").

    Returns:
        Processed query result, or default on error.
    """
    try:
        with get_session() as session:
            result = session.execute(text(query_str), params or {})
            return processor(result)
    except Exception as e:
        logger.error(f"Error in {context}: {e}" if context else f"Read query error: {e}")
        return default


def _execute_write(
    query_str: str,
    params: Optional[Dict[str, Any]] = None,
    context: str = "",
) -> bool:
    """
    Execute a write query with standard error handling.

    Args:
        query_str: SQL query string.
        params: Optional query parameters.
        context: Descriptive label for error logging (e.g. "record_alert_sent").

    Returns:
        True if successful, False on error.
    """
    try:
        with get_session() as session:
            session.execute(text(query_str), params or {})
        return True
    except Exception as e:
        logger.error(f"Error in {context}: {e}" if context else f"Write query error: {e}")
        return False
```

#### 3b. Refactor each function to use the helpers

Below are before/after for **every function** that changes. Functions are listed in order of appearance in the file.

---

**`get_subscription` (line 61-87) — read-single pattern**

Before:
```python
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
```

After:
```python
def get_subscription(chat_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a Telegram subscription by chat_id.

    Args:
        chat_id: Telegram chat ID.

    Returns:
        Subscription dict or None if not found.
    """
    return _execute_read(
        """
        SELECT
            id, chat_id, chat_type, username, first_name, last_name,
            title, is_active, subscribed_at, unsubscribed_at,
            alert_preferences, last_alert_at, alerts_sent_count,
            last_interaction_at, consecutive_errors, last_error,
            created_at, updated_at
        FROM telegram_subscriptions
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id)},
        processor=_row_to_dict,
        default=None,
        context=f"get_subscription(chat_id={chat_id})",
    )
```

---

**`get_active_subscriptions` (line 90-113) — read-list pattern**

Before:
```python
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
```

After:
```python
def get_active_subscriptions() -> List[Dict[str, Any]]:
    """
    Get all active Telegram subscriptions.

    Returns:
        List of subscription dicts.
    """
    return _execute_read(
        """
        SELECT
            id, chat_id, chat_type, username, first_name, last_name,
            title, is_active, subscribed_at, alert_preferences,
            last_alert_at, alerts_sent_count, consecutive_errors
        FROM telegram_subscriptions
        WHERE is_active = true
            AND consecutive_errors < 5
        ORDER BY subscribed_at ASC
        """,
        default=[],
        context="get_active_subscriptions",
    )
```

---

**`create_subscription` (line 116-186) — mixed read+write, requires custom logic**

This function has branching logic (check existing, reactivate, or insert). Only the INSERT portion at the end can use `_execute_write`. The function's outer try/except still wraps the entire flow because `get_subscription` is called first.

Before (lines 138-186, the try block body):
```python
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
```

After:
```python
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

        success = _execute_write(
            """
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
            """,
            params={
                "chat_id": str(chat_id),
                "chat_type": chat_type,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "alert_preferences": json.dumps(default_prefs),
            },
            context=f"create_subscription(chat_id={chat_id})",
        )
        if success:
            logger.info(f"Created Telegram subscription for chat_id {chat_id}")
        return success
    except Exception as e:
        logger.error(f"Error creating subscription for chat_id {chat_id}: {e}")
        return False
```

---

**`update_subscription` (line 189-228) — write with validation, keeps custom logic**

This function has the `_UPDATABLE_COLUMNS` validation and dynamic SET clause construction. The validation logic cannot be moved into a generic helper without losing clarity. **Leave this function unchanged.** It already has thorough test coverage.

---

**`record_alert_sent` (line 238-254) — write pattern**

Before:
```python
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
```

After:
```python
def record_alert_sent(chat_id: str) -> bool:
    """Record that an alert was sent to this subscription."""
    return _execute_write(
        """
        UPDATE telegram_subscriptions
        SET last_alert_at = NOW(),
            alerts_sent_count = alerts_sent_count + 1,
            consecutive_errors = 0,
            updated_at = NOW()
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id)},
        context=f"record_alert_sent(chat_id={chat_id})",
    )
```

---

**`record_error` (line 257-274) — write pattern**

Before:
```python
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
```

After:
```python
def record_error(chat_id: str, error_message: str) -> bool:
    """Record an error for this subscription."""
    return _execute_write(
        """
        UPDATE telegram_subscriptions
        SET consecutive_errors = consecutive_errors + 1,
            last_error = :error_message,
            updated_at = NOW()
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id), "error_message": error_message},
        context=f"record_error(chat_id={chat_id})",
    )
```

---

**`get_subscription_stats` (line 277-295) — read-single with fallback**

Before:
```python
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
```

After:
```python
def get_subscription_stats() -> Dict[str, Any]:
    """Get statistics about Telegram subscriptions."""
    result = _execute_read(
        """
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active,
            COUNT(CASE WHEN chat_type = 'private' THEN 1 END) as private_chats,
            COUNT(CASE WHEN chat_type IN ('group', 'supergroup') THEN 1 END) as groups,
            COUNT(CASE WHEN chat_type = 'channel' THEN 1 END) as channels,
            SUM(alerts_sent_count) as total_alerts_sent
        FROM telegram_subscriptions
        """,
        processor=_row_to_dict,
        default=None,
        context="get_subscription_stats",
    )
    return result or {}
```

---

**`get_new_predictions_since` (line 303-350) — read-list with post-processing**

This function does post-processing (datetime serialization) after the query. It cannot fully collapse into `_execute_read` without a custom processor. Use `_execute_read` for the query, then do the post-processing outside.

Before:
```python
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
```

After:
```python
def get_new_predictions_since(since: datetime) -> List[Dict[str, Any]]:
    """
    Get new completed predictions created after the given timestamp.

    Args:
        since: Only return predictions created after this timestamp.

    Returns:
        List of prediction dicts with associated shitpost data.
    """
    results = _execute_read(
        """
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
        """,
        params={"since": since},
        default=[],
        context="get_new_predictions_since",
    )
    for row_dict in results:
        if isinstance(row_dict.get("timestamp"), datetime):
            row_dict["timestamp"] = row_dict["timestamp"].isoformat()
        if isinstance(row_dict.get("prediction_created_at"), datetime):
            row_dict["prediction_created_at"] = row_dict[
                "prediction_created_at"
            ].isoformat()
    return results
```

---

**`get_prediction_stats` (line 353-389) — read-single with computation**

Before:
```python
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
```

After:
```python
def get_prediction_stats() -> Dict[str, Any]:
    """
    Get overall prediction accuracy statistics from prediction_outcomes.

    Returns:
        Dict with accuracy, win_rate, total_pnl, total_predictions.
    """
    row = _execute_read(
        """
        SELECT
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_count,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_count,
            COALESCE(SUM(return_t7), 0) as total_return
        FROM prediction_outcomes
        """,
        processor=_row_to_dict,
        default=None,
        context="get_prediction_stats",
    )
    if not row:
        return {}

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
```

---

**`get_latest_predictions` (line 392-431) — read-list with post-processing**

Before:
```python
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
```

After:
```python
def get_latest_predictions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent completed predictions with outcome data.

    Args:
        limit: Number of predictions to return.

    Returns:
        List of prediction dicts with outcome status.
    """
    results = _execute_read(
        """
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
        """,
        params={"limit": limit},
        default=[],
        context="get_latest_predictions",
    )
    for row_dict in results:
        if isinstance(row_dict.get("created_at"), datetime):
            row_dict["created_at"] = row_dict["created_at"].isoformat()
    return results
```

---

**`get_last_alert_check` (line 439-461) — custom read (uses fetchone, not fetchall)**

This function uses `result.fetchone()` directly instead of `_row_to_dict` or `_rows_to_dicts`. It requires a custom processor to work with `_execute_read`.

Before:
```python
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
```

After:
```python
def _extract_scalar(result) -> Any:
    """Extract a single scalar value from a query result."""
    row = result.fetchone()
    if row and row[0]:
        return row[0]
    return None


def get_last_alert_check() -> Optional[datetime]:
    """
    Get the timestamp of the last alert check from the database.

    Uses the most recent last_alert_at across all active subscriptions as a proxy.
    """
    return _execute_read(
        """
        SELECT MAX(last_alert_at) as last_check
        FROM telegram_subscriptions
        WHERE is_active = true
        """,
        processor=_extract_scalar,
        default=None,
        context="get_last_alert_check",
    )
```

Note: `_extract_scalar` is added as a private helper alongside `_row_to_dict` and `_rows_to_dicts`. Place it right after `_rows_to_dicts` (after line 33) and before `_execute_read`.

### Step 4: Run the tests again after refactoring

Run:
```bash
./venv/bin/python -m pytest shit_tests/notifications/test_db.py -v
```

All 62 tests must still pass. If any fail, the refactor introduced a regression -- fix before proceeding.

### Step 5: Run the full test suite

Run:
```bash
./venv/bin/python -m pytest -v
```

Verify no tests outside `shit_tests/notifications/` broke.

### Step 6: Run linting and formatting

```bash
./venv/bin/python -m ruff check notifications/db.py shit_tests/notifications/test_db.py
./venv/bin/python -m ruff format notifications/db.py shit_tests/notifications/test_db.py
```

---

## Complete Final State of `notifications/db.py`

For absolute clarity, here is the full file after all changes:

```python
"""
Database operations for the notifications module.

Handles subscription CRUD, alert history, and last-check timestamp persistence.
Uses the project's sync session pattern from shit/db/sync_session.py.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("notifications_db")


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


def _extract_scalar(result) -> Any:
    """Extract a single scalar value from a query result."""
    row = result.fetchone()
    if row and row[0]:
        return row[0]
    return None


def _execute_read(
    query_str: str,
    params: Optional[Dict[str, Any]] = None,
    processor=_rows_to_dicts,
    default: Any = None,
    context: str = "",
) -> Any:
    """
    Execute a read query with standard error handling.

    Args:
        query_str: SQL query string.
        params: Optional query parameters.
        processor: Function to process the result (default: _rows_to_dicts).
                   Use _row_to_dict for single-row queries.
        default: Value to return on error or empty result.
        context: Descriptive label for error logging (e.g. "get_subscription").

    Returns:
        Processed query result, or default on error.
    """
    try:
        with get_session() as session:
            result = session.execute(text(query_str), params or {})
            return processor(result)
    except Exception as e:
        logger.error(f"Error in {context}: {e}" if context else f"Read query error: {e}")
        return default


def _execute_write(
    query_str: str,
    params: Optional[Dict[str, Any]] = None,
    context: str = "",
) -> bool:
    """
    Execute a write query with standard error handling.

    Args:
        query_str: SQL query string.
        params: Optional query parameters.
        context: Descriptive label for error logging (e.g. "record_alert_sent").

    Returns:
        True if successful, False on error.
    """
    try:
        with get_session() as session:
            session.execute(text(query_str), params or {})
        return True
    except Exception as e:
        logger.error(f"Error in {context}: {e}" if context else f"Write query error: {e}")
        return False


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
    return _execute_read(
        """
        SELECT
            id, chat_id, chat_type, username, first_name, last_name,
            title, is_active, subscribed_at, unsubscribed_at,
            alert_preferences, last_alert_at, alerts_sent_count,
            last_interaction_at, consecutive_errors, last_error,
            created_at, updated_at
        FROM telegram_subscriptions
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id)},
        processor=_row_to_dict,
        default=None,
        context=f"get_subscription(chat_id={chat_id})",
    )


def get_active_subscriptions() -> List[Dict[str, Any]]:
    """
    Get all active Telegram subscriptions.

    Returns:
        List of subscription dicts.
    """
    return _execute_read(
        """
        SELECT
            id, chat_id, chat_type, username, first_name, last_name,
            title, is_active, subscribed_at, alert_preferences,
            last_alert_at, alerts_sent_count, consecutive_errors
        FROM telegram_subscriptions
        WHERE is_active = true
            AND consecutive_errors < 5
        ORDER BY subscribed_at ASC
        """,
        default=[],
        context="get_active_subscriptions",
    )


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

        success = _execute_write(
            """
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
            """,
            params={
                "chat_id": str(chat_id),
                "chat_type": chat_type,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "title": title,
                "alert_preferences": json.dumps(default_prefs),
            },
            context=f"create_subscription(chat_id={chat_id})",
        )
        if success:
            logger.info(f"Created Telegram subscription for chat_id {chat_id}")
        return success
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
    return _execute_write(
        """
        UPDATE telegram_subscriptions
        SET last_alert_at = NOW(),
            alerts_sent_count = alerts_sent_count + 1,
            consecutive_errors = 0,
            updated_at = NOW()
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id)},
        context=f"record_alert_sent(chat_id={chat_id})",
    )


def record_error(chat_id: str, error_message: str) -> bool:
    """Record an error for this subscription."""
    return _execute_write(
        """
        UPDATE telegram_subscriptions
        SET consecutive_errors = consecutive_errors + 1,
            last_error = :error_message,
            updated_at = NOW()
        WHERE chat_id = :chat_id
        """,
        params={"chat_id": str(chat_id), "error_message": error_message},
        context=f"record_error(chat_id={chat_id})",
    )


def get_subscription_stats() -> Dict[str, Any]:
    """Get statistics about Telegram subscriptions."""
    result = _execute_read(
        """
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active,
            COUNT(CASE WHEN chat_type = 'private' THEN 1 END) as private_chats,
            COUNT(CASE WHEN chat_type IN ('group', 'supergroup') THEN 1 END) as groups,
            COUNT(CASE WHEN chat_type = 'channel' THEN 1 END) as channels,
            SUM(alerts_sent_count) as total_alerts_sent
        FROM telegram_subscriptions
        """,
        processor=_row_to_dict,
        default=None,
        context="get_subscription_stats",
    )
    return result or {}


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
    results = _execute_read(
        """
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
        """,
        params={"since": since},
        default=[],
        context="get_new_predictions_since",
    )
    for row_dict in results:
        if isinstance(row_dict.get("timestamp"), datetime):
            row_dict["timestamp"] = row_dict["timestamp"].isoformat()
        if isinstance(row_dict.get("prediction_created_at"), datetime):
            row_dict["prediction_created_at"] = row_dict[
                "prediction_created_at"
            ].isoformat()
    return results


def get_prediction_stats() -> Dict[str, Any]:
    """
    Get overall prediction accuracy statistics from prediction_outcomes.

    Returns:
        Dict with accuracy, win_rate, total_pnl, total_predictions.
    """
    row = _execute_read(
        """
        SELECT
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_count,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_count,
            COALESCE(SUM(return_t7), 0) as total_return
        FROM prediction_outcomes
        """,
        processor=_row_to_dict,
        default=None,
        context="get_prediction_stats",
    )
    if not row:
        return {}

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


def get_latest_predictions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get the most recent completed predictions with outcome data.

    Args:
        limit: Number of predictions to return.

    Returns:
        List of prediction dicts with outcome status.
    """
    results = _execute_read(
        """
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
        """,
        params={"limit": limit},
        default=[],
        context="get_latest_predictions",
    )
    for row_dict in results:
        if isinstance(row_dict.get("created_at"), datetime):
            row_dict["created_at"] = row_dict["created_at"].isoformat()
    return results


# ============================================================
# Last check timestamp persistence
# ============================================================


def get_last_alert_check() -> Optional[datetime]:
    """
    Get the timestamp of the last alert check from the database.

    Uses the most recent last_alert_at across all active subscriptions as a proxy.
    """
    return _execute_read(
        """
        SELECT MAX(last_alert_at) as last_check
        FROM telegram_subscriptions
        WHERE is_active = true
        """,
        processor=_extract_scalar,
        default=None,
        context="get_last_alert_check",
    )
```

---

## Test Plan

### New tests added (54 tests across 14 test classes)

| Class | Tests | What it verifies |
|---|---|---|
| `TestRowToDict` | 4 | Single row, multiple rows (first returned), empty, None values |
| `TestRowsToDicts` | 3 | Multiple rows, empty, single row |
| `TestGetSubscription` | 4 | Found, not found, database error, int→str coercion |
| `TestGetActiveSubscriptions` | 3 | List returned, empty, database error |
| `TestCreateSubscription` | 5 | New creation, reactivation, already active, DB error, default None params |
| `TestUpdateSubscription` | 5 | JSON serialization, string pass-through, multi-column, DB error, invalid column |
| `TestDeactivateSubscription` | 2 | Sets is_active=False, error case |
| `TestRecordAlertSent` | 3 | Success, int→str coercion, DB error |
| `TestRecordError` | 3 | Success, params passed correctly, DB error |
| `TestGetSubscriptionStats` | 3 | Stats dict, empty table, DB error |
| `TestGetNewPredictionsSince` | 5 | Results returned, datetime serialization, string not converted, empty, DB error |
| `TestGetPredictionStats` | 5 | Computed stats, zero-division safety, None values, no rows, DB error |
| `TestGetLatestPredictions` | 5 | Results with outcomes, datetime serialization, limit param, default limit, DB error |
| `TestGetLastAlertCheck` | 4 | datetime returned, NULL → None, no rows → None, DB error |

### Existing tests preserved (8 tests across 2 test classes)

| Class | Tests |
|---|---|
| `TestUpdatableColumnsWhitelist` | 3 |
| `TestUpdateSubscriptionInjectionPrevention` | 5 |

### Coverage expectations

Before: ~15% coverage of `notifications/db.py` (only `update_subscription` and `_UPDATABLE_COLUMNS`)

After: ~95%+ coverage. Every public function has at least:
- Happy path test
- Error/exception test
- Edge case test (empty results, None values, type coercion)

### Running tests

```bash
# Just the notifications tests
./venv/bin/python -m pytest shit_tests/notifications/test_db.py -v

# Full test suite
./venv/bin/python -m pytest -v

# With coverage for notifications/db.py
./venv/bin/python -m pytest shit_tests/notifications/test_db.py --cov=notifications.db --cov-report=term-missing
```

---

## Documentation Updates

### Inline comments
- The new `_execute_read` and `_execute_write` helpers have full docstrings explaining args and return values.
- The `_extract_scalar` helper has a docstring.
- The `get_last_alert_check` docstring is updated (removed reference to "notification_state table").

### No external documentation changes needed
- This is an internal refactor with test additions. No README, API doc, or user-facing documentation changes.

---

## Stress Testing & Edge Cases

### Edge cases handled by tests

1. **`_row_to_dict` with multiple rows**: Only the first row is returned (matches current behavior).
2. **`get_subscription` with int chat_id**: Coerced to string before query.
3. **`create_subscription` for already-active sub**: Returns True immediately, no INSERT.
4. **`create_subscription` for inactive sub**: Calls `update_subscription` to reactivate.
5. **`update_subscription` with dict alert_preferences**: JSON-serialized before query.
6. **`update_subscription` with string alert_preferences**: Passed as-is (no double-serialization).
7. **`get_prediction_stats` with zero evaluated**: Division by zero avoided, returns 0.0.
8. **`get_prediction_stats` with None DB values**: `or 0` fallback prevents TypeError.
9. **`get_new_predictions_since` with string timestamps**: Left as-is (isinstance check).
10. **`get_last_alert_check` with NULL max**: Returns None, not an error.

### Error scenarios

Every function that touches the database is tested with a mock that raises `Exception`. The expected behavior is:
- Read functions return their default (None, [], or {})
- Write functions return False
- Errors are logged (verified by the fact that no exception propagates)

---

## Verification Checklist

- [ ] All 62 tests pass: `./venv/bin/python -m pytest shit_tests/notifications/test_db.py -v`
- [ ] Full test suite passes: `./venv/bin/python -m pytest -v`
- [ ] Linting passes: `./venv/bin/python -m ruff check notifications/db.py shit_tests/notifications/test_db.py`
- [ ] Formatting passes: `./venv/bin/python -m ruff format --check notifications/db.py shit_tests/notifications/test_db.py`
- [ ] No new imports added to conftest (existing `mock_sync_session` autouse fixture is sufficient)
- [ ] `_execute_read` and `_execute_write` are private (underscore prefix)
- [ ] `_extract_scalar` is private (underscore prefix)
- [ ] `update_subscription` is NOT refactored (keeps its custom validation logic)
- [ ] `create_subscription` outer try/except is preserved (wraps get_subscription + _execute_write)
- [ ] All public function signatures are unchanged (no breaking changes)
- [ ] All return types are unchanged (no behavioral changes)
- [ ] Coverage of `notifications/db.py` is 95%+ (run with `--cov=notifications.db`)

---

## What NOT To Do

1. **Do NOT refactor `update_subscription` to use `_execute_write`.** It has custom validation logic (column whitelist, dynamic SET clause) that does not fit the generic helper pattern. The dynamic `text(f"...")` construction requires the session to be in the same scope as the validation. Leave it as-is.

2. **Do NOT make `_execute_read`/`_execute_write` public.** They are internal helpers for this module only. Other modules (`api/dependencies.py`, `shitty_ui/data/base.py`) have their own query execution patterns.

3. **Do NOT change the `mock_sync_session` conftest fixture.** It works correctly as-is. The fixture yields the mock session, and `__enter__` returns the same mock, so `session.execute(...)` calls land on the mock. Adding complexity here will break existing tests.

4. **Do NOT add `_execute_read`/`_execute_write` to test imports.** Tests should test public function behavior, not internal helpers. The helpers are tested implicitly through the public functions that use them.

5. **Do NOT change default return values.** Each function has a specific default (`None`, `[]`, `{}`, `False`). The refactored versions must return the same defaults. Pay special attention to `get_subscription_stats()` which returns `{}` on error, and `get_new_predictions_since()` which returns `[]`.

6. **Do NOT remove the `text()` import.** Even though most functions no longer call `text()` directly, `update_subscription` still uses it, and `_execute_read`/`_execute_write` use it internally.

7. **Do NOT add type annotations to the `processor` parameter of `_execute_read`.** The processors (`_row_to_dict`, `_rows_to_dicts`, `_extract_scalar`) have different return types. Using `Callable` with a union would add complexity without value. The default `_rows_to_dicts` is sufficient documentation.

8. **Do NOT write tests before reading the file.** Step 1 says to write tests, but the implementation plan assumes you have already read the source. If implementing, read `notifications/db.py` first to understand current behavior, then write tests, then refactor.

9. **Do NOT change the order of functions in `db.py`.** Keep the same logical grouping: helpers at top, subscription CRUD in the middle, alert queries below, last-check at the bottom. The new helpers (`_extract_scalar`, `_execute_read`, `_execute_write`) go between the existing helpers and `_UPDATABLE_COLUMNS`.
