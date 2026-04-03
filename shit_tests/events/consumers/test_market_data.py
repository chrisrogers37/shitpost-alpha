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
        process_single_prediction with the correct arguments. Also verifies
        PriceSnapshotService is invoked for live price capture.
        Mocking:
          - AutoBackfillService.process_single_prediction returns (3, 2)
          - PriceSnapshotService.capture_for_prediction returns 3 snapshots
          - SessionLocal context manager
        Assertions:
          - process_single_prediction called with prediction_id=42, calculate_outcome=True
          - Return dict has prediction_id, snapshots_captured, assets_backfilled, outcomes_calculated
        """
        mock_backfill = MagicMock()
        mock_backfill.process_single_prediction.return_value = (3, 2)

        mock_snapshot_svc = MagicMock()
        mock_snapshot_svc.capture_for_prediction.return_value = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]

        mock_session = MagicMock()

        with (
            patch(
                "shit.market_data.auto_backfill_service.AutoBackfillService",
                return_value=mock_backfill,
            ),
            patch(
                "shit.market_data.snapshot_service.PriceSnapshotService",
                return_value=mock_snapshot_svc,
            ),
            patch(
                "shit.db.sync_session.SessionLocal",
                return_value=mock_session,
            ),
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

            mock_backfill.process_single_prediction.assert_called_once_with(
                prediction_id=42,
                calculate_outcome=True,
            )
            assert result == {
                "prediction_id": 42,
                "snapshots_captured": 3,
                "assets_backfilled": 3,
                "outcomes_calculated": 2,
            }

    def test_logs_warning_when_zero_snapshots_captured(self):
        """Verify a warning is logged when snapshot capture returns 0 despite having assets.

        What it verifies: When PriceSnapshotService.capture_for_prediction raises
        an exception, snapshots_captured stays 0 and a warning is logged.
        Mocking:
          - PriceSnapshotService.capture_for_prediction raises RuntimeError
          - AutoBackfillService.process_single_prediction returns (0, 0)
          - SessionLocal context manager
        Assertions:
          - Warning log contains "No snapshots captured"
          - Result has snapshots_captured=0
        """
        mock_backfill = MagicMock()
        mock_backfill.process_single_prediction.return_value = (0, 0)

        mock_snapshot_svc = MagicMock()
        mock_snapshot_svc.capture_for_prediction.side_effect = RuntimeError(
            "yfinance down"
        )

        mock_session = MagicMock()

        with (
            patch(
                "shit.market_data.auto_backfill_service.AutoBackfillService",
                return_value=mock_backfill,
            ),
            patch(
                "shit.market_data.snapshot_service.PriceSnapshotService",
                return_value=mock_snapshot_svc,
            ),
            patch(
                "shit.db.sync_session.SessionLocal",
                return_value=mock_session,
            ),
            patch("shit.market_data.event_consumer.logger") as mock_logger,
        ):
            worker = MarketDataWorker.__new__(MarketDataWorker)
            result = worker.process_event(
                "prediction_created",
                {
                    "prediction_id": 99,
                    "assets": ["AAPL", "TSLA"],
                    "analysis_status": "completed",
                },
            )

            assert result["snapshots_captured"] == 0
            # Should have warning about capture failure + warning about 0 snapshots
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("No snapshots captured" in w for w in warning_calls)
