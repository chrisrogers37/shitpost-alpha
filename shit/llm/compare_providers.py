"""
LLM Provider Comparison and Ensemble Analysis

Run the same content through multiple providers, compare results,
and optionally merge into a consensus prediction for production use.
"""

import asyncio
import time
from collections import Counter
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from shit.llm.llm_client import LLMClient
from shit.llm.provider_config import PROVIDERS, get_provider, get_recommended_model
from shit.logging import get_service_logger

logger = get_service_logger("llm_compare")


@dataclass
class ProviderResult:
    """Result from a single provider analysis."""

    provider: str
    model: str
    assets: List[str] = field(default_factory=list)
    market_impact: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    thesis: str = ""
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class ConsensusResult:
    """Merged consensus from multiple provider analyses."""

    assets: List[str] = field(default_factory=list)
    market_impact: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    thesis: str = ""
    agreement_level: str = "single"  # unanimous, majority, split, single
    asset_agreement: float = 0.0
    sentiment_agreement: float = 0.0
    confidence_spread: float = 0.0
    dissenting_views: List[Dict] = field(default_factory=list)

    def to_analysis_dict(self) -> Dict:
        """Convert consensus to the analysis dict format expected by store_analysis."""
        return {
            "assets": self.assets,
            "market_impact": self.market_impact,
            "confidence": self.confidence,
            "thesis": self.thesis,
        }


@dataclass
class EnsembleResult:
    """Full ensemble result with consensus and individual outputs."""

    consensus: ConsensusResult
    individual_results: List[ProviderResult] = field(default_factory=list)
    providers_queried: int = 0
    providers_succeeded: int = 0

    def to_storage_dict(self) -> Dict:
        """Serialize individual results for JSON storage in ensemble_results column."""
        return {
            "providers_queried": self.providers_queried,
            "providers_succeeded": self.providers_succeeded,
            "results": [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "assets": r.assets,
                    "market_impact": r.market_impact,
                    "confidence": r.confidence,
                    "thesis": r.thesis,
                    "latency_ms": round(r.latency_ms, 1),
                    "success": r.success,
                    "error": r.error,
                }
                for r in self.individual_results
            ],
        }

    def to_metadata_dict(self) -> Dict:
        """Serialize agreement metrics for JSON storage in ensemble_metadata column."""
        return {
            "agreement_level": self.consensus.agreement_level,
            "asset_agreement": round(self.consensus.asset_agreement, 3),
            "sentiment_agreement": round(self.consensus.sentiment_agreement, 3),
            "confidence_spread": round(self.consensus.confidence_spread, 3),
            "providers_queried": self.providers_queried,
            "providers_succeeded": self.providers_succeeded,
            "dissenting_views": self.consensus.dissenting_views,
        }


@dataclass
class ComparisonResult:
    """Comparison result across multiple providers."""

    content: str
    results: List[ProviderResult] = field(default_factory=list)
    asset_agreement: float = 0.0  # 0.0-1.0, how much providers agree on assets
    sentiment_agreement: float = 0.0  # 0.0-1.0, how much providers agree on sentiment
    confidence_spread: float = 0.0  # Difference between max and min confidence


