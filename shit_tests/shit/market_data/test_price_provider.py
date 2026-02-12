"""Tests for price_provider.py -- abstract interface, ProviderChain, RawPriceRecord."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from shit.market_data.price_provider import (
    PriceProvider, ProviderChain, ProviderError, RawPriceRecord,
)


class TestRawPriceRecord:
    def test_creation(self):
        r = RawPriceRecord(
            symbol="AAPL", date=date(2026, 1, 15),
            open=150.0, high=155.0, low=149.0, close=153.0,
            volume=1000000, adjusted_close=153.0, source="test",
        )
        assert r.symbol == "AAPL"
        assert r.close == 153.0
        assert r.source == "test"

    def test_optional_fields_can_be_none(self):
        r = RawPriceRecord(
            symbol="X", date=date(2026, 1, 1),
            open=None, high=None, low=None, close=10.0,
            volume=None, adjusted_close=None, source="test",
        )
        assert r.open is None
        assert r.volume is None


class TestProviderError:
    def test_stores_provider_name(self):
        e = ProviderError("yfinance", "API down")
        assert e.provider_name == "yfinance"
        assert "yfinance" in str(e)

    def test_stores_original_error(self):
        original = ValueError("bad")
        e = ProviderError("test", "wrapper", original_error=original)
        assert e.original_error is original

    def test_message_format(self):
        e = ProviderError("alphavantage", "Rate limited")
        assert str(e) == "[alphavantage] Rate limited"

    def test_original_error_default_none(self):
        e = ProviderError("test", "msg")
        assert e.original_error is None


class TestPriceProviderABC:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            PriceProvider()


class TestProviderChain:
    def _make_provider(self, name, available=True, records=None, error=None):
        p = MagicMock(spec=PriceProvider)
        p.name = name
        p.is_available.return_value = available
        if error:
            p.fetch_prices.side_effect = error
        else:
            p.fetch_prices.return_value = records or []
        return p

    def test_returns_first_successful_result(self):
        p1 = self._make_provider("p1", records=[MagicMock()])
        p2 = self._make_provider("p2", records=[MagicMock(), MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1  # From p1
        p2.fetch_prices.assert_not_called()

    def test_falls_back_on_error(self):
        p1 = self._make_provider("p1", error=ProviderError("p1", "down"))
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1

    def test_falls_back_on_empty_result(self):
        p1 = self._make_provider("p1", records=[])
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        result = chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 1

    def test_raises_when_all_fail(self):
        p1 = self._make_provider("p1", error=ProviderError("p1", "down"))
        p2 = self._make_provider("p2", error=ProviderError("p2", "also down"))
        chain = ProviderChain([p1, p2])

        with pytest.raises(ProviderError, match="all_providers"):
            chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    def test_excludes_unavailable_providers(self):
        p1 = self._make_provider("p1", available=False)
        p2 = self._make_provider("p2", records=[MagicMock()])
        chain = ProviderChain([p1, p2])

        assert len(chain.providers) == 1
        assert chain.providers[0].name == "p2"

    def test_empty_chain_logs_warning(self):
        chain = ProviderChain([])
        assert len(chain.providers) == 0

    def test_raises_when_all_return_empty(self):
        """When all providers return empty AND throw no errors, raises ProviderError."""
        p1 = self._make_provider("p1", records=[])
        p2 = self._make_provider("p2", records=[])
        chain = ProviderChain([p1, p2])

        with pytest.raises(ProviderError, match="all_providers"):
            chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    def test_mixed_error_and_empty(self):
        """First provider errors, second returns empty -> raises."""
        p1 = self._make_provider("p1", error=ProviderError("p1", "error"))
        p2 = self._make_provider("p2", records=[])
        chain = ProviderChain([p1, p2])

        with pytest.raises(ProviderError, match="all_providers"):
            chain.fetch_with_fallback("AAPL", date(2026, 1, 1), date(2026, 1, 31))
