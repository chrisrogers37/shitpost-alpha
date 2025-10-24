"""
Tests for LLMClient - LLM API interaction and response parsing.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from shit.llm.llm_client import LLMClient


class TestLLMClient:
    """Test cases for LLMClient."""

    @pytest.fixture
    def test_llm_config(self):
        """Test LLM configuration."""
        return {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "api_key": "test-api-key"
        }

    @pytest.fixture
    def llm_client(self, test_llm_config):
        """LLM client instance for testing."""
        return LLMClient(
            provider=test_llm_config["provider"],
            model=test_llm_config["model"],
            api_key=test_llm_config["api_key"]
        )

    @pytest.fixture
    def sample_analysis_response(self):
        """Sample LLM analysis response."""
        return {
            "assets": ["TSLA", "AAPL"],
            "market_impact": {
                "TSLA": "bullish",
                "AAPL": "neutral"
            },
            "confidence": 0.85,
            "thesis": "Positive sentiment about Tesla stock"
        }

    @pytest.mark.asyncio
    async def test_initialization_openai(self, llm_client):
        """Test OpenAI client initialization."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful connection test
            mock_client.chat.completions.create = AsyncMock(return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="Test response"))]
            ))
            
            await llm_client.initialize()
            
            # Verify OpenAI client was created
            mock_openai.assert_called_once_with(api_key="test-api-key")
            assert llm_client.client == mock_client

    @pytest.mark.asyncio
    async def test_initialization_anthropic(self):
        """Test Anthropic client initialization."""
        client = LLMClient(
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="test-anthropic-key"
        )
        
        with patch('shit.llm.llm_client.anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            
            # Mock successful connection test
            mock_client.messages.create = MagicMock(return_value=MagicMock(
                content=[MagicMock(text="Test response")]
            ))
            
            await client.initialize()
            
            # Verify Anthropic client was created
            mock_anthropic.Anthropic.assert_called_once_with(api_key="test-anthropic-key")
            assert client.client == mock_client

    @pytest.mark.asyncio
    async def test_initialization_unsupported_provider(self):
        """Test initialization with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMClient(provider="unsupported", model="test-model", api_key="test-key")

    @pytest.mark.asyncio
    async def test_initialization_connection_error(self, llm_client):
        """Test initialization with connection error."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock connection test failure
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            
            with pytest.raises(Exception, match="Connection failed"):
                await llm_client.initialize()

    @pytest.mark.asyncio
    async def test_analyze_success(self, llm_client, sample_analysis_response):
        """Test successful content analysis."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful analysis
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(sample_analysis_response)
            ))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            await llm_client.initialize()
            
            result = await llm_client.analyze("Tesla stock is going up!")
            
            assert result == sample_analysis_response
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_custom_prompt(self, llm_client, sample_analysis_response):
        """Test analysis with custom prompt function."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful analysis
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(sample_analysis_response)
            ))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            await llm_client.initialize()
            
            # Custom prompt function
            def custom_prompt(content):
                return f"Custom prompt: {content}"
            
            result = await llm_client.analyze("Test content", prompt_func=custom_prompt)
            
            assert result == sample_analysis_response

    @pytest.mark.asyncio
    async def test_analyze_api_error(self, llm_client):
        """Test analysis with API error."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock API error
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API error")
            )
            
            await llm_client.initialize()
            
            result = await llm_client.analyze("Test content")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_timeout(self, llm_client):
        """Test analysis with timeout."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock timeout
            import asyncio
            mock_client.chat.completions.create = AsyncMock(
                side_effect=asyncio.TimeoutError("Request timeout")
            )
            
            await llm_client.initialize()
            
            result = await llm_client.analyze("Test content")
            assert result is None

    @pytest.mark.asyncio
    async def test_parse_analysis_response_valid_json(self, llm_client, sample_analysis_response):
        """Test parsing valid JSON response."""
        json_response = json.dumps(sample_analysis_response)
        result = await llm_client._parse_analysis_response(json_response)
        
        assert result == sample_analysis_response

    @pytest.mark.asyncio
    async def test_parse_analysis_response_invalid_json(self, llm_client):
        """Test parsing invalid JSON response."""
        invalid_json = "This is not valid JSON"
        result = await llm_client._parse_analysis_response(invalid_json)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_analysis_response_malformed_json(self, llm_client):
        """Test parsing malformed JSON response."""
        malformed_json = '{"assets": ["TSLA"], "confidence": 0.85}'  # Missing required fields
        result = await llm_client._parse_analysis_response(malformed_json)
        
        # Should return None due to validation failure
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_analysis_response_empty(self, llm_client):
        """Test parsing empty response."""
        result = await llm_client._parse_analysis_response("")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_analysis_response_none(self, llm_client):
        """Test parsing None response."""
        result = await llm_client._parse_analysis_response(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_call_llm_openai(self, llm_client):
        """Test OpenAI LLM call."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            await llm_client.initialize()
            
            result = await llm_client._call_llm("Test prompt", "Test system message")
            
            assert result == "Test response"
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_anthropic(self):
        """Test Anthropic LLM call."""
        client = LLMClient(
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="test-key"
        )
        
        with patch('shit.llm.llm_client.anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            
            # Mock successful response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Test response")]
            mock_client.messages.create = MagicMock(return_value=mock_response)
            
            await client.initialize()
            
            result = await client._call_llm("Test prompt", "Test system message")
            
            assert result == "Test response"
            mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_error(self, llm_client):
        """Test LLM call with error."""
        with patch('shit.llm.llm_client.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock error response
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("LLM error")
            )
            
            await llm_client.initialize()
            
            result = await llm_client._call_llm("Test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_json_valid(self, llm_client):
        """Test extracting valid JSON from text."""
        text = 'Some text before {"assets": ["TSLA"], "confidence": 0.85} some text after'
        result = llm_client._extract_json(text)
        
        expected = {"assets": ["TSLA"], "confidence": 0.85}
        assert result == expected

    @pytest.mark.asyncio
    async def test_extract_json_invalid(self, llm_client):
        """Test extracting invalid JSON from text."""
        text = "No JSON in this text"
        result = llm_client._extract_json(text)
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_json_multiple(self, llm_client):
        """Test extracting JSON when multiple JSON objects exist."""
        text = 'First: {"key1": "value1"} Second: {"key2": "value2"}'
        result = llm_client._extract_json(text)
        
        # Should return the first valid JSON
        expected = {"key1": "value1"}
        assert result == expected

    @pytest.mark.asyncio
    async def test_parse_manual_response(self, llm_client):
        """Test manual response parsing fallback."""
        response = "Analysis: Tesla stock looks bullish with high confidence"
        result = await llm_client._parse_manual_response(response)
        
        # Should return None for manual parsing (not implemented)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_analysis_summary(self, llm_client, sample_analysis_response):
        """Test getting analysis summary."""
        summary = await llm_client.get_analysis_summary(sample_analysis_response)
        
        assert isinstance(summary, str)
        assert "TSLA" in summary
        assert "bullish" in summary
        assert "0.85" in summary

    @pytest.mark.asyncio
    async def test_get_analysis_summary_empty(self, llm_client):
        """Test getting summary for empty analysis."""
        summary = await llm_client.get_analysis_summary({})
        assert summary == "No analysis available"

    @pytest.mark.asyncio
    async def test_confidence_threshold(self, llm_client):
        """Test confidence threshold property."""
        assert llm_client.confidence_threshold == 0.7  # Default value

    @pytest.mark.asyncio
    async def test_provider_property(self, llm_client):
        """Test provider property."""
        assert llm_client.provider == "openai"

    @pytest.mark.asyncio
    async def test_model_property(self, llm_client):
        """Test model property."""
        assert llm_client.model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_api_key_property(self, llm_client):
        """Test API key property."""
        assert llm_client.api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_initialization_with_settings(self):
        """Test initialization using settings."""
        with patch('shit.llm.llm_client.settings') as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.LLM_MODEL = "gpt-4"
            mock_settings.get_llm_api_key.return_value = "settings-key"
            mock_settings.CONFIDENCE_THRESHOLD = 0.8
            
            client = LLMClient()  # No parameters, should use settings
            
            assert client.provider == "openai"
            assert client.model == "gpt-4"
            assert client.api_key == "settings-key"
            assert client.confidence_threshold == 0.8

    @pytest.mark.asyncio
    async def test_initialization_with_partial_override(self):
        """Test initialization with partial parameter override."""
        with patch('shit.llm.llm_client.settings') as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.LLM_MODEL = "gpt-4"
            mock_settings.get_llm_api_key.return_value = "settings-key"
            mock_settings.CONFIDENCE_THRESHOLD = 0.7
            
            client = LLMClient(model="gpt-3.5-turbo")  # Override model only
            
            assert client.provider == "openai"  # From settings
            assert client.model == "gpt-3.5-turbo"  # Overridden
            assert client.api_key == "settings-key"  # From settings
