"""
S3 Processor
Domain-specific operations for S3 to database processing.
Extracted from ShitpostDatabase for modularity.
"""


from typing import Dict, Optional, Any, List
from datetime import datetime

from shit.db.database_operations import DatabaseOperations
from shit.db.database_utils import DatabaseUtils
from shit.s3 import S3DataLake
from shitvault.shitpost_operations import ShitpostOperations
from shitvault.signal_operations import SignalOperations
from shitvault.shitpost_models import TruthSocialShitpost
from shit.db.signal_utils import SignalTransformer

# Use centralized DatabaseLogger for beautiful logging
from shit.logging.service_loggers import DatabaseLogger

# Create DatabaseLogger instance
db_logger = DatabaseLogger("s3_processor")
logger = db_logger.logger

class S3Processor:
    """Operations for processing S3 data to database."""
    
    def __init__(self, db_ops: DatabaseOperations, s3_data_lake: S3DataLake, source: str = "truth_social"):
        self.db_ops = db_ops
        self.s3_data_lake = s3_data_lake
        self.source = source
        self.signal_ops = SignalOperations(db_ops)
        self.shitpost_ops = ShitpostOperations(db_ops)  # Keep for backward compat
        self._transformer = SignalTransformer.get_transformer(source)
    
    async def process_s3_to_database(self, start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None,
                                   limit: Optional[int] = None,
                                   incremental: bool = False,
                                   dry_run: bool = False) -> Dict[str, int]:
        """Process S3 data and load into database (consolidated method).
        
        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            limit: Maximum number of records to process (optional)
            incremental: If True, only process files from today (incremental mode)
            dry_run: If True, don't actually store to database
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            logger.info("")
            logger.info("═══════════════════════════════════════════════════════════")
            if dry_run:
                logger.info("PROCESSING S3 TO DATABASE (DRY RUN)")
            else:
                logger.info("PROCESSING S3 TO DATABASE")
            logger.info("═══════════════════════════════════════════════════════════")
            
            # Handle incremental mode
            if incremental:
                # Find the most recent processed post ID from database
                most_recent_post_id = await self._get_most_recent_post_id()
                if most_recent_post_id:
                    logger.info(f"Incremental mode: Found most recent post ID: {most_recent_post_id}")
                    # Get S3 keys and find the cutoff point
                    s3_keys = await self.s3_data_lake.list_raw_data(start_date, end_date, limit)
                    cutoff_index = await self._find_cutoff_index(s3_keys, most_recent_post_id)
                    if cutoff_index is not None:
                        # Only process keys before the cutoff (newer posts)
                        if cutoff_index == 0:
                            logger.info(f"Incremental mode: Most recent post already processed - found 0 new posts to process")
                        else:
                            logger.info(f"Incremental mode: Found {cutoff_index} new posts to process (cutoff at index {cutoff_index})")
                        s3_keys = s3_keys[:cutoff_index]
                    else:
                        logger.info(f"Incremental mode: Post ID {most_recent_post_id} not found in S3 - processing all files")
                else:
                    logger.info(f"Incremental mode: No posts found in database - will process all S3 files")
                    most_recent_post_id = None
            
            logger.info(f"Date range: {start_date} to {end_date}")
            logger.info(f"Limit: {limit}")
            
            stats = {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
            
            # Process S3 data (use filtered keys if in incremental mode)
            if incremental and most_recent_post_id and 's3_keys' in locals():
                # Process only the filtered S3 keys (newer posts)
                for s3_key in s3_keys:
                    stats['total_processed'] += 1
                    s3_data = await self.s3_data_lake.get_raw_data(s3_key)
                    if s3_data:
                        await self._process_single_s3_data(s3_data, stats, dry_run)
            else:
                # Normal processing - stream all data
                async for s3_data in self.s3_data_lake.stream_raw_data(start_date, end_date, limit):
                    stats['total_processed'] += 1
                    await self._process_single_s3_data(s3_data, stats, dry_run)
                
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
    
    async def _get_most_recent_post_id(self) -> Optional[str]:
        """Get the most recent processed post ID from the database.
        
        Returns:
            The most recent post ID, or None if no posts exist
        """
        try:
            # Query for the most recent post by timestamp
            from sqlalchemy import select, desc
            stmt = select(TruthSocialShitpost.shitpost_id).order_by(desc(TruthSocialShitpost.timestamp)).limit(1)
            result = await self.db_ops.session.execute(stmt)
            most_recent_id = result.scalar()
            
            if most_recent_id:
                logger.debug(f"Found most recent post ID in database: {most_recent_id}")
                return most_recent_id
            else:
                logger.debug("No posts found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error getting most recent post ID: {e}")
            return None
    
    async def _find_cutoff_index(self, s3_keys: List[str], target_post_id: str) -> Optional[int]:
        """Find the index in S3 keys where we should stop processing.
        
        Args:
            s3_keys: List of S3 keys sorted in reverse chronological order
            target_post_id: The post ID to find
            
        Returns:
            Index where to stop processing, or None if not found
        """
        try:
            for i, s3_key in enumerate(s3_keys):
                # Extract post ID from S3 key
                filename = s3_key.split('/')[-1].replace('.json', '')
                if filename == target_post_id:
                    logger.debug(f"Found target post ID {target_post_id} at index {i}")
                    return i
            logger.debug(f"Target post ID {target_post_id} not found in S3 keys")
            return None
        except Exception as e:
            logger.error(f"Error finding cutoff index: {e}")
            return None
    
    async def _process_single_s3_data(self, s3_data: Dict, stats: Dict, dry_run: bool):
        """Process a single S3 data record.
        
        Args:
            s3_data: S3 data to process
            stats: Statistics dictionary to update
            dry_run: If True, don't actually store to database
        """
        try:
            if dry_run:
                # In dry run, just count what would be processed
                stats['successful'] += 1
            else:
                # Transform using source-specific transformer and store in signals table
                signal_data = self._transformer(s3_data)
                result = await self.signal_ops.store_signal(signal_data)

                # Also store in legacy table for backward compatibility
                # TODO: Remove after full migration is complete
                legacy_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
                await self.shitpost_ops.store_shitpost(legacy_data)

                if result:
                    stats['successful'] += 1
                else:
                    stats['skipped'] += 1  # Already exists

        except Exception as e:
            logger.error(f"Error processing S3 data: {e}")
            stats['failed'] += 1
    
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
