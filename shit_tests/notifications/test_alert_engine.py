"""
Tests for notifications/alert_engine.py.
Covers alert filtering, quiet hours, sentiment extraction, and the main dispatch loop.
"""

from unittest.mock import patch

from notifications.alert_engine import (
    _extract_sentiment,
    check_and_dispatch,
    filter_predictions_by_preferences,
    is_in_quiet_hours,
)


class TestFilterPredictionsByPreferences:
    """Test the prediction filtering logic."""

    def _make_alert(self, confidence=0.8, assets=None, sentiment="bullish"):
        return {
            "prediction_id": 1,
            "text": "Test post",
            "confidence": confidence,
            "assets": assets or ["AAPL"],
            "sentiment": sentiment,
        }

    def test_matches_when_all_criteria_met(self):
        """Prediction matches when confidence, asset, and sentiment all pass."""
        alerts = [self._make_alert(confidence=0.85, assets=["AAPL"])]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": ["AAPL"],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 1

    def test_filters_low_confidence(self):
        """Predictions below confidence threshold are excluded."""
        alerts = [self._make_alert(confidence=0.5)]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 0

    def test_filters_wrong_asset(self):
        """Predictions for non-matching assets are excluded."""
        alerts = [self._make_alert(assets=["GOOGL"])]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": ["AAPL"],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 0

    def test_empty_assets_matches_all(self):
        """Empty assets_of_interest list matches all assets."""
        alerts = [self._make_alert(assets=["GOOGL"])]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 1

    def test_filters_wrong_sentiment(self):
        """Predictions with non-matching sentiment are excluded."""
        alerts = [self._make_alert(sentiment="bearish")]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "bullish",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 0

    def test_sentiment_all_matches_everything(self):
        """Sentiment filter 'all' matches any sentiment."""
        alerts = [
            self._make_alert(sentiment="bullish"),
            self._make_alert(sentiment="bearish"),
            self._make_alert(sentiment="neutral"),
        ]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 3

    def test_none_confidence_excluded(self):
        """Predictions with None confidence are excluded."""
        alerts = [self._make_alert(confidence=None)]
        prefs = {
            "min_confidence": 0.5,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 0

    def test_multiple_asset_overlap(self):
        """Match when prediction has multiple assets and one overlaps."""
        alerts = [self._make_alert(assets=["GOOGL", "AAPL", "MSFT"])]
        prefs = {
            "min_confidence": 0.7,
            "assets_of_interest": ["AAPL"],
            "sentiment_filter": "all",
        }
        result = filter_predictions_by_preferences(alerts, prefs)
        assert len(result) == 1


class TestIsInQuietHours:
    """Test quiet hours checking."""

    def test_returns_false_when_disabled(self):
        """Returns False when quiet hours are disabled."""
        prefs = {"quiet_hours_enabled": False}
        assert is_in_quiet_hours(prefs) is False

    def test_returns_false_with_empty_prefs(self):
        """Returns False with empty preferences."""
        assert is_in_quiet_hours({}) is False


class TestExtractSentiment:
    """Test sentiment extraction from market_impact."""

    def test_extracts_bullish(self):
        result = _extract_sentiment({"AAPL": "bullish"})
        assert result == "bullish"

    def test_extracts_bearish(self):
        result = _extract_sentiment({"TSLA": "bearish"})
        assert result == "bearish"

    def test_returns_neutral_for_empty(self):
        assert _extract_sentiment({}) == "neutral"
        assert _extract_sentiment(None) == "neutral"

    def test_returns_neutral_for_non_dict(self):
        assert _extract_sentiment("bullish") == "neutral"
        assert _extract_sentiment([]) == "neutral"

    def test_handles_json_string(self):
        """Handles market_impact as a JSON string."""
        import json

        result = _extract_sentiment(json.dumps({"AAPL": "bullish"}))
        assert result == "bullish"


class TestCheckAndDispatch:
    """Test the main alert dispatch loop."""

    @patch("notifications.alert_engine.send_telegram_message")
    @patch("notifications.alert_engine.format_telegram_alert")
    @patch("notifications.alert_engine.get_active_subscriptions")
    @patch("notifications.alert_engine.get_new_predictions_since")
    @patch("notifications.alert_engine.get_last_alert_check")
    def test_no_predictions_returns_zero(
        self, mock_last_check, mock_preds, mock_subs, mock_format, mock_send
    ):
        """Returns zero counts when no new predictions."""
        mock_last_check.return_value = None
        mock_preds.return_value = []

        result = check_and_dispatch()
        assert result["predictions_found"] == 0
        assert result["alerts_sent"] == 0

    @patch("notifications.alert_engine.record_alert_sent")
    @patch("notifications.alert_engine.send_telegram_message")
    @patch("notifications.alert_engine.format_telegram_alert")
    @patch("notifications.alert_engine.get_active_subscriptions")
    @patch("notifications.alert_engine.get_new_predictions_since")
    @patch("notifications.alert_engine.get_last_alert_check")
    def test_dispatches_to_matching_subscriber(
        self,
        mock_last_check,
        mock_preds,
        mock_subs,
        mock_format,
        mock_send,
        mock_record,
    ):
        """Sends alerts to subscribers whose preferences match."""
        mock_last_check.return_value = None
        mock_preds.return_value = [
            {
                "prediction_id": 1,
                "shitpost_id": "abc",
                "text": "AAPL going up!",
                "confidence": 0.85,
                "assets": ["AAPL"],
                "market_impact": {"AAPL": "bullish"},
                "thesis": "Strong earnings",
                "timestamp": "2024-01-15T10:00:00",
            }
        ]
        mock_subs.return_value = [
            {
                "chat_id": "123",
                "alert_preferences": {
                    "min_confidence": 0.7,
                    "assets_of_interest": [],
                    "sentiment_filter": "all",
                    "quiet_hours_enabled": False,
                },
            }
        ]
        mock_format.return_value = "Formatted alert"
        mock_send.return_value = (True, None)

        result = check_and_dispatch()
        assert result["predictions_found"] == 1
        assert result["alerts_sent"] == 1
        mock_record.assert_called_once_with("123")

    @patch("notifications.alert_engine.send_telegram_message")
    @patch("notifications.alert_engine.format_telegram_alert")
    @patch("notifications.alert_engine.get_active_subscriptions")
    @patch("notifications.alert_engine.get_new_predictions_since")
    @patch("notifications.alert_engine.get_last_alert_check")
    def test_filters_low_confidence_subscriber(
        self, mock_last_check, mock_preds, mock_subs, mock_format, mock_send
    ):
        """Filters out subscribers with higher confidence threshold."""
        mock_last_check.return_value = None
        mock_preds.return_value = [
            {
                "prediction_id": 1,
                "shitpost_id": "abc",
                "text": "test",
                "confidence": 0.6,
                "assets": ["AAPL"],
                "market_impact": {"AAPL": "bullish"},
                "thesis": "test",
                "timestamp": "2024-01-15T10:00:00",
            }
        ]
        mock_subs.return_value = [
            {
                "chat_id": "123",
                "alert_preferences": {
                    "min_confidence": 0.8,
                    "assets_of_interest": [],
                    "sentiment_filter": "all",
                    "quiet_hours_enabled": False,
                },
            }
        ]

        result = check_and_dispatch()
        assert result["filtered"] == 1
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @patch("notifications.alert_engine.get_active_subscriptions")
    @patch("notifications.alert_engine.get_new_predictions_since")
    @patch("notifications.alert_engine.get_last_alert_check")
    def test_no_subscribers_returns_early(self, mock_last_check, mock_preds, mock_subs):
        """Returns early when no active subscribers."""
        mock_last_check.return_value = None
        mock_preds.return_value = [
            {
                "prediction_id": 1,
                "text": "test",
                "confidence": 0.85,
                "assets": ["AAPL"],
                "market_impact": {},
                "thesis": "test",
                "timestamp": "2024-01-15T10:00:00",
                "shitpost_id": "abc",
            }
        ]
        mock_subs.return_value = []

        result = check_and_dispatch()
        assert result["predictions_found"] == 1
        assert result["alerts_sent"] == 0
