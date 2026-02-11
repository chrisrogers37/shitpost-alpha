"""
Tests for LLM provider comparison module.
"""

import pytest

from shit.llm.compare_providers import (
    ComparisonResult,
    ProviderComparator,
    ProviderResult,
    format_comparison_report,
)


class TestProviderComparator:
    """Test provider comparison logic."""

    def test_calculate_agreement_identical_results(self):
        """Perfect agreement when all providers return the same assets/sentiment."""
        comparison = ComparisonResult(content="test")
        comparison.results = [
            ProviderResult(
                provider="openai",
                model="gpt-4o",
                assets=["TSLA", "AAPL"],
                market_impact={"TSLA": "bullish", "AAPL": "neutral"},
                confidence=0.85,
                success=True,
            ),
            ProviderResult(
                provider="anthropic",
                model="claude-sonnet-4",
                assets=["TSLA", "AAPL"],
                market_impact={"TSLA": "bullish", "AAPL": "neutral"},
                confidence=0.80,
                success=True,
            ),
        ]

        comparator = ProviderComparator()
        comparator._calculate_agreement(comparison)

        assert comparison.asset_agreement == 1.0
        assert comparison.sentiment_agreement == 1.0
        assert comparison.confidence_spread == pytest.approx(0.05)

    def test_calculate_agreement_different_assets(self):
        """Partial agreement when providers return different assets."""
        comparison = ComparisonResult(content="test")
        comparison.results = [
            ProviderResult(
                provider="openai",
                model="gpt-4o",
                assets=["TSLA", "AAPL"],
                market_impact={"TSLA": "bullish"},
                confidence=0.85,
                success=True,
            ),
            ProviderResult(
                provider="anthropic",
                model="claude-sonnet-4",
                assets=["TSLA", "GOOG"],
                market_impact={"TSLA": "bearish"},
                confidence=0.70,
                success=True,
            ),
        ]

        comparator = ProviderComparator()
        comparator._calculate_agreement(comparison)

        # Jaccard: intersection={TSLA} / union={TSLA, AAPL, GOOG} = 1/3
        assert comparison.asset_agreement == pytest.approx(1 / 3)
        # Sentiment: TSLA is bullish vs bearish = 0 agreement
        assert comparison.sentiment_agreement == 0.0
        assert comparison.confidence_spread == pytest.approx(0.15)

    def test_calculate_agreement_single_result(self):
        """No agreement calculated with only one result."""
        comparison = ComparisonResult(content="test")
        comparison.results = [
            ProviderResult(
                provider="openai",
                model="gpt-4o",
                assets=["TSLA"],
                confidence=0.85,
                success=True,
            ),
        ]

        comparator = ProviderComparator()
        comparator._calculate_agreement(comparison)

        # Defaults remain
        assert comparison.asset_agreement == 0.0
        assert comparison.sentiment_agreement == 0.0

    def test_format_comparison_report(self):
        """Report includes provider names, assets, and agreement metrics."""
        comparison = ComparisonResult(content="Test content for report")
        comparison.results = [
            ProviderResult(
                provider="openai",
                model="gpt-4o",
                assets=["TSLA"],
                market_impact={"TSLA": "bullish"},
                confidence=0.85,
                thesis="Bullish on Tesla",
                latency_ms=1200,
                success=True,
            ),
        ]
        comparison.asset_agreement = 1.0
        comparison.sentiment_agreement = 1.0
        comparison.confidence_spread = 0.0

        report = format_comparison_report(comparison)

        assert "OPENAI" in report
        assert "gpt-4o" in report
        assert "TSLA" in report
        assert "85.0%" in report
        assert "1200ms" in report
        assert "Asset Agreement" in report

    def test_format_report_with_error(self):
        """Report handles failed provider results."""
        comparison = ComparisonResult(content="Test")
        comparison.results = [
            ProviderResult(
                provider="grok",
                model="grok-2",
                success=False,
                error="API key invalid",
            ),
        ]

        report = format_comparison_report(comparison)

        assert "GROK" in report
        assert "ERROR" in report
        assert "API key invalid" in report
