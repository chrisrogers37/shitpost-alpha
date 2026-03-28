"""
Market Data CLI — Price Fetching Commands

Commands for fetching, backfilling, and inspecting market prices.
"""

import click
from datetime import date, timedelta
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.market_data.client import MarketDataClient
from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command()
@click.option("--symbol", "-s", required=True, help="Ticker symbol (e.g., AAPL, TSLA)")
@click.option("--days", "-d", default=30, help="Number of days of history to fetch")
@click.option("--force", "-f", is_flag=True, help="Force refresh even if data exists")
def fetch_prices(symbol: str, days: int, force: bool):
    """Fetch historical prices for a symbol."""
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()

    print_info(f"Fetching {days} days of price data for {symbol}...")

    try:
        with MarketDataClient() as client:
            prices = client.fetch_price_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                force_refresh=force,
            )

            if prices:
                print_success(f"✅ Fetched {len(prices)} prices for {symbol}")

                # Show recent prices
                table = Table(title=f"Recent Prices for {symbol}")
                table.add_column("Date", style="cyan")
                table.add_column("Close", style="green", justify="right")
                table.add_column("Volume", style="yellow", justify="right")

                for price in prices[-10:]:  # Last 10 prices
                    table.add_row(
                        str(price.date),
                        f"${price.close:.2f}",
                        f"{price.volume:,}" if price.volume else "N/A",
                    )

                console.print(table)
            else:
                print_error(f"❌ No prices found for {symbol}")

    except Exception as e:
        print_error(f"❌ Error fetching prices: {e}")
        raise click.Abort()


@click.command()
@click.option(
    "--days", "-d", default=30, help="Fetch prices for assets mentioned in last N days"
)
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def update_all_prices(days: int, limit: Optional[int]):
    """Update prices for all assets mentioned in predictions."""
    from shitvault.shitpost_models import Prediction
    from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper
    from sqlalchemy import func, distinct  # noqa: F401

    print_info(f"Finding assets mentioned in predictions (last {days} days)...")

    try:
        with get_session() as session:
            # Get unique assets from predictions
            cutoff_date = date.today() - timedelta(days=days)  # noqa: F841

            query = session.query(
                func.jsonb_array_elements_text(Prediction.assets).label("asset")
            ).distinct()

            if limit:
                query = query.limit(limit)

            # This is PostgreSQL specific - for SQLite we'll need a different approach
            try:
                assets = [row[0] for row in query.all()]
            except Exception:
                # Fallback: jsonb_array_elements_text fails when column is JSON (not JSONB)
                session.rollback()
                predictions = (
                    session.query(Prediction).filter(Prediction.assets != None).all()  # noqa: E711
                )

                if limit:
                    predictions = predictions[:limit]

                assets = set()
                for pred in predictions:
                    if pred.assets:
                        assets.update(pred.assets)
                assets = list(assets)

            if not assets:
                print_info("No assets found in predictions")
                return

            print_info(f"Found {len(assets)} unique assets: {', '.join(assets)}")

            # Update prices for each asset
            client = MarketDataClient(session=session)
            start_date = date.today() - timedelta(days=days)

            results = client.update_prices_for_symbols(
                symbols=assets, start_date=start_date
            )

            # Print results
            table = Table(title="Price Update Results")
            table.add_column("Symbol", style="cyan")
            table.add_column("Prices Fetched", style="green", justify="right")

            total_fetched = 0
            for symbol, count in sorted(results.items()):
                table.add_row(symbol, str(count))
                total_fetched += count

            console.print(table)
            print_success(f"✅ Fetched {total_fetched} total price records")

    except Exception as e:
        print_error(f"❌ Error updating prices: {e}")
        raise click.Abort()


