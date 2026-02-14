"""
S3 Processor Event Consumer

Consumes ``posts_harvested`` events and processes S3 data to database.
Runs as a standalone worker via ``python -m shitvault.event_consumer --once``.
"""

import argparse
import sys

from shit.config.shitpost_settings import settings
from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger

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
        from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
        from shit.s3 import S3Config, S3DataLake
        from shitvault.s3_processor import S3Processor

        s3_keys = payload.get("s3_keys", [])
        source = payload.get("source", "truth_social")

        if not s3_keys:
            logger.info("No S3 keys in event payload, skipping")
            return {"total_processed": 0, "successful": 0}

        async def _process():
            db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
            db_client = DatabaseClient(db_config)
            await db_client.initialize()

            s3_config = S3Config(
                bucket_name=settings.S3_BUCKET_NAME,
                access_key_id=settings.AWS_ACCESS_KEY_ID,
                secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region=settings.AWS_REGION,
            )
            s3_data_lake = S3DataLake(s3_config)
            await s3_data_lake.initialize()

            try:
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
                            await processor._process_single_s3_data(s3_data, stats, dry_run=False)

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
            finally:
                await db_client.cleanup()

        return asyncio.run(_process())


def main() -> int:
    """CLI entry point for the S3 processor event consumer."""
    setup_cli_logging(service_name="s3_processor_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shitvault.event_consumer",
        description="S3 Processor event consumer worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain queue and exit (for cron deployment)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between polls in persistent mode (default: 2.0)",
    )
    args = parser.parse_args()

    worker = S3ProcessorWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
