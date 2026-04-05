/** API client — fetch wrapper with base URL handling. */

import type { FeedResponse, LiveQuote, PriceResponse } from "../types/api";

const BASE_URL = "";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function fetchFeedPost(offset: number): Promise<FeedResponse> {
  return fetchJson<FeedResponse>(`/api/feed/at?offset=${offset}`);
}

export function fetchPriceData(
  symbol: string,
  days: number,
  postTimestamp?: string,
): Promise<PriceResponse> {
  const params = new URLSearchParams({ days: String(days) });
  if (postTimestamp) params.set("post_timestamp", postTimestamp);
  return fetchJson<PriceResponse>(`/api/prices/${symbol}?${params}`);
}

export function fetchLiveQuote(symbol: string): Promise<LiveQuote> {
  return fetchJson<LiveQuote>(`/api/prices/${symbol}/live`);
}
