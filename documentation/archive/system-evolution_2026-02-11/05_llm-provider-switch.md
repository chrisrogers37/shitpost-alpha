# Phase 05: LLM Provider Switch (Claude/Grok)

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat: add Grok/xAI provider and provider comparison tooling for LLM analysis` |
| **Risk Level** | Low |
| **Estimated Effort** | Low (4-6 hours implementation, 2 hours testing) |
| **Files Created** | `shit/llm/provider_config.py`, `shit/llm/compare_providers.py`, `shitpost_ai/compare_cli.py`, `shit_tests/shit/llm/test_provider_config.py`, `shit_tests/shit/llm/test_compare_providers.py`, `shit_tests/shit/llm/test_llm_client_grok.py` |
| **Files Modified** | `shit/llm/llm_client.py`, `shit/config/shitpost_settings.py`, `shit/llm/__init__.py`, `requirements.txt`, `shit_tests/shit/llm/test_llm_client.py`, `CHANGELOG.md`, `CLAUDE.md` |
| **Files Deleted** | None |

---

## Context: Why This Matters

All changes are additive. The existing OpenAI and Anthropic code paths are only refactored minimally for normalization, and no database schema changes are required. The `llm_provider` and `llm_model` columns already exist on the `predictions` table.

**Cost optimization**: OpenAI GPT-4 is the most expensive option at roughly $30-60/million input tokens. Claude Sonnet models and Grok models offer competitive quality at lower price points.

**Quality improvement**: Different models have different strengths. Claude models tend to produce more structured JSON output with fewer parsing failures. Grok (built by xAI) has strong political/social media context which is directly relevant to analyzing Trump's Truth Social posts.

**Vendor diversification**: Running production on a single LLM provider creates a single point of failure. If OpenAI has an outage or changes pricing, the system should be able to switch providers with a single environment variable change.

**Evaluation capability**: The comparison tooling allows the team to run the same posts through multiple providers side-by-side, measuring confidence scores, asset extraction accuracy, and response latency -- enabling data-driven provider selection.

---

## Dependencies

**None.** This phase has zero dependencies on any other phase. It can be implemented in parallel with all other system-evolution phases. The only external requirements are API keys for the providers you want to test (Anthropic API key for Claude, xAI API key for Grok).

---

## Audit of Current State

### Anthropic Code Path (Already Functional)

The current Anthropic code path at `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py` lines 44-45 and 156-169 is **already correct** for the current `anthropic` SDK (version `>=0.7.0` per `requirements.txt` line 16).

**Key observations**:
- Line 45: Uses `anthropic.AsyncAnthropic(api_key=self.api_key)` -- correct for SDK >=0.7.0
- Line 159: Uses `self.client.messages.create(...)` -- correct Messages API
- Line 162: Passes `system=system_message` as a top-level keyword argument -- correct (the Messages API takes `system` as a separate parameter, not as a message role)
- Line 163-165: Uses `messages=[{"role": "user", "content": prompt}]` -- correct format
- Line 169: Extracts response via `response.content[0].text` -- correct

**One concern**: The `anthropic>=0.7.0` version pin is very old. The current Anthropic SDK is well past 0.40+. While backward-compatible, I recommend updating the pin to `anthropic>=0.40.0` to get the latest models (Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 4 Opus) and improved error handling.

### OpenAI Code Path (Functional, Foundation for Grok)

The OpenAI code path at lines 40-42 and 141-154 uses `AsyncOpenAI(api_key=self.api_key)`. This is correct for `openai>=1.0.0` (the new SDK).

**Critical for Grok**: The `AsyncOpenAI` constructor accepts a `base_url` parameter. Grok's API is OpenAI-compatible, meaning we can reuse the exact same OpenAI code path by passing `base_url="https://api.x.ai/v1"`. This is the standard approach for OpenAI-compatible providers.

### Settings (Needs Extension)

`/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py`:
- Line 38: `LLM_PROVIDER` defaults to `"openai"`, comment says `# openai, anthropic` -- needs to add `grok`
- Line 36-37: Has `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` -- needs `XAI_API_KEY`
- Lines 114-129: `get_llm_api_key()` only handles `openai` and `anthropic` -- needs `grok` branch

### Response Format (Already Normalized)

