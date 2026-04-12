"""Tests for ensemble integration in ShitpostAnalyzer (Feature 05)."""

from unittest.mock import AsyncMock, patch

import pytest

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer


@pytest.fixture
def mock_ensemble_result():
    """Build a mock EnsembleResult."""
    from shit.llm.compare_providers import (
        ConsensusResult,
        EnsembleResult,
        ProviderResult,
    )

    consensus = ConsensusResult(
        assets=["TSLA"],
        market_impact={"TSLA": "bearish"},
        confidence=0.85,
        thesis="Negative auto sentiment",
        agreement_level="unanimous",
        asset_agreement=1.0,
        sentiment_agreement=1.0,
        confidence_spread=0.05,
    )
    return EnsembleResult(
        consensus=consensus,
        individual_results=[
            ProviderResult(
                provider="openai",
                model="gpt-4o",
                assets=["TSLA"],
                market_impact={"TSLA": "bearish"},
                confidence=0.87,
                thesis="OpenAI thesis",
                latency_ms=1200,
                success=True,
            ),
            ProviderResult(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                assets=["TSLA"],
                market_impact={"TSLA": "bearish"},
                confidence=0.83,
                thesis="Claude thesis",
                latency_ms=900,
                success=True,
            ),
        ],
        providers_queried=2,
        providers_succeeded=2,
    )


