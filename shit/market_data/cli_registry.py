"""
Market Data CLI — Ticker Registry Commands

Commands for managing the ticker registry.
"""

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command(name="ticker-registry")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["active", "inactive", "invalid", "all"]),
    default="all",
    help="Filter by ticker status",
)
def ticker_registry_cmd(status: str):
    """Show all tracked tickers in the registry."""
    from shit.market_data.ticker_registry import TickerRegistryService
    from shit.market_data.models import TickerRegistry

    try:
        service = TickerRegistryService()
        stats = service.get_registry_stats()

        rprint("\n[bold]Ticker Registry Stats:[/bold]")
        rprint(f"  Total: {stats['total']}")
        rprint(f"  Active: [green]{stats['active']}[/green]")
        rprint(f"  Invalid: [red]{stats['invalid']}[/red]")
        rprint(f"  Inactive: [yellow]{stats['inactive']}[/yellow]")

        with get_session() as session:
            query = session.query(TickerRegistry)
            if status != "all":
                query = query.filter(TickerRegistry.status == status)
            query = query.order_by(TickerRegistry.first_seen_date.desc())
            tickers = query.all()

            if not tickers:
                print_info("No tickers found matching filter")
                return

            table = Table(title=f"Ticker Registry ({status})")
            table.add_column("Symbol", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("First Seen", style="yellow")
            table.add_column("Last Update", style="white")
            table.add_column("Records", style="magenta", justify="right")

            for t in tickers:
                table.add_row(
                    t.symbol,
                    t.status,
                    str(t.first_seen_date),
                    str(t.last_price_update.date()) if t.last_price_update else "Never",
                    str(t.total_price_records),
                )

            console.print(table)

    except Exception as e:
        print_error(f"Error reading ticker registry: {e}")
        raise click.Abort()


@click.command(name="register-tickers")
@click.argument("symbols", nargs=-1, required=True)
def register_tickers_cmd(symbols: tuple):
    """Manually register tickers for tracking (e.g., register-tickers AAPL TSLA BTC-USD)."""
    from shit.market_data.ticker_registry import TickerRegistryService

    try:
        service = TickerRegistryService()
        newly_registered, already_known = service.register_tickers(list(symbols))

        if newly_registered:
            print_success(
                f"Registered {len(newly_registered)} new tickers: {', '.join(newly_registered)}"
            )
        if already_known:
            print_info(f"Already registered: {', '.join(already_known)}")

    except Exception as e:
        print_error(f"Error registering tickers: {e}")
        raise click.Abort()