@click.command()
@click.option("--symbol", "-s", help="Show stats for specific symbol")
def price_stats(symbol: Optional[str]):
    """Show statistics about stored price data."""
    try:
        with MarketDataClient() as client:
            if symbol:
                # Stats for specific symbol
                stats = client.get_price_stats(symbol)

                if stats["count"] == 0:
                    print_info(f"No price data found for {symbol}")
                    return

                rprint(f"\n[bold]Price Data for {symbol}:[/bold]")
                rprint(f"  Total Records: {stats['count']}")
                rprint(
                    f"  Date Range: {stats['earliest_date']} to {stats['latest_date']}"
                )
                rprint(f"  Latest Price: ${stats['latest_price']:.2f}")

            else:
                # Stats for all symbols
                from shit.market_data.models import MarketPrice
                from sqlalchemy import func

                with get_session() as session:
                    symbols = (
                        session.query(
                            MarketPrice.symbol,
                            func.count(MarketPrice.id).label("count"),
                            func.max(MarketPrice.date).label("latest_date"),
                        )
                        .group_by(MarketPrice.symbol)
                        .all()
                    )

                    if not symbols:
                        print_info("No price data found in database")
                        return

                    table = Table(title="Price Data Summary")
                    table.add_column("Symbol", style="cyan")
                    table.add_column("Records", style="green", justify="right")
                    table.add_column("Latest Date", style="yellow")

                    for symbol, count, latest_date in sorted(symbols):
                        table.add_row(symbol, str(count), str(latest_date))

                    console.print(table)
                    print_info(f"\nTotal symbols: {len(symbols)}")

    except Exception as e:
        print_error(f"❌ Error getting stats: {e}")
        raise click.Abort()


@click.command()
@click.option("--days", "-d", default=7, help="Process predictions from last N days")
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def auto_backfill(days: int, limit: Optional[int]):
    """Automatically backfill assets for recent predictions."""
    from shit.market_data.auto_backfill_service import AutoBackfillService

    print_info(f"Auto-backfilling assets for predictions from last {days} days...")

    try:
        service = AutoBackfillService()
        stats = service.process_new_predictions(days_back=days, limit=limit)

        rprint("\n[bold]Auto-Backfill Results:[/bold]")
        rprint(f"  Predictions processed: {stats['predictions_processed']}")
        rprint(f"  Assets backfilled: {stats['assets_backfilled']}")
        rprint(f"  Outcomes calculated: {stats['outcomes_calculated']}")
        rprint(f"  Errors: {stats['errors']}")

        if stats["assets_backfilled"] > 0:
            print_success(f"✅ Backfilled {stats['assets_backfilled']} assets")
        else:
            print_info("No new assets needed backfilling")

    except Exception as e:
        print_error(f"❌ Error during auto-backfill: {e}")
        raise click.Abort()


@click.command()
def backfill_all_missing():
    """One-time backfill of ALL missing assets (initial setup)."""
    from shit.market_data.auto_backfill_service import AutoBackfillService

    print_info("Starting comprehensive backfill of all missing assets...")
    print_info("This may take 10-20 minutes depending on number of assets...")

    try:
        service = AutoBackfillService()
        stats = service.process_all_missing_assets()

        rprint("\n[bold]Comprehensive Backfill Results:[/bold]")
        rprint(f"  Total unique assets: {stats['total_assets']}")
        rprint(f"  Missing assets found: {stats['missing_assets']}")
        rprint(f"  Successfully backfilled: {stats['backfilled']}")
        rprint(f"  Failed: {stats['failed']}")

        success_rate = (
            (stats["backfilled"] / stats["missing_assets"] * 100)
            if stats["missing_assets"] > 0
            else 0
        )
        rprint(f"\n  [bold magenta]Success Rate: {success_rate:.1f}%[/bold magenta]")

        if stats["backfilled"] > 0:
            print_success(f"✅ Backfilled {stats['backfilled']} assets")

            # Suggest next step
            print_info("\nNext step: Calculate outcomes for all predictions")
            print_info("Run: python -m shit.market_data calculate-outcomes --days 365")
        else:
            print_info("No assets needed backfilling")

    except Exception as e:
        print_error(f"❌ Error during backfill: {e}")
        raise click.Abort()
