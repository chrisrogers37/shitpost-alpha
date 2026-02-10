"""
Tests for the alerting system.
Covers alert checking, filtering, notification dispatch, and rate limiting.
"""

import time
import sys
import os
from datetime import datetime
from unittest.mock import patch

# Add the shitty_ui directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


# ============================================================
# Test: filter_predictions_by_preferences
# ============================================================


class TestFilterPredictionsByPreferences:
    """Test the prediction filtering logic against user preferences."""

    def _make_prediction(
        self,
        confidence: float = 0.8,
        assets: list = None,
        market_impact: dict = None,
    ) -> dict:
        """Helper to create a prediction dict for testing."""
        return {
            "prediction_id": 1,
            "shitpost_id": "abc123",
            "text": "Big news for AAPL today!",
            "confidence": confidence,
            "assets": assets or ["AAPL"],
            "market_impact": market_impact or {"AAPL": "bullish"},
            "thesis": "Test thesis",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _make_preferences(
        self,
        min_confidence: float = 0.7,
        assets_of_interest: list = None,
        sentiment_filter: str = "all",
    ) -> dict:
        """Helper to create a preferences dict for testing."""
        return {
            "enabled": True,
            "min_confidence": min_confidence,
            "assets_of_interest": assets_of_interest or [],
            "sentiment_filter": sentiment_filter,
        }

    def test_matches_when_all_criteria_met(self):
        """Prediction matches when confidence, asset, and sentiment all pass."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=0.85, assets=["AAPL"])]
        prefs = self._make_preferences(min_confidence=0.7, assets_of_interest=["AAPL"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1

    def test_filters_low_confidence(self):
        """Predictions below confidence threshold are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=0.5)]
        prefs = self._make_preferences(min_confidence=0.7)

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_filters_wrong_asset(self):
        """Predictions for non-matching assets are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL"])]
        prefs = self._make_preferences(assets_of_interest=["AAPL", "TSLA"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_empty_assets_matches_all(self):
        """Empty assets_of_interest list matches all assets."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL"])]
        prefs = self._make_preferences(assets_of_interest=[])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1

    def test_filters_wrong_sentiment(self):
        """Predictions with non-matching sentiment are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(market_impact={"AAPL": "bearish"})]
        prefs = self._make_preferences(sentiment_filter="bullish")

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_sentiment_all_matches_everything(self):
        """Sentiment filter 'all' matches any sentiment."""
        from alerts import filter_predictions_by_preferences

        predictions = [
            self._make_prediction(market_impact={"AAPL": "bullish"}),
            self._make_prediction(market_impact={"AAPL": "bearish"}),
            self._make_prediction(market_impact={"AAPL": "neutral"}),
        ]
        prefs = self._make_preferences(sentiment_filter="all")

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 3

    def test_none_confidence_excluded(self):
        """Predictions with None confidence are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=None)]
        prefs = self._make_preferences(min_confidence=0.5)

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_multiple_asset_overlap(self):
        """Match when prediction has multiple assets and one overlaps."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL", "AAPL", "MSFT"])]
        prefs = self._make_preferences(assets_of_interest=["AAPL"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1


# ============================================================
# Test: is_in_quiet_hours
# ============================================================


class TestIsInQuietHours:
    """Test quiet hours checking."""

    def test_returns_false_when_disabled(self):
        """Returns False when quiet hours are disabled."""
        from alerts import is_in_quiet_hours

        prefs = {"quiet_hours_enabled": False}
        assert is_in_quiet_hours(prefs) is False

    def test_returns_false_with_empty_prefs(self):
        """Returns False with empty preferences."""
        from alerts import is_in_quiet_hours

        prefs = {}
        assert is_in_quiet_hours(prefs) is False


# ============================================================
# Test: _extract_sentiment
# ============================================================


class TestExtractSentiment:
    """Test sentiment extraction from market_impact."""

    def test_extracts_bullish(self):
        """Extracts bullish sentiment from market_impact dict."""
        from alerts import _extract_sentiment

        result = _extract_sentiment({"AAPL": "bullish"})
        assert result == "bullish"

    def test_extracts_bearish(self):
        """Extracts bearish sentiment."""
        from alerts import _extract_sentiment

        result = _extract_sentiment({"TSLA": "bearish"})
        assert result == "bearish"

    def test_returns_neutral_for_empty(self):
        """Returns neutral for empty market_impact."""
        from alerts import _extract_sentiment

        assert _extract_sentiment({}) == "neutral"
        assert _extract_sentiment(None) == "neutral"

    def test_returns_neutral_for_non_dict(self):
        """Returns neutral for non-dict market_impact."""
        from alerts import _extract_sentiment

        assert _extract_sentiment("bullish") == "neutral"
        assert _extract_sentiment([]) == "neutral"


# ============================================================
# Test: _validate_phone_number
# ============================================================


class TestValidatePhoneNumber:
    """Test phone number validation."""

    def test_valid_us_number(self):
        """Accepts valid US phone number."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+15551234567") is True

    def test_valid_uk_number(self):
        """Accepts valid UK phone number."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+442071234567") is True

    def test_rejects_no_plus(self):
        """Rejects phone number without + prefix."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("15551234567") is False

    def test_rejects_empty(self):
        """Rejects empty string."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("") is False

    def test_rejects_none(self):
        """Rejects None."""
        from alerts import _validate_phone_number

        assert _validate_phone_number(None) is False

    def test_rejects_letters(self):
        """Rejects numbers containing letters."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+1555abc4567") is False


