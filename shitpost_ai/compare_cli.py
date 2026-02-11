"""
Provider Comparison CLI
Compare LLM providers for shitpost analysis quality.
"""

import argparse
import asyncio
import sys
from typing import List, Optional

from shit.llm.compare_providers import ProviderComparator, format_comparison_report
from shit.llm.provider_config import PROVIDERS, get_all_provider_ids
from shit.logging import setup_cli_logging


COMPARE_EXAMPLES = """
Examples:
  # Compare all available providers on sample content
  python -m shitpost_ai compare --content "Tesla is destroying American jobs!"

  # Compare specific providers
  python -m shitpost_ai compare --providers openai anthropic --content "Tariffs on China!"

  # Compare using a post from the database (by shitpost_id)
  python -m shitpost_ai compare --shitpost-id 123456789

  # List available providers and models
  python -m shitpost_ai compare --list-providers
"""


def create_compare_parser() -> argparse.ArgumentParser:
    """Create argument parser for comparison CLI."""
    parser = argparse.ArgumentParser(
        description="Compare LLM provider analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=COMPARE_EXAMPLES,
    )

    parser.add_argument(
        "--content", type=str, help="Content text to analyze across providers"
    )
    parser.add_argument(
        "--shitpost-id",
        type=str,
        help="Analyze a specific shitpost from the database by ID",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=get_all_provider_ids(),
        help="Specific providers to compare (default: all available)",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available providers and their models",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser


def list_providers() -> None:
    """Print all available providers and their models."""
    print("\n=== Available LLM Providers ===\n")
    for provider_id, config in PROVIDERS.items():
        print(f"  {provider_id} ({config.display_name})")
        print(f"    SDK: {config.sdk_type}")
        print(f"    API Key Env: {config.api_key_env_var}")
        if config.base_url:
            print(f"    Base URL: {config.base_url}")
        print("    Models:")
        for model in config.models:
            rec = " [RECOMMENDED]" if model.recommended else ""
            print(f"      - {model.model_id}{rec}")
            print(
                f"        Cost: ${model.input_cost_per_1m_tokens}/1M in, "
                f"${model.output_cost_per_1m_tokens}/1M out"
            )
            if model.notes:
                print(f"        Note: {model.notes}")
        print()


async def run_comparison(
    content: str, providers: Optional[List[str]] = None
) -> None:
    """Run comparison and print report."""
    comparator = ProviderComparator(providers=providers)

    initialized = await comparator.initialize()
    if len(initialized) < 2:
        print(
            f"\nOnly {len(initialized)} provider(s) initialized. "
            "Need at least 2 for comparison."
        )
        print("Check that API keys are set for the providers you want to compare.")
        print("Run with --list-providers to see required environment variables.")
        return

    print(f"\nComparing {len(initialized)} providers: {', '.join(initialized)}")
    print("Running analysis...\n")

    result = await comparator.compare(content)
    report = format_comparison_report(result)
    print(report)


async def compare_main() -> None:
    """Main entry point for comparison CLI."""
    parser = create_compare_parser()
    args = parser.parse_args(sys.argv[2:])  # Skip 'compare' subcommand

    setup_cli_logging(verbose=args.verbose)

    if args.list_providers:
        list_providers()
        return

    if args.shitpost_id:
        # Fetch content from database
        from shit.config.shitpost_settings import settings
        from shit.db import DatabaseConfig, DatabaseClient, DatabaseOperations
        from shitvault.shitpost_operations import ShitpostOperations

        db_config = DatabaseConfig(database_url=settings.DATABASE_URL)
        db_client = DatabaseClient(db_config)
        await db_client.initialize()

        async with db_client.get_session() as session:
            db_ops = DatabaseOperations(session)
            shitpost_ops = ShitpostOperations(db_ops)
            shitpost = await shitpost_ops.get_shitpost_by_id(args.shitpost_id)

            if not shitpost:
                print(f"Shitpost {args.shitpost_id} not found in database")
                return

            content = shitpost.get("text", "")

        await db_client.cleanup()

    elif args.content:
        content = args.content
    else:
        parser.error("Either --content or --shitpost-id is required")
        return

    await run_comparison(content, providers=args.providers)
