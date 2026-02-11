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
        notes="Best balance of cost and quality for production use",
    ),
    ModelConfig(
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_cost_per_1m_tokens=0.15,
        output_cost_per_1m_tokens=0.60,
        max_output_tokens=16384,
        context_window=128000,
        notes="Cheapest OpenAI option, good for testing",
    ),
    ModelConfig(
        model_id="gpt-4",
        display_name="GPT-4",
        input_cost_per_1m_tokens=30.00,
        output_cost_per_1m_tokens=60.00,
        max_output_tokens=8192,
        context_window=8192,
        notes="Legacy model, expensive. Consider migrating to gpt-4o",
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
        notes="Best quality/cost ratio for structured analysis",
    ),
    ModelConfig(
        model_id="claude-haiku-3-5-20241022",
        display_name="Claude 3.5 Haiku",
        input_cost_per_1m_tokens=0.80,
        output_cost_per_1m_tokens=4.00,
        max_output_tokens=8192,
        context_window=200000,
        notes="Fast and cheap, good for high-volume analysis",
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
        notes="Strong social media context, native X/Truth Social understanding",
    ),
    ModelConfig(
        model_id="grok-2-mini",
        display_name="Grok 2 Mini",
        input_cost_per_1m_tokens=0.10,
        output_cost_per_1m_tokens=0.40,
        max_output_tokens=8192,
        context_window=131072,
        notes="Cheapest option, experimental quality",
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
        notes="Current production provider",
    ),
    "anthropic": ProviderConfig(
        provider_id="anthropic",
        display_name="Anthropic",
        base_url=None,  # Uses native Anthropic SDK
        api_key_env_var="ANTHROPIC_API_KEY",
        sdk_type="anthropic",
        models=ANTHROPIC_MODELS,
        rate_limit_rpm=60,
        notes="Alternative provider with strong structured output",
    ),
    "grok": ProviderConfig(
        provider_id="grok",
        display_name="xAI (Grok)",
        base_url="https://api.x.ai/v1",
        api_key_env_var="XAI_API_KEY",
        sdk_type="openai",  # Grok uses OpenAI-compatible API
        models=GROK_MODELS,
        rate_limit_rpm=60,
        notes="xAI's model with strong social media/political context",
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
