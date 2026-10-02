"""Post text as the pickers and the similarity model read it."""

import re

LINK = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)


def normalize(text: str) -> str:
    """A post's words: links removed and whitespace collapsed. One function for live
    posts and history, for the rules, the AI picker and the similarity model."""
    return " ".join(LINK.sub(" ", text).split())


WORD = re.compile(r"[^\W_]")
"""A letter or a digit, in any script."""


def has_words(text: str) -> bool:
    """Whether a post has a letter or a digit once its links are out. A post of only
    emoji, symbols or punctuation has none, like a post of only links: every such post
    gets about the same vector, so it would match every earlier one at about 1.0."""
    return WORD.search(normalize(text)) is not None


LINK_LIKE = re.compile(
    r"(?:https?://|\bwww\.)\S+"
    r"|\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"(?:com|net|org|gov|edu|mil|io|co|us|uk|ly|me|tv|news|info|biz|ai|app|social|live)\b"
    r"(?:/\S*)?",
    re.IGNORECASE,
)
"""Anything Telegram or X would turn into a link: a URL, www., or a bare domain such as
whitehouse.gov or Amazon.com. Broader than LINK, which normalize() uses and which the
frozen pickers and vectors were made with, so the two stay apart."""


def excerpt(text: str, limit: int) -> str:
    """A post's words for public display: links and bare domains removed, whitespace
    collapsed, and cut at a word to `limit` characters or fewer (ending in an ellipsis
    when cut)."""
    words = " ".join(LINK_LIKE.sub(" ", text).split())
    if len(words) <= limit:
        return words
    cut = words[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,;:-") + "…"