The `_parse_analysis_response()` method at line 175 works on raw text strings and is provider-agnostic. The `_call_llm()` method already normalizes each provider's response to a plain string (line 154 for OpenAI, line 169 for Anthropic). This pattern just needs extending for Grok.

### Database (No Changes Needed)

The `Prediction` model at `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_models.py` line 150-151 already has `llm_provider` (String(50)) and `llm_model` (String(100)) columns. The `store_analysis` method at `/Users/chris/Projects/shitpost-alpha/shitvault/prediction_operations.py` lines 82-83 already reads these from `analysis_data`. No schema changes are required.

---

## Detailed Implementation Plan

### Step 1: Create Provider Configuration Module

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/llm/provider_config.py`

This module provides a single source of truth for all provider metadata, including supported models, costs, rate limits, and base URLs.

```python
"""
LLM Provider Configuration
Centralized provider metadata for model selection and cost tracking.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model."""
    model_id: str
    display_name: str
    input_cost_per_1m_tokens: float  # USD per 1M input tokens
    output_cost_per_1m_tokens: float  # USD per 1M output tokens
    max_output_tokens: int
    context_window: int
    recommended: bool = False
    notes: str = ""


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    provider_id: str  # 'openai', 'anthropic', 'grok'
    display_name: str
    base_url: Optional[str]  # None for providers with built-in SDK support
    api_key_env_var: str  # Environment variable name for API key
    sdk_type: str  # 'openai' or 'anthropic' -- which SDK to use
    models: List[ModelConfig] = field(default_factory=list)
    rate_limit_rpm: int = 60  # Requests per minute
    notes: str = ""


# --- Provider Definitions ---

OPENAI_MODELS = [
    ModelConfig(
        model_id="gpt-4o",
        display_name="GPT-4o",
        input_cost_per_1m_tokens=2.50,
        output_cost_per_1m_tokens=10.00,
        max_output_tokens=16384,
        context_window=128000,
        recommended=True,
        notes="Best balance of cost and quality for production use"
    ),
    ModelConfig(
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_cost_per_1m_tokens=0.15,
        output_cost_per_1m_tokens=0.60,
        max_output_tokens=16384,
        context_window=128000,
        notes="Cheapest OpenAI option, good for testing"
    ),
    ModelConfig(
        model_id="gpt-4",
        display_name="GPT-4",
        input_cost_per_1m_tokens=30.00,
        output_cost_per_1m_tokens=60.00,
        max_output_tokens=8192,
        context_window=8192,
        notes="Legacy model, expensive. Consider migrating to gpt-4o"
    ),
]

ANTHROPIC_MODELS = [
    ModelConfig(
        model_id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        input_cost_per_1m_tokens=3.00,
        output_cost_per_1m_tokens=15.00,
        max_output_tokens=8192,
        context_window=200000,
        recommended=True,
        notes="Best quality/cost ratio for structured analysis"
    ),
    ModelConfig(
        model_id="claude-haiku-3-5-20241022",
        display_name="Claude 3.5 Haiku",
        input_cost_per_1m_tokens=0.80,
        output_cost_per_1m_tokens=4.00,
        max_output_tokens=8192,
        context_window=200000,
        notes="Fast and cheap, good for high-volume analysis"
    ),
]

GROK_MODELS = [
    ModelConfig(
        model_id="grok-2",
        display_name="Grok 2",
        input_cost_per_1m_tokens=2.00,
        output_cost_per_1m_tokens=10.00,
        max_output_tokens=8192,
        context_window=131072,
        recommended=True,
        notes="Strong social media context, native X/Truth Social understanding"
    ),
    ModelConfig(
        model_id="grok-2-mini",
        display_name="Grok 2 Mini",
        input_cost_per_1m_tokens=0.10,
        output_cost_per_1m_tokens=0.40,
        max_output_tokens=8192,
        context_window=131072,
        notes="Cheapest option, experimental quality"
    ),
]

PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        provider_id="openai",
        display_name="OpenAI",
        base_url=None,  # Uses default OpenAI API
        api_key_env_var="OPENAI_API_KEY",
        sdk_type="openai",
        models=OPENAI_MODELS,
        rate_limit_rpm=60,
        notes="Current production provider"
    ),
    "anthropic": ProviderConfig(
        provider_id="anthropic",
        display_name="Anthropic",
        base_url=None,  # Uses native Anthropic SDK
        api_key_env_var="ANTHROPIC_API_KEY",
        sdk_type="anthropic",
        models=ANTHROPIC_MODELS,
        rate_limit_rpm=60,
        notes="Alternative provider with strong structured output"
    ),
    "grok": ProviderConfig(
        provider_id="grok",
        display_name="xAI (Grok)",
        base_url="https://api.x.ai/v1",
        api_key_env_var="XAI_API_KEY",
        sdk_type="openai",  # Grok uses OpenAI-compatible API
        models=GROK_MODELS,
        rate_limit_rpm=60,
        notes="xAI's model with strong social media/political context"
    ),
}


def get_provider(provider_id: str) -> ProviderConfig:
    """Get provider configuration by ID.

    Args:
        provider_id: Provider identifier ('openai', 'anthropic', 'grok')

    Returns:
        ProviderConfig for the specified provider

    Raises:
        ValueError: If provider_id is not supported
    """
    if provider_id not in PROVIDERS:
        supported = ", ".join(PROVIDERS.keys())
        raise ValueError(
            f"Unsupported provider: '{provider_id}'. "
            f"Supported providers: {supported}"
        )
    return PROVIDERS[provider_id]


def get_recommended_model(provider_id: str) -> Optional[ModelConfig]:
    """Get the recommended model for a provider.

    Args:
        provider_id: Provider identifier

    Returns:
        Recommended ModelConfig, or first model if none marked recommended
    """
    provider = get_provider(provider_id)
    for model in provider.models:
        if model.recommended:
            return model
    return provider.models[0] if provider.models else None


def get_all_provider_ids() -> List[str]:
    """Get list of all supported provider IDs."""
    return list(PROVIDERS.keys())
```

### Step 2: Update Settings Configuration

**File**: `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py`

**Change 1**: Add `XAI_API_KEY` and `LLM_BASE_URL` settings (after line 37)

Current (lines 36-39):
```python
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # openai, anthropic
    LLM_MODEL: str = Field(default="gpt-4", env="LLM_MODEL")
```

New (lines 36-42):
```python
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    XAI_API_KEY: Optional[str] = Field(default=None, env="XAI_API_KEY")
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # openai, anthropic, grok
    LLM_MODEL: str = Field(default="gpt-4", env="LLM_MODEL")
    LLM_BASE_URL: Optional[str] = Field(default=None, env="LLM_BASE_URL")  # Custom base URL for OpenAI-compatible APIs
```

**Change 2**: Extend `get_llm_api_key()` method (lines 114-129)

Current:
```python
    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'"
                )
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'"
                )
            return self.ANTHROPIC_API_KEY
        else:
            raise ValueError(f"Unsupported LLM provider: {self.LLM_PROVIDER}")
```

New:
```python
    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'"
                )
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'"
                )
            return self.ANTHROPIC_API_KEY
        elif self.LLM_PROVIDER == "grok":
            if not self.XAI_API_KEY:
                raise ValueError(
                    "XAI_API_KEY is required when LLM_PROVIDER is 'grok'"
                )
            return self.XAI_API_KEY
        else:
            raise ValueError(f"Unsupported LLM provider: {self.LLM_PROVIDER}")

    def get_llm_base_url(self) -> Optional[str]:
        """Get the base URL for the LLM provider, if applicable.

        Returns:
            Base URL string for OpenAI-compatible providers, or None for native SDKs.
        """
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        if self.LLM_PROVIDER == "grok":
            return "https://api.x.ai/v1"
        return None
```

### Step 3: Update LLMClient for Multi-Provider Support

**File**: `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py`

**Change 1**: Update `__init__` to support Grok via `base_url` (lines 26-47)

Current:
```python
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        """Initialize LLM client with optional overrides.

        Args:
            provider: LLM provider ('openai' or 'anthropic')
            model: Model name (e.g., 'gpt-4', 'claude-3-sonnet')
            api_key: API key (if not provided, uses settings)
        """
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.get_llm_api_key()
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD

        # Initialize client based on provider
        if self.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
