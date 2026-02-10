"""
Multi-channel notification dispatch for Shitpost Alpha.

Handles email (SMTP/SendGrid) and SMS (Twilio) dispatch.
Telegram dispatch is handled by the alert_engine module.
"""

import logging
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# Module-level rate limiters
_sms_sent_timestamps: List[float] = []
_SMS_RATE_LIMIT = 10
_SMS_RATE_WINDOW = 3600

_email_sent_timestamps: List[float] = []
_EMAIL_RATE_LIMIT = 20
_EMAIL_RATE_WINDOW = 3600


# ============================================================
# Email Dispatch
# ============================================================


def _validate_email(email: str) -> bool:
    """Basic email validation."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def _check_email_rate_limit() -> bool:
    """Check if sending another email would exceed the rate limit."""
    now = time.time()
    cutoff = now - _EMAIL_RATE_WINDOW
    while _email_sent_timestamps and _email_sent_timestamps[0] < cutoff:
        _email_sent_timestamps.pop(0)
    if len(_email_sent_timestamps) >= _EMAIL_RATE_LIMIT:
        logger.warning(
            f"Email rate limit reached: {len(_email_sent_timestamps)} in last hour"
        )
        return False
    return True


def _record_email_sent() -> None:
    """Record that an email was sent for rate limiting."""
    _email_sent_timestamps.append(time.time())


def send_email_alert(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """
    Send an email alert to the user.

    Reads configuration from settings to determine whether to use
    SMTP or SendGrid.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML version of the email body.
        text_body: Plain text version of the email body.

    Returns:
        True if the email was sent successfully.
    """
    if not _validate_email(to_email):
        logger.error(f"Invalid email address: {to_email}")
        return False

    if not _check_email_rate_limit():
        logger.warning(f"Email to {to_email} blocked by rate limit")
        return False

    try:
        from shit.config.shitpost_settings import settings
    except ImportError:
        logger.error("Could not import settings for email configuration")
        return False

    provider = getattr(settings, "EMAIL_PROVIDER", "smtp")

    if provider == "sendgrid":
        result = _send_via_sendgrid(to_email, subject, html_body, text_body, settings)
    else:
        result = _send_via_smtp(to_email, subject, html_body, text_body, settings)

    if result:
        _record_email_sent()
    return result


def _send_via_smtp(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    settings: Any,
) -> bool:
    """
    Send an email using SMTP.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML body.
        text_body: Plain text body.
        settings: Application settings with SMTP configuration.

    Returns:
        True if sent successfully.
    """
    smtp_host = getattr(settings, "SMTP_HOST", None)
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USERNAME", None)
    smtp_pass = getattr(settings, "SMTP_PASSWORD", None)
    use_tls = getattr(settings, "SMTP_USE_TLS", True)
    from_addr = getattr(settings, "EMAIL_FROM_ADDRESS", "alerts@shitpostalpha.com")
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Shitpost Alpha")

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured. Skipping email alert.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.ehlo()

        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email alert sent to {to_email}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}")
        return False


def _send_via_sendgrid(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    settings: Any,
) -> bool:
    """
    Send an email using the SendGrid API.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML body.
        text_body: Plain text body.
        settings: Application settings with SendGrid configuration.

    Returns:
        True if sent successfully.
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", None)
    from_addr = getattr(settings, "EMAIL_FROM_ADDRESS", "alerts@shitpostalpha.com")
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Shitpost Alpha")

    if not api_key:
        logger.warning("SendGrid API key not configured. Skipping email alert.")
        return False

    try:
        import requests

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject,
                }
            ],
            "from": {"email": from_addr, "name": from_name},
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }

        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if response.status_code in (200, 201, 202):
            logger.info(f"SendGrid email sent to {to_email}")
            return True
        else:
            logger.error(
                f"SendGrid API error: {response.status_code} - {response.text}"
            )
            return False

    except ImportError:
        logger.error("requests package not available for SendGrid API call")
        return False
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False


# ============================================================
# SMS Dispatch
# ============================================================


def _validate_phone_number(phone: str) -> bool:
    """
    Validate that a phone number is in E.164 format.

    E.164 format: + followed by 1-15 digits.

    Args:
        phone: Phone number string to validate.

    Returns:
        True if the phone number appears valid.
    """
    if not phone:
        return False
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone.strip()))


