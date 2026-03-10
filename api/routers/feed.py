"""Feed API router — single-post-at-a-time endpoint."""

from fastapi import APIRouter, HTTPException, Query

from api.queries.feed_queries import (
    get_analyzed_post_at_offset,
    get_outcomes_for_prediction,
    get_total_analyzed_posts,
)
from api.schemas.feed import (
    Correct,
    Engagement,
    FeedResponse,
    Navigation,
    Outcome,
    Pnl,
    Post,
    Prediction,
    Returns,
    Scores,
)

router = APIRouter()


def _build_feed_response(offset: int) -> FeedResponse:
    """Build a complete feed response for a given offset."""
    row = get_analyzed_post_at_offset(offset)
    if row is None:
        raise HTTPException(status_code=404, detail="No post found at this offset")

    total = get_total_analyzed_posts()
    outcomes_raw = get_outcomes_for_prediction(row["prediction_id"])

    # Build post
    post = Post(
        shitpost_id=row["shitpost_id"],
        text=row["text"] or "",
        content_html=row.get("content_html"),
        timestamp=row["timestamp"].isoformat()
        if hasattr(row["timestamp"], "isoformat")
        else str(row["timestamp"]),
        username=row["username"] or "",
        url=row.get("url"),
        engagement=Engagement(
            replies=row.get("replies_count") or 0,
            reblogs=row.get("reblogs_count") or 0,
            favourites=row.get("favourites_count") or 0,
            upvotes=row.get("upvotes_count") or 0,
            downvotes=row.get("downvotes_count") or 0,
        ),
    )

    # Build prediction
    assets = row.get("assets") or []
    market_impact = row.get("market_impact") or {}

    prediction = Prediction(
        prediction_id=row["prediction_id"],
        confidence=row.get("confidence"),
        thesis=row.get("thesis"),
        assets=assets if isinstance(assets, list) else [],
        market_impact=market_impact if isinstance(market_impact, dict) else {},
        scores=Scores(
            engagement=row.get("engagement_score"),
            viral=row.get("viral_score"),
            sentiment=row.get("sentiment_score"),
            urgency=row.get("urgency_score"),
        ),
    )

    # Build outcomes
    outcomes = []
    for o in outcomes_raw:
        outcomes.append(
            Outcome(
                symbol=o["symbol"],
                sentiment=o.get("prediction_sentiment"),
                confidence=o.get("prediction_confidence"),
                price_at_prediction=o.get("price_at_prediction"),
                price_at_post=o.get("price_at_post"),
                returns=Returns(
                    same_day=o.get("return_same_day"),
                    hour_1=o.get("return_1h"),
                    t1=o.get("return_t1"),
                    t3=o.get("return_t3"),
                    t7=o.get("return_t7"),
                    t30=o.get("return_t30"),
                ),
                correct=Correct(
                    same_day=o.get("correct_same_day"),
                    hour_1=o.get("correct_1h"),
                    t1=o.get("correct_t1"),
                    t3=o.get("correct_t3"),
                    t7=o.get("correct_t7"),
                    t30=o.get("correct_t30"),
                ),
                pnl=Pnl(
                    same_day=o.get("pnl_same_day"),
                    hour_1=o.get("pnl_1h"),
                    t1=o.get("pnl_t1"),
                    t3=o.get("pnl_t3"),
                    t7=o.get("pnl_t7"),
                    t30=o.get("pnl_t30"),
                ),
                is_complete=o.get("is_complete", False) or False,
            )
        )

    navigation = Navigation(
        has_newer=offset > 0,
        has_older=offset < total - 1,
        current_offset=offset,
        total_posts=total,
    )

    return FeedResponse(
        post=post,
        prediction=prediction,
        outcomes=outcomes,
        navigation=navigation,
    )


@router.get("/latest", response_model=FeedResponse)
def get_latest_post():
    """Get the most recent analyzed shitpost."""
    return _build_feed_response(0)


@router.get("/at", response_model=FeedResponse)
def get_post_at_offset(offset: int = Query(default=0, ge=0)):
    """Get the Nth most recent analyzed shitpost."""
    return _build_feed_response(offset)
