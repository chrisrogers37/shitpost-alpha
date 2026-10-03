"""List responses: {stream_id, items, next_before}, paged with ?before=<cursor>&limit=.

A route fetches `limit + 1` rows ordered by its sort key, newest first, below the
`before` key if there is one, then calls take_page. The cursor is opaque to clients: the
URL-safe base64 of the sort key (a list of integers, such as [id])."""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from engine.web.errors import ApiError
from engine.web.models import ApiModel, ApiResponse

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
_BIGINT = range(-(2**63), 2**63)

SortKey = tuple[int, ...]


class Page[ItemT: ApiModel](ApiResponse):
    items: list[ItemT]
    next_before: str | None
    """Pass as `before` to get the next page; null on the last page."""


def encode_cursor(key: SortKey) -> str:
    raw = json.dumps(list(key), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str, size: int) -> SortKey:
    """The sort key in `cursor`, which must hold `size` integers. Anything else is a 400."""
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (binascii.Error, ValueError):  # ValueError covers bad JSON and bad UTF-8
        key = None
    if (
        not isinstance(key, list)
        or len(key) != size
        or not all(type(part) is int and part in _BIGINT for part in key)
        or encode_cursor(tuple(key)) != cursor  # one spelling per key
    ):
        raise ApiError("bad_request", "before: not a cursor from this list")
    return tuple(key)


@dataclass(frozen=True)
class PageQuery:
    """?before=<cursor>&limit=. Take it as a `page: PageParams` parameter."""

    before: str | None
    limit: int

    def before_key(self, size: int) -> SortKey | None:
        """The decoded `before` cursor, or None for the first page."""
        return None if self.before is None else decode_cursor(self.before, size)


def _page_query(
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PageQuery:
    return PageQuery(before, limit)


PageParams = Annotated[PageQuery, Depends(_page_query)]
"""A dependency, not a query model: FastAPI reads a query model's fields only when it is a
route's only query parameter, and a list route usually takes filters too."""


def take_page[RowT](
    rows: Sequence[RowT], limit: int, key: Callable[[RowT], SortKey]
) -> tuple[list[RowT], str | None]:
    """Split rows fetched with LIMIT limit + 1 into this page and the next page's cursor."""
    page = list(rows[:limit])
    return page, encode_cursor(key(page[-1])) if len(rows) > limit else None
