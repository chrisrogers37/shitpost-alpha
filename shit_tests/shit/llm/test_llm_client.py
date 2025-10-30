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
        # Patch the imports before creating the client
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            client = LLMClient(
                provider=test_llm_config["provider"],
                model=test_llm_config["model"],
                api_key=test_llm_config["api_key"]
            )
            return client

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
    async def test_initialization_openai(self):
        """Test OpenAI client initialization."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful connection test with "OK" in response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="OK - Test response"))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            # Verify OpenAI client was created
            mock_openai.assert_called_once_with(api_key="test-key")
            assert client.client == mock_client

    @pytest.mark.asyncio
    async def test_initialization_anthropic(self):
        """Test Anthropic client initialization."""
        with patch('anthropic.Anthropic') as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock successful connection test with "OK" in response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="OK - Test response")]
            
            # Mock the messages.create as an async coroutine
            async def mock_create(*args, **kwargs):
                return mock_response
            
            mock_client.messages.create = mock_create
            
            client = LLMClient(
                provider="anthropic",
                model="claude-3-sonnet",
                api_key="test-anthropic-key"
            )
            await client.initialize()
            
            # Verify Anthropic client was created
            mock_anthropic_class.assert_called_once_with(api_key="test-anthropic-key")
            assert client.client == mock_client

    @pytest.mark.asyncio
    async def test_initialization_unsupported_provider(self):
        """Test initialization with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMClient(provider="unsupported", model="test-model", api_key="test-key")

    @pytest.mark.asyncio
    async def test_initialization_connection_error(self):
        """Test initialization with connection error."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock connection test failure
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            # The error gets wrapped as "LLM connection test failed"
            with pytest.raises(Exception, match="LLM connection test failed"):
                await client.initialize()

    @pytest.mark.asyncio
    async def test_analyze_success(self, sample_analysis_response):
        """Test successful content analysis."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            # Mock successful analysis
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(sample_analysis_response)
            ))]
            
            # Set up call sequence: init call returns OK, analyze call returns analysis
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Tesla stock is going up!")
            
            assert result is not None
            assert result['assets'] == sample_analysis_response['assets']
            assert result['confidence'] == sample_analysis_response['confidence']

    @pytest.mark.asyncio
    async def test_analyze_with_custom_prompt(self, sample_analysis_response):
        """Test analysis with custom prompt function."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock init and analysis responses
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(sample_analysis_response)
            ))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            # Custom prompt function
            def custom_prompt(content):
                return f"Custom prompt: {content}"
            
            result = await client.analyze("Test content", prompt_func=custom_prompt)
            
            assert result is not None
            assert result['assets'] == sample_analysis_response['assets']

    @pytest.mark.asyncio
    async def test_analyze_api_error(self):
        """Test analysis with API error."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init but failed analysis
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, Exception("API error")]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_timeout(self):
        """Test analysis with timeout."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init but timeout on analysis
            import asyncio
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, asyncio.TimeoutError("Request timeout")]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            assert result is None

    @pytest.mark.asyncio
    async def test_parse_analysis_response_valid_json(self, sample_analysis_response):
        """Test parsing valid JSON response."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            json_response = json.dumps(sample_analysis_response)
            result = await client._parse_analysis_response(json_response)
            
            assert result == sample_analysis_response

    @pytest.mark.asyncio
    async def test_parse_analysis_response_invalid_json(self):
        """Test parsing invalid JSON response falls back to manual parsing."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            invalid_json = "This is not valid JSON"
            result = await client._parse_analysis_response(invalid_json)
            
            # Should fall back to manual parsing and return a dictionary
            assert result is not None
            assert isinstance(result, dict)
            assert 'assets' in result
            assert 'confidence' in result

    @pytest.mark.asyncio
    async def test_parse_analysis_response_malformed_json(self):
        """Test parsing malformed JSON response (missing required fields)."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            malformed_json = '{"assets": ["TSLA"], "confidence": 0.85}'  # Missing required fields
            result = await client._parse_analysis_response(malformed_json)
            
            # Should fall back to manual parsing
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parse_analysis_response_empty(self):
        """Test parsing empty response."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client._parse_analysis_response("")
            # Falls back to manual parsing which returns a dict
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parse_analysis_response_none(self):
        """Test parsing None response."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client._parse_analysis_response(None)
            assert result is None

    @pytest.mark.asyncio
    async def test_call_llm_openai(self):
        """Test OpenAI LLM call."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful responses
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_call_response = MagicMock()
            mock_call_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_call_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client._call_llm("Test prompt", "Test system message")
            
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_call_llm_anthropic(self):
        """Test Anthropic LLM call."""
        with patch('anthropic.Anthropic') as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client
            
            # Mock successful responses
            call_count = [0]
            
            async def mock_create(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return MagicMock(content=[MagicMock(text="OK")])
                else:
                    return MagicMock(content=[MagicMock(text="Test response")])
            
            mock_client.messages.create = mock_create
            
            client = LLMClient(
                provider="anthropic",
                model="claude-3-sonnet",
                api_key="test-key"
            )
            await client.initialize()
            
            result = await client._call_llm("Test prompt", "Test system message")
            
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_call_llm_error(self):
        """Test LLM call with error."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init but error on call
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, Exception("LLM error")]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client._call_llm("Test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_json_valid(self):
        """Test extracting valid JSON from text."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            text = 'Some text before {"assets": ["TSLA"], "confidence": 0.85} some text after'
            result = client._extract_json(text)
            
            # _extract_json returns a JSON string, not a dict
            assert result is not None
            assert json.loads(result) == {"assets": ["TSLA"], "confidence": 0.85}

    @pytest.mark.asyncio
    async def test_extract_json_invalid(self):
        """Test extracting invalid JSON from text."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            text = "No JSON in this text"
            result = client._extract_json(text)
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_json_multiple(self):
        """Test extracting JSON when multiple JSON objects exist."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            # The _extract_json method extracts from first { to last }
            # Multiple separate JSON objects will result in invalid JSON
            text = 'First: {"key1": "value1"} Second: {"key2": "value2"}'
            result = client._extract_json(text)
            
            # This returns None because the range from first { to last } is not valid JSON
            assert result is None

    @pytest.mark.asyncio
    async def test_parse_manual_response(self):
        """Test manual response parsing fallback."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            response = "Analysis: Tesla stock looks bullish with high confidence"
            result = await client._parse_manual_response(response)
            
            # Manual parsing returns a dict with default structure
            assert result is not None
            assert isinstance(result, dict)
            assert 'assets' in result
            assert 'confidence' in result

    @pytest.mark.asyncio
    async def test_get_analysis_summary(self, sample_analysis_response):
        """Test getting analysis summary."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            summary = await client.get_analysis_summary(sample_analysis_response)
            
            assert isinstance(summary, str)
            assert "TSLA" in summary
            assert "85" in summary  # Confidence as percentage

    @pytest.mark.asyncio
    async def test_get_analysis_summary_empty(self):
        """Test getting summary for empty analysis."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            summary = await client.get_analysis_summary({})
            # Should return a string with default values
            assert isinstance(summary, str)
            assert "None detected" in summary or "Confidence" in summary

    @pytest.mark.asyncio
    async def test_confidence_threshold(self):
        """Test confidence threshold property."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            assert client.confidence_threshold == 0.7  # Default value from settings

    @pytest.mark.asyncio
    async def test_provider_property(self):
        """Test provider property."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            assert client.provider == "openai"

    @pytest.mark.asyncio
    async def test_model_property(self):
        """Test model property."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            assert client.model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_api_key_property(self):
        """Test API key property."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-api-key")
            
            assert client.api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_initialization_with_settings(self):
        """Test initialization using settings."""
        with patch('shit.llm.llm_client.settings') as mock_settings:
            mock_settings.LLM_PROVIDER = "openai"
            mock_settings.LLM_MODEL = "gpt-4"
            mock_settings.get_llm_api_key.return_value = "settings-key"
            mock_settings.CONFIDENCE_THRESHOLD = 0.8
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_openai.return_value = AsyncMock()
                
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
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_openai.return_value = AsyncMock()
                
                client = LLMClient(model="gpt-3.5-turbo")  # Override model only
                
                assert client.provider == "openai"  # From settings
                assert client.model == "gpt-3.5-turbo"  # Overridden
                assert client.api_key == "settings-key"  # From settings

    @pytest.mark.asyncio
    async def test_analyze_short_content(self):
        """Test analysis with content that's too short."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            # Content too short (less than 10 characters)
            result = await client.analyze("Hi")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_empty_content(self):
        """Test analysis with empty content."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client.analyze("")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_whitespace_content(self):
        """Test analysis with whitespace-only content."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client.analyze("   \n\t   ")
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_none_content(self):
        """Test analysis with None content."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client.analyze(None)
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_with_metadata(self, sample_analysis_response):
        """Test analysis includes proper metadata."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init and analysis
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(sample_analysis_response)
            ))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Tesla stock is going up!")
            
            # Verify metadata is included
            assert result is not None
            assert 'meets_threshold' in result
            assert 'analysis_quality' in result
            assert 'original_content' in result
            assert 'llm_provider' in result
            assert 'llm_model' in result
            assert 'analysis_timestamp' in result
            
            # Verify metadata values
            assert result['original_content'] == "Tesla stock is going up!"
            assert result['llm_provider'] == "openai"
            assert result['llm_model'] == "gpt-3.5-turbo"
            assert isinstance(result['analysis_timestamp'], str)

    @pytest.mark.asyncio
    async def test_quality_label_high_confidence(self):
        """Test quality label for high confidence."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            # Test high confidence (>= 0.8)
            quality = client._get_quality_label(0.9)
            assert quality == "high"
            
            quality = client._get_quality_label(0.8)
            assert quality == "high"

    @pytest.mark.asyncio
    async def test_quality_label_medium_confidence(self):
        """Test quality label for medium confidence."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            # Test medium confidence (0.6-0.79)
            quality = client._get_quality_label(0.7)
            assert quality == "medium"
            
            quality = client._get_quality_label(0.6)
            assert quality == "medium"

    @pytest.mark.asyncio
    async def test_quality_label_low_confidence(self):
        """Test quality label for low confidence."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            # Test low confidence (< 0.6)
            quality = client._get_quality_label(0.5)
            assert quality == "low"
            
            quality = client._get_quality_label(0.0)
            assert quality == "low"

    @pytest.mark.asyncio
    async def test_confidence_threshold_check(self, sample_analysis_response):
        """Test that meets_threshold is calculated correctly."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock responses
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            # Test with confidence above threshold (0.7)
            high_confidence_response = sample_analysis_response.copy()
            high_confidence_response['confidence'] = 0.85
            
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(high_confidence_response)
            ))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            
            assert result is not None
            assert result['meets_threshold'] is True
            assert result['analysis_quality'] == "high"

    @pytest.mark.asyncio
    async def test_confidence_threshold_below(self, sample_analysis_response):
        """Test that meets_threshold is False when confidence is below threshold."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock responses
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            # Test with confidence below threshold (0.7)
            low_confidence_response = sample_analysis_response.copy()
            low_confidence_response['confidence'] = 0.5
            
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(
                content=json.dumps(low_confidence_response)
            ))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            
            assert result is not None
            assert result['meets_threshold'] is False
            assert result['analysis_quality'] == "low"

    @pytest.mark.asyncio
    async def test_parse_manual_response_with_asset_keywords(self):
        """Test manual parsing extracts assets from keywords."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            response = "Tesla stock looks great! The company is doing well. Apple corporation is also strong."
            result = await client._parse_manual_response(response)
            
            assert result is not None
            assert isinstance(result, dict)
            assert 'assets' in result
            assert isinstance(result['assets'], list)
            # Should extract some assets from keywords
            assert len(result['assets']) > 0

    @pytest.mark.asyncio
    async def test_parse_manual_response_empty_string(self):
        """Test manual parsing with empty string."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            result = await client._parse_manual_response("")
            
            assert result is not None
            assert isinstance(result, dict)
            assert 'assets' in result
            assert 'confidence' in result
            assert result['assets'] == []  # Should be empty list

    @pytest.mark.asyncio
    async def test_get_timestamp_format(self):
        """Test timestamp format is ISO format."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = AsyncMock()
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            
            timestamp = client._get_timestamp()
            
            assert isinstance(timestamp, str)
            assert len(timestamp) > 10  # Should be substantial
            # Should contain ISO format indicators
            assert "T" in timestamp or "-" in timestamp

    @pytest.mark.asyncio
    async def test_analyze_with_error_handling(self):
        """Test analyze method with error handling."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init but error in analyze
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, Exception("Test error")]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            
            # The error is caught in _call_llm and returns None, which causes analyze to return None
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_with_parse_error(self):
        """Test analyze method when response parsing fails."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            
            # Mock successful init and call but parsing fails
            mock_init_response = MagicMock()
            mock_init_response.choices = [MagicMock(message=MagicMock(content="OK"))]
            
            mock_analysis_response = MagicMock()
            mock_analysis_response.choices = [MagicMock(message=MagicMock(content="Invalid response"))]
            
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_init_response, mock_analysis_response]
            )
            
            client = LLMClient(provider="openai", model="gpt-3.5-turbo", api_key="test-key")
            await client.initialize()
            
            result = await client.analyze("Test content")
            
            # When JSON parsing fails, it falls back to manual parsing which returns a dict
            assert result is not None
            assert isinstance(result, dict)
            assert 'assets' in result
            assert 'confidence' in result
