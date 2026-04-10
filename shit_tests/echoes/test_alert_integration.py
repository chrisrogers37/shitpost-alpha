"""
Tests for echo integration in Telegram alerts and event consumer.

Covers: format_telegram_alert echo rendering, event consumer echo enrichment.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import patch, MagicMock

from notifications.telegram_sender import format_telegram_alert, _format_echo_section


class TestFormatEchoSection:
    def test_no_echoes_returns_empty(self):
        assert _format_echo_section({}) == ""
        assert _format_echo_section({"echoes": None}) == ""
        assert _format_echo_section({"echoes": {"count": 0}}) == ""

    def test_with_full_echoes(self):
        alert = {
            "echoes": {
                "count": 3,
                "avg_return": 1.8,
                "win_rate": 0.6667,
                "correct": 2,
                "incorrect": 1,
                "pending": 0,
                "avg_pnl": 18.0,
            }
        }
        result = _format_echo_section(alert)
        assert "Historical Echoes" in result
        assert "3 similar posts" in result
        assert "1\\.8%" in result  # escape_markdown escapes the dot
        assert "2/3" in result
        assert "\\+18" in result  # escape_markdown escapes the plus

    def test_pending_only(self):
        alert = {
            "echoes": {
                "count": 2,
                "avg_return": None,
                "win_rate": None,
                "correct": 0,
                "incorrect": 0,
                "pending": 2,
                "avg_pnl": None,
            }
        }
        result = _format_echo_section(alert)
        assert "pending" in result
        assert "too recent" in result

    def test_partial_data_with_evaluated_outcomes(self):
        """When some outcomes are evaluated, show return stats but not win rate if None."""
        alert = {
            "echoes": {
                "count": 2,
                "avg_return": 2.5,
                "win_rate": None,
                "correct": 1,
                "incorrect": 0,
                "pending": 1,
                "avg_pnl": None,
            }
        }
        result = _format_echo_section(alert)
        assert "2\\.5%" in result  # escape_markdown escapes the dot
        assert "P&L" not in result  # avg_pnl is None


class TestFormatTelegramAlertWithEchoes:
    def test_alert_with_echoes_included(self):
        alert = {
            "sentiment": "bullish",
            "confidence": 0.82,
            "assets": ["XLE", "OXY"],
            "text": "Drill baby drill!",
            "thesis": "Pro-energy policy signals",
            "echoes": {
                "count": 3,
                "avg_return": 1.8,
                "win_rate": 0.6667,
                "correct": 2,
                "incorrect": 1,
                "pending": 0,
                "avg_pnl": 18.0,
            },
        }
        result = format_telegram_alert(alert)
        assert "SHITPOST ALPHA ALERT" in result
        assert "Historical Echoes" in result
        assert "NOT financial advice" in result

    def test_alert_without_echoes_unchanged(self):
        alert = {
            "sentiment": "bullish",
            "confidence": 0.82,
            "assets": ["XLE"],
            "text": "Energy is great",
            "thesis": "Bullish energy",
        }
        result = format_telegram_alert(alert)
        assert "SHITPOST ALPHA ALERT" in result
        assert "Historical Echoes" not in result


class TestEventConsumerEchoEnrichment:
    def test_echo_enrichment_added_to_alert(self):
        """Verify event consumer adds echoes to the alert dict before dispatch."""
        from notifications.event_consumer import NotificationsWorker

        mock_echo_data = {
            "count": 2,
            "timeframe": "t7",
            "avg_return": 1.5,
            "win_rate": 0.5,
            "correct": 1,
            "incorrect": 1,
            "pending": 0,
            "avg_pnl": 15.0,
            "matches": [],
        }

        worker = NotificationsWorker.__new__(NotificationsWorker)

        with (
            patch(
                "notifications.db.get_active_subscriptions",
                return_value=[],
            ),
            patch("shit.echoes.echo_service.EchoService") as MockService,
        ):
            mock_svc = MagicMock()
            mock_svc.get_embedding.return_value = [0.1] * 1536
            mock_svc.find_similar_posts.return_value = [{"prediction_id": 10}]
            mock_svc.aggregate_echoes.return_value = mock_echo_data
            MockService.return_value = mock_svc

            worker.process_event(
                "prediction_created",
                {
                    "prediction_id": 1,
                    "analysis_status": "completed",
                    "assets": ["XLE"],
                    "confidence": 0.8,
                },
            )

        # No subscribers, so 0 alerts sent, but the echo lookup was attempted
        mock_svc.get_embedding.assert_called_once_with(1)

    def test_echo_failure_does_not_break_alert(self):
        """If echo lookup fails, alert should still dispatch."""
        from notifications.event_consumer import NotificationsWorker

        worker = NotificationsWorker.__new__(NotificationsWorker)

        with (
            patch(
                "notifications.db.get_active_subscriptions",
                return_value=[{"chat_id": "123", "alert_preferences": {}}],
            ),
            patch(
                "notifications.alert_engine.filter_predictions_by_preferences",
                side_effect=lambda alerts, _: alerts,
            ),
            patch(
                "notifications.telegram_sender.format_telegram_alert",
                return_value="test message",
            ),
            patch(
                "notifications.telegram_sender.send_telegram_message",
                return_value=(True, None),
            ),
            patch(
                "notifications.db.record_alert_sent",
            ),
            patch(
                "shit.echoes.echo_service.EchoService", side_effect=Exception("DB down")
            ),
        ):
            result = worker.process_event(
                "prediction_created",
                {
                    "prediction_id": 1,
                    "analysis_status": "completed",
                    "assets": ["XLE"],
                    "confidence": 0.8,
                },
            )

        assert result["alerts_sent"] == 1