class ConsensusBuilder:
    """Merges multiple provider results into a single consensus prediction."""

    def merge(self, results: List[ProviderResult]) -> ConsensusResult:
        """Merge successful provider results into a consensus.

        Args:
            results: List of successful ProviderResult instances.

        Returns:
            ConsensusResult with merged prediction data.
        """
        if not results:
            return ConsensusResult()

        if len(results) == 1:
            r = results[0]
            return ConsensusResult(
                assets=list(r.assets),
                market_impact=dict(r.market_impact),
                confidence=r.confidence,
                thesis=r.thesis,
                agreement_level="single",
            )

        # Union of all detected assets
        all_assets = []
        seen = set()
        for r in results:
            for asset in r.assets:
                upper = asset.upper()
                if upper not in seen:
                    seen.add(upper)
                    all_assets.append(upper)

        # Majority vote on sentiment per asset
        consensus_impact = {}
        for asset in all_assets:
            consensus_impact[asset] = self._vote_sentiment(asset, results)

        # Raw mean confidence (no bonus/penalty — calibration handles adjustment)
        confidences = [r.confidence for r in results]
        mean_confidence = sum(confidences) / len(confidences)
        spread = max(confidences) - min(confidences)

        # Pick thesis from highest-confidence individual result
        best = max(results, key=lambda r: r.confidence)
        thesis = best.thesis

        # Agreement metrics
        asset_agreement = self._compute_asset_agreement(results)
        sentiment_agreement = self._compute_sentiment_agreement(
            results, all_assets, consensus_impact
        )
        agreement_level = self._classify_agreement(
            results, all_assets, consensus_impact
        )
        dissenting_views = self._capture_dissenting_views(
            results, all_assets, consensus_impact
        )

        return ConsensusResult(
            assets=all_assets,
            market_impact=consensus_impact,
            confidence=round(mean_confidence, 4),
            thesis=thesis,
            agreement_level=agreement_level,
            asset_agreement=asset_agreement,
            sentiment_agreement=sentiment_agreement,
            confidence_spread=spread,
            dissenting_views=dissenting_views,
        )

    def _vote_sentiment(self, asset: str, results: List[ProviderResult]) -> str:
        """Majority vote on sentiment for a single asset."""
        votes = []
        for r in results:
            sentiment = r.market_impact.get(asset) or r.market_impact.get(asset.upper())
            if sentiment:
                votes.append(sentiment.lower())

        if not votes:
            return "neutral"

        counts = Counter(votes)
        winner, winner_count = counts.most_common(1)[0]

        # Majority = more than half
        if winner_count > len(votes) / 2:
            return winner
        # Tie between bullish/bearish = neutral (conservative)
        return "neutral"

    def _compute_asset_agreement(self, results: List[ProviderResult]) -> float:
        """Jaccard similarity of asset sets across providers."""
        asset_sets = [set(a.upper() for a in r.assets) for r in results]
        non_empty = [s for s in asset_sets if s]
        if not non_empty:
            return 1.0  # All agree: no assets

        union = set().union(*non_empty)
        intersection = set(non_empty[0])
        for s in non_empty[1:]:
            intersection = intersection.intersection(s)

        return len(intersection) / len(union) if union else 1.0

    def _compute_sentiment_agreement(
        self,
        results: List[ProviderResult],
        all_assets: List[str],
        consensus_impact: Dict[str, str],
    ) -> float:
        """Fraction of per-asset sentiments that match the consensus."""
        total = 0
        matching = 0
        for asset in all_assets:
            for r in results:
                sentiment = r.market_impact.get(asset) or r.market_impact.get(
                    asset.upper()
                )
                if sentiment:
                    total += 1
                    if sentiment.lower() == consensus_impact.get(asset, ""):
                        matching += 1
        return matching / total if total > 0 else 1.0

    def _classify_agreement(
        self,
        results: List[ProviderResult],
        all_assets: List[str],
        consensus_impact: Dict[str, str],
    ) -> str:
        """Classify the agreement level across providers."""
        if len(results) < 2:
            return "single"

        # Check if all providers agree on all asset sentiments
        all_agree = True
        any_majority = True
        for asset in all_assets:
            sentiments = []
            for r in results:
                s = r.market_impact.get(asset) or r.market_impact.get(asset.upper())
                if s:
                    sentiments.append(s.lower())
            if len(set(sentiments)) > 1:
                all_agree = False
                counts = Counter(sentiments)
                winner_count = counts.most_common(1)[0][1]
                if winner_count <= len(sentiments) / 2:
                    any_majority = False

        if all_agree:
            return "unanimous"
        if any_majority:
            return "majority"
        return "split"

    def _capture_dissenting_views(
        self,
        results: List[ProviderResult],
        all_assets: List[str],
        consensus_impact: Dict[str, str],
    ) -> List[Dict]:
        """Record where models disagreed."""
        dissenting = []
        for asset in all_assets:
            sentiments_by_provider = {}
            for r in results:
                s = r.market_impact.get(asset) or r.market_impact.get(asset.upper())
                if s:
                    sentiments_by_provider[r.provider] = s.lower()
            if len(set(sentiments_by_provider.values())) > 1:
                dissenting.append(
                    {
                        "asset": asset,
                        "sentiments": sentiments_by_provider,
                        "consensus": consensus_impact.get(asset, "neutral"),
                    }
                )
        return dissenting


