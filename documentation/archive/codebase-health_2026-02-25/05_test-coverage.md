# Phase 05 — Add Missing Test Coverage

| Field | Value |
|---|---|
| **PR title** | `test: add coverage for compare_cli and remove dead backfill_prices module` |
| **Risk** | Low |
| **Effort** | Low (~3 hours) |
| **Files created** | 1 |
| **Files deleted** | 1 |
| **Files modified** | 1 |
| **Dependencies** | None |
| **Unlocks** | Nothing |

---

## Context

The tech debt scan identified 4 modules as having zero test coverage. Thorough investigation reveals that **2 of these 4 are already well-tested**:

1. **`shitty_ui/callbacks/alert_components.py`** (627 LOC) — **ALREADY TESTED.** `shit_tests/shitty_ui/test_alert_callbacks.py` contains 8 test classes with 47+ tests covering all 9 builder functions.

2. **`shitty_ui/components/cards/empty_states.py`** (221 LOC) — **ALREADY TESTED.** Coverage is split across `test_layout.py` (TestErrorCard, TestEmptyChart, TestEmptyStateChart) and `test_cards.py` (TestEmptyStateHtml).

3. **`shitpost_ai/compare_cli.py`** (156 LOC) — **TRULY UNTESTED.** Zero references in `shit_tests/`. This phase adds tests for it.

4. **`shit/market_data/backfill_prices.py`** (162 LOC) — **DEAD CODE.** Not imported anywhere in production code. Superseded by the event-driven market data worker (`auto_backfill_service.py`). This phase removes it.

Actual scope: **1 new test file + 1 dead code removal**.

---

## Dependencies

- **Phase 02 (Query Builder Dedup)**: No conflict. Phase 02 touches `shitty_ui/data/signal_queries.py`. This phase touches `shit_tests/shitpost_ai/` and `shit/market_data/`. Zero file overlap.
- **Phase 04 (Callback Split)**: No conflict. This phase does NOT create tests for `alert_components.py` (already tested). Zero file overlap.

This phase can safely run in parallel with all other phases.

---

## Detailed Implementation Plan

### Step 1: Create `shit_tests/shitpost_ai/test_compare_cli.py`

Create at: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitpost_ai/test_compare_cli.py`

Follows the existing CLI test pattern from `shit_tests/shitpost_ai/test_shitpost_ai_cli.py`.

**Full file content:**

```python
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
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Available LLM Providers" in all_output

    def test_prints_each_provider_id(self):
        """Test that each configured provider appears in the output."""
        from shitpost_ai.compare_cli import list_providers
        from shit.llm.provider_config import PROVIDERS

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
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
                str(call[0][0]) for call in mock_print.call_args_list
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
                    str(call[0][0]) for call in mock_print.call_args_list
                )
                assert "[RECOMMENDED]" in all_output

    def test_prints_cost_info(self):
        """Test that cost information is included for models."""
        from shitpost_ai.compare_cli import list_providers

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
            )
            assert "Cost:" in all_output
            assert "/1M" in all_output

    def test_prints_sdk_type(self):
        """Test that SDK type is printed for each provider."""
        from shitpost_ai.compare_cli import list_providers

        with patch("builtins.print") as mock_print:
            list_providers()
            all_output = " ".join(
                str(call[0][0]) for call in mock_print.call_args_list
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
```

**Test count: 27 tests across 4 classes.**

Notes:
- `compare_main()` is NOT tested — it calls `sys.argv[2:]` directly. The 3 functions it delegates to are all fully tested.
- Tests import inside test functions to avoid import-time side effects from settings/DB initialization.

### Step 2: Remove dead code — `shit/market_data/backfill_prices.py`

**Delete this file:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/backfill_prices.py`

**Rationale:** Not imported by any production code. Superseded by event-driven `auto_backfill_service.py`. Uses synchronous `get_session()` for manual one-off backfills — the event-driven pipeline handles this automatically.

### Step 3: Update `shit/README.md`

Remove `backfill_prices.py` references:
- From directory tree listing (line ~61): `│   ├── backfill_prices.py   # Manual price backfill script`
- From description list (line ~191): `- **`backfill_prices.py`** - Manual price backfill script`

---

## Test Plan

### New tests
- `shit_tests/shitpost_ai/test_compare_cli.py` — 27 tests

### Existing tests NOT to modify
- `test_alert_callbacks.py` — already comprehensive for alert_components.py
- `test_layout.py` and `test_cards.py` — already cover empty_states.py

### Manual verification
1. Run new tests: `./venv/bin/python -m pytest shit_tests/shitpost_ai/test_compare_cli.py -v`
2. Confirm no import of `backfill_prices` breaks: `./venv/bin/python -c "from shit.market_data.client import MarketDataClient; print('OK')"`
3. Full suite: `./venv/bin/python -m pytest -v`
4. Verify no test references deleted module: `grep -r "backfill_prices" shit_tests/`

---

## Documentation Updates

### CHANGELOG.md

```markdown
### Added
- **Compare CLI tests** — 27 tests for `shitpost_ai/compare_cli.py` covering parser creation, provider listing, and comparison execution

### Removed
- **`shit/market_data/backfill_prices.py`** — Dead code removal; manual backfill script superseded by event-driven market data worker (`auto_backfill_service.py`)
```

---

## Stress Testing & Edge Cases

- Zero providers initialized (empty list)
- Exactly one provider initialized (below minimum)
- Two or more providers initialized (success path)
- `None` providers parameter (all available)
- Explicit provider list passed through
- Empty parser args (all defaults)

### Deletion safety
- `backfill_prices.py` has zero runtime importers — only referenced in archived documentation
- The `if __name__ == "__main__"` block means it was only invoked as a standalone script

---

## Verification Checklist

- [ ] `shit_tests/shitpost_ai/test_compare_cli.py` created with 27 tests
- [ ] All tests pass: `./venv/bin/python -m pytest shit_tests/shitpost_ai/test_compare_cli.py -v`
- [ ] `shit/market_data/backfill_prices.py` deleted
- [ ] `shit/README.md` updated (2 line removals)
- [ ] `CHANGELOG.md` updated
- [ ] Full suite passes: `./venv/bin/python -m pytest -v`
- [ ] No ruff lint errors: `./venv/bin/python -m ruff check shit_tests/shitpost_ai/test_compare_cli.py`
- [ ] `grep -r "backfill_prices" shit_tests/` returns no matches

---

## What NOT To Do

1. **Do NOT create `test_alert_components.py`** — already fully tested in `test_alert_callbacks.py` (47+ tests)
2. **Do NOT create `test_empty_states.py`** — already tested across `test_layout.py` and `test_cards.py`
3. **Do NOT write tests for `backfill_prices.py` before deleting it** — testing dead code being removed is pointless
4. **Do NOT test `compare_main()` directly** — orchestrator with `sys.argv` dependency, covered by its delegates
5. **Do NOT modify archived `PHASE0_STABILIZATION_RUNBOOK.md`** — references `backfill_prices.py` but archives preserve historical state
6. **Do NOT add `__init__.py` files** — `shit_tests/shitpost_ai/` already exists
7. **Do NOT use module-level imports** for `shitpost_ai.compare_cli` — import inside test functions to avoid side effects
