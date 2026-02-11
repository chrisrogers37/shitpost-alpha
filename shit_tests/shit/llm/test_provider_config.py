"""
Tests for LLM provider configuration module.
"""

import pytest

from shit.llm.provider_config import (
    PROVIDERS,
    ModelConfig,
    ProviderConfig,
    get_all_provider_ids,
    get_provider,
    get_recommended_model,
)


class TestProviderConfig:
    """Test provider configuration registry."""

    def test_all_providers_defined(self):
        """All expected providers exist in PROVIDERS dict."""
        assert "openai" in PROVIDERS
        assert "anthropic" in PROVIDERS
        assert "grok" in PROVIDERS

    def test_get_provider_valid(self):
        """get_provider returns config for valid provider IDs."""
        for provider_id in ["openai", "anthropic", "grok"]:
            config = get_provider(provider_id)
            assert isinstance(config, ProviderConfig)
            assert config.provider_id == provider_id

    def test_get_provider_invalid(self):
        """get_provider raises ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_provider("nonexistent")

    def test_grok_uses_openai_sdk(self):
        """Grok provider uses the OpenAI SDK type."""
        config = get_provider("grok")
        assert config.sdk_type == "openai"

    def test_anthropic_uses_anthropic_sdk(self):
        """Anthropic provider uses the Anthropic SDK type."""
        config = get_provider("anthropic")
        assert config.sdk_type == "anthropic"

    def test_each_provider_has_models(self):
        """Every provider has at least one model defined."""
        for provider_id, config in PROVIDERS.items():
            assert len(config.models) > 0, f"{provider_id} has no models"

    def test_each_provider_has_recommended_model(self):
        """Every provider has a recommended model."""
        for provider_id in PROVIDERS:
            model = get_recommended_model(provider_id)
            assert model is not None, f"{provider_id} has no recommended model"
            assert isinstance(model, ModelConfig)

    def test_get_all_provider_ids(self):
        """get_all_provider_ids returns all provider keys."""
        ids = get_all_provider_ids()
        assert set(ids) == {"openai", "anthropic", "grok"}

    def test_model_costs_are_positive(self):
        """All model costs are positive numbers."""
        for provider_id, config in PROVIDERS.items():
            for model in config.models:
                assert model.input_cost_per_1m_tokens > 0, (
                    f"{provider_id}/{model.model_id} has non-positive input cost"
                )
                assert model.output_cost_per_1m_tokens > 0, (
                    f"{provider_id}/{model.model_id} has non-positive output cost"
                )

    def test_provider_api_key_env_vars(self):
        """Each provider has a valid API key env var name."""
        expected = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "grok": "XAI_API_KEY",
        }
        for provider_id, env_var in expected.items():
            config = get_provider(provider_id)
            assert config.api_key_env_var == env_var

    def test_grok_has_base_url(self):
        """Grok provider has a base_url set."""
        config = get_provider("grok")
        assert config.base_url == "https://api.x.ai/v1"

    def test_openai_has_no_base_url(self):
        """OpenAI provider has no custom base_url."""
        config = get_provider("openai")
        assert config.base_url is None

    def test_anthropic_has_no_base_url(self):
        """Anthropic provider has no custom base_url."""
        config = get_provider("anthropic")
        assert config.base_url is None
