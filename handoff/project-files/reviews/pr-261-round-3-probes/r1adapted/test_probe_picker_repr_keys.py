"""Probe: AiPicker is a plain @dataclass whose `secrets` field holds the three ENGINE_ keys
as plain str, so repr(picker) prints them - and so does repr(Scorer) (which holds the
picker), pytest's failure output, `--showlocals`, any log line that formats either with
%r, and error trackers that capture locals. Settings keeps them as SecretStr; the picker
undoes that. Fake keys, no client call.

Passes while the leak is real.
"""

from engine.extract.ai import AiPicker
from engine.extract.rules import current_rules
from engine.extract.score import Scorer
from engine.settings import Settings
from tests.extract_helpers import StubEmbedder, ready_config

FAKE = {
    "openai_key": "<redacted>",
    "anthropic_key": "sk-ant-fake-PROBE-000",
}


def test_the_picker_and_the_scorer_print_the_keys() -> None:
    settings = Settings(database_url="postgresql://probe@127.0.0.1:1/none", **FAKE)  # type: ignore[arg-type]
    assert FAKE["openai_key"] not in repr(settings)  # SecretStr keeps it out here
    config = ready_config()
    picker = AiPicker.from_settings(settings, config)
    assert picker is not None
    scorer = Scorer(current_rules(), StubEmbedder(), picker)
    for text in (repr(picker), repr(scorer)):
        assert all(key in text for key in FAKE.values())
