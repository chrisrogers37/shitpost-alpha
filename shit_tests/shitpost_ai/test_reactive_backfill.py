"""
Tests for reactive backfill integration in shitpost_ai/shitpost_analyzer.py.

Tests the _trigger_reactive_backfill method and its integration with _analyze_shitpost.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from shitpost_ai.shitpost_analyzer import ShitpostAnalyzer

BACKFILL_PATCH = "shitpost_ai.shitpost_analyzer.auto_backfill_prediction"
SNAPSHOT_SVC_PATCH = "shit.market_data.snapshot_service.PriceSnapshotService"
SESSION_PATCH = "shit.db.sync_session.SessionLocal"


class TestCaptureSnapshots:
    """Tests for ShitpostAnalyzer._capture_snapshots static method."""

    def test_captures_snapshots_and_commits(self):
        mock_session = MagicMock()
        mock_svc = MagicMock()
        mock_svc.capture_for_prediction.return_value = [MagicMock(), MagicMock()]

        with (
            patch(SESSION_PATCH, return_value=mock_session),
            patch(SNAPSHOT_SVC_PATCH, return_value=mock_svc),
        ):
            result = ShitpostAnalyzer._capture_snapshots(42, ["AAPL", "TSLA"])

        assert result == 2
        mock_svc.capture_for_prediction.assert_called_once_with(
            session=mock_session.__enter__(),
            prediction_id=42,
            assets=["AAPL", "TSLA"],
            post_published_at=None,
        )
        mock_session.__enter__().commit.assert_called_once()

    def test_passes_post_published_at(self):
        from datetime import datetime

        ts = datetime(2026, 3, 25, 14, 30, 0)
        mock_session = MagicMock()
        mock_svc = MagicMock()
        mock_svc.capture_for_prediction.return_value = []

        with (
            patch(SESSION_PATCH, return_value=mock_session),
            patch(SNAPSHOT_SVC_PATCH, return_value=mock_svc),
        ):
            ShitpostAnalyzer._capture_snapshots(42, ["AAPL"], post_published_at=ts)

        mock_svc.capture_for_prediction.assert_called_once_with(
            session=mock_session.__enter__(),
            prediction_id=42,
            assets=["AAPL"],
            post_published_at=ts,
        )

    def test_propagates_exceptions(self):
        mock_session = MagicMock()
        mock_svc = MagicMock()
        mock_svc.capture_for_prediction.side_effect = RuntimeError("db down")

        with (
            patch(SESSION_PATCH, return_value=mock_session),
            patch(SNAPSHOT_SVC_PATCH, return_value=mock_svc),
        ):
            with pytest.raises(RuntimeError, match="db down"):
                ShitpostAnalyzer._capture_snapshots(42, ["AAPL"])


class TestTriggerReactiveBackfill:
    """Tests for ShitpostAnalyzer._trigger_reactive_backfill."""

    @pytest.fixture
    def analyzer(self):
        """Create an analyzer instance without initializing DB/LLM."""
        with patch("shitpost_ai.shitpost_analyzer.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///:memory:"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            a = ShitpostAnalyzer()
        return a

    @pytest.mark.asyncio
    async def test_captures_snapshots_before_backfill(self, analyzer):
        """Snapshot capture runs before backfill (most time-sensitive first)."""
        call_order = []
        with (
            patch.object(
                ShitpostAnalyzer,
                "_capture_snapshots",
                side_effect=lambda *a, **k: call_order.append("snapshot") or 2,
            ),
            patch(
                BACKFILL_PATCH,
                side_effect=lambda *a, **k: call_order.append("backfill") or True,
            ),
        ):
            await analyzer._trigger_reactive_backfill(42, ["AAPL"])
        assert call_order == ["snapshot", "backfill"]

    @pytest.mark.asyncio
    async def test_calls_auto_backfill_prediction_with_correct_id(self, analyzer):
        with (
            patch.object(ShitpostAnalyzer, "_capture_snapshots", return_value=0),
            patch(BACKFILL_PATCH, return_value=True) as mock_bf,
        ):
            await analyzer._trigger_reactive_backfill(42, ["AAPL", "TSLA"])
        mock_bf.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_snapshot_failure_does_not_block_backfill(self, analyzer):
        """If snapshot capture fails, backfill should still run."""
        with (
            patch.object(
                ShitpostAnalyzer,
                "_capture_snapshots",
                side_effect=RuntimeError("snap fail"),
            ),
            patch(BACKFILL_PATCH, return_value=True) as mock_bf,
        ):
            await analyzer._trigger_reactive_backfill(42, ["AAPL"])
        mock_bf.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_logs_success_on_backfill(self, analyzer):
        with (
            patch.object(ShitpostAnalyzer, "_capture_snapshots", return_value=0),
            patch(BACKFILL_PATCH, return_value=True),
        ):
            with patch("shitpost_ai.shitpost_analyzer.logger") as mock_logger:
                await analyzer._trigger_reactive_backfill(42, ["AAPL"])
                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_logs_debug_when_no_new_data_needed(self, analyzer):
        with (
            patch.object(ShitpostAnalyzer, "_capture_snapshots", return_value=0),
            patch(BACKFILL_PATCH, return_value=False),
        ):
            with patch("shitpost_ai.shitpost_analyzer.logger") as mock_logger:
                await analyzer._trigger_reactive_backfill(42, ["AAPL"])
                mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_catches_exception_and_logs_warning(self, analyzer):
        with (
            patch.object(ShitpostAnalyzer, "_capture_snapshots", return_value=0),
            patch(BACKFILL_PATCH, side_effect=Exception("boom")),
        ):
            with patch("shitpost_ai.shitpost_analyzer.logger") as mock_logger:
                await analyzer._trigger_reactive_backfill(42, ["AAPL"])
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_does_not_propagate_backfill_errors(self, analyzer):
        with (
            patch.object(ShitpostAnalyzer, "_capture_snapshots", return_value=0),
            patch(BACKFILL_PATCH, side_effect=RuntimeError("db down")),
        ):
            await analyzer._trigger_reactive_backfill(42, ["AAPL"])


class TestAnalyzeShitpostReactiveIntegration:
    """Tests for _analyze_shitpost integration with reactive backfill."""

    @pytest.fixture
    def analyzer(self):
        """Create a fully mocked analyzer."""
        with patch("shitpost_ai.shitpost_analyzer.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///:memory:"
            mock_settings.SYSTEM_LAUNCH_DATE = "2024-01-01"
            a = ShitpostAnalyzer()

        a.bypass_service = MagicMock()
        a.bypass_service.should_bypass_post.return_value = (False, None)
        a.llm_client = AsyncMock()
        a.prediction_ops = AsyncMock()
        return a

    def _make_shitpost(self, shitpost_id="post_123"):
        return {
            "shitpost_id": shitpost_id,
            "text": "AAPL is going to the moon!",
            "username": "testuser",
            "timestamp": "2024-01-15T12:00:00Z",
            "replies_count": 10,
            "reblogs_count": 5,
            "favourites_count": 20,
            "upvotes_count": 15,
            "account_verified": True,
            "account_followers_count": 1000,
            "has_media": False,
            "mentions": [],
            "tags": [],
        }

    @pytest.mark.asyncio
    async def test_triggers_backfill_after_successful_analysis(self, analyzer):
        analysis = {"assets": ["AAPL"], "confidence": 0.85, "thesis": "bullish"}
        analyzer.llm_client.analyze.return_value = analysis
        analyzer.prediction_ops.store_analysis.return_value = "42"

        with patch.object(
            analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
        ) as mock_bf:
            await analyzer._analyze_shitpost(self._make_shitpost(), dry_run=False)
            mock_bf.assert_called_once_with(42, ["AAPL"], post_published_at=None)

    @pytest.mark.asyncio
    async def test_does_not_trigger_backfill_on_dry_run(self, analyzer):
        analysis = {"assets": ["AAPL"], "confidence": 0.85}
        analyzer.llm_client.analyze.return_value = analysis

        with patch.object(
            analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
        ) as mock_bf:
            await analyzer._analyze_shitpost(self._make_shitpost(), dry_run=True)
            mock_bf.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_trigger_backfill_when_no_assets(self, analyzer):
        analysis = {"assets": [], "confidence": 0.3}
        analyzer.llm_client.analyze.return_value = analysis
        analyzer.prediction_ops.store_analysis.return_value = "42"

        with patch.object(
            analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
        ) as mock_bf:
            await analyzer._analyze_shitpost(self._make_shitpost(), dry_run=False)
            mock_bf.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_trigger_backfill_when_store_fails(self, analyzer):
        analysis = {"assets": ["AAPL"], "confidence": 0.85}
        analyzer.llm_client.analyze.return_value = analysis
        analyzer.prediction_ops.store_analysis.return_value = None

        with patch.object(
            analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
        ) as mock_bf:
            await analyzer._analyze_shitpost(self._make_shitpost(), dry_run=False)
            mock_bf.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_trigger_backfill_for_bypassed_posts(self, analyzer):
        analyzer.bypass_service.should_bypass_post.return_value = (True, "retruth")
        analyzer.prediction_ops.handle_no_text_prediction = AsyncMock()

        with patch.object(
            analyzer, "_trigger_reactive_backfill", new_callable=AsyncMock
        ) as mock_bf:
            result = await analyzer._analyze_shitpost(
                self._make_shitpost(), dry_run=False
            )
            mock_bf.assert_not_called()
            assert result["analysis_status"] == "bypassed"
