"""Tests for pre-market morning briefing (Feature 07)."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from notifications.briefing import (
    ET,
    aggregate_by_asset,
    format_briefing_message,
    is_briefing_day,
    is_briefing_time,
    send_morning_briefing,
)
from notifications.telegram_bot import handle_briefing_command, process_update


# ============================================================
# Aggregation Tests
# ============================================================


class TestAggregateByAsset:
    """Test aggregate_by_asset()."""

    def test_single_asset(self):
        predictions = [
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "post_text": "Tesla is failing",
            },
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.78,
                "post_text": "EV market crashing",
            },
        ]
        result = aggregate_by_asset(predictions)
        assert "TSLA" in result
        assert result["TSLA"]["count"] == 2
        assert result["TSLA"]["sentiment"] == "bearish"
        assert result["TSLA"]["avg_confidence"] == pytest.approx(0.815)

    def test_multiple_assets_sorted_by_count(self):
        predictions = [
            {
                "market_impact": {"TSLA": "bearish", "F": "neutral"},
                "confidence": 0.85,
                "post_text": "Auto sector in trouble",
            },
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.90,
                "post_text": "Tesla bad",
            },
        ]
        result = aggregate_by_asset(predictions)
        symbols = list(result.keys())
        assert symbols[0] == "TSLA"
        assert result["TSLA"]["count"] == 2
        assert result["F"]["count"] == 1

    def test_empty_predictions(self):
        result = aggregate_by_asset([])
        assert result == {}

    def test_mixed_sentiments_majority_wins(self):
        predictions = [
            {"market_impact": {"TSLA": "bearish"}, "confidence": 0.85, "post_text": ""},
            {"market_impact": {"TSLA": "bearish"}, "confidence": 0.80, "post_text": ""},
            {"market_impact": {"TSLA": "bullish"}, "confidence": 0.70, "post_text": ""},
        ]
        result = aggregate_by_asset(predictions)
        assert result["TSLA"]["sentiment"] == "bearish"

    def test_json_string_market_impact(self):
        predictions = [
            {
                "market_impact": json.dumps({"AAPL": "bullish"}),
                "confidence": 0.75,
                "post_text": "Apple strong",
            },
        ]
        result = aggregate_by_asset(predictions)
        assert "AAPL" in result
        assert result["AAPL"]["sentiment"] == "bullish"

    def test_none_post_text(self):
        predictions = [
            {
                "market_impact": {"SPY": "bearish"},
                "confidence": 0.80,
                "post_text": None,
            },
        ]
        result = aggregate_by_asset(predictions)
        assert result["SPY"]["predictions"][0]["text"] == ""

    def test_confidence_range(self):
        predictions = [
            {"market_impact": {"TSLA": "bearish"}, "confidence": 0.90, "post_text": ""},
            {"market_impact": {"TSLA": "bearish"}, "confidence": 0.70, "post_text": ""},
        ]
        result = aggregate_by_asset(predictions)
        assert result["TSLA"]["min_confidence"] == 0.70
        assert result["TSLA"]["max_confidence"] == 0.90


# ============================================================
# Formatting Tests
# ============================================================


class TestFormatBriefingMessage:
    """Test format_briefing_message()."""

    def test_quiet_night(self):
        message = format_briefing_message("Wednesday, April 9, 2026", [], {})
        assert "QUIET NIGHT" in message
        assert "MORNING BRIEFING" in message
        assert "April 9" in message

    def test_active_night(self):
        predictions = [
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "post_text": "Bad",
            },
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.78,
                "post_text": "Worse",
            },
            {"market_impact": {"F": "neutral"}, "confidence": 0.72, "post_text": "Ok"},
        ]
        asset_summary = aggregate_by_asset(predictions)
        message = format_briefing_message(
            "Wednesday, April 9, 2026", predictions, asset_summary
        )
        assert "3 posts analyzed" in message
        assert "TSLA" in message
        assert "ASSET BREAKDOWN" in message
        assert "BEARISH" in message

    def test_single_prediction(self):
        predictions = [
            {
                "market_impact": {"NVDA": "bullish"},
                "confidence": 0.90,
                "post_text": "Chips",
            },
        ]
        asset_summary = aggregate_by_asset(predictions)
        message = format_briefing_message(
            "Thursday, April 10, 2026", predictions, asset_summary
        )
        assert "1 post analyzed" in message
        assert "NVDA" in message

    def test_escapes_markdown(self):
        predictions = [
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "post_text": "Tesla Inc. (TSLA) is failing!",
            },
        ]
        asset_summary = aggregate_by_asset(predictions)
        message = format_briefing_message("April 9, 2026", predictions, asset_summary)
        # Dots and parens should be escaped
        assert "Inc\\." in message
        assert "\\(TSLA\\)" in message

    def test_under_telegram_limit(self):
        # Generate a large but reasonable briefing
        predictions = []
        for i in range(10):
            predictions.append(
                {
                    "market_impact": {f"T{i:02d}": "bearish"},
                    "confidence": 0.80,
                    "post_text": f"Post about ticker T{i:02d} with some content",
                }
            )
        asset_summary = aggregate_by_asset(predictions)
        message = format_briefing_message("April 9, 2026", predictions, asset_summary)
        assert len(message) <= 4096

    def test_footer_present(self):
        message = format_briefing_message("April 9, 2026", [], {})
        assert "NOT financial advice" in message
        assert "/briefing off" in message

    def test_truncation_for_many_assets(self):
        """Very large briefing triggers compact format."""
        predictions = []
        for i in range(50):
            predictions.append(
                {
                    "market_impact": {f"TICK{i:03d}": "bearish"},
                    "confidence": 0.80,
                    "post_text": "A" * 80,
                }
            )
        asset_summary = aggregate_by_asset(predictions)
        message = format_briefing_message("April 9, 2026", predictions, asset_summary)
        assert len(message) <= 4096


# ============================================================
# Scheduling Tests
# ============================================================


class TestScheduling:
    """Test briefing time and day checks."""

    def test_is_briefing_time_correct(self):
        t = datetime(2026, 4, 9, 8, 30, tzinfo=ET)
        assert is_briefing_time(t) is True

    def test_is_briefing_time_early(self):
        t = datetime(2026, 4, 9, 8, 20, tzinfo=ET)
        assert is_briefing_time(t) is False

    def test_is_briefing_time_late(self):
        t = datetime(2026, 4, 9, 8, 40, tzinfo=ET)
        assert is_briefing_time(t) is False

    def test_is_briefing_time_wrong_hour(self):
        t = datetime(2026, 4, 9, 15, 30, tzinfo=ET)
        assert is_briefing_time(t) is False

    def test_is_briefing_time_edge_25(self):
        t = datetime(2026, 4, 9, 8, 25, tzinfo=ET)
        assert is_briefing_time(t) is True

    def test_is_briefing_time_edge_35(self):
        t = datetime(2026, 4, 9, 8, 35, tzinfo=ET)
        assert is_briefing_time(t) is True

    @patch("notifications.briefing.MarketCalendar")
    def test_is_briefing_day_trading_day(self, mock_cal_cls):
        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = True
        mock_cal_cls.return_value = mock_cal

        t = datetime(2026, 4, 9, 8, 30, tzinfo=ET)  # Wednesday
        assert is_briefing_day(t) is True

    @patch("notifications.briefing.MarketCalendar")
    def test_is_briefing_day_weekend(self, mock_cal_cls):
        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = False
        mock_cal_cls.return_value = mock_cal

        t = datetime(2026, 4, 12, 8, 30, tzinfo=ET)  # Saturday
        assert is_briefing_day(t) is False


# ============================================================
# Subscriber Preference Tests
# ============================================================


class TestBriefingCommand:
    """Test /briefing command handler."""

    @patch("notifications.telegram_bot.get_subscription")
    def test_not_subscribed(self, mock_get_sub):
        mock_get_sub.return_value = None
        result = handle_briefing_command("123")
        assert "not subscribed" in result

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_briefing_off(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": True}}
        mock_update.return_value = True
        result = handle_briefing_command("123", "off")
        assert "disabled" in result
        call_args = mock_update.call_args
        prefs = call_args[1]["alert_preferences"]
        assert prefs["briefing_enabled"] is False

    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_briefing_on(self, mock_get_sub, mock_update):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": False}}
        mock_update.return_value = True
        result = handle_briefing_command("123", "on")
        assert "enabled" in result
        assert "8:30 AM ET" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_briefing_status_enabled(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": True}}
        result = handle_briefing_command("123")
        assert "enabled" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_briefing_status_disabled(self, mock_get_sub):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": False}}
        result = handle_briefing_command("123")
        assert "disabled" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_briefing_default_enabled(self, mock_get_sub):
        """New subscribers default to briefing enabled."""
        mock_get_sub.return_value = {"alert_preferences": {}}
        result = handle_briefing_command("123")
        assert "enabled" in result

    @patch("notifications.telegram_bot.get_subscription")
    def test_json_string_prefs(self, mock_get_sub):
        mock_get_sub.return_value = {
            "alert_preferences": json.dumps({"briefing_enabled": True})
        }
        result = handle_briefing_command("123")
        assert "enabled" in result


# ============================================================
# Send Morning Briefing Tests
# ============================================================


class TestSendMorningBriefing:
    """Test send_morning_briefing() orchestrator."""

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_sends_to_opted_in(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = []
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {"briefing_enabled": True}},
            {"chat_id": "222", "alert_preferences": {"briefing_enabled": True}},
        ]
        mock_send.return_value = (True, None)

        results = send_morning_briefing()
        assert results["sent"] == 2
        assert results["skipped"] == 0
        assert mock_send.call_count == 2

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_skips_opted_out(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = []
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {"briefing_enabled": True}},
            {"chat_id": "222", "alert_preferences": {"briefing_enabled": False}},
        ]
        mock_send.return_value = (True, None)

        results = send_morning_briefing()
        assert results["sent"] == 1
        assert results["skipped"] == 1

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_default_enabled(self, mock_preds, mock_subs, mock_send):
        """Subscribers without explicit pref default to enabled."""
        mock_preds.return_value = []
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {}},
        ]
        mock_send.return_value = (True, None)

        results = send_morning_briefing()
        assert results["sent"] == 1

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_handles_send_failure(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = []
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {}},
        ]
        mock_send.return_value = (False, "Bot blocked")

        results = send_morning_briefing()
        assert results["sent"] == 0
        assert results["failed"] == 1

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_no_subscribers(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = []
        mock_subs.return_value = []

        results = send_morning_briefing()
        assert results["sent"] == 0
        assert results["total_subscribers"] == 0
        mock_send.assert_not_called()

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_json_string_prefs(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = []
        mock_subs.return_value = [
            {
                "chat_id": "111",
                "alert_preferences": json.dumps({"briefing_enabled": True}),
            },
        ]
        mock_send.return_value = (True, None)

        results = send_morning_briefing()
        assert results["sent"] == 1

    @patch("notifications.briefing.send_telegram_message")
    @patch("notifications.briefing.get_active_subscriptions")
    @patch("notifications.briefing.get_overnight_predictions")
    def test_predictions_count_tracked(self, mock_preds, mock_subs, mock_send):
        mock_preds.return_value = [
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.85,
                "post_text": "Bad",
            },
            {
                "market_impact": {"TSLA": "bearish"},
                "confidence": 0.80,
                "post_text": "Worse",
            },
        ]
        mock_subs.return_value = [
            {"chat_id": "111", "alert_preferences": {}},
        ]
        mock_send.return_value = (True, None)

        results = send_morning_briefing()
        assert results["predictions_count"] == 2


# ============================================================
# Process Update Routing Tests
# ============================================================


class TestProcessUpdateBriefing:
    """Test /briefing routing through process_update."""

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.get_subscription")
    def test_routes_to_briefing_handler(self, mock_get_sub, mock_send):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": True}}
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"username": "testuser"},
                "text": "/briefing",
            }
        }
        result = process_update(update)
        assert result is not None
        assert "enabled" in result

    @patch("notifications.telegram_bot.send_telegram_message")
    @patch("notifications.telegram_bot.update_subscription")
    @patch("notifications.telegram_bot.get_subscription")
    def test_routes_briefing_off(self, mock_get_sub, mock_update, mock_send):
        mock_get_sub.return_value = {"alert_preferences": {"briefing_enabled": True}}
        mock_update.return_value = True
        update = {
            "message": {
                "chat": {"id": 123, "type": "private"},
                "from": {"username": "testuser"},
                "text": "/briefing off",
            }
        }
        result = process_update(update)
        assert "disabled" in result
