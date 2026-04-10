"""Tests for the calibration API endpoint."""

from unittest.mock import patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.main import app
from shit.market_data.models import CalibrationCurve

client = TestClient(app)


class TestCalibrationCurveEndpoint:
    """Tests for GET /api/calibration/curve."""

    def _make_curve(self):
        curve = CalibrationCurve(
            id=1,
            fitted_at=datetime(2026, 4, 10, 2, 0, 0, tzinfo=timezone.utc),
            timeframe="t7",
            window_start=datetime(2025, 10, 10, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 10, tzinfo=timezone.utc),
            n_predictions=500,
            n_bins=10,
            bin_stats=[
                {
                    "bin_label": "0.7-0.8",
                    "bin_center": 0.75,
                    "n_total": 120,
                    "n_correct": 74,
                    "accuracy": 0.6167,
                }
            ],
            lookup_table={"0.7-0.8": 0.6167, "0.8-0.9": 0.55},
        )
        return curve

    def test_returns_curve(self):
        """Returns calibration curve data when available."""
        curve = self._make_curve()

        with patch(
            "shit.market_data.calibration.CalibrationService._load_latest_curve",
            return_value=curve,
        ):
            resp = client.get("/api/calibration/curve?timeframe=t7")

        assert resp.status_code == 200
        body = resp.json()
        assert body["timeframe"] == "t7"
        assert body["n_predictions"] == 500
        assert len(body["bin_stats"]) == 1
        assert body["lookup_table"]["0.7-0.8"] == 0.6167

    def test_returns_404_when_no_curve(self):
        """Returns 404 when no calibration curve is available."""
        with patch(
            "shit.market_data.calibration.CalibrationService._load_latest_curve",
            return_value=None,
        ):
            resp = client.get("/api/calibration/curve?timeframe=t7")

        assert resp.status_code == 404

    def test_validates_timeframe_parameter(self):
        """Rejects invalid timeframe values."""
        resp = client.get("/api/calibration/curve?timeframe=t99")
        assert resp.status_code == 422

    def test_default_timeframe_is_t7(self):
        """Default timeframe is t7 when not specified."""
        curve = self._make_curve()

        with patch(
            "shit.market_data.calibration.CalibrationService.__init__",
            return_value=None,
        ) as mock_init, patch(
            "shit.market_data.calibration.CalibrationService._load_latest_curve",
            return_value=curve,
        ):
            resp = client.get("/api/calibration/curve")

        assert resp.status_code == 200
        mock_init.assert_called_once_with(timeframe="t7")
