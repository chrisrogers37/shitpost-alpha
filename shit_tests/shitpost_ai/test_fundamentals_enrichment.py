"""
Tests for fundamentals enrichment in LLM analysis prompts.

Covers: pre-extraction of tickers from text, fundamentals lookup from
ticker_registry, enhanced content formatting, prompt guidance injection,
and the market cap formatter.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer, _format_market_cap
from shit.llm.prompts import get_analysis_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FUNDAMENTALS = [
    {
        "symbol": "AAPL",
        "company_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 3_200_000_000_000,
        "pe_ratio": 29.8,
        "forward_pe": 27.5,
        "beta": 1.21,
        "dividend_yield": 0.005,
        "asset_type": "stock",
        "exchange": "NASDAQ",
    },
    {
        "symbol": "TSLA",
        "company_name": "Tesla, Inc.",
        "sector": "Consumer Cyclical",
        "industry": "Auto Manufacturers",
        "market_cap": 800_000_000_000,
        "pe_ratio": 65.2,
        "forward_pe": 55.0,
        "beta": 2.05,
        "dividend_yield": None,
        "asset_type": "stock",
        "exchange": "NASDAQ",
    },
]


@pytest.fixture
def analyzer():
    """Create a ShitpostAnalyzer with mocked dependencies."""
    with patch("shitpost_ai.shitpost_analyzer.settings") as mock_settings:
        mock_settings.DATABASE_URL = "sqlite:///:memory:"
        mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4"

        with (
            patch("shitpost_ai.shitpost_analyzer.DatabaseConfig"),
            patch("shitpost_ai.shitpost_analyzer.DatabaseClient"),
            patch("shitpost_ai.shitpost_analyzer.LLMClient") as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.initialize = AsyncMock()
            mock_llm.test_connection = AsyncMock()
            mock_llm_cls.return_value = mock_llm

            a = ShitpostAnalyzer(mode="incremental")
            a.db_ops = MagicMock()
            a.shitpost_ops = MagicMock()
            a.prediction_ops = MagicMock()
            # Pre-populate ticker validator caches to avoid DB calls
            a.ticker_validator._known_active = {"AAPL", "TSLA", "NVDA", "GOOGL", "MSFT"}
            a.ticker_validator._company_names = {
                "apple inc.": "AAPL",
                "apple": "AAPL",
                "tesla, inc.": "TSLA",
                "tesla": "TSLA",
                "nvidia corporation": "NVDA",
                "nvidia": "NVDA",
                "alphabet inc.": "GOOGL",
                "alphabet": "GOOGL",
                "google": "GOOGL",
                "microsoft corporation": "MSFT",
                "microsoft": "MSFT",
            }
            return a


# ---------------------------------------------------------------------------
# _format_market_cap
# ---------------------------------------------------------------------------


class TestFormatMarketCap:
    def test_trillions(self):
        assert _format_market_cap(3_200_000_000_000) == "$3.2T"

    def test_billions(self):
        assert _format_market_cap(150_500_000_000) == "$150.5B"

    def test_millions(self):
        assert _format_market_cap(500_000_000) == "$500M"

    def test_small(self):
        assert _format_market_cap(50_000) == "$50,000"

    def test_exact_trillion_boundary(self):
        assert _format_market_cap(1_000_000_000_000) == "$1.0T"

    def test_exact_billion_boundary(self):
        assert _format_market_cap(1_000_000_000) == "$1.0B"


# ---------------------------------------------------------------------------
# _pre_extract_tickers
# ---------------------------------------------------------------------------


class TestPreExtractTickers:
    def test_dollar_sign_mentions(self, analyzer):
        result = analyzer._pre_extract_tickers("Buy $AAPL and $TSLA now!")
        assert "AAPL" in result
        assert "TSLA" in result

    def test_company_names(self, analyzer):
        result = analyzer._pre_extract_tickers("Apple and Tesla are doing great")
        assert "AAPL" in result
        assert "TSLA" in result

    def test_uppercase_words_matching_active(self, analyzer):
        result = analyzer._pre_extract_tickers("NVDA is crushing it today")
        assert "NVDA" in result

    def test_deduplication(self, analyzer):
        result = analyzer._pre_extract_tickers("$AAPL Apple AAPL everywhere")
        assert result.count("AAPL") == 1

    def test_max_cap_10(self, analyzer):
        # Create text with more than 10 tickers
        text = " ".join(f"${chr(65 + i)}{chr(65 + i)}" for i in range(15))
        result = analyzer._pre_extract_tickers(text)
        assert len(result) <= 10

    def test_empty_text(self, analyzer):
        assert analyzer._pre_extract_tickers("") == []

    def test_none_text(self, analyzer):
        assert analyzer._pre_extract_tickers(None) == []

    def test_no_tickers_found(self, analyzer):
        result = analyzer._pre_extract_tickers("Just a normal sentence about weather")
        assert result == []

    def test_mixed_strategies(self, analyzer):
        """Dollar sign + company name + uppercase word all found."""
        result = analyzer._pre_extract_tickers("$AAPL Apple is great and NVDA too")
        assert "AAPL" in result
        assert "NVDA" in result


# ---------------------------------------------------------------------------
# _match_company_names
# ---------------------------------------------------------------------------


class TestMatchCompanyNames:
    def test_matches_full_name(self, analyzer):
        result = analyzer._match_company_names("Apple Inc. is doing well")
        assert "AAPL" in result

    def test_matches_short_name(self, analyzer):
        result = analyzer._match_company_names("Tesla stock is up")
        assert "TSLA" in result

    def test_case_insensitive(self, analyzer):
        result = analyzer._match_company_names("APPLE is amazing")
        assert "AAPL" in result

    def test_no_match(self, analyzer):
        result = analyzer._match_company_names("Nothing relevant here")
        assert result == []

    def test_multiple_matches(self, analyzer):
        result = analyzer._match_company_names("Apple and Google are competing")
        assert "AAPL" in result
        assert "GOOGL" in result

    def test_empty_company_names(self, analyzer):
        analyzer.ticker_validator._company_names = {}
        result = analyzer._match_company_names("Apple is great")
        assert result == []


# ---------------------------------------------------------------------------
# _lookup_fundamentals
# ---------------------------------------------------------------------------


class TestLookupFundamentals:
    def test_returns_fundamentals_for_known_symbols(self):
        mock_row = MagicMock(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=3_200_000_000_000,
            pe_ratio=29.8,
            forward_pe=27.5,
            beta=1.21,
            dividend_yield=0.005,
            asset_type="stock",
            exchange="NASDAQ",
        )
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [
            mock_row
        ]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("shit.db.sync_session.get_session", return_value=mock_ctx):
            result = ShitpostAnalyzer._lookup_fundamentals(["AAPL"])

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["market_cap"] == 3_200_000_000_000
        assert result[0]["sector"] == "Technology"

    def test_empty_symbols_returns_empty(self):
        assert ShitpostAnalyzer._lookup_fundamentals([]) == []

    def test_unknown_symbol_returns_empty(self):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("shit.db.sync_session.get_session", return_value=mock_ctx):
            result = ShitpostAnalyzer._lookup_fundamentals(["NOTREAL"])

        assert result == []


# ---------------------------------------------------------------------------
# _prepare_enhanced_content with fundamentals
# ---------------------------------------------------------------------------


class TestPrepareEnhancedContentWithFundamentals:
    def _make_signal_data(self):
        return {
            "text": "Apple is doing great!",
            "username": "realDonaldTrump",
            "timestamp": "2026-04-09T14:30:00",
            "platform": "truth_social",
            "replies_count": 100,
            "reblogs_count": 500,
            "favourites_count": 1000,
            "account_verified": True,
            "account_followers_count": 7_500_000,
            "has_media": False,
            "mentions": [],
            "tags": [],
        }

    def test_with_fundamentals_includes_asset_context(self, analyzer):
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(), fundamentals=SAMPLE_FUNDAMENTALS
        )
        assert "ASSET CONTEXT (from market data):" in content
        assert "AAPL (Apple Inc.)" in content
        assert "Technology / Consumer Electronics" in content
        assert "$3.2T" in content
        assert "P/E: 29.8" in content
        assert "Beta: 1.21" in content

    def test_without_fundamentals_no_asset_context(self, analyzer):
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(), fundamentals=[]
        )
        assert "ASSET CONTEXT" not in content

    def test_none_fundamentals_no_asset_context(self, analyzer):
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(), fundamentals=None
        )
        assert "ASSET CONTEXT" not in content

    def test_fundamentals_with_no_dividend(self, analyzer):
        """TSLA has no dividend — should not show Div field."""
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(),
            fundamentals=[SAMPLE_FUNDAMENTALS[1]],  # TSLA
        )
        assert "TSLA (Tesla, Inc.)" in content
        assert "Div:" not in content

    def test_fundamentals_with_missing_fields(self, analyzer):
        """Ticker with only symbol — should still render a line."""
        sparse = {
            "symbol": "XYZ",
            "company_name": None,
            "sector": None,
            "industry": None,
            "market_cap": None,
            "pe_ratio": None,
            "forward_pe": None,
            "beta": None,
            "dividend_yield": None,
            "asset_type": None,
            "exchange": None,
        }
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(), fundamentals=[sparse]
        )
        assert "- XYZ" in content

    def test_still_contains_base_content(self, analyzer):
        """Fundamentals should be additive — base content still present."""
        content = analyzer._prepare_enhanced_content(
            self._make_signal_data(), fundamentals=SAMPLE_FUNDAMENTALS
        )
        assert "Content: Apple is doing great!" in content
        assert "Author: realDonaldTrump" in content
        assert "Engagement:" in content


# ---------------------------------------------------------------------------
# Prompt guidance injection
# ---------------------------------------------------------------------------


class TestPromptFundamentalsGuidance:
    def test_includes_guidance_when_has_fundamentals(self):
        prompt = get_analysis_prompt("Test content", has_fundamentals=True)
        assert "ASSET CONTEXT is provided" in prompt
        assert "Large-cap stocks" in prompt

    def test_excludes_guidance_when_no_fundamentals(self):
        prompt = get_analysis_prompt("Test content", has_fundamentals=False)
        assert "Large-cap stocks" not in prompt

    def test_default_has_no_guidance(self):
        prompt = get_analysis_prompt("Test content")
        assert "Large-cap stocks" not in prompt

    def test_ticker_guidelines_always_present(self):
        """Base ticker guidelines should always be in the prompt."""
        prompt_with = get_analysis_prompt("Test", has_fundamentals=True)
        prompt_without = get_analysis_prompt("Test", has_fundamentals=False)
        assert "Use CURRENT, actively-traded US ticker symbols" in prompt_with
        assert "Use CURRENT, actively-traded US ticker symbols" in prompt_without


# ---------------------------------------------------------------------------
# Integration: _analyze_shitpost with fundamentals
# ---------------------------------------------------------------------------


class TestAnalyzeShitpostWithFundamentals:
    @pytest.mark.asyncio
    async def test_fundamentals_passed_to_enhanced_content(self, analyzer):
        """Verify fundamentals flow from pre-extraction through to enhanced content."""
        sample_data = {
            "shitpost_id": "test_001",
            "text": "Apple is killing it!",
            "username": "realDonaldTrump",
            "timestamp": "2026-04-09T14:30:00",
            "platform": "truth_social",
            "replies_count": 100,
            "reblogs_count": 500,
            "favourites_count": 1000,
            "account_verified": True,
            "account_followers_count": 7_500_000,
            "has_media": False,
            "mentions": [],
            "tags": [],
        }
        sample_result = {
            "assets": ["AAPL"],
            "market_impact": {"AAPL": "bullish"},
            "confidence": 0.7,
            "thesis": "Positive endorsement",
        }

        with (
            patch.object(
                analyzer.bypass_service,
                "should_bypass_post",
                return_value=(False, None),
            ),
            patch.object(
                analyzer,
                "_lookup_fundamentals",
                return_value=SAMPLE_FUNDAMENTALS[:1],
            ),
            patch.object(
                analyzer.llm_client,
                "analyze",
                new_callable=AsyncMock,
                return_value=sample_result,
            ) as mock_llm,
            patch.object(
                analyzer,
                "_enhance_analysis_with_shitpost_data",
                return_value=sample_result,
            ),
            patch.object(
                analyzer.prediction_ops,
                "store_analysis",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch.object(
                analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
            ),
        ):
            result = await analyzer._analyze_shitpost(sample_data)

            assert result == sample_result
            # Verify LLM was called with has_fundamentals=True
            call_kwargs = mock_llm.call_args
            assert call_kwargs.kwargs.get("has_fundamentals") is True
            # Verify enhanced content includes ASSET CONTEXT
            content_arg = call_kwargs.args[0]
            assert "ASSET CONTEXT" in content_arg
            assert "AAPL (Apple Inc.)" in content_arg
