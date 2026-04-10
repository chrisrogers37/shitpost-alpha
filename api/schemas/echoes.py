"""Pydantic response models for the Historical Echoes API."""

from pydantic import BaseModel
from typing import Any, Optional


class EchoOutcome(BaseModel):
    symbol: str
    return_value: Optional[float] = None
    correct: Optional[bool] = None


class EchoMatch(BaseModel):
    prediction_id: int
    similarity: float
    assets: list[Any]
    thesis: str
    post_timestamp: Optional[str] = None
    outcomes: list[EchoOutcome]


class EchoResponse(BaseModel):
    count: int
    timeframe: str
    avg_return: Optional[float] = None
    median_return: Optional[float] = None
    win_rate: Optional[float] = None
    correct: int = 0
    incorrect: int = 0
    pending: int = 0
    avg_pnl: Optional[float] = None
    matches: list[EchoMatch]
