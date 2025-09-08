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

__all__ = [
    'LLMClient',
    'get_analysis_prompt',
    'get_detailed_analysis_prompt',
    'get_sector_analysis_prompt',
    'get_crypto_analysis_prompt',
    'get_alert_prompt'
]