```

New:
```python
    def __init__(self, provider: str = None, model: str = None, api_key: str = None, base_url: str = None):
        """Initialize LLM client with optional overrides.

        Args:
            provider: LLM provider ('openai', 'anthropic', or 'grok')
            model: Model name (e.g., 'gpt-4', 'claude-sonnet-4-20250514', 'grok-2')
            api_key: API key (if not provided, uses settings)
            base_url: Custom base URL for OpenAI-compatible APIs (if not provided, uses settings)
        """
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.get_llm_api_key()
        self.base_url = base_url or settings.get_llm_base_url()
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD

        # Determine SDK type: grok uses OpenAI-compatible API
        self._sdk_type = self._get_sdk_type()

        # Initialize client based on SDK type
        if self._sdk_type == "openai":
            from openai import AsyncOpenAI
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self.client = AsyncOpenAI(**client_kwargs)
        elif self._sdk_type == "anthropic":
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _get_sdk_type(self) -> str:
        """Determine which SDK to use for this provider.

        Returns:
            'openai' or 'anthropic'

        Raises:
            ValueError: If provider is not supported
        """
        sdk_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "grok": "openai",  # Grok uses OpenAI-compatible API
        }
        if self.provider not in sdk_map:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        return sdk_map[self.provider]
```

**Change 2**: Update `_call_llm` to use `_sdk_type` instead of `self.provider` (lines 130-173)

Current (lines 141 and 156):
```python
            if self.provider == "openai":
                ...
            elif self.provider == "anthropic":
                ...
```

New:
```python
            if self._sdk_type == "openai":
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_message or "You are a helpful AI assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    ),
                    timeout=30.0  # 30 second timeout
                )
                return response.choices[0].message.content

            elif self._sdk_type == "anthropic":
                response = await asyncio.wait_for(
                    self.client.messages.create(
                        model=self.model,
                        max_tokens=1000,
                        temperature=0.3,
                        system=system_message or "You are a helpful AI assistant.",
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    ),
                    timeout=30.0  # 30 second timeout
                )
                return response.content[0].text
```

This is the key insight: by switching from `self.provider` to `self._sdk_type`, the Grok provider automatically routes through the OpenAI SDK code path with the custom `base_url` already set in `__init__`.

### Step 4: Create Provider Comparison Module

**New file**: `/Users/chris/Projects/shitpost-alpha/shit/llm/compare_providers.py`

```python
"""
LLM Provider Comparison
Run the same content through multiple providers and compare results.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from shit.llm.llm_client import LLMClient
from shit.llm.provider_config import PROVIDERS, get_provider
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
                # Determine model and API key
                from shit.config.shitpost_settings import Settings
                settings = Settings()

                api_key = getattr(settings, provider_config.api_key_env_var, None)
                if not api_key:
                    logger.warning(
                        f"Skipping {provider_id}: no API key found "
                        f"(set {provider_config.api_key_env_var})"
                    )
                    continue

                # Get recommended model for this provider
                from shit.llm.provider_config import get_recommended_model
                model_config = get_recommended_model(provider_id)
                model_id = model_config.model_id if model_config else None

                base_url = provider_config.base_url

                client = LLMClient(
                    provider=provider_id,
                    model=model_id,
                    api_key=api_key,
                    base_url=base_url
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
                result.assets = analysis.get('assets', [])
                result.market_impact = analysis.get('market_impact', {})
                result.confidence = analysis.get('confidence', 0.0)
                result.thesis = analysis.get('thesis', '')
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
        # For each common asset, check if sentiment direction matches
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
                    # Count pairwise agreements
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

    content_preview = comparison.content[:100] + "..." if len(comparison.content) > 100 else comparison.content
    lines.append(f"Content: {content_preview}")
    lines.append("")

    for result in comparison.results:
        lines.append(f"--- {result.provider.upper()} ({result.model}) ---")
        if result.success:
            lines.append(f"  Assets:     {', '.join(result.assets) if result.assets else 'None'}")
            lines.append(f"  Impact:     {result.market_impact}")
            lines.append(f"  Confidence: {result.confidence:.1%}")
            lines.append(f"  Latency:    {result.latency_ms:.0f}ms")
            thesis_preview = result.thesis[:120] + "..." if len(result.thesis) > 120 else result.thesis
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
```

### Step 5: Create Comparison CLI

**New file**: `/Users/chris/Projects/shitpost-alpha/shitpost_ai/compare_cli.py`

```python
"""
Provider Comparison CLI
Compare LLM providers for shitpost analysis quality.
"""

import argparse
import asyncio
import sys
from typing import List, Optional

from shit.llm.compare_providers import ProviderComparator, format_comparison_report
from shit.llm.provider_config import PROVIDERS, get_all_provider_ids
from shit.logging import setup_cli_logging


COMPARE_EXAMPLES = """
Examples:
  # Compare all available providers on sample content
  python -m shitpost_ai compare --content "Tesla is destroying American jobs!"

  # Compare specific providers
  python -m shitpost_ai compare --providers openai anthropic --content "Tariffs on China!"

  # Compare using a post from the database (by shitpost_id)
  python -m shitpost_ai compare --shitpost-id 123456789

  # List available providers and models
  python -m shitpost_ai compare --list-providers
