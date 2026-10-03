"""Probe: check_reason passes lines that state a direction. The prompt itself lists "up"
and "down" as banned, but the rule check (the brief's backstop: "A rule check rejects
lines that break this") has neither, nor higher/lower, increase/decrease, benefit,
decline, pressure, headwind/tailwind, strengthen/weaken, good/bad for. Each line below
is under 120 characters, has no $ or %, and returns None (accepted).

Passes while the gap is real.
"""

import pytest

from engine.extract.reason import check_reason

DIRECTIONAL = [
    "Steel tariffs could send Nucor higher",
    "Export curbs may push Nvidia lower",
    "Tariff relief could drive Ford up",
    "Drug price cuts may push Pfizer down",
    "New tariffs benefit US steel makers like Nucor",
    "Boeing orders may increase after the trade deal",
    "Chip export ban could cause Nvidia sales to decline",
    "Puts pressure on Apple's China supply chain",
    "A tailwind for Lockheed Martin and Northrop Grumman",
    "Bad news for Pfizer and Merck",
    "Strengthens the case for owning Exxon",
]


@pytest.mark.parametrize("line", DIRECTIONAL)
def test_directional_lines_pass_the_check(line: str) -> None:
    assert check_reason(line, 120, 'Tariffs on foreign steel and chips') is None
