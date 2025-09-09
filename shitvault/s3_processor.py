"""
S3 Processor
Domain-specific operations for S3 to database processing.
Extracted from ShitpostDatabase for modularity.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

from shit.db.database_operations import DatabaseOperations
from shit.db.database_utils import DatabaseUtils
from shit.s3 import S3DataLake
from shitvault.shitpost_operations import ShitpostOperations

logger = logging.getLogger(__name__)

class S3Processor:
    """Operations for processing S3 data to database."""
    
    def __init__(self, db_ops: DatabaseOperations, s3_data_lake: S3DataLake):
        self.db_ops = db_ops
        self.s3_data_lake = s3_data_lake
        self.shitpost_ops = ShitpostOperations(db_ops)
    
    async def process_s3_to_database(self, start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None,
                                   limit: Optional[int] = None,
                                   dry_run: bool = False) -> Dict[str, int]:
        """Process S3 data and load into database (consolidated method).
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of records to process (optional)
            dry_run: If True, don't actually store to database
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            if dry_run:
                logger.info(f"Starting S3 to Database processing (DRY RUN - no database writes)...")
            else:
                logger.info(f"Starting S3 to Database processing...")
            logger.info(f"Date range: {start_date} to {end_date}")
            logger.info(f"Limit: {limit}")
            
            stats = {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
            
            # Stream data from S3
            async for s3_data in self.s3_data_lake.stream_raw_data(start_date, end_date, limit):
                stats['total_processed'] += 1
                
                try:
                    if dry_run:
                        # In dry run, just count what would be processed
                        stats['successful'] += 1
                    else:
                        # Transform S3 data to database format
                        transformed_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
                        
                        # Store in database (deduplication handled by store_shitpost)
                        result = await self.shitpost_ops.store_shitpost(transformed_data)
                        
                        if result:
                            stats['successful'] += 1
                        else:
                            stats['skipped'] += 1  # Already exists
                            
                except Exception as e:
                    logger.error(f"Error processing S3 data: {e}")
                    stats['failed'] += 1
                
                # Log progress (less frequently)
                if stats['total_processed'] % 500 == 0:
                    logger.info(f"Processed {stats['total_processed']} records...")
            
            if dry_run:
                logger.info(f"S3 to Database processing completed (DRY RUN):")
                logger.info(f"  Total processed: {stats['total_processed']}")
                logger.info(f"  Would be successful: {stats['successful']}")
                logger.info(f"  Would fail: {stats['failed']}")
                logger.info(f"  Would be skipped: {stats['skipped']}")
            else:
                logger.info(f"S3 to Database processing completed:")
                logger.info(f"  Total processed: {stats['total_processed']}")
                logger.info(f"  Successful: {stats['successful']}")
                logger.info(f"  Failed: {stats['failed']}")
                logger.info(f"  Skipped: {stats['skipped']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in S3 to Database processing: {e}")
            raise
    
    async def get_s3_processing_stats(self) -> Dict[str, any]:
        """Get statistics about S3 and database data.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get S3 stats
            s3_stats = await self.s3_data_lake.get_data_stats()
            
            # Get database stats (we'll need to implement this in Statistics class)
            # For now, return basic structure
            return {
                's3_stats': s3_stats.__dict__,
                'db_stats': {},  # Will be populated by Statistics class
                'processing_summary': {
                    's3_files': s3_stats.total_files,
                    'db_records': 0,  # Will be populated by Statistics class
                    'processing_ratio': 0.0  # Will be calculated by Statistics class
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting S3 processing stats: {e}")
            raise
