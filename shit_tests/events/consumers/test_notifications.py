"""Tests for the NotificationsWorker event consumer."""

import json
from unittest.mock import patch

from notifications.event_consumer import NotificationsWorker
from shit.events.event_types import ConsumerGroup


class TestNotificationsWorker:
    """Tests for NotificationsWorker.process_event()."""

    def test_consumer_group_is_notifications(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: NotificationsWorker.consumer_group == ConsumerGroup.NOTIFICATIONS
        Mocking: None.
        Assertions: consumer_group attribute matches the NOTIFICATIONS constant.
        """
        assert NotificationsWorker.consumer_group == ConsumerGroup.NOTIFICATIONS

    def test_skip_non_completed_analysis(self):
        """Verify events with analysis_status != 'completed' are skipped.

        What it verifies: When analysis_status is "bypassed", the worker returns
        immediately with skipped=True and does not query subscribers.
        Mocking: None (early return before any imports/calls).
        Assertions:
          - Return dict has skipped=True
          - Return dict has reason containing "status=bypassed"
        """
        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "bypassed",
                "assets": ["TSLA"],
            },
        )

        assert result["skipped"] is True
        assert "bypassed" in result["reason"]

    def test_skip_error_analysis_status(self):
        """Verify events with analysis_status='error' are skipped.

        What it verifies: Same early-return logic for error status.
        Mocking: None.
        Assertions: skipped=True, reason contains "error".
        """
        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {"prediction_id": 99, "analysis_status": "error", "assets": []},
        )

        assert result["skipped"] is True
        assert "error" in result["reason"]

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    @patch("notifications.db.record_alert_sent")
    @patch("notifications.db.record_error")
    @patch("notifications.db.get_active_subscriptions")
    @patch("notifications.alert_engine.filter_predictions_by_preferences")
    def test_no_subscribers_returns_zero_alerts(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that when there are no active subscribers, no alerts are sent.

        What it verifies: get_active_subscriptions returns [], so the loop is
        never entered and results show 0 across the board.
        Mocking:
          - get_active_subscriptions returns []
        Assertions:
          - alerts_sent=0, alerts_failed=0, filtered=0
          - filter_predictions_by_preferences was NOT called
          - send_telegram_message was NOT called
        """
        mock_get_subs.return_value = []

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result == {"alerts_sent": 0, "alerts_failed": 0, "filtered": 0}
        mock_filter.assert_not_called()
        mock_send.assert_not_called()

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    @patch("notifications.db.record_alert_sent")
    @patch("notifications.db.record_error")
    @patch("notifications.db.get_active_subscriptions")
    @patch("notifications.alert_engine.filter_predictions_by_preferences")
    def test_successful_dispatch_to_subscriber(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify successful alert dispatch to a single subscriber.

        What it verifies: When a subscriber exists and the alert matches their
        preferences, format + send + record_alert_sent are all called.
        Mocking:
          - get_active_subscriptions returns 1 subscriber with chat_id=12345
          - filter_predictions_by_preferences returns the alert (match)
          - format_telegram_alert returns a message string
          - send_telegram_message returns (True, None)
        Assertions:
          - alerts_sent=1, alerts_failed=0, filtered=0
          - send_telegram_message called with chat_id=12345
          - record_alert_sent called with chat_id=12345
        """
        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": {"min_confidence": 0.5}},
        ]
        mock_filter.return_value = [{"prediction_id": 99, "confidence": 0.85}]
        mock_format.return_value = "Alert: TSLA prediction"
        mock_send.return_value = (True, None)

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result["alerts_sent"] == 1
        assert result["alerts_failed"] == 0
        assert result["filtered"] == 0
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == 12345
        assert call_args[0][1] == "Alert: TSLA prediction"
        # reply_markup is passed as keyword arg when prediction_id is present
        assert "reply_markup" in call_args[1]
        mock_record_sent.assert_called_once_with(12345)

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    @patch("notifications.db.record_alert_sent")
    @patch("notifications.db.record_error")
    @patch("notifications.db.get_active_subscriptions")
    @patch("notifications.alert_engine.filter_predictions_by_preferences")
    def test_filtered_subscriber_not_dispatched(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that subscribers whose preferences don't match are filtered out.

        What it verifies: When filter_predictions_by_preferences returns [],
        the subscriber is counted as "filtered" and no message is sent.
        Mocking:
          - get_active_subscriptions returns 1 subscriber
          - filter_predictions_by_preferences returns [] (no match)
        Assertions:
          - alerts_sent=0, filtered=1
          - send_telegram_message was NOT called
        """
        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": {"min_confidence": 0.99}},
        ]
        mock_filter.return_value = []  # No match

        worker = NotificationsWorker.__new__(NotificationsWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        assert result["filtered"] == 1
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("notifications.telegram_sender.send_telegram_message")
    @patch("notifications.telegram_sender.format_telegram_alert")
    @patch("notifications.db.record_alert_sent")
    @patch("notifications.db.record_error")
    @patch("notifications.db.get_active_subscriptions")
    @patch("notifications.alert_engine.filter_predictions_by_preferences")
    def test_json_string_preferences_parsed(
        self,
        mock_filter,
        mock_get_subs,
        mock_record_error,
        mock_record_sent,
        mock_format,
        mock_send,
    ):
        """Verify that alert_preferences stored as a JSON string are parsed.

        What it verifies: When alert_preferences is a string (as can happen with
        some database drivers), it's json.loads()-ed before passing to
        filter_predictions_by_preferences. (See lines 76-80 of the source.)
        Mocking:
          - get_active_subscriptions returns subscriber with string prefs
          - filter_predictions_by_preferences receives the parsed dict
        Assertions:
          - filter_predictions_by_preferences called with a dict (not a string)
        """
        prefs_dict = {"min_confidence": 0.5, "assets": ["TSLA"]}
        prefs_string = json.dumps(prefs_dict)

        mock_get_subs.return_value = [
            {"chat_id": 12345, "alert_preferences": prefs_string},
        ]
        mock_filter.return_value = [{"prediction_id": 99}]
        mock_format.return_value = "Alert message"
        mock_send.return_value = (True, None)

        worker = NotificationsWorker.__new__(NotificationsWorker)
        worker.process_event(
            "prediction_created",
            {
                "prediction_id": 99,
                "analysis_status": "completed",
                "assets": ["TSLA"],
                "confidence": 0.85,
            },
        )

        # Verify filter was called with the parsed dict, not the raw string
        filter_call_args = mock_filter.call_args
        prefs_arg = filter_call_args[0][1]  # Second positional arg
        assert isinstance(prefs_arg, dict)
        assert prefs_arg == prefs_dict
