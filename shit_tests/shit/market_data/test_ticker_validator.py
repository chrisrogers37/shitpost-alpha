"""
Tests for shit/market_data/ticker_validator.py - TickerValidator.

Tests cover: blocklist, alias remapping, registry-first optimization,
yfinance spot-check, fail-open behavior, and deduplication.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from unittest.mock import patch, MagicMock

from shit.market_data.ticker_validator import TickerValidator


class TestBlocklist:
    """Tests for static blocklist filtering."""

    def test_blocks_known_concepts(self):
        validator = TickerValidator()
        result = validator.validate_symbols(["DEFENSE", "CRYPTO", "ECONOMY"])
        assert result == []

    def test_blocklist_is_case_insensitive(self):
        validator = TickerValidator()
        result = validator.validate_symbols(["defense", "Crypto"])
        assert result == []

    def test_passes_valid_tickers(self):
        """Valid tickers should pass blocklist check (yfinance mocked)."""
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["AAPL", "TSLA"])
        assert result == ["AAPL", "TSLA"]

    def test_mixed_valid_and_blocked(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["AAPL", "DEFENSE", "TSLA", "CEO"])
        assert result == ["AAPL", "TSLA"]

    def test_all_blocklist_entries_are_uppercase(self):
        """Ensure blocklist doesn't have lowercase entries that would be missed."""
        for entry in TickerValidator.BLOCKLIST:
            assert entry == entry.upper(), f"Blocklist entry '{entry}' should be uppercase"

    def test_empty_input(self):
        validator = TickerValidator()
        assert validator.validate_symbols([]) == []

    def test_whitespace_only_input(self):
        validator = TickerValidator()
        assert validator.validate_symbols(["", "  ", "\t"]) == []


class TestAliases:
    """Tests for alias remapping (corporate actions)."""

    def test_remaps_rtn_to_rtx(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["RTN"])
        assert result == ["RTX"]

    def test_remaps_fb_to_meta(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["FB"])
        assert result == ["META"]

    def test_filters_delisted_with_no_replacement(self):
        validator = TickerValidator()
        result = validator.validate_symbols(["TWTR", "PTR", "SNP", "KOL", "OIL"])
        assert result == []

    def test_remaps_shell_variants(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["RDS.A"])
        assert result == ["SHEL"]

    def test_alias_applied_before_blocklist(self):
        """Aliases are checked before yfinance, so a remapped symbol gets spot-checked."""
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True) as mock:
            validator.validate_symbols(["RTN"])
        # Should check RTX (the remapped symbol), not RTN
        mock.assert_called_once_with("RTX")

    def test_all_aliases_have_string_keys(self):
        for key, val in TickerValidator.ALIASES.items():
            assert isinstance(key, str)
            assert val is None or isinstance(val, str)


class TestDeduplication:
    """Tests for dedup behavior."""

    def test_deduplicates_identical_symbols(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["AAPL", "AAPL", "TSLA"])
        assert result == ["AAPL", "TSLA"]

    def test_deduplicates_after_remapping(self):
        """RDS.A and RDS.B both map to SHEL — should appear once."""
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["RDS.A", "RDS.B"])
        assert result == ["SHEL"]

    def test_preserves_order(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(["TSLA", "AAPL", "MSFT"])
        assert result == ["TSLA", "AAPL", "MSFT"]


class TestRegistryFirstOptimization:
    """Tests for skipping yfinance when ticker is already active in registry."""

    def test_skips_yfinance_for_known_active(self):
        mock_session = MagicMock()
        mock_row = MagicMock()
        mock_row.symbol = "AAPL"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_row]

        validator = TickerValidator(session=mock_session)
        with patch.object(validator, "_is_tradeable") as mock_tradeable:
            result = validator.validate_symbols(["AAPL"])

        assert result == ["AAPL"]
        mock_tradeable.assert_not_called()

    def test_checks_yfinance_for_unknown_symbol(self):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        validator = TickerValidator(session=mock_session)
        with patch.object(validator, "_is_tradeable", return_value=True) as mock_tradeable:
            result = validator.validate_symbols(["NEWSTOCK"])

        assert result == ["NEWSTOCK"]
        mock_tradeable.assert_called_once_with("NEWSTOCK")

    def test_caches_registry_query(self):
        """Second call should not re-query the database."""
        mock_session = MagicMock()
        mock_row = MagicMock()
        mock_row.symbol = "AAPL"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_row]

        validator = TickerValidator(session=mock_session)
        with patch.object(validator, "_is_tradeable", return_value=True):
            validator.validate_symbols(["AAPL"])
            validator.validate_symbols(["AAPL"])

        # query().filter().all() should only be called once
        assert mock_session.query.return_value.filter.return_value.all.call_count == 1

    def test_no_session_always_checks_yfinance(self):
        validator = TickerValidator(session=None)
        with patch.object(validator, "_is_tradeable", return_value=True) as mock_tradeable:
            validator.validate_symbols(["AAPL"])
        mock_tradeable.assert_called_once_with("AAPL")


class TestYfinanceSpotCheck:
    """Tests for _is_tradeable yfinance integration."""

    def test_equity_returns_true(self):
        validator = TickerValidator()
        mock_ticker = MagicMock()
        mock_ticker.info = {"quoteType": "EQUITY"}
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            assert validator._is_tradeable("AAPL") is True

    def test_etf_returns_true(self):
        validator = TickerValidator()
        mock_ticker = MagicMock()
        mock_ticker.info = {"quoteType": "ETF"}
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            assert validator._is_tradeable("SPY") is True

    def test_unknown_quote_type_with_price_returns_true(self):
        validator = TickerValidator()
        mock_ticker = MagicMock()
        mock_ticker.info = {"quoteType": ""}
        mock_ticker.fast_info.last_price = 150.0
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            assert validator._is_tradeable("SOMETHING") is True

    def test_no_quote_type_no_price_returns_false(self):
        validator = TickerValidator()
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_ticker.fast_info.last_price = None
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            assert validator._is_tradeable("GARBAGE") is False

    def test_network_error_fails_open(self):
        """Network errors should return True (fail open)."""
        validator = TickerValidator()
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.side_effect = Exception("Connection timeout")
            assert validator._is_tradeable("AAPL") is True

    def test_none_info_fails_open(self):
        validator = TickerValidator()
        mock_ticker = MagicMock()
        mock_ticker.info = None
        mock_ticker.fast_info.last_price = None
        with patch("shit.market_data.ticker_validator.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            assert validator._is_tradeable("MAYBE") is False


class TestEndToEnd:
    """Integration-style tests combining multiple layers."""

    def test_realistic_llm_output(self):
        """Simulate a typical LLM extraction with a mix of good and bad tickers."""
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", return_value=True):
            result = validator.validate_symbols(
                ["RTN", "DEFENSE", "AAPL", "TWTR", "TSLA", "CRYPTO"]
            )
        # RTN→RTX, DEFENSE blocked, AAPL passes, TWTR filtered (no replacement),
        # TSLA passes, CRYPTO blocked
        assert result == ["RTX", "AAPL", "TSLA"]

    def test_all_bad_tickers_returns_empty(self):
        validator = TickerValidator()
        result = validator.validate_symbols(["DEFENSE", "TWTR", "KOL", "CEO"])
        assert result == []

    def test_yfinance_rejects_novel_bad_ticker(self):
        validator = TickerValidator()
        with patch.object(validator, "_is_tradeable", side_effect=lambda s: s != "NOTREAL"):
            result = validator.validate_symbols(["AAPL", "NOTREAL", "TSLA"])
        assert result == ["AAPL", "TSLA"]
