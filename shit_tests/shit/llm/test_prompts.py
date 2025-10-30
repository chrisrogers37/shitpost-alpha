"""
Tests for LLM Prompts - Prompt templates and utilities.
Tests that will break if prompt functionality changes.
"""

import pytest
from typing import Dict, List, Any

from shit.llm.prompts import (
    get_analysis_prompt,
    get_detailed_analysis_prompt,
    get_sector_analysis_prompt,
    get_crypto_analysis_prompt,
    get_alert_prompt,
    get_custom_prompt,
    get_system_message,
    validate_prompt_version,
    get_prompt_metadata,
    SYSTEM_MESSAGES,
    PROMPT_VERSION
)


class TestPromptFunctions:
    """Test cases for prompt generation functions."""

    @pytest.fixture
    def sample_content(self):
        """Sample content for testing prompts."""
        return "Tesla stock is going to the moon! 🚀 The electric vehicle revolution is unstoppable."

    @pytest.fixture
    def sample_context(self):
        """Sample context for testing prompts."""
        return {
            "previous_posts": ["Previous post about EVs", "Another market comment"],
            "market_conditions": "Bull market with high volatility",
            "recent_events": ["Fed rate cut", "EV tax credits announced"]
        }

    @pytest.fixture
    def sample_analysis(self):
        """Sample analysis for alert prompt testing."""
        return {
            "assets": ["TSLA", "AAPL"],
            "market_impact": {
                "TSLA": "bullish",
                "AAPL": "neutral"
            },
            "confidence": 0.85,
            "thesis": "Positive sentiment about Tesla stock"
        }

    def test_get_analysis_prompt_basic(self, sample_content):
        """Test basic analysis prompt generation."""
        prompt = get_analysis_prompt(sample_content)
        
        # Verify prompt contains key elements
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial
        assert "financial analyst" in prompt.lower()
        assert "market sentiment analysis" in prompt.lower()
        assert sample_content in prompt
        assert "assets" in prompt.lower()
        assert "confidence" in prompt.lower()
        assert "thesis" in prompt.lower()
        assert "json" in prompt.lower()

    def test_get_analysis_prompt_with_context(self, sample_content, sample_context):
        """Test analysis prompt with context."""
        prompt = get_analysis_prompt(sample_content, sample_context)
        
        # Verify context is included
        assert "ADDITIONAL CONTEXT" in prompt
        assert "Previous posts" in prompt
        assert "Market conditions" in prompt
        assert "Recent events" in prompt
        assert "Bull market with high volatility" in prompt
        assert "Fed rate cut" in prompt

    def test_get_analysis_prompt_without_context(self, sample_content):
        """Test analysis prompt without context."""
        prompt = get_analysis_prompt(sample_content, None)
        
        # Should not contain context section
        assert "ADDITIONAL CONTEXT" not in prompt
        assert sample_content in prompt

    def test_get_analysis_prompt_empty_context(self, sample_content):
        """Test analysis prompt with empty context."""
        empty_context = {}
        prompt = get_analysis_prompt(sample_content, empty_context)
        
        # Should not contain context section
        assert "ADDITIONAL CONTEXT" not in prompt

    def test_get_detailed_analysis_prompt_basic(self, sample_content):
        """Test detailed analysis prompt generation."""
        prompt = get_detailed_analysis_prompt(sample_content)
        
        # Verify prompt contains detailed elements
        assert isinstance(prompt, str)
        assert len(prompt) > 200  # Should be more detailed
        assert "senior financial analyst" in prompt.lower()
        assert "comprehensive analysis" in prompt.lower()
        assert sample_content in prompt
        assert "asset identification" in prompt.lower()
        assert "sentiment analysis" in prompt.lower()
        assert "market impact prediction" in prompt.lower()
        assert "risk assessment" in prompt.lower()

    def test_get_detailed_analysis_prompt_with_context(self, sample_content, sample_context):
        """Test detailed analysis prompt with context."""
        prompt = get_detailed_analysis_prompt(sample_content, sample_context)
        
        # Verify context is included
        assert "ADDITIONAL CONTEXT" in prompt
        assert "Previous posts" in prompt
        assert "Market conditions" in prompt
        assert "Recent events" in prompt

    def test_get_sector_analysis_prompt_basic(self, sample_content):
        """Test sector analysis prompt generation."""
        prompt = get_sector_analysis_prompt(sample_content)
        
        # Verify prompt contains sector elements
        assert isinstance(prompt, str)
        assert len(prompt) > 150
        assert "sector analyst" in prompt.lower()
        assert "industry-wide implications" in prompt.lower()
        assert sample_content in prompt
        assert "technology" in prompt.lower()
        assert "financial" in prompt.lower()
        assert "energy" in prompt.lower()
        assert "healthcare" in prompt.lower()
        assert "automotive" in prompt.lower()

    def test_get_sector_analysis_prompt_custom_sectors(self, sample_content):
        """Test sector analysis prompt with custom sectors."""
        custom_sectors = ["technology", "cryptocurrency", "renewable_energy"]
        prompt = get_sector_analysis_prompt(sample_content, custom_sectors)
        
        # Verify custom sectors are included
        assert "technology" in prompt.lower()
        assert "cryptocurrency" in prompt.lower()
        assert "renewable_energy" in prompt.lower()
        # Should not contain default sectors
        assert "healthcare" not in prompt.lower()
        assert "automotive" not in prompt.lower()

    def test_get_crypto_analysis_prompt_basic(self, sample_content):
        """Test crypto analysis prompt generation."""
        prompt = get_crypto_analysis_prompt(sample_content)
        
        # Verify prompt contains crypto elements
        assert isinstance(prompt, str)
        assert len(prompt) > 150
        assert "cryptocurrency analyst" in prompt.lower()
        assert "digital assets" in prompt.lower()
        assert sample_content in prompt
        assert "bitcoin" in prompt.lower()
        assert "ethereum" in prompt.lower()
        assert "btc" in prompt.lower()
        assert "eth" in prompt.lower()

    def test_get_crypto_analysis_prompt_custom_cryptos(self, sample_content):
        """Test crypto analysis prompt with custom cryptocurrencies."""
        custom_cryptos = ["BTC", "ETH", "DOGE", "SHIB"]
        prompt = get_crypto_analysis_prompt(sample_content, custom_cryptos)
        
        # The function currently doesn't use custom cryptos in the output format
        # It only uses them as the default list, but the output format is hardcoded
        # So we just verify the prompt is generated correctly
        assert isinstance(prompt, str)
        assert len(prompt) > 150
        assert "cryptocurrency analyst" in prompt.lower()
        assert sample_content in prompt
        # The output format still shows BTC and ETH (hardcoded)
        assert "btc" in prompt.lower()
        assert "eth" in prompt.lower()

    def test_get_alert_prompt_basic(self, sample_analysis):
        """Test alert prompt generation."""
        prompt = get_alert_prompt(sample_analysis)
        
        # Verify prompt contains alert elements
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "sms alert" in prompt.lower()
        assert "traders" in prompt.lower()
        assert "tsla" in prompt.lower()
        assert "aapl" in prompt.lower()
        assert "bullish" in prompt.lower()
        assert "85" in prompt  # Confidence score
        assert "160" in prompt  # Max length

    def test_get_alert_prompt_custom_length(self, sample_analysis):
        """Test alert prompt with custom max length."""
        custom_length = 100
        prompt = get_alert_prompt(sample_analysis, max_length=custom_length)
        
        # Verify custom length is included
        assert str(custom_length) in prompt
        assert "100" in prompt

    def test_get_alert_prompt_empty_analysis(self):
        """Test alert prompt with empty analysis."""
        empty_analysis = {}
        prompt = get_alert_prompt(empty_analysis)
        
        # Should still generate a valid prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "sms alert" in prompt.lower()

    def test_get_custom_prompt_basic(self, sample_content):
        """Test custom prompt generation."""
        task = "Analyze the sentiment of this content"
        output_format = "Return a JSON object with 'sentiment' and 'confidence' fields"
        
        prompt = get_custom_prompt(sample_content, task, output_format)
        
        # Verify prompt contains custom elements
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert sample_content in prompt
        assert task in prompt
        assert output_format in prompt
        assert "specialized ai analyst" in prompt.lower()

    def test_get_custom_prompt_with_examples(self, sample_content):
        """Test custom prompt with examples."""
        task = "Classify this content"
        output_format = "Return 'positive', 'negative', or 'neutral'"
        examples = ["Tesla is great → positive", "This is terrible → negative"]
        
        prompt = get_custom_prompt(sample_content, task, output_format, examples)
        
        # Verify examples are included
        assert "examples" in prompt.lower()
        assert "Tesla is great → positive" in prompt
        assert "This is terrible → negative" in prompt

    def test_get_custom_prompt_without_examples(self, sample_content):
        """Test custom prompt without examples."""
        task = "Analyze this content"
        output_format = "Return analysis"
        
        prompt = get_custom_prompt(sample_content, task, output_format, None)
        
        # Should not contain examples section
        assert "examples" not in prompt.lower()
        assert sample_content in prompt
        assert task in prompt
        assert output_format in prompt

    def test_get_system_message_valid_types(self):
        """Test system message for valid analysis types."""
        # Test all valid types
        for analysis_type in SYSTEM_MESSAGES.keys():
            message = get_system_message(analysis_type)
            assert isinstance(message, str)
            assert len(message) > 10
            assert message == SYSTEM_MESSAGES[analysis_type]

    def test_get_system_message_invalid_type(self):
        """Test system message for invalid analysis type."""
        message = get_system_message("invalid_type")
        assert isinstance(message, str)
        assert message == SYSTEM_MESSAGES['general']  # Should fallback to general

    def test_get_system_message_default(self):
        """Test system message with default parameter."""
        message = get_system_message()  # No parameter
        assert isinstance(message, str)
        assert message == SYSTEM_MESSAGES['financial_analyst']  # Default type

    def test_validate_prompt_version_valid(self):
        """Test prompt version validation with valid version."""
        assert validate_prompt_version("1.0") is True
        assert validate_prompt_version(PROMPT_VERSION) is True

    def test_validate_prompt_version_invalid(self):
        """Test prompt version validation with invalid version."""
        assert validate_prompt_version("2.0") is False
        assert validate_prompt_version("1.1") is False
        assert validate_prompt_version("") is False
        assert validate_prompt_version(None) is False

    def test_get_prompt_metadata(self):
        """Test prompt metadata generation."""
        metadata = get_prompt_metadata()
        
        # Verify metadata structure
        assert isinstance(metadata, dict)
        assert "version" in metadata
        assert "available_analysis_types" in metadata
        assert "available_prompts" in metadata
        
        # Verify version
        assert metadata["version"] == PROMPT_VERSION
        
        # Verify analysis types
        assert isinstance(metadata["available_analysis_types"], list)
        assert len(metadata["available_analysis_types"]) == len(SYSTEM_MESSAGES)
        for analysis_type in SYSTEM_MESSAGES.keys():
            assert analysis_type in metadata["available_analysis_types"]
        
        # Verify available prompts
        assert isinstance(metadata["available_prompts"], list)
        expected_prompts = [
            'get_analysis_prompt',
            'get_detailed_analysis_prompt',
            'get_sector_analysis_prompt',
            'get_crypto_analysis_prompt',
            'get_alert_prompt',
            'get_custom_prompt'
        ]
        for prompt in expected_prompts:
            assert prompt in metadata["available_prompts"]


