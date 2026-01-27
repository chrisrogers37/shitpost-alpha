"""
Market Data Backfill Script
Intelligently backfills price data for all assets mentioned in predictions.
"""

from datetime import date, timedelta
from typing import List, Set
from shit.market_data.client import MarketDataClient
from shit.db.sync_session import get_session
from shitvault.shitpost_models import Prediction
from shit.logging import print_success, print_error, print_info
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


def get_all_prediction_assets(days_back: int = None) -> List[str]:
    """
    Extract all unique assets mentioned in predictions.

    Args:
        days_back: Only look at predictions from last N days (None = all time)

    Returns:
        List of unique ticker symbols
    """
    with get_session() as session:
        query = session.query(Prediction).filter(
            Prediction.assets != None,
            Prediction.analysis_status == 'completed'
        )

        if days_back:
            cutoff_date = date.today() - timedelta(days=days_back)
            query = query.filter(Prediction.created_at >= cutoff_date)

        predictions = query.all()

        assets: Set[str] = set()
        for pred in predictions:
            if pred.assets and isinstance(pred.assets, list):
                assets.update(pred.assets)

        # Filter out invalid symbols
        valid_assets = []
        for asset in sorted(assets):
            # Skip Korean exchange symbols (yfinance doesn't support well)
            if asset.startswith('KRX:'):
                continue
            # Skip if asset looks invalid
            if not asset or len(asset) > 10 or ' ' in asset:
                continue
            valid_assets.append(asset)

        return valid_assets


def get_earliest_prediction_date() -> date:
    """Get the earliest prediction date to determine backfill range."""
    with get_session() as session:
        earliest = session.query(Prediction).filter(
            Prediction.created_at != None
        ).order_by(Prediction.created_at.asc()).first()

        if earliest and earliest.created_at:
            return earliest.created_at.date()
        return date.today() - timedelta(days=365)


def backfill_all_prediction_assets(
    days_back: int = None,
    force_refresh: bool = False,
    batch_size: int = 10
):
    """
    Backfill price data for all assets mentioned in predictions.

    Args:
        days_back: How far back to fetch prices (None = from earliest prediction)
        force_refresh: Re-fetch even if data exists
        batch_size: Process N assets at a time
    """
    print_info("Starting market data backfill...")

    # Get list of assets to backfill
    assets = get_all_prediction_assets()
    print_info(f"Found {len(assets)} unique assets to backfill")

    if not assets:
        print_info("No assets to backfill!")
        return

    # Determine date range
    if days_back:
        start_date = date.today() - timedelta(days=days_back)
    else:
        start_date = get_earliest_prediction_date()

    end_date = date.today()

    print_info(f"Fetching prices from {start_date} to {end_date}")
    print_info(f"Assets to process: {', '.join(assets[:10])}{'...' if len(assets) > 10 else ''}")

    # Process with progress bar
    success_count = 0
    error_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task(f"Backfilling {len(assets)} assets...", total=len(assets))

        with MarketDataClient() as client:
            for i, symbol in enumerate(assets):
                try:
                    progress.update(task, description=f"Fetching {symbol} ({i+1}/{len(assets)})")

                    prices = client.fetch_price_history(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        force_refresh=force_refresh
                    )

                    if len(prices) > 0:
                        success_count += 1
                        print_info(f"  ✓ {symbol}: {len(prices)} prices")
                    else:
                        skipped_count += 1
                        print_info(f"  ⊘ {symbol}: No data available")

                except Exception as e:
                    error_count += 1
                    print_error(f"  ✗ {symbol}: {str(e)[:50]}")

                progress.update(task, advance=1)

    # Summary
    print_success(f"\n✅ Backfill complete!")
    print_info(f"  Success: {success_count}")
    print_info(f"  Skipped: {skipped_count}")
    print_info(f"  Errors: {error_count}")
    print_info(f"  Total: {len(assets)}")


if __name__ == "__main__":
    import sys

    # Simple CLI
    force = "--force" in sys.argv

    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        days = int(sys.argv[idx + 1])
        backfill_all_prediction_assets(days_back=days, force_refresh=force)
    else:
        # Backfill from earliest prediction to today
        backfill_all_prediction_assets(force_refresh=force)
