"""
Shared CLI Arguments

Provides reusable argparse argument definitions shared across CLI modules.
Each module can add these standard arguments to its own parser, then layer
on module-specific extras.

Usage::

    import argparse
    from shit.cli.shared_args import add_standard_arguments, validate_standard_args

    parser = argparse.ArgumentParser(description="My CLI")
    add_standard_arguments(parser)
    # Add module-specific args here...

    args = parser.parse_args()
    validate_standard_args(args)
"""

import argparse


def add_standard_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the standard set of CLI arguments to a parser.

    Adds the following arguments:
        --mode: choices=["incremental", "backfill", "range"], default="incremental"
        --from / dest=start_date: Start date for range mode (YYYY-MM-DD)
        --to / dest=end_date: End date for range mode (YYYY-MM-DD)
        --limit: Maximum number of records to process (int)
        --dry-run: Show what would be done without making changes
        --verbose / -v: Enable verbose logging

    Args:
        parser: The ArgumentParser (or subparser) to add arguments to.
    """
    parser.add_argument(
        "--mode",
        choices=["incremental", "backfill", "range"],
        default="incremental",
        help="Processing mode (default: incremental)",
    )
    parser.add_argument(
        "--from",
        dest="start_date",
        help="Start date for range mode (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="end_date",
        help="End date for range mode (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of records to process (optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )


def validate_standard_args(args: argparse.Namespace) -> None:
    """Validate standard CLI arguments.

    Checks that ``--from`` is provided when ``--mode range`` is selected.
    The ``--to`` date is always optional (defaults to today).

    Args:
        args: Parsed command line arguments.

    Raises:
        SystemExit: If ``--mode range`` is used without ``--from``.
    """
    if args.mode == "range" and not args.start_date:
        raise SystemExit("--from date is required for range mode")