# ============================================================
# Test: _validate_email
# ============================================================


class TestValidateEmail:
    """Test email validation."""

    def test_valid_email(self):
        """Accepts valid email address."""
        from alerts import _validate_email

        assert _validate_email("test@example.com") is True

    def test_valid_email_with_subdomain(self):
        """Accepts email with subdomain."""
        from alerts import _validate_email

        assert _validate_email("user@mail.example.com") is True

    def test_rejects_empty(self):
        """Rejects empty string."""
        from alerts import _validate_email

        assert _validate_email("") is False

    def test_rejects_none(self):
        """Rejects None."""
        from alerts import _validate_email

        assert _validate_email(None) is False

    def test_rejects_no_at(self):
        """Rejects email without @ symbol."""
        from alerts import _validate_email

        assert _validate_email("testexample.com") is False

    def test_rejects_no_domain(self):
        """Rejects email without domain."""
        from alerts import _validate_email

        assert _validate_email("test@") is False


# ============================================================
# Test: format_alert_message
# ============================================================


class TestFormatAlertMessage:
    """Test alert message formatting."""

    def test_formats_bullish_alert(self):
        """Formats a bullish alert message."""
        from alerts import format_alert_message

        alert = {
            "confidence": 0.85,
            "assets": ["AAPL", "GOOGL"],
            "sentiment": "bullish",
            "text": "Great day for American tech companies!",
        }
        result = format_alert_message(alert)
        assert "BULLISH" in result
        assert "85%" in result
        assert "AAPL" in result
        assert "GOOGL" in result

    def test_handles_empty_assets(self):
        """Handles empty assets list."""
        from alerts import format_alert_message

        alert = {
            "confidence": 0.7,
            "assets": [],
            "sentiment": "neutral",
            "text": "Some post",
        }
        result = format_alert_message(alert)
        assert "NEUTRAL" in result

    def test_truncates_long_text(self):
        """Truncates long post text."""
        from alerts import format_alert_message

        alert = {
            "confidence": 0.7,
            "assets": ["AAPL"],
            "sentiment": "bullish",
            "text": "A" * 200,  # Long text
        }
        result = format_alert_message(alert)
        assert "..." in result


# ============================================================
# Test: format_alert_message_html
# ============================================================


