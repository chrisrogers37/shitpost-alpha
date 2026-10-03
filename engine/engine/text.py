"""Post text as the pickers and the similarity model read it."""

import re

LINK = re.compile(r"https?://\S+|\bwww\.\S+", re.IGNORECASE)


def normalize(text: str) -> str:
    """A post's words: links removed and whitespace collapsed. One function for live
    posts and history, for the rules, the AI picker and the similarity model."""
    return " ".join(LINK.sub(" ", text).split())
