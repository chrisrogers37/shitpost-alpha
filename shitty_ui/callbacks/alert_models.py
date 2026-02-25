"""Pydantic model for alert preferences.

Replaces the paired build_preferences_dict() / extract_preferences_tuple()
functions with a single type-safe model that handles serialization
in both directions.
"""

from pydantic import BaseModel, Field


class AlertPreferences(BaseModel):
    """Alert preferences as stored in localStorage.

    This is the canonical shape of the preferences object.
    Use from_form_fields() to build from Dash form values,
    and to_form_tuple() to extract back to the 12-element
    tuple expected by load_preferences_into_form().
    """

    enabled: bool = False
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    assets_of_interest: list[str] = Field(default_factory=list)
    sentiment_filter: str = "all"
    browser_notifications: bool = True
    email_enabled: bool = False
    email_address: str = ""
    sms_enabled: bool = False
    sms_phone_number: str = ""
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    max_alerts_per_hour: int = 10

    @classmethod
    def from_form_fields(
        cls,
        enabled: bool,
        min_confidence: float,
        assets: list,
        sentiment: str,
        browser_on: bool,
        email_on: bool,
        email_addr: str,
        sms_on: bool,
        sms_phone: str,
        quiet_on: bool,
        quiet_start: str,
        quiet_end: str,
    ) -> "AlertPreferences":
        """Build from individual Dash form field values.

        Applies safe defaults for None values, matching the
        original build_preferences_dict() behavior exactly.
        """
        return cls(
            enabled=bool(enabled),
            min_confidence=float(min_confidence or 0.7),
            assets_of_interest=assets or [],
            sentiment_filter=sentiment or "all",
            browser_notifications=bool(browser_on),
            email_enabled=bool(email_on),
            email_address=email_addr or "",
            sms_enabled=bool(sms_on),
            sms_phone_number=sms_phone or "",
            quiet_hours_enabled=bool(quiet_on),
            quiet_hours_start=quiet_start or "22:00",
            quiet_hours_end=quiet_end or "08:00",
        )

    def to_form_tuple(self) -> tuple:
        """Extract to the 12-element tuple matching Output order
        of load_preferences_into_form().

        Returns:
            Tuple of (enabled, min_confidence, assets, sentiment,
            browser_on, email_on, email_addr, sms_on, sms_phone,
            quiet_on, quiet_start, quiet_end).
        """
        return (
            self.enabled,
            self.min_confidence,
            self.assets_of_interest,
            self.sentiment_filter,
            self.browser_notifications,
            self.email_enabled,
            self.email_address,
            self.sms_enabled,
            self.sms_phone_number,
            self.quiet_hours_enabled,
            self.quiet_hours_start,
            self.quiet_hours_end,
        )

    def to_dict(self) -> dict:
        """Serialize to the dict shape expected by localStorage.

        Equivalent to the original build_preferences_dict() output.
        """
        return self.model_dump()

    @classmethod
    def from_stored(cls, prefs: dict) -> "AlertPreferences":
        """Construct from a localStorage dict, filling defaults for missing keys.

        Equivalent to the original extract_preferences_tuple() input handling.
        """
        return cls(**{k: v for k, v in (prefs or {}).items() if k in cls.model_fields})
