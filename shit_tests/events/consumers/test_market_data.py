"""Tests for the MarketDataWorker event consumer."""

from unittest.mock import patch, MagicMock

from shit.market_data.event_consumer import MarketDataWorker
from shit.events.event_types import ConsumerGroup


class TestMarketDataWorker:
    """Tests for MarketDataWorker.process_event()."""

    def test_consumer_group_is_market_data(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: MarketDataWorker.consumer_group == ConsumerGroup.MARKET_DATA
        Mocking: None.
        Assertions: consumer_group attribute matches the MARKET_DATA constant.
        """
        assert MarketDataWorker.consumer_group == ConsumerGroup.MARKET_DATA

    def test_skip_when_no_prediction_id(self):
        """Verify events without prediction_id are skipped.

        What it verifies: When payload has no prediction_id key, process_event
        returns {"skipped": True, "reason": "no prediction_id"} immediately.
        Mocking: None (early return before any service calls).
        Assertions:
          - Return dict has skipped=True
          - Return dict reason says "no prediction_id"
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {"assets": ["TSLA"], "analysis_status": "completed"},
        )

        assert result["skipped"] is True
        assert "no prediction_id" in result["reason"]

    def test_skip_when_analysis_not_completed(self):
        """Verify events with non-completed analysis_status are skipped.

        What it verifies: When analysis_status is "bypassed", the worker skips
        without calling AutoBackfillService.
        Mocking: None (early return).
        Assertions:
          - Return dict has skipped=True
          - Return dict reason says "not applicable"
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 42,
                "assets": ["TSLA"],
                "analysis_status": "bypassed",
            },
        )

        assert result["skipped"] is True
        assert "not applicable" in result["reason"]

    def test_skip_when_no_assets(self):
        """Verify events with empty assets list are skipped.

        What it verifies: When analysis_status is "completed" but assets is
        empty, the worker skips (the `not assets` check in the source).
        Mocking: None (early return).
        Assertions:
          - Return dict has skipped=True
        """
        worker = MarketDataWorker.__new__(MarketDataWorker)
        result = worker.process_event(
            "prediction_created",
            {
                "prediction_id": 42,
                "assets": [],
                "analysis_status": "completed",
            },
        )

        assert result["skipped"] is True

    def test_successful_backfill_returns_stats(self):
        """Verify successful processing calls AutoBackfillService and returns stats.

        What it verifies: For a valid prediction_created event (completed status,
        non-empty assets), the worker creates an AutoBackfillService and calls
        process_single_prediction with the correct arguments.
        Mocking:
          - AutoBackfillService.process_single_prediction returns (3, 2)
        Assertions:
          - process_single_prediction called with prediction_id=42, calculate_outcome=True
          - Return dict has prediction_id=42, assets_backfilled=3, outcomes_calculated=2
        """
        mock_service = MagicMock()
        mock_service.process_single_prediction.return_value = (3, 2)

        with patch(
            "shit.market_data.auto_backfill_service.AutoBackfillService",
            return_value=mock_service,
        ):
            worker = MarketDataWorker.__new__(MarketDataWorker)
            result = worker.process_event(
                "prediction_created",
                {
                    "prediction_id": 42,
                    "assets": ["TSLA", "AAPL", "SPY"],
                    "analysis_status": "completed",
                    "confidence": 0.85,
                },
            )

            mock_service.process_single_prediction.assert_called_once_with(
                prediction_id=42,
                calculate_outcome=True,
            )
            assert result == {
                "prediction_id": 42,
                "assets_backfilled": 3,
                "outcomes_calculated": 2,
            }