class ProviderComparator:
    """Compare LLM provider analysis results."""

    def __init__(self, providers: Optional[List[str]] = None):
        """Initialize comparator with provider list.

        Args:
            providers: List of provider IDs to compare.
                       Defaults to all providers with available API keys.
        """
        self.provider_ids = providers or list(PROVIDERS.keys())
        self.clients: Dict[str, LLMClient] = {}
        self.consensus_builder = ConsensusBuilder()

    async def initialize(self) -> List[str]:
        """Initialize LLM clients for all specified providers.

        Returns:
            List of provider IDs that were successfully initialized.
        """
        initialized = []

        for provider_id in self.provider_ids:
            try:
                provider_config = get_provider(provider_id)
                # Determine API key from settings
                from shit.config.shitpost_settings import Settings

                s = Settings()

                api_key = getattr(s, provider_config.api_key_env_var, None)
                if not api_key:
                    logger.warning(
                        f"Skipping {provider_id}: no API key found "
                        f"(set {provider_config.api_key_env_var})"
                    )
                    continue

                model_config = get_recommended_model(provider_id)
                model_id = model_config.model_id if model_config else None

                base_url = provider_config.base_url

                client = LLMClient(
                    provider=provider_id,
                    model=model_id,
                    api_key=api_key,
                    base_url=base_url,
                )
                await client.initialize()
                self.clients[provider_id] = client
                initialized.append(provider_id)
                logger.info(f"Initialized {provider_id} with model {model_id}")

            except Exception as e:
                logger.warning(f"Failed to initialize {provider_id}: {e}")

        return initialized

    async def analyze_ensemble(
        self, content: str, prompt_func=None, **kwargs
    ) -> EnsembleResult:
        """Run content through all initialized providers and merge into consensus.

        Args:
            content: Content to analyze.
            prompt_func: Optional prompt function passed to each LLMClient.analyze().
            **kwargs: Additional kwargs for the prompt function.

        Returns:
            EnsembleResult with consensus and individual results.

        Raises:
            RuntimeError: If all providers fail.
        """
        tasks = []
        for provider_id, client in self.clients.items():
            tasks.append(self._analyze_with_provider(provider_id, client, content))

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        for result in raw_results:
            if isinstance(result, Exception):
                failed.append(
                    ProviderResult(
                        provider="unknown",
                        model="unknown",
                        success=False,
                        error=str(result),
                    )
                )
            elif result.success:
                successful.append(result)
            else:
                failed.append(result)

        if not successful:
            raise RuntimeError(
                f"All {len(tasks)} ensemble providers failed: "
                + "; ".join(r.error or "unknown" for r in failed)
            )

        consensus = self.consensus_builder.merge(successful)

        return EnsembleResult(
            consensus=consensus,
            individual_results=successful + failed,
            providers_queried=len(tasks),
            providers_succeeded=len(successful),
        )

    async def compare(self, content: str) -> ComparisonResult:
        """Run content through all initialized providers and compare results.

        Args:
            content: Content to analyze

        Returns:
            ComparisonResult with per-provider results and agreement metrics
        """
        comparison = ComparisonResult(content=content)

        # Run all providers concurrently
        tasks = []
        for provider_id, client in self.clients.items():
            tasks.append(self._analyze_with_provider(provider_id, client, content))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Provider comparison error: {result}")
                continue
            comparison.results.append(result)

        # Calculate agreement metrics
        self._calculate_agreement(comparison)

        return comparison

    async def _analyze_with_provider(
        self, provider_id: str, client: LLMClient, content: str
    ) -> ProviderResult:
        """Analyze content with a single provider, capturing timing."""
        result = ProviderResult(provider=provider_id, model=client.model)

        start_time = time.monotonic()
        try:
            analysis = await client.analyze(content)
            result.latency_ms = (time.monotonic() - start_time) * 1000

            if analysis:
                result.assets = analysis.get("assets", [])
                result.market_impact = analysis.get("market_impact", {})
                result.confidence = analysis.get("confidence", 0.0)
                result.thesis = analysis.get("thesis", "")
                result.raw_response = analysis
                result.success = True
            else:
                result.success = False
                result.error = "Analysis returned None"

        except Exception as e:
            result.latency_ms = (time.monotonic() - start_time) * 1000
            result.success = False
            result.error = str(e)

        return result

    def _calculate_agreement(self, comparison: ComparisonResult) -> None:
        """Calculate agreement metrics across providers."""
        successful = [r for r in comparison.results if r.success]

        if len(successful) < 2:
            return

        # Asset agreement: Jaccard similarity of asset sets
        all_asset_sets = [set(r.assets) for r in successful]
        if any(s for s in all_asset_sets):  # At least one non-empty
            union = set().union(*all_asset_sets)
            intersection = set(all_asset_sets[0])
            for s in all_asset_sets[1:]:
                intersection = intersection.intersection(s)
            comparison.asset_agreement = (
                len(intersection) / len(union) if union else 1.0
            )
        else:
            comparison.asset_agreement = 1.0  # All agree: no assets

        # Sentiment agreement: compare market_impact values
        common_assets = set()
        for r in successful:
            common_assets.update(r.market_impact.keys())

        if common_assets:
            agreements = 0
            comparisons = 0
            for asset in common_assets:
                sentiments = [
                    r.market_impact.get(asset)
                    for r in successful
                    if asset in r.market_impact
                ]
                if len(sentiments) >= 2:
                    for i in range(len(sentiments)):
                        for j in range(i + 1, len(sentiments)):
                            comparisons += 1
                            if sentiments[i] == sentiments[j]:
                                agreements += 1
            comparison.sentiment_agreement = (
                agreements / comparisons if comparisons else 1.0
            )

        # Confidence spread
        confidences = [r.confidence for r in successful]
        comparison.confidence_spread = max(confidences) - min(confidences)


