"""
Tests for notifications/dispatcher.py.
Covers email/SMS validation, rate limiting, and message formatting.
"""

import time

from notifications.dispatcher import (
    _check_email_rate_limit,
    _check_sms_rate_limit,
    _email_sent_timestamps,
    _sms_sent_timestamps,
    _validate_email,
    _validate_phone_number,
    _EMAIL_RATE_LIMIT,
    _SMS_RATE_LIMIT,
    format_alert_message,
    format_alert_message_html,
)


class TestValidatePhoneNumber:
    """Test phone number validation."""

    def test_valid_us_number(self):
        assert _validate_phone_number("+15551234567") is True

    def test_valid_uk_number(self):
        assert _validate_phone_number("+442071234567") is True

    def test_rejects_no_plus(self):
        assert _validate_phone_number("15551234567") is False

    def test_rejects_empty(self):
        assert _validate_phone_number("") is False

    def test_rejects_none(self):
        assert _validate_phone_number(None) is False

    def test_rejects_letters(self):
        assert _validate_phone_number("+1555abc4567") is False


class TestValidateEmail:
    """Test email validation."""

    def test_valid_email(self):
        assert _validate_email("test@example.com") is True

    def test_valid_email_with_subdomain(self):
        assert _validate_email("user@mail.example.com") is True

    def test_rejects_empty(self):
        assert _validate_email("") is False

    def test_rejects_none(self):
        assert _validate_email(None) is False

    def test_rejects_no_at(self):
        assert _validate_email("testexample.com") is False

    def test_rejects_no_domain(self):
        assert _validate_email("test@") is False


class TestRateLimiting:
    """Test SMS and email rate limiting."""

    def test_sms_rate_limit_allows_initial(self):
        """Allows SMS when under rate limit."""
        _sms_sent_timestamps.clear()
        assert _check_sms_rate_limit() is True

    def test_sms_rate_limit_blocks_when_exceeded(self):
        """Blocks SMS when rate limit is exceeded."""
        _sms_sent_timestamps.clear()
        now = time.time()
        for _ in range(_SMS_RATE_LIMIT):
            _sms_sent_timestamps.append(now)
        assert _check_sms_rate_limit() is False

    def test_sms_rate_limit_clears_old_entries(self):
        """Old SMS timestamps are cleared from the rate limiter."""
        _sms_sent_timestamps.clear()
        old_time = time.time() - 7200
        for _ in range(_SMS_RATE_LIMIT):
            _sms_sent_timestamps.append(old_time)
        assert _check_sms_rate_limit() is True

    def test_email_rate_limit_allows_initial(self):
        """Allows email when under rate limit."""
        _email_sent_timestamps.clear()
        assert _check_email_rate_limit() is True

    def test_email_rate_limit_blocks_when_exceeded(self):
        """Blocks email when rate limit is exceeded."""
        _email_sent_timestamps.clear()
        now = time.time()
        for _ in range(_EMAIL_RATE_LIMIT):
            _email_sent_timestamps.append(now)
        assert _check_email_rate_limit() is False


class TestFormatAlertMessage:
    """Test plain text alert message formatting."""

    def test_formats_bullish_alert(self, sample_alert):
        """Formats a bullish alert message."""
        result = format_alert_message(sample_alert)
        assert "BULLISH" in result
        assert "85%" in result
        assert "AAPL" in result

    def test_handles_empty_assets(self):
        """Handles empty assets list."""
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
        alert = {
            "confidence": 0.7,
            "assets": ["AAPL"],
            "sentiment": "bullish",
            "text": "A" * 200,
        }
        result = format_alert_message(alert)
        assert "..." in result


class TestFormatAlertMessageHtml:
    """Test HTML email formatting."""

    def test_returns_html_string(self, sample_alert):
        """Returns an HTML string."""
        result = format_alert_message_html(sample_alert)
        assert "<div" in result
        assert "BULLISH" in result
        assert "85%" in result

    def test_colors_bullish_green(self):
        """Bullish sentiment uses green color."""
        alert = {
            "confidence": 0.85,
            "assets": ["AAPL"],
            "sentiment": "bullish",
            "text": "Test",
            "thesis": "Test",
        }
        result = format_alert_message_html(alert)
        assert "#10b981" in result

    def test_colors_bearish_red(self):
        """Bearish sentiment uses red color."""
        alert = {
            "confidence": 0.85,
            "assets": ["AAPL"],
            "sentiment": "bearish",
            "text": "Test",
            "thesis": "Test",
        }
        result = format_alert_message_html(alert)
        assert "#ef4444" in result
