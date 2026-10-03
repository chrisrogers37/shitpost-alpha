"""Links to the public site. The engine, the notification code and the site build them here."""

from urllib.parse import quote

SITE_URL = "https://shitpostalpha.com"


def signal_url(public_id: str) -> str:
    """The page for one signal: https://shitpostalpha.com/s/<public_id>."""
    if not public_id:
        raise ValueError("public_id is empty")
    return f"{SITE_URL}/s/{quote(public_id, safe='')}"
