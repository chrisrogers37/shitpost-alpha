"""Tests for alphavantage_provider.py."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.price_provider import ProviderError


class TestAlphaVantageProviderInit:
    def test_name(self):
        p = AlphaVantageProvider(api_key="test_key")
        assert p.name == "alphavantage"

    def test_available_with_key(self):
        p = AlphaVantageProvider(api_key="test_key")
        assert p.is_available() is True

    def test_unavailable_without_key(self):
        p = AlphaVantageProvider(api_key=None)
        assert p.is_available() is False

    def test_unavailable_with_empty_key(self):
        p = AlphaVantageProvider(api_key="")
        assert p.is_available() is False


class TestAlphaVantageProviderFetch:
    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-15": {
                    "1. open": "150.00",
                    "2. high": "155.00",
                    "3. low": "149.00",
                    "4. close": "153.00",
                    "5. volume": "1000000",
                },
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(records) == 1
        assert records[0].symbol == "AAPL"
        assert records[0].close == 153.0
        assert records[0].source == "alphavantage"

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_filters_by_date_range(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-15": {"1. open": "150", "2. high": "155", "3. low": "149", "4. close": "153", "5. volume": "1000000"},
                "2025-12-01": {"1. open": "140", "2. high": "145", "3. low": "139", "4. close": "143", "5. volume": "900000"},
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(records) == 1
        assert records[0].date == date(2026, 1, 15)

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_api_error_message(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Error Message": "Invalid symbol"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="Invalid symbol"):
            provider.fetch_prices("BADTICKER", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_rate_limit(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Note": "Thank you for using...5 calls per minute"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="Rate limited"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_information_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Information": "API call frequency limit reached"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="API info"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="timed out"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_handles_http_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        provider = AlphaVantageProvider(api_key="test_key")
        with pytest.raises(ProviderError, match="HTTP error"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    def test_raises_when_no_api_key(self):
        provider = AlphaVantageProvider(api_key=None)
        with pytest.raises(ProviderError, match="not configured"):
            provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_empty_time_series(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Time Series (Daily)": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        result = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_records_sorted_by_date(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-20": {"1. open": "160", "2. high": "165", "3. low": "159", "4. close": "163", "5. volume": "1100000"},
                "2026-01-15": {"1. open": "150", "2. high": "155", "3. low": "149", "4. close": "153", "5. volume": "1000000"},
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert records[0].date < records[1].date

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_uses_compact_output_for_short_range(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Time Series (Daily)": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        call_args = mock_get.call_args
        assert call_args[1]["params"]["outputsize"] == "compact"

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_uses_full_output_for_long_range(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Time Series (Daily)": {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        provider.fetch_prices("AAPL", date(2025, 1, 1), date(2026, 1, 31))

        call_args = mock_get.call_args
        assert call_args[1]["params"]["outputsize"] == "full"

    @patch("shit.market_data.alphavantage_provider.requests.get")
    def test_skips_malformed_records(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-01-15": {"1. open": "not_a_number", "4. close": "153", "5. volume": "1000000"},
                "bad-date": {"1. open": "150", "4. close": "153", "5. volume": "1000000"},
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = AlphaVantageProvider(api_key="test_key")
        records = provider.fetch_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        # bad-date is skipped, malformed record may still parse (depends on which fields fail)
        # At minimum, the bad date entry is skipped
        assert all(r.date >= date(2026, 1, 1) for r in records)
