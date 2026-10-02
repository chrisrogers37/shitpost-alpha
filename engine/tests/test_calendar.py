from datetime import UTC, date, datetime

import pytest

from engine.market.calendar import (
    is_open,
    is_session,
    next_open,
    session_close,
    session_on_or_after,
    session_open,
    trading_days_after,
)


def utc(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def test_a_holiday_is_not_a_session() -> None:
    assert not is_session(date(2024, 7, 4))
    assert not is_open(utc(2024, 7, 4, 16))
    assert session_on_or_after(utc(2024, 7, 4, 16)) == date(2024, 7, 5)
    assert trading_days_after(date(2024, 7, 3), 1) == date(2024, 7, 5)
    assert trading_days_after(date(2024, 7, 5), -1) == date(2024, 7, 3)
    with pytest.raises(ValueError, match="not an XNYS session"):
        session_close(date(2024, 7, 4))


def test_a_half_day_closes_at_one_new_york_time() -> None:
    assert session_close(date(2024, 11, 29)) == utc(2024, 11, 29, 18)  # 13:00 EST
    assert is_open(utc(2024, 11, 29, 17, 59, 59))
    assert not is_open(utc(2024, 11, 29, 18))
    assert session_on_or_after(utc(2024, 11, 29, 18, 30)) == date(2024, 12, 2)


@pytest.mark.parametrize(
    ("session", "opens", "closes"),
    [
        (date(2024, 3, 8), utc(2024, 3, 8, 14, 30), utc(2024, 3, 8, 21)),  # EST
        (date(2024, 3, 11), utc(2024, 3, 11, 13, 30), utc(2024, 3, 11, 20)),  # EDT from 3-10
        (date(2024, 11, 1), utc(2024, 11, 1, 13, 30), utc(2024, 11, 1, 20)),  # EDT
        (date(2024, 11, 4), utc(2024, 11, 4, 14, 30), utc(2024, 11, 4, 21)),  # EST from 11-3
    ],
)
def test_daylight_saving_changes_move_the_utc_hours(
    session: date, opens: datetime, closes: datetime
) -> None:
    assert (session_open(session), session_close(session)) == (opens, closes)
    assert is_open(opens) and not is_open(closes)


def test_the_session_on_or_after_a_time() -> None:
    assert session_on_or_after(utc(2024, 7, 10, 12)) == date(2024, 7, 10)  # before the open
    assert session_on_or_after(utc(2024, 7, 10, 15)) == date(2024, 7, 10)  # open
    assert session_on_or_after(utc(2024, 7, 10, 20)) == date(2024, 7, 11)  # at the close
    assert session_on_or_after(utc(2024, 7, 13, 15)) == date(2024, 7, 15)  # Saturday
    with pytest.raises(ValueError, match="no timezone"):
        session_on_or_after(datetime(2024, 7, 10, 12))


def test_next_open() -> None:
    monday = utc(2024, 7, 15, 13, 30)
    assert next_open(utc(2024, 7, 13, 15)) == monday  # from a Saturday
    assert next_open(monday) == monday
    assert next_open(utc(2024, 7, 15, 13, 31)) == utc(2024, 7, 16, 13, 30)
    assert next_open(utc(2024, 7, 3, 21)) == utc(2024, 7, 5, 13, 30)  # over a holiday
