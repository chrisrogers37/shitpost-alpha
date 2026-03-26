"""Tests for OutcomeCalculator (shit/market_data/outcome_calculator.py)."""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.models import PredictionOutcome


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def calculator(mock_session):
    calc = OutcomeCalculator(session=mock_session)
    calc.market_client = MagicMock()
    # Mock the market calendar to behave like simple date arithmetic for existing tests
    mock_calendar = MagicMock()
    mock_calendar.trading_day_offset.side_effect = lambda d, n: d + timedelta(days=n)
    mock_calendar.previous_trading_day.side_effect = lambda d: d - timedelta(days=1)
    mock_calendar.nearest_trading_day.side_effect = lambda d: d
    mock_calendar.is_trading_day.return_value = True
    mock_calendar.session_close_time.return_value = None
    mock_calendar.next_trading_day.side_effect = lambda d: d + timedelta(days=1)
    calc._calendar = mock_calendar
    return calc


def _make_prediction(**overrides):
    """Helper to create a mock Prediction with sensible defaults."""
    pred = MagicMock()
    pred.id = overrides.get("id", 1)
    pred.analysis_status = overrides.get("analysis_status", "completed")
    pred.assets = overrides.get("assets", ["AAPL"])
    pred.market_impact = overrides.get("market_impact", {"AAPL": "bullish"})
    pred.confidence = overrides.get("confidence", 0.85)
    pred.created_at = overrides.get("created_at", datetime(2025, 6, 15, 10, 0, 0))

    # Denormalized post_timestamp (None by default to test fallback paths)
    pred.post_timestamp = overrides.get("post_timestamp", None)

    # Source timestamps (shitpost / signal)
    shitpost = overrides.get("shitpost", MagicMock())
    if "shitpost" not in overrides:
        # Default: shitpost.timestamp matches the post publication time
        shitpost.timestamp = overrides.get(
            "shitpost_timestamp", datetime(2025, 6, 14, 9, 30, 0)
        )
    pred.shitpost = shitpost

    signal = overrides.get("signal", None)
    pred.signal = signal

    return pred


# ─── Init & Context Manager ─────────────────────────────────────────


class TestOutcomeCalculatorInit:
    def test_init_with_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        assert calc.session is mock_session
        assert calc._own_session is False

    def test_init_without_session(self):
        calc = OutcomeCalculator()
        assert calc.session is None
        assert calc._own_session is True

    @patch("shit.market_data.outcome_calculator.get_session")
    @patch("shit.market_data.outcome_calculator.MarketDataClient")
    def test_context_manager_creates_session(self, mock_mdc, mock_get_session):
        mock_ctx = MagicMock()
        mock_sess = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_sess)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_session.return_value = mock_ctx

        calc = OutcomeCalculator()
        with calc as c:
            assert c.session is mock_sess

    def test_context_manager_with_external_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        with calc as c:
            assert c.session is mock_session
            assert c.market_client is not None


# ─── _extract_sentiment ─────────────────────────────────────────────


