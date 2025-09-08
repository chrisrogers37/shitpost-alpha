"""
LLM Prompts
Modular prompt templates for various analysis types.
"""

from typing import Dict, Optional, Any


# Base prompt templates
SYSTEM_MESSAGES = {
    'financial_analyst': "You are a financial analyst specializing in market sentiment analysis.",
    'sector_analyst': "You are a sector analyst specializing in identifying industry-wide implications from political statements.",
    'crypto_analyst': "You are a cryptocurrency analyst specializing in political sentiment impact on digital assets.",
    'general': "You are a helpful AI assistant."
}

# Prompt versions for consistency
PROMPT_VERSION = "1.0"


def get_analysis_prompt(content: str, context: Optional[Dict] = None) -> str:
    """Get the main analysis prompt for financial content.
    
    Args:
        content: Content to analyze
        context: Optional context dictionary
        
    Returns:
        Formatted prompt string
    """
    context_str = ""
    if context:
        context_str = f"""
ADDITIONAL CONTEXT:
- Previous posts: {context.get('previous_posts', [])}
- Market conditions: {context.get('market_conditions', 'Unknown')}
- Recent events: {context.get('recent_events', [])}
"""
    
    prompt = f"""
You are a financial analyst specializing in market sentiment analysis. Your task is to analyze the following content and identify potential financial market implications.

CONTENT TO ANALYZE:
"{content}"
{context_str}

ANALYSIS TASK:
Identify if this content could move any financial markets. Focus on:
1. Companies, stocks, or cryptocurrencies mentioned
2. Market sectors or commodities referenced
3. Sentiment (bullish/bearish/neutral) for each asset
4. Confidence level in your analysis
5. Brief investment thesis explaining the potential market impact

OUTPUT FORMAT:
Respond with a JSON object containing:
{{
    "assets": ["TICKER1", "TICKER2"],  // List of stock/crypto tickers mentioned
    "market_impact": {{
        "TICKER1": "bullish/bearish/neutral",
        "TICKER2": "bullish/bearish/neutral"
    }},
    "confidence": 0.85,  // Confidence score 0.0-1.0
    "thesis": "Brief explanation of why this content might move markets"
}}

ANALYSIS GUIDELINES:
- Focus on specific companies, stocks, or cryptocurrencies mentioned
- Consider political influence on market sentiment
- Be conservative with confidence scores
- If no financial implications detected, return empty arrays
- Use standard ticker symbols (e.g., TSLA, AAPL, BTC, GLD)
- Consider both direct mentions and implied references

EXAMPLES:
- "Tesla is a disaster" → {{"assets": ["TSLA"], "market_impact": {{"TSLA": "bearish"}}, "confidence": 0.9, "thesis": "Direct negative comment about Tesla stock"}}
- "The economy is great" → {{"assets": [], "market_impact": {{}}, "confidence": 0.3, "thesis": "General positive sentiment but no specific assets mentioned"}}

Now analyze the provided content:
"""
    
    return prompt.strip()