"""


def create_compare_parser() -> argparse.ArgumentParser:
    """Create argument parser for comparison CLI."""
    parser = argparse.ArgumentParser(
        description="Compare LLM provider analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=COMPARE_EXAMPLES
    )

    parser.add_argument(
        "--content",
        type=str,
        help="Content text to analyze across providers"
    )
    parser.add_argument(
        "--shitpost-id",
        type=str,
        help="Analyze a specific shitpost from the database by ID"
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=get_all_provider_ids(),
        help="Specific providers to compare (default: all available)"
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available providers and their models"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser


def list_providers() -> None:
    """Print all available providers and their models."""
    print("\n=== Available LLM Providers ===\n")
    for provider_id, config in PROVIDERS.items():
        print(f"  {provider_id} ({config.display_name})")
        print(f"    SDK: {config.sdk_type}")
        print(f"    API Key Env: {config.api_key_env_var}")
        if config.base_url:
            print(f"    Base URL: {config.base_url}")
        print(f"    Models:")
        for model in config.models:
            rec = " [RECOMMENDED]" if model.recommended else ""
            print(f"      - {model.model_id}{rec}")
            print(f"        Cost: ${model.input_cost_per_1m_tokens}/1M in, ${model.output_cost_per_1m_tokens}/1M out")
            if model.notes:
                print(f"        Note: {model.notes}")
        print()


async def run_comparison(content: str, providers: Optional[List[str]] = None) -> None:
    """Run comparison and print report."""
    comparator = ProviderComparator(providers=providers)

    initialized = await comparator.initialize()
    if len(initialized) < 2:
        print(f"\nOnly {len(initialized)} provider(s) initialized. Need at least 2 for comparison.")
        print("Check that API keys are set for the providers you want to compare.")
        print("Run with --list-providers to see required environment variables.")
        return

    print(f"\nComparing {len(initialized)} providers: {', '.join(initialized)}")
    print("Running analysis...\n")

    result = await comparator.compare(content)
    report = format_comparison_report(result)
    print(report)


async def compare_main() -> None:
    """Main entry point for comparison CLI."""
    parser = create_compare_parser()
    args = parser.parse_args(sys.argv[2:])  # Skip 'compare' subcommand

    setup_cli_logging(verbose=args.verbose)

    if args.list_providers:
        list_providers()
        return

    if args.shitpost_id:
        # Fetch content from database
        from shit.config.shitpost_settings import settings
        from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
        from shitvault.shitpost_operations import ShitpostOperations

        db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        db_client = DatabaseClient(db_config)
        await db_client.initialize()

        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            shitpost_ops = ShitpostOperations(db_ops)
            shitpost = await shitpost_ops.get_shitpost_by_id(args.shitpost_id)

            if not shitpost:
                print(f"Shitpost {args.shitpost_id} not found in database")
                return

            content = shitpost.get('text', '')

        await db_client.cleanup()

    elif args.content:
        content = args.content
    else:
        parser.error("Either --content or --shitpost-id is required")
        return

    await run_comparison(content, providers=args.providers)
```

### Step 6: Update shitpost_ai __main__.py for Compare Subcommand

**File**: `/Users/chris/Projects/shitpost-alpha/shitpost_ai/__main__.py`

Add support for the `compare` subcommand. The modification needs to detect if the first argument is `compare` and route to the comparison CLI, otherwise fall through to the existing analyzer logic.

Add this after the existing imports (line 16) and before the existing `async def main()`:

```python
def _is_compare_command() -> bool:
    """Check if the CLI was invoked with the 'compare' subcommand."""
    return len(sys.argv) > 1 and sys.argv[1] == "compare"
```

Then at the bottom of the file, change lines 85-86:

Current:
```python
if __name__ == "__main__":
    asyncio.run(main())
```

New:
```python
if __name__ == "__main__":
    if _is_compare_command():
        from shitpost_ai.compare_cli import compare_main
        asyncio.run(compare_main())
    else:
        asyncio.run(main())
```

### Step 7: Update LLM Module __init__.py

**File**: `/Users/chris/Projects/shitpost-alpha/shit/llm/__init__.py`

Add export of provider config:

```python
"""
LLM Utilities
Base LLM client and prompt utilities for the Shitpost-Alpha project.
"""

from .llm_client import LLMClient
from .prompts import (
    get_analysis_prompt,
    get_detailed_analysis_prompt,
    get_sector_analysis_prompt,
    get_crypto_analysis_prompt,
    get_alert_prompt
)
from .provider_config import PROVIDERS, get_provider, get_recommended_model

__all__ = [
    'LLMClient',
    'get_analysis_prompt',
    'get_detailed_analysis_prompt',
    'get_sector_analysis_prompt',
    'get_crypto_analysis_prompt',
    'get_alert_prompt',
    'PROVIDERS',
    'get_provider',
    'get_recommended_model',
]
```

### Step 8: Update requirements.txt

**File**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

Change line 16 from:
```
anthropic>=0.7.0
```
to:
```
anthropic>=0.40.0
```

No new packages are needed. Grok uses the `openai` package (already installed) with a custom `base_url`. The `openai>=1.0.0` version already supports the `base_url` parameter.

---

## Test Plan

### New Test File 1: Grok Provider Path

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client_grok.py`

Tests for Grok/xAI provider path in LLMClient. Grok uses the OpenAI-compatible API with a custom base_url.

```
class TestGrokProvider:
    test_grok_initialization
    test_grok_uses_openai_sdk
    test_grok_call_llm
    test_grok_analyze_produces_correct_metadata
    test_grok_default_base_url_from_settings
```

**Approximate count: 5 tests**

### New Test File 2: Provider Config

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_provider_config.py`

```
class TestProviderConfig:
    test_all_providers_defined
    test_get_provider_valid
    test_get_provider_invalid
    test_grok_uses_openai_sdk
    test_anthropic_uses_anthropic_sdk
    test_each_provider_has_models
    test_each_provider_has_recommended_model
    test_get_all_provider_ids
    test_model_costs_are_positive
    test_provider_api_key_env_vars
```

**Approximate count: 10 tests**

### New Test File 3: Provider Comparison

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_compare_providers.py`

```
class TestProviderComparator:
    test_calculate_agreement_identical_results
    test_calculate_agreement_different_assets
    test_format_comparison_report
    test_format_report_with_error
```

**Approximate count: 4 tests**

### Updates to Existing Test File

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client.py`

Add the following tests at the end of the `TestLLMClient` class:

```
    test_sdk_type_openai
    test_sdk_type_anthropic
    test_sdk_type_grok
    test_base_url_not_passed_for_openai
```

**Approximate count: 4 tests**

### Settings Tests

Add to existing settings tests (or create new file if none exists):

Test that `get_llm_api_key()` raises `ValueError` for grok when `XAI_API_KEY` is not set, and returns the key when it is. Test that `get_llm_base_url()` returns `"https://api.x.ai/v1"` for grok and `None` for openai/anthropic.

**Total new tests: ~25**

---

## Documentation Updates

### CLAUDE.md Updates

In the `LLM Configuration` section of the Settings class comment (line 38), update the comment:

```python
LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # openai, anthropic, grok
```

In the **Environment Variables** section, add:

```
# LLM Configuration
XAI_API_KEY=xxx            # xAI/Grok API key (optional, for Grok provider)
LLM_BASE_URL=              # Custom base URL for OpenAI-compatible APIs (optional)
```

Add a new section under **Common Development Tasks**:

```
# Compare LLM providers
python -m shitpost_ai compare --content "Tesla is going bankrupt!"
python -m shitpost_ai compare --list-providers
python -m shitpost_ai compare --providers openai grok --shitpost-id 123456
```

### CHANGELOG.md

Under `## [Unreleased]`:

```markdown
### Added
- **Grok/xAI LLM Provider** - Added xAI's Grok as a third LLM provider option
  - Uses OpenAI-compatible API with custom base_url
  - Supports grok-2 and grok-2-mini models
  - Configure with `LLM_PROVIDER=grok` and `XAI_API_KEY`
- **Provider Configuration Module** - Centralized provider metadata with model costs, rate limits, and recommendations
- **Provider Comparison CLI** - Run `python -m shitpost_ai compare` to analyze content across multiple providers side-by-side
  - Measures latency, asset extraction, sentiment agreement, and confidence spread
  - Supports `--list-providers` to see all models and pricing

### Changed
- **LLMClient** - Refactored to use SDK-type routing instead of provider-name routing
  - Grok routes through OpenAI SDK with custom base_url
  - Added `base_url` parameter for OpenAI-compatible providers
- **Anthropic SDK** - Updated minimum version from 0.7.0 to 0.40.0 for latest model support
```

---

## Stress Testing & Edge Cases

### API Differences Across Providers

**Temperature parameter**: All three providers support `temperature=0.3`. No changes needed.

**Max tokens**: All three support `max_tokens=1000`. Grok's API accepts the same parameter name as OpenAI.

**System message**: OpenAI and Grok use `{"role": "system", "content": ...}` in the messages array. Anthropic uses `system=` as a top-level parameter. The existing code already handles this correctly.

**Response format**: OpenAI and Grok return `response.choices[0].message.content`. Anthropic returns `response.content[0].text`. The existing code already handles this.

### Response Format Variations

**JSON reliability**: Claude models tend to produce cleaner JSON with fewer markdown code fences. GPT-4 sometimes wraps JSON in triple backticks. Grok behavior is similar to GPT-4.

The existing `_extract_json()` method (lines 196-210) uses `text.find('{')` and `text.rfind('}')` which handles all these cases correctly -- it strips any surrounding text/markdown and extracts the JSON object.

**Edge case**: If a model returns the JSON inside a markdown code block, the `_extract_json` method still works because `find('{')` will find the opening brace inside the code block.

### Rate Limits

| Provider | Rate Limit | Notes |
|----------|-----------|-------|
| OpenAI GPT-4o | ~500 RPM (Tier 1) | Higher tiers available |
| Anthropic Claude | ~60 RPM (default) | Varies by model |
| xAI Grok | ~60 RPM (default) | Beta, limits may change |

The existing `llm_rate_limiter` in `/Users/chris/Projects/shitpost-alpha/shit/utils/error_handling.py` (line 200) is set to 50 RPM, which is conservative enough for all providers. No changes needed.

### Error Handling

**Grok-specific errors**: Grok may return different error codes than OpenAI despite using the same SDK. The existing catch-all `except Exception` in `_call_llm()` (line 171) handles this.

**Authentication failures**: If an incorrect `XAI_API_KEY` is provided, the OpenAI SDK will raise an `AuthenticationError`. This is caught by the existing exception handler.

**Model not found**: If `grok-2` is specified but the API doesn't recognize it (e.g., the model name changed), the SDK raises an error that is caught by existing handlers.

### Connection Test

The `_test_connection()` method (lines 61-73) sends a simple "Respond with 'OK'" prompt. This works identically across all three providers since it's just a basic chat completion.

---

## Verification Checklist

After implementation, verify each item:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Run existing LLM tests to ensure no regressions
pytest -v shit_tests/shit/llm/

# 3. Run only the new tests
pytest -v shit_tests/shit/llm/test_llm_client_grok.py
pytest -v shit_tests/shit/llm/test_provider_config.py
pytest -v shit_tests/shit/llm/test_compare_providers.py

# 4. Verify Grok initialization creates AsyncOpenAI with base_url
python3 -c "from shit.llm.provider_config import get_provider; p = get_provider('grok'); print(f'SDK: {p.sdk_type}, URL: {p.base_url}')"

# 5. Verify provider config is importable
python3 -c "from shit.llm import PROVIDERS, get_provider, get_recommended_model; print(f'Providers: {list(PROVIDERS.keys())}')"

# 6. Verify comparison CLI help
python3 -m shitpost_ai compare --list-providers

# 7. Check code style
python3 -m ruff check shit/llm/provider_config.py
python3 -m ruff check shit/llm/compare_providers.py
python3 -m ruff check shit/llm/llm_client.py
python3 -m ruff check shit/config/shitpost_settings.py

# 8. Format code
python3 -m ruff format .

# 9. Run full test suite
pytest -v
```

**Additional verification items**:
- [ ] **Grok initialization**: `LLMClient(provider="grok", model="grok-2", api_key="...", base_url="https://api.x.ai/v1")` creates an `AsyncOpenAI` instance with `base_url`
- [ ] **Grok analysis**: Running `.analyze()` on a Grok client produces output with `llm_provider="grok"` and `llm_model="grok-2"` in the result dict
- [ ] **Anthropic still works**: `LLMClient(provider="anthropic", ...)` still initializes and calls correctly
- [ ] **OpenAI unchanged**: `LLMClient(provider="openai", ...)` still works identically (no `base_url` passed when not needed)
- [ ] **Settings validation**: `get_llm_api_key()` raises `ValueError` for `grok` when `XAI_API_KEY` is missing
- [ ] **Settings base URL**: `get_llm_base_url()` returns `"https://api.x.ai/v1"` for grok, `None` for openai/anthropic
- [ ] **Provider config**: `get_provider("grok")` returns correct config, `get_provider("invalid")` raises `ValueError`
- [ ] **Response parsing**: JSON parsing works identically for all providers (test with same sample JSON)
- [ ] **Database storage**: Predictions stored via Grok analysis have `llm_provider='grok'` and `llm_model='grok-2'`
- [ ] **Lint clean**: `ruff check .` passes
- [ ] **Format clean**: `ruff format .` passes
- [ ] **CHANGELOG updated**: Entry added under `[Unreleased]`

---

## What NOT To Do

1. **Do NOT install a separate `grok` or `xai` Python package.** Grok uses the standard `openai` SDK with a custom `base_url`. Adding a separate package creates an unnecessary dependency.

2. **Do NOT change the database schema.** The `predictions` table already has `llm_provider` and `llm_model` columns (see `/Users/chris/Projects/shitpost-alpha/shitvault/shitpost_models.py` lines 150-152). No migration is needed.

3. **Do NOT modify the prompts.** The prompts in `/Users/chris/Projects/shitpost-alpha/shit/llm/prompts.py` are provider-agnostic. They instruct the LLM to return JSON with a specific structure. All three providers understand these instructions. Do not add provider-specific prompt variations.

4. **Do NOT remove the Anthropic-specific code path.** Anthropic has a fundamentally different API (Messages API vs. Chat Completions), so it cannot be unified with the OpenAI SDK path. Keep the `if _sdk_type == "anthropic"` branch.

5. **Do NOT run the comparison script against production without explicit user approval.** Each comparison call sends content to multiple LLM APIs, costing real money. The comparison CLI is for development/evaluation use.

6. **Do NOT hardcode API keys.** All keys must come from environment variables via the settings singleton. The comparison CLI must also read keys from settings, not accept them as CLI arguments.

7. **Do NOT change the default provider.** Production is running `LLM_PROVIDER=openai` and `LLM_MODEL=gpt-4`. The defaults in settings must remain unchanged. Provider switching should only happen by changing environment variables.

8. **Do NOT make the comparison script a required dependency of the main pipeline.** The comparison module (`compare_providers.py`) must be importable independently. The main `ShitpostAnalyzer` should not import from it.

9. **Do NOT update model pricing without verifying current prices.** The costs listed in `provider_config.py` are approximate. They should include a comment noting they are approximate and may change. Do not use them for billing calculations.

10. **Do NOT break the existing test fixtures.** The `conftest.py` at `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py` sets `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in `setup_test_environment()` (lines 551-554). Add `XAI_API_KEY` to this fixture as well, but do not remove or change existing entries.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py` - Core file to modify: add `base_url` parameter, `_sdk_type` routing, and Grok support
- `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py` - Add `XAI_API_KEY`, `LLM_BASE_URL`, extend `get_llm_api_key()` and add `get_llm_base_url()`
- `/Users/chris/Projects/shitpost-alpha/shit/llm/provider_config.py` - New file: centralized provider metadata (models, costs, base URLs)
- `/Users/chris/Projects/shitpost-alpha/shit/llm/compare_providers.py` - New file: comparison engine for running content through multiple providers
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client.py` - Existing test file: add `_sdk_type` and `base_url` tests to maintain coverage