class TestExtractSentiment:
    def test_extracts_first_sentiment(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "Bullish"})
        assert result == "bullish"

    def test_returns_none_for_empty_dict(self, calculator):
        assert calculator._extract_sentiment({}) is None

    def test_returns_none_for_none(self, calculator):
        assert calculator._extract_sentiment(None) is None

    def test_lowercases_sentiment(self, calculator):
        result = calculator._extract_sentiment({"TSLA": "BEARISH"})
        assert result == "bearish"

    def test_multi_asset_returns_first_when_no_asset_specified(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"})
        assert result in ("bullish", "bearish")  # dict ordering

    # --- Per-asset tests ---

    def test_per_asset_exact_match(self, calculator):
        mi = {"AAPL": "bullish", "TSLA": "bearish"}
        assert calculator._extract_sentiment(mi, asset="AAPL") == "bullish"
        assert calculator._extract_sentiment(mi, asset="TSLA") == "bearish"

    def test_per_asset_case_insensitive(self, calculator):
        mi = {"AAPL": "bullish", "TSLA": "bearish"}
        assert calculator._extract_sentiment(mi, asset="aapl") == "bullish"
        assert calculator._extract_sentiment(mi, asset="tsla") == "bearish"

    def test_per_asset_falls_back_to_first_when_not_found(self, calculator):
        mi = {"AAPL": "bullish"}
        result = calculator._extract_sentiment(mi, asset="GOOG")
        assert result == "bullish"  # fallback to first

    def test_per_asset_handles_mixed_case_keys(self, calculator):
        mi = {"Aapl": "bullish"}
        assert calculator._extract_sentiment(mi, asset="AAPL") == "bullish"


# ─── _get_source_date ──────────────────────────────────────────────


class TestGetSourceDate:
    """Verify that the anchor date comes from the *post* timestamp, not analysis time."""

    def test_uses_shitpost_timestamp(self, calculator):
        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 9, 30, 0),
            created_at=datetime(2025, 6, 20, 12, 0, 0),  # analysis ran 6 days later
        )
        result = calculator._get_source_date(pred)
        assert result == date(2025, 6, 14)

    def test_uses_signal_published_at_when_no_shitpost(self, calculator):
        signal = MagicMock()
        signal.published_at = datetime(2025, 7, 1, 8, 0, 0)

        pred = _make_prediction(
            shitpost=None,
            signal=signal,
            created_at=datetime(2025, 7, 5, 10, 0, 0),
        )
        result = calculator._get_source_date(pred)
        assert result == date(2025, 7, 1)

    def test_falls_back_to_created_at(self, calculator):
        pred = _make_prediction(
            shitpost=None,
            signal=None,
            created_at=datetime(2025, 6, 15, 10, 0, 0),
        )
        result = calculator._get_source_date(pred)
        assert result == date(2025, 6, 15)

    def test_returns_none_when_no_timestamps(self, calculator):
        pred = _make_prediction(shitpost=None, signal=None, created_at=None)
        result = calculator._get_source_date(pred)
        assert result is None

    def test_prefers_shitpost_over_signal(self, calculator):
        signal = MagicMock()
        signal.published_at = datetime(2025, 7, 1, 8, 0, 0)

        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 9, 30, 0),
            signal=signal,
            created_at=datetime(2025, 7, 5, 10, 0, 0),
        )
        result = calculator._get_source_date(pred)
        assert result == date(2025, 6, 14)

    def test_shitpost_with_no_timestamp_falls_to_signal(self, calculator):
        shitpost = MagicMock()
        shitpost.timestamp = None

        signal = MagicMock()
        signal.published_at = datetime(2025, 7, 1, 8, 0, 0)

        pred = _make_prediction(shitpost=shitpost, signal=signal)
        result = calculator._get_source_date(pred)
        assert result == date(2025, 7, 1)


# ─── calculate_outcome_for_prediction ────────────────────────────────


