"""Calibration curve API endpoint."""

from fastapi import APIRouter, HTTPException, Query

from api.schemas.calibration import CalibrationCurveResponse

router = APIRouter()


@router.get("/curve", response_model=CalibrationCurveResponse)
def get_calibration_curve(
    timeframe: str = Query("t7", pattern="^t(1|3|7|30)$"),
):
    """Get the latest calibration curve for a given timeframe."""
    from shit.market_data.calibration import CalibrationService

    svc = CalibrationService(timeframe=timeframe)
    curve = svc._load_latest_curve()
    if not curve:
        raise HTTPException(404, "No calibration curve available")

    return CalibrationCurveResponse(
        fitted_at=curve.fitted_at.isoformat(),
        timeframe=curve.timeframe,
        n_predictions=curve.n_predictions,
        n_bins=curve.n_bins,
        bin_stats=curve.bin_stats,
        lookup_table=curve.lookup_table,
    )
