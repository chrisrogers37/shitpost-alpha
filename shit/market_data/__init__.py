"""
Market Data Module
Fetches stock prices and calculates prediction outcomes.
"""

from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.health import run_health_check, HealthReport

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "run_health_check",
    "HealthReport",
]
