"""The reason line: one line of 120 characters or fewer saying why a post may matter for
the instruments it names. One of the AI picker's pinned models writes it (the Anthropic
one). It has its own version, reason.json, so changing it needs no new picker version.
It decides nothing: the alert is decided without it. A rule check rejects a line that
states a direction, a price, a target or advice, an amount, a number the post doesn't
have or a link, or that is too long. It fails closed: on a rejection, an error, a cut-off
reply or a 15 s timeout there is no line and the alert goes out without one. The alert
stage calls it (engine/alerts/stage.py)."""

import asyncio
import logging
import re
from collections.abc import Sequence

from engine.extract.ai import AiConfig, Client, scrubbed
from engine.text import LINK_LIKE

log = logging.getLogger(__name__)

NEUTRAL = re.compile(
    r"\b(?:lower\s+courts?|(?:shut|crack|step|stand|back|turn|wind|calm)(?:s|ed|ing|ting|ped|ping)?"
    r"\s+down|shutdowns?|crackdowns?|(?:set|sign|follow|line|wrap|take|bring|meet)"
    r"(?:s|ed|ing|ting|ped|ping)?[\s-]+up|(?:social\s+security|medicare|medicaid|veterans'?)"
    r"\s+benefits?|rais(?:es|ed|ing)\s+(?:the\s+)?questions?)\b",
    re.IGNORECASE,
)
"""Phrases with a direction word in them that state no direction ("lower court", "shut
down", "Social Security benefits"): taken out before DIRECTION is looked for."""
DIRECTION = re.compile(
    r"\b(?:buy\w*|sell\w*|short\w*|bull\w*|bear\w*|upside|downside|rise[sn]?|rising|rose|"
    r"fall\w*|fell|drop\w*|surg\w*|soar\w*|plung\w*|jump\w*|rall\w*|crash\w*|tank\w*|"
    r"gain\w*|lose[sr]?|losing|loss\w*|climb\w*|sink\w*|sank|slump\w*|spik\w*|boost\w*|"
    r"hurt\w*|lift\w*|weigh\w*|rebound\w*|outperform\w*|underperform\w*|target\w*|"
    r"recommend\w*|advi[cs]e\w*|should|opportunit\w*|positive|negative|"
    r"up|down|higher|lower|increas\w*|decreas\w*|rais\w*|doubl\w*|halv\w*|benefit\w*|"
    r"harm(?:s|ed|ing|ful)?|declin\w*|pressur\w*|headwind\w*|tailwind\w*|strengthen\w*|"
    r"weaken\w*|outpac\w*|skyrocket\w*|rocket(?:ed|ing)|plummet\w*|tumbl\w*|"
    r"slid(?:e|es|ing)?|dip(?:s|ped|ping)?|pop(?:s|ped|ping)?|highs|lows|"
    r"(?:record|all[\s-]time)\s+(?:highs?|lows?)|boon|windfall|blow\s+to|wins?\s+for|"
    r"winners?|upgrad\w*|downgrad\w*|favou?r\w*|help(?:s|ed|ing|ful)?|hit(?:s|ting)?|"
    r"squeez\w*|brighten\w*|boom(?:s|ed|ing)?|rout|routs|routed|mooning|to\s+the\s+moon|"
    r"crater(?:s|ed|ing)?|nosediv\w*|skid(?:s|ded|ding)?|erod\w*|(?:under|over)valu\w*|"
    r"(?:good|bad|great|terrible)\s+(?:news\s+)?for|watch|investors?|"
    r"(?:stock|share)\s+prices?|price\s+target\w*)\b",
    re.IGNORECASE,
)
"""Words that state a direction, a price, a target or advice. tests/test_reason_corpus.py
measures every change against lines that must be rejected and lines that must pass."""
AMOUNT = re.compile(
    r"[$€£%]|(?<![A-Za-z])(?:percent|bps|dollars?|billions?|millions?|trillions?|bn)\b"
    r"|\d\.\d",
    re.IGNORECASE,
)
"""Money, a percentage or a figure with decimals: prompts/reason.md leaves out every
amount, even one the post gives."""
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str) -> set[str]:
    """The numbers in `text`, with thousands commas taken out ("1,500" is "1500")."""
    return {found.replace(",", "") for found in NUMBER.findall(text)}


def check_reason(line: str, max_chars: int, words: str, names: Sequence[str] = ()) -> str | None:
    """Why `line` is rejected, or None if it passes. `words` is the post and `names` the
    instruments' names it was given: any other number in the line (a price or a level the
    model made up) is rejected, and so is any amount at all, or a link."""
    if not line:
        return "empty"
    if "\n" in line or "\r" in line:
        return "more than one line"
    if len(line) > max_chars:
        return f"{len(line)} characters, over {max_chars}"
    if found := LINK_LIKE.search(line):
        return f"has a link: {found.group(0)!r}"
    if found := DIRECTION.search(NEUTRAL.sub(" ", line)):
        return f"states a direction, price, target or advice: {found.group(0)!r}"
    if found := AMOUNT.search(line):
        return f"states an amount: {found.group(0)!r}"
    if made_up := numbers_in(line) - numbers_in(" ".join([words, *names])):
        return f"states a number the post doesn't have: {', '.join(sorted(made_up))}"
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
    if reply.problem:
        log.warning("reason line: %s", reply.problem)
        return None
    line = reply.text.strip()
    if problem := check_reason(line, spec.max_chars, words, names):
        log.warning("reason line rejected (%s): %r", problem, line)
        return None
    return line
