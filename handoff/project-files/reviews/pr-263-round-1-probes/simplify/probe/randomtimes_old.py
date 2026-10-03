"""Random times (Gate 0 v1): 100 per post, each a random minute in the post's New York
weekday and hour on a random date in the sample that falls on that weekday. Each post's
draw is seeded from its key alone, so it never depends on what else is in the run."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

from engine.backtest import gate

NEW_YORK = ZoneInfo("America/New_York")
Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]


def bucket(posted_at: datetime) -> int:
    """A post's New York weekday (0 is Monday) and hour, as weekday * 24 + hour."""
    local = posted_at.astimezone(NEW_YORK)
    return local.weekday() * 24 + local.hour


class RandomTimes:
    """Draws for one sample period (its first and last New York date, inclusive)."""

    def __init__(self, first: date, last: date, per_post: int = gate.RANDOM_TIMES) -> None:
        self.per_post = per_post
        days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
        self.by_weekday = [
            np.array([i for i, day in enumerate(days) if day.weekday() == w], dtype=np.int64)
            for w in range(7)
        ]
        # The local hour's start on each date, as zoneinfo reads it (a time that doesn't
        # exist, or happens twice, at a daylight-saving change takes fold 0); a minute in
        # that hour is this plus 60 s a minute.
        self.hour_starts = np.array(
            [
                [
                    datetime(d.year, d.month, d.day, hour, tzinfo=NEW_YORK).timestamp()
                    for hour in range(24)
                ]
                for d in days
            ],
            dtype=np.float64,
        )

    def draw(self, key: str, post_bucket: int) -> Floats:
        """`per_post` random times (seconds since the epoch) for one post."""
        weekday, hour = divmod(post_bucket, 24)
        pool = self.by_weekday[weekday]
        rng = np.random.default_rng(gate.seed("random-times", key))
        picks = pool[rng.integers(0, len(pool), self.per_post)]
        minutes = rng.integers(0, 60, self.per_post)
        result: Floats = self.hour_starts[picks, hour] + minutes * 60.0
        return result

    def draw_all(self, keys: Sequence[str], buckets: Ints) -> Floats:
        """One row of random times per post."""
        if not len(keys):
            return np.zeros((0, self.per_post))
        return np.stack([self.draw(key, int(b)) for key, b in zip(keys, buckets, strict=True)])


def bucket_medians(values: Floats, buckets: Ints) -> dict[int, tuple[int, float | None]]:
    """Per bucket: how many values there are (NaN left out) and their median. `values`
    has one row of random-time moves per post; `buckets` one bucket per post."""
    flat = values.ravel()
    each = np.repeat(buckets, values.shape[1]) if values.ndim == 2 else buckets
    keep = np.isfinite(flat)
    flat, each = flat[keep], each[keep]
    if not len(flat):
        return {}
    order = np.argsort(each, kind="stable")
    flat, each = flat[order], each[order]
    found, starts = np.unique(each, return_index=True)
    result: dict[int, tuple[int, float | None]] = {}
    for b, part in zip(found, np.split(flat, starts[1:]), strict=True):
        result[int(b)] = (len(part), float(np.median(part)))
    return result
