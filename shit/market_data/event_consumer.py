"""
Market Data Event Consumer

Consumes ``prediction_created`` events and triggers market data backfill
and outcome calculation for new predictions.
Runs as a standalone worker via ``python -m shit.market_data.event_consumer --once``.
"""

import argparse
import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger

logger = get_service_logger("market_data_worker")


class MarketDataWorker(EventWorker):
    """Processes prediction_created events by backfilling market data."""

    consumer_group = ConsumerGroup.MARKET_DATA

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a prediction_created event.

        Triggers market data backfill and outcome calculation for the
        prediction's assets.

        Args:
            event_type: Should be EventType.PREDICTION_CREATED.
            payload: Contains prediction_id, assets, confidence, analysis_status.

        Returns:
            Backfill statistics dict.
        """
        from shit.market_data.auto_backfill_service import AutoBackfillService

        prediction_id = payload.get("prediction_id")
        assets = payload.get("assets", [])
        analysis_status = payload.get("analysis_status", "")

        if not prediction_id:
            logger.warning("No prediction_id in event payload")
            return {"skipped": True, "reason": "no prediction_id"}

        # Only process completed analyses with assets
        if analysis_status != "completed" or not assets:
            logger.debug(
                f"Skipping prediction {prediction_id}: "
                f"status={analysis_status}, assets={assets}"
            )
            return {"skipped": True, "reason": "not applicable"}

        service = AutoBackfillService()
        backfilled, outcomes = service.process_single_prediction(
            prediction_id=prediction_id,
            calculate_outcome=True,
        )

        return {
            "prediction_id": prediction_id,
            "assets_backfilled": backfilled,
            "outcomes_calculated": outcomes,
        }


def main() -> int:
    """CLI entry point for the market data event consumer."""
    setup_cli_logging(service_name="market_data_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shit.market_data.event_consumer",
        description="Market Data event consumer worker",
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

    worker = MarketDataWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