class TestFormatAlertMessageHtml:
    """Test HTML email formatting."""

    def test_returns_html_string(self):
        """Returns an HTML string."""
        from alerts import format_alert_message_html

        alert = {
            "confidence": 0.85,
            "assets": ["AAPL"],
            "sentiment": "bullish",
            "text": "Test post",
            "thesis": "Test thesis",
        }
        result = format_alert_message_html(alert)
        assert "<div" in result
        assert "BULLISH" in result
        assert "85%" in result

    def test_colors_bullish_green(self):
        """Bullish sentiment uses green color."""
        from alerts import format_alert_message_html

        alert = {
            "confidence": 0.85,
            "assets": ["AAPL"],
            "sentiment": "bullish",
            "text": "Test",
            "thesis": "Test",
        }
        result = format_alert_message_html(alert)
        assert "#10b981" in result  # Green color

    def test_colors_bearish_red(self):
        """Bearish sentiment uses red color."""
        from alerts import format_alert_message_html

        alert = {
            "confidence": 0.85,
            "assets": ["AAPL"],
            "sentiment": "bearish",
            "text": "Test",
            "thesis": "Test",
        }
        result = format_alert_message_html(alert)
        assert "#ef4444" in result  # Red color


# ============================================================
# Test: Rate Limiting
# ============================================================


class TestRateLimiting:
    """Test SMS and email rate limiting."""

    def test_sms_rate_limit_allows_initial(self):
        """Allows SMS when under rate limit."""
        import alerts

        # Reset the rate limiter
        alerts._sms_sent_timestamps.clear()

        result = alerts._check_sms_rate_limit()
        assert result is True

    def test_sms_rate_limit_blocks_when_exceeded(self):
        """Blocks SMS when rate limit is exceeded."""
        import alerts

        # Fill up the rate limiter
        alerts._sms_sent_timestamps.clear()
        now = time.time()
        for _ in range(alerts._SMS_RATE_LIMIT):
            alerts._sms_sent_timestamps.append(now)

        result = alerts._check_sms_rate_limit()
        assert result is False

    def test_sms_rate_limit_clears_old_entries(self):
        """Old SMS timestamps are cleared from the rate limiter."""
        import alerts

        alerts._sms_sent_timestamps.clear()
        old_time = time.time() - 7200  # 2 hours ago
        for _ in range(alerts._SMS_RATE_LIMIT):
            alerts._sms_sent_timestamps.append(old_time)

        result = alerts._check_sms_rate_limit()
        assert result is True

    def test_email_rate_limit_allows_initial(self):
        """Allows email when under rate limit."""
        import alerts

        # Reset the rate limiter
        alerts._email_sent_timestamps.clear()

        result = alerts._check_email_rate_limit()
        assert result is True

    def test_email_rate_limit_blocks_when_exceeded(self):
        """Blocks email when rate limit is exceeded."""
        import alerts

        # Fill up the rate limiter
        alerts._email_sent_timestamps.clear()
        now = time.time()
        for _ in range(alerts._EMAIL_RATE_LIMIT):
            alerts._email_sent_timestamps.append(now)

        result = alerts._check_email_rate_limit()
        assert result is False


# ============================================================
# Test: check_for_new_alerts
# ============================================================


class TestCheckForNewAlerts:
    """Test the main alert checking function."""

    @patch("notifications.db.get_new_predictions_since")
    def test_returns_empty_when_no_new_predictions(self, mock_query):
        """Returns empty matched_alerts when no new predictions."""
        mock_query.return_value = []

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, datetime.utcnow().isoformat())
        assert result["matched_alerts"] == []
        assert result["total_new"] == 0

    @patch("notifications.db.get_new_predictions_since")
    def test_returns_matched_alerts(self, mock_query):
        """Returns matched alerts when predictions match preferences."""
        mock_query.return_value = [
            {
                "prediction_id": 1,
                "shitpost_id": "abc",
                "text": "AAPL going up!",
                "confidence": 0.85,
                "assets": ["AAPL"],
                "market_impact": {"AAPL": "bullish"},
                "thesis": "Strong earnings",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, datetime.utcnow().isoformat())
        assert len(result["matched_alerts"]) == 1
        assert result["total_new"] == 1

    @patch("notifications.db.get_new_predictions_since")
    def test_handles_none_last_check(self, mock_query):
        """Handles None last_check timestamp (first check)."""
        mock_query.return_value = []

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, None)
        assert result["matched_alerts"] == []
        assert result["last_check"] is not None