def get_detailed_analysis_prompt(content: str, context: Optional[Dict] = None) -> str:
    """Get a more detailed analysis prompt with additional context.
    
    Args:
        content: Content to analyze
        context: Optional context dictionary
        
    Returns:
        Formatted prompt string
    """
    context_str = ""
    if context:
        context_str = f"""
ADDITIONAL CONTEXT:
- Previous posts: {context.get('previous_posts', [])}
- Market conditions: {context.get('market_conditions', 'Unknown')}
- Recent events: {context.get('recent_events', [])}
"""
    
    prompt = f"""
You are a senior financial analyst with expertise in political market sentiment. Analyze this content with enhanced context.

CONTENT TO ANALYZE:
"{content}"
{context_str}

DETAILED ANALYSIS TASK:
Provide a comprehensive analysis including:

1. ASSET IDENTIFICATION:
   - Direct mentions (companies, stocks, crypto)
   - Indirect references (sectors, commodities)
   - Potential beneficiaries/victims

2. SENTIMENT ANALYSIS:
   - Overall sentiment (positive/negative/neutral)
   - Sentiment strength (1-10 scale)
   - Emotional tone (angry, supportive, critical, etc.)

3. MARKET IMPACT PREDICTION:
   - Short-term impact (next 24 hours)
   - Medium-term impact (next week)
   - Potential price movement magnitude

4. RISK ASSESSMENT:
   - Confidence in analysis
   - Potential confounding factors
   - Market conditions that could amplify/dampen impact

OUTPUT FORMAT:
{{
    "assets": ["TICKER1", "TICKER2"],
    "market_impact": {{
        "TICKER1": {{
            "sentiment": "bullish/bearish/neutral",
            "confidence": 0.85,
            "short_term": "positive/negative/neutral",
            "magnitude": "low/medium/high"
        }}
    }},
    "overall_sentiment": "positive/negative/neutral",
    "sentiment_strength": 7,
    "emotional_tone": "critical",
    "thesis": "Detailed explanation of market implications",
    "risks": ["List of potential confounding factors"],
    "confidence": 0.85
}}

Now provide your detailed analysis:
"""
    
    return prompt.strip()


def get_sector_analysis_prompt(content: str, sectors: Optional[list] = None) -> str:
    """Get a sector-focused analysis prompt.
    
    Args:
        content: Content to analyze
        sectors: Optional list of sectors to focus on
        
    Returns:
        Formatted prompt string
    """
    sector_list = sectors or ["technology", "financial", "energy", "healthcare", "automotive"]
    
    prompt = f"""
You are a sector analyst specializing in identifying industry-wide implications from political statements.

CONTENT TO ANALYZE:
"{content}"

SECTOR ANALYSIS TASK:
Identify which market sectors could be impacted by this content:

"""
    
    for sector in sector_list:
        sector_name = sector.title()
        prompt += f"""
{sector_name.upper()} SECTOR:
   - {sector_name} companies mentioned
   - Regulatory implications
   - Policy implications
   - Market impact potential
"""
    
    prompt += f"""
OUTPUT FORMAT:
{{
    "sectors": {{
        "technology": {{
            "impact": "positive/negative/neutral",
            "companies": ["AAPL", "GOOGL"],
            "confidence": 0.8,
            "reasoning": "Explanation"
        }},
        "financial": {{
            "impact": "positive/negative/neutral",
            "companies": ["JPM", "BAC"],
            "confidence": 0.7,
            "reasoning": "Explanation"
        }}
    }},
    "overall_market_sentiment": "bullish/bearish/neutral",
    "confidence": 0.75
}}

Provide your sector analysis:
"""
    
    return prompt.strip()


def get_crypto_analysis_prompt(content: str, cryptocurrencies: Optional[list] = None) -> str:
    """Get a cryptocurrency-focused analysis prompt.
    
    Args:
        content: Content to analyze
        cryptocurrencies: Optional list of cryptocurrencies to focus on
        
    Returns:
        Formatted prompt string
    """
    crypto_list = cryptocurrencies or ["BTC", "ETH", "ADA", "SOL"]
    
    prompt = f"""
You are a cryptocurrency analyst specializing in political sentiment impact on digital assets.

CONTENT TO ANALYZE:
"{content}"

CRYPTO ANALYSIS TASK:
Analyze the potential impact on cryptocurrency markets:

1. DIRECT CRYPTO MENTIONS:
   - Bitcoin, Ethereum, other cryptocurrencies
   - Blockchain companies
   - Crypto-related stocks

2. REGULATORY IMPLICATIONS:
   - Potential policy changes
   - SEC or regulatory actions
   - Tax implications

3. MACROECONOMIC FACTORS:
   - Inflation/deflation themes
   - Dollar strength/weakness
   - Safe haven vs risk asset positioning

4. SENTIMENT ANALYSIS:
   - Crypto-friendly vs crypto-hostile
   - Adoption implications
   - Institutional interest

OUTPUT FORMAT:
{{
    "cryptocurrencies": {{
        "BTC": {{
            "sentiment": "bullish/bearish/neutral",
            "confidence": 0.8,
            "reasoning": "Explanation",
            "price_impact": "positive/negative/neutral"
        }},
        "ETH": {{
            "sentiment": "bullish/bearish/neutral",
            "confidence": 0.7,
            "reasoning": "Explanation",
            "price_impact": "positive/negative/neutral"
        }}
    }},
    "regulatory_risk": "low/medium/high",
    "overall_crypto_sentiment": "positive/negative/neutral",
    "confidence": 0.75,
    "thesis": "Overall crypto market impact explanation"
}}

Provide your cryptocurrency analysis:
"""
    
    return prompt.strip()


