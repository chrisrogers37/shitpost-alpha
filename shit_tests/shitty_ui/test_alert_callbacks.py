"""
Tests for alert callback helpers and sub-component builders.

Covers:
- alert_components.py: Panel sub-component builders
- alerts.py (callbacks layer): build_preferences_dict, extract_preferences_tuple,
  build_alert_history_card
"""

import sys
import os
from datetime import datetime

# Add the shitty_ui directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import dash_bootstrap_components as dbc
from dash import html, dcc

from callbacks.alert_components import (
    build_master_toggle_section,
    build_status_indicator,
    build_confidence_threshold_section,
    build_asset_selection_section,
    build_sentiment_filter_section,
    build_notification_channels_section,
    build_quiet_hours_section,
    build_action_buttons_section,
)
from callbacks.alerts import (
    build_preferences_dict,
    extract_preferences_tuple,
    build_alert_history_card,
)


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)


def _find_component_by_id(component, target_id) -> object:
    """Recursively search for a component with a specific id."""
    if hasattr(component, "id") and component.id == target_id:
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                if child is not None:
                    result = _find_component_by_id(child, target_id)
                    if result is not None:
                        return result
        elif children is not None:
            return _find_component_by_id(children, target_id)
    return None


# ============================================================
# Sub-component builder tests
# ============================================================


class TestBuildMasterToggleSection:
    """Test the master toggle sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_master_toggle_section()
        assert isinstance(result, html.Div)

    def test_contains_switch_with_correct_id(self):
        """Contains a dbc.Switch with id='alert-master-toggle'."""
        result = build_master_toggle_section()
        switch = _find_component_by_id(result, "alert-master-toggle")
        assert switch is not None
        assert isinstance(switch, dbc.Switch)

    def test_switch_default_value_false(self):
        """Master toggle defaults to False (alerts off)."""
        result = build_master_toggle_section()
        switch = _find_component_by_id(result, "alert-master-toggle")
        assert switch.value is False

    def test_contains_enable_alerts_label(self):
        """Contains 'Enable Alerts' text."""
        result = build_master_toggle_section()
        text = _extract_text(result)
        assert "Enable Alerts" in text


class TestBuildStatusIndicator:
    """Test the alert status indicator sub-component."""

    def test_returns_div_with_correct_id(self):
        """Returns html.Div with id='alert-status-indicator'."""
        result = build_status_indicator()
        assert isinstance(result, html.Div)
        assert result.id == "alert-status-indicator"

    def test_default_text_says_disabled(self):
        """Default text says 'Alerts disabled'."""
        result = build_status_indicator()
        text = _extract_text(result)
        assert "Alerts disabled" in text


class TestBuildConfidenceThresholdSection:
    """Test the confidence slider sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_confidence_threshold_section()
        assert isinstance(result, html.Div)

    def test_contains_slider_with_correct_id(self):
        """Contains a dcc.Slider with id='alert-confidence-slider'."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider is not None
        assert isinstance(slider, dcc.Slider)

    def test_slider_default_value_is_070(self):
        """Slider default value is 0.7 (70%)."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider.value == 0.7

    def test_slider_range_0_to_1(self):
        """Slider range is 0.0 to 1.0."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider.min == 0.0
        assert slider.max == 1.0

    def test_contains_display_element(self):
        """Contains the percentage display element."""
        result = build_confidence_threshold_section()
        display = _find_component_by_id(result, "confidence-threshold-display")
        assert display is not None
        assert display.children == "70%"


class TestBuildAssetSelectionSection:
    """Test the asset dropdown sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_asset_selection_section()
        assert isinstance(result, html.Div)

    def test_contains_dropdown_with_correct_id(self):
        """Contains a dcc.Dropdown with id='alert-assets-dropdown'."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown is not None
        assert isinstance(dropdown, dcc.Dropdown)

    def test_dropdown_is_multi_select(self):
        """Dropdown allows multiple selection."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown.multi is True

    def test_dropdown_starts_empty(self):
        """Dropdown options start empty (populated by callback)."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown.options == []
        assert dropdown.value == []


class TestBuildSentimentFilterSection:
    """Test the sentiment radio buttons sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_sentiment_filter_section()
        assert isinstance(result, html.Div)

    def test_contains_radio_items_with_correct_id(self):
        """Contains dbc.RadioItems with id='alert-sentiment-radio'."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        assert radio is not None
        assert isinstance(radio, dbc.RadioItems)

    def test_default_value_is_all(self):
        """Default sentiment filter is 'all'."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        assert radio.value == "all"

    def test_has_four_options(self):
        """Has four sentiment options: all, bullish, bearish, neutral."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        values = [opt["value"] for opt in radio.options]
        assert values == ["all", "bullish", "bearish", "neutral"]


class TestBuildNotificationChannelsSection:
    """Test the notification channels sub-component."""

    def test_returns_list_of_five_elements(self):
        """Returns a list of 5 elements (browser, status, email, sms, telegram)."""
        result = build_notification_channels_section()
        assert isinstance(result, list)
        assert len(result) == 5

    def test_contains_browser_toggle(self):
        """Contains the browser notifications switch."""
        result = build_notification_channels_section()
        # Search across all elements
        for elem in result:
            switch = _find_component_by_id(elem, "alert-browser-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is True  # Browser notifications on by default
                return
        assert False, "alert-browser-toggle not found"

    def test_contains_email_toggle(self):
        """Contains the email notifications switch."""
        result = build_notification_channels_section()
        for elem in result:
            switch = _find_component_by_id(elem, "alert-email-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is False  # Email off by default
                return
        assert False, "alert-email-toggle not found"

    def test_contains_sms_toggle(self):
        """Contains the SMS notifications switch."""
        result = build_notification_channels_section()
        for elem in result:
            switch = _find_component_by_id(elem, "alert-sms-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is False  # SMS off by default
                return
        assert False, "alert-sms-toggle not found"

    def test_contains_telegram_link(self):
        """Contains the Telegram bot link."""
        result = build_notification_channels_section()
        all_text = " ".join(_extract_text(elem) for elem in result)
        assert "ShitpostAlphaBot" in all_text


class TestBuildQuietHoursSection:
    """Test the quiet hours sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_quiet_hours_section()
        assert isinstance(result, html.Div)

    def test_contains_toggle_with_correct_id(self):
        """Contains switch with id='alert-quiet-hours-toggle'."""
        result = build_quiet_hours_section()
        switch = _find_component_by_id(result, "alert-quiet-hours-toggle")
        assert switch is not None
        assert isinstance(switch, dbc.Switch)

    def test_toggle_default_off(self):
        """Quiet hours toggle defaults to False."""
        result = build_quiet_hours_section()
        switch = _find_component_by_id(result, "alert-quiet-hours-toggle")
        assert switch.value is False

    def test_contains_time_inputs(self):
        """Contains start and end time inputs."""
        result = build_quiet_hours_section()
        start = _find_component_by_id(result, "quiet-hours-start")
        end = _find_component_by_id(result, "quiet-hours-end")
        assert start is not None
        assert end is not None
        assert start.value == "22:00"
        assert end.value == "08:00"


