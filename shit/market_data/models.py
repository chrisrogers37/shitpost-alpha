"""
Market Data Models
SQLAlchemy models for tracking stock prices and prediction outcomes.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    Date,
    DateTime,
    Float,
    BigInteger,
    ForeignKey,
    Integer,
    Boolean,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from shit.db.data_models import Base, TimestampMixin, IDMixin


class MarketPrice(Base, IDMixin, TimestampMixin):
    """Model for storing historical stock/asset prices from market data APIs."""

    __tablename__ = "market_prices"

    # Asset identification
    symbol = Column(
        String(20), nullable=False, index=True
    )  # Ticker symbol (AAPL, TSLA, BTC-USD, etc.)
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
    last_updated = Column(
        DateTime, default=datetime.utcnow
    )  # When this data was fetched

    # Metadata
    is_market_open = Column(Boolean, default=True)  # Was market open this day?
    has_split = Column(Boolean, default=False)  # Did a stock split occur?
    has_dividend = Column(Boolean, default=False)  # Was dividend paid?

    def __repr__(self):
        return f"<MarketPrice(symbol='{self.symbol}', date={self.date}, close=${self.close})>"

    # Unique constraint on symbol + date (one price record per symbol per day)
    __table_args__ = ({"sqlite_autoincrement": True},)


class PredictionOutcome(Base, IDMixin, TimestampMixin):
    """Model for tracking actual outcomes of predictions with detailed metrics."""

    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "prediction_id", "symbol",
            name="uq_prediction_outcomes_pred_symbol",
        ),
        CheckConstraint(
            "prediction_sentiment IN ('bullish', 'bearish', 'neutral') OR prediction_sentiment IS NULL",
            name="ck_prediction_outcomes_sentiment",
        ),
    )

    # Link to prediction
    prediction_id = Column(
        Integer, ForeignKey("predictions.id"), nullable=False, index=True
    )

    # Asset being tracked
    symbol = Column(String(20), nullable=False, index=True)  # Ticker symbol

    # Prediction details (denormalized for easier querying)
    prediction_date = Column(
        Date, nullable=False, index=True
    )  # When prediction was made
    prediction_sentiment = Column(
        String(20), nullable=True
    )  # bullish, bearish, neutral
    prediction_confidence = Column(Float, nullable=True)  # 0.0-1.0
    prediction_timeframe_days = Column(Integer, nullable=True)  # Expected timeframe

    # Post publication timestamp (full datetime for intraday calculations)
    post_published_at = Column(DateTime, nullable=True)

    # Price at prediction time (daily close)
    price_at_prediction = Column(Float, nullable=True)  # Price when prediction was made

    # Intraday snapshot prices (captured once at prediction creation)
    price_at_post = Column(Float, nullable=True)  # Price when post was published
    price_at_next_close = Column(Float, nullable=True)  # Next market close after post
    price_1h_after = Column(Float, nullable=True)  # 1 hour after post

    # Outcomes at different timeframes (T+N days)
    price_t1 = Column(Float, nullable=True)  # Price after 1 day
    price_t3 = Column(Float, nullable=True)  # Price after 3 days
    price_t7 = Column(Float, nullable=True)  # Price after 7 days
    price_t30 = Column(Float, nullable=True)  # Price after 30 days

    # Returns (percentage change) -- daily timeframes (trading days)
    return_t1 = Column(Float, nullable=True)  # T+1 trading day
    return_t3 = Column(Float, nullable=True)  # T+3 trading days
    return_t7 = Column(Float, nullable=True)  # T+7 trading days
    return_t30 = Column(Float, nullable=True)  # T+30 trading days

    # Returns -- intraday timeframes
    return_same_day = Column(
        Float, nullable=True
    )  # price_at_post -> price_at_next_close
    return_1h = Column(Float, nullable=True)  # price_at_post -> price_1h_after

    # Accuracy validation -- daily timeframes
    correct_t1 = Column(Boolean, nullable=True)
    correct_t3 = Column(Boolean, nullable=True)
    correct_t7 = Column(Boolean, nullable=True)
    correct_t30 = Column(Boolean, nullable=True)

    # Accuracy -- intraday timeframes
    correct_same_day = Column(Boolean, nullable=True)
    correct_1h = Column(Boolean, nullable=True)

    # Profit/Loss simulation ($1000 position) -- daily
    pnl_t1 = Column(Float, nullable=True)
    pnl_t3 = Column(Float, nullable=True)
    pnl_t7 = Column(Float, nullable=True)
    pnl_t30 = Column(Float, nullable=True)

    # P&L -- intraday
    pnl_same_day = Column(Float, nullable=True)
    pnl_1h = Column(Float, nullable=True)

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

    def calculate_return(
        self, price_initial: float, price_final: Optional[float]
    ) -> Optional[float]:
        """Calculate percentage return between two prices."""
        if price_initial is None or price_final is None or price_initial == 0:
            return None
        return ((price_final - price_initial) / price_initial) * 100

    def calculate_pnl(
        self, return_pct: Optional[float], position_size: float = 1000.0
    ) -> Optional[float]:
        """Calculate P&L for a given return percentage and position size."""
        if return_pct is None:
            return None
        return (return_pct / 100) * position_size

    def is_correct(
        self, sentiment: str, return_pct: Optional[float], threshold: float = 0.5
    ) -> Optional[bool]:
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

        if sentiment == "bullish":
            return return_pct > threshold
        elif sentiment == "bearish":
            return return_pct < -threshold
        elif sentiment == "neutral":
            return abs(return_pct) <= threshold
        else:
            return None


class PriceSnapshot(Base, IDMixin, TimestampMixin):
    """Point-in-time price capture for tickers at prediction creation.

    Captures the live market price for each ticker immediately when
    a prediction is created, providing the most precise price reference
    tied to the moment the system becomes aware of relevant assets.
    """

    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "prediction_id", "symbol",
            name="uq_price_snapshot_pred_symbol",
        ),
        CheckConstraint("price > 0", name="ck_price_snapshot_positive"),
    )

    # Linkage
    prediction_id = Column(
        Integer, ForeignKey("predictions.id"), nullable=False, index=True
    )
    symbol = Column(String(20), nullable=False)

    # Captured price data
    price = Column(Float, nullable=False)
    captured_at = Column(DateTime, nullable=False)
    post_published_at = Column(DateTime, nullable=True)

    # Source and context
    source = Column(String(50), default="yfinance_fast_info")
    market_status = Column(String(20), nullable=True)

    # Additional market data at capture time
    previous_close = Column(Float, nullable=True)
    day_high = Column(Float, nullable=True)
    day_low = Column(Float, nullable=True)
    volume = Column(BigInteger, nullable=True)

    def __repr__(self):
        return (
            f"<PriceSnapshot(symbol='{self.symbol}', "
            f"price=${self.price}, captured={self.captured_at})>"
        )


class TickerRegistry(Base, IDMixin, TimestampMixin):
    """Registry of all ticker symbols the system tracks.

    Once a ticker appears in an LLM prediction, it is registered here
    and tracked for ongoing price updates. This provides:
    - Instant lookup of whether a ticker is already known
    - Status tracking (active, inactive, invalid)
    - Audit trail of when each ticker was first seen
    - Source prediction linkage for debugging
    - Company fundamental data from yfinance
    """

    __tablename__ = "ticker_registry"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'invalid')",
            name="ck_ticker_registry_status",
        ),
    )

    # Ticker identification
    symbol = Column(String(20), unique=True, nullable=False, index=True)

    # Lifecycle tracking
    first_seen_date = Column(Date, nullable=False, index=True)
    source_prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)

    # Status: active (tracked), inactive (manually disabled), invalid (yfinance can't find it)
    status = Column(String(20), nullable=False, default="active", index=True)
    status_reason = Column(String(255), nullable=True)

    # Price data tracking
    last_price_update = Column(DateTime, nullable=True)
    price_data_start = Column(Date, nullable=True)
    price_data_end = Column(Date, nullable=True)
    total_price_records = Column(Integer, default=0)

    # Metadata
    asset_type = Column(
        String(20), nullable=True
    )  # stock, crypto, etf, commodity, index
    exchange = Column(String(20), nullable=True)  # NYSE, NASDAQ, etc.

    # Company fundamentals (populated by FundamentalsProvider)
    company_name = Column(String(255), nullable=True)  # e.g. "Apple Inc."
    sector = Column(String(100), nullable=True)  # e.g. "Technology"
    industry = Column(String(100), nullable=True)  # e.g. "Consumer Electronics"
    market_cap = Column(BigInteger, nullable=True)  # Market capitalization in USD
    pe_ratio = Column(Float, nullable=True)  # Trailing P/E ratio
    forward_pe = Column(Float, nullable=True)  # Forward P/E ratio
    dividend_yield = Column(Float, nullable=True)  # Dividend yield (0.0-1.0)
    beta = Column(Float, nullable=True)  # Beta coefficient
    description = Column(Text, nullable=True)  # Short business summary
    fundamentals_updated_at = Column(
        DateTime, nullable=True
    )  # Last fundamentals refresh

    def __repr__(self):
        name_part = f" ({self.company_name})" if self.company_name else ""
        return f"<TickerRegistry(symbol='{self.symbol}'{name_part}, status='{self.status}')>"


# Indexes for efficient querying
from sqlalchemy import Index

# Create composite indexes for common queries
Index("idx_market_price_symbol_date", MarketPrice.symbol, MarketPrice.date, unique=True)
Index(
    "idx_prediction_outcome_symbol_date",
    PredictionOutcome.symbol,
    PredictionOutcome.prediction_date,
)
Index("idx_prediction_outcome_prediction_id", PredictionOutcome.prediction_id)
Index("idx_ticker_registry_symbol", TickerRegistry.symbol, unique=True)
Index("idx_ticker_registry_status", TickerRegistry.status)
Index("idx_ticker_registry_sector", TickerRegistry.sector)
Index(
    "idx_price_snapshot_symbol_captured",
    PriceSnapshot.symbol,
    PriceSnapshot.captured_at,
)