class TestAnalyzerEnsembleIntegration:
    """Test ensemble mode in ShitpostAnalyzer._analyze_shitpost."""

    @patch("shitpost_ai.shitpost_analyzer.settings")
    def test_ensemble_disabled_by_default(self, mock_settings):
        """When ENSEMBLE_ENABLED=False, ensemble_analyzer is None."""
        mock_settings.ENSEMBLE_ENABLED = False
        mock_settings.DATABASE_URL = "sqlite://"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4o"
        mock_settings.CONFIDENCE_THRESHOLD = 0.7
        mock_settings.SYSTEM_LAUNCH_DATE = "2025-01-01"
        mock_settings.get_llm_api_key.return_value = "test-key"
        mock_settings.get_llm_base_url.return_value = None

        analyzer = ShitpostAnalyzer()
        assert analyzer.ensemble_enabled is False
        assert analyzer.ensemble_analyzer is None

    @patch("shitpost_ai.shitpost_analyzer.settings")
    def test_ensemble_enabled_flag(self, mock_settings):
        """When ENSEMBLE_ENABLED=True, ensemble flag is set."""
        mock_settings.ENSEMBLE_ENABLED = True
        mock_settings.ENSEMBLE_PROVIDERS = "openai,anthropic"
        mock_settings.ENSEMBLE_MIN_PROVIDERS = 2
        mock_settings.DATABASE_URL = "sqlite://"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4o"
        mock_settings.CONFIDENCE_THRESHOLD = 0.7
        mock_settings.SYSTEM_LAUNCH_DATE = "2025-01-01"
        mock_settings.get_llm_api_key.return_value = "test-key"
        mock_settings.get_llm_base_url.return_value = None

        analyzer = ShitpostAnalyzer()
        assert analyzer.ensemble_enabled is True

    @pytest.mark.asyncio
    @patch("shitpost_ai.shitpost_analyzer.auto_backfill_prediction")
    @patch("shitpost_ai.shitpost_analyzer.TickerValidator")
    @patch("shitpost_ai.shitpost_analyzer.BypassService")
    @patch("shitpost_ai.shitpost_analyzer.LLMClient")
    @patch("shitpost_ai.shitpost_analyzer.settings")
    async def test_ensemble_analysis_stores_results(
        self,
        mock_settings,
        mock_llm_cls,
        mock_bypass_cls,
        mock_ticker_cls,
        mock_backfill,
        mock_ensemble_result,
    ):
        """Ensemble results are passed to store_analysis."""
        mock_settings.ENSEMBLE_ENABLED = True
        mock_settings.DATABASE_URL = "sqlite://"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4o"
        mock_settings.CONFIDENCE_THRESHOLD = 0.7
        mock_settings.SYSTEM_LAUNCH_DATE = "2025-01-01"
        mock_settings.get_llm_api_key.return_value = "test-key"
        mock_settings.get_llm_base_url.return_value = None

        # Setup mocks
        mock_bypass_cls.return_value.should_bypass_post.return_value = (False, None)
        mock_ticker_cls.return_value.validate_symbols.return_value = ["TSLA"]
        mock_ticker_cls.return_value._company_names = {}
        mock_ticker_cls.return_value._known_active = set()
        mock_ticker_cls.return_value.ALIASES = {}

        analyzer = ShitpostAnalyzer()

        # Mock ensemble analyzer
        mock_ensemble = AsyncMock()
        mock_ensemble.analyze_ensemble.return_value = mock_ensemble_result
        analyzer.ensemble_analyzer = mock_ensemble

        # Mock prediction_ops
        analyzer.prediction_ops = AsyncMock()
        analyzer.prediction_ops.store_analysis.return_value = "42"

        shitpost = {
            "shitpost_id": "test-123",
            "text": "Tesla is destroying the auto industry",
            "content": "<p>Tesla is destroying the auto industry</p>",
            "timestamp": "2026-04-11T12:00:00Z",
            "username": "testuser",
        }

        result = await analyzer._analyze_shitpost(shitpost, dry_run=True)

        assert result is not None
        assert result["assets"] == ["TSLA"]
        assert result["ensemble_results"] is not None
        assert result["ensemble_metadata"] is not None
        assert result["ensemble_metadata"]["agreement_level"] == "unanimous"

    @pytest.mark.asyncio
    @patch("shitpost_ai.shitpost_analyzer.TickerValidator")
    @patch("shitpost_ai.shitpost_analyzer.BypassService")
    @patch("shitpost_ai.shitpost_analyzer.LLMClient")
    @patch("shitpost_ai.shitpost_analyzer.settings")
    async def test_ensemble_fallback_to_single_model(
        self,
        mock_settings,
        mock_llm_cls,
        mock_bypass_cls,
        mock_ticker_cls,
    ):
        """When ensemble fails, falls back to single-model analysis."""
        mock_settings.ENSEMBLE_ENABLED = True
        mock_settings.DATABASE_URL = "sqlite://"
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.LLM_MODEL = "gpt-4o"
        mock_settings.CONFIDENCE_THRESHOLD = 0.7
        mock_settings.SYSTEM_LAUNCH_DATE = "2025-01-01"
        mock_settings.get_llm_api_key.return_value = "test-key"
        mock_settings.get_llm_base_url.return_value = None

        mock_bypass_cls.return_value.should_bypass_post.return_value = (False, None)
        mock_ticker_cls.return_value.validate_symbols.return_value = ["TSLA"]
        mock_ticker_cls.return_value._company_names = {}
        mock_ticker_cls.return_value._known_active = set()
        mock_ticker_cls.return_value.ALIASES = {}

        analyzer = ShitpostAnalyzer()

        # Ensemble fails
        mock_ensemble = AsyncMock()
        mock_ensemble.analyze_ensemble.side_effect = RuntimeError(
            "All providers failed"
        )
        analyzer.ensemble_analyzer = mock_ensemble

        # Single model succeeds
        mock_llm = AsyncMock()
        mock_llm.analyze.return_value = {
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bearish"},
            "confidence": 0.85,
            "thesis": "Fallback thesis",
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
        }
        analyzer.llm_client = mock_llm

        shitpost = {
            "shitpost_id": "test-456",
            "text": "Tesla is done for",
            "content": "<p>Tesla is done for</p>",
            "timestamp": "2026-04-11T12:00:00Z",
        }

        result = await analyzer._analyze_shitpost(shitpost, dry_run=True)

        assert result is not None
        assert "ensemble_results" not in result
        mock_llm.analyze.assert_called_once()
