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
        model_id="gpt-5.4",
        display_name="GPT-5.4",
        input_cost_per_1m_tokens=2.50,
        output_cost_per_1m_tokens=15.00,
        max_output_tokens=16384,
        context_window=128000,
        recommended=True,
        notes="Current flagship, best reasoning and analysis quality",
    ),
    ModelConfig(
        model_id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        input_cost_per_1m_tokens=0.75,
        output_cost_per_1m_tokens=4.50,
        max_output_tokens=16384,
        context_window=128000,
        notes="Cost-effective alternative, good for high-volume",
    ),
]

ANTHROPIC_MODELS = [
    ModelConfig(
        model_id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        input_cost_per_1m_tokens=5.00,
        output_cost_per_1m_tokens=25.00,
        max_output_tokens=128000,
        context_window=1000000,
        recommended=True,
        notes="Most intelligent model, exceptional reasoning and coding",
    ),
    ModelConfig(
        model_id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        input_cost_per_1m_tokens=3.00,
        output_cost_per_1m_tokens=15.00,
        max_output_tokens=64000,
        context_window=1000000,
        notes="Best speed/intelligence ratio, cost-effective alternative to Opus",
    ),
    ModelConfig(
        model_id="claude-haiku-4-5-20251001",
        display_name="Claude Haiku 4.5",
        input_cost_per_1m_tokens=1.00,
        output_cost_per_1m_tokens=5.00,
        max_output_tokens=64000,
        context_window=200000,
        notes="Fastest Claude model, near-frontier intelligence",
    ),
]

GROK_MODELS = [
    ModelConfig(
        model_id="grok-4.20-0309-non-reasoning",
        display_name="Grok 4",
        input_cost_per_1m_tokens=2.00,
        output_cost_per_1m_tokens=6.00,
        max_output_tokens=8192,
        context_window=2000000,
        recommended=True,
        notes="Latest Grok, strong social media/political context, 2M context",
    ),
    ModelConfig(
        model_id="grok-4-1-fast-non-reasoning",
        display_name="Grok 4 Fast",
        input_cost_per_1m_tokens=0.20,
        output_cost_per_1m_tokens=0.50,
        max_output_tokens=8192,
        context_window=2000000,
        notes="Fast and cheap Grok, good for high-volume",
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