class TestBuildActionButtonsSection:
    """Test the save/test/clear buttons sub-component."""

    def test_returns_list_of_three_elements(self):
        """Returns a list of 3 elements (buttons div, toast, note)."""
        result = build_action_buttons_section()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_contains_save_button(self):
        """Contains save preferences button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "save-alert-prefs-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        assert False, "save-alert-prefs-button not found"

    def test_contains_test_alert_button(self):
        """Contains test alert button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "test-alert-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        assert False, "test-alert-button not found"

    def test_contains_clear_history_button(self):
        """Contains clear alert history button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "clear-alert-history-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        assert False, "clear-alert-history-button not found"

    def test_contains_toast(self):
        """Contains save confirmation toast."""
        result = build_action_buttons_section()
        for elem in result:
            toast = _find_component_by_id(elem, "alert-save-toast")
            if toast is not None:
                assert isinstance(toast, dbc.Toast)
                assert toast.is_open is False
                return
        assert False, "alert-save-toast not found"


# ============================================================
# build_preferences_dict tests
# ============================================================


class TestBuildPreferencesDict:
    """Test preference dict assembly from form fields."""

    def test_basic_assembly(self):
        """Assembles all fields into a preferences dict."""
        result = build_preferences_dict(
            enabled=True,
            min_confidence=0.8,
            assets=["AAPL", "TSLA"],
            sentiment="bullish",
            browser_on=True,
            email_on=True,
            email_addr="test@example.com",
            sms_on=False,
            sms_phone="",
            quiet_on=True,
            quiet_start="23:00",
            quiet_end="07:00",
        )
        assert result["enabled"] is True
        assert result["min_confidence"] == 0.8
        assert result["assets_of_interest"] == ["AAPL", "TSLA"]
        assert result["sentiment_filter"] == "bullish"
        assert result["browser_notifications"] is True
        assert result["email_enabled"] is True
        assert result["email_address"] == "test@example.com"
        assert result["sms_enabled"] is False
        assert result["sms_phone_number"] == ""
        assert result["quiet_hours_enabled"] is True
        assert result["quiet_hours_start"] == "23:00"
        assert result["quiet_hours_end"] == "07:00"
        assert result["max_alerts_per_hour"] == 10

    def test_none_confidence_defaults_to_070(self):
        """None confidence defaults to 0.7."""
        result = build_preferences_dict(
            enabled=True, min_confidence=None,
            assets=[], sentiment="all",
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["min_confidence"] == 0.7

    def test_none_assets_defaults_to_empty_list(self):
        """None assets defaults to empty list."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=None, sentiment=None,
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["assets_of_interest"] == []
        assert result["sentiment_filter"] == "all"

    def test_none_email_defaults_to_empty_string(self):
        """None email address defaults to empty string."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=[], sentiment="all",
            browser_on=True, email_on=True, email_addr=None,
            sms_on=True, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["email_address"] == ""
        assert result["sms_phone_number"] == ""

    def test_none_quiet_hours_defaults(self):
        """None quiet hours start/end default to 22:00/08:00."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=[], sentiment="all",
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=True, quiet_start=None, quiet_end=None,
        )
        assert result["quiet_hours_start"] == "22:00"
        assert result["quiet_hours_end"] == "08:00"

    def test_has_all_thirteen_keys(self):
        """Result dict contains exactly 13 keys."""
        result = build_preferences_dict(
            enabled=False, min_confidence=0.5,
            assets=[], sentiment="all",
            browser_on=False, email_on=False, email_addr="",
            sms_on=False, sms_phone="",
            quiet_on=False, quiet_start="22:00", quiet_end="08:00",
        )
        expected_keys = {
            "enabled", "min_confidence", "assets_of_interest",
            "sentiment_filter", "browser_notifications",
            "email_enabled", "email_address",
            "sms_enabled", "sms_phone_number",
            "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end",
            "max_alerts_per_hour",
        }
        assert set(result.keys()) == expected_keys


