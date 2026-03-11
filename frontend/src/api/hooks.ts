/** React Query hooks for feed and price data. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { fetchFeedPost, fetchPriceData } from "./client";

export function useFeedPost(offset: number) {
  return useQuery({
    queryKey: ["feed", offset],
    queryFn: () => fetchFeedPost(offset),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}

export function usePriceData(
  symbol: string | undefined,
  days: number,
  postTimestamp?: string,
) {
  return useQuery({
    queryKey: ["prices", symbol, days, postTimestamp],
    queryFn: () => fetchPriceData(symbol!, days, postTimestamp),
    staleTime: 5 * 60_000,
    enabled: !!symbol,
  });
}

export function usePrefetchAdjacentPosts(
  currentOffset: number,
  hasNewer: boolean,
  hasOlder: boolean,
) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (hasNewer && currentOffset > 0) {
      queryClient.prefetchQuery({
        queryKey: ["feed", currentOffset - 1],
        queryFn: () => fetchFeedPost(currentOffset - 1),
        staleTime: 60_000,
      });
    }
    if (hasOlder) {
      queryClient.prefetchQuery({
        queryKey: ["feed", currentOffset + 1],
        queryFn: () => fetchFeedPost(currentOffset + 1),
        staleTime: 60_000,
      });
    }
  }, [currentOffset, hasNewer, hasOlder, queryClient]);
}
