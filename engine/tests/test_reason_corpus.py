"""The reason line's check against a corpus: lines that state a direction, an amount, advice,
a made-up number or a link must be rejected, and neutral lines must pass. Every change to
the word lists in engine/extract/reason.py is measured here."""

import pytest

from engine.extract.reason import check_reason

POST = (
    "Tariffs on foreign steel will bring 1,500 jobs back to our great steel towns. "
    "Apple is investing $1.5B in Texas, and Section 232 protects us. Nvidia will build "
    "4 chip plants in Arizona, a 500 billion dollar investment. Big win!"
)
NAMES = ("Nucor", "Apple", "3M", "SPDR S&P 500 ETF Trust", "NVIDIA")

REJECTED = [
    # direction
    "Nucor could skyrocket on the tariff news",
    "Apple shares could plummet on the tariff threat",
    "Tariffs may send Nucor to new highs",
    "Nucor at all-time highs",
    "Steel tariffs could be a boon for Nucor",
    "A windfall for Nucor from steel tariffs",
    "Nucor could see an upgrade after the tariff news",
    "A downgrade risk for Nucor from tariffs",
    "Nucor may dip on tariff news",
    "Nucor stock could pop",
    "Steel tariffs favor Nucor over importers",
    "Steel tariffs could squeeze Nucor margins",
    "A blow to Apple's China supply chain",
    "Tariffs could help Nucor and US Steel",
    "Steel tariffs may hit Apple's margins",
    "A win for Nucor and Cleveland-Cliffs",
    "Names 3M among the steel tariff winners",
    "Apple could tumble on the China news",
    "Nucor could slide as tariffs bite",
    "Nucor's outlook brightens with tariffs",
    "Nvidia shares could rise on this",
    "Steel tariffs could send Nucor higher",
    "Export curbs may push Nvidia lower",
    "Tariff relief could drive Ford up",
    "Drug price cuts may push Pfizer down",
    "New tariffs benefit US steel makers like Nucor",
    "American Eagle benefits from its ad",
    "Imports harming the auto industry",
    "Boeing orders may increase after the trade deal",
    "Chip export ban could cause Nvidia sales to decline",
    "Puts pressure on Apple's China supply chain",
    "A tailwind for Lockheed Martin and Northrop Grumman",
    "A headwind for Apple",
    "Bad news for Pfizer and Merck",
    "Strengthens the case for owning Exxon",
    "Expect Nvidia to outpace rivals",
    "Nucor could crater if tariffs end",
    "Apple may nosedive on China tariffs",
    "Tariffs could erode Apple's margins",
    "Steel stocks could boom on the tariffs",
    "Nucor shares rocketed after the post",
    "Tariffs could lift Nucor and Steel Dynamics",
    "Apple may lose ground on tariffs",
    "The post weighs on Apple",
    "Tariffs are positive for Nucor",
    "Bullish for steel makers",
    "Bitcoin to the moon on the reserve plan",
    "Apple sell-off feared over China tariffs",
    # advice, prices, targets
    "Buy Apple",
    "Nucor is a buy",
    "You should look at Apple",
    "Investors may want to watch Boeing",
    "A good opportunity in Nucor",
    "Nucor looks undervalued after the tariff news",
    "Nucor's stock price could react",
    "Analysts' price target for Nucor in focus",
    # amounts, even ones the post has
    "A $500 billion plan",
    "Tariffs of 25 percent on steel",
    "Names Nvidia's 4 chip plants and its 500 billion dollar plan",
    "Names Apple's 1.5 billion Texas investment",
    "Names Apple's 1.5 Texas plant",
    "Apple could hit two hundred dollars",
    # numbers the post doesn't have
    "Apple at 200 after the tariff news",
    "Nvidia's 5 new plants",
    # links
    "See whitehouse.gov for the steel tariff order",
    "Details at https://example.com/nucor",
]

PASSES = [
    "Names Nvidia's plans to build chip plants in Arizona",
    "Names Nvidia's 4 chip plants in Arizona",
    "Steel tariffs and the 1500 jobs they bring back to steel towns",
    "Steel tariffs and the 1,500 jobs they bring back to steel towns",
    "Names the S&P 500 and Nucor in the tariff fight",
    "Names 3M and Nucor in the steel tariff push",
    "Section 232 steel tariffs name Nucor and US Steel",
    "Names steel under the Harmonized Tariff Schedule",
    "Names Harmony Gold in a mining deal",
    "Medicare benefits changes name UnitedHealth",
    "Social Security benefits talk names payroll processors",
    "A lower court ruling on Google's search deal",
    "Government shut down talk names defense contractors",
    "Names Boeing amid a crack down on imports",
    "Fed governor stepping down named in the post",
    "Raises questions about Pfizer's vaccine contract",
    "Sets up a meeting with Apple's chief on Texas plants",
    "A follow-up on Apple's Texas plant",
    "Apple's Texas investment named in a post on jobs",
    "Steel tariffs on foreign makers name Nucor",
    "Post on Chinese chip export rules names Nvidia",
    "Trade talks with Japan name Toyota and Honda",
    "A post on drug pricing names Pfizer and Merck",
    "Names Exxon and Chevron in an oil drilling plan",
    "Names Lockheed Martin in a defense contract post",
    "Names Tesla and Elon Musk in a feud post",
    "Steel tariff post names Cleveland-Cliffs and Nucor",
    "Names Intel in a government stake post",
    "Crypto reserve post names Bitcoin",
    "Interest rate post names the Fed and big banks",
    "A post on Venezuela oil names Chevron",
    "Diplomatic talks with China name Apple and Nvidia",
    "A popular post on Amazon's postal deal",
]


def test_the_corpus_is_big_enough() -> None:
    assert len(REJECTED) >= 50 and len(PASSES) >= 30


@pytest.mark.parametrize("line", REJECTED)
def test_a_line_with_a_direction_amount_advice_or_link_is_rejected(line: str) -> None:
    assert check_reason(line, 120, POST, NAMES) is not None


@pytest.mark.parametrize("line", PASSES)
def test_a_neutral_line_passes(line: str) -> None:
    assert check_reason(line, 120, POST, NAMES) is None


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("", "empty"),
        ("Two\nlines", "more than one line"),
        ("x" * 121, "121 characters, over 120"),
        ("Buy Apple", "states a direction"),
        ("A $500 billion plan", "states an amount"),
        ("Names Apple's 1.5 Texas plant", "states an amount"),
        ("Apple at 200 after the tariff news", "number the post doesn't have: 200"),
        ("See whitehouse.gov for the order", "has a link"),
    ],
)
def test_the_check_says_why(line: str, problem: str) -> None:
    assert problem in (check_reason(line, 120, POST, NAMES) or "")


def test_a_number_only_in_the_names_needs_the_names() -> None:
    assert check_reason("Names 3M in the steel tariff push", 120, POST, NAMES) is None
    assert "number" in (check_reason("Names 3M in the steel tariff push", 120, POST) or "")
