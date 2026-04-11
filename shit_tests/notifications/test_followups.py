"""Tests for 'What Happened' follow-up messages (Feature 08)."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from notifications.followups import (
    _is_data_available,
    _is_horizon_due,
    _should_abandon,
    create_followup_tracking,
    format_followup_message,
    process_due_followups,
)
from notifications.telegram_bot import handle_followups_command, process_update


# ============================================================
# Follow-up Creation Tests
# ============================================================


class TestCreateFollowupTracking:
    """Test follow-up row creation."""

    @patch("notifications.followups._execute_write")
    def test_creates_with_correct_params(self, mock_write):
        mock_write.return_value = True
        now = datetime(2026, 4, 9, 14, 0, tzinfo=timezone.utc)
        result = create_followup_tracking(
            prediction_id=42, chat_id="123", alert_sent_at=now
        )
        assert result is True
        call_args = mock_write.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert params["prediction_id"] == 42
        assert params["chat_id"] == "123"
        # First check should be alert_time + 65 minutes
        expected_check = now + timedelta(minutes=65)
        assert params["next_check_at"] == expected_check

    @patch("notifications.followups._execute_write")
    def test_idempotent_on_conflict(self, mock_write):
        """ON CONFLICT DO NOTHING means duplicates are safe."""
        mock_write.return_value = True
        now = datetime(2026, 4, 9, 14, 0, tzinfo=timezone.utc)
        create_followup_tracking(42, "123", now)
        create_followup_tracking(42, "123", now)
        assert mock_write.call_count == 2  # Both calls execute, DB handles dedup


# ============================================================
# Data Availability Tests
# ============================================================


class TestDataAvailability:
    """Test data availability checks."""

    def test_1h_available(self):
        outcome = {"return_1h": -0.8}
        assert _is_data_available(outcome, "1h") is True

    def test_1h_not_available(self):
        outcome = {"return_1h": None}
        assert _is_data_available(outcome, "1h") is False

    def test_1d_available(self):
        outcome = {"return_t1": -1.2}
        assert _is_data_available(outcome, "1d") is True

    def test_7d_not_available(self):
        outcome = {"return_t7": None}
        assert _is_data_available(outcome, "7d") is False

    def test_abandon_after_max_deferral(self):
        """After expected time + 48h, abandon the horizon."""
        alert_time = datetime.now(timezone.utc) - timedelta(
            hours=100
        )  # Well past 1h + 48h
        followup = {"original_alert_sent_at": alert_time}
        assert _should_abandon(followup, "1h") is True

    def test_no_abandon_within_window(self):
        alert_time = datetime.now(timezone.utc) - timedelta(hours=1)
        followup = {"original_alert_sent_at": alert_time}
        assert _should_abandon(followup, "1h") is False


# ============================================================
# Horizon Due Tests
# ============================================================


class TestIsHorizonDue:
    """Test horizon due logic."""

    def test_1h_due_after_1_hour(self):
        alert_time = datetime.now(timezone.utc) - timedelta(hours=1, minutes=5)
        followup = {"original_alert_sent_at": alert_time, "sent_1h": None}
        assert _is_horizon_due(followup, "1h") is True

    def test_1h_not_due_too_early(self):
        alert_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        followup = {"original_alert_sent_at": alert_time, "sent_1h": None}
        assert _is_horizon_due(followup, "1h") is False

    def test_already_sent_not_due(self):
        alert_time = datetime.now(timezone.utc) - timedelta(hours=2)
        followup = {"original_alert_sent_at": alert_time, "sent_1h": True}
        assert _is_horizon_due(followup, "1h") is False

    def test_abandoned_not_due(self):
        alert_time = datetime.now(timezone.utc) - timedelta(hours=2)
        followup = {"original_alert_sent_at": alert_time, "sent_1h": False}
        assert _is_horizon_due(followup, "1h") is False

    def test_1d_due_after_20_hours(self):
        alert_time = datetime.now(timezone.utc) - timedelta(hours=21)
        followup = {"original_alert_sent_at": alert_time, "sent_1d": None}
        assert _is_horizon_due(followup, "1d") is True

    def test_7d_due_after_9_days(self):
        alert_time = datetime.now(timezone.utc) - timedelta(days=10)
        followup = {"original_alert_sent_at": alert_time, "sent_7d": None}
        assert _is_horizon_due(followup, "7d") is True


# ============================================================
# Message Formatting Tests
# ============================================================


class TestFormatFollowupMessage:
    """Test follow-up message formatting."""

    def test_1h_single_asset_correct(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_1h_after": 243.20,
                "return_1h": -0.9,
                "correct_1h": True,
                "pnl_1h": 9.0,
            }
        ]
        message = format_followup_message("1h", outcomes)
        assert "UPDATE" in message
        assert "TSLA" in message
        assert "CORRECT" in message
        assert "1 hour later" in message

    def test_1h_single_asset_incorrect(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_1h_after": 247.10,
                "return_1h": 0.7,
                "correct_1h": False,
                "pnl_1h": -7.0,
            }
        ]
        message = format_followup_message("1h", outcomes)
        assert "INCORRECT" in message

    def test_1d_with_pnl(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_t1": 241.30,
                "return_t1": -1.7,
                "correct_t1": True,
                "pnl_t1": 17.10,
            }
        ]
        message = format_followup_message("1d", outcomes)
        assert "VERDICT" in message
        assert "P&L" in message
        assert "gained" in message
        assert "17" in message

    def test_7d_final_result(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_t7": 237.20,
                "return_t7": -3.4,
                "correct_t7": True,
                "pnl_t7": 33.80,
            }
        ]
        message = format_followup_message("7d", outcomes)
        assert "FINAL RESULT" in message
        assert "7 trading days" in message

    def test_multi_asset(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_t1": 241.30,
                "return_t1": -1.7,
                "correct_t1": True,
                "pnl_t1": 17.10,
            },
            {
                "symbol": "F",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.78,
                "price_at_post": 12.80,
                "price_t1": 12.65,
                "return_t1": -1.2,
                "correct_t1": True,
                "pnl_t1": 11.70,
            },
        ]
        message = format_followup_message("1d", outcomes)
        assert "2 assets" in message
        assert "TSLA" in message
        assert "F:" in message  # Note: "F" with colon
        assert "Overall" in message

    def test_escapes_markdown(self):
        outcomes = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_1h_after": 243.20,
                "return_1h": -0.9,
                "correct_1h": True,
                "pnl_1h": 9.0,
            }
        ]
        message = format_followup_message("1h", outcomes)
        # Dots and parens should be escaped in MarkdownV2
        assert "\\." in message
        assert "\\(" in message

    def test_1d_loss_pnl(self):
        outcomes = [
            {
                "symbol": "META",
                "prediction_sentiment": "bullish",
                "prediction_confidence": 0.73,
                "price_at_post": 500.00,
                "price_t1": 496.00,
                "return_t1": -0.8,
                "correct_t1": False,
                "pnl_t1": -8.00,
            }
        ]
        message = format_followup_message("1d", outcomes)
        assert "lost" in message

    def test_footer_present(self):
        outcomes = [
            {
                "symbol": "SPY",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.80,
                "price_at_post": 500.00,
                "price_1h_after": 499.00,
                "return_1h": -0.2,
                "correct_1h": True,
                "pnl_1h": 2.0,
            }
        ]
        message = format_followup_message("1h", outcomes)
        assert "/followups off" in message


# ============================================================
# /followups Command Tests
# ============================================================


class TestFollowupsCommand:
    """Test /followups bot command."""

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed(self, mock_get_sub):
        mock_get_sub.return_value = None
        result = handle_followups_command("123")
        assert "not subscribed" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_followups_off(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"followups_enabled": True}}
        mock_update.return_value = True
        result = handle_followups_command("123", "off")
        assert "disabled" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_followups_on(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"followups_enabled": False}}
        mock_update.return_value = True
        result = handle_followups_command("123", "on")
        assert "enabled" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_followups_status(self, mock_get_sub):
        mock_get_sub.return_value = {
            "alert_preferences": {
                "followups_enabled": True,
                "followup_horizons": ["1h", "1d", "7d"],
            }
        }
        result = handle_followups_command("123")
        assert "enabled" in result
        assert "1h" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_selective_horizons(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {}}
        mock_update.return_value = True
        result = handle_followups_command("123", "1h,7d")
        assert "1h" in result
        assert "7d" in result
        call_args = mock_update.call_args
        prefs = call_args[1]["alert_preferences"]
        assert prefs["followup_horizons"] == ["1h", "7d"]

    @patch("notifications.telegram_bot.get_subscription")
    def test_default_enabled(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {}}
        result = handle_followups_command("123")
        assert "enabled" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_json_string_prefs(self, mock_get_sub):
        mock_get_sub.return_value = {
            "alert_preferences": json.dumps({"followups_enabled": True})
        }
        result = handle_followups_command("123")
        assert "enabled" in result


# ============================================================
# Process Due Follow-ups Tests
# ============================================================


class TestProcessDueFollowups:
    """Test process_due_followups orchestrator."""

    @patch("notifications.followups.get_due_followups")
    def test_empty_returns_zeros(self, mock_due):
        mock_due.return_value = []
        results = process_due_followups()
        assert results["checked"] == 0
        assert results["sent"] == 0

    @patch("notifications.followups.time_module")
    @patch("notifications.followups.send_telegram_message")
    @patch("notifications.followups._get_subscriber_prefs")
    @patch("notifications.followups._check_daily_limit")
    @patch("notifications.followups.get_followup_outcomes")
    @patch("notifications.followups._update_followup_sent")
    @patch("notifications.followups._defer_followup")
    @patch("notifications.followups.get_due_followups")
    def test_sends_when_data_available(
        self,
        mock_due,
        mock_defer,
        mock_update_sent,
        mock_outcomes,
        mock_limit,
        mock_prefs,
        mock_send,
        mock_time,
    ):
        now = datetime.now(timezone.utc)
        mock_due.return_value = [
            {
                "id": 1,
                "prediction_id": 42,
                "chat_id": "123",
                "sent_1h": None,
                "sent_1d": None,
                "sent_7d": None,
                "original_alert_sent_at": now - timedelta(hours=2),
                "next_check_at": now - timedelta(minutes=5),
                "assets": ["TSLA"],
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "calibrated_confidence": None,
                "post_text": "Bad news",
            }
        ]
        mock_limit.return_value = True
        mock_prefs.return_value = {
            "followups_enabled": True,
            "followup_horizons": ["1h", "1d", "7d"],
        }
        mock_outcomes.return_value = [
            {
                "symbol": "TSLA",
                "prediction_sentiment": "bearish",
                "prediction_confidence": 0.85,
                "price_at_post": 245.50,
                "price_1h_after": 243.20,
                "return_1h": -0.9,
                "correct_1h": True,
                "pnl_1h": 9.0,
                "return_t1": None,
                "return_t7": None,
            }
        ]
        mock_send.return_value = (True, None)
        mock_update_sent.return_value = True

        results = process_due_followups()
        assert results["sent"] == 1
        mock_send.assert_called_once()
        mock_update_sent.assert_called_once()

    @patch("notifications.followups._check_daily_limit")
    @patch("notifications.followups.get_due_followups")
    def test_respects_daily_limit(self, mock_due, mock_limit):
        now = datetime.now(timezone.utc)
        mock_due.return_value = [
            {
                "id": 1,
                "prediction_id": 42,
                "chat_id": "123",
                "sent_1h": None,
                "sent_1d": None,
                "sent_7d": None,
                "original_alert_sent_at": now - timedelta(hours=2),
                "next_check_at": now,
            }
        ]
        mock_limit.return_value = False  # Limit reached

        results = process_due_followups()
        assert results["skipped"] == 1
        assert results["sent"] == 0


# ============================================================
# Process Update Routing Tests
# ============================================================


class TestProcessUpdateFollowups:
    """Test /followups routing through process_update."""

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.get_subscription")
    def test_routes_to_followups_handler(self, mock_get_sub, mock_send):
        mock_get_sub.return_value = {"alert_preferences": {"followups_enabled": True}}
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"username": "testuser"},
                "text": "/followups",
            }
        }
        result = process_update(update)
        assert result is not None
        assert "enabled" in result
