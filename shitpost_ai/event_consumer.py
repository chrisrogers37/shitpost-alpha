"""
Analyzer Event Consumer

Consumes ``signals_stored`` events and runs LLM analysis on new signals.
Runs as a standalone worker via ``python -m shitpost_ai.event_consumer --once``.
"""

import argparse
import sys

from shit.events.event_types import EventType, ConsumerGroup
from shit.events.worker import EventWorker
from shit.logging import setup_cli_logging, get_service_logger

logger = get_service_logger("analyzer_worker")


class AnalyzerWorker(EventWorker):
    """Processes signals_stored events by running LLM analysis."""

    consumer_group = ConsumerGroup.ANALYZER

    def process_event(self, event_type: str, payload: dict) -> dict:
        """Process a signals_stored event.

        Runs the analyzer on unprocessed shitposts. The analyzer already
        handles deduplication (skips already-analyzed posts), so we can
        safely trigger it on every signals_stored event.

        Args:
            event_type: Should be EventType.SIGNALS_STORED.
            payload: Contains signal_ids, source, count.

        Returns:
            Analysis statistics dict.
        """
        import asyncio
        from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer

        signal_count = payload.get("count", 0)
        logger.info(f"Analyzing {signal_count} new signals")

        async def _analyze():
            analyzer = ShitpostAnalyzer(
                mode="incremental",
                batch_size=max(signal_count, 5),
            )
            try:
                await analyzer.initialize()
                analyzed = await analyzer.analyze_shitposts(dry_run=False)
                return {"posts_analyzed": analyzed}
            finally:
                await analyzer.cleanup()

        return asyncio.run(_analyze())


def main() -> int:
    """CLI entry point for the analyzer event consumer."""
    setup_cli_logging(service_name="analyzer_worker")

    parser = argparse.ArgumentParser(
        prog="python -m shitpost_ai.event_consumer",
        description="Analyzer event consumer worker",
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

    worker = AnalyzerWorker(poll_interval=args.poll_interval)

    if args.once:
        total = worker.run_once()
        print(f"Processed {total} events")
    else:
        worker.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
