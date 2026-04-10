"""Pydantic response models for the calibration API."""

from pydantic import BaseModel
from typing import Optional


class BinStat(BaseModel):
    bin_label: str
    bin_center: float
    n_total: int
    n_correct: int
    accuracy: Optional[float] = None


class CalibrationCurveResponse(BaseModel):
    fitted_at: str
    timeframe: str
    n_predictions: int
    n_bins: int
    bin_stats: list[BinStat]
    lookup_table: dict[str, Optional[float]]