def format_comparison_report(comparison: ComparisonResult) -> str:
    """Format a comparison result as a human-readable report.

    Args:
        comparison: ComparisonResult to format

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("LLM PROVIDER COMPARISON REPORT")
    lines.append("=" * 70)
    lines.append("")

    content_preview = (
        comparison.content[:100] + "..."
        if len(comparison.content) > 100
        else comparison.content
    )
    lines.append(f"Content: {content_preview}")
    lines.append("")

    for result in comparison.results:
        lines.append(f"--- {result.provider.upper()} ({result.model}) ---")
        if result.success:
            lines.append(
                f"  Assets:     {', '.join(result.assets) if result.assets else 'None'}"
            )
            lines.append(f"  Impact:     {result.market_impact}")
            lines.append(f"  Confidence: {result.confidence:.1%}")
            lines.append(f"  Latency:    {result.latency_ms:.0f}ms")
            thesis_preview = (
                result.thesis[:120] + "..."
                if len(result.thesis) > 120
                else result.thesis
            )
            lines.append(f"  Thesis:     {thesis_preview}")
        else:
            lines.append(f"  ERROR: {result.error}")
        lines.append("")

    lines.append("--- AGREEMENT METRICS ---")
    lines.append(f"  Asset Agreement:     {comparison.asset_agreement:.1%}")
    lines.append(f"  Sentiment Agreement: {comparison.sentiment_agreement:.1%}")
    lines.append(f"  Confidence Spread:   {comparison.confidence_spread:.2f}")
    lines.append("=" * 70)

    return "\n".join(lines)