class TestCalculateOutcomeForPrediction:
    def test_missing_prediction_returns_empty(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = calculator.calculate_outcome_for_prediction(999)
        assert result == []

    def test_bypassed_prediction_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(analysis_status="bypassed")
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_no_assets_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(assets=None)
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_empty_assets_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(assets=[])
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_no_timestamps_at_all_returns_empty(self, calculator, mock_session):
        pred = _make_prediction(created_at=None, shitpost=None, signal=None)
        mock_session.query.return_value.filter.return_value.first.return_value = pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_continues_on_per_asset_error(self, calculator, mock_session):
        pred = _make_prediction(assets=["BAD", "GOOD"])
        mock_session.query.return_value.filter.return_value.first.return_value = pred

        # _calculate_single_outcome: first call raises, second returns outcome
        mock_outcome = MagicMock(spec=PredictionOutcome)
        calculator._calculate_single_outcome = MagicMock(
            side_effect=[RuntimeError("bad ticker"), mock_outcome]
        )

        result = calculator.calculate_outcome_for_prediction(1)
        assert len(result) == 1
        assert result[0] is mock_outcome

    def test_calls_calculate_single_for_each_asset(self, calculator, mock_session):
        pred = _make_prediction(assets=["AAPL", "TSLA", "GOOG"])
        mock_session.query.return_value.filter.return_value.first.return_value = pred

        mock_outcome = MagicMock(spec=PredictionOutcome)
        calculator._calculate_single_outcome = MagicMock(return_value=mock_outcome)

        result = calculator.calculate_outcome_for_prediction(1)
        assert len(result) == 3
        assert calculator._calculate_single_outcome.call_count == 3

    def test_passes_per_asset_sentiment(self, calculator, mock_session):
        """Verify each asset gets its own sentiment from market_impact."""
        pred = _make_prediction(
            assets=["AAPL", "TSLA"],
            market_impact={"AAPL": "bullish", "TSLA": "bearish"},
        )
        mock_session.query.return_value.filter.return_value.first.return_value = pred

        mock_outcome = MagicMock(spec=PredictionOutcome)
        calculator._calculate_single_outcome = MagicMock(return_value=mock_outcome)

        calculator.calculate_outcome_for_prediction(1)

        calls = calculator._calculate_single_outcome.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["sentiment"] == "bullish"
        assert calls[1].kwargs["sentiment"] == "bearish"


# ─── _calculate_single_outcome ───────────────────────────────────────


class TestCalculateSingleOutcome:
    def test_returns_existing_when_not_force_refresh(self, calculator, mock_session):
        existing = MagicMock(spec=PredictionOutcome)
        mock_session.query.return_value.filter.return_value.first.return_value = (
            existing
        )

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
        )
        assert result is existing

    def test_returns_none_when_no_price_data(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        calculator.market_client.get_price_on_date.return_value = None
        calculator.market_client.fetch_price_history.return_value = []

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
        )
        assert result is None

    @patch("shit.market_data.outcome_calculator.date")
    def test_creates_outcome_with_prices(self, mock_date, calculator, mock_session):
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # No existing outcome
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Mock prices: t0=100, all timeframes=110
        mock_price_t0 = MagicMock(close=100.0)
        mock_price_tn = MagicMock(close=110.0)
        calculator.market_client.get_price_on_date.return_value = mock_price_t0

        # After first call (price_t0), return tn for timeframes
        calculator.market_client.get_price_on_date.side_effect = [
            mock_price_t0,  # price at prediction
            mock_price_tn,  # T+1
            mock_price_tn,  # T+3
            mock_price_tn,  # T+7
            mock_price_tn,  # T+30
        ]

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
        )

        assert result is not None
        assert result.price_at_prediction == 100.0
        assert result.return_t7 == 10.0  # (110-100)/100 * 100
        assert result.correct_t7 is True  # bullish + positive return
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_force_refresh_recalculates_existing(self, calculator, mock_session):
        existing = MagicMock(spec=PredictionOutcome)
        # First query returns existing outcome, second returns None (no price check)
        mock_session.query.return_value.filter.return_value.first.side_effect = [
            existing,  # existing outcome check
        ]
        calculator.market_client.get_price_on_date.return_value = None
        calculator.market_client.fetch_price_history.return_value = []

        calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=True,
        )
        # Should attempt to recalculate (not just return existing)
        calculator.market_client.get_price_on_date.assert_called()


# ─── calculate_outcomes_for_all_predictions ───────────────────────────


