"""Tests for MarketCalendar (shit/market_data/market_calendar.py)."""

import pytest
from datetime import date, datetime, timezone

from shit.market_data.market_calendar import MarketCalendar


@pytest.fixture
def cal():
    return MarketCalendar()


class TestIsTradingDay:
    def test_weekday_is_trading_day(self, cal):
        # Monday 2025-06-16
        assert cal.is_trading_day(date(2025, 6, 16)) is True

    def test_saturday_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 6, 14)) is False

    def test_sunday_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 6, 15)) is False

    def test_christmas_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 12, 25)) is False

    def test_july_4th_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 7, 4)) is False

    def test_new_years_day_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2026, 1, 1)) is False


class TestNextTradingDay:
    def test_friday_next_is_monday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 13))  # Friday
        assert result == date(2025, 6, 16)  # Monday

    def test_saturday_next_is_monday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 14))  # Saturday
        assert result == date(2025, 6, 16)

    def test_wednesday_next_is_thursday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 11))  # Wednesday
        assert result == date(2025, 6, 12)  # Thursday

    def test_day_before_holiday_skips_holiday(self, cal):
        # July 3 2025 is Thursday, July 4 is holiday, next = July 7 (Monday)
        result = cal.next_trading_day(date(2025, 7, 3))
        assert result == date(2025, 7, 7)


class TestPreviousTradingDay:
    def test_monday_previous_is_friday(self, cal):
        result = cal.previous_trading_day(date(2025, 6, 16))  # Monday
        assert result == date(2025, 6, 13)  # Friday

    def test_sunday_previous_is_friday(self, cal):
        result = cal.previous_trading_day(date(2025, 6, 15))  # Sunday
        assert result == date(2025, 6, 13)  # Friday


class TestTradingDayOffset:
    def test_t_plus_1_on_friday_is_monday(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 13), 1)  # Friday +1
        assert result == date(2025, 6, 16)  # Monday

    def test_t_plus_3_on_friday(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 13), 3)  # Friday +3
        assert result == date(2025, 6, 18)  # Wednesday

    def test_t_plus_7_spans_full_week(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 9), 7)  # Monday +7
        assert result == date(2025, 6, 18)  # Next Wednesday

    def test_t_plus_1_on_saturday_snaps_forward(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 14), 1)  # Saturday +1
        assert result == date(2025, 6, 17)  # Tuesday (Monday=snap + 1)

    def test_offset_zero_returns_nearest_trading_day(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 14), 0)  # Saturday
        assert result == date(2025, 6, 16)  # Monday

    def test_negative_offset(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 16), -1)  # Monday -1
        assert result == date(2025, 6, 13)  # Friday

    def test_offset_across_holiday(self, cal):
        # July 3 2025 (Thu) + 1 should skip July 4 (holiday) -> July 7 (Mon)
        result = cal.trading_day_offset(date(2025, 7, 3), 1)
        assert result == date(2025, 7, 7)


class TestTradingDaysBetween:
    def test_monday_to_friday_is_5(self, cal):
        result = cal.trading_days_between(date(2025, 6, 9), date(2025, 6, 13))
        assert result == 5

    def test_friday_to_monday_is_2(self, cal):
        result = cal.trading_days_between(date(2025, 6, 13), date(2025, 6, 16))
        assert result == 2

    def test_same_day_trading_day_is_1(self, cal):
        result = cal.trading_days_between(date(2025, 6, 9), date(2025, 6, 9))
        assert result == 1

    def test_same_day_non_trading_is_0(self, cal):
        result = cal.trading_days_between(date(2025, 6, 14), date(2025, 6, 14))
        assert result == 0


class TestMarketHours:
    def test_next_market_close_during_hours(self, cal):
        # 2 PM UTC on a Monday (10 AM ET) -- market is open, close is 8 PM UTC (4 PM ET)
        dt = datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc)
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 16)

    def test_next_market_close_after_hours(self, cal):
        # 9 PM UTC on Monday (5 PM ET) -- after close, next close is Tuesday
        dt = datetime(2025, 6, 16, 21, 0, 0, tzinfo=timezone.utc)
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 17)

    def test_next_market_close_on_weekend(self, cal):
        dt = datetime(2025, 6, 14, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 16)  # Monday's close

    def test_is_market_open_during_session(self, cal):
        # 2 PM UTC (10 AM ET) on a trading day
        dt = datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is True

    def test_is_market_open_after_close(self, cal):
        dt = datetime(2025, 6, 16, 21, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is False

    def test_is_market_open_on_weekend(self, cal):
        dt = datetime(2025, 6, 14, 14, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is False


class TestSessionTimes:
    def test_session_open_time_returns_datetime(self, cal):
        result = cal.session_open_time(date(2025, 6, 16))  # Monday
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_session_close_time_returns_datetime(self, cal):
        result = cal.session_close_time(date(2025, 6, 16))  # Monday
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_session_open_time_non_trading_day_returns_none(self, cal):
        assert cal.session_open_time(date(2025, 6, 14)) is None  # Saturday

    def test_session_close_time_non_trading_day_returns_none(self, cal):
        assert cal.session_close_time(date(2025, 6, 14)) is None  # Saturday


class TestCalendarDaysForTradingDays:
    def test_5_trading_days(self, cal):
        result = cal.calendar_days_for_trading_days(5)
        assert result == 9  # 7 + 2 buffer

    def test_1_trading_day(self, cal):
        result = cal.calendar_days_for_trading_days(1)
        assert result == 3  # 1 + 2 buffer

    def test_30_trading_days(self, cal):
        result = cal.calendar_days_for_trading_days(30)
        assert result == 44  # 6*7 + 0 + 2


class TestNaiveFallbacks:
    """Test that fallback methods work when exchange_calendars fails."""

    def test_naive_next_trading_day_skips_weekend(self):
        result = MarketCalendar._naive_next_trading_day(date(2025, 6, 13))
        assert result == date(2025, 6, 16)

    def test_naive_previous_trading_day_skips_weekend(self):
        result = MarketCalendar._naive_previous_trading_day(date(2025, 6, 16))
        assert result == date(2025, 6, 13)

    def test_naive_offset_forward(self):
        result = MarketCalendar._naive_offset(date(2025, 6, 13), 3)
        assert result == date(2025, 6, 18)

    def test_naive_offset_backward(self):
        result = MarketCalendar._naive_offset(date(2025, 6, 16), -1)
        assert result == date(2025, 6, 13)

    def test_ensure_utc_naive_datetime(self):
        dt = datetime(2025, 6, 16, 14, 0, 0)
        result = MarketCalendar._ensure_utc(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 14

    def test_ensure_utc_aware_datetime(self):
        dt = datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc)
        result = MarketCalendar._ensure_utc(dt)
        assert result.tzinfo == timezone.utc


class TestNearestTradingDay:
    def test_trading_day_returns_same(self, cal):
        result = cal.nearest_trading_day(date(2025, 6, 16))  # Monday
        assert result == date(2025, 6, 16)

    def test_weekend_returns_next_monday(self, cal):
        result = cal.nearest_trading_day(date(2025, 6, 14))  # Saturday
        assert result == date(2025, 6, 16)  # Monday
