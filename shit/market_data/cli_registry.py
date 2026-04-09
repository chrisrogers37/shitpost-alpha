"""
Market Data CLI — Ticker Registry Commands

Commands for managing the ticker registry, including retroactive
cleanup of historical predictions (remap aliases, remove concepts).
"""

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from sqlalchemy import text

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


@click.command(name="remap-tickers")
@click.option("--dry-run", is_flag=True, help="Show what would change without modifying data")
def remap_tickers_cmd(dry_run: bool):
    """Remap historical predictions with delisted/renamed tickers using ALIASES.

    Updates predictions.assets and predictions.market_impact for tickers
    that have a known replacement (e.g., RTN→RTX, FB→META).
    """
    from shit.market_data.ticker_validator import TickerValidator

    aliases_with_replacement = {
        old: new for old, new in TickerValidator.ALIASES.items() if new is not None
    }

    if not aliases_with_replacement:
        print_info("No aliases with replacements configured")
        return

    try:
        total_remapped = 0
        with get_session() as session:
            for old_symbol, new_symbol in aliases_with_replacement.items():
                # Count affected predictions
                result = session.execute(
                    text(
                        "SELECT COUNT(*) FROM predictions "
                        "WHERE assets::text LIKE :pattern"
                    ),
                    {"pattern": f'%"{old_symbol}"%'},
                )
                count = result.scalar()

                if count == 0:
                    continue

                if dry_run:
                    rprint(
                        f"  [yellow]Would remap[/yellow] {old_symbol} → {new_symbol}: "
                        f"[bold]{count}[/bold] predictions"
                    )
                else:
                    # Update assets array
                    session.execute(
                        text("""
                            UPDATE predictions
                            SET assets = (
                                SELECT jsonb_agg(
                                    CASE WHEN elem = :old THEN :new ELSE elem END
                                )
                                FROM jsonb_array_elements_text(assets::jsonb) AS elem
                            )::json
                            WHERE assets::text LIKE :pattern
                        """),
                        {"old": old_symbol, "new": new_symbol, "pattern": f'%"{old_symbol}"%'},
                    )
                    # Update market_impact keys
                    session.execute(
                        text("""
                            UPDATE predictions
                            SET market_impact = (
                                market_impact::jsonb - :old
                                || jsonb_build_object(:new, market_impact::jsonb -> :old)
                            )::json
                            WHERE market_impact::text LIKE :pattern
                        """),
                        {"old": old_symbol, "new": new_symbol, "pattern": f'%"{old_symbol}"%'},
                    )
                    rprint(
                        f"  [green]Remapped[/green] {old_symbol} → {new_symbol}: "
                        f"[bold]{count}[/bold] predictions"
                    )
                total_remapped += count

            if not dry_run:
                session.commit()

        if total_remapped == 0:
            print_info("No predictions to remap")
        elif dry_run:
            rprint(f"\n[yellow]Dry run:[/yellow] {total_remapped} predictions would be remapped")
        else:
            print_success(f"Remapped {total_remapped} predictions")

    except Exception as e:
        print_error(f"Error remapping tickers: {e}")
        raise click.Abort()


@click.command(name="clean-concept-tickers")
@click.option("--dry-run", is_flag=True, help="Show what would change without modifying data")
def clean_concept_tickers_cmd(dry_run: bool):
    """Remove non-ticker concepts (DEFENSE, CRYPTO, etc.) from historical predictions.

    Removes concept strings from predictions.assets arrays and
    predictions.market_impact dicts.
    """
    from shit.market_data.ticker_validator import TickerValidator

    concepts = sorted(TickerValidator.BLOCKLIST)

    try:
        total_cleaned = 0
        with get_session() as session:
            for concept in concepts:
                # Count affected predictions
                result = session.execute(
                    text(
                        "SELECT COUNT(*) FROM predictions "
                        "WHERE assets::text LIKE :pattern"
                    ),
                    {"pattern": f'%"{concept}"%'},
                )
                count = result.scalar()

                if count == 0:
                    continue

                if dry_run:
                    rprint(
                        f"  [yellow]Would remove[/yellow] {concept}: "
                        f"[bold]{count}[/bold] predictions"
                    )
                else:
                    # Remove from assets array
                    session.execute(
                        text("""
                            UPDATE predictions
                            SET assets = (
                                SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                                FROM jsonb_array_elements_text(assets::jsonb) AS elem
                                WHERE elem != :concept
                            )::json
                            WHERE assets::text LIKE :pattern
                        """),
                        {"concept": concept, "pattern": f'%"{concept}"%'},
                    )
                    # Remove from market_impact
                    session.execute(
                        text("""
                            UPDATE predictions
                            SET market_impact = (market_impact::jsonb - :concept)::json
                            WHERE market_impact::text LIKE :pattern
                        """),
                        {"concept": concept, "pattern": f'%"{concept}"%'},
                    )
                    rprint(
                        f"  [green]Removed[/green] {concept}: "
                        f"[bold]{count}[/bold] predictions"
                    )
                total_cleaned += count

            if not dry_run:
                session.commit()

        if total_cleaned == 0:
            print_info("No concept tickers found in predictions")
        elif dry_run:
            rprint(f"\n[yellow]Dry run:[/yellow] {total_cleaned} predictions would be cleaned")
        else:
            print_success(f"Cleaned {total_cleaned} predictions")

    except Exception as e:
        print_error(f"Error cleaning concept tickers: {e}")
        raise click.Abort()
