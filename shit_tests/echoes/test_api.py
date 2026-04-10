"""
Tests for the Historical Echoes API endpoint.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class TestEchoesEndpoint:
    def test_returns_echoes_for_prediction(self):
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

        with patch("shit.echoes.echo_service.EchoService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_embedding.return_value = [0.1] * 1536
            mock_svc.find_similar_posts.return_value = [{"prediction_id": 10}]
            mock_svc.aggregate_echoes.return_value = mock_echo_data
            MockService.return_value = mock_svc

            resp = client.get("/api/echoes/for-prediction/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert data["avg_return"] == 1.5

    def test_404_when_no_embedding(self):
        with patch("shit.echoes.echo_service.EchoService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_embedding.return_value = None
            MockService.return_value = mock_svc

            resp = client.get("/api/echoes/for-prediction/999")

        assert resp.status_code == 404

    def test_custom_timeframe_param(self):
        with patch("shit.echoes.echo_service.EchoService") as MockService:
            mock_svc = MagicMock()
            mock_svc.get_embedding.return_value = [0.1] * 1536
            mock_svc.find_similar_posts.return_value = []
            mock_svc.aggregate_echoes.return_value = {
                "count": 0,
                "timeframe": "t30",
                "matches": [],
            }
            MockService.return_value = mock_svc

            resp = client.get("/api/echoes/for-prediction/1?timeframe=t30")

        assert resp.status_code == 200
        mock_svc.aggregate_echoes.assert_called_once_with([], timeframe="t30")
