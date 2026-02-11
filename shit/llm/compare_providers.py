"""
LLM Provider Comparison
Run the same content through multiple providers and compare results.
"""

import asyncio
import time
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
class ComparisonResult:
    """Comparison result across multiple providers."""
    content: str
    results: List[ProviderResult] = field(default_factory=list)
    asset_agreement: float = 0.0  # 0.0-1.0, how much providers agree on assets
    sentiment_agreement: float = 0.0  # 0.0-1.0, how much providers agree on sentiment
    confidence_spread: float = 0.0  # Difference between max and min confidence


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
