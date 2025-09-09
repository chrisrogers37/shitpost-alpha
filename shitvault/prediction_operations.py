"""
Prediction Operations
Domain-specific operations for prediction management.
Extracted from ShitpostDatabase for modularity.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from sqlalchemy import select

from shit.db.database_operations import DatabaseOperations
from shit.db.database_utils import DatabaseUtils
from shitvault.shitpost_models import Prediction

logger = logging.getLogger(__name__)

class PredictionOperations:
    """Operations for managing predictions."""
    
    def __init__(self, db_ops: DatabaseOperations):
        self.db_ops = db_ops
    
    async def store_analysis(self, shitpost_id: str, analysis_data: Dict[str, Any], shitpost_data: Dict[str, Any] = None) -> Optional[str]:
        """Store LLM analysis results in the database with enhanced shitpost data."""
        try:
            # Calculate engagement scores
            engagement_score = None
            viral_score = None
            if shitpost_data:
                replies = shitpost_data.get('replies_count', 0)
                reblogs = shitpost_data.get('reblogs_count', 0)
                favourites = shitpost_data.get('favourites_count', 0)
                upvotes = shitpost_data.get('upvotes_count', 0)
                followers = shitpost_data.get('account_followers_count', 0)
                
                # Engagement score based on interaction rate
                if followers > 0:
                    engagement_score = (replies + reblogs + favourites) / followers
                
                # Viral score based on reblog/favourite ratio
                if favourites > 0:
                    viral_score = reblogs / favourites
            
            prediction = Prediction(
                shitpost_id=shitpost_id,
                assets=analysis_data.get('assets', []),
                market_impact=analysis_data.get('market_impact', {}),
                confidence=analysis_data.get('confidence', 0.0),
                thesis=analysis_data.get('thesis', ''),
                
                # Set analysis status for successful analyses
                analysis_status='completed',
                analysis_comment=None,
                
                # Enhanced analysis scores
                engagement_score=engagement_score,
                viral_score=viral_score,
                sentiment_score=analysis_data.get('sentiment_score'),
                urgency_score=analysis_data.get('urgency_score'),
                
                # Content analysis
                has_media=shitpost_data.get('has_media', False) if shitpost_data else False,
                mentions_count=len(shitpost_data.get('mentions', [])) if shitpost_data else 0,
                hashtags_count=len(shitpost_data.get('tags', [])) if shitpost_data else 0,
                content_length=len(shitpost_data.get('text', '')) if shitpost_data else 0,
                
                # Engagement metrics at analysis time
                replies_at_analysis=shitpost_data.get('replies_count', 0) if shitpost_data else 0,
                reblogs_at_analysis=shitpost_data.get('reblogs_count', 0) if shitpost_data else 0,
                favourites_at_analysis=shitpost_data.get('favourites_count', 0) if shitpost_data else 0,
                upvotes_at_analysis=shitpost_data.get('upvotes_count', 0) if shitpost_data else 0,
                
                # LLM metadata
                llm_provider=analysis_data.get('llm_provider'),
                llm_model=analysis_data.get('llm_model'),
                analysis_timestamp=DatabaseUtils.parse_timestamp(analysis_data.get('analysis_timestamp'))
            )
            
            self.db_ops.session.add(prediction)
            await self.db_ops.session.commit()
            await self.db_ops.session.refresh(prediction)
            
            logger.debug(f"Stored enhanced analysis with ID: {prediction.id}")
            return str(prediction.id)
            
        except Exception as e:
            logger.error(f"Error storing analysis: {e}")
            return None
    
    async def handle_no_text_prediction(self, shitpost_id: str, shitpost_data: Dict[str, Any]) -> Optional[str]:
        """Create a prediction record for posts that can't be analyzed."""
        try:
            # Determine the bypass reason based on content
            reason = self._get_bypass_reason(shitpost_data)
            
            prediction = Prediction(
                shitpost_id=shitpost_id,
                analysis_status='bypassed',
                analysis_comment=reason,
                # Set minimal required fields for bypassed posts
                confidence=None,
                thesis=None,
                assets=[],
                market_impact={},
                engagement_score=None,
                viral_score=None,
                sentiment_score=None,
                urgency_score=None,
                has_media=shitpost_data.get('has_media', False),
                mentions_count=len(shitpost_data.get('mentions', [])),
                hashtags_count=len(shitpost_data.get('tags', [])),
                content_length=len(shitpost_data.get('text', '')),
                replies_at_analysis=shitpost_data.get('replies_count', 0),
                reblogs_at_analysis=shitpost_data.get('reblogs_count', 0),
                favourites_at_analysis=shitpost_data.get('favourites_count', 0),
                upvotes_at_analysis=shitpost_data.get('upvotes_count', 0),
                llm_provider=None,
                llm_model=None,
                analysis_timestamp=datetime.now()
            )
            
            self.db_ops.session.add(prediction)
            await self.db_ops.session.commit()
            await self.db_ops.session.refresh(prediction)
            
            logger.info(f"Created bypassed prediction for {shitpost_id}: {reason}")
            return str(prediction.id)
            
        except Exception as e:
            logger.error(f"Error creating bypassed prediction: {e}")
            return None
    
    def _get_bypass_reason(self, shitpost_data: Dict[str, Any]) -> str:
        """Determine why a post should be bypassed for analysis."""
        text_content = shitpost_data.get('text', '').strip()
        
        if not text_content:
            return "No text content"
        elif len(text_content) < 10:
            return "Text too short"
        elif text_content.lower() in ['test', 'testing', 'hello', 'hi']:
            return "Test content"
        elif len(text_content.split()) < 3:
            return "Insufficient words"
        else:
            return "Content not analyzable"
    
    async def check_prediction_exists(self, shitpost_id: str) -> bool:
        """Check if a prediction already exists for a shitpost."""
        try:
            stmt = select(Prediction.id).where(Prediction.shitpost_id == shitpost_id)
            result = await self.db_ops.session.execute(stmt)
            return result.scalar_one_or_none() is not None
            
        except Exception as e:
            logger.error(f"Error checking prediction existence: {e}")
            return False
