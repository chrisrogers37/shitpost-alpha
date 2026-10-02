import pytest

from engine.links import SITE_URL, signal_url


def test_signal_url() -> None:
    assert SITE_URL == "https://shitpostalpha.com"
    assert signal_url("k3x9q") == "https://shitpostalpha.com/s/k3x9q"
    assert signal_url("../a b") == "https://shitpostalpha.com/s/..%2Fa%20b"
    with pytest.raises(ValueError):
        signal_url("")
