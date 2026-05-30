"""Feed API router — single-post-at-a-time endpoint."""

from fastapi import APIRouter, HTTPException, Query, Request

from api.rate_limit import limiter
from api.schemas.feed import FeedResponse
from api.services.feed_service import FeedService

router = APIRouter()
_service = FeedService()


@router.get("/latest", response_model=FeedResponse)
@limiter.limit("60/minute")
def get_latest_post(request: Request):
    """Get the most recent analyzed shitpost."""
    result = _service.get_feed_response(0)
    if result is None:
        raise HTTPException(status_code=404, detail="No post found at this offset")
    return result


@router.get("/at", response_model=FeedResponse)
@limiter.limit("60/minute")
def get_post_at_offset(request: Request, offset: int = Query(default=0, ge=0)):
    """Get the Nth most recent analyzed shitpost."""
    result = _service.get_feed_response(offset)
    if result is None:
        raise HTTPException(status_code=404, detail="No post found at this offset")
    return result
