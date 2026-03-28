"""
Market Data CLI

Command-line interface for market data operations.

Commands are organized into submodules:
- cli_fetch.py — Price fetching, backfilling, and stats
- cli_outcomes.py — Outcome calculation, maturation, accuracy, health, pipeline
- cli_registry.py — Ticker registry management
"""

import click

from shit.market_data.cli_fetch import (
    fetch_prices,
    update_all_prices,
    price_stats,
    auto_backfill,
    backfill_all_missing,
)
from shit.market_data.cli_outcomes import (
    calculate_outcomes,
    fix_sentiments,
    mature_outcomes,
    accuracy_report,
    health_check,
    auto_pipeline,
)
from shit.market_data.cli_registry import (
    ticker_registry_cmd,
    register_tickers_cmd,
)


@click.group()
def cli():
    """Market data commands for tracking prices and prediction outcomes."""
    pass


# Price fetching commands
cli.add_command(fetch_prices)
cli.add_command(update_all_prices)
cli.add_command(price_stats)
cli.add_command(auto_backfill)
cli.add_command(backfill_all_missing)

# Outcome commands
cli.add_command(calculate_outcomes)
cli.add_command(fix_sentiments)
cli.add_command(mature_outcomes)
cli.add_command(accuracy_report)
cli.add_command(health_check)
cli.add_command(auto_pipeline)

# Registry commands
cli.add_command(ticker_registry_cmd)
cli.add_command(register_tickers_cmd)


if __name__ == "__main__":
    cli()