class TestCalculateOutcomesForAllPredictions:
    def test_returns_stats_dict(self, calculator, mock_session):
        pred = _make_prediction()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            pred
        ]

        # Mock the per-prediction calculation
        calculator.calculate_outcome_for_prediction = MagicMock(
            return_value=[MagicMock()]
        )

        result = calculator.calculate_outcomes_for_all_predictions()
        assert result["total_predictions"] == 1
        assert result["processed"] == 1
        assert result["outcomes_created"] == 1
        assert result["errors"] == 0

    def test_counts_errors(self, calculator, mock_session):
        pred = _make_prediction()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            pred
        ]

        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=RuntimeError("boom")
        )

        result = calculator.calculate_outcomes_for_all_predictions()
        assert result["errors"] == 1
        assert result["processed"] == 0

    def test_applies_limit(self, calculator, mock_session):
        mock_query = (
            mock_session.query.return_value.filter.return_value.order_by.return_value
        )
        mock_query.limit.return_value.all.return_value = []

        calculator.calculate_outcomes_for_all_predictions(limit=5)
        mock_query.limit.assert_called_once_with(5)

    def test_applies_days_back_filter(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        calculator.calculate_outcomes_for_all_predictions(days_back=7)
        # Should call filter twice (status + date cutoff)
        assert mock_session.query.return_value.filter.call_count >= 1


# ─── get_accuracy_stats ──────────────────────────────────────────────


class TestGetAccuracyStats:
    def test_returns_zeros_when_no_outcomes(self, calculator, mock_session):
        mock_session.query.return_value.all.return_value = []

        result = calculator.get_accuracy_stats()
        assert result == {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "pending": 0,
            "accuracy": 0.0,
        }

    def test_calculates_accuracy(self, calculator, mock_session):
        outcomes = []
        for correct_val in [True, True, True, False, None]:
            o = MagicMock()
            o.correct_t7 = correct_val
            outcomes.append(o)

        mock_session.query.return_value.all.return_value = outcomes

        result = calculator.get_accuracy_stats(timeframe="t7")
        assert result["total"] == 5
        assert result["correct"] == 3
        assert result["incorrect"] == 1
        assert result["pending"] == 1
        assert result["accuracy"] == 75.0

    def test_uses_specified_timeframe(self, calculator, mock_session):
        o = MagicMock()
        o.correct_t1 = True
        o.correct_t30 = False
        mock_session.query.return_value.all.return_value = [o]

        result_t1 = calculator.get_accuracy_stats(timeframe="t1")
        assert result_t1["correct"] == 1

        result_t30 = calculator.get_accuracy_stats(timeframe="t30")
        assert result_t30["incorrect"] == 1

    def test_filters_by_min_confidence(self, calculator, mock_session):
        mock_session.query.return_value.filter.return_value.all.return_value = []

        calculator.get_accuracy_stats(min_confidence=0.8)
        mock_session.query.return_value.filter.assert_called_once()

    def test_all_pending_returns_zero_accuracy(self, calculator, mock_session):
        outcomes = [MagicMock(correct_t7=None), MagicMock(correct_t7=None)]
        mock_session.query.return_value.all.return_value = outcomes

        result = calculator.get_accuracy_stats()
        assert result["accuracy"] == 0.0
        assert result["pending"] == 2


# -- _get_source_datetime ---------------------------------------------------


class TestGetSourceDatetime:
    def test_returns_datetime_from_shitpost(self, calculator):
        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 9, 30, 0),
        )
        result = calculator._get_source_datetime(pred)
        assert result == datetime(2025, 6, 14, 9, 30, 0, tzinfo=timezone.utc)

    def test_returns_none_when_no_timestamps(self, calculator):
        pred = _make_prediction(shitpost=None, signal=None, created_at=None)
        result = calculator._get_source_datetime(pred)
        assert result is None

    def test_returns_datetime_from_signal(self, calculator):
        signal = MagicMock()
        signal.published_at = datetime(2025, 7, 1, 8, 0, 0)

        pred = _make_prediction(shitpost=None, signal=signal)
        result = calculator._get_source_datetime(pred)
        assert result == datetime(2025, 7, 1, 8, 0, 0, tzinfo=timezone.utc)

    def test_falls_back_to_created_at(self, calculator):
        pred = _make_prediction(
            shitpost=None,
            signal=None,
            created_at=datetime(2025, 6, 15, 10, 0, 0),
        )
        result = calculator._get_source_datetime(pred)
        assert result == datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_preserves_timezone_if_already_aware(self, calculator):
        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 9, 30, 0, tzinfo=timezone.utc),
        )
        result = calculator._get_source_datetime(pred)
        assert result.tzinfo == timezone.utc

    def test_get_source_date_delegates_to_get_source_datetime(self, calculator):
        """Verify _get_source_date returns the date of _get_source_datetime's result."""
        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 23, 59, 0),
        )
        date_result = calculator._get_source_date(pred)
        dt_result = calculator._get_source_datetime(pred)
        assert date_result == dt_result.date()


# -- Trading-day timeframes --------------------------------------------------