def get_alert_prompt(analysis: Dict, max_length: int = 160) -> str:
    """Get a prompt for generating SMS alert content.
    
    Args:
        analysis: Analysis result dictionary
        max_length: Maximum character length for alert
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""
You are creating a concise SMS alert for traders based on this financial analysis:

ANALYSIS:
{analysis}

ALERT TASK:
Create a short, actionable SMS alert that includes:
1. Key assets mentioned
2. Sentiment direction
3. Confidence level
4. Brief actionable insight

REQUIREMENTS:
- Maximum {max_length} characters
- Clear and actionable
- Include emojis for visual appeal
- Focus on most impactful assets
- Use trading terminology

EXAMPLE FORMAT:
🚨 SHITPOST-ALPHA SIGNAL 🚨
Trump: "EVs are killing jobs!"
→ TSLA 📉 | F 📉 | GM 📉
→ Bearish Auto, 85% confidence
→ Posted 2min ago

Create the SMS alert:
"""
    
    return prompt.strip()


def get_custom_prompt(content: str, task: str, output_format: str, examples: Optional[list] = None) -> str:
    """Get a custom prompt for specific analysis tasks.
    
    Args:
        content: Content to analyze
        task: Description of the analysis task
        output_format: Expected output format
        examples: Optional list of examples
        
    Returns:
        Formatted prompt string
    """
    examples_str = ""
    if examples:
        examples_str = "\nEXAMPLES:\n"
        for example in examples:
            examples_str += f"- {example}\n"
    
    prompt = f"""
You are a specialized AI analyst. Your task is to analyze the following content:

CONTENT TO ANALYZE:
"{content}"

TASK:
{task}

OUTPUT FORMAT:
{output_format}
{examples_str}

Now provide your analysis:
"""
    
    return prompt.strip()


def get_system_message(analysis_type: str = 'financial_analyst') -> str:
    """Get system message for specific analysis type.
    
    Args:
        analysis_type: Type of analysis ('financial_analyst', 'sector_analyst', 'crypto_analyst', 'general')
        
    Returns:
        System message string
    """
    return SYSTEM_MESSAGES.get(analysis_type, SYSTEM_MESSAGES['general'])


def validate_prompt_version(version: str) -> bool:
    """Validate prompt version for consistency.
    
    Args:
        version: Version string to validate
        
    Returns:
        True if version is valid
    """
    return version == PROMPT_VERSION


def get_prompt_metadata() -> Dict[str, Any]:
    """Get metadata about prompt system.
    
    Returns:
        Dictionary with prompt metadata
    """
    return {
        'version': PROMPT_VERSION,
        'available_analysis_types': list(SYSTEM_MESSAGES.keys()),
        'available_prompts': [
            'get_analysis_prompt',
            'get_detailed_analysis_prompt',
            'get_sector_analysis_prompt',
            'get_crypto_analysis_prompt',
            'get_alert_prompt',
            'get_custom_prompt'
        ]
    }
