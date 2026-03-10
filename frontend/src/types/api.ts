/** TypeScript interfaces matching the FastAPI response schemas. */

export interface Engagement {
  replies: number;
  reblogs: number;
  favourites: number;
  upvotes: number;
  downvotes: number;
}

export interface Post {
  shitpost_id: string;
  text: string;
  content_html: string | null;
  timestamp: string;
  username: string;
  url: string | null;
  engagement: Engagement;
}

export interface Scores {
  engagement: number | null;
  viral: number | null;
  sentiment: number | null;
  urgency: number | null;
}

export interface Prediction {
  prediction_id: number;
  confidence: number | null;
  thesis: string | null;
  assets: string[];
  market_impact: Record<string, string>;
  scores: Scores;
}

export interface Returns {
  same_day: number | null;
  hour_1: number | null;
  t1: number | null;
  t3: number | null;
  t7: number | null;
  t30: number | null;
}

export interface Correct {
  same_day: boolean | null;
  hour_1: boolean | null;
  t1: boolean | null;
  t3: boolean | null;
  t7: boolean | null;
  t30: boolean | null;
}

export interface Pnl {
  same_day: number | null;
  hour_1: number | null;
  t1: number | null;
  t3: number | null;
  t7: number | null;
  t30: number | null;
}

export interface Outcome {
  symbol: string;
  sentiment: string | null;
  confidence: number | null;
  price_at_prediction: number | null;
  price_at_post: number | null;
  current_price: number | null;
  returns: Returns;
  correct: Correct;
  pnl: Pnl;
  is_complete: boolean;
}

export interface Navigation {
  has_newer: boolean;
  has_older: boolean;
  current_offset: number;
  total_posts: number;
}

export interface FeedResponse {
  post: Post;
  prediction: Prediction;
  outcomes: Outcome[];
  navigation: Navigation;
}

export interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceResponse {
  symbol: string;
  post_timestamp: string | null;
  candles: Candle[];
  post_date_index: number | null;
}
