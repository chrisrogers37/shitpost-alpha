"""Tests for PredictionOutcome model methods — core financial math."""

from shit.market_data.models import PredictionOutcome


class TestCalculateReturn:
    """Test percentage return calculation."""

    def test_positive_return(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_return(100.0, 110.0)
        assert result == 10.0

    def test_negative_return(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_return(100.0, 90.0)
        assert result == -10.0

    def test_zero_return(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_return(100.0, 100.0)
        assert result == 0.0

    def test_none_initial_price(self):
        outcome = PredictionOutcome()
        assert outcome.calculate_return(None, 110.0) is None

    def test_none_final_price(self):
        outcome = PredictionOutcome()
        assert outcome.calculate_return(100.0, None) is None

    def test_zero_initial_price(self):
        outcome = PredictionOutcome()
        assert outcome.calculate_return(0.0, 110.0) is None

    def test_small_fractional_return(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_return(100.0, 100.5)
        assert abs(result - 0.5) < 0.001


class TestIsCorrect:
    """Test prediction correctness logic."""

    def test_bullish_correct_when_price_rises(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bullish", 5.0) is True

    def test_bullish_incorrect_when_price_falls(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bullish", -5.0) is False

    def test_bullish_incorrect_within_threshold(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bullish", 0.3) is False

    def test_bearish_correct_when_price_falls(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bearish", -5.0) is True

    def test_bearish_incorrect_when_price_rises(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bearish", 5.0) is False

    def test_bearish_incorrect_within_threshold(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bearish", -0.3) is False

    def test_neutral_correct_within_threshold(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("neutral", 0.3) is True

    def test_neutral_incorrect_when_big_move(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("neutral", 5.0) is False

    def test_custom_threshold(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bullish", 0.3, threshold=0.2) is True
        assert outcome.is_correct("bullish", 0.3, threshold=0.5) is False

    def test_none_return_pct(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("bullish", None) is None

    def test_none_sentiment(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct(None, 5.0) is None

    def test_unknown_sentiment(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("sideways", 5.0) is None

    def test_case_insensitive(self):
        outcome = PredictionOutcome()
        assert outcome.is_correct("BULLISH", 5.0) is True
        assert outcome.is_correct("Bearish", -5.0) is True


class TestCalculatePnl:
    """Test P&L simulation."""

    def test_positive_pnl(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_pnl(10.0)
        assert result == 100.0  # 10% of $1000

    def test_negative_pnl(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_pnl(-5.0)
        assert result == -50.0  # -5% of $1000

    def test_custom_position_size(self):
        outcome = PredictionOutcome()
        result = outcome.calculate_pnl(10.0, position_size=5000.0)
        assert result == 500.0  # 10% of $5000

    def test_none_return(self):
        outcome = PredictionOutcome()
        assert outcome.calculate_pnl(None) is None

    def test_zero_return(self):
        outcome = PredictionOutcome()
        assert outcome.calculate_pnl(0.0) == 0.0
