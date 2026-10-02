"""The reason line: one line of 120 characters or fewer saying why a post may matter for
the instruments it names. One designated model writes it (ai.json's "reason"; by default
the pinned Anthropic model). It decides nothing: the alert is already decided when it is
asked. A rule check rejects a line that states a direction, a price, a target or advice,
or that is too long; on a rejection, an error or a 15 s timeout there is no line and the
alert goes out without one. PR 6 calls it."""

import asyncio
import logging
import re
from collections.abc import Sequence

from engine.extract.ai import AiConfig, Client, scrubbed

log = logging.getLogger(__name__)

DIRECTION = re.compile(
    r"\b(?:buy\w*|sell\w*|short\w*|bull\w*|bear\w*|upside|downside|rise[sn]?|rising|rose|"
    r"fall\w*|fell|drop\w*|surg\w*|soar\w*|plung\w*|jump\w*|rall\w*|crash\w*|tank\w*|"
    r"gain\w*|lose[sr]?|losing|loss\w*|climb\w*|sink\w*|sank|slump\w*|spik\w*|boost\w*|benefit\w*|harm\w*|"
    r"hurt\w*|lift\w*|weigh\w*|rebound\w*|outperform\w*|underperform\w*|target\w*|"
    r"recommend\w*|advi[cs]e\w*|should|opportunit\w*|positive|negative|"
    r"(?:stock|share)\s+prices?|price\s+target\w*)\b",
    re.IGNORECASE,
)
"""Words that state a direction, a price, a target or advice."""
MONEY_OR_PERCENT = re.compile(r"[$%€£]|\bpercent\b|\bbps\b", re.IGNORECASE)


def check_reason(line: str, max_chars: int) -> str | None:
    """Why `line` is rejected, or None if it passes."""
    if not line:
        return "empty"
    if "\n" in line or "\r" in line:
        return "more than one line"
    if len(line) > max_chars:
        return f"{len(line)} characters, over {max_chars}"
    if found := DIRECTION.search(line):
        return f"states a direction, price, target or advice: {found.group(0)!r}"
    if found := MONEY_OR_PERCENT.search(line):
        return f"states an amount: {found.group(0)!r}"
    return None


def reason_input(words: str, topic: str, names: Sequence[str]) -> str:
    return f"Post:\n{words}\n\nTopic: {topic}\nInstruments: {', '.join(names)}"


async def reason_line(
    client: Client,
    config: AiConfig,
    words: str,
    topic: str,
    names: Sequence[str],
    *,
    secrets: Sequence[str] = (),
) -> str | None:
    """The line, or None (logged with why) on a timeout, an error or a rejected line."""
    spec = config.reason
    try:
        async with asyncio.timeout(config.timeout_seconds):
            reply = await client.ask(
                spec.instructions, reason_input(words, topic, names), None, spec.max_output_tokens
            )
    except TimeoutError:
        log.warning("reason line: timeout after %g s", config.timeout_seconds)
        return None
    except Exception as exc:
        log.warning("reason line: %s", scrubbed(f"{type(exc).__name__}: {exc}", secrets))
        return None
    line = reply.text.strip()
    if problem := check_reason(line, spec.max_chars):
        log.warning("reason line rejected (%s): %r", problem, line)
        return None
    return line
