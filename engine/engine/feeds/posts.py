"""One post as a feed delivers it, mapped to the shape every feed shares.

Truth Social runs a Mastodon fork, so a status id is a snowflake: `id >> 16` is
milliseconds since the Unix epoch. A post's time comes from its id, never from a feed's
own timestamp.
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Literal

PLATFORM = "truth_social"
ACCOUNT_ID = "107780257626128497"
HANDLE = "realDonaldTrump"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

Kind = Literal["post", "reply", "quote", "repost"]
NotScored = Literal["repost", "no_text"]

_STATUS_ID = re.compile(r"\d{15,20}")
STATUS_URL = re.compile(
    r"https?://(?:www\.)?truthsocial\.com/"
    r"(?:@[\w.]+/(?:posts/)?|users/[\w.]+/statuses/)(?P<id>\d{15,20})\b/?"
)
_REPOST_OF_URL = re.compile(r"RT:\s*" + STATUS_URL.pattern)
_QUOTE_MARKER = re.compile(r"(?:^|\s)RE:\s*" + STATUS_URL.pattern)
# UTF-8 bytes that were decoded as Latin-1 (CNN's archive has about 900 such posts).
# Repaired only in CNN's text: elsewhere a pair like "É " is correct text.
_MOJIBAKE = re.compile(
    r"[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3}"
)
# What is left of a no-break space ("Â\xa0") when the space was trimmed away.
_ORPHAN_A = re.compile(r"Â(?=\s|$)")


def parse_status_id(value: object) -> str:
    status_id = str(value).strip()
    if not _STATUS_ID.fullmatch(status_id) or int(status_id) >= 2**63:  # ids are bigints
        raise ValueError(f"not a Truth Social status id: {value!r}")
    return status_id


def status_time(status_id: str) -> datetime:
    """When the post was made, from its id (to the millisecond)."""
    return EPOCH + timedelta(milliseconds=int(status_id) >> 16)


def signal_key(status_id: str) -> str:
    return f"{PLATFORM}:{status_id}"


@dataclass(frozen=True)
class Post:
    status_id: str
    kind: Kind
    points_to: str | None
    """Status id of the post a reply, quote or repost points to, when the feed says."""
    text: str
    """Plain text of the post's own words (a quote's marker and link are removed)."""
    has_media: bool | None
    """None when the feed doesn't report media (trumpstruth)."""
    raw: dict[str, Any]
    """The feed's item, as delivered."""

    @property
    def key(self) -> str:
        return signal_key(self.status_id)

    @property
    def posted_at(self) -> datetime:
        return status_time(self.status_id)

    @property
    def url(self) -> str:
        return f"https://truthsocial.com/@{HANDLE}/{self.status_id}"

    @property
    def not_scored(self) -> NotScored | None:
        """Why live scoring skips this post: reposts and posts with no text of their own."""
        if self.kind == "repost":
            return "repost"
        if not self.text:
            return "no_text"
        return None


def mirror_post(status_id: str, text: str, has_media: bool | None, raw: dict[str, Any]) -> Post:
    """A post from a mirror (CNN, trumpstruth), which shows only text.

    A repost is text starting "RT @handle" or "RT: <status url>"; only the second names
    the reposted status. A quote carries "RE: <status url>", or is the bare status url
    when it adds no words of its own.
    """
    if text.startswith(("RT @", "RT:")):
        repost_of = _REPOST_OF_URL.match(text)
        points_to = repost_of["id"] if repost_of else None
        return Post(status_id, "repost", points_to, text, has_media, raw)
    own, quoted = split_quote(text)
    return Post(status_id, "quote" if quoted else "post", quoted, own, has_media, raw)


def split_quote(text: str) -> tuple[str, str | None]:
    """Separate a quote's own words from its "RE: <url>" marker or bare quoted url."""
    if marker := _QUOTE_MARKER.search(text):
        return (text[: marker.start()] + text[marker.end() :]).strip(), marker["id"]
    if bare := STATUS_URL.fullmatch(text):
        return "", bare["id"]
    return text, None


def clean_text(text: str) -> str:
    """Turn no-break spaces into spaces, drop NULs (Postgres text refuses them) and trim
    blank space."""
    lines = (line.rstrip() for line in text.replace("\xa0", " ").replace("\x00", "").splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def plain_text(content: str) -> str:
    """Text from CNN's archive (and its CC0 copy): plain text with HTML entities, a few
    posts escaped twice, and UTF-8 that was decoded as Latin-1 in about 900 posts."""
    for _ in range(3):
        unescaped = html.unescape(content)
        if unescaped == content:
            break
        content = unescaped
    return clean_text(_ORPHAN_A.sub("", _MOJIBAKE.sub(_redecode, content)))


def html_text(content: str) -> str:
    """Text from HTML (Mastodon statuses, trumpstruth): line breaks kept, tags dropped."""
    parser = _TextParser()
    parser.feed(content)
    parser.close()
    return clean_text("".join(parser.parts))


def _redecode(match: re.Match[str]) -> str:
    try:
        return match[0].encode("latin-1").decode("utf-8")
    except UnicodeDecodeError:
        return match[0]


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