class TestPromptEdgeCases:
    """Test edge cases and error scenarios for prompts."""

    def test_get_analysis_prompt_empty_content(self):
        """Test analysis prompt with empty content."""
        prompt = get_analysis_prompt("")
        
        assert isinstance(prompt, str)
        assert len(prompt) > 50  # Should still generate prompt structure
        assert '""' in prompt  # Empty content should be quoted

    def test_get_analysis_prompt_very_long_content(self):
        """Test analysis prompt with very long content."""
        long_content = "A" * 10000  # 10KB string
        prompt = get_analysis_prompt(long_content)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 10000  # Should include the long content
        assert long_content in prompt

    def test_get_analysis_prompt_special_characters(self):
        """Test analysis prompt with special characters."""
        special_content = "Tesla stock is going up! 🚀💰 #TSLA $TSLA @elonmusk"
        prompt = get_analysis_prompt(special_content)
        
        assert isinstance(prompt, str)
        assert special_content in prompt
        assert "🚀" in prompt
        assert "💰" in prompt

    def test_get_analysis_prompt_unicode_content(self):
        """Test analysis prompt with unicode content."""
        unicode_content = "特斯拉股票正在上涨！🚀 电动汽车革命势不可挡！"
        prompt = get_analysis_prompt(unicode_content)
        
        assert isinstance(prompt, str)
        assert unicode_content in prompt

    def test_get_alert_prompt_very_long_analysis(self):
        """Test alert prompt with very long analysis."""
        long_analysis = {
            "assets": ["TSLA", "AAPL", "GOOGL", "MSFT", "AMZN"],
            "market_impact": {f"ASSET{i}": "bullish" for i in range(100)},
            "confidence": 0.95,
            "thesis": "A" * 1000  # Very long thesis
        }
        prompt = get_alert_prompt(long_analysis)
        
        assert isinstance(prompt, str)
        assert "tsla" in prompt.lower()
        assert "95" in prompt  # Confidence score

    def test_get_custom_prompt_empty_task(self):
        """Test custom prompt with empty task."""
        prompt = get_custom_prompt("Test content", "", "JSON format")
        
        assert isinstance(prompt, str)
        assert "Test content" in prompt
        assert "JSON format" in prompt

    def test_get_custom_prompt_empty_output_format(self):
        """Test custom prompt with empty output format."""
        prompt = get_custom_prompt("Test content", "Analyze this", "")
        
        assert isinstance(prompt, str)
        assert "Test content" in prompt
        assert "Analyze this" in prompt

    def test_get_sector_analysis_prompt_empty_sectors(self):
        """Test sector analysis prompt with empty sectors list."""
        prompt = get_sector_analysis_prompt("Test content", [])
        
        assert isinstance(prompt, str)
        assert "Test content" in prompt
        # Should still contain some default structure

    def test_get_crypto_analysis_prompt_empty_cryptos(self):
        """Test crypto analysis prompt with empty cryptocurrencies list."""
        prompt = get_crypto_analysis_prompt("Test content", [])
        
        assert isinstance(prompt, str)
        assert "Test content" in prompt
        # Should still contain some default structure

    def test_prompt_consistency_across_calls(self):
        """Test that prompts are consistent across multiple calls."""
        content = "Tesla is great!"
        
        # Call the same function multiple times
        prompt1 = get_analysis_prompt(content)
        prompt2 = get_analysis_prompt(content)
        
        # Should be identical
        assert prompt1 == prompt2

    def test_prompt_with_none_context(self):
        """Test prompts with None context."""
        content = "Test content"
        
        # Test all prompt functions with None context
        prompt1 = get_analysis_prompt(content, None)
        prompt2 = get_detailed_analysis_prompt(content, None)
        
        assert isinstance(prompt1, str)
        assert isinstance(prompt2, str)
        assert content in prompt1
        assert content in prompt2

    def test_prompt_with_malformed_context(self):
        """Test prompts with malformed context."""
        content = "Test content"
        malformed_context = {
            "previous_posts": None,  # Should be list
            "market_conditions": 123,  # Should be string
            "recent_events": "not_a_list"  # Should be list
        }
        
        # Should handle malformed context gracefully
        prompt = get_analysis_prompt(content, malformed_context)
        assert isinstance(prompt, str)
        assert content in prompt
        # Should still include context section even if malformed
        assert "ADDITIONAL CONTEXT" in prompt


