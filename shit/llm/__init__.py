"""
LLM Utilities
Base LLM client and prompt utilities for the Shitpost-Alpha project.
"""

from .llm_client import LLMClient
from .compare_providers import (
    ConsensusBuilder,
    ConsensusResult,
    EnsembleResult,
    ProviderComparator,
    ProviderResult,
)
from .prompts import (
    get_analysis_prompt,
    get_detailed_analysis_prompt,
    get_sector_analysis_prompt,
    get_crypto_analysis_prompt,
    get_alert_prompt,
)
from .provider_config import PROVIDERS, get_provider, get_recommended_model

__all__ = [
    "LLMClient",
    "ConsensusBuilder",
    "ConsensusResult",
    "EnsembleResult",
    "ProviderComparator",
    "ProviderResult",
    "get_analysis_prompt",
    "get_detailed_analysis_prompt",
    "get_sector_analysis_prompt",
    "get_crypto_analysis_prompt",
    "get_alert_prompt",
    "PROVIDERS",
    "get_provider",
    "get_recommended_model",
]
