"""
Notifications Event Consumer

Consumes ``prediction_created`` events and dispatches alerts to subscribers.
Runs as a standalone worker via ``python -m notifications.event_consumer --once``.
"""

import sys

from shit.events.event_types import ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

logger = get_service_logger("notifications_worker")


class NotificationsWorker(EventWorker):
    """Processes prediction_created events by dispatching alerts."""

    consumer_group = ConsumerGroup.NOTIFICATIONS

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a prediction_created event.

        Formats the prediction as an alert and dispatches it to all
        matching subscribers via Telegram.

        Args:
            event_type: Should be EventType.PREDICTION_CREATED.
            payload: Contains prediction_id, assets, confidence, analysis_status.

        Returns:
            Dispatch statistics dict.
        """
        from notifications.alert_engine import (
            filter_predictions_by_preferences,
        )
        from notifications.db import (
            get_active_subscriptions,
            record_alert_sent,
            record_error,
        )
        from notifications.telegram_sender import (
            build_vote_keyboard,
            format_telegram_alert,
            send_telegram_message,
        )
        import json

        prediction_id = payload.get("prediction_id")
        analysis_status = payload.get("analysis_status", "")

        if analysis_status != "completed":
            return {"skipped": True, "reason": f"status={analysis_status}"}

        # Build alert from event payload
        alert = {
            "prediction_id": prediction_id,
            "shitpost_id": payload.get("shitpost_id"),
            "confidence": payload.get("confidence"),
            "calibrated_confidence": payload.get("calibrated_confidence"),
            "assets": payload.get("assets", []),
            "sentiment": "neutral",  # Will be enriched if market_impact available
            "thesis": "",
            "text": "",
            "ensemble_metadata": payload.get("ensemble_metadata"),
        }

        # Enrich alert with Historical Echoes
        try:
            from shit.echoes.echo_service import EchoService

            echo_service = EchoService()
            embedding = echo_service.get_embedding(prediction_id)
            if embedding:
                matches = echo_service.find_similar_posts(
                    embedding,
                    limit=5,
                    exclude_prediction_id=prediction_id,
                )
                alert["echoes"] = echo_service.aggregate_echoes(matches, timeframe="t7")
        except Exception as e:
            logger.debug(f"Echo lookup skipped for prediction {prediction_id}: {e}")

        results = {"alerts_sent": 0, "alerts_failed": 0, "filtered": 0}

        subscriptions = get_active_subscriptions()
        if not subscriptions:
            logger.info("No active subscribers")
            return results

        for sub in subscriptions:
            prefs = sub.get("alert_preferences", {})
            if isinstance(prefs, str):
                try:
                    prefs = json.loads(prefs)
                except json.JSONDecodeError:
                    prefs = {}

            matched = filter_predictions_by_preferences([alert], prefs)
            if not matched:
                results["filtered"] += 1
                continue

            chat_id = sub["chat_id"]
            for a in matched:
                message = format_telegram_alert(a)
                reply_markup = (
                    build_vote_keyboard(prediction_id) if prediction_id else None
                )
                success, error = send_telegram_message(
                    chat_id, message, reply_markup=reply_markup
                )

                if success:
                    record_alert_sent(chat_id)
                    results["alerts_sent"] += 1

                    # Create follow-up tracking (fail-open)
                    if prediction_id:
                        try:
                            from notifications.followups import (
                                create_followup_tracking,
                            )
                            from datetime import datetime

                            create_followup_tracking(
                                prediction_id=prediction_id,
                                chat_id=chat_id,
                                alert_sent_at=datetime.utcnow(),
                            )
                        except Exception:
                            logger.debug(
                                f"Follow-up tracking failed for prediction {prediction_id}"
                            )
                else:
                    record_error(chat_id, error or "Unknown error")
                    results["alerts_failed"] += 1

        logger.info(
            f"Notification dispatch: {results['alerts_sent']} sent, "
            f"{results['alerts_failed']} failed, {results['filtered']} filtered"
        )
        return results


def main() -> int:
    """CLI entry point for the notifications event consumer."""
    return run_worker_main(
        NotificationsWorker,
        service_name="notifications_worker",
        prog="python -m notifications.event_consumer",
        description="Notifications event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
