"""Tests for confidence calibration service."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from shit.market_data.calibration import CalibrationService, VALID_TIMEFRAMES, refit_all
from shit.market_data.models import CalibrationCurve


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    """Default calibration service with T+7 timeframe."""
    return CalibrationService(timeframe="t7", min_samples=10, min_per_bin=3)


@pytest.fixture
def overconfident_data():
    """500 predictions simulating an overconfident LLM.

    Raw confidence is uniformly 0.3-0.95. Actual accuracy = raw * 0.7,
    so 0.9 confidence -> ~63% correct, not 90%.
    """
    import random

    random.seed(42)
    data = []
    for _ in range(500):
        conf = random.uniform(0.3, 0.95)
        correct = random.random() < (conf * 0.7)
        data.append({"confidence": conf, "correct": correct})
    return data


@pytest.fixture
def uniform_data():
    """200 predictions spread uniformly across 10 bins, 50% accuracy each."""
    data = []
    for bin_idx in range(10):
        conf_center = bin_idx / 10 + 0.05
        for j in range(20):
            data.append({"confidence": conf_center, "correct": j % 2 == 0})
    return data


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_valid_timeframes(self):
        for tf in VALID_TIMEFRAMES:
            svc = CalibrationService(timeframe=tf)
            assert svc.timeframe == tf

    def test_invalid_timeframe_raises(self):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            CalibrationService(timeframe="t99")

    def test_defaults(self):
        svc = CalibrationService()
        assert svc.timeframe == "t7"
        assert svc.window_days == 180
        assert svc.min_samples == 100
        assert svc.min_per_bin == 5
        assert svc.n_bins == 10
        assert svc.max_age_days == 30


# ---------------------------------------------------------------------------
# Lookup Table
# ---------------------------------------------------------------------------


class TestLookupTable:
    def test_uniform_accuracy(self, service, uniform_data):
        confidences = [d["confidence"] for d in uniform_data]
        correct_flags = [d["correct"] for d in uniform_data]
        lookup = service._build_lookup_table(confidences, correct_flags)

        # Each bin has 20 samples (200 / 10), alternating -> 50% accuracy
        for label, accuracy in lookup.items():
            assert accuracy == 0.5

    def test_sparse_bins_return_none(self):
        svc = CalibrationService(min_per_bin=5)
        confidences = [0.85, 0.86]  # Only 2 samples in the 0.8-0.9 bin
        correct_flags = [True, False]
        lookup = svc._build_lookup_table(confidences, correct_flags)

        assert lookup["0.8-0.9"] is None  # Below min_per_bin

    def test_empty_data(self, service):
        lookup = service._build_lookup_table([], [])
        assert lookup == {}

    def test_overconfident_model(self, service, overconfident_data):
        confidences = [d["confidence"] for d in overconfident_data]
        correct_flags = [d["correct"] for d in overconfident_data]
        lookup = service._build_lookup_table(confidences, correct_flags)

        # High-confidence bin (0.8-0.9) should be well below 0.85 midpoint
        high_bin = lookup.get("0.8-0.9")
        assert high_bin is not None
        assert high_bin < 0.80  # Overconfident: actual < raw

    def test_single_bin(self, service):
        """All predictions in one bin."""
        confidences = [0.75, 0.76, 0.77, 0.78, 0.79]
        correct_flags = [True, True, False, True, False]
        lookup = service._build_lookup_table(confidences, correct_flags)

        assert "0.7-0.8" in lookup
        assert lookup["0.7-0.8"] == 0.6  # 3/5

    def test_boundary_confidence_1_0(self, service):
        """Confidence of exactly 1.0 goes into the last bin."""
        confidences = [1.0, 1.0, 1.0, 1.0, 1.0]
        correct_flags = [True, True, True, True, False]
        lookup = service._build_lookup_table(confidences, correct_flags)

        assert "0.9-1.0" in lookup
        assert lookup["0.9-1.0"] == 0.8  # 4/5

    def test_boundary_confidence_0_0(self, service):
        """Confidence of exactly 0.0 goes into the first bin."""
        confidences = [0.0, 0.0, 0.0]
        correct_flags = [False, False, True]
        lookup = service._build_lookup_table(confidences, correct_flags)

        assert "0.0-0.1" in lookup
        assert lookup["0.0-0.1"] == 0.3333  # 1/3 rounded to 4 decimal places


# ---------------------------------------------------------------------------
# Bin Stats
# ---------------------------------------------------------------------------


class TestBinStats:
    def test_all_bins_present(self, service, uniform_data):
        confidences = [d["confidence"] for d in uniform_data]
        correct_flags = [d["correct"] for d in uniform_data]
        stats = service._compute_bin_stats(confidences, correct_flags)

        assert len(stats) == 10
        for i, s in enumerate(stats):
            assert s["bin_label"] == f"{i / 10:.1f}-{(i + 1) / 10:.1f}"
            assert "bin_center" in s
            assert "n_total" in s
            assert "n_correct" in s
            assert "accuracy" in s

    def test_empty_bins_have_zero_total(self, service):
        confidences = [0.55]  # Only bin 5
        correct_flags = [True]
        stats = service._compute_bin_stats(confidences, correct_flags)

        assert stats[0]["n_total"] == 0
        assert stats[0]["accuracy"] is None
        assert stats[5]["n_total"] == 1
        assert stats[5]["accuracy"] == 1.0

    def test_bin_centers(self, service):
        stats = service._compute_bin_stats([], [])
        assert stats[0]["bin_center"] == 0.05
        assert stats[5]["bin_center"] == 0.55
        assert stats[9]["bin_center"] == 0.95


# ---------------------------------------------------------------------------
# Calibrate (lookup application)
# ---------------------------------------------------------------------------


class TestCalibrate:
    def test_returns_none_when_no_curve(self, service):
        with patch.object(service, "_load_latest_curve", return_value=None):
            result = service.calibrate(0.8)
            assert result is None

    def test_returns_accuracy_for_bin(self, service):
        mock_curve = MagicMock()
        mock_curve.lookup_table = {"0.7-0.8": 0.62, "0.8-0.9": 0.55}

        with patch.object(service, "_load_latest_curve", return_value=mock_curve):
            assert service.calibrate(0.75) == 0.62
            assert service.calibrate(0.85) == 0.55

    def test_returns_none_for_sparse_bin(self, service):
        mock_curve = MagicMock()
        mock_curve.lookup_table = {"0.7-0.8": 0.62, "0.8-0.9": None}

        with patch.object(service, "_load_latest_curve", return_value=mock_curve):
            assert service.calibrate(0.85) is None

    def test_boundary_1_0_uses_last_bin(self, service):
        mock_curve = MagicMock()
        mock_curve.lookup_table = {"0.9-1.0": 0.71}

        with patch.object(service, "_load_latest_curve", return_value=mock_curve):
            assert service.calibrate(1.0) == 0.71

    def test_boundary_0_0_uses_first_bin(self, service):
        mock_curve = MagicMock()
        mock_curve.lookup_table = {"0.0-0.1": 0.12}

        with patch.object(service, "_load_latest_curve", return_value=mock_curve):
            assert service.calibrate(0.0) == 0.12


# ---------------------------------------------------------------------------
# Fit (end-to-end with mocked DB)
# ---------------------------------------------------------------------------


class TestFit:
    def test_insufficient_data_returns_none(self, service):
        with patch.object(service, "_query_calibration_data", return_value=[]):
            result = service.fit()
            assert result is None

    def test_fit_stores_curve(self, service, overconfident_data):
        with patch.object(service, "_query_calibration_data", return_value=overconfident_data):
            with patch.object(service, "_store_curve") as mock_store:
                curve = service.fit()

                assert curve is not None
                assert curve.timeframe == "t7"
                assert curve.n_predictions == 500
                assert curve.n_bins == 10
                assert isinstance(curve.lookup_table, dict)
                assert isinstance(curve.bin_stats, list)
                assert len(curve.bin_stats) == 10
                mock_store.assert_called_once_with(curve)


# ---------------------------------------------------------------------------
# Staleness Guard
# ---------------------------------------------------------------------------


class TestStaleness:
    def test_fresh_curve_returned(self, service):
        curve = CalibrationCurve(
            fitted_at=datetime.now(timezone.utc) - timedelta(days=5),
            timeframe="t7",
            window_start=datetime.now(timezone.utc) - timedelta(days=185),
            window_end=datetime.now(timezone.utc) - timedelta(days=5),
            n_predictions=200,
            n_bins=10,
            bin_stats=[],
            lookup_table={"0.7-0.8": 0.62},
        )

        mock_session = MagicMock()
        mock_query = mock_session.query.return_value.filter.return_value.order_by.return_value
        mock_query.first.return_value = curve

        with patch("shit.market_data.calibration.get_session") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            result = service._load_latest_curve()

        assert result is not None

    def test_stale_curve_returns_none(self):
        svc = CalibrationService(max_age_days=7)
        curve = CalibrationCurve(
            fitted_at=datetime.now(timezone.utc) - timedelta(days=10),
            timeframe="t7",
            window_start=datetime.now(timezone.utc) - timedelta(days=190),
            window_end=datetime.now(timezone.utc) - timedelta(days=10),
            n_predictions=200,
            n_bins=10,
            bin_stats=[],
            lookup_table={"0.7-0.8": 0.62},
        )

        mock_session = MagicMock()
        mock_query = mock_session.query.return_value.filter.return_value.order_by.return_value
        mock_query.first.return_value = curve

        with patch("shit.market_data.calibration.get_session") as mock_get:
            mock_get.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get.return_value.__exit__ = MagicMock(return_value=False)
            result = svc._load_latest_curve()

        assert result is None


# ---------------------------------------------------------------------------
# Refit All
# ---------------------------------------------------------------------------


class TestRefitAll:
    def test_refits_all_timeframes(self):
        with patch("shit.market_data.calibration.CalibrationService") as MockSvc:
            mock_instance = MagicMock()
            mock_curve = MagicMock()
            mock_curve.n_predictions = 300
            mock_instance.fit.return_value = mock_curve
            MockSvc.return_value = mock_instance

            results = refit_all()

            assert len(results) == 4
            for tf in VALID_TIMEFRAMES:
                assert results[tf] == 300

    def test_refits_single_timeframe(self):
        with patch("shit.market_data.calibration.CalibrationService") as MockSvc:
            mock_instance = MagicMock()
            mock_curve = MagicMock()
            mock_curve.n_predictions = 150
            mock_instance.fit.return_value = mock_curve
            MockSvc.return_value = mock_instance

            results = refit_all(timeframes=["t7"])

            assert results == {"t7": 150}
            MockSvc.assert_called_once_with(timeframe="t7")

    def test_insufficient_data_returns_zero(self):
        with patch("shit.market_data.calibration.CalibrationService") as MockSvc:
            mock_instance = MagicMock()
            mock_instance.fit.return_value = None
            MockSvc.return_value = mock_instance

            results = refit_all(timeframes=["t7"])

            assert results == {"t7": 0}
