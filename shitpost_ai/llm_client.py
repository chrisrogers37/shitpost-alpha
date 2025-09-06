"""
LLM Client
Provides LLM API interaction layer for OpenAI and Anthropic services.
"""

import json
import logging
from typing import Dict, Optional, List
import openai
import anthropic
import asyncio

from shit.config.shitpost_settings import settings
from shitpost_ai.prompts import get_analysis_prompt
from shit.utils.error_handling import handle_exceptions

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM API client for OpenAI and Anthropic services."""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.api_key = settings.get_llm_api_key()
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD
        
        # Initialize client based on provider
        if self.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    async def initialize(self):
        """Initialize the LLM client."""
        logger.info(f"Initializing LLM client with {self.provider}/{self.model}")
        
        # Test connection
        try:
            await self._test_connection()
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    async def _test_connection(self):
        """Test LLM connection with a simple prompt."""
        test_prompt = "Respond with 'OK' if you can read this."
        
        try:
            response = await self._call_llm(test_prompt)
            if response and "OK" in response:
                logger.info("LLM connection test successful")
            else:
                raise Exception("LLM connection test failed")
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            raise
    
    async def analyze(self, content: str) -> Optional[Dict]:
        """Analyze content for financial implications."""
        try:
            if not content or len(content.strip()) < 10:
                logger.warning("Content too short for meaningful analysis")
                return None
            
            # Get analysis prompt
            prompt = get_analysis_prompt(content)
            
            # Call LLM
            response = await self._call_llm(prompt)
            
            if not response:
                logger.warning("No response from LLM")
                return None
            
            # Parse response
            analysis = await self._parse_analysis_response(response)
            
            if not analysis:
                logger.warning("Failed to parse LLM response")
                return None
            
            # Always save confidence metadata for future RAG enhancement
            confidence = analysis.get('confidence', 0.0)
            analysis['meets_threshold'] = confidence >= self.confidence_threshold
            analysis['analysis_quality'] = self._get_quality_label(confidence)
            
            # Add metadata
            analysis['original_content'] = content
            analysis['llm_provider'] = self.provider
            analysis['llm_model'] = self.model
            analysis['analysis_timestamp'] = self._get_timestamp()
            
            logger.info(f"Analysis completed with confidence {confidence} (quality: {analysis['analysis_quality']})")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing content: {e}")
            await handle_exceptions(e)
            return None
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM with the given prompt."""
        try:
            if self.provider == "openai":
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a financial analyst specializing in market sentiment analysis."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    ),
                    timeout=30.0  # 30 second timeout
                )
                return response.choices[0].message.content
            
            elif self.provider == "anthropic":
                response = await asyncio.wait_for(
                    self.client.messages.create(
                        model=self.model,
                        max_tokens=1000,
                        temperature=0.3,
                        system="You are a financial analyst specializing in market sentiment analysis.",
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    ),
                    timeout=30.0  # 30 second timeout
                )
                return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None
    
    async def _parse_analysis_response(self, response: str) -> Optional[Dict]:
        """Parse the LLM response into structured analysis."""
        try:
            # Try to extract JSON from response
            json_match = self._extract_json(response)
            if json_match:
                analysis = json.loads(json_match)
                
                # Validate required fields
                required_fields = ['assets', 'market_impact', 'confidence', 'thesis']
                if all(field in analysis for field in required_fields):
                    return analysis
            
            # Fallback: try to parse manually
            return await self._parse_manual_response(response)
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text response."""
        try:
            # Look for JSON-like content
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start != -1 and end != 0:
                json_str = text[start:end]
                # Validate JSON
                json.loads(json_str)
                return json_str
        except:
            pass
        
        return None
    
    async def _parse_manual_response(self, response: str) -> Optional[Dict]:
        """Manually parse response if JSON extraction fails."""
        try:
            # Simple keyword-based parsing as fallback
            analysis = {
                'assets': [],
                'market_impact': {},
                'confidence': 0.5,  # Default confidence
                'thesis': response[:200] + "..." if len(response) > 200 else response
            }
            
            # Extract assets mentioned
            asset_keywords = ['stock', 'company', 'corporation', 'inc', 'ltd', 'corp']
            words = response.lower().split()
            for word in words:
                if any(keyword in word for keyword in asset_keywords):
                    analysis['assets'].append(word.upper())
            
            # Remove duplicates
            analysis['assets'] = list(set(analysis['assets']))
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in manual parsing: {e}")
            return None
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def get_analysis_summary(self, analysis: Dict) -> str:
        """Generate a human-readable summary of the analysis."""
        try:
            assets = analysis.get('assets', [])
            confidence = analysis.get('confidence', 0.0)
            thesis = analysis.get('thesis', '')
            
            summary = f"Analysis (Confidence: {confidence:.1%})\n"
            summary += f"Assets: {', '.join(assets) if assets else 'None detected'}\n"
            summary += f"Thesis: {thesis[:100]}{'...' if len(thesis) > 100 else ''}"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Analysis summary unavailable"

    def _get_quality_label(self, confidence: float) -> str:
        """Get quality label based on confidence score."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        else:
            return "low"


# For testing purposes
async def test_llm_client():
    """Test function to verify LLM client."""
    client = LLMClient()
    await client.initialize()
    
    test_content = "The electric vehicle scam is destroying our auto industry. Ford and GM are going bankrupt because of these fake cars."
    
    print("Testing LLM client...")
    analysis = await client.analyze(test_content)
    
    if analysis:
        print(f"Analysis: {analysis}")
        summary = await client.get_analysis_summary(analysis)
        print(f"Summary: {summary}")
    else:
        print("No analysis generated")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_client())
