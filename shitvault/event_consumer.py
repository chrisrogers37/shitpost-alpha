"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

logger = get_service_logger("s3_processor_worker")


class S3ProcessorWorker(EventWorker):
    """Processes posts_harvested events by loading S3 data into the database."""

    consumer_group = ConsumerGroup.S3_PROCESSOR

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a posts_harvested event.

        Runs the S3 processor for the specific keys in the event payload,
        then emits a signals_stored event with the resulting signal IDs.

        Args:
            event_type: Should be EventType.POSTS_HARVESTED.
            payload: Contains s3_keys, source, count, mode.

        Returns:
            Processing statistics dict.
        """
        import asyncio
        from shit.db import DatabaseOperations
        from shit.services import db_and_s3_service
        from shitvault.s3_processor import S3Processor

        s3_keys = payload.get("s3_keys", [])
        source = payload.get("source", "truth_social")

        if not s3_keys:
            logger.info("No S3 keys in event payload, skipping")
            return {"total_processed": 0, "successful": 0}

        async def _process():
            async with db_and_s3_service() as (db_client, s3_data_lake):
                async with db_client.get_session() as session:
                    db_ops = DatabaseOperations(session)
                    processor = S3Processor(db_ops, s3_data_lake, source=source)

                    stats = {
                        "total_processed": 0,
                        "successful": 0,
                        "failed": 0,
                        "skipped": 0,
                        "signal_ids": [],
                    }

                    for s3_key in s3_keys:
                        stats["total_processed"] += 1
                        s3_data = await s3_data_lake.get_raw_data(s3_key)
                        if s3_data:
                            await processor._process_single_s3_data(
                                s3_data, stats, dry_run=False
                            )

                    # Emit downstream event
                    signal_ids = stats.pop("signal_ids", [])
                    if signal_ids:
                        from shit.events.producer import emit_event

                        emit_event(
                            event_type=EventType.SIGNALS_STORED,
                            payload={
                                "signal_ids": signal_ids,
                                "source": source,
                                "count": len(signal_ids),
                            },
                            source_service="s3_processor",
                        )

                    return stats

        return asyncio.run(_process())


def main() -> int:
    """CLI entry point for the S3 processor event consumer."""
    return run_worker_main(
        S3ProcessorWorker,
        service_name="s3_processor_worker",
        prog="python -m shitvault.event_consumer",
        description="S3 Processor event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
