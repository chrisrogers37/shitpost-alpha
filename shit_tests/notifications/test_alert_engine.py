"""
Tests for notifications/alert_engine.py.
Covers alert filtering, quiet hours, sentiment extraction, and the main dispatch loop.
"""

from unittest.mock import patch

from notifications.alert_engine import (
    _extract_sentiment,
    check_and_dispatch,
    enrich_alert,
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


class TestCalibratedConfidenceFiltering:
    """Test that filtering prefers calibrated_confidence when available."""

    def _make_alert(self, confidence=0.8, calibrated=None, assets=None):
        return {
            "prediction_id": 1,
            "text": "Test",
            "confidence": confidence,
            "calibrated_confidence": calibrated,
            "assets": assets or ["AAPL"],
            "sentiment": "bullish",
        }

    def _prefs(self, min_confidence=0.7):
        return {
            "min_confidence": min_confidence,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }

    def test_uses_calibrated_when_available(self):
        """Calibrated confidence takes precedence over raw."""
        # Raw 0.85 passes 0.7 threshold, but calibrated 0.55 does not
        alerts = [self._make_alert(confidence=0.85, calibrated=0.55)]
        result = filter_predictions_by_preferences(alerts, self._prefs(0.7))
        assert len(result) == 0

    def test_calibrated_passes_threshold(self):
        """Alert passes when calibrated confidence meets threshold."""
        alerts = [self._make_alert(confidence=0.85, calibrated=0.75)]
        result = filter_predictions_by_preferences(alerts, self._prefs(0.7))
        assert len(result) == 1

    def test_falls_back_to_raw_when_calibrated_is_none(self):
        """Raw confidence used when calibrated is None (no curve)."""
        alerts = [self._make_alert(confidence=0.85, calibrated=None)]
        result = filter_predictions_by_preferences(alerts, self._prefs(0.7))
        assert len(result) == 1

    def test_falls_back_to_raw_when_calibrated_missing(self):
        """Raw confidence used when calibrated_confidence key is absent."""
        alert = {"prediction_id": 1, "confidence": 0.85, "assets": ["AAPL"], "sentiment": "bullish"}
        result = filter_predictions_by_preferences([alert], self._prefs(0.7))
        assert len(result) == 1


class TestEnrichAlert:
    """Tests for the unified alert enrichment function.

    CalibrationService and EchoService are imported lazily inside enrich_alert()
    via `from X import Y` inside try blocks.  Those imports resolve through their
    source modules, so we patch them there.
    """

    def test_adds_calibrated_confidence(self):
        """enrich_alert adds calibrated_confidence from CalibrationService."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch("shit.market_data.calibration.CalibrationService") as mock_cal:
            mock_cal.return_value.calibrate.return_value = 0.65
            result = enrich_alert(alert)
        assert result["calibrated_confidence"] == 0.65

    def test_skips_calibration_if_already_set(self):
        """enrich_alert does not overwrite existing calibrated_confidence."""
        alert = {"prediction_id": 1, "confidence": 0.8, "calibrated_confidence": 0.7}
        result = enrich_alert(alert)
        assert result["calibrated_confidence"] == 0.7

    def test_adds_echoes(self):
        """enrich_alert adds echoes from EchoService."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        echoes_result = {"count": 3, "win_rate": 0.67, "avg_return": 1.2}
        with patch("shit.echoes.echo_service.EchoService") as mock_echo:
            mock_echo.return_value.get_embedding.return_value = [0.1] * 1536
            mock_echo.return_value.find_similar_posts.return_value = [{"prediction_id": 2}]
            mock_echo.return_value.aggregate_echoes.return_value = echoes_result
            with patch("shit.market_data.calibration.CalibrationService") as mock_cal:
                mock_cal.return_value.calibrate.return_value = None
                result = enrich_alert(alert)
        assert result["echoes"] == echoes_result

    def test_skips_echoes_if_no_prediction_id(self):
        """enrich_alert skips echo lookup when prediction_id is missing."""
        alert = {"confidence": 0.8}
        result = enrich_alert(alert)
        assert "echoes" not in result

    def test_calibration_failure_does_not_block(self):
        """enrich_alert continues when calibration raises an exception."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch(
            "shit.market_data.calibration.CalibrationService",
            side_effect=Exception("boom"),
        ):
            result = enrich_alert(alert)
        assert "calibrated_confidence" not in result

    def test_echo_failure_does_not_block(self):
        """enrich_alert continues when echo service raises an exception."""
        alert = {"prediction_id": 1, "confidence": 0.8}
        with patch("shit.market_data.calibration.CalibrationService") as mock_cal:
            mock_cal.return_value.calibrate.return_value = None
            with patch(
                "shit.echoes.echo_service.EchoService",
                side_effect=Exception("boom"),
            ):
                result = enrich_alert(alert)
        assert "echoes" not in result
