"""Tests for Multi-LLM Ensemble consensus and analysis (Feature 05)."""

from unittest.mock import MagicMock

import pytest

from shit.llm.compare_providers import (
    ConsensusBuilder,
    ConsensusResult,
    EnsembleResult,
    ProviderComparator,
    ProviderResult,
)


# ============================================================
# Fixtures
# ============================================================


def _make_result(
    provider: str = "openai",
    model: str = "gpt-4o",
    assets: list | None = None,
    market_impact: dict | None = None,
    confidence: float = 0.85,
    thesis: str = "Test thesis",
    success: bool = True,
    error: str | None = None,
    latency_ms: float = 1000.0,
) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        model=model,
        assets=["TSLA"] if assets is None else assets,
        market_impact={"TSLA": "bearish"} if market_impact is None else market_impact,
        confidence=confidence,
        thesis=thesis,
        success=success,
        error=error,
        latency_ms=latency_ms,
    )


# ============================================================
# ConsensusBuilder Tests
# ============================================================


class TestConsensusBuilder:
    """Test consensus merge logic."""

    def setup_method(self):
        self.builder = ConsensusBuilder()

    def test_unanimous_agreement(self):
        """3 providers all agree: bearish TSLA."""
        results = [
            _make_result("openai", confidence=0.85, market_impact={"TSLA": "bearish"}),
            _make_result(
                "anthropic",
                model="claude-sonnet-4-20250514",
                confidence=0.80,
                market_impact={"TSLA": "bearish"},
            ),
            _make_result(
                "grok",
                model="grok-2",
                confidence=0.90,
                market_impact={"TSLA": "bearish"},
            ),
        ]
        consensus = self.builder.merge(results)

        assert consensus.agreement_level == "unanimous"
        assert consensus.market_impact["TSLA"] == "bearish"
        assert consensus.assets == ["TSLA"]

    def test_majority_agreement(self):
        """2/3 agree bearish, 1 neutral -> majority bearish."""
        results = [
            _make_result("openai", market_impact={"TSLA": "bearish"}),
            _make_result("anthropic", market_impact={"TSLA": "bearish"}),
            _make_result("grok", market_impact={"TSLA": "neutral"}),
        ]
        consensus = self.builder.merge(results)

        assert consensus.agreement_level == "majority"
        assert consensus.market_impact["TSLA"] == "bearish"

    def test_split_decision_neutral_fallback(self):
        """Each provider has different sentiment -> neutral."""
        results = [
            _make_result("openai", market_impact={"TSLA": "bearish"}),
            _make_result("anthropic", market_impact={"TSLA": "bullish"}),
            _make_result("grok", market_impact={"TSLA": "neutral"}),
        ]
        consensus = self.builder.merge(results)

        assert consensus.agreement_level == "split"
        assert consensus.market_impact["TSLA"] == "neutral"

    def test_single_provider(self):
        """Only 1 result -> single mode, passthrough."""
        result = _make_result("openai", confidence=0.85)
        consensus = self.builder.merge([result])

        assert consensus.agreement_level == "single"
        assert consensus.confidence == 0.85
        assert consensus.assets == ["TSLA"]
        assert consensus.market_impact == {"TSLA": "bearish"}

    def test_empty_results(self):
        consensus = self.builder.merge([])
        assert consensus.agreement_level == "single"
        assert consensus.assets == []

    def test_confidence_is_raw_mean(self):
        """Confidence should be the raw mean — no agreement bonus/penalty."""
        results = [
            _make_result("openai", confidence=0.80),
            _make_result("anthropic", confidence=0.90),
            _make_result("grok", confidence=0.70),
        ]
        consensus = self.builder.merge(results)

        expected = (0.80 + 0.90 + 0.70) / 3
        assert abs(consensus.confidence - expected) < 0.001

    def test_confidence_spread(self):
        results = [
            _make_result("openai", confidence=0.70),
            _make_result("anthropic", confidence=0.90),
        ]
        consensus = self.builder.merge(results)
        assert abs(consensus.confidence_spread - 0.20) < 0.001

    def test_asset_union(self):
        """All provider assets included in consensus."""
        results = [
            _make_result("openai", assets=["TSLA"]),
            _make_result("anthropic", assets=["TSLA", "F"]),
            _make_result("grok", assets=["TSLA", "F", "GM"]),
        ]
        consensus = self.builder.merge(results)

        assert set(consensus.assets) == {"TSLA", "F", "GM"}

    def test_asset_agreement_jaccard(self):
        """Jaccard: intersection/union = 1/3."""
        results = [
            _make_result("openai", assets=["TSLA"]),
            _make_result("anthropic", assets=["TSLA", "F"]),
            _make_result("grok", assets=["TSLA", "F", "GM"]),
        ]
        consensus = self.builder.merge(results)

        # Intersection: {TSLA}, Union: {TSLA, F, GM} -> 1/3
        assert abs(consensus.asset_agreement - 1 / 3) < 0.01

    def test_dissenting_views_captured(self):
        """Disagreements are recorded correctly."""
        results = [
            _make_result(
                "openai",
                assets=["TSLA", "F"],
                market_impact={"TSLA": "bearish", "F": "neutral"},
            ),
            _make_result(
                "grok",
                assets=["TSLA", "F"],
                market_impact={"TSLA": "bearish", "F": "bearish"},
            ),
        ]
        consensus = self.builder.merge(results)

        # TSLA: both agree bearish -> no dissent
        # F: openai neutral, grok bearish -> dissent
        assert len(consensus.dissenting_views) == 1
        assert consensus.dissenting_views[0]["asset"] == "F"

    def test_all_agree_no_assets(self):
        """All providers say no financial relevance."""
        results = [
            _make_result("openai", assets=[], market_impact={}, confidence=0.1),
            _make_result("anthropic", assets=[], market_impact={}, confidence=0.15),
        ]
        consensus = self.builder.merge(results)

        assert consensus.assets == []
        assert consensus.market_impact == {}
        assert consensus.asset_agreement == 1.0

    def test_thesis_from_highest_confidence(self):
        """Thesis is picked from the highest-confidence provider."""
        results = [
            _make_result("openai", confidence=0.70, thesis="OpenAI says bearish"),
            _make_result(
                "anthropic", confidence=0.95, thesis="Claude says very bearish"
            ),
            _make_result("grok", confidence=0.80, thesis="Grok agrees bearish"),
        ]
        consensus = self.builder.merge(results)
        assert consensus.thesis == "Claude says very bearish"

    def test_case_insensitive_assets(self):
        """Asset tickers are uppercased and deduped."""
        results = [
            _make_result("openai", assets=["tsla", "F"]),
            _make_result("anthropic", assets=["TSLA", "f"]),
        ]
        consensus = self.builder.merge(results)
        assert set(consensus.assets) == {"TSLA", "F"}

    def test_to_analysis_dict(self):
        """ConsensusResult.to_analysis_dict() returns correct format."""
        consensus = ConsensusResult(
            assets=["TSLA"],
            market_impact={"TSLA": "bearish"},
            confidence=0.85,
            thesis="Test thesis",
        )
        d = consensus.to_analysis_dict()
        assert d["assets"] == ["TSLA"]
        assert d["market_impact"] == {"TSLA": "bearish"}
        assert d["confidence"] == 0.85
        assert d["thesis"] == "Test thesis"


