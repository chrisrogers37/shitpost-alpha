"""
Market Data Models
SQLAlchemy models for tracking stock prices and prediction outcomes.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, String, Date, DateTime, Float, BigInteger, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship
from decimal import Decimal

from shit.db.data_models import Base, TimestampMixin, IDMixin


class MarketPrice(Base, IDMixin, TimestampMixin):
    """Model for storing historical stock/asset prices from market data APIs."""

    __tablename__ = "market_prices"

    # Asset identification
    symbol = Column(String(20), nullable=False, index=True)  # Ticker symbol (AAPL, TSLA, BTC-USD, etc.)
    date = Column(Date, nullable=False, index=True)  # Trading date

    # OHLCV data (Open, High, Low, Close, Volume)
    open = Column(Float, nullable=True)  # Opening price
    high = Column(Float, nullable=True)  # Highest price
    low = Column(Float, nullable=True)  # Lowest price
    close = Column(Float, nullable=False)  # Closing price
    volume = Column(BigInteger, nullable=True)  # Trading volume

    # Adjusted close for splits/dividends
    adjusted_close = Column(Float, nullable=True)  # Adjusted closing price

    # Data source tracking
    source = Column(String(50), default="yfinance")  # yfinance, alpha_vantage, etc.
    last_updated = Column(DateTime, default=datetime.utcnow)  # When this data was fetched

    # Metadata
    is_market_open = Column(Boolean, default=True)  # Was market open this day?
    has_split = Column(Boolean, default=False)  # Did a stock split occur?
    has_dividend = Column(Boolean, default=False)  # Was dividend paid?

    def __repr__(self):
        return f"<MarketPrice(symbol='{self.symbol}', date={self.date}, close=${self.close})>"

    # Unique constraint on symbol + date (one price record per symbol per day)
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class PredictionOutcome(Base, IDMixin, TimestampMixin):
    """Model for tracking actual outcomes of predictions with detailed metrics."""

    __tablename__ = "prediction_outcomes"

    # Link to prediction
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)

    # Asset being tracked
    symbol = Column(String(20), nullable=False, index=True)  # Ticker symbol

    # Prediction details (denormalized for easier querying)
    prediction_date = Column(Date, nullable=False, index=True)  # When prediction was made
    prediction_sentiment = Column(String(20), nullable=True)  # bullish, bearish, neutral
    prediction_confidence = Column(Float, nullable=True)  # 0.0-1.0
    prediction_timeframe_days = Column(Integer, nullable=True)  # Expected timeframe

    # Price at prediction time
    price_at_prediction = Column(Float, nullable=True)  # Price when prediction was made

    # Outcomes at different timeframes (T+N days)
    price_t1 = Column(Float, nullable=True)  # Price after 1 day
    price_t3 = Column(Float, nullable=True)  # Price after 3 days
    price_t7 = Column(Float, nullable=True)  # Price after 7 days
    price_t30 = Column(Float, nullable=True)  # Price after 30 days

    # Returns (percentage change)
    return_t1 = Column(Float, nullable=True)  # % change after 1 day
    return_t3 = Column(Float, nullable=True)  # % change after 3 days
    return_t7 = Column(Float, nullable=True)  # % change after 7 days
    return_t30 = Column(Float, nullable=True)  # % change after 30 days

    # Accuracy validation (was prediction correct?)
    correct_t1 = Column(Boolean, nullable=True)  # Correct at T+1?
    correct_t3 = Column(Boolean, nullable=True)  # Correct at T+3?
    correct_t7 = Column(Boolean, nullable=True)  # Correct at T+7?
    correct_t30 = Column(Boolean, nullable=True)  # Correct at T+30?

    # Profit/Loss simulation (assuming $1000 position)
    pnl_t1 = Column(Float, nullable=True)  # P&L after 1 day
    pnl_t3 = Column(Float, nullable=True)  # P&L after 3 days
    pnl_t7 = Column(Float, nullable=True)  # P&L after 7 days
    pnl_t30 = Column(Float, nullable=True)  # P&L after 30 days

    # Market context (for better analysis)
    market_volatility = Column(Float, nullable=True)  # VIX or calculated volatility
    sector = Column(String(50), nullable=True)  # Technology, Finance, etc.

    # Tracking metadata
    last_price_update = Column(DateTime, nullable=True)  # When prices were last fetched
    is_complete = Column(Boolean, default=False)  # All timeframes tracked?
    notes = Column(Text, nullable=True)  # Any special notes (splits, dividends, etc.)

    # Relationships
    # prediction = relationship("Prediction", foreign_keys=[prediction_id])  # Commented out to avoid circular import

    def __repr__(self):
        return f"<PredictionOutcome(symbol='{self.symbol}', sentiment='{self.prediction_sentiment}', return_t7={self.return_t7}%)>"

    def calculate_return(self, price_initial: float, price_final: Optional[float]) -> Optional[float]:
        """Calculate percentage return between two prices."""
        if price_initial is None or price_final is None or price_initial == 0:
            return None
        return ((price_final - price_initial) / price_initial) * 100

    def calculate_pnl(self, return_pct: Optional[float], position_size: float = 1000.0) -> Optional[float]:
        """Calculate P&L for a given return percentage and position size."""
        if return_pct is None:
            return None
        return (return_pct / 100) * position_size

    def is_correct(self, sentiment: str, return_pct: Optional[float], threshold: float = 0.5) -> Optional[bool]:
        """
        Determine if prediction was correct based on sentiment and actual return.

        Args:
            sentiment: 'bullish', 'bearish', or 'neutral'
            return_pct: Actual percentage return
            threshold: Minimum % change to count as movement (default 0.5%)

        Returns:
            True if correct, False if incorrect, None if insufficient data
        """
        if return_pct is None or sentiment is None:
            return None

        sentiment = sentiment.lower()

        if sentiment == 'bullish':
            return return_pct > threshold
        elif sentiment == 'bearish':
            return return_pct < -threshold
        elif sentiment == 'neutral':
            return abs(return_pct) <= threshold
        else:
            return None


# Indexes for efficient querying
from sqlalchemy import Index

# Create composite indexes for common queries
Index('idx_market_price_symbol_date', MarketPrice.symbol, MarketPrice.date, unique=True)
Index('idx_prediction_outcome_symbol_date', PredictionOutcome.symbol, PredictionOutcome.prediction_date)
Index('idx_prediction_outcome_prediction_id', PredictionOutcome.prediction_id)
