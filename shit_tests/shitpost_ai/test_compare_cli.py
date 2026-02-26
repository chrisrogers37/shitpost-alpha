"""
Tests for shitpost_ai/compare_cli.py — Provider Comparison CLI.
"""

import pytest
import argparse
from unittest.mock import patch, MagicMock, AsyncMock


class TestCreateCompareParser:
    """Test cases for create_compare_parser function."""

    def test_returns_argument_parser(self):
        """Test that function returns an ArgumentParser instance."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_has_content_argument(self):
        """Test parser has --content argument."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        help_text = parser.format_help()
        assert "--content" in help_text

    def test_parser_has_shitpost_id_argument(self):
        """Test parser has --shitpost-id argument."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        help_text = parser.format_help()
        assert "--shitpost-id" in help_text

    def test_parser_has_providers_argument(self):
        """Test parser has --providers argument."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        help_text = parser.format_help()
        assert "--providers" in help_text

    def test_parser_has_list_providers_flag(self):
        """Test parser has --list-providers flag."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        help_text = parser.format_help()
        assert "--list-providers" in help_text

    def test_parser_has_verbose_flag(self):
        """Test parser has --verbose / -v flag."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        help_text = parser.format_help()
        assert "--verbose" in help_text
        assert "-v" in help_text

    def test_parser_has_epilog_with_examples(self):
        """Test parser epilog contains usage examples."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        assert parser.epilog is not None
        assert "Examples:" in parser.epilog
        assert "python -m shitpost_ai compare" in parser.epilog

    def test_content_argument_stores_string(self):
        """Test --content argument stores a string value."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args(["--content", "Tesla is going to the moon!"])
        assert args.content == "Tesla is going to the moon!"

    def test_shitpost_id_argument_stores_string(self):
        """Test --shitpost-id argument stores a string value."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args(["--shitpost-id", "123456789"])
        assert args.shitpost_id == "123456789"

    def test_list_providers_flag_default_false(self):
        """Test --list-providers defaults to False."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args([])
        assert args.list_providers is False

    def test_list_providers_flag_sets_true(self):
        """Test --list-providers flag sets value to True."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args(["--list-providers"])
        assert args.list_providers is True

    def test_verbose_flag_default_false(self):
        """Test --verbose defaults to False."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args([])
        assert args.verbose is False

    def test_verbose_flag_sets_true(self):
        """Test --verbose flag sets value to True."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_verbose_short_flag_sets_true(self):
        """Test -v short flag sets verbose to True."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_providers_accepts_multiple_values(self):
        """Test --providers accepts multiple space-separated provider IDs."""
        from shitpost_ai.compare_cli import create_compare_parser
        from shit.llm.provider_config import get_all_provider_ids

        parser = create_compare_parser()
        provider_ids = get_all_provider_ids()
        if len(provider_ids) >= 2:
            args = parser.parse_args(
                ["--providers", provider_ids[0], provider_ids[1]]
            )
            assert args.providers == [provider_ids[0], provider_ids[1]]

    def test_providers_default_is_none(self):
        """Test --providers defaults to None when not provided."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args([])
        assert args.providers is None

    def test_all_arguments_combined(self):
        """Test parser with all arguments specified together."""
        from shitpost_ai.compare_cli import create_compare_parser

        parser = create_compare_parser()
        args = parser.parse_args([
            "--content", "Tariffs on China!",
            "--verbose",
        ])
        assert args.content == "Tariffs on China!"
        assert args.verbose is True
        assert args.list_providers is False


class TestListProviders:
    """Test cases for list_providers function."""

    def test_prints_provider_info(self):
        """Test that list_providers prints provider names and models."""
        from shitpost_ai.compare_cli import list_providers

        with patch("builtins.print") as mock_print:
            list_providers()
            assert mock_print.call_count > 0
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list if call[0]
            )
            assert "Available LLM Providers" in all_output

    def test_prints_each_provider_id(self):
        """Test that each configured provider appears in the output."""
        from shitpost_ai.compare_cli import list_providers
        from shit.llm.provider_config import PROVIDERS

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list if call[0]
            )
            for provider_id in PROVIDERS:
                assert provider_id in all_output

    def test_prints_model_ids(self):
        """Test that model IDs are included in the output."""
        from shitpost_ai.compare_cli import list_providers
        from shit.llm.provider_config import PROVIDERS

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list if call[0]
            )
            for config in PROVIDERS.values():
                if config.models:
                    assert config.models[0].model_id in all_output

    def test_prints_recommended_marker(self):
        """Test that [RECOMMENDED] marker appears for recommended models."""
        from shitpost_ai.compare_cli import list_providers
        from shit.llm.provider_config import PROVIDERS

        has_recommended = any(
            model.recommended
            for config in PROVIDERS.values()
            for model in config.models
        )
        if has_recommended:
            with patch("builtins.print") as mock_print:
                list_providers()
                all_output = " ".join(
                    str(call[0][0]) for call in mock_print.call_args_list if call[0]
                )
                assert "[RECOMMENDED]" in all_output

    def test_prints_cost_info(self):
        """Test that cost information is included for models."""
        from shitpost_ai.compare_cli import list_providers

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list if call[0]
            )
            assert "Cost:" in all_output
            assert "/1M" in all_output

    def test_prints_sdk_type(self):
        """Test that SDK type is printed for each provider."""
        from shitpost_ai.compare_cli import list_providers

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list if call[0]
            )
            assert "SDK:" in all_output


class TestRunComparison:
    """Test cases for run_comparison async function."""

    @pytest.mark.asyncio
    async def test_prints_error_when_fewer_than_two_providers(self):
        """Test error message when fewer than 2 providers initialize."""
        from shitpost_ai.compare_cli import run_comparison

        mock_comparator = MagicMock()
        mock_comparator.initialize = AsyncMock(return_value=["openai"])

        with patch(
            "shitpost_ai.compare_cli.ProviderComparator",
            return_value=mock_comparator,
        ), patch("builtins.print") as mock_print:
            await run_comparison("Test content")
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Only 1 provider(s) initialized" in all_output
            assert "Need at least 2 for comparison" in all_output

    @pytest.mark.asyncio
    async def test_prints_error_when_zero_providers(self):
        """Test error message when zero providers initialize."""
        from shitpost_ai.compare_cli import run_comparison

        mock_comparator = MagicMock()
        mock_comparator.initialize = AsyncMock(return_value=[])

        with patch(
            "shitpost_ai.compare_cli.ProviderComparator",
            return_value=mock_comparator,
        ), patch("builtins.print") as mock_print:
            await run_comparison("Test content")
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Only 0 provider(s) initialized" in all_output

    @pytest.mark.asyncio
    async def test_runs_comparison_with_two_or_more_providers(self):
        """Test successful comparison when 2+ providers available."""
        from shitpost_ai.compare_cli import run_comparison

        mock_result = MagicMock()
        mock_comparator = MagicMock()
        mock_comparator.initialize = AsyncMock(return_value=["openai", "anthropic"])
        mock_comparator.compare = AsyncMock(return_value=mock_result)

        with patch(
            "shitpost_ai.compare_cli.ProviderComparator",
            return_value=mock_comparator,
        ), patch(
            "shitpost_ai.compare_cli.format_comparison_report",
            return_value="Comparison Report",
        ) as mock_format, patch("builtins.print") as mock_print:
            await run_comparison("Test content")
            mock_comparator.compare.assert_called_once_with("Test content")
            mock_format.assert_called_once_with(mock_result)
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Comparing 2 providers" in all_output
            assert "Comparison Report" in all_output

    @pytest.mark.asyncio
    async def test_passes_providers_parameter(self):
        """Test that providers parameter is forwarded to ProviderComparator."""
        from shitpost_ai.compare_cli import run_comparison

        mock_result = MagicMock()
        mock_comparator = MagicMock()
        mock_comparator.initialize = AsyncMock(return_value=["openai", "anthropic"])
        mock_comparator.compare = AsyncMock(return_value=mock_result)

        with patch(
            "shitpost_ai.compare_cli.ProviderComparator",
            return_value=mock_comparator,
        ) as mock_cls, patch(
            "shitpost_ai.compare_cli.format_comparison_report",
            return_value="Report",
        ), patch("builtins.print"):
            await run_comparison("Content", providers=["openai", "anthropic"])
            mock_cls.assert_called_once_with(providers=["openai", "anthropic"])

    @pytest.mark.asyncio
    async def test_passes_none_providers_by_default(self):
        """Test that None providers means all available providers."""
        from shitpost_ai.compare_cli import run_comparison

        mock_comparator = MagicMock()
        mock_comparator.initialize = AsyncMock(return_value=["a"])

        with patch(
            "shitpost_ai.compare_cli.ProviderComparator",
            return_value=mock_comparator,
        ) as mock_cls, patch("builtins.print"):
            await run_comparison("Content")
            mock_cls.assert_called_once_with(providers=None)


class TestCompareExamples:
    """Test cases for the COMPARE_EXAMPLES constant."""

    def test_compare_examples_is_string(self):
        """Test COMPARE_EXAMPLES is a non-empty string."""
        from shitpost_ai.compare_cli import COMPARE_EXAMPLES

        assert isinstance(COMPARE_EXAMPLES, str)
        assert len(COMPARE_EXAMPLES) > 0

    def test_compare_examples_contains_usage_patterns(self):
        """Test COMPARE_EXAMPLES shows key usage patterns."""
        from shitpost_ai.compare_cli import COMPARE_EXAMPLES

        assert "Examples:" in COMPARE_EXAMPLES
        assert "--content" in COMPARE_EXAMPLES
        assert "--providers" in COMPARE_EXAMPLES
        assert "--shitpost-id" in COMPARE_EXAMPLES
        assert "--list-providers" in COMPARE_EXAMPLES
