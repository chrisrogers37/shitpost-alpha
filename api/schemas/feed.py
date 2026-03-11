"""Pydantic response models for the feed API."""

from pydantic import BaseModel
from typing import Optional


class Engagement(BaseModel):
    replies: int = 0
    reblogs: int = 0
    favourites: int = 0
    upvotes: int = 0
    downvotes: int = 0


class Post(BaseModel):
    shitpost_id: str
    text: str
    content_html: Optional[str] = None
    timestamp: str
    username: str
    url: Optional[str] = None
    engagement: Engagement


class Scores(BaseModel):
    engagement: Optional[float] = None
    viral: Optional[float] = None
    sentiment: Optional[float] = None
    urgency: Optional[float] = None


class Prediction(BaseModel):
    prediction_id: int
    confidence: Optional[float] = None
    thesis: Optional[str] = None
    assets: list[str] = []
    market_impact: dict[str, str] = {}
    scores: Scores


class Returns(BaseModel):
    same_day: Optional[float] = None
    hour_1: Optional[float] = None
    t1: Optional[float] = None
    t3: Optional[float] = None
    t7: Optional[float] = None
    t30: Optional[float] = None


class Correct(BaseModel):
    same_day: Optional[bool] = None
    hour_1: Optional[bool] = None
    t1: Optional[bool] = None
    t3: Optional[bool] = None
    t7: Optional[bool] = None
    t30: Optional[bool] = None


class Pnl(BaseModel):
    same_day: Optional[float] = None
    hour_1: Optional[float] = None
    t1: Optional[float] = None
    t3: Optional[float] = None
    t7: Optional[float] = None
    t30: Optional[float] = None


class Outcome(BaseModel):
    symbol: str
    sentiment: Optional[str] = None
    confidence: Optional[float] = None
    price_at_prediction: Optional[float] = None
    price_at_post: Optional[float] = None
    current_price: Optional[float] = None
    returns: Returns
    correct: Correct
    pnl: Pnl
    is_complete: bool = False


class Navigation(BaseModel):
    has_newer: bool
    has_older: bool
    current_offset: int
    total_posts: int


class FeedResponse(BaseModel):
    post: Post
    prediction: Prediction
    outcomes: list[Outcome]
    navigation: Navigation


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceResponse(BaseModel):
    symbol: str
    post_timestamp: Optional[str] = None
    candles: list[Candle]
    post_date_index: Optional[int] = None
