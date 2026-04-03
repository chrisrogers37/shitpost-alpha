"""
Market Data Event Consumer

Consumes ``prediction_created`` events and triggers market data backfill
and outcome calculation for new predictions.
Runs as a standalone worker via ``python -m shit.market_data.event_consumer --once``.
"""

import sys

from shit.events.event_types import ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

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
        from datetime import datetime

        from shit.db.sync_session import SessionLocal
        from shit.market_data.auto_backfill_service import AutoBackfillService
        from shit.market_data.snapshot_service import PriceSnapshotService

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

        # Capture live price snapshots immediately
        snapshots_captured = 0
        post_published_at = None
        if payload.get("post_published_at"):
            try:
                post_published_at = datetime.fromisoformat(payload["post_published_at"])
            except (ValueError, TypeError):
                pass

        try:
            with SessionLocal() as session:
                snapshot_svc = PriceSnapshotService()
                snapshots = snapshot_svc.capture_for_prediction(
                    session=session,
                    prediction_id=prediction_id,
                    assets=assets,
                    post_published_at=post_published_at,
                )
                snapshots_captured = len(snapshots)
                session.commit()
        except Exception as e:
            logger.warning(
                f"Snapshot capture failed for prediction {prediction_id}: {e}"
            )

        if snapshots_captured == 0 and assets:
            logger.warning(
                f"No snapshots captured for prediction {prediction_id} "
                f"despite having {len(assets)} assets: {assets}"
            )

        # Backfill price history + calculate outcomes
        service = AutoBackfillService()
        backfilled, outcomes = service.process_single_prediction(
            prediction_id=prediction_id,
            calculate_outcome=True,
        )

        return {
            "prediction_id": prediction_id,
            "snapshots_captured": snapshots_captured,
            "assets_backfilled": backfilled,
            "outcomes_calculated": outcomes,
        }


def main() -> int:
    """CLI entry point for the market data event consumer."""
    return run_worker_main(
        MarketDataWorker,
        service_name="market_data_worker",
        prog="python -m shit.market_data.event_consumer",
        description="Market Data event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
