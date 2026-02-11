"""
Market Data Module
Fetches stock prices and calculates prediction outcomes.
"""

from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
]
