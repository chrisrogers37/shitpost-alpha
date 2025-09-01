#!/usr/bin/env python3
"""
Shitpost Analyzer
Business logic orchestrator for analyzing shitposts with enhanced context.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from config.shitpost_settings import Settings
from shitpost_ai.llm_client import LLMClient
from database.shitpost_db import ShitpostDatabase
from utils.error_handling import handle_exceptions

logger = logging.getLogger(__name__)


class ShitpostAnalyzer:
    """Analyzes shitposts for financial implications with enhanced context."""
    
    def __init__(self):
        self.settings = Settings()
        self.db_manager = ShitpostDatabase()
        self.llm_client = LLMClient()
        self.launch_date = self.settings.SYSTEM_LAUNCH_DATE
        
    async def initialize(self):
        """Initialize the shitpost analyzer."""
        logger.info("Initializing Shitpost Analyzer...")
        
        await self.db_manager.initialize()
        await self.llm_client.initialize()
        
        logger.info(f"Shitpost Analyzer initialized with launch date: {self.launch_date}")
    
    async def analyze_unprocessed_shitposts(self, batch_size: int = 5) -> int:
        """
        Analyze unprocessed shitposts from the database.
        
        Args:
            batch_size: Number of shitposts to process in one batch
            
        Returns:
            Number of shitposts successfully analyzed
        """
        try:
            # Get unprocessed shitposts
            shitposts = await self.db_manager.get_unprocessed_shitposts(
                launch_date=self.launch_date,
                limit=batch_size
            )
            
            if not shitposts:
                logger.info("No unprocessed shitposts found for analysis")
                return 0
            
            logger.info(f"Found {len(shitposts)} unprocessed shitposts to analyze")
            
            analyzed_count = 0
            
            for shitpost in shitposts:
                try:
                    # Check if prediction already exists (double-check)
                    if await self.db_manager.check_prediction_exists(shitpost['id']):
                        logger.info(f"Prediction already exists for shitpost {shitpost['id']}, skipping")
                        continue
                    
                    # Analyze the shitpost
                    analysis = await self._analyze_shitpost(shitpost)
                    
                    if analysis:
                        # Store enhanced analysis with shitpost data
                        prediction_id = await self.db_manager.store_analysis(
                            post_id=str(shitpost['id']),
                            analysis_data=analysis,
                            post_data=shitpost
                        )
                        
                        if prediction_id:
                            analyzed_count += 1
                            logger.info(f"Successfully analyzed shitpost {shitpost['id']} -> prediction {prediction_id}")
                        else:
                            logger.error(f"Failed to store analysis for shitpost {shitpost['id']}")
                    else:
                        logger.warning(f"No analysis generated for shitpost {shitpost['id']}")
                        
                except Exception as e:
                    logger.error(f"Error analyzing shitpost {shitpost['id']}: {e}")
                    await handle_exceptions(e)
                    continue
            
            logger.info(f"Batch analysis complete: {analyzed_count}/{len(shitposts)} shitposts analyzed")
            return analyzed_count
            
        except Exception as e:
            logger.error(f"Error in batch analysis: {e}")
            await handle_exceptions(e)
            return 0
    
    async def _analyze_shitpost(self, shitpost: Dict) -> Optional[Dict]:
        """
        Analyze a single shitpost with enhanced context.
        
        Args:
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced analysis results
        """
        try:
            # Prepare enhanced content for analysis
            enhanced_content = self._prepare_enhanced_content(shitpost)
            
            # Analyze with LLM
            analysis = await self.llm_client.analyze(enhanced_content)
            
            if not analysis:
                return None
            
            # Enhance analysis with Truth Social data
            enhanced_analysis = self._enhance_analysis_with_shitpost_data(analysis, shitpost)
            
            return enhanced_analysis
            
        except Exception as e:
            logger.error(f"Error in shitpost analysis: {e}")
            return None
    
    def _prepare_enhanced_content(self, shitpost: Dict) -> str:
        """
        Prepare enhanced content for LLM analysis.
        
        Args:
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced content string
        """
        content_parts = []
        
        # Main content
        content_parts.append(f"SHITPOST CONTENT: {shitpost.get('text', '')}")
        
        # Engagement context
        replies = shitpost.get('replies_count', 0)
        reblogs = shitpost.get('reblogs_count', 0)
        favourites = shitpost.get('favourites_count', 0)
        upvotes = shitpost.get('upvotes_count', 0)
        
        if any([replies, reblogs, favourites, upvotes]):
            content_parts.append(f"ENGAGEMENT: {replies} replies, {reblogs} reblogs, {favourites} favourites, {upvotes} upvotes")
        
        # Account context
        followers = shitpost.get('account_followers_count', 0)
        verified = shitpost.get('account_verified', False)
        
        if followers > 0:
            content_parts.append(f"ACCOUNT: {followers:,} followers, verified: {verified}")
        
        # Media context
        if shitpost.get('has_media', False):
            content_parts.append("MEDIA: Shitpost contains media attachments")
        
        # Mentions and hashtags
        mentions = shitpost.get('mentions', [])
        tags = shitpost.get('tags', [])
        
        if mentions:
            content_parts.append(f"MENTIONS: {', '.join(mentions)}")
        
        if tags:
            content_parts.append(f"HASHTAGS: {', '.join(tags)}")
        
        return "\n".join(content_parts)
    
    def _enhance_analysis_with_shitpost_data(self, analysis: Dict, shitpost: Dict) -> Dict:
        """
        Enhance LLM analysis with Truth Social shitpost data.
        
        Args:
            analysis: Original LLM analysis
            shitpost: Shitpost data from database
            
        Returns:
            Enhanced analysis
        """
        enhanced = analysis.copy()
        
        # Calculate engagement-based scores
        replies = shitpost.get('replies_count', 0)
        reblogs = shitpost.get('reblogs_count', 0)
        favourites = shitpost.get('favourites_count', 0)
        upvotes = shitpost.get('upvotes_count', 0)
        followers = shitpost.get('account_followers_count', 0)
        
        # Engagement score
        if followers > 0:
            engagement_rate = (replies + reblogs + favourites) / followers
            enhanced['engagement_score'] = min(engagement_rate * 100, 1.0)  # Normalize to 0-1
        
        # Viral score
        if favourites > 0:
            viral_ratio = reblogs / favourites
            enhanced['viral_score'] = min(viral_ratio, 1.0)
        
        # Urgency indicators
        urgency_indicators = []
        if '!' in shitpost.get('text', ''):
            urgency_indicators.append('exclamation_marks')
        if any(word in shitpost.get('text', '').upper() for word in ['URGENT', 'IMMEDIATE', 'NOW', 'ASAP']):
            urgency_indicators.append('urgency_keywords')
        if replies > 1000:
            urgency_indicators.append('high_engagement')
        
        enhanced['urgency_indicators'] = urgency_indicators
        enhanced['urgency_score'] = len(urgency_indicators) / 3.0  # Normalize to 0-1
        
        # Add shitpost metadata
        enhanced['shitpost_metadata'] = {
            'has_media': shitpost.get('has_media', False),
            'mentions_count': len(shitpost.get('mentions', [])),
            'hashtags_count': len(shitpost.get('tags', [])),
            'content_length': len(shitpost.get('text', '')),
            'engagement_metrics': {
                'replies': replies,
                'reblogs': reblogs,
                'favourites': favourites,
                'upvotes': upvotes
            }
        }
        
        return enhanced
    
    async def run_continuous_analysis(self, interval_seconds: int = 300):
        """
        Run continuous analysis of unprocessed shitposts.
        
        Args:
            interval_seconds: Seconds between analysis runs
        """
        logger.info(f"Starting continuous shitpost analysis (interval: {interval_seconds}s)")
        
        while True:
            try:
                analyzed_count = await self.analyze_unprocessed_shitposts(batch_size=5)
                
                if analyzed_count > 0:
                    logger.info(f"Analyzed {analyzed_count} shitposts in this cycle")
                else:
                    logger.debug("No shitposts analyzed in this cycle")
                
                # Wait before next cycle
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Continuous shitpost analysis stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous shitpost analysis: {e}")
                await handle_exceptions(e)
                await asyncio.sleep(interval_seconds)
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.db_manager.cleanup()
        logger.info("Shitpost Analyzer cleaned up")


if __name__ == "__main__":
    # Test the shitpost analyzer
    async def test():
        analyzer = ShitpostAnalyzer()
        try:
            await analyzer.initialize()
            analyzed = await analyzer.analyze_unprocessed_shitposts(batch_size=3)
            print(f"Analyzed {analyzed} shitposts")
        finally:
            await analyzer.cleanup()
    
    asyncio.run(test())
