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
