"""
Statistics
Domain-specific operations for generating statistics.
Extracted from ShitpostDatabase for modularity.
"""


from typing import Dict, Any
from sqlalchemy import case, func, select

from shit.db.database_operations import DatabaseOperations
from shitvault.shitpost_models import TruthSocialShitpost, Prediction

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("statistics")
logger = db_logger.logger

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
            # Query 1: All shitpost + prediction stats in one shot
            stats_stmt = select(
                func.count(TruthSocialShitpost.id).label("shitpost_count"),
                func.min(TruthSocialShitpost.timestamp).label("min_date"),
                func.max(TruthSocialShitpost.timestamp).label("max_date"),
            )
            stats_result = await self.db_ops.session.execute(stats_stmt)
            row = stats_result.one()
            shitpost_count = row.shitpost_count or 0
            min_date = row.min_date
            max_date = row.max_date

            # Query 2: All prediction aggregates including status counts + analysis date range
            pred_stmt = select(
                func.count(Prediction.id).label("total"),
                func.avg(Prediction.confidence).label("avg_confidence"),
                func.count(case((Prediction.analysis_status == 'completed', 1))).label("completed_count"),
                func.count(case((Prediction.analysis_status == 'bypassed', 1))).label("bypassed_count"),
                func.count(case((Prediction.analysis_status == 'error', 1))).label("error_count"),
                func.count(case((Prediction.analysis_status == 'pending', 1))).label("pending_count"),
                func.min(Prediction.post_timestamp).label("min_analysis_date"),
                func.max(Prediction.post_timestamp).label("max_analysis_date"),
            )
            pred_result = await self.db_ops.session.execute(pred_stmt)
            pred = pred_result.one()
            analysis_count = pred.total or 0
            avg_confidence = pred.avg_confidence or 0.0

            return {
                'total_shitposts': shitpost_count,
                'total_analyses': analysis_count,
                'average_confidence': round(avg_confidence, 3),
                'analysis_rate': round(analysis_count / max(shitpost_count, 1), 3),
                'earliest_post': min_date.isoformat() if min_date else None,
                'latest_post': max_date.isoformat() if max_date else None,
                'earliest_analyzed_post': pred.min_analysis_date.isoformat() if pred.min_analysis_date else None,
                'latest_analyzed_post': pred.max_analysis_date.isoformat() if pred.max_analysis_date else None,
                'completed_count': pred.completed_count,
                'bypassed_count': pred.bypassed_count,
                'error_count': pred.error_count,
                'pending_count': pred.pending_count,
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
