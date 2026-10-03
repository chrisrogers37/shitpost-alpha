"""Round 2 probes on the reason-line check at 4554d3d (reason.py:18-50).

Each test passes while what it describes is true.
"""

import pytest

from engine.extract.reason import check_reason

POST = (
    "Tariffs on foreign steel will bring 1,500 jobs back to our great steel towns. "
    "Apple is investing $1.5B in Texas. Big win!"
)

# Lines that still state a direction or advice and pass the check.
STILL_PASSING = [
    "Steel tariffs could be a boon for Nucor",
    "A blow to Apple's China supply chain",
    "Tariffs could help Nucor and US Steel",
    "Steel tariffs may hit Apple's margins",
    "A win for Nucor and Cleveland-Cliffs",
    "Nucor could see an upgrade after the tariff news",
    "Apple shares could plummet on the tariff threat",
    "Nucor could skyrocket on the tariff news",
    "Apple could tumble on the China news",
    "Steel tariffs favor Nucor over importers",
    "Apple could hit two hundred dollars",
    "A downgrade risk for Nucor from tariffs",
    "Tariffs may send Nucor to new highs",
    "Nucor at all-time highs",
    "Nucor could slide as tariffs bite",
    "A windfall for Nucor from steel tariffs",
    "Nucor may dip on tariff news",
    "Nucor stock could pop",
    "Steel tariffs could squeeze Nucor margins",
    "Nucor's outlook brightens with tariffs",
]


@pytest.mark.parametrize("line", STILL_PASSING)
def test_direction_or_advice_still_passes(line: str) -> None:
    assert check_reason(line, 120, POST) is None


# Numbers the post has in another form, or that are part of a name: rejected (fail-closed).
FALSE_REJECTIONS = [
    ("Steel tariffs and the 1500 jobs they bring back", "1500"),  # post: "1,500"
    ("Names the S&P 500 and Nucor in the tariff fight", "500"),  # an index name
    ("Names the Fortune 500 steel makers", "500"),
    ("Names 3M and Nucor in the steel tariff push", "3"),  # a company name
    ("Names Apple's 1.5 billion Texas investment", None),  # "$1.5B" -> 1.5 is in the post
]


@pytest.mark.parametrize(("line", "number"), FALSE_REJECTIONS)
def test_numbers_in_another_form_or_in_names(line: str, number: str | None) -> None:
    found = check_reason(line, 120, POST)
    if number is None:
        assert found is None
    else:
        assert found is not None, line
        print(line, "->", found)


def test_names_given_to_the_model_are_not_counted_as_the_posts() -> None:
    # reason_input() passes the instrument names to the model; a number in a name the
    # model was given ("3M") is rejected because check_reason only looks at the post.
    assert check_reason("Names 3M among the steel tariff winners", 120, POST) is not None


def test_amount_words_pass_while_the_symbol_is_rejected() -> None:
    # "$" is an amount, but "dollars" is not: the same amount passes in words.
    assert "amount" in (check_reason("Apple's $1.5 billion Texas plant", 120, POST) or "")
    assert check_reason("Apple's 1.5 billion dollar Texas plant", 120, POST) is None


COMMON_FALSE_POSITIVES = [
    "A lower court ruling on Google's search deal",
    "Government shut down talk names defense contractors",
    "Medicare benefits changes name UnitedHealth",
    "Names Boeing amid a crack down on imports",
    "Raises questions about Pfizer's vaccine contract",
]


@pytest.mark.parametrize("line", COMMON_FALSE_POSITIVES)
def test_neutral_lines_rejected_by_new_words(line: str) -> None:
    assert "direction" in (check_reason(line, 120, POST) or "")