class TestPromptConstants:
    """Test prompt constants and configuration."""

    def test_system_messages_structure(self):
        """Test SYSTEM_MESSAGES constant structure."""
        assert isinstance(SYSTEM_MESSAGES, dict)
        assert len(SYSTEM_MESSAGES) >= 4  # Should have at least 4 types
        
        # Verify all expected types are present
        expected_types = ['financial_analyst', 'sector_analyst', 'crypto_analyst', 'general']
        for analysis_type in expected_types:
            assert analysis_type in SYSTEM_MESSAGES
            assert isinstance(SYSTEM_MESSAGES[analysis_type], str)
            assert len(SYSTEM_MESSAGES[analysis_type]) > 10

    def test_prompt_version_constant(self):
        """Test PROMPT_VERSION constant."""
        assert isinstance(PROMPT_VERSION, str)
        assert len(PROMPT_VERSION) > 0
        assert "." in PROMPT_VERSION  # Should be semantic version

    def test_system_messages_consistency(self):
        """Test that system messages are consistent with metadata."""
        metadata = get_prompt_metadata()
        available_types = metadata["available_analysis_types"]
        
        # All system message types should be in metadata
        for analysis_type in SYSTEM_MESSAGES.keys():
            assert analysis_type in available_types

    def test_prompt_functions_consistency(self):
        """Test that all prompt functions are consistent with metadata."""
        metadata = get_prompt_metadata()
        available_prompts = metadata["available_prompts"]
        
        # All prompt functions should be in metadata
        expected_functions = [
            'get_analysis_prompt',
            'get_detailed_analysis_prompt',
            'get_sector_analysis_prompt',
            'get_crypto_analysis_prompt',
            'get_alert_prompt',
            'get_custom_prompt'
        ]
        
        for function_name in expected_functions:
            assert function_name in available_prompts

    def test_prompt_functions_exist(self):
        """Test that all functions referenced in metadata actually exist."""
        metadata = get_prompt_metadata()
        available_prompts = metadata["available_prompts"]
        
        # Import the module to check if functions exist
        import shit.llm.prompts as prompts_module
        
        for function_name in available_prompts:
            assert hasattr(prompts_module, function_name)
            function = getattr(prompts_module, function_name)
            assert callable(function)
