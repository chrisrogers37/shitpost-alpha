"""
Statistics
Domain-specific operations for generating statistics.
Extracted from ShitpostDatabase for modularity.
"""

import logging
from typing import Dict, Any
from sqlalchemy import func, select

from shit.db.database_operations import DatabaseOperations
from shitvault.shitpost_models import TruthSocialShitpost, Prediction

logger = logging.getLogger(__name__)

class Statistics:
    """Operations for generating statistics."""
    
    def __init__(self, db_ops: DatabaseOperations):
        self.db_ops = db_ops
    
    async def get_analysis_stats(self) -> Dict[str, Any]:
        """Get basic statistics about stored shitpost data."""
        try:
            # Count shitposts
            shitpost_count_result = await self.db_ops.session.execute(
                func.count(TruthSocialShitpost.id)
            )
            shitpost_count = shitpost_count_result.scalar()
            
            # Count analyses
            analysis_count_result = await self.db_ops.session.execute(
                func.count(Prediction.id)
            )
            analysis_count = analysis_count_result.scalar()
            
            # Average confidence
            avg_confidence_result = await self.db_ops.session.execute(
                func.avg(Prediction.confidence)
            )
            avg_confidence = avg_confidence_result.scalar() or 0.0
            
            return {
                'total_shitposts': shitpost_count,
                'total_analyses': analysis_count,
                'average_confidence': round(avg_confidence, 3),
                'analysis_rate': round(analysis_count / max(shitpost_count, 1), 3)
            }
            
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {
                'total_shitposts': 0,
                'total_analyses': 0,
                'average_confidence': 0.0,
                'analysis_rate': 0.0
            }
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            # Count shitposts
            shitpost_count_result = await self.db_ops.session.execute(
                select(func.count(TruthSocialShitpost.id))
            )
            shitpost_count = shitpost_count_result.scalar()
            
            # Count analyses
            analysis_count_result = await self.db_ops.session.execute(
                select(func.count(Prediction.id))
            )
            analysis_count = analysis_count_result.scalar()
            
            # Count by analysis status
            status_counts = {}
            for status in ['completed', 'bypassed', 'error', 'pending']:
                status_result = await self.db_ops.session.execute(
                    select(func.count(Prediction.id)).where(Prediction.analysis_status == status)
                )
                status_counts[f'{status}_count'] = status_result.scalar()
            
            # Average confidence
            avg_confidence_result = await self.db_ops.session.execute(
                select(func.avg(Prediction.confidence))
            )
            avg_confidence = avg_confidence_result.scalar() or 0.0
            
            # Date range (using actual Truth Social post timestamps)
            date_range_result = await self.db_ops.session.execute(
                select(func.min(TruthSocialShitpost.timestamp))
            )
            min_date = date_range_result.scalar()
            
            date_range_result = await self.db_ops.session.execute(
                select(func.max(TruthSocialShitpost.timestamp))
            )
            max_date = date_range_result.scalar()
            
            # Analysis date range (using actual Truth Social post timestamps for analyzed posts)
            analysis_date_range_result = await self.db_ops.session.execute(
                select(func.min(TruthSocialShitpost.timestamp))
                .join(Prediction, TruthSocialShitpost.shitpost_id == Prediction.shitpost_id)
            )
            min_analysis_date = analysis_date_range_result.scalar()
            
            analysis_date_range_result = await self.db_ops.session.execute(
                select(func.max(TruthSocialShitpost.timestamp))
                .join(Prediction, TruthSocialShitpost.shitpost_id == Prediction.shitpost_id)
            )
            max_analysis_date = analysis_date_range_result.scalar()
            
            return {
                'total_shitposts': shitpost_count,
                'total_analyses': analysis_count,
                'average_confidence': round(avg_confidence, 3),
                'analysis_rate': round(analysis_count / max(shitpost_count, 1), 3),
                'earliest_post': min_date.isoformat() if min_date else None,
                'latest_post': max_date.isoformat() if max_date else None,
                'earliest_analyzed_post': min_analysis_date.isoformat() if min_analysis_date else None,
                'latest_analyzed_post': max_analysis_date.isoformat() if max_analysis_date else None,
                **status_counts
            }
            
        except Exception as e:
            logger.error(f"Error fetching database stats: {e}")
            return {
                'total_shitposts': 0,
                'total_analyses': 0,
                'average_confidence': 0.0,
                'analysis_rate': 0.0,
                'earliest_post': None,
                'latest_post': None,
                'earliest_analyzed_post': None,
                'latest_analyzed_post': None,
                'completed_count': 0,
                'bypassed_count': 0,
                'error_count': 0,
                'pending_count': 0
            }
