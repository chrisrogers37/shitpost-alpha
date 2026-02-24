"""
Analyzer Event Consumer

Consumes ``signals_stored`` events and runs LLM analysis on new signals.
Runs as a standalone worker via ``python -m shitpost_ai.event_consumer --once``.
"""

import sys

from shit.events.event_types import ConsumerGroup
from shit.events.worker import EventWorker, run_worker_main
from shit.logging import get_service_logger

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
    return run_worker_main(
        AnalyzerWorker,
        service_name="analyzer_worker",
        prog="python -m shitpost_ai.event_consumer",
        description="Analyzer event consumer worker",
    )


if __name__ == "__main__":
    sys.exit(main())