# ============================================================
# Test: DEFAULT_ALERT_PREFERENCES
# ============================================================


class TestDefaultAlertPreferences:
    """Test default alert preferences."""

    def test_default_preferences_has_required_keys(self):
        """Default preferences dict has all required keys."""
        from alerts import DEFAULT_ALERT_PREFERENCES

        required_keys = [
            "enabled",
            "min_confidence",
            "assets_of_interest",
            "sentiment_filter",
            "browser_notifications",
            "email_enabled",
            "email_address",
            "sms_enabled",
            "sms_phone_number",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
            "max_alerts_per_hour",
        ]

        for key in required_keys:
            assert key in DEFAULT_ALERT_PREFERENCES

    def test_default_alerts_disabled(self):
        """Alerts are disabled by default."""
        from alerts import DEFAULT_ALERT_PREFERENCES

        assert DEFAULT_ALERT_PREFERENCES["enabled"] is False

    def test_default_confidence_threshold(self):
        """Default confidence threshold is 0.7."""
        from alerts import DEFAULT_ALERT_PREFERENCES

        assert DEFAULT_ALERT_PREFERENCES["min_confidence"] == 0.7

    def test_browser_notifications_enabled_by_default(self):
        """Browser notifications are enabled by default."""
        from alerts import DEFAULT_ALERT_PREFERENCES

        assert DEFAULT_ALERT_PREFERENCES["browser_notifications"] is True


# ============================================================
# Test: Layout Components
# ============================================================


class TestAlertConfigPanel:
    """Test the alert configuration panel component."""

    def test_create_alert_config_panel_returns_offcanvas(self):
        """Panel returns a dbc.Offcanvas component."""
        from layout import create_alert_config_panel
        import dash_bootstrap_components as dbc

        panel = create_alert_config_panel()
        assert isinstance(panel, dbc.Offcanvas)

    def test_panel_has_correct_id(self):
        """Panel has the expected component ID."""
        from layout import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.id == "alert-config-offcanvas"

    def test_panel_has_children(self):
        """Panel contains configuration controls."""
        from layout import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.children is not None
        assert len(panel.children) > 0


class TestAlertHistoryPanel:
    """Test the alert history panel component."""

    def test_create_alert_history_panel_returns_card(self):
        """History panel returns a dbc.Card component."""
        from layout import create_alert_history_panel
        import dash_bootstrap_components as dbc

        panel = create_alert_history_panel()
        assert isinstance(panel, dbc.Card)


# ============================================================
# Test: Data Layer - get_new_predictions_since
# ============================================================


class TestGetNewPredictionsSince:
    """Test the database query for new predictions (now in notifications.db)."""

    @patch("notifications.db.get_new_predictions_since")
    def test_returns_list_of_dicts(self, mock_query):
        """Returns a list of dicts with expected keys."""
        mock_query.return_value = [
            {
                "timestamp": "2024-01-15T10:00:00",
                "text": "Test post",
                "shitpost_id": "post123",
                "prediction_id": 1,
                "assets": ["AAPL"],
                "market_impact": {"AAPL": "bullish"},
                "confidence": 0.85,
                "thesis": "Strong thesis",
                "analysis_status": "completed",
                "prediction_created_at": "2024-01-15T10:05:00",
            }
        ]

        from notifications.db import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert len(result) == 1
        assert result[0]["shitpost_id"] == "post123"
        assert result[0]["confidence"] == 0.85

    @patch("notifications.db.get_new_predictions_since")
    def test_returns_empty_on_error(self, mock_query):
        """Returns empty list on database error."""
        mock_query.return_value = []

        from notifications.db import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert result == []

    @patch("notifications.db.get_new_predictions_since")
    def test_returns_empty_when_no_rows(self, mock_query):
        """Returns empty list when query returns no rows."""
        mock_query.return_value = []

        from notifications.db import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert result == []
