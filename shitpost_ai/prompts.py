"""
LLM Prompts
Optimized prompts for analyzing Truth Social content for financial implications.
"""

from typing import Dict


def get_analysis_prompt(content: str) -> str:
    """Get the main analysis prompt for Truth Social content."""
    
    prompt = f"""
You are a financial analyst specializing in market sentiment analysis. Your task is to analyze the following Truth Social post from Donald Trump and identify potential financial market implications.

TRUTH SOCIAL POST:
"{content}"

ANALYSIS TASK:
Identify if this post could move any financial markets. Focus on:
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
    "thesis": "Brief explanation of why this post might move markets"
}}

ANALYSIS GUIDELINES:
- Focus on specific companies, stocks, or cryptocurrencies mentioned
- Consider Trump's influence on market sentiment
- Be conservative with confidence scores
- If no financial implications detected, return null for assets
- Use standard ticker symbols (e.g., TSLA, AAPL, BTC, GLD)
- Consider both direct mentions and implied references

EXAMPLES:
- "Tesla is a disaster" → {{"assets": ["TSLA"], "market_impact": {{"TSLA": "bearish"}}, "confidence": 0.9, "thesis": "Direct negative comment about Tesla stock"}}
- "The economy is great" → {{"assets": [], "market_impact": {{}}, "confidence": 0.3, "thesis": "General positive sentiment but no specific assets mentioned"}}

Now analyze the provided Truth Social post:
"""
    
    return prompt.strip()


def get_detailed_analysis_prompt(content: str, context: Dict = None) -> str:
    """Get a more detailed analysis prompt with additional context."""
    
    context_str = ""
    if context:
        context_str = f"""
ADDITIONAL CONTEXT:
- Previous posts: {context.get('previous_posts', [])}
- Market conditions: {context.get('market_conditions', 'Unknown')}
- Recent events: {context.get('recent_events', [])}
"""
    
    prompt = f"""
You are a senior financial analyst with expertise in political market sentiment. Analyze this Truth Social post with enhanced context.

TRUTH SOCIAL POST:
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


def get_sector_analysis_prompt(content: str) -> str:
    """Get a sector-focused analysis prompt."""
    
    prompt = f"""
You are a sector analyst specializing in identifying industry-wide implications from political statements.

TRUTH SOCIAL POST:
"{content}"

SECTOR ANALYSIS TASK:
Identify which market sectors could be impacted by this post:

1. TECHNOLOGY SECTOR:
   - Tech companies mentioned
   - Regulatory implications
   - Innovation/competition themes

2. FINANCIAL SECTOR:
   - Banks, financial institutions
   - Regulatory changes
   - Economic policy implications

3. ENERGY SECTOR:
   - Oil, gas, renewable energy
   - Energy policy implications
   - Infrastructure investments

4. HEALTHCARE SECTOR:
   - Pharmaceutical companies
   - Healthcare policy
   - Medical technology

5. AUTOMOTIVE SECTOR:
   - Car manufacturers
   - EV vs traditional vehicles
   - Trade policy implications

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


def get_crypto_analysis_prompt(content: str) -> str:
    """Get a cryptocurrency-focused analysis prompt."""
    
    prompt = f"""
You are a cryptocurrency analyst specializing in political sentiment impact on digital assets.

TRUTH SOCIAL POST:
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


def get_alert_prompt(analysis: Dict) -> str:
    """Get a prompt for generating SMS alert content."""
    
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
- Maximum 160 characters
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
