"""Tests for the AnalyzerWorker event consumer."""

import pytest
from unittest.mock import patch, AsyncMock

from shitpost_ai.event_consumer import AnalyzerWorker
from shit.events.event_types import ConsumerGroup


class TestAnalyzerWorker:
    """Tests for AnalyzerWorker.process_event()."""

    def test_consumer_group_is_analyzer(self):
        """Verify the worker registers with the correct consumer group.

        What it verifies: AnalyzerWorker.consumer_group == ConsumerGroup.ANALYZER
        Mocking: None.
        Assertions: consumer_group attribute matches the ANALYZER constant.
        """
        assert AnalyzerWorker.consumer_group == ConsumerGroup.ANALYZER

    def test_batch_size_uses_signal_count_when_larger(self):
        """Verify batch_size is max(signal_count, 5) -- uses signal_count when count > 5.

        What it verifies: When payload has count=10, the ShitpostAnalyzer is
        instantiated with batch_size=10 (not the minimum 5).
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=10
          - analyze_shitposts called with dry_run=False
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=10)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            result = worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1"] * 10, "source": "truth_social", "count": 10},
            )

            mock_cls.assert_called_once_with(mode="incremental", batch_size=10)
            mock_analyzer.analyze_shitposts.assert_awaited_once_with(dry_run=False)
            assert result == {"posts_analyzed": 10}

    def test_batch_size_minimum_is_five(self):
        """Verify batch_size floor of 5 when signal_count < 5.

        What it verifies: When payload has count=2, batch_size is max(2, 5) = 5.
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=5
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=2)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1", "s2"], "source": "truth_social", "count": 2},
            )

            mock_cls.assert_called_once_with(mode="incremental", batch_size=5)

    def test_batch_size_with_zero_count(self):
        """Verify batch_size when count is 0 or missing from payload.

        What it verifies: When payload has no 'count' key, max(0, 5) = 5.
        Mocking:
          - ShitpostAnalyzer constructor, initialize, analyze_shitposts, cleanup
        Assertions:
          - ShitpostAnalyzer called with batch_size=5
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=0)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ) as mock_cls:
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event("signals_stored", {"signal_ids": [], "source": "ts"})

            mock_cls.assert_called_once_with(mode="incremental", batch_size=5)

    def test_cleanup_called_on_success(self):
        """Verify analyzer.cleanup() is called after successful analysis.

        What it verifies: The try/finally ensures cleanup() is always awaited.
        Mocking:
          - ShitpostAnalyzer with successful analyze_shitposts
        Assertions:
          - cleanup was awaited exactly once
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(return_value=3)
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ):
            worker = AnalyzerWorker.__new__(AnalyzerWorker)
            worker.process_event(
                "signals_stored",
                {"signal_ids": ["s1"], "source": "ts", "count": 1},
            )

            mock_analyzer.cleanup.assert_awaited_once()

    def test_cleanup_called_on_failure(self):
        """Verify analyzer.cleanup() is called even when analysis raises.

        What it verifies: The try/finally block in _analyze() ensures cleanup()
        runs even if analyze_shitposts raises an exception.
        Mocking:
          - ShitpostAnalyzer.analyze_shitposts raises RuntimeError
        Assertions:
          - cleanup was awaited exactly once
          - The exception propagates
        """
        mock_analyzer = AsyncMock()
        mock_analyzer.initialize = AsyncMock()
        mock_analyzer.analyze_shitposts = AsyncMock(
            side_effect=RuntimeError("LLM API down")
        )
        mock_analyzer.cleanup = AsyncMock()

        with patch(
            "shitpost_ai.shitpost_analyzer.ShitpostAnalyzer",
            return_value=mock_analyzer,
        ):
            worker = AnalyzerWorker.__new__(AnalyzerWorker)

            with pytest.raises(RuntimeError, match="LLM API down"):
                worker.process_event(
                    "signals_stored",
                    {"signal_ids": ["s1"], "source": "ts", "count": 1},
                )

            mock_analyzer.cleanup.assert_awaited_once()
