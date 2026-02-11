"""
Tests for Grok/xAI provider path in LLMClient.
Grok uses the OpenAI-compatible API with a custom base_url.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from shit.llm.llm_client import LLMClient


class TestGrokProvider:
    """Test Grok provider initialization and routing."""

    def test_grok_initialization(self):
        """Grok provider creates an AsyncOpenAI client with base_url."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = AsyncMock()

            client = LLMClient(
                provider="grok",
                model="grok-2",
                api_key="test-xai-key",
                base_url="https://api.x.ai/v1",
            )

            mock_openai.assert_called_once_with(
                api_key="test-xai-key",
                base_url="https://api.x.ai/v1",
            )
            assert client.provider == "grok"
            assert client.model == "grok-2"
            assert client.base_url == "https://api.x.ai/v1"

    def test_grok_uses_openai_sdk(self):
        """Grok provider routes through the OpenAI SDK type."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = AsyncMock()

            client = LLMClient(
                provider="grok",
                model="grok-2",
                api_key="test-xai-key",
                base_url="https://api.x.ai/v1",
            )

            assert client._sdk_type == "openai"

    @pytest.mark.asyncio
    async def test_grok_call_llm(self):
        """Grok call routes through OpenAI chat completions path."""
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock init and call responses
            mock_init_response = MagicMock()
            mock_init_response.choices = [
                MagicMock(message=MagicMock(content="OK"))
            ]

            mock_call_response = MagicMock()
            mock_call_response.choices = [
                MagicMock(message=MagicMock(content="Grok response"))
            ]

            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_call_response]
            )

            client = LLMClient(
                provider="grok",
                model="grok-2",
                api_key="test-xai-key",
                base_url="https://api.x.ai/v1",
            )
            await client.initialize()

            result = await client._call_llm("Test prompt")
            assert result == "Grok response"

    @pytest.mark.asyncio
    async def test_grok_analyze_produces_correct_metadata(self):
        """Grok analysis includes provider='grok' in metadata."""
        sample_response = {
            "assets": ["TSLA"],
            "market_impact": {"TSLA": "bullish"},
            "confidence": 0.8,
            "thesis": "Test thesis",
        }

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            mock_init_response = MagicMock()
            mock_init_response.choices = [
                MagicMock(message=MagicMock(content="OK"))
            ]

            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [
                MagicMock(
                    message=MagicMock(content=json.dumps(sample_response))
                )
            ]

            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )

            client = LLMClient(
                provider="grok",
                model="grok-2",
                api_key="test-xai-key",
                base_url="https://api.x.ai/v1",
            )
            await client.initialize()

            result = await client.analyze(
                "Tesla is making great American cars!"
            )

            assert result is not None
            assert result["llm_provider"] == "grok"
            assert result["llm_model"] == "grok-2"

    def test_grok_default_base_url_from_settings(self):
        """Grok gets base_url from settings when not provided explicitly."""
        with patch("shit.llm.llm_client.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "grok"
            mock_settings.LLM_MODEL = "grok-2"
            mock_settings.get_llm_api_key.return_value = "test-xai-key"
            mock_settings.get_llm_base_url.return_value = (
                "https://api.x.ai/v1"
            )
            mock_settings.CONFIDENCE_THRESHOLD = 0.7

            with patch("openai.AsyncOpenAI") as mock_openai:
                mock_openai.return_value = AsyncMock()

                client = LLMClient()

                assert client.provider == "grok"
                assert client.base_url == "https://api.x.ai/v1"
                mock_openai.assert_called_once_with(
                    api_key="test-xai-key",
                    base_url="https://api.x.ai/v1",
                )
