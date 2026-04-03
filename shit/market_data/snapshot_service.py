"""
Price Snapshot Service

Captures live market prices for tickers at prediction creation time.
Each snapshot records the exact price at the moment the system becomes
aware of relevant assets — the most precise price reference available.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from shit.logging import get_service_logger
from shit.market_data.market_timing import classify_market_status
from shit.market_data.models import PriceSnapshot
from shit.market_data.yfinance_provider import LiveQuote, fetch_live_quote

logger = get_service_logger("snapshot_service")


class PriceSnapshotService:
    """Captures and stores live price snapshots for prediction assets."""

    def capture_for_prediction(
        self,
        session: Session,
        prediction_id: int,
        assets: list[str],
        post_published_at: Optional[datetime] = None,
    ) -> list[PriceSnapshot]:
        """Capture live price snapshots for all assets in a prediction.

        For each asset, fetches the current price via yfinance fast_info
        and stores a PriceSnapshot row. Failures for individual tickers
        are logged but do not block other captures.

        Args:
            session: SQLAlchemy session for database writes.
            prediction_id: The prediction these snapshots belong to.
            assets: List of ticker symbols to capture.
            post_published_at: When the original post was published.

        Returns:
            List of successfully created PriceSnapshot instances.
        """
        if not assets:
            return []

        now = datetime.now(timezone.utc)
        market_status = classify_market_status(now)
        snapshots: list[PriceSnapshot] = []

        # Batch check for existing snapshots (avoid N+1)
        existing_symbols = {
            row.symbol
            for row in session.query(PriceSnapshot.symbol)
            .filter(
                PriceSnapshot.prediction_id == prediction_id,
                PriceSnapshot.symbol.in_(assets),
            )
            .all()
        }

        for symbol in assets:
            if symbol in existing_symbols:
                logger.debug(
                    f"Snapshot already exists for {symbol} "
                    f"prediction {prediction_id}"
                )
                continue
            try:
                snapshot = self._capture_single(
                    session=session,
                    prediction_id=prediction_id,
                    symbol=symbol,
                    post_published_at=post_published_at,
                    market_status=market_status,
                )
                if snapshot:
                    snapshots.append(snapshot)
            except Exception as e:
                logger.warning(
                    f"Failed to capture snapshot for {symbol}: {e}",
                    extra={
                        "prediction_id": prediction_id,
                        "symbol": symbol,
                    },
                )

        if snapshots:
            logger.info(
                f"Captured {len(snapshots)}/{len(assets)} price snapshots "
                f"for prediction {prediction_id}",
                extra={
                    "prediction_id": prediction_id,
                    "captured": len(snapshots),
                    "total": len(assets),
                    "market_status": market_status,
                },
            )

        return snapshots

    def _capture_single(
        self,
        session: Session,
        prediction_id: int,
        symbol: str,
        post_published_at: Optional[datetime],
        market_status: str,
    ) -> Optional[PriceSnapshot]:
        """Capture a single price snapshot for one symbol."""
        quote: Optional[LiveQuote] = fetch_live_quote(symbol)
        if quote is None:
            logger.debug(f"No live quote available for {symbol}")
            return None

        snapshot = PriceSnapshot(
            prediction_id=prediction_id,
            symbol=symbol,
            price=quote.price,
            captured_at=quote.captured_at,
            post_published_at=post_published_at,
            source=quote.source,
            market_status=market_status,
            previous_close=quote.previous_close,
            day_high=quote.day_high,
            day_low=quote.day_low,
            volume=quote.volume,
        )
        session.add(snapshot)
        session.flush()

        logger.debug(
            f"Captured {symbol} @ ${quote.price:.2f} "
            f"({market_status})",
            extra={
                "prediction_id": prediction_id,
                "symbol": symbol,
                "price": quote.price,
            },
        )
        return snapshot