# ============================================================
# extract_preferences_tuple tests
# ============================================================


class TestExtractPreferencesTuple:
    """Test preferences dict to form-values tuple conversion."""

    def test_full_round_trip(self):
        """build_preferences_dict -> extract_preferences_tuple round-trip."""
        prefs = build_preferences_dict(
            enabled=True, min_confidence=0.85,
            assets=["AAPL"], sentiment="bearish",
            browser_on=False, email_on=True, email_addr="x@y.com",
            sms_on=True, sms_phone="+15551234567",
            quiet_on=True, quiet_start="21:00", quiet_end="09:00",
        )
        result = extract_preferences_tuple(prefs)
        assert result == (
            True, 0.85, ["AAPL"], "bearish",
            False, True, "x@y.com",
            True, "+15551234567",
            True, "21:00", "09:00",
        )

    def test_returns_12_element_tuple(self):
        """Always returns exactly 12 elements."""
        result = extract_preferences_tuple({})
        assert len(result) == 12

    def test_defaults_for_empty_prefs(self):
        """Empty prefs dict returns safe defaults."""
        result = extract_preferences_tuple({})
        assert result == (
            False, 0.7, [], "all",
            True, False, "",
            False, "",
            False, "22:00", "08:00",
        )

    def test_partial_prefs_fills_defaults(self):
        """Partial prefs dict fills in defaults for missing keys."""
        result = extract_preferences_tuple({"enabled": True, "min_confidence": 0.9})
        assert result[0] is True  # enabled
        assert result[1] == 0.9   # min_confidence
        assert result[2] == []    # assets (default)
        assert result[3] == "all" # sentiment (default)


# ============================================================
# build_alert_history_card tests
# ============================================================


