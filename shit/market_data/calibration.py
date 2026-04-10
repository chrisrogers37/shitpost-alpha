"""
Confidence Calibration Service

Fits calibration curves from historical prediction outcomes and applies
calibrated confidence to new predictions. Uses bin-based lookup tables
to map raw LLM confidence to empirical accuracy rates.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from shit.db.sync_session import get_session
from shit.logging import get_service_logger
from shit.market_data.models import CalibrationCurve

logger = get_service_logger("calibration")

VALID_TIMEFRAMES = ("t1", "t3", "t7", "t30")


class CalibrationService:
    """Fits and applies confidence calibration curves."""

    def __init__(
        self,
        timeframe: str = "t7",
        window_days: int = 180,
        min_samples: int = 100,
        min_per_bin: int = 5,
        n_bins: int = 10,
        max_age_days: int = 30,
    ):
        if timeframe not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {VALID_TIMEFRAMES}")
        self.timeframe = timeframe
        self.window_days = window_days
        self.min_samples = min_samples
        self.min_per_bin = min_per_bin
        self.n_bins = n_bins
        self.max_age_days = max_age_days

    def fit(self) -> Optional[CalibrationCurve]:
        """Fit a calibration curve from historical prediction outcomes.

        Returns:
            CalibrationCurve ORM instance if enough data, None otherwise.
        """
        data = self._query_calibration_data()
        if len(data) < self.min_samples:
            logger.warning(
                f"Insufficient data for calibration: {len(data)} < {self.min_samples}"
            )
            return None

        confidences = [d["confidence"] for d in data]
        correct_flags = [d["correct"] for d in data]

        lookup = self._build_lookup_table(confidences, correct_flags)
        bin_stats = self._compute_bin_stats(confidences, correct_flags)

        now = datetime.now(timezone.utc)
        curve = CalibrationCurve(
            fitted_at=now,
            timeframe=self.timeframe,
            window_start=now - timedelta(days=self.window_days),
            window_end=now,
            n_predictions=len(data),
            n_bins=self.n_bins,
            bin_stats=bin_stats,
            lookup_table=lookup,
        )

        self._store_curve(curve)
        logger.info(
            f"Calibration curve fitted: {len(data)} predictions, "
            f"timeframe={self.timeframe}"
        )
        return curve

    def calibrate(self, raw_confidence: float) -> Optional[float]:
        """Apply calibration to a raw confidence score.

        Args:
            raw_confidence: LLM-reported confidence (0.0-1.0).

        Returns:
            Calibrated confidence, or None if no curve available or bin has
            insufficient data.
        """
        curve = self._load_latest_curve()
        if not curve:
            return None

        bin_idx = min(int(raw_confidence * self.n_bins), self.n_bins - 1)
        label = f"{bin_idx / self.n_bins:.1f}-{(bin_idx + 1) / self.n_bins:.1f}"
        return curve.lookup_table.get(label)

    def _query_calibration_data(self) -> list[dict]:
        """Query predictions with outcomes for calibration fitting."""
        correct_col = f"correct_{self.timeframe}"
        window_start = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        query = text(f"""
            SELECT
                p.confidence,
                po.{correct_col} as correct
            FROM predictions p
            JOIN prediction_outcomes po ON po.prediction_id = p.id
            WHERE p.analysis_status = 'completed'
                AND p.confidence IS NOT NULL
                AND po.{correct_col} IS NOT NULL
                AND p.created_at >= :window_start
        """)

        with get_session() as session:
            result = session.execute(query, {"window_start": window_start})
            return [dict(row._mapping) for row in result]

    def _build_lookup_table(
        self, confidences: list[float], correct_flags: list[bool]
    ) -> dict[str, float | None]:
        """Build bin-based calibration lookup table."""
        bins: dict[str, dict[str, int]] = {}
        for conf, correct in zip(confidences, correct_flags):
            bin_idx = min(int(conf * self.n_bins), self.n_bins - 1)
            label = f"{bin_idx / self.n_bins:.1f}-{(bin_idx + 1) / self.n_bins:.1f}"
            if label not in bins:
                bins[label] = {"total": 0, "correct": 0}
            bins[label]["total"] += 1
            if correct:
                bins[label]["correct"] += 1

        return {
            label: round(data["correct"] / data["total"], 4)
            if data["total"] >= self.min_per_bin
            else None
            for label, data in sorted(bins.items())
        }

    def _compute_bin_stats(
        self, confidences: list[float], correct_flags: list[bool]
    ) -> list[dict]:
        """Compute detailed per-bin statistics."""
        bins: dict[int, dict[str, int]] = {}
        for conf, correct in zip(confidences, correct_flags):
            bin_idx = min(int(conf * self.n_bins), self.n_bins - 1)
            if bin_idx not in bins:
                bins[bin_idx] = {"total": 0, "correct": 0}
            bins[bin_idx]["total"] += 1
            if correct:
                bins[bin_idx]["correct"] += 1

        stats = []
        for i in range(self.n_bins):
            data = bins.get(i, {"total": 0, "correct": 0})
            total = data["total"]
            n_correct = data["correct"]
            accuracy = round(n_correct / total, 4) if total > 0 else None
            stats.append({
                "bin_label": f"{i / self.n_bins:.1f}-{(i + 1) / self.n_bins:.1f}",
                "bin_center": round((i + 0.5) / self.n_bins, 2),
                "n_total": total,
                "n_correct": n_correct,
                "accuracy": accuracy,
            })
        return stats

    def _store_curve(self, curve: CalibrationCurve) -> None:
        """Persist calibration curve to database."""
        with get_session() as session:
            session.add(curve)

    def _load_latest_curve(self) -> Optional[CalibrationCurve]:
        """Load the most recently fitted calibration curve.

        Returns None if no curve exists or the latest curve is older
        than max_age_days (staleness guard).
        """
        with get_session() as session:
            curve = (
                session.query(CalibrationCurve)
                .filter(CalibrationCurve.timeframe == self.timeframe)
                .order_by(CalibrationCurve.fitted_at.desc())
                .first()
            )
            if not curve:
                return None

            age = datetime.now(timezone.utc) - curve.fitted_at.replace(
                tzinfo=timezone.utc
            )
            if age > timedelta(days=self.max_age_days):
                logger.warning(
                    f"Calibration curve is stale ({age.days} days old > "
                    f"{self.max_age_days} max). Falling back to raw confidence."
                )
                return None

            # Detach from session so it can be used after session closes
            session.expunge(curve)
            return curve


def refit_all(timeframes: list[str] | None = None) -> dict[str, int]:
    """Refit calibration curves for all (or specified) timeframes.

    Returns:
        Dict mapping timeframe to n_predictions fitted, or 0 if insufficient data.
    """
    if timeframes is None:
        timeframes = list(VALID_TIMEFRAMES)

    results = {}
    for tf in timeframes:
        svc = CalibrationService(timeframe=tf)
        curve = svc.fit()
        results[tf] = curve.n_predictions if curve else 0

    return results


def main() -> None:
    """CLI entry point for calibration refit."""
    import argparse
    from shit.logging import setup_cli_logging

    parser = argparse.ArgumentParser(
        prog="python -m shit.market_data.calibration",
        description="Fit confidence calibration curves from historical outcomes",
    )
    parser.add_argument(
        "--refit",
        action="store_true",
        required=True,
        help="Refit calibration curves",
    )
    parser.add_argument(
        "--timeframe",
        choices=VALID_TIMEFRAMES,
        default=None,
        help="Single timeframe to refit (default: all)",
    )
    args = parser.parse_args()

    setup_cli_logging(verbose=True)

    timeframes = [args.timeframe] if args.timeframe else None
    results = refit_all(timeframes)

    for tf, n in results.items():
        if n > 0:
            logger.info(f"  {tf}: fitted from {n} predictions")
        else:
            logger.warning(f"  {tf}: insufficient data")


if __name__ == "__main__":
    main()