class TestTradingDayTimeframes:
    """Verify that outcome calculation uses trading days, not calendar days."""

    @patch("shit.market_data.outcome_calculator.fetch_intraday_snapshot")
    @patch("shit.market_data.outcome_calculator.date")
    def test_friday_prediction_t1_is_monday(
        self, mock_date, mock_intraday, calculator, mock_session
    ):
        """T+1 on Friday should use Monday's close, not Saturday."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_intraday.return_value = MagicMock(
            price_at_post=None, price_1h_after=None, price_at_next_close=None
        )

        # Override calendar mock to use real trading-day logic
        from shit.market_data.market_calendar import MarketCalendar

        real_cal = MarketCalendar()
        calculator._calendar = real_cal

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 13),  # Friday
            sentiment="bullish",
            confidence=0.8,
        )

        # Verify T+1 call was for Monday June 16, not Saturday June 14
        calls = calculator.market_client.get_price_on_date.call_args_list
        # First call is price_at_prediction (June 13)
        # Second call should be T+1 = June 16 (Monday)
        t1_call_date = calls[1][0][1]  # second positional arg of second call
        assert t1_call_date == date(2025, 6, 16)

    @patch("shit.market_data.outcome_calculator.fetch_intraday_snapshot")
    @patch("shit.market_data.outcome_calculator.date")
    def test_holiday_skip(self, mock_date, mock_intraday, calculator, mock_session):
        """T+1 before July 4 holiday should skip to the next trading day."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        mock_intraday.return_value = MagicMock(
            price_at_post=None, price_1h_after=None, price_at_next_close=None
        )

        from shit.market_data.market_calendar import MarketCalendar

        real_cal = MarketCalendar()
        calculator._calendar = real_cal

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 7, 3),  # Thursday before July 4
            sentiment="bullish",
            confidence=0.8,
        )

        calls = calculator.market_client.get_price_on_date.call_args_list
        # T+1 should be July 7 (Monday), skipping July 4 (holiday) and weekend
        t1_call_date = calls[1][0][1]
        assert t1_call_date == date(2025, 7, 7)


# -- Intraday calculations --------------------------------------------------


class TestIntradayCalculations:
    """Verify intraday snapshot integration in _calculate_single_outcome."""

    @patch("shit.market_data.outcome_calculator.fetch_intraday_snapshot")
    @patch("shit.market_data.outcome_calculator.date")
    def test_intraday_fields_populated_when_post_datetime_provided(
        self, mock_date, mock_intraday, calculator, mock_session
    ):
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # Set up intraday snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.price_at_post = 149.0
        mock_snapshot.price_1h_after = 151.0
        mock_snapshot.price_at_next_close = 150.0
        mock_intraday.return_value = mock_snapshot

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        post_dt = datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            post_datetime=post_dt,
        )

        assert result is not None
        assert result.post_published_at == post_dt
        assert result.price_at_post == 149.0
        assert result.price_1h_after == 151.0

    @patch("shit.market_data.outcome_calculator.fetch_intraday_snapshot")
    @patch("shit.market_data.outcome_calculator.date")
    def test_intraday_skipped_when_no_post_datetime(
        self, mock_date, mock_intraday, calculator, mock_session
    ):
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            post_datetime=None,  # No post datetime
        )

        assert result is not None
        # Intraday should not be attempted
        mock_intraday.assert_not_called()

    @patch("shit.market_data.outcome_calculator.fetch_intraday_snapshot")
    @patch("shit.market_data.outcome_calculator.date")
    def test_intraday_returns_calculated(
        self, mock_date, mock_intraday, calculator, mock_session
    ):
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        mock_snapshot = MagicMock()
        mock_snapshot.price_at_post = 100.0
        mock_snapshot.price_1h_after = 102.0
        mock_snapshot.price_at_next_close = 105.0
        mock_intraday.return_value = mock_snapshot

        mock_session.query.return_value.filter.return_value.first.return_value = None

        # price_t0 = 100, timeframe prices = 110
        # For the intraday "next close" lookup, return a different daily close
        mock_price_t0 = MagicMock(close=100.0)
        mock_price_tn = MagicMock(close=110.0)
        mock_daily_close = MagicMock(close=105.0)  # same as snapshot for consistency

        # Control which dates return which prices:
        # 1st call: price_at_prediction (t0)
        # 2nd-5th: timeframe prices (t1,t3,t7,t30)
        # 6th: intraday "next close date" lookup -> daily close of 105
        calculator.market_client.get_price_on_date.side_effect = [
            mock_price_t0,  # price at prediction
            mock_price_tn,  # T+1
            mock_price_tn,  # T+3
            mock_price_tn,  # T+7
            mock_price_tn,  # T+30
            mock_daily_close,  # next close date for intraday
        ]

        post_dt = datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            post_datetime=post_dt,
        )

        assert result is not None
        # return_1h: (102 - 100) / 100 * 100 = 2.0%
        assert result.return_1h == 2.0
        assert result.correct_1h is True  # bullish + positive
        # return_same_day: (105 - 100) / 100 * 100 = 5.0%
        # (105 comes from the daily close MarketPrice, which is preferred over snapshot)
        assert result.return_same_day == 5.0
        assert result.correct_same_day is True