def _check_sms_rate_limit() -> bool:
    """Check if sending another SMS would exceed the rate limit."""
    now = time.time()
    cutoff = now - _SMS_RATE_WINDOW
    while _sms_sent_timestamps and _sms_sent_timestamps[0] < cutoff:
        _sms_sent_timestamps.pop(0)
    if len(_sms_sent_timestamps) >= _SMS_RATE_LIMIT:
        logger.warning(
            f"SMS rate limit reached: {len(_sms_sent_timestamps)} "
            f"messages in the last hour (limit: {_SMS_RATE_LIMIT})"
        )
        return False
    return True


def _record_sms_sent() -> None:
    """Record that an SMS was sent for rate limiting purposes."""
    _sms_sent_timestamps.append(time.time())


def send_sms_alert(
    to_phone: str,
    message: str,
) -> bool:
    """
    Send an SMS alert via Twilio.

    Args:
        to_phone: Recipient phone number in E.164 format.
        message: The SMS message body.

    Returns:
        True if the SMS was sent successfully.
    """
    try:
        from shit.config.shitpost_settings import settings
    except ImportError:
        logger.error("Could not import settings for Twilio configuration")
        return False

    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER

    if not account_sid or not auth_token or not from_number:
        logger.warning("Twilio not configured. Skipping SMS alert.")
        return False

    if not _validate_phone_number(to_phone):
        logger.error(f"Invalid phone number format: {to_phone}")
        return False

    if not _check_sms_rate_limit():
        logger.warning(f"SMS to {to_phone} blocked by rate limit")
        return False

    # Truncate message to Twilio's limit (1600 chars)
    if len(message) > 1600:
        message = message[:1597] + "..."

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        sms = client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone,
        )

        _record_sms_sent()
        logger.info(f"SMS alert sent to {to_phone}, SID: {sms.sid}")
        return True

    except ImportError:
        logger.error("Twilio package not installed. Run: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"Twilio error sending SMS to {to_phone}: {e}")
        return False


# ============================================================
# Alert message formatting (for email/SMS)
# ============================================================


def format_alert_message(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into a plain text notification message.

    Args:
        alert: Alert dict with keys: text, confidence, assets, sentiment, thesis.

    Returns:
        Formatted message string suitable for email/SMS.
    """
    confidence_pct = f"{alert.get('confidence', 0):.0%}"
    assets_str = ", ".join(alert.get("assets", [])[:5])
    sentiment = alert.get("sentiment", "neutral").upper()

    message = (
        f"New {sentiment} prediction ({confidence_pct} confidence)\n"
        f"Assets: {assets_str}\n"
        f"Post: {alert.get('text', '')[:120]}..."
    )
    return message


def format_alert_message_html(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into an HTML email body.

    Args:
        alert: Alert dict.

    Returns:
        HTML string for email body.
    """
    confidence_pct = f"{alert.get('confidence', 0):.0%}"
    assets_str = ", ".join(alert.get("assets", [])[:5])
    sentiment = alert.get("sentiment", "neutral").upper()
    thesis = alert.get("thesis", "No thesis provided.")

    if sentiment == "BULLISH":
        sentiment_color = "#10b981"
    elif sentiment == "BEARISH":
        sentiment_color = "#ef4444"
    else:
        sentiment_color = "#94a3b8"

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e293b; padding: 20px; border-radius: 8px;">
            <h2 style="color: #3b82f6; margin: 0 0 10px 0;">Shitpost Alpha Alert</h2>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: {sentiment_color}; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                    {sentiment} ({confidence_pct} confidence)
                </div>
                <div style="color: #94a3b8; font-size: 14px;">
                    Assets: {assets_str}
                </div>
            </div>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: #f1f5f9; font-size: 14px; line-height: 1.5;">
                    {alert.get("text", "")[:300]}
                </div>
            </div>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">
                    Thesis
                </div>
                <div style="color: #f1f5f9; font-size: 14px; line-height: 1.5;">
                    {thesis[:500]}
                </div>
            </div>

            <div style="color: #475569; font-size: 12px; text-align: center; margin-top: 20px;">
                This is NOT financial advice. For entertainment and research purposes only.
            </div>
        </div>
    </div>
    """