class TestBuildAlertHistoryCard:
    """Test individual alert history card rendering."""

    def _make_alert(self, **overrides) -> dict:
        """Create a minimal alert dict."""
        base = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["AAPL", "TSLA"],
            "text": "Big news for tech stocks today!",
            "alert_triggered_at": "2025-06-15T14:30:00Z",
        }
        base.update(overrides)
        return base

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_alert_history_card(self._make_alert())
        assert isinstance(result, html.Div)

    def test_bullish_sentiment_shows_arrow_up(self):
        """Bullish alert shows arrow-up icon."""
        result = build_alert_history_card(self._make_alert(sentiment="bullish"))
        text = _extract_text(result)
        assert "BULLISH" in text

    def test_bearish_sentiment_shows_arrow_down(self):
        """Bearish alert shows arrow-down icon."""
        result = build_alert_history_card(self._make_alert(sentiment="bearish"))
        text = _extract_text(result)
        assert "BEARISH" in text

    def test_neutral_sentiment_shows_minus(self):
        """Neutral alert shows minus icon."""
        result = build_alert_history_card(self._make_alert(sentiment="neutral"))
        text = _extract_text(result)
        assert "NEUTRAL" in text

    def test_unknown_sentiment_defaults_to_neutral(self):
        """Unknown sentiment value defaults to neutral styling."""
        result = build_alert_history_card(self._make_alert(sentiment="confused"))
        text = _extract_text(result)
        assert "CONFUSED" in text  # Uppercased, uses neutral styling

    def test_timestamp_formatting(self):
        """Formats ISO timestamp as 'Mon DD, HH:MM'."""
        result = build_alert_history_card(
            self._make_alert(alert_triggered_at="2025-06-15T14:30:00Z")
        )
        text = _extract_text(result)
        assert "Jun 15, 14:30" in text

    def test_invalid_timestamp_falls_back(self):
        """Invalid timestamp falls back to string slice."""
        result = build_alert_history_card(
            self._make_alert(alert_triggered_at="not-a-date")
        )
        text = _extract_text(result)
        assert "not-a-date" in text

    def test_empty_timestamp_handled(self):
        """Empty timestamp string does not crash."""
        result = build_alert_history_card(self._make_alert(alert_triggered_at=""))
        assert isinstance(result, html.Div)

    def test_none_timestamp_handled(self):
        """None timestamp does not crash."""
        result = build_alert_history_card(self._make_alert(alert_triggered_at=None))
        assert isinstance(result, html.Div)

    def test_text_truncation_at_120_chars(self):
        """Text longer than 120 chars is truncated with ellipsis."""
        long_text = "A" * 150
        result = build_alert_history_card(self._make_alert(text=long_text))
        text = _extract_text(result)
        assert "..." in text

    def test_short_text_no_truncation(self):
        """Short text is not truncated."""
        result = build_alert_history_card(self._make_alert(text="Short post"))
        text = _extract_text(result)
        assert "Short post" in text
        # Should not have trailing ellipsis
        assert text.count("...") == 0

    def test_assets_displayed(self):
        """Assets are displayed in the card."""
        result = build_alert_history_card(
            self._make_alert(assets=["AAPL", "TSLA", "GOOGL"])
        )
        text = _extract_text(result)
        assert "AAPL" in text
        assert "TSLA" in text
        assert "GOOGL" in text

    def test_assets_limited_to_three(self):
        """Only first 3 assets are displayed."""
        result = build_alert_history_card(
            self._make_alert(assets=["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"])
        )
        text = _extract_text(result)
        assert "AAPL" in text
        assert "MSFT" not in text

    def test_empty_assets_handled(self):
        """Empty assets list does not crash."""
        result = build_alert_history_card(self._make_alert(assets=[]))
        assert isinstance(result, html.Div)

    def test_confidence_displayed_as_percentage(self):
        """Confidence is displayed as a percentage."""
        result = build_alert_history_card(self._make_alert(confidence=0.85))
        text = _extract_text(result)
        assert "85%" in text

    def test_zero_confidence_shows_empty(self):
        """Zero confidence shows empty string (falsy)."""
        result = build_alert_history_card(self._make_alert(confidence=0))
        text = _extract_text(result)
        # confidence=0 is falsy, so the f-string branch produces ""
        assert "0%" not in text

    def test_missing_keys_use_defaults(self):
        """Alert dict with missing keys uses safe defaults."""
        result = build_alert_history_card({})
        assert isinstance(result, html.Div)
        text = _extract_text(result)
        assert "NEUTRAL" in text


# ============================================================
# create_alert_config_panel integration test
# ============================================================


class TestCreateAlertConfigPanelIntegration:
    """Test that the refactored panel still produces the same structure."""

    def test_returns_offcanvas(self):
        """Panel returns a dbc.Offcanvas component."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert isinstance(panel, dbc.Offcanvas)

    def test_has_correct_id(self):
        """Panel has the expected component ID."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.id == "alert-config-offcanvas"

    def test_all_critical_ids_present(self):
        """All critical component IDs are present in the panel tree."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        critical_ids = [
            "alert-master-toggle",
            "alert-status-indicator",
            "alert-confidence-slider",
            "confidence-threshold-display",
            "alert-assets-dropdown",
            "alert-sentiment-radio",
            "alert-browser-toggle",
            "browser-notification-status",
            "alert-email-toggle",
            "alert-email-input",
            "email-input-collapse",
            "alert-sms-toggle",
            "alert-sms-input",
            "sms-input-collapse",
            "alert-quiet-hours-toggle",
            "quiet-hours-start",
            "quiet-hours-end",
            "quiet-hours-collapse",
            "save-alert-prefs-button",
            "test-alert-button",
            "clear-alert-history-button",
            "alert-save-toast",
        ]
        for component_id in critical_ids:
            found = _find_component_by_id(panel, component_id)
            assert found is not None, f"Component '{component_id}' not found in panel"

    def test_panel_has_children(self):
        """Panel contains child components."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.children is not None
        assert len(panel.children) > 0