# ============================================================
# EnsembleResult Serialization Tests
# ============================================================


class TestEnsembleResult:
    """Test EnsembleResult serialization for storage."""

    def test_to_storage_dict(self):
        result = EnsembleResult(
            consensus=ConsensusResult(assets=["TSLA"]),
            individual_results=[
                _make_result("openai"),
                _make_result("anthropic", success=False, error="timeout"),
            ],
            providers_queried=2,
            providers_succeeded=1,
        )
        d = result.to_storage_dict()

        assert d["providers_queried"] == 2
        assert d["providers_succeeded"] == 1
        assert len(d["results"]) == 2
        assert d["results"][0]["provider"] == "openai"
        assert d["results"][1]["success"] is False

    def test_to_metadata_dict(self):
        result = EnsembleResult(
            consensus=ConsensusResult(
                agreement_level="majority",
                asset_agreement=0.333,
                sentiment_agreement=0.833,
                confidence_spread=0.14,
                dissenting_views=[{"asset": "F", "sentiments": {}}],
            ),
            providers_queried=3,
            providers_succeeded=3,
        )
        d = result.to_metadata_dict()

        assert d["agreement_level"] == "majority"
        assert d["providers_queried"] == 3
        assert len(d["dissenting_views"]) == 1


# ============================================================
# ProviderComparator.analyze_ensemble Tests
# ============================================================


class TestProviderComparatorEnsemble:
    """Test ensemble analysis via ProviderComparator."""

    @pytest.mark.asyncio
    async def test_all_providers_succeed(self):
        comparator = ProviderComparator(providers=["openai", "anthropic"])
        comparator.clients = {
            "openai": MagicMock(),
            "anthropic": MagicMock(),
        }

        async def mock_analyze(pid, client, content):
            return _make_result(
                pid,
                confidence=0.85 if pid == "openai" else 0.80,
            )

        comparator._analyze_with_provider = mock_analyze

        result = await comparator.analyze_ensemble("test content")

        assert result.providers_queried == 2
        assert result.providers_succeeded == 2
        assert result.consensus.agreement_level in ("unanimous", "majority", "single")
        assert len(result.individual_results) == 2

    @pytest.mark.asyncio
    async def test_one_provider_fails_graceful_degradation(self):
        comparator = ProviderComparator(providers=["openai", "anthropic", "grok"])
        comparator.clients = {
            "openai": MagicMock(),
            "anthropic": MagicMock(),
            "grok": MagicMock(),
        }

        call_count = 0

        async def mock_analyze(pid, client, content):
            nonlocal call_count
            call_count += 1
            if pid == "grok":
                return _make_result(pid, success=False, error="API timeout")
            return _make_result(pid, confidence=0.85)

        comparator._analyze_with_provider = mock_analyze

        result = await comparator.analyze_ensemble("test content")

        assert result.providers_queried == 3
        assert result.providers_succeeded == 2
        assert len(result.individual_results) == 3  # includes failed

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        comparator = ProviderComparator(providers=["openai"])
        comparator.clients = {"openai": MagicMock()}

        async def mock_analyze(pid, client, content):
            return _make_result(pid, success=False, error="API down")

        comparator._analyze_with_provider = mock_analyze

        with pytest.raises(RuntimeError, match="All.*providers failed"):
            await comparator.analyze_ensemble("test content")

    @pytest.mark.asyncio
    async def test_exception_in_provider_handled(self):
        """asyncio.gather with return_exceptions catches exceptions."""
        comparator = ProviderComparator(providers=["openai", "anthropic"])
        comparator.clients = {
            "openai": MagicMock(),
            "anthropic": MagicMock(),
        }

        async def mock_analyze(pid, client, content):
            if pid == "anthropic":
                raise ConnectionError("Network error")
            return _make_result(pid)

        comparator._analyze_with_provider = mock_analyze

        result = await comparator.analyze_ensemble("test content")

        assert result.providers_succeeded == 1
        assert result.providers_queried == 2
        # The failed one should appear with success=False
        failed = [r for r in result.individual_results if not r.success]
        assert len(failed) == 1
